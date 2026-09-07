"""backend/app/routers/tenants.py - tenant listing + onboarding."""

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import get_db, get_role, require_role
from ..models import Tenant
from ..schemas import TenantCreate, TenantOut

router = APIRouter(prefix="/tenants", tags=["tenants"])


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


@router.get("", response_model=list[TenantOut])
def list_tenants(db: Session = Depends(get_db), role: str = Depends(get_role)):
    return db.query(Tenant).order_by(Tenant.name).all()


@router.post("", response_model=TenantOut, status_code=201)
def create_tenant(
    body: TenantCreate,
    db: Session = Depends(get_db),
    role: str = Depends(require_role("admin")),
):
    slug = slugify(body.name)
    if db.query(Tenant).filter(Tenant.slug == slug).first() is not None:
        raise HTTPException(status_code=409, detail=f"tenant with slug '{slug}' already exists")
    tenant = Tenant(name=body.name, slug=slug)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant
