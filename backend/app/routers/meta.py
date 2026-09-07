"""backend/app/routers/meta.py - health check + seed provenance for the
frontend's prototype banner."""

import json

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import SEED_JSON_PATH
from ..deps import get_db, get_role
from ..models import Order
from ..schemas import MetaOut, RoleOut
from ..constants import ROLES

router = APIRouter(tags=["meta"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/meta", response_model=MetaOut)
def get_meta(db: Session = Depends(get_db), role: str = Depends(get_role)):
    with open(SEED_JSON_PATH) as f:
        seed_meta = json.load(f)["meta"]

    n_orders = db.query(func.count(Order.order_id)).scalar()

    return MetaOut(
        generated_at=seed_meta["generated_at"],
        model=seed_meta["model"],
        n_orders=n_orders,
        achieved_overall_auc=seed_meta.get("achieved_overall_auc"),
        achieved_cold_customer_auc=seed_meta.get("achieved_cold_customer_auc"),
        tenants=seed_meta["tenants"],
        notice=seed_meta["notice"],
    )


@router.get("/roles", response_model=list[RoleOut])
def list_roles(role: str = Depends(get_role)):
    return [RoleOut(role=r, label=v["label"], description=v["description"]) for r, v in ROLES.items()]
