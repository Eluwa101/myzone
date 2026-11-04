from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.controllers import customer_controller
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.customer import CustomerStatus
from app.models.user import User
from app.schemas.customer import (
    CustomerCreate,
    CustomerListOut,
    CustomerOut,
    CustomerUpdate,
    DuplicateGroup,
    ImportResult,
    MergeRequest,
)

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.post("", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
def create_customer(
    data: CustomerCreate,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return customer_controller.create_customer(db, current_user.org_id, data, force=force)
    except customer_controller.DuplicateCustomerError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": f"This looks like an existing customer: {e.existing.name}.",
                "existing_id": str(e.existing.id),
            },
        )


@router.get("", response_model=CustomerListOut)
def list_customers(
    search: str | None = None,
    status_filter: CustomerStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = customer_controller.list_customers(
        db, current_user.org_id, search=search, status=status_filter, page=page, page_size=page_size
    )
    return CustomerListOut(items=items, total=total, page=page, page_size=page_size)


@router.get("/duplicates", response_model=list[DuplicateGroup])
def duplicates(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    groups = customer_controller.find_duplicate_groups(db, current_user.org_id)
    return [DuplicateGroup(keep=g[0], duplicates=g[1:]) for g in groups]


@router.post("/merge", response_model=CustomerOut)
def merge(data: MergeRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return customer_controller.merge_customers(db, current_user.org_id, data.keep_id, data.merge_id)
    except customer_controller.CustomerNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")


@router.post("/import", response_model=ImportResult)
def import_customers(
    csv_text: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return customer_controller.import_csv(db, current_user.org_id, csv_text)


@router.get("/export")
def export_customers(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    csv_text = customer_controller.export_csv(db, current_user.org_id)
    return Response(content=csv_text, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=customers.csv"})


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return customer_controller.get_customer(db, current_user.org_id, customer_id)
    except customer_controller.CustomerNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")


@router.patch("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: UUID,
    data: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return customer_controller.update_customer(db, current_user.org_id, customer_id, data)
    except customer_controller.CustomerNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(customer_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        customer_controller.delete_customer(db, current_user.org_id, customer_id)
    except customer_controller.CustomerNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
