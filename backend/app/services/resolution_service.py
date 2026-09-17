import logging
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case
from app.models.enums import CaseStatus, ResolutionStatus, UserRole, NotificationType
from app.models.resolution import CaseResolution
from app.models.timeline_audit import AuditLog
from app.models.user import User
from app.services.case_lifecycle import CaseLifecycleService
from app.services.timeline_service import TimelineService
from app.services.notification_service import (
    create_notification,
    create_team_notifications,
)

logger = logging.getLogger(__name__)


class ResolutionService:
    @staticmethod
    async def propose_resolution(
        db: AsyncSession,
        case: Case,
        operator: User,
        actions_taken: str,
        findings: Optional[str] = None,
        remaining_issues: Optional[str] = None,
    ) -> CaseResolution:
        """
        Operator submits a formal proposed resolution for a case.
        Transitions case status to RESOLUTION_PROPOSED.
        """
        # 1. Validate lifecycle transition
        CaseLifecycleService.validate_transition(case, CaseStatus.RESOLUTION_PROPOSED, operator)

        now = datetime.now(timezone.utc)

        # 2. Create resolution record
        resolution = CaseResolution(
            case_id=case.id,
            operator_id=operator.id,
            actions_taken=actions_taken,
            findings=findings,
            remaining_issues=remaining_issues,
            status=ResolutionStatus.PROPOSED,
            proposed_at=now,
        )
        db.add(resolution)
        await db.flush()

        # 3. Update case status
        case.status = CaseStatus.RESOLUTION_PROPOSED
        case.updated_at = now

        # 4. Record Timeline event & Audit log
        await TimelineService.record_event(
            db=db,
            case_id=case.id,
            event_type="RESOLUTION_PROPOSED",
            summary=f"Resolution proposed by {operator.full_name}",
            actor=operator,
            details={
                "resolution_id": resolution.id,
                "actions_taken": actions_taken[:150],
                "findings": findings,
            },
        )

        audit = AuditLog(
            actor_id=operator.id,
            action="PROPOSE_RESOLUTION",
            entity_type="Case",
            entity_id=str(case.id),
            previous_state={"status": case.status.value},
            new_state={"status": CaseStatus.RESOLUTION_PROPOSED.value, "resolution_id": resolution.id},
            context_notes=actions_taken,
        )
        db.add(audit)

        # 5. Dispatch notification to requester
        if case.requester_id:
            await create_notification(
                db=db,
                user_id=case.requester_id,
                notification_type=NotificationType.RESOLUTION,
                title=f"Resolution Proposed: {case.case_number}",
                message=f"A resolution has been proposed for case {case.case_number}. Please verify the fix and confirm or provide feedback.",
                case_id=case.id,
            )

        # Load relation
        stmt = (
            select(CaseResolution)
            .options(selectinload(CaseResolution.operator))
            .where(CaseResolution.id == resolution.id)
        )
        return (await db.execute(stmt)).scalar_one()

    @staticmethod
    async def confirm_resolution(
        db: AsyncSession,
        case: Case,
        user: User,
        feedback: Optional[str] = None,
    ) -> CaseResolution:
        """
        Requester confirms proposed resolution.
        Transitions case to CLOSED.
        """
        if user.role == UserRole.REQUESTER and case.requester_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the case requester can confirm this resolution.",
            )

        if case.status != CaseStatus.RESOLUTION_PROPOSED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot confirm resolution on a case in '{case.status.value}' status. Must be in 'RESOLUTION_PROPOSED'.",
            )

        # Find latest pending resolution
        stmt = (
            select(CaseResolution)
            .where(
                CaseResolution.case_id == case.id,
                CaseResolution.status == ResolutionStatus.PROPOSED,
            )
            .order_by(CaseResolution.proposed_at.desc())
        )
        resolution = (await db.execute(stmt)).scalars().first()
        if not resolution:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No pending proposed resolution found for this case.",
            )

        now = datetime.now(timezone.utc)
        resolution.status = ResolutionStatus.CONFIRMED
        resolution.confirmed_at = now
        resolution.requester_feedback = feedback

        # Update case to CLOSED
        case.status = CaseStatus.CLOSED
        case.closed_at = now
        case.updated_at = now

        # Record Timeline events
        summary_confirm = f"Resolution confirmed by {user.full_name}."
        if feedback:
            summary_confirm += f" Feedback: {feedback}"

        await TimelineService.record_event(
            db=db,
            case_id=case.id,
            event_type="RESOLUTION_CONFIRMED",
            summary=summary_confirm,
            actor=user,
            details={"resolution_id": resolution.id, "feedback": feedback},
        )

        await TimelineService.record_event(
            db=db,
            case_id=case.id,
            event_type="CASE_CLOSED",
            summary=f"Case {case.case_number} closed successfully.",
            actor=user,
            details={"closed_at": now.isoformat()},
        )

        audit = AuditLog(
            actor_id=user.id,
            action="CONFIRM_RESOLUTION",
            entity_type="Case",
            entity_id=str(case.id),
            previous_state={"status": CaseStatus.RESOLUTION_PROPOSED.value},
            new_state={"status": CaseStatus.CLOSED.value},
            context_notes=feedback,
        )
        db.add(audit)

        # Notify assigned operator
        if case.assigned_operator_id and case.assigned_operator_id != user.id:
            await create_notification(
                db=db,
                user_id=case.assigned_operator_id,
                notification_type=NotificationType.RESOLUTION,
                title=f"Case Confirmed & Closed: {case.case_number}",
                message=f"Requester {user.full_name} confirmed the resolution for case {case.case_number}.",
                case_id=case.id,
            )

        stmt = (
            select(CaseResolution)
            .options(selectinload(CaseResolution.operator))
            .where(CaseResolution.id == resolution.id)
        )
        return (await db.execute(stmt)).scalar_one()

    @staticmethod
    async def reject_resolution(
        db: AsyncSession,
        case: Case,
        user: User,
        rejection_reason: str,
    ) -> CaseResolution:
        """
        Requester rejects proposed resolution.
        Transitions case to REOPENED for further investigation.
        """
        if user.role == UserRole.REQUESTER and case.requester_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the case requester can reject this resolution.",
            )

        if case.status != CaseStatus.RESOLUTION_PROPOSED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reject resolution on a case in '{case.status.value}' status. Must be in 'RESOLUTION_PROPOSED'.",
            )

        stmt = (
            select(CaseResolution)
            .where(
                CaseResolution.case_id == case.id,
                CaseResolution.status == ResolutionStatus.PROPOSED,
            )
            .order_by(CaseResolution.proposed_at.desc())
        )
        resolution = (await db.execute(stmt)).scalars().first()
        if not resolution:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No pending proposed resolution found for this case.",
            )

        now = datetime.now(timezone.utc)
        resolution.status = ResolutionStatus.REJECTED
        resolution.rejection_reason = rejection_reason

        # Reopen case
        case.status = CaseStatus.REOPENED
        case.updated_at = now

        # Timeline events
        await TimelineService.record_event(
            db=db,
            case_id=case.id,
            event_type="RESOLUTION_REJECTED",
            summary=f"Resolution rejected by {user.full_name}. Reason: {rejection_reason}",
            actor=user,
            details={"resolution_id": resolution.id, "rejection_reason": rejection_reason},
        )

        await TimelineService.record_event(
            db=db,
            case_id=case.id,
            event_type="CASE_REOPENED",
            summary=f"Case {case.case_number} reopened for further investigation.",
            actor=user,
            details={"reopened_at": now.isoformat()},
        )

        audit = AuditLog(
            actor_id=user.id,
            action="REJECT_RESOLUTION",
            entity_type="Case",
            entity_id=str(case.id),
            previous_state={"status": CaseStatus.RESOLUTION_PROPOSED.value},
            new_state={"status": CaseStatus.REOPENED.value},
            context_notes=rejection_reason,
        )
        db.add(audit)

        # Notify operator and team
        if case.assigned_operator_id:
            await create_notification(
                db=db,
                user_id=case.assigned_operator_id,
                notification_type=NotificationType.REOPENED,
                title=f"Case Reopened: {case.case_number}",
                message=f"Requester {user.full_name} rejected the proposed resolution for case {case.case_number}: '{rejection_reason}'",
                case_id=case.id,
            )
        elif case.assigned_team_id:
            await create_team_notifications(
                db=db,
                team_id=case.assigned_team_id,
                notification_type=NotificationType.REOPENED,
                title=f"Case Reopened: {case.case_number}",
                message=f"Requester {user.full_name} rejected the proposed resolution for case {case.case_number}: '{rejection_reason}'",
                case_id=case.id,
                exclude_user_id=user.id,
            )

        stmt = (
            select(CaseResolution)
            .options(selectinload(CaseResolution.operator))
            .where(CaseResolution.id == resolution.id)
        )
        return (await db.execute(stmt)).scalar_one()

    @staticmethod
    async def get_case_resolutions(
        db: AsyncSession,
        case_id: int,
    ) -> List[CaseResolution]:
        """
        Lists all resolution proposals and attempts for a case.
        """
        stmt = (
            select(CaseResolution)
            .options(selectinload(CaseResolution.operator))
            .where(CaseResolution.case_id == case_id)
            .order_by(CaseResolution.proposed_at.desc())
        )
        return list((await db.execute(stmt)).scalars().all())


resolution_service = ResolutionService()
