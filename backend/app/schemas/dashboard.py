from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict
from app.models.enums import CaseStatus, CasePriority


class RecentCaseItem(BaseModel):
    id: int
    case_number: str
    title: str
    status: CaseStatus
    priority: CasePriority
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RequesterDashboardResponse(BaseModel):
    active_cases_count: int
    waiting_for_requester_count: int
    resolved_cases_count: int
    unread_notifications_count: int
    recent_cases: List[RecentCaseItem]


class OperatorDashboardResponse(BaseModel):
    assigned_open_cases_count: int
    high_priority_cases_count: int
    at_risk_cases_count: int
    waiting_for_info_count: int
    pending_tasks_count: int
    unassigned_queue_count: int
    escalated_cases_count: int
    resolved_today_count: int
    recent_assigned_cases: List[RecentCaseItem]


class OperatorWorkloadItem(BaseModel):
    operator_id: int
    operator_name: str
    active_cases: int


class TeamLeadDashboardResponse(BaseModel):
    team_id: Optional[int] = None
    team_name: Optional[str] = None
    team_active_cases_count: int
    team_unassigned_cases_count: int
    team_at_risk_cases_count: int
    team_escalated_cases_count: int
    priority_breakdown: Dict[str, int]
    operator_workload: List[OperatorWorkloadItem]
    sla_breach_count: int


class TeamPerformanceItem(BaseModel):
    team_id: int
    team_name: str
    total_cases: int
    active_cases: int
    resolved_cases: int
    breached_cases: int


class CategoryBreakdownItem(BaseModel):
    category_id: int
    category_name: str
    case_count: int


class ManagerDashboardResponse(BaseModel):
    total_cases: int
    active_cases: int
    resolved_cases: int
    sla_compliance_rate: float
    avg_resolution_time_hours: float
    active_escalations_count: int
    reopened_cases_count: int
    team_performance: List[TeamPerformanceItem]
    category_breakdown: List[CategoryBreakdownItem]


class AdminDashboardResponse(BaseModel):
    total_users: int
    users_by_role: Dict[str, int]
    total_teams: int
    total_categories: int
    active_sla_policies: int
    total_cases: int
    total_audit_logs: int
    ai_analyses_total: int
    ai_acceptance_rate: float
