import datetime
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.customer import CustomerStatus

Combinator = Literal["and", "or", "nor"]

Operator = Literal[
    "equals",
    "not_equals",
    "contains",
    "not_contains",
    "in_list",
    "not_in_list",
    "is_set",
    "is_not_set",
    "greater_than",
    "less_than",
    "between",
    "within_last_days",
    "over_days_ago",
]


class SegmentCondition(BaseModel):
    """One leaf test, e.g. {field: "status", operator: "equals", value: "lead"}.
    `field` is one of FIELD_REGISTRY's keys (see segment_fields.py), or
    "extra.<key>" for one of the org's own custom fields. value/value2/values
    are used depending on operator: most use `value`, "between" also uses
    `value2` as the upper bound, "in_list"/"not_in_list" use `values`."""

    type: Literal["condition"] = "condition"
    field: str = Field(min_length=1, max_length=120)
    operator: Operator
    value: str | float | bool | None = None
    value2: str | float | None = None
    values: list[str] | None = None


class SegmentGroup(BaseModel):
    """A combinator applied to a list of conditions and/or nested groups -
    the recursion is what lets the builder express arbitrary
    (A AND B) OR (C AND NOT D)-style queries. An empty group matches
    everyone (vacuously true), so a brand-new segment with no conditions
    yet previews as "everyone", matching the old default-filters behavior."""

    type: Literal["group"] = "group"
    combinator: Combinator = "and"
    conditions: list[Annotated[Union[SegmentCondition, "SegmentGroup"], Field(discriminator="type")]] = Field(default_factory=list)


SegmentGroup.model_rebuild()

# Public name kept stable - a segment's filters ARE a (possibly nested) group.
SegmentFilters = SegmentGroup


class SegmentSuggestRequest(BaseModel):
    description: str = Field(min_length=1, max_length=500)


class SegmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    filters: SegmentFilters = Field(default_factory=SegmentFilters)
    sql: str | None = Field(default=None, max_length=5000)


class SegmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    filters: SegmentFilters | None = None
    # "" switches the segment back to the visual filters
    sql: str | None = Field(default=None, max_length=5000)


class SegmentOut(BaseModel):
    id: UUID
    name: str
    filters: SegmentFilters
    sql: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class SegmentMemberOut(BaseModel):
    id: UUID
    name: str
    first_name: str | None
    email: str | None
    phone: str | None
    status: CustomerStatus

    model_config = {"from_attributes": True}


class SegmentResult(BaseModel):
    total: int
    members: list[SegmentMemberOut]


class SegmentFieldOut(BaseModel):
    key: str
    label: str
    type: Literal["text", "enum", "date", "number", "boolean"]
    choices: list[str] | None = None


class SegmentFieldsOut(BaseModel):
    fields: list[SegmentFieldOut]
    operators_by_type: dict[str, list[Operator]]
    custom_fields: list[str]


class SegmentSQLRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=5000)


class SegmentSQLSuggestRequest(BaseModel):
    description: str = Field(min_length=1, max_length=1000)
    # when given, the assistant edits this query instead of starting over
    current_sql: str | None = Field(default=None, max_length=5000)


class SegmentSQLSuggestion(BaseModel):
    sql: str


class SandboxColumnOut(BaseModel):
    name: str
    type: str
    description: str


class SandboxTableOut(BaseModel):
    name: str
    columns: list[SandboxColumnOut]
