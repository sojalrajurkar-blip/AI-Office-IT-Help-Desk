import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case
from app.models.category import Category
from app.models.enums import (
    CaseStatus,
    CasePriority,
    EscalationStatus,
    TaskStatus,
    UserRole,
)
from app.models.notification import InAppNotification
from app.models.sla import CaseEscalation, SLAPolicy
from app.models.task import CaseTask
from app.models.timeline_audit import AuditLog
from app.models.user import User, Team
from app.models.ai import AICaseAnalysis
from app.schemas.dashboard import (
    RecentCaseItem,
    RequesterDashboardResponse,
    OperatorDashboardResponse,
    OperatorWorkloadItem,
    TeamLeadDashboardResponse,
    TeamPerformanceItem,
    CategoryBreakdownItem,
    ManagerDashboardResponse,
    AdminDashboardResponse,
)

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = [
    CaseStatus.CONFIRMED,
    CaseStatus.CLOSED,
    CaseStatus.CANCELLED,
    CaseStatus.DUPLICATE,
]


class DashboardService:
    @staticmethod
    async def get_requester_dashboard(db: AsyncSession, user: User) -> RequesterDashboardResponse:
        """
        Dashboard tailored for Requesters (FR-DASH-001).
        """
        # Active cases (non-terminal)
        active_stmt = select(func.count(Case.id)).where(
            Case.requester_id == user.id,
            Case.status.notin_(TERMINAL_STATUSES),
        )
        active_count = (await db.execute(active_stmt)).scalar_one() or 0

        # Waiting for requester (WAITING_FOR_INFO or RESOLUTION_PROPOSED)
        waiting_stmt = select(func.count(Case.id)).where(
            Case.requester_id == user.id,
            Case.status.in_([CaseStatus.WAITING_FOR_INFO, CaseStatus.RESOLUTION_PROPOSED]),
        )
        waiting_count = (await db.execute(waiting_stmt)).scalar_one() or 0

        # Resolved / Closed
        resolved_stmt = select(func.count(Case.id)).where(
            Case.requester_id == user.id,
            Case.status.in_([CaseStatus.CONFIRMED, CaseStatus.CLOSED]),
        )
        resolved_count = (await db.execute(resolved_stmt)).scalar_one() or 0

        # Unread notifications
        notif_stmt = select(func.count(InAppNotification.id)).where(
            InAppNotification.user_id == user.id,
            InAppNotification.is_read == False,
        )
        unread_notifs = (await db.execute(notif_stmt)).scalar_one() or 0

        # Recent cases (top 5)
        recent_stmt = (
            select(Case)
            .where(Case.requester_id == user.id)
            .order_by(Case.updated_at.desc())
            .limit(5)
        )
        recent_cases = list((await db.execute(recent_stmt)).scalars().all())

        return RequesterDashboardResponse(
            active_cases_count=active_count,
            waiting_for_requester_count=waiting_count,
            resolved_cases_count=resolved_count,
            unread_notifications_count=unread_notifs,
            recent_cases=[RecentCaseItem.model_validate(c) for c in recent_cases],
        )

    @staticmethod
    async def get_operator_dashboard(db: AsyncSession, user: User) -> OperatorDashboardResponse:
        """
        Dashboard tailored for IT Operators (FR-DASH-002).
        """
        # Assigned open cases
        assigned_stmt = select(func.count(Case.id)).where(
            Case.assigned_operator_id == user.id,
            Case.status.notin_(TERMINAL_STATUSES),
        )
        assigned_open = (await db.execute(assigned_stmt)).scalar_one() or 0

        # High / Critical priority assigned
        high_pri_stmt = select(func.count(Case.id)).where(
            Case.assigned_operator_id == user.id,
            Case.status.notin_(TERMINAL_STATUSES),
            Case.priority.in_([CasePriority.HIGH, CasePriority.CRITICAL]),
        )
        high_pri_count = (await db.execute(high_pri_stmt)).scalar_one() or 0

        # At-risk cases assigned
        at_risk_stmt = select(func.count(Case.id)).where(
            Case.assigned_operator_id == user.id,
            Case.status.notin_(TERMINAL_STATUSES),
            Case.is_sla_breached == True,
        )
        at_risk_count = (await db.execute(at_risk_stmt)).scalar_one() or 0

        # Waiting for info
        waiting_stmt = select(func.count(Case.id)).where(
            Case.assigned_operator_id == user.id,
            Case.status == CaseStatus.WAITING_FOR_INFO,
        )
        waiting_count = (await db.execute(waiting_stmt)).scalar_one() or 0

        # Pending / In-progress tasks
        task_stmt = select(func.count(CaseTask.id)).where(
            CaseTask.assigned_to_id == user.id,
            CaseTask.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
        )
        pending_tasks = (await db.execute(task_stmt)).scalar_one() or 0

        # Unassigned queue (in operator's team or globally unassigned)
        if user.team_id:
            unassigned_stmt = select(func.count(Case.id)).where(
                Case.assigned_team_id == user.team_id,
                Case.assigned_operator_id.is_(None),
                Case.status.notin_(TERMINAL_STATUSES),
            )
        else:
            unassigned_stmt = select(func.count(Case.id)).where(
                Case.assigned_operator_id.is_(None),
                Case.status.notin_(TERMINAL_STATUSES),
            )
        unassigned_count = (await db.execute(unassigned_stmt)).scalar_one() or 0

        # Escalated cases
        esc_stmt = select(func.count(Case.id)).where(
            or_(Case.assigned_operator_id == user.id, Case.assigned_team_id == user.team_id),
            Case.status == CaseStatus.ESCALATED,
        )
        escalated_count = (await db.execute(esc_stmt)).scalar_one() or 0

        # Resolved today
        now = datetime.now(timezone.utc)
        today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        resolved_today_stmt = select(func.count(Case.id)).where(
            Case.assigned_operator_id == user.id,
            Case.status.in_([CaseStatus.CONFIRMED, CaseStatus.CLOSED]),
            Case.closed_at >= today_start,
        )
        resolved_today = (await db.execute(resolved_today_stmt)).scalar_one() or 0

        # Recent assigned cases
        recent_stmt = (
            select(Case)
            .where(Case.assigned_operator_id == user.id)
            .order_by(Case.updated_at.desc())
            .limit(5)
        )
        recent_cases = list((await db.execute(recent_stmt)).scalars().all())

        return OperatorDashboardResponse(
            assigned_open_cases_count=assigned_open,
            high_priority_cases_count=high_pri_count,
            at_risk_cases_count=at_risk_count,
            waiting_for_info_count=waiting_count,
            pending_tasks_count=pending_tasks,
            unassigned_queue_count=unassigned_count,
            escalated_cases_count=escalated_count,
            resolved_today_count=resolved_today,
            recent_assigned_cases=[RecentCaseItem.model_validate(c) for c in recent_cases],
        )

    @staticmethod
    async def get_team_lead_dashboard(db: AsyncSession, user: User) -> TeamLeadDashboardResponse:
        """
        Dashboard tailored for Team Leads (FR-DASH-003).
        """
        team_id = user.team_id
        team_name = None

        # Resolve team details if user has team or leads one
        if not team_id:
            led_team_stmt = select(Team).where(Team.lead_id == user.id)
            led_team = (await db.execute(led_team_stmt)).scalar_one_or_none()
            if led_team:
                team_id = led_team.id
                team_name = led_team.name
        else:
            team_obj = await db.get(Team, team_id)
            if team_obj:
                team_name = team_obj.name

        base_filter = [Case.assigned_team_id == team_id] if team_id else []

        # Team active cases
        active_stmt = select(func.count(Case.id)).where(
            *base_filter,
            Case.status.notin_(TERMINAL_STATUSES),
        )
        team_active = (await db.execute(active_stmt)).scalar_one() or 0

        # Team unassigned queue
        unassigned_stmt = select(func.count(Case.id)).where(
            *base_filter,
            Case.assigned_operator_id.is_(None),
            Case.status.notin_(TERMINAL_STATUSES),
        )
        team_unassigned = (await db.execute(unassigned_stmt)).scalar_one() or 0

        # Team at risk / breached
        at_risk_stmt = select(func.count(Case.id)).where(
            *base_filter,
            Case.is_sla_breached == True,
            Case.status.notin_(TERMINAL_STATUSES),
        )
        team_at_risk = (await db.execute(at_risk_stmt)).scalar_one() or 0

        # Team escalated
        esc_stmt = select(func.count(Case.id)).where(
            *base_filter,
            Case.status == CaseStatus.ESCALATED,
        )
        team_escalated = (await db.execute(esc_stmt)).scalar_one() or 0

        # Priority breakdown
        pri_stmt = select(Case.priority, func.count(Case.id)).where(
            *base_filter,
            Case.status.notin_(TERMINAL_STATUSES),
        ).group_by(Case.priority)
        pri_rows = (await db.execute(pri_stmt)).all()
        priority_breakdown = {p.value: 0 for p in CasePriority}
        for pri, count in pri_rows:
            if pri:
                priority_breakdown[pri.value] = count

        # Operator workload
        op_workload: List[OperatorWorkloadItem] = []
        if team_id:
            team_members_stmt = select(User).where(
                User.team_id == team_id,
                User.is_active == True,
            )
            members = (await db.execute(team_members_stmt)).scalars().all()
            for m in members:
                m_cases_stmt = select(func.count(Case.id)).where(
                    Case.assigned_operator_id == m.id,
                    Case.status.notin_(TERMINAL_STATUSES),
                )
                m_count = (await db.execute(m_cases_stmt)).scalar_one() or 0
                op_workload.append(OperatorWorkloadItem(
                    operator_id=m.id,
                    operator_name=m.full_name,
                    active_cases=m_count,
                ))

        # Total SLA breaches on team cases
        breach_stmt = select(func.count(Case.id)).where(
            *base_filter,
            Case.is_sla_breached == True,
        )
        sla_breach_count = (await db.execute(breach_stmt)).scalar_one() or 0

        return TeamLeadDashboardResponse(
            team_id=team_id,
            team_name=team_name,
            team_active_cases_count=team_active,
            team_unassigned_cases_count=team_unassigned,
            team_at_risk_cases_count=team_at_risk,
            team_escalated_cases_count=team_escalated,
            priority_breakdown=priority_breakdown,
            operator_workload=op_workload,
            sla_breach_count=sla_breach_count,
        )

    @staticmethod
    async def get_manager_dashboard(db: AsyncSession, user: User) -> ManagerDashboardResponse:
        """
        Dashboard tailored for IT Managers (FR-DASH-004).
        """
        # Total cases
        total_stmt = select(func.count(Case.id))
        total_cases = (await db.execute(total_stmt)).scalar_one() or 0

        # Active cases
        active_stmt = select(func.count(Case.id)).where(Case.status.notin_(TERMINAL_STATUSES))
        active_cases = (await db.execute(active_stmt)).scalar_one() or 0

        # Resolved cases
        resolved_stmt = select(func.count(Case.id)).where(Case.status.in_([CaseStatus.CONFIRMED, CaseStatus.CLOSED]))
        resolved_cases = (await db.execute(resolved_stmt)).scalar_one() or 0

        # Breached cases count
        breached_stmt = select(func.count(Case.id)).where(Case.is_sla_breached == True)
        breached_cases = (await db.execute(breached_stmt)).scalar_one() or 0

        sla_compliance = 100.0
        if total_cases > 0:
            compliant_cases = max(0, total_cases - breached_cases)
            sla_compliance = round((compliant_cases / total_cases) * 100.0, 1)

        # Average resolution time (hours)
        closed_cases_stmt = select(Case.created_at, Case.closed_at).where(
            Case.closed_at.isnot(None)
        )
        closed_rows = (await db.execute(closed_cases_stmt)).all()
        avg_resolution_hours = 0.0
        if closed_rows:
            durations = [(row[1] - row[0]).total_seconds() / 3600.0 for row in closed_rows if row[0] and row[1]]
            if durations:
                avg_resolution_hours = round(sum(durations) / len(durations), 1)

        # Active escalations count
        esc_stmt = select(func.count(CaseEscalation.id)).where(CaseEscalation.status == EscalationStatus.PENDING)
        active_escalations = (await db.execute(esc_stmt)).scalar_one() or 0

        # Reopened cases count
        reopened_stmt = select(func.count(Case.id)).where(Case.status == CaseStatus.REOPENED)
        reopened_cases = (await db.execute(reopened_stmt)).scalar_one() or 0

        # Team performance breakdown
        teams_stmt = select(Team).where(Team.is_active == True)
        teams = list((await db.execute(teams_stmt)).scalars().all())
        team_perf: List[TeamPerformanceItem] = []
        for t in teams:
            t_total = (await db.execute(select(func.count(Case.id)).where(Case.assigned_team_id == t.id))).scalar_one() or 0
            t_active = (await db.execute(select(func.count(Case.id)).where(Case.assigned_team_id == t.id, Case.status.notin_(TERMINAL_STATUSES)))).scalar_one() or 0
            t_resolved = (await db.execute(select(func.count(Case.id)).where(Case.assigned_team_id == t.id, Case.status.in_([CaseStatus.CONFIRMED, CaseStatus.CLOSED])))).scalar_one() or 0
            t_breached = (await db.execute(select(func.count(Case.id)).where(Case.assigned_team_id == t.id, Case.is_sla_breached == True))).scalar_one() or 0
            team_perf.append(TeamPerformanceItem(
                team_id=t.id,
                team_name=t.name,
                total_cases=t_total,
                active_cases=t_active,
                resolved_cases=t_resolved,
                breached_cases=t_breached,
            ))

        # Category breakdown
        cat_stmt = select(Category).where(Category.is_active == True)
        categories = list((await db.execute(cat_stmt)).scalars().all())
        cat_breakdown: List[CategoryBreakdownItem] = []
        for c in categories:
            c_count = (await db.execute(select(func.count(Case.id)).where(Case.category_id == c.id))).scalar_one() or 0
            cat_breakdown.append(CategoryBreakdownItem(
                category_id=c.id,
                category_name=c.name,
                case_count=c_count,
            ))

        return ManagerDashboardResponse(
            total_cases=total_cases,
            active_cases=active_cases,
            resolved_cases=resolved_cases,
            sla_compliance_rate=sla_compliance,
            avg_resolution_time_hours=avg_resolution_hours,
            active_escalations_count=active_escalations,
            reopened_cases_count=reopened_cases,
            team_performance=team_perf,
            category_breakdown=cat_breakdown,
        )

    @staticmethod
    async def get_admin_dashboard(db: AsyncSession, user: User) -> AdminDashboardResponse:
        """
        Dashboard tailored for System Administrators (FR-DASH-005).
        """
        # Total users
        total_users = (await db.execute(select(func.count(User.id)))).scalar_one() or 0

        # Users by role
        role_rows = (await db.execute(select(User.role, func.count(User.id)).group_by(User.role))).all()
        users_by_role = {r.value: 0 for r in UserRole}
        for role, count in role_rows:
            if role:
                users_by_role[role.value] = count

        # Teams count
        total_teams = (await db.execute(select(func.count(Team.id)))).scalar_one() or 0

        # Categories count
        total_categories = (await db.execute(select(func.count(Category.id)))).scalar_one() or 0

        # Active SLA policies
        active_sla = (await db.execute(select(func.count(SLAPolicy.id)).where(SLAPolicy.is_active == True))).scalar_one() or 0

        # Total cases
        total_cases = (await db.execute(select(func.count(Case.id)))).scalar_one() or 0

        # Audit logs count
        total_audit_logs = (await db.execute(select(func.count(AuditLog.id)))).scalar_one() or 0

        # AI analyses stats
        ai_total = (await db.execute(select(func.count(AICaseAnalysis.id)))).scalar_one() or 0
        ai_accepted = (await db.execute(select(func.count(AICaseAnalysis.id)).where(AICaseAnalysis.is_accepted == True))).scalar_one() or 0
        ai_reviewed = (await db.execute(select(func.count(AICaseAnalysis.id)).where((AICaseAnalysis.reviewed_at.isnot(None)) | (AICaseAnalysis.is_accepted == True) | (AICaseAnalysis.is_overridden == True)))).scalar_one() or 0

        ai_acceptance_rate = 100.0
        if ai_reviewed > 0:
            ai_acceptance_rate = round((ai_accepted / ai_reviewed) * 100.0, 1)

        return AdminDashboardResponse(
            total_users=total_users,
            users_by_role=users_by_role,
            total_teams=total_teams,
            total_categories=total_categories,
            active_sla_policies=active_sla,
            total_cases=total_cases,
            total_audit_logs=total_audit_logs,
            ai_analyses_total=ai_total,
            ai_acceptance_rate=ai_acceptance_rate,
        )


dashboard_service = DashboardService()
