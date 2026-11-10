import datetime
import hashlib
import hmac
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.controllers import customer_controller, notification_controller, order_controller, transaction_controller
from app.models.custom_form import CustomForm, FormSubmission, generate_public_token, generate_webhook_secret
from app.models.customer import Customer
from app.models.organization import Organization
from app.schemas.customer import CustomerCreate
from app.schemas.form import CUSTOMER_FIELD_KEYS, ORDER_FIELD_KEYS, TRANSACTION_FIELD_KEYS, FormCreate, FormUpdate
from app.schemas.order import OrderCreate, OrderItem
from app.schemas.transaction import TransactionCreate


class FormNotFoundError(Exception):
    pass


class MissingRequiredFieldsError(Exception):
    def __init__(self, missing: list[str]):
        self.missing = missing


class InvalidSignatureError(Exception):
    pass


def create_form(db: Session, org_id: UUID, data: FormCreate) -> CustomForm:
    form = CustomForm(org_id=org_id, name=data.name, fields=[f.model_dump() for f in data.fields])
    db.add(form)
    db.commit()
    db.refresh(form)
    return form


def list_forms(db: Session, org_id: UUID) -> list[CustomForm]:
    return db.query(CustomForm).filter(CustomForm.org_id == org_id).order_by(CustomForm.created_at.desc()).all()


def get_form(db: Session, org_id: UUID, form_id: UUID) -> CustomForm:
    form = db.query(CustomForm).filter(CustomForm.org_id == org_id, CustomForm.id == form_id).first()
    if not form:
        raise FormNotFoundError()
    return form


def update_form(db: Session, org_id: UUID, form_id: UUID, data: FormUpdate) -> CustomForm:
    form = get_form(db, org_id, form_id)
    if data.name is not None:
        form.name = data.name
    if data.fields is not None:
        form.fields = [f.model_dump() for f in data.fields]
    if data.is_active is not None:
        form.is_active = data.is_active
    if data.regenerate_token:
        form.public_token = generate_public_token()
    if data.enable_signing:
        form.webhook_secret = generate_webhook_secret()
    elif data.disable_signing:
        form.webhook_secret = None
    db.commit()
    db.refresh(form)
    return form


def delete_form(db: Session, org_id: UUID, form_id: UUID) -> None:
    form = get_form(db, org_id, form_id)
    db.delete(form)
    db.commit()


def list_submissions(db: Session, org_id: UUID, form_id: UUID) -> list[FormSubmission]:
    get_form(db, org_id, form_id)  # raises FormNotFoundError if not owned by this org
    return (
        db.query(FormSubmission)
        .options(joinedload(FormSubmission.customer))
        .filter(FormSubmission.org_id == org_id, FormSubmission.form_id == form_id)
        .order_by(FormSubmission.created_at.desc())
        .all()
    )


# --- public: no auth, driven entirely by the unguessable public_token -----


def get_public_form(db: Session, token: str) -> CustomForm:
    form = db.query(CustomForm).filter(CustomForm.public_token == token).first()
    if not form or not form.is_active:
        raise FormNotFoundError()
    return form


def get_public_form_business_name(db: Session, form: CustomForm) -> str | None:
    """The business identity to show a customer filling out this form -
    the org's own business-profile name if they've set one (Settings ->
    Business profile), falling back to the org's account name."""
    org = db.query(Organization).options(joinedload(Organization.settings)).filter(Organization.id == form.org_id).first()
    if org is None:
        return None
    if org.settings and org.settings.biz_name:
        return org.settings.biz_name
    return org.name


def _upsert_customer(db: Session, org_id: UUID, data: CustomerCreate) -> tuple[Customer, bool]:
    """Same "fill in blanks, merge extra" behavior as CSV import - there's
    no human on a public submission to resolve a duplicate conflict, so a
    likely-duplicate is merged into automatically rather than creating a
    second record."""
    match = customer_controller.find_match(db, org_id, data.model_dump())
    if match:
        for field in ["first_name", "last_name", "phone", "email", "job", "nationality", "pet", "address", "notes", "interests"]:
            value = getattr(data, field, None)
            if value and not getattr(match, field, None):
                setattr(match, field, value)
        match.extra = {**(data.extra or {}), **(match.extra or {})}
        customer_controller.recompute_derived_fields(match)
        db.commit()
        db.refresh(match)
        return match, False
    customer = customer_controller.create_customer(db, org_id, data, force=True)
    return customer, True


def _log_submission_transaction(db: Session, org_id: UUID, customer_id: UUID, tx_fields: dict[str, str]) -> bool:
    """A transaction only gets logged if the submission actually included
    both an item and an amount - the two fields Transaction itself
    requires. Anything else (date/qty/currency) is optional and defaults
    the same way the add_transaction agent tool does."""
    item = tx_fields.get("tx_item")
    amount_raw = tx_fields.get("tx_amount")
    if not item or not amount_raw:
        return False
    try:
        amount = float(amount_raw)
    except ValueError:
        return False
    qty_raw = tx_fields.get("tx_qty")
    try:
        qty = float(qty_raw) if qty_raw else 1
    except ValueError:
        qty = 1
    tx_date = tx_fields.get("tx_date") or datetime.date.today().isoformat()
    transaction_controller.add_transaction(
        db, org_id, customer_id,
        TransactionCreate(date=tx_date, item=item, qty=qty, amount=amount, currency=(tx_fields.get("tx_currency") or "").upper()),
    )
    return True


def _log_submission_order(db: Session, org_id: UUID, customer_id: UUID, order_fields: dict[str, str]) -> bool:
    """Mirrors _log_submission_transaction: an order only gets logged if the
    submission actually named an item - everything else is optional."""
    item = order_fields.get("order_item")
    if not item:
        return False
    qty_raw = order_fields.get("order_qty")
    try:
        qty = float(qty_raw) if qty_raw else 1
    except ValueError:
        qty = 1
    price_raw = order_fields.get("order_price")
    try:
        price = float(price_raw) if price_raw else None
    except ValueError:
        price = None
    order_date = order_fields.get("order_date") or datetime.date.today().isoformat()
    order_controller.create_order(
        db, org_id, customer_id,
        OrderCreate(
            order_date=order_date,
            delivery_date=order_fields.get("order_delivery_date") or None,
            items=[OrderItem(name=item, qty=qty, price=price)],
            amount=(qty * price) if price is not None else None,
            currency=(order_fields.get("order_currency") or "").upper() or None,
        ),
    )
    return True


def submit_public_form(
    db: Session, token: str, payload: dict, raw_body: bytes = b"", signature: str | None = None
) -> tuple[FormSubmission, bool, bool, bool]:
    form = get_public_form(db, token)

    if form.webhook_secret:
        expected = hmac.new(form.webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()
        if not signature or not hmac.compare_digest(expected, signature):
            raise InvalidSignatureError()

    missing = [f["label"] for f in form.fields if f.get("required") and not str(payload.get(f["key"], "")).strip()]
    if missing:
        raise MissingRequiredFieldsError(missing)

    customer_fields: dict[str, str] = {}
    transaction_fields: dict[str, str] = {}
    order_fields: dict[str, str] = {}
    extra: dict[str, str] = {}
    for f in form.fields:
        value = payload.get(f["key"])
        if value is None or not str(value).strip():
            continue
        value = str(value).strip()
        category = f.get("category", "custom")
        if category == "customer" and f["key"] in CUSTOMER_FIELD_KEYS:
            customer_fields[f["key"]] = value
        elif category == "transaction" and f["key"] in TRANSACTION_FIELD_KEYS:
            transaction_fields[f["key"]] = value
        elif category == "order" and f["key"] in ORDER_FIELD_KEYS:
            order_fields[f["key"]] = value
        elif category == "custom":
            extra[f["label"]] = value

    data = CustomerCreate(**customer_fields, extra=extra)
    customer, created = _upsert_customer(db, form.org_id, data)

    transaction_logged = _log_submission_transaction(db, form.org_id, customer.id, transaction_fields)
    order_logged = _log_submission_order(db, form.org_id, customer.id, order_fields)

    submission = FormSubmission(form_id=form.id, org_id=form.org_id, customer_id=customer.id, raw_payload=payload)
    db.add(submission)
    db.commit()
    db.refresh(submission)
    notification_controller.create_notification(
        db,
        form.org_id,
        "form.submission",
        f"New submission via {form.name}: {customer.name}",
        link=f"/customers/{customer.id}",
    )
    return submission, created, transaction_logged, order_logged
