from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.agent.segment_suggest import SegmentSuggestionError, suggest_segment_filters, suggest_segment_sql
from app.controllers import segment_controller
from app.controllers.segment_fields import FIELD_REGISTRY, OPERATORS_BY_TYPE, list_custom_field_keys
from app.controllers.segment_sql import SegmentSQLError, run_sql_segment, sandbox_schema, schema_as_text
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.segment import (
    SegmentCreate,
    SegmentFieldOut,
    SegmentFieldsOut,
    SegmentFilters,
    SegmentOut,
    SandboxTableOut,
    SegmentResult,
    SegmentSQLRequest,
    SegmentSQLSuggestion,
    SegmentSQLSuggestRequest,
    SegmentSuggestRequest,
    SegmentUpdate,
)

router = APIRouter(prefix="/api/segments", tags=["segments"])


@router.get("/fields", response_model=SegmentFieldsOut)
def get_fields(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return SegmentFieldsOut(
        fields=[SegmentFieldOut(key=f.key, label=f.label, type=f.type, choices=f.choices) for f in FIELD_REGISTRY.values()],
        operators_by_type=OPERATORS_BY_TYPE,
        custom_fields=list_custom_field_keys(db, current_user.org_id),
    )


@router.post("/suggest", response_model=SegmentFilters)
def suggest_filters(data: SegmentSuggestRequest, current_user: User = Depends(get_current_user)):
    try:
        return suggest_segment_filters(data.description)
    except SegmentSuggestionError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Couldn't turn that into filters - try describing it more simply.",
        )


def _sql_error(e: SegmentSQLError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))


@router.get("/sql/schema", response_model=list[SandboxTableOut])
def get_sql_schema(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return sandbox_schema(db, current_user.org_id)


@router.post("/sql/preview", response_model=SegmentResult)
def preview_sql_segment(data: SegmentSQLRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        members = run_sql_segment(db, current_user.org_id, data.sql)
    except SegmentSQLError as e:
        raise _sql_error(e)
    return SegmentResult(total=len(members), members=members)


@router.post("/sql/suggest", response_model=SegmentSQLSuggestion)
def suggest_sql(data: SegmentSQLSuggestRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    schema_text = schema_as_text(sandbox_schema(db, current_user.org_id))
    try:
        return SegmentSQLSuggestion(sql=suggest_segment_sql(data.description, schema_text, data.current_sql))
    except SegmentSuggestionError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Couldn't write a query for that - try describing it differently.",
        )


@router.get("", response_model=list[SegmentOut])
def list_segments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return segment_controller.list_segments(db, current_user.org_id)


@router.post("", response_model=SegmentOut, status_code=status.HTTP_201_CREATED)
def create_segment(data: SegmentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return segment_controller.create_segment(db, current_user.org_id, data)
    except SegmentSQLError as e:
        raise _sql_error(e)


@router.post("/preview", response_model=SegmentResult)
def preview_segment(filters: SegmentFilters, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    members = segment_controller.resolve_members(db, current_user.org_id, filters)
    return SegmentResult(total=len(members), members=members)


@router.get("/{segment_id}", response_model=SegmentOut)
def get_segment(segment_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return segment_controller.get_segment(db, current_user.org_id, segment_id)
    except segment_controller.SegmentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found.")


@router.patch("/{segment_id}", response_model=SegmentOut)
def update_segment(
    segment_id: UUID,
    data: SegmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return segment_controller.update_segment(db, current_user.org_id, segment_id, data)
    except segment_controller.SegmentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found.")
    except SegmentSQLError as e:
        raise _sql_error(e)


@router.delete("/{segment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_segment(segment_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        segment_controller.delete_segment(db, current_user.org_id, segment_id)
    except segment_controller.SegmentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{segment_id}/members", response_model=SegmentResult)
def get_segment_members(segment_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        segment = segment_controller.get_segment(db, current_user.org_id, segment_id)
    except segment_controller.SegmentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found.")
    try:
        members = segment_controller.resolve_segment(db, segment)
    except SegmentSQLError as e:
        raise _sql_error(e)
    return SegmentResult(total=len(members), members=members)
