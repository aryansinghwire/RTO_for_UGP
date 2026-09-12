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

__all__ = [
    "get_db", "get_role", "require_role", "get_tenant_or_none", "get_tenant_or_404",
    "get_actor_tenant", "require_tenant_scope",
]


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


def get_actor_tenant(
    x_actor_tenant: Optional[str] = Header(default=None, alias="X-Actor-Tenant"),
) -> Optional[str]:
    """The tenant the caller *belongs to*, as opposed to the `?tenant=` they're
    asking about.

    In a real deployment this would come off the authenticated session/JWT. The
    prototype has no auth, so the frontend states it in a header - which means
    it is a simulation of tenant isolation, not a security boundary. It still
    exercises the real code path: every scoped endpoint compares this against
    the tenant being addressed.
    """
    return x_actor_tenant


def require_tenant_scope(
    tenant: Tenant = Depends(get_tenant_or_404),
    role: str = Depends(get_role),
    actor_tenant: Optional[str] = Depends(get_actor_tenant),
) -> Tenant:
    """Resolve the addressed tenant and confirm the caller may act on it.

    'admin' is the cross-tenant platform role and passes through. Every other
    role is pinned to its own tenant: a Tenant Admin at Aurora Apparel cannot
    read or change Nimbus Fashion Co.'s configuration.
    """
    if role == "admin":
        return tenant
    if actor_tenant is None:
        raise HTTPException(
            status_code=403,
            detail=(f"role '{role}' is tenant-scoped - the request must identify "
                    f"the caller's own tenant via the X-Actor-Tenant header"),
        )
    if actor_tenant != tenant.slug:
        raise HTTPException(
            status_code=403,
            detail=(f"role '{role}' is scoped to tenant '{actor_tenant}' and cannot "
                    f"act on tenant '{tenant.slug}'"),
        )
    return tenant
