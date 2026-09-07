"""backend/app/services/alerts.py - live spike detection.

Deliberately a simple threshold check, not a real hypothesis test: for each
(tenant, cohort), compare the actual return/RTO rate in a recent window
against the cohort's historical baseline, and flag if the gap is large enough
AND the window has enough orders to not be noise (only 397 distinct products
exist in the test set, so small cohorts must not fire spurious alerts).
"""

from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import ALERT_MIN_GAP, ALERT_MIN_N
from ..models import Order, Tenant
from .reporting import get_baseline_rate

RECENT_WINDOW_DAYS = 14
COHORT_TYPES = ["product", "country", "product_type"]
COHORT_COLUMNS = {
    "product": Order.product_ref,
    "country": Order.country_bucket,
    "product_type": Order.product_type_bucket,
}


def _recent_window(db: Session, tenant_id):
    q = db.query(func.max(Order.order_date))
    if tenant_id is not None:
        q = q.filter(Order.tenant_id == tenant_id)
    max_date_str = q.scalar()
    if max_date_str is None:
        return None, None
    end = datetime.strptime(max_date_str, "%Y-%m-%d").date()
    start = end - timedelta(days=RECENT_WINDOW_DAYS - 1)
    return start.isoformat(), end.isoformat()


def _alerts_for_tenant(db: Session, tenant: Tenant, min_gap: float, min_n: int) -> list[dict]:
    start, end = _recent_window(db, tenant.id)
    if start is None:
        return []

    alerts = []
    for cohort_type in COHORT_TYPES:
        col = COHORT_COLUMNS[cohort_type]
        keys = [
            row[0] for row in
            db.query(col).filter(Order.tenant_id == tenant.id).distinct().all()
        ]
        for key in keys:
            window_q = (
                db.query(func.count(Order.order_id), func.avg(Order.is_returned_ground_truth))
                .filter(
                    Order.tenant_id == tenant.id,
                    col == key,
                    Order.order_date >= start,
                    Order.order_date <= end,
                )
            )
            n, actual_rate = window_q.one()
            n = int(n or 0)
            if n < min_n:
                continue
            actual_rate = float(actual_rate or 0.0)

            baseline_rate, _ = get_baseline_rate(db, tenant.id, cohort_type, key)
            gap = actual_rate - baseline_rate
            if gap >= min_gap:
                alerts.append({
                    "tenant": tenant.name,
                    "cohort_type": cohort_type,
                    "cohort_key": key,
                    "baseline_rate": baseline_rate,
                    "actual_rate": actual_rate,
                    "gap": gap,
                    "n_orders": n,
                    "severity": "high" if gap >= 0.25 else "medium",
                })
    return alerts


def get_alerts(db: Session, tenant: Tenant | None, min_gap: float = ALERT_MIN_GAP,
                min_n: int = ALERT_MIN_N) -> list[dict]:
    tenants = [tenant] if tenant is not None else db.query(Tenant).all()
    out = []
    for t in tenants:
        out.extend(_alerts_for_tenant(db, t, min_gap, min_n))
    out.sort(key=lambda a: -a["gap"])
    return out
