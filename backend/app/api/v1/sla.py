from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.case import Case
from app.models.enums import CaseStatus, UserRole
from app.models.sla import CaseEscalation, CaseRiskRecord, SLAPolicy
from app.models.user import User
from app.schemas.sla import (
    CaseEscalationCreate,
    CaseEscalationResolveRequest,
    CaseEscalationResponse,
    CaseRiskEvaluationResponse,
    CaseRiskRecordResponse,
    CaseSLAStatusResponse,
    SLAPolicyCreate,
    SLAPolicyResponse,
    SLASweepSummaryResponse,
)
from app.services.sla_service import sla_service

router = APIRouter()

STAFF_ROLES = [
    UserRole.OPERATOR,
    UserRole.TEAM_LEAD,
    UserRole.MANAGER,
    UserRole.ADMIN,
]

SUPERVISOR_ROLES = [
    UserRole.TEAM_LEAD,
    UserRole.MANAGER,
    UserRole.ADMIN,
]


def _to_escalation_response(esc: CaseEscalation) -> CaseEscalationResponse:
    return CaseEscalationResponse(
        id=esc.id,
        case_id=esc.case_id,
        escalated_by_id=esc.escalated_by_id,
        escalated_by_name=esc.escalated_by.full_name if esc.escalated_by else None,
        target_role=esc.target_role,
        reason=esc.reason,
        status=esc.status,
        resolution_notes=esc.resolution_notes,
        resolved_by_id=esc.resolved_by_id,
        resolved_by_name=esc.resolved_by.full_name if esc.resolved_by else None,
        created_at=esc.created_at,
        resolved_at=esc.resolved_at,
    )


# -----------------------------------------------------------------------------
# SLA Policies Endpoints
# -----------------------------------------------------------------------------

@router.get("/sla/policies", response_model=List[SLAPolicyResponse])
async def list_sla_policies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lists all configured SLA policies."""
    stmt = select(SLAPolicy).order_by(SLAPolicy.response_time_hours.asc())
    policies = (await db.execute(stmt)).scalars().all()
    return policies


@router.post("/sla/policies", response_model=SLAPolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_sla_policy(
    body: SLAPolicyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN])),
):
    """Creates a new SLA policy. Admin only."""
    policy = SLAPolicy(
        name=body.name,
        priority=body.priority,
        response_time_hours=body.response_time_hours,
        resolution_time_hours=body.resolution_time_hours,
        is_active=True,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return policy


# -----------------------------------------------------------------------------
# Case SLA Status & Risk Assessment Endpoints
# -----------------------------------------------------------------------------

@router.get("/cases/{case_id}/sla-status", response_model=CaseSLAStatusResponse)
async def get_case_sla_status(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Inspects SLA countdown, deadline progress, remaining minutes, and breach flags."""
    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    # Authorization check
    if current_user.role == UserRole.REQUESTER and case.requester_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access forbidden to this case")

    # Check and apply breach flag if overdue
    breached = await sla_service.check_and_apply_sla_breach(case, db)
    if breached:
        await db.commit()

    return sla_service.get_case_sla_status(case)


@router.get("/cases/{case_id}/risk", response_model=CaseRiskEvaluationResponse)
async def get_case_risk(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(STAFF_ROLES)),
):
    """Fetches current risk level, explanatory warning reasons, and risk signals."""
    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    risk_record = await sla_service.evaluate_case_risk(case, db, actor=current_user)
    await db.commit()

    sla_status = sla_service.get_case_sla_status(case)
    summary = f"Risk evaluated as {risk_record.risk_level.value}."
    if risk_record.reasons:
        summary += f" Key driver: {risk_record.reasons[0]}"

    return CaseRiskEvaluationResponse(
        case_id=case.id,
        case_number=case.case_number,
        risk_level=risk_record.risk_level,
        reasons=risk_record.reasons,
        is_at_risk=sla_status.is_at_risk,
        summary=summary,
    )


@router.post("/cases/{case_id}/risk/evaluate", response_model=CaseRiskEvaluationResponse)
async def evaluate_case_risk(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(STAFF_ROLES)),
):
    """Triggers on-demand evaluation of case risk."""
    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    risk_record = await sla_service.evaluate_case_risk(case, db, actor=current_user)
    await db.commit()

    sla_status = sla_service.get_case_sla_status(case)
    summary = f"Risk evaluated as {risk_record.risk_level.value}."
    if risk_record.reasons:
        summary += f" Key driver: {risk_record.reasons[0]}"

    return CaseRiskEvaluationResponse(
        case_id=case.id,
        case_number=case.case_number,
        risk_level=risk_record.risk_level,
        reasons=risk_record.reasons,
        is_at_risk=sla_status.is_at_risk,
        summary=summary,
    )


# -----------------------------------------------------------------------------
# Escalation Endpoints
# -----------------------------------------------------------------------------

@router.post("/cases/{case_id}/escalate", response_model=CaseEscalationResponse, status_code=status.HTTP_201_CREATED)
async def escalate_case(
    case_id: int,
    body: CaseEscalationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(STAFF_ROLES)),
):
    """
    Escalates a case to a supervisor role (Team Lead, Manager, Admin).
    Transitions case status to ESCALATED.
    """
    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    terminal_states = [CaseStatus.CONFIRMED, CaseStatus.CLOSED, CaseStatus.CANCELLED, CaseStatus.DUPLICATE]
    if case.status in terminal_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot escalate a case in {case.status.value} status.",
        )

    escalation = await sla_service.escalate_case(
        case=case,
        user=current_user,
        reason=body.reason,
        target_role=body.target_role,
        db=db,
    )
    await db.commit()

    # Eager load relations
    stmt = (
        select(CaseEscalation)
        .options(
            selectinload(CaseEscalation.escalated_by),
            selectinload(CaseEscalation.resolved_by),
        )
        .where(CaseEscalation.id == escalation.id)
    )
    loaded = (await db.execute(stmt)).scalar_one()
    return _to_escalation_response(loaded)


@router.get("/cases/{case_id}/escalations", response_model=List[CaseEscalationResponse])
async def list_case_escalations(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(STAFF_ROLES)),
):
    """Lists escalation history for a case. Staff only."""
    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    stmt = (
        select(CaseEscalation)
        .options(
            selectinload(CaseEscalation.escalated_by),
            selectinload(CaseEscalation.resolved_by),
        )
        .where(CaseEscalation.case_id == case_id)
        .order_by(CaseEscalation.created_at.desc())
    )
    escalations = (await db.execute(stmt)).scalars().all()
    return [_to_escalation_response(e) for e in escalations]


@router.post("/escalations/{escalation_id}/resolve", response_model=CaseEscalationResponse)
async def resolve_escalation(
    escalation_id: int,
    body: CaseEscalationResolveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(SUPERVISOR_ROLES)),
):
    """
    Resolves an escalation with resolution notes and unfreezes case back to active status.
    Restricted to Team Lead, Manager, or Admin.
    """
    escalation = await db.get(CaseEscalation, escalation_id)
    if not escalation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escalation record not found")

    if escalation.status == CaseStatus.CLOSED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Escalation is already resolved")

    updated = await sla_service.resolve_escalation(
        escalation=escalation,
        resolver=current_user,
        resolution_notes=body.resolution_notes,
        next_status=body.next_status,
        db=db,
    )
    await db.commit()

    stmt = (
        select(CaseEscalation)
        .options(
            selectinload(CaseEscalation.escalated_by),
            selectinload(CaseEscalation.resolved_by),
        )
        .where(CaseEscalation.id == updated.id)
    )
    loaded = (await db.execute(stmt)).scalar_one()
    return _to_escalation_response(loaded)


# -----------------------------------------------------------------------------
# Lightweight Sweep Engine Endpoint
# -----------------------------------------------------------------------------

@router.post("/sla/sweep", response_model=SLASweepSummaryResponse)
async def trigger_sla_sweep(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(STAFF_ROLES)),
):
    """
    Triggers batch SLA breach and risk detection sweep across all active tickets.
    Staff only.
    """
    return await sla_service.run_sla_and_risk_sweep(db)
