#!/usr/bin/env python3
"""
backend/scripts/seed_db.py - loads serving/output/orders_seed.json into SQLite.

Idempotent: refuses to reseed a non-empty DB unless --force is passed (which
drops and recreates all tables first). Also computes baseline_stats once here
(not in serving/), per the approved plan.

Run from the repo root:
    .venv/bin/python -m backend.scripts.seed_db
    .venv/bin/python -m backend.scripts.seed_db --force
"""

import json
import re
import sys

from sqlalchemy import func

from ..app.config import SEED_JSON_PATH
from ..app.db import Base, SessionLocal, engine
from ..app.models import BaselineStat, Order, OrderStatus, Tenant


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def load_seed():
    with open(SEED_JSON_PATH) as f:
        return json.load(f)


def seed(force: bool = False):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        existing = db.query(func.count(Order.order_id)).scalar()
        if existing and not force:
            print(f"DB already has {existing:,} orders - pass --force to wipe and reseed.")
            return

        if existing and force:
            print("wiping existing tables...")
            Base.metadata.drop_all(bind=engine)
            Base.metadata.create_all(bind=engine)

        doc = load_seed()
        meta = doc["meta"]
        orders = doc["orders"]
        print(f"loaded {len(orders):,} orders from {SEED_JSON_PATH} "
              f"(model={meta['model']}, achieved_overall_auc={meta['achieved_overall_auc']})")

        tenant_by_name = {}
        for name in meta["tenants"]:
            tenant = Tenant(name=name, slug=slugify(name))
            db.add(tenant)
            tenant_by_name[name] = tenant
        db.flush()  # assign ids without committing yet

        print(f"created {len(tenant_by_name)} tenants: "
              f"{[(t.name, t.slug) for t in tenant_by_name.values()]}")

        for i, rec in enumerate(orders):
            tenant = tenant_by_name[rec["tenant"]]
            order = Order(
                order_id=rec["order_id"],
                tenant_id=tenant.id,
                customer_ref=rec["customer_ref"],
                product_ref=rec["product_ref"],
                order_date=rec["order_date"],
                model_risk_score=rec["risk_score"],
                reasons_json=json.dumps(rec["reasons"]),
                customer_no_history=rec["customer_no_history"],
                product_no_history=rec["product_no_history"],
                customer_return_rate=rec["customer_return_rate"],
                product_return_rate=rec["product_return_rate"],
                avg_discount_value=rec["avg_discount_value"],
                avg_gbp_price=rec["avg_gbp_price"],
                country_bucket=rec["country_bucket"],
                product_brand_bucket=rec["product_brand_bucket"],
                product_type_bucket=rec["product_type_bucket"],
                raw_features_json=json.dumps(rec["raw_features"]),
                is_returned_ground_truth=rec["is_returned_ground_truth"],
            )
            db.add(order)
            db.add(OrderStatus(
                order_id=rec["order_id"],
                current_score=rec["risk_score"],
                status="pending",
            ))
            if (i + 1) % 4000 == 0:
                db.flush()
                print(f"  ...{i + 1:,} orders staged")

        db.commit()
        print(f"committed {len(orders):,} orders + status rows")

        compute_baseline_stats(db)
        print("computed baseline_stats")

    finally:
        db.close()


def compute_baseline_stats(db):
    """baseline_return_rate = mean(product_return_rate) per (tenant, cohort) -
    a real, precomputed historical feature, not derived from the synthetic
    order_date/tenant assignment. See services/reporting.py for the same
    definition used at query time when a cache miss occurs."""
    cohort_columns = {
        "product": Order.product_ref,
        "country": Order.country_bucket,
        "product_type": Order.product_type_bucket,
    }

    for tenant in db.query(Tenant).all():
        overall_avg, overall_n = (
            db.query(func.avg(Order.product_return_rate), func.count(Order.order_id))
            .filter(Order.tenant_id == tenant.id)
            .one()
        )
        db.add(BaselineStat(
            tenant_id=tenant.id, cohort_type="overall", cohort_key="overall",
            baseline_return_rate=float(overall_avg or 0.0), n_baseline_orders=int(overall_n or 0),
        ))

        for cohort_type, col in cohort_columns.items():
            rows = (
                db.query(col, func.avg(Order.product_return_rate), func.count(Order.order_id))
                .filter(Order.tenant_id == tenant.id)
                .group_by(col)
                .all()
            )
            for key, avg_rate, n in rows:
                db.add(BaselineStat(
                    tenant_id=tenant.id, cohort_type=cohort_type, cohort_key=key,
                    baseline_return_rate=float(avg_rate or 0.0), n_baseline_orders=int(n or 0),
                ))

    db.commit()


if __name__ == "__main__":
    seed(force="--force" in sys.argv)
