"""backend/app/schemas.py - Pydantic request/response models."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str


class TenantCreate(BaseModel):
    name: str


class RoleOut(BaseModel):
    role: str
    label: str
    description: str


class OrderListItem(BaseModel):
    """Summary row for the queue table - no raw_features, keeps list payloads light."""
    order_id: str
    tenant: str
    order_date: str
    customer_ref: str
    product_ref: str
    current_score: float
    model_risk_score: float
    status: str
    reasons: list[str]
    customer_no_history: bool
    product_no_history: bool
    country_bucket: str
    product_brand_bucket: str
    product_type_bucket: str


class PaginatedOrders(BaseModel):
    items: list[OrderListItem]
    page: int
    page_size: int
    total: int


class OrderDetail(OrderListItem):
    """Full drill-down. Deliberately has NO is_returned_ground_truth field -
    that must never appear on an individual order."""
    customer_return_rate: float
    product_return_rate: float
    avg_discount_value: float
    avg_gbp_price: float
    override_score: Optional[float] = None
    override_reason: Optional[str] = None
    overridden_by: Optional[str] = None
    overridden_at: Optional[datetime] = None
    raw_features: dict[str, Any]


class OverrideRequest(BaseModel):
    new_score: float
    reason: str
    actor_name: Optional[str] = None


class ActionRequest(BaseModel):
    action_type: str
    trigger: str = "manual"
    note: Optional[str] = None
    actor_name: Optional[str] = None


class ActionOutcomeUpdate(BaseModel):
    outcome: str
    note: Optional[str] = None


class HistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    action_type: Optional[str] = None
    trigger: str
    outcome: Optional[str] = None
    old_score: Optional[float] = None
    new_score: Optional[float] = None
    note: Optional[str] = None
    actor_role: str
    actor_name: Optional[str] = None
    created_at: datetime


class AuditLogEntry(HistoryEntry):
    order_id: str
    tenant: str


class PaginatedAuditLog(BaseModel):
    items: list[AuditLogEntry]
    page: int
    page_size: int
    total: int


class ReportingBucket(BaseModel):
    bucket: str
    baseline_return_rate: float
    actual_return_rate: float
    n_orders: int


class ReportingResponse(BaseModel):
    cohort_type: str
    cohort_key: str
    granularity: str
    buckets: list[ReportingBucket]


class AlertOut(BaseModel):
    tenant: str
    cohort_type: str
    cohort_key: str
    baseline_rate: float
    actual_rate: float
    gap: float
    n_orders: int
    severity: str


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant: str
    name: str
    score_threshold: float
    action_type: str
    is_active: bool


class RuleCreate(BaseModel):
    name: str
    score_threshold: float
    action_type: str


class RuleUpdate(BaseModel):
    is_active: Optional[bool] = None
    score_threshold: Optional[float] = None
    action_type: Optional[str] = None


class MetaOut(BaseModel):
    generated_at: str
    model: str
    n_orders: int
    achieved_overall_auc: Optional[float]
    achieved_cold_customer_auc: Optional[float]
    tenants: list[str]
    notice: str
