"""backend/app/routers/alerts.py - live spike-alert list."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..config import ALERT_MIN_GAP, ALERT_MIN_N
from ..deps import get_db, get_role, get_tenant_or_none
from ..models import Tenant
from ..schemas import AlertOut
from ..services.alerts import get_alerts

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
def list_alerts(
    tenant: Optional[Tenant] = Depends(get_tenant_or_none),
    min_gap: float = Query(default=ALERT_MIN_GAP, ge=0.0, le=1.0),
    min_n: int = Query(default=ALERT_MIN_N, ge=1),
    db: Session = Depends(get_db),
    role: str = Depends(get_role),
):
    alerts = get_alerts(db, tenant, min_gap=min_gap, min_n=min_n)
    return [AlertOut(**a) for a in alerts]
