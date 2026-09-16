import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.case import Case
from app.models.communication import CaseMessage
from app.models.enums import (
    CasePriority,
    CaseSeverity,
    CaseStatus,
    EscalationStatus,
    MessageType,
    RiskLevel,
    UserRole,
)
from app.models.sla import CaseEscalation, CaseRiskRecord, SLAPolicy
from app.models.timeline_audit import TimelineEvent
from app.models.user import User
from app.schemas.sla import (
    CaseRiskEvaluationResponse,
    CaseSLAStatusResponse,
    SLASweepSummaryResponse,
)
from app.services.timeline_service import TimelineService

logger = logging.getLogger(__name__)


class SLAService:
    @staticmethod
    def get_case_sla_status(case: Case) -> CaseSLAStatusResponse:
        now = datetime.now(timezone.utc)
        resp_remaining = None
        resol_remaining = None
        pct_elapsed = 0.0
        is_resp_breached = False
        is_resol_breached = False
        warning_msg = None

        if case.response_deadline:
            delta = (case.response_deadline - now).total_seconds() / 60
            resp_remaining = round(delta, 1)
            if delta < 0 and case.status == CaseStatus.REPORTED:
                is_resp_breached = True

        if case.resolution_deadline:
            delta = (case.resolution_deadline - now).total_seconds() / 60
            resol_remaining = round(delta, 1)
            terminal_states = [CaseStatus.CONFIRMED, CaseStatus.CLOSED, CaseStatus.CANCELLED, CaseStatus.DUPLICATE]
            if delta < 0 and case.status not in terminal_states:
                is_resol_breached = True

            if case.created_at:
                total_sec = (case.resolution_deadline - case.created_at).total_seconds()
                if total_sec > 0:
                    elapsed_sec = (now - case.created_at).total_seconds()
                    pct_elapsed = round(min(100.0, max(0.0, (elapsed_sec / total_sec) * 100.0)), 1)
                    if elapsed_sec > total_sec:
                        pct_elapsed = round((elapsed_sec / total_sec) * 100.0, 1)

        is_breached = case.is_sla_breached or is_resp_breached or is_resol_breached
        is_at_risk = pct_elapsed >= 75.0 or is_breached

        if is_breached:
            warning_msg = "SLA deadline has been breached."
        elif pct_elapsed >= 75.0:
            warning_msg = f"Over {pct_elapsed}% of SLA resolution window has elapsed."

        return CaseSLAStatusResponse(
            case_id=case.id,
            case_number=case.case_number,
            priority=case.priority,
            response_deadline=case.response_deadline,
            resolution_deadline=case.resolution_deadline,
            response_time_remaining_minutes=resp_remaining,
            resolution_time_remaining_minutes=resol_remaining,
            percentage_time_elapsed=pct_elapsed,
            is_response_breached=is_resp_breached,
            is_resolution_breached=is_resol_breached,
            is_sla_breached=is_breached,
            sla_breached_at=case.sla_breached_at,
            is_at_risk=is_at_risk,
            warning_message=warning_msg,
        )

    @staticmethod
    async def check_and_apply_sla_breach(case: Case, db: AsyncSession) -> bool:
        now = datetime.now(timezone.utc)
        terminal_states = [CaseStatus.CONFIRMED, CaseStatus.CLOSED, CaseStatus.CANCELLED, CaseStatus.DUPLICATE]
        if case.status in terminal_states:
            return False

        breached = False
        breach_reason = ""

        if case.response_deadline and now > case.response_deadline and case.status == CaseStatus.REPORTED:
            breached = True
            breach_reason = "Initial response deadline passed without assignment/investigation."
        elif case.resolution_deadline and now > case.resolution_deadline:
            breached = True
            breach_reason = "Target resolution deadline passed without resolution."

        if breached and not case.is_sla_breached:
            case.is_sla_breached = True
            case.sla_breached_at = now
            await TimelineService.record_event(
                db=db,
                case_id=case.id,
                event_type="SLA_BREACHED",
                summary=f"SLA breached: {breach_reason}",
                details={"sla_breached_at": now.isoformat(), "reason": breach_reason},
            )
            return True

        return False

    @staticmethod
    async def evaluate_case_risk(
        case: Case,
        db: AsyncSession,
        actor: Optional[User] = None,
    ) -> CaseRiskRecord:
        """
        Evaluates 7 core multi-factor risk signals specified in Section 11 of the system requirements:
        1. Approaching or breached deadlines
        2. Inactivity duration
        3. Repeated follow-ups without response
        4. Reassignment frequency
        5. Reopened status
        6. Stale waiting-for-info state
        7. High severity / critical disruption
        """
        now = datetime.now(timezone.utc)
        risk_score = 0
        reasons: List[str] = []

        # 1. SLA Deadlines
        sla_status = SLAService.get_case_sla_status(case)
        if sla_status.is_sla_breached:
            risk_score += 40
            reasons.append("SLA target deadline has been breached.")
        elif sla_status.is_at_risk:
            risk_score += 25
            reasons.append(f"Approaching deadline ({sla_status.percentage_time_elapsed}% time elapsed).")

        # 2. Inactivity
        inactivity_delta = (now - case.updated_at).total_seconds() / 3600
        if case.priority in [CasePriority.CRITICAL, CasePriority.HIGH] and inactivity_delta >= 2.0:
            risk_score += 20
            reasons.append(f"Inactivity: No updates for {round(inactivity_delta, 1)} hours on high-priority ticket.")
        elif inactivity_delta >= 8.0:
            risk_score += 15
            reasons.append(f"Inactivity: No updates for {round(inactivity_delta, 1)} hours.")

        # 3. Repeated Requester Follow-ups
        msgs_stmt = (
            select(CaseMessage)
            .where(CaseMessage.case_id == case.id)
            .order_by(CaseMessage.created_at.desc())
            .limit(5)
        )
        recent_msgs = (await db.execute(msgs_stmt)).scalars().all()
        consecutive_requester_msgs = 0
        for m in recent_msgs:
            if m.sender_id == case.requester_id and m.message_type == MessageType.COMMUNICATION:
                consecutive_requester_msgs += 1
            else:
                break
        if consecutive_requester_msgs >= 2:
            risk_score += 20
            reasons.append(f"Requester has sent {consecutive_requester_msgs} messages waiting for IT response.")

        # 4. Multiple Reassignments
        events_stmt = (
            select(TimelineEvent)
            .where(TimelineEvent.case_id == case.id, TimelineEvent.event_type.in_(["CASE_ASSIGNED", "CASE_REASSIGNED"]))
        )
        assign_events = (await db.execute(events_stmt)).scalars().all()
        if len(assign_events) >= 3:
            risk_score += 20
            reasons.append(f"Case has been reassigned {len(assign_events)} times.")

        # 5. Reopened status
        if case.status == CaseStatus.REOPENED:
            risk_score += 25
            reasons.append("Case was previously closed and reopened by requester.")

        # 6. Stale in WAITING_FOR_INFO
        if case.status == CaseStatus.WAITING_FOR_INFO and inactivity_delta >= 24.0:
            risk_score += 15
            reasons.append("Case has been waiting for info for over 24 hours.")

        # 7. Critical Severity / High Blast Radius
        if case.severity == CaseSeverity.CRITICAL:
            risk_score += 25
            reasons.append("Critical severity with potential widespread office disruption.")

        # Determine level based on cumulative score
        if risk_score >= 50:
            level = RiskLevel.CRITICAL
        elif risk_score >= 35:
            level = RiskLevel.HIGH
        elif risk_score >= 20:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW

        if not reasons:
            reasons.append("Standard operating parameters; no active risk flags.")

        # Query existing active risk record or create new
        existing_stmt = (
            select(CaseRiskRecord)
            .where(CaseRiskRecord.case_id == case.id, CaseRiskRecord.is_resolved.is_(False))
            .order_by(CaseRiskRecord.detected_at.desc())
            .limit(1)
        )
        risk_record = (await db.execute(existing_stmt)).scalar_one_or_none()

        if not risk_record:
            risk_record = CaseRiskRecord(
                case_id=case.id,
                risk_level=level,
                reasons=reasons,
                is_resolved=False,
                detected_at=now,
            )
            db.add(risk_record)
            await db.flush()
        else:
            old_level = risk_record.risk_level
            risk_record.risk_level = level
            risk_record.reasons = reasons

            # If risk elevated to HIGH or CRITICAL, record timeline event
            if level in [RiskLevel.HIGH, RiskLevel.CRITICAL] and old_level not in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                await TimelineService.record_event(
                    db=db,
                    case_id=case.id,
                    event_type="RISK_ELEVATED",
                    summary=f"Risk level elevated to {level.value}: {reasons[0]}",
                    actor=actor,
                    details={"risk_level": level.value, "reasons": reasons},
                )

        return risk_record

    @staticmethod
    async def escalate_case(
        case: Case,
        user: User,
        reason: str,
        target_role: UserRole,
        db: AsyncSession,
    ) -> CaseEscalation:
        now = datetime.now(timezone.utc)
        escalation = CaseEscalation(
            case_id=case.id,
            escalated_by_id=user.id,
            target_role=target_role,
            reason=reason,
            status=EscalationStatus.PENDING,
            created_at=now,
        )
        db.add(escalation)
        case.status = CaseStatus.ESCALATED
        case.updated_at = now

        await db.flush()

        await TimelineService.record_event(
            db=db,
            case_id=case.id,
            event_type="CASE_ESCALATED",
            summary=f"Case escalated to {target_role.value} by {user.full_name}. Reason: {reason}",
            actor=user,
            details={
                "escalation_id": escalation.id,
                "target_role": target_role.value,
                "reason": reason,
            },
        )
        return escalation

    @staticmethod
    async def resolve_escalation(
        escalation: CaseEscalation,
        resolver: User,
        resolution_notes: str,
        next_status: Optional[CaseStatus],
        db: AsyncSession,
    ) -> CaseEscalation:
        now = datetime.now(timezone.utc)
        escalation.status = EscalationStatus.RESOLVED
        escalation.resolution_notes = resolution_notes
        escalation.resolved_by_id = resolver.id
        escalation.resolved_at = now

        case = await db.get(Case, escalation.case_id)
        if case and case.status == CaseStatus.ESCALATED:
            case.status = next_status or CaseStatus.INVESTIGATING
            case.updated_at = now

        await TimelineService.record_event(
            db=db,
            case_id=escalation.case_id,
            event_type="ESCALATION_RESOLVED",
            summary=f"Escalation resolved by {resolver.full_name}. Case status set to {case.status.value if case else 'INVESTIGATING'}.",
            actor=resolver,
            details={
                "escalation_id": escalation.id,
                "resolution_notes": resolution_notes,
                "new_status": case.status.value if case else None,
            },
        )
        return escalation

    @staticmethod
    async def run_sla_and_risk_sweep(db: AsyncSession) -> SLASweepSummaryResponse:
        """
        Lightweight batch sweep over active tickets to update SLA breach flags and risk assessments.
        """
        terminal_states = [CaseStatus.CONFIRMED, CaseStatus.CLOSED, CaseStatus.CANCELLED, CaseStatus.DUPLICATE]
        stmt = select(Case).where(Case.status.notin_(terminal_states))
        active_cases = (await db.execute(stmt)).scalars().all()

        breaches = 0
        at_risk = 0
        updated_numbers: List[str] = []

        for c in active_cases:
            breached = await SLAService.check_and_apply_sla_breach(c, db)
            if breached:
                breaches += 1
                updated_numbers.append(c.case_number)

            risk_rec = await SLAService.evaluate_case_risk(c, db)
            if risk_rec.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                at_risk += 1
                if c.case_number not in updated_numbers:
                    updated_numbers.append(c.case_number)

        await db.commit()

        return SLASweepSummaryResponse(
            total_scanned=len(active_cases),
            breaches_detected=breaches,
            at_risk_detected=at_risk,
            updated_cases=updated_numbers,
        )


sla_service = SLAService()
