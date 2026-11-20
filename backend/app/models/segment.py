import datetime
import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, Uuid as UUID, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Segment(Base):
    __tablename__ = "segments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), index=True)

    name: Mapped[str] = mapped_column(String(200))
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    # when set, the segment is defined by this SQL (run in a per-org
    # sandbox - see segment_sql.py) and `filters` is ignored
    sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    # When the member list was last (re)run against the definition. A segment is a
    # SNAPSHOT: the list below stays as it is until someone adds new matches or reruns
    # it. NULL = never run (a segment from before snapshots) - run on first use.
    refreshed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    member_rows = relationship("SegmentMember", cascade="all, delete-orphan", lazy="selectin")

    @property
    def member_count(self) -> int:
        return len(self.member_rows)


class SegmentMember(Base):
    """One customer in a segment's stored list."""

    __tablename__ = "segment_members"

    segment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("segments.id"), primary_key=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), primary_key=True, index=True)
    added_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
