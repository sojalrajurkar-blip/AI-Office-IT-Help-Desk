from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.case import Case
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.resolution import (
    ResolutionProposeRequest,
    ResolutionConfirmRequest,
    ResolutionRejectRequest,
    ResolutionResponse,
)
from app.services.resolution_service import resolution_service

router = APIRouter(prefix="/cases", tags=["Case Resolution & Reopening"])

STAFF_ROLES = [UserRole.OPERATOR, UserRole.TEAM_LEAD, UserRole.MANAGER, UserRole.ADMIN]


@router.post("/{case_id}/resolution/propose", response_model=ResolutionResponse, status_code=status.HTTP_201_CREATED)
async def propose_resolution(
    case_id: int,
    body: ResolutionProposeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(STAFF_ROLES)),
):
    """
    Operator or IT staff proposes a resolution for a case.
    Transitions case to RESOLUTION_PROPOSED.
    """
    case = await get_case_or_404(case_id, db)
    resolution = await resolution_service.propose_resolution(
        db=db,
        case=case,
        operator=current_user,
        actions_taken=body.actions_taken,
        findings=body.findings,
        remaining_issues=body.remaining_issues,
    )
    await db.commit()
    return resolution


@router.post("/{case_id}/resolution/confirm", response_model=ResolutionResponse)
async def confirm_resolution(
    case_id: int,
    body: ResolutionConfirmRequest = ResolutionConfirmRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Case requester confirms the proposed resolution.
    Transitions case to CLOSED.
    """
    case = await get_case_or_404(case_id, db)
    resolution = await resolution_service.confirm_resolution(
        db=db,
        case=case,
        user=current_user,
        feedback=body.feedback,
    )
    await db.commit()
    return resolution


@router.post("/{case_id}/resolution/reject", response_model=ResolutionResponse)
async def reject_resolution(
    case_id: int,
    body: ResolutionRejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Case requester rejects the proposed resolution.
    Transitions case to REOPENED for further investigation.
    """
    case = await get_case_or_404(case_id, db)
    resolution = await resolution_service.reject_resolution(
        db=db,
        case=case,
        user=current_user,
        rejection_reason=body.rejection_reason,
    )
    await db.commit()
    return resolution


@router.get("/{case_id}/resolutions", response_model=List[ResolutionResponse])
async def list_case_resolutions(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all resolution proposals and history for a case.
    """
    case = await get_case_or_404(case_id, db)
    if current_user.role == UserRole.REQUESTER and case.requester_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this case.")

    return await resolution_service.get_case_resolutions(db=db, case_id=case_id)


async def get_case_or_404(case_id: int, db: AsyncSession) -> Case:
    stmt = select(Case).where(Case.id == case_id)
    case = (await db.execute(stmt)).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")
    return case
