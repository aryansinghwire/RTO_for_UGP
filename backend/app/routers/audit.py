"""backend/app/routers/audit.py - admin/oversight view over intervention_log."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..config import ROLE_LEVELS
from ..deps import get_db, get_tenant_or_none, require_role
from ..models import InterventionLog, Tenant
from ..schemas import AuditLogEntry, PaginatedAuditLog

router = APIRouter(prefix="/audit-log", tags=["audit"])


@router.get("", response_model=PaginatedAuditLog)
def get_audit_log(
    tenant: Optional[Tenant] = Depends(get_tenant_or_none),
    actor_role: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
    since: Optional[str] = Query(default=None, description="ISO date, inclusive"),
    until: Optional[str] = Query(default=None, description="ISO date, inclusive"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    role: str = Depends(require_role("ops_manager")),
):
    if actor_role is not None and actor_role not in ROLE_LEVELS:
        raise HTTPException(status_code=422, detail=f"actor_role must be one of {list(ROLE_LEVELS)}")
    if event_type is not None and event_type not in ("override", "intervention_action"):
        raise HTTPException(status_code=422, detail="event_type must be 'override' or 'intervention_action'")

    q = db.query(InterventionLog)
    if tenant is not None:
        q = q.filter(InterventionLog.tenant_id == tenant.id)
    if actor_role is not None:
        q = q.filter(InterventionLog.actor_role == actor_role)
    if event_type is not None:
        q = q.filter(InterventionLog.event_type == event_type)
    if since is not None:
        q = q.filter(InterventionLog.created_at >= datetime.strptime(since, "%Y-%m-%d"))
    if until is not None:
        until_end = datetime.strptime(until, "%Y-%m-%d") + timedelta(days=1)
        q = q.filter(InterventionLog.created_at < until_end)

    total = q.count()
    rows = (
        q.order_by(InterventionLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [
        AuditLogEntry(
            order_id=r.order_id,
            tenant=r.tenant.name,
            id=r.id,
            event_type=r.event_type,
            action_type=r.action_type,
            trigger=r.trigger,
            outcome=r.outcome,
            old_score=r.old_score,
            new_score=r.new_score,
            note=r.note,
            actor_role=r.actor_role,
            actor_name=r.actor_name,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return PaginatedAuditLog(items=items, page=page, page_size=page_size, total=total)
