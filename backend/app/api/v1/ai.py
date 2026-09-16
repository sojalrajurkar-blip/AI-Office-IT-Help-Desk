from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.ai import AICaseAnalysis
from app.models.case import Case
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.ai import (
    AICaseAnalysisResponse,
    AICaseAnalysisReviewRequest,
    AIDraftMessageRequest,
    AIDraftMessageResponse,
    AIDuplicateCheckRequest,
    AIDuplicateCheckResponse,
)
from app.services.ai_service import ai_service
from app.services.timeline_service import TimelineService

router = APIRouter()

STAFF_ROLES = [
    UserRole.OPERATOR,
    UserRole.TEAM_LEAD,
    UserRole.MANAGER,
    UserRole.ADMIN,
]


def _to_analysis_response(analysis: AICaseAnalysis) -> AICaseAnalysisResponse:
    return AICaseAnalysisResponse(
        id=analysis.id,
        case_id=analysis.case_id,
        suggested_category_id=analysis.suggested_category_id,
        suggested_category_name=analysis.suggested_category.name if analysis.suggested_category else None,
        suggested_priority=analysis.suggested_priority,
        suggested_severity=analysis.suggested_severity,
        suggested_team_id=analysis.suggested_team_id,
        suggested_team_name=analysis.suggested_team.name if analysis.suggested_team else None,
        missing_information=analysis.missing_information or [],
        recommended_questions=analysis.recommended_questions or [],
        related_case_ids=analysis.related_case_ids or [],
        recommended_next_action=analysis.recommended_next_action,
        case_summary=analysis.case_summary,
        risk_insight=analysis.risk_insight,
        confidence_score=analysis.confidence_score,
        is_accepted=analysis.is_accepted,
        is_overridden=analysis.is_overridden,
        override_reason=analysis.override_reason,
        reviewed_by_id=analysis.reviewed_by_id,
        reviewed_at=analysis.reviewed_at,
        created_at=analysis.created_at,
    )


# -----------------------------------------------------------------------------
# Standalone AI Utilities
# -----------------------------------------------------------------------------

@router.post("/check-duplicates", response_model=AIDuplicateCheckResponse)
async def check_duplicates(
    data: AIDuplicateCheckRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Scans for potential duplicate or related cases based on title and description.
    Available to all authenticated roles prior to or during ticket triage.
    """
    return await ai_service.detect_duplicates(
        title=data.title,
        description=data.description,
        db=db,
        category_id=data.category_id,
    )


# -----------------------------------------------------------------------------
# Case-Level AI Analysis & Review
# -----------------------------------------------------------------------------

@router.post("/cases/{case_id}/ai-analysis", response_model=AICaseAnalysisResponse, status_code=status.HTTP_201_CREATED)
async def trigger_ai_case_analysis(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(STAFF_ROLES)),
):
    """
    Triggers or re-runs AI triage analysis on a case.
    Restricted to IT Staff (Operator, Team Lead, Manager, Admin).
    """
    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    analysis = await ai_service.analyze_case(case=case, db=db, actor=current_user)
    await db.commit()

    # Eager load relationships for response
    stmt = (
        select(AICaseAnalysis)
        .options(
            selectinload(AICaseAnalysis.suggested_category),
            selectinload(AICaseAnalysis.suggested_team),
        )
        .where(AICaseAnalysis.id == analysis.id)
    )
    loaded = (await db.execute(stmt)).scalar_one()
    return _to_analysis_response(loaded)


@router.get("/cases/{case_id}/ai-analyses", response_model=List[AICaseAnalysisResponse])
async def list_ai_analyses_for_case(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(STAFF_ROLES)),
):
    """
    Lists all AI analyses and human audit reviews for a specific case.
    Restricted to IT Staff.
    """
    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    stmt = (
        select(AICaseAnalysis)
        .options(
            selectinload(AICaseAnalysis.suggested_category),
            selectinload(AICaseAnalysis.suggested_team),
        )
        .where(AICaseAnalysis.case_id == case_id)
        .order_by(AICaseAnalysis.created_at.desc())
    )
    analyses = (await db.execute(stmt)).scalars().all()
    return [_to_analysis_response(a) for a in analyses]


@router.post("/cases/{case_id}/ai-analyses/{analysis_id}/review", response_model=AICaseAnalysisResponse)
async def review_ai_case_analysis(
    case_id: int,
    analysis_id: int,
    body: AICaseAnalysisReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(STAFF_ROLES)),
):
    """
    Allows IT staff to Accept or Override AI recommendations (Human-in-the-loop).
    If accepted and apply_changes=True, applies category, priority, and team to the case.
    """
    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    analysis = await db.get(AICaseAnalysis, analysis_id)
    if not analysis or analysis.case_id != case_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI Analysis record not found for this case")

    analysis.reviewed_by_id = current_user.id
    analysis.reviewed_at = datetime.now(timezone.utc)

    if body.is_accepted:
        analysis.is_accepted = True
        analysis.is_overridden = False
        analysis.override_reason = None

        applied_fields = []
        if body.apply_changes:
            if analysis.suggested_category_id:
                case.category_id = analysis.suggested_category_id
                applied_fields.append("category")
            if analysis.suggested_priority:
                case.priority = analysis.suggested_priority
                applied_fields.append(f"priority={analysis.suggested_priority.value}")
            if analysis.suggested_team_id:
                case.assigned_team_id = analysis.suggested_team_id
                applied_fields.append("assigned_team")

        await TimelineService.record_event(
            db=db,
            case_id=case.id,
            event_type="AI_ANALYSIS_ACCEPTED",
            summary=f"AI recommendations accepted by {current_user.full_name} ({', '.join(applied_fields)}).",
            actor=current_user,
            details={"analysis_id": analysis.id, "applied_fields": applied_fields},
        )

    elif body.is_overridden:
        if not body.override_reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Override reason is required when overriding AI recommendations.",
            )
        analysis.is_overridden = True
        analysis.is_accepted = False
        analysis.override_reason = body.override_reason

        await TimelineService.record_event(
            db=db,
            case_id=case.id,
            event_type="AI_ANALYSIS_OVERRIDDEN",
            summary=f"AI recommendations overridden by {current_user.full_name}. Reason: {body.override_reason}",
            actor=current_user,
            details={"analysis_id": analysis.id, "override_reason": body.override_reason},
        )

    await db.commit()

    # Eager load relationships for response
    stmt = (
        select(AICaseAnalysis)
        .options(
            selectinload(AICaseAnalysis.suggested_category),
            selectinload(AICaseAnalysis.suggested_team),
        )
        .where(AICaseAnalysis.id == analysis.id)
    )
    loaded = (await db.execute(stmt)).scalar_one()
    return _to_analysis_response(loaded)


@router.post("/cases/{case_id}/ai-draft", response_model=AIDraftMessageResponse)
async def draft_communication(
    case_id: int,
    body: AIDraftMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(STAFF_ROLES)),
):
    """
    Drafts professional communication (info request, status update, workaround, resolution explanation).
    Restricted to IT Staff.
    """
    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    return await ai_service.draft_communication(
        case=case,
        draft_type=body.draft_type,
        db=db,
        instructions=body.instructions,
    )
