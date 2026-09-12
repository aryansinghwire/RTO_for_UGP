"""backend/app/models.py - SQLAlchemy ORM models.

Schema per the approved plan (eventual-forging-firefly.md):
  tenants, orders (immutable), order_status (mutable current state),
  intervention_log (append-only), automated_rules, baseline_stats.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, ForeignKey, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .db import Base


def utcnow():
    return datetime.now(timezone.utc)


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=utcnow)


class Order(Base):
    """Immutable, loaded once from serving/output/orders_seed.json. The
    model's own score is never mutated post-seed - overrides live in
    OrderStatus instead, so the original model output stays auditable."""
    __tablename__ = "orders"

    order_id = Column(String, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    customer_ref = Column(String, nullable=False)
    product_ref = Column(String, nullable=False)
    order_date = Column(String, nullable=False, index=True)  # ISO date, synthetic

    model_risk_score = Column(Float, nullable=False, index=True)
    reasons_json = Column(Text, nullable=False)

    customer_no_history = Column(Integer, nullable=False)
    product_no_history = Column(Integer, nullable=False)
    customer_return_rate = Column(Float, nullable=False)
    product_return_rate = Column(Float, nullable=False)
    avg_discount_value = Column(Float, nullable=False)
    avg_gbp_price = Column(Float, nullable=False)

    country_bucket = Column(String, nullable=False)
    # deliberately NOT called "brand" - this is a real product attribute,
    # never to be confused with the synthetic tenant/company assignment
    product_brand_bucket = Column(String, nullable=False)
    product_type_bucket = Column(String, nullable=False)

    raw_features_json = Column(Text, nullable=False)

    # never returned by the order-detail endpoint - aggregate/reporting use only
    is_returned_ground_truth = Column(Integer, nullable=False)

    created_at = Column(DateTime, default=utcnow)

    tenant = relationship("Tenant")
    status = relationship("OrderStatus", uselist=False, back_populates="order")


class OrderStatus(Base):
    """1:1 mutable current-state row per order."""
    __tablename__ = "order_status"

    order_id = Column(String, ForeignKey("orders.order_id"), primary_key=True)
    current_score = Column(Float, nullable=False)
    status = Column(String, nullable=False, default="pending")  # pending|overridden|actioned|closed

    override_score = Column(Float, nullable=True)
    override_reason = Column(Text, nullable=True)
    overridden_by = Column(String, nullable=True)
    overridden_at = Column(DateTime, nullable=True)

    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    order = relationship("Order", back_populates="status")


class InterventionLog(Base):
    """Append-only. Backs override history, action/outcome logging, and the
    admin audit log - all the same table, filtered by event_type."""
    __tablename__ = "intervention_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String, ForeignKey("orders.order_id"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    event_type = Column(String, nullable=False)  # override | intervention_action
    action_type = Column(String, nullable=True)  # call_customer, send_reminder_email, ...
    trigger = Column(String, nullable=False, default="manual")  # manual | automated_threshold
    outcome = Column(String, nullable=True)  # pending | resolved_kept | resolved_prevented | no_response

    old_score = Column(Float, nullable=True)
    new_score = Column(Float, nullable=True)
    note = Column(Text, nullable=True)

    actor_role = Column(String, nullable=False)
    actor_name = Column(String, nullable=True)

    created_at = Column(DateTime, default=utcnow, index=True)

    tenant = relationship("Tenant")


class AutomatedRule(Base):
    """A per-tenant automated action, configured over a *score window* rather
    than a single floor: the rule fires on orders whose current score falls in
    [score_min, score_max]. A window lets a tenant route mid-band orders to a
    cheap action (reminder email) and top-band orders to an expensive one
    (call the customer) without the two rules overlapping.

    Rules are tenant-scoped and a Tenant Admin may only touch their own
    tenant's - see deps.require_tenant_scope.
    """
    __tablename__ = "automated_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    score_min = Column(Float, nullable=False)
    score_max = Column(Float, nullable=False)
    action_type = Column(String, nullable=False)
    is_active = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=utcnow)

    tenant = relationship("Tenant")


class BaselineStat(Base):
    """Precomputed once by scripts/seed_db.py - not touched by serving/."""
    __tablename__ = "baseline_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    cohort_type = Column(String, nullable=False)  # overall | product | country | product_type
    cohort_key = Column(String, nullable=False)
    baseline_return_rate = Column(Float, nullable=False)
    n_baseline_orders = Column(Integer, nullable=False)
    computed_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "cohort_type", "cohort_key", name="uq_baseline_cohort"),
    )
