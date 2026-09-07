"""backend/app/deps.py - FastAPI dependencies: DB session, simulated role
check, tenant resolution.

There's no real authentication in this prototype - roles are simulated via an
X-Role header. Reads are open to any recognized role; only state-changing
endpoints call require_role(...) to gate writes, per the approved plan.
"""

from typing import Optional

from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from .config import DEFAULT_ROLE, ROLE_LEVELS
from .db import get_db
from .models import Tenant

__all__ = ["get_db", "get_role", "require_role", "get_tenant_or_none", "get_tenant_or_404"]


def get_role(x_role: str = Header(default=DEFAULT_ROLE, alias="X-Role")) -> str:
    if x_role not in ROLE_LEVELS:
        raise HTTPException(
            status_code=403,
            detail=f"unknown role '{x_role}' - must be one of {list(ROLE_LEVELS)}",
        )
    return x_role


def require_role(min_role: str):
    min_level = ROLE_LEVELS[min_role]

    def _check(role: str = Depends(get_role)) -> str:
        if ROLE_LEVELS[role] < min_level:
            raise HTTPException(
                status_code=403,
                detail=f"role '{role}' cannot perform this action (requires >= '{min_role}')",
            )
        return role

    return _check


def get_tenant_or_none(
    tenant: Optional[str] = Query(default=None, description="tenant slug"),
    db: Session = Depends(get_db),
) -> Optional[Tenant]:
    if tenant is None:
        return None
    row = db.query(Tenant).filter(Tenant.slug == tenant).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"unknown tenant '{tenant}'")
    return row


def get_tenant_or_404(
    tenant: str = Query(..., description="tenant slug"),
    db: Session = Depends(get_db),
) -> Tenant:
    row = db.query(Tenant).filter(Tenant.slug == tenant).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"unknown tenant '{tenant}'")
    return row
