from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.agent.segment_suggest import SegmentSuggestionError, suggest_segment_filters
from app.controllers import segment_controller
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.segment import SegmentCreate, SegmentFilters, SegmentOut, SegmentResult, SegmentSuggestRequest, SegmentUpdate

router = APIRouter(prefix="/api/segments", tags=["segments"])


@router.post("/suggest", response_model=SegmentFilters)
def suggest_filters(data: SegmentSuggestRequest, current_user: User = Depends(get_current_user)):
    try:
        return suggest_segment_filters(data.description)
    except SegmentSuggestionError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Couldn't turn that into filters - try describing it more simply.",
        )


@router.get("", response_model=list[SegmentOut])
def list_segments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return segment_controller.list_segments(db, current_user.org_id)


@router.post("", response_model=SegmentOut, status_code=status.HTTP_201_CREATED)
def create_segment(data: SegmentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return segment_controller.create_segment(db, current_user.org_id, data)


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
    members = segment_controller.resolve_members(db, current_user.org_id, SegmentFilters(**segment.filters))
    return SegmentResult(total=len(members), members=members)
