"""backend/app/routers/rules.py - automated-rule CRUD + manual sweep."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..constants import ACTION_TYPES
from ..deps import get_db, get_role, get_tenant_or_404, get_tenant_or_none, require_role
from ..models import AutomatedRule, Tenant
from ..schemas import RuleCreate, RuleOut, RuleUpdate
from ..services.rules_engine import evaluate_rules

router = APIRouter(prefix="/rules", tags=["rules"])


def _to_rule_out(rule: AutomatedRule) -> dict:
    return {
        "id": rule.id,
        "tenant": rule.tenant.name,
        "name": rule.name,
        "score_threshold": rule.score_threshold,
        "action_type": rule.action_type,
        "is_active": bool(rule.is_active),
    }


@router.get("", response_model=list[RuleOut])
def list_rules(
    tenant: Optional[Tenant] = Depends(get_tenant_or_none),
    db: Session = Depends(get_db),
    role: str = Depends(get_role),
):
    q = db.query(AutomatedRule)
    if tenant is not None:
        q = q.filter(AutomatedRule.tenant_id == tenant.id)
    return [RuleOut(**_to_rule_out(r)) for r in q.all()]


@router.post("", response_model=RuleOut, status_code=201)
def create_rule(
    body: RuleCreate,
    tenant: Tenant = Depends(get_tenant_or_404),
    db: Session = Depends(get_db),
    role: str = Depends(require_role("ops_manager")),
):
    if body.action_type not in ACTION_TYPES:
        raise HTTPException(status_code=422, detail=f"action_type must be one of {sorted(ACTION_TYPES)}")
    if not (0.0 <= body.score_threshold <= 1.0):
        raise HTTPException(status_code=422, detail="score_threshold must be between 0 and 1")

    rule = AutomatedRule(
        tenant_id=tenant.id,
        name=body.name,
        score_threshold=body.score_threshold,
        action_type=body.action_type,
        is_active=1,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return RuleOut(**_to_rule_out(rule))


@router.patch("/{rule_id}", response_model=RuleOut)
def update_rule(
    rule_id: int,
    body: RuleUpdate,
    db: Session = Depends(get_db),
    role: str = Depends(require_role("ops_manager")),
):
    rule = db.query(AutomatedRule).filter(AutomatedRule.id == rule_id).first()
    if rule is None:
        raise HTTPException(status_code=404, detail=f"rule '{rule_id}' not found")

    if body.action_type is not None:
        if body.action_type not in ACTION_TYPES:
            raise HTTPException(status_code=422, detail=f"action_type must be one of {sorted(ACTION_TYPES)}")
        rule.action_type = body.action_type
    if body.score_threshold is not None:
        if not (0.0 <= body.score_threshold <= 1.0):
            raise HTTPException(status_code=422, detail="score_threshold must be between 0 and 1")
        rule.score_threshold = body.score_threshold
    if body.is_active is not None:
        rule.is_active = 1 if body.is_active else 0

    db.commit()
    db.refresh(rule)
    return RuleOut(**_to_rule_out(rule))


@router.post("/evaluate")
def evaluate(
    tenant: Tenant = Depends(get_tenant_or_404),
    db: Session = Depends(get_db),
    role: str = Depends(require_role("ops_manager")),
):
    return evaluate_rules(db, tenant.id)
