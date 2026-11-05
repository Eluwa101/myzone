import datetime
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.controllers import customer_controller, transaction_controller
from app.models.custom_form import CustomForm, FormSubmission, generate_public_token
from app.models.customer import Customer
from app.schemas.customer import CustomerCreate
from app.schemas.form import CUSTOMER_FIELD_KEYS, TRANSACTION_FIELD_KEYS, FormCreate, FormUpdate
from app.schemas.transaction import TransactionCreate


class FormNotFoundError(Exception):
    pass


class MissingRequiredFieldsError(Exception):
    def __init__(self, missing: list[str]):
        self.missing = missing


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


def _upsert_customer(db: Session, org_id: UUID, data: CustomerCreate) -> tuple[Customer, bool]:
    """Same "fill in blanks, merge extra" behavior as CSV import - there's
    no human on a public submission to resolve a duplicate conflict, so a
    likely-duplicate is merged into automatically rather than creating a
    second record."""
    match = customer_controller.find_match(db, org_id, data.model_dump())
    if match:
        for field in ["phone", "email", "job", "nationality", "pet", "address", "notes", "interests"]:
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


def submit_public_form(db: Session, token: str, payload: dict[str, str]) -> tuple[FormSubmission, bool, bool]:
    form = get_public_form(db, token)

    missing = [f["label"] for f in form.fields if f.get("required") and not str(payload.get(f["key"], "")).strip()]
    if missing:
        raise MissingRequiredFieldsError(missing)

    customer_fields: dict[str, str] = {}
    transaction_fields: dict[str, str] = {}
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
        elif category == "custom":
            extra[f["label"]] = value

    data = CustomerCreate(name=customer_fields.get("name", ""), **{k: v for k, v in customer_fields.items() if k != "name"}, extra=extra)
    customer, created = _upsert_customer(db, form.org_id, data)

    transaction_logged = _log_submission_transaction(db, form.org_id, customer.id, transaction_fields)

    submission = FormSubmission(form_id=form.id, org_id=form.org_id, customer_id=customer.id, raw_payload=payload)
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission, created, transaction_logged
