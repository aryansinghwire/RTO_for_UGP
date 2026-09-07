"""backend/app/routers/reporting.py - baseline-vs-actual comparison."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..deps import get_db, get_role, get_tenant_or_none
from ..models import Tenant
from ..schemas import ReportingBucket, ReportingResponse
from ..services.reporting import baseline_vs_actual

router = APIRouter(prefix="/reporting", tags=["reporting"])

COHORT_TYPES = {"overall", "product", "country", "product_type"}
GRANULARITIES = {"day", "week"}


@router.get("/baseline-vs-actual", response_model=ReportingResponse)
def get_baseline_vs_actual(
    tenant: Optional[Tenant] = Depends(get_tenant_or_none),
    granularity: str = Query(default="week"),
    cohort_type: str = Query(default="overall"),
    cohort_key: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    role: str = Depends(get_role),
):
    if granularity not in GRANULARITIES:
        raise HTTPException(status_code=422, detail=f"granularity must be one of {sorted(GRANULARITIES)}")
    if cohort_type not in COHORT_TYPES:
        raise HTTPException(status_code=422, detail=f"cohort_type must be one of {sorted(COHORT_TYPES)}")
    if cohort_type != "overall" and not cohort_key:
        raise HTTPException(status_code=422, detail="cohort_key is required unless cohort_type='overall'")

    tenant_id = tenant.id if tenant is not None else None
    buckets = baseline_vs_actual(db, tenant_id, cohort_type, cohort_key or "", granularity)

    return ReportingResponse(
        cohort_type=cohort_type,
        cohort_key=cohort_key or "overall",
        granularity=granularity,
        buckets=[ReportingBucket(**b) for b in buckets],
    )
