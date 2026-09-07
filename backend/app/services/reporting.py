"""backend/app/services/reporting.py - baseline-vs-actual aggregation.

Baseline = the mean of `product_return_rate`, a REAL, already-historical
feature computed upstream (not from the synthetic order_date/tenant). Actual =
the REAL `is_returned_ground_truth` outcome rate, bucketed by the SYNTHETIC
order_date so there's something to plot a trend against. Only the calendar
bucketing is synthetic - both quantities being compared are real, which is
why this is presented as "observed outcome rate" replaying historical test
orders, not a live production accuracy claim (see config.PROTOTYPE_NOTICE).
"""

from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Order, BaselineStat


def _cohort_filter(query, cohort_type: str, cohort_key: str):
    if cohort_type == "overall":
        return query
    if cohort_type == "product":
        return query.filter(Order.product_ref == cohort_key)
    if cohort_type == "country":
        return query.filter(Order.country_bucket == cohort_key)
    if cohort_type == "product_type":
        return query.filter(Order.product_type_bucket == cohort_key)
    raise ValueError(f"unknown cohort_type '{cohort_type}'")


def _bucket_label(date_str: str, granularity: str) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    if granularity == "day":
        return d.isoformat()
    monday = d - timedelta(days=d.weekday())
    return monday.isoformat()


def get_baseline_rate(db: Session, tenant_id, cohort_type: str, cohort_key: str) -> tuple[float, int]:
    """Returns (baseline_return_rate, n_orders_used). Prefers the precomputed
    BaselineStat cache when scoped to a single tenant (matches the seeded
    design); computes live otherwise (e.g. an all-tenants overview)."""
    if tenant_id is not None:
        row = (
            db.query(BaselineStat)
            .filter(
                BaselineStat.tenant_id == tenant_id,
                BaselineStat.cohort_type == cohort_type,
                BaselineStat.cohort_key == cohort_key,
            )
            .first()
        )
        if row is not None:
            return row.baseline_return_rate, row.n_baseline_orders

    q = db.query(func.avg(Order.product_return_rate), func.count(Order.order_id))
    if tenant_id is not None:
        q = q.filter(Order.tenant_id == tenant_id)
    q = _cohort_filter(q, cohort_type, cohort_key)
    avg_rate, n = q.one()
    return float(avg_rate or 0.0), int(n or 0)


def baseline_vs_actual(db: Session, tenant_id, cohort_type: str, cohort_key: str,
                        granularity: str) -> list[dict]:
    baseline_rate, _ = get_baseline_rate(db, tenant_id, cohort_type, cohort_key)

    q = db.query(Order.order_date, Order.is_returned_ground_truth)
    if tenant_id is not None:
        q = q.filter(Order.tenant_id == tenant_id)
    q = _cohort_filter(q, cohort_type, cohort_key)

    buckets: dict[str, dict] = {}
    for order_date, returned in q.all():
        label = _bucket_label(order_date, granularity)
        b = buckets.setdefault(label, {"n": 0, "returned": 0})
        b["n"] += 1
        b["returned"] += int(returned)

    out = []
    for label in sorted(buckets.keys()):
        b = buckets[label]
        actual_rate = b["returned"] / b["n"] if b["n"] else 0.0
        out.append({
            "bucket": label,
            "baseline_return_rate": baseline_rate,
            "actual_return_rate": actual_rate,
            "n_orders": b["n"],
        })
    return out
