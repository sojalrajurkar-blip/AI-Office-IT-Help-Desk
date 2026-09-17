from typing import Any, Union
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.dashboard import (
    RequesterDashboardResponse,
    OperatorDashboardResponse,
    TeamLeadDashboardResponse,
    ManagerDashboardResponse,
    AdminDashboardResponse,
)
from app.services.dashboard_service import dashboard_service

router = APIRouter(prefix="/dashboards", tags=["Role Dashboards & Analytics"])

STAFF_ROLES = [UserRole.OPERATOR, UserRole.TEAM_LEAD, UserRole.MANAGER, UserRole.ADMIN]
LEAD_AND_ABOVE = [UserRole.TEAM_LEAD, UserRole.MANAGER, UserRole.ADMIN]
MANAGER_AND_ABOVE = [UserRole.MANAGER, UserRole.ADMIN]


@router.get("/me", response_model=Union[
    RequesterDashboardResponse,
    OperatorDashboardResponse,
    TeamLeadDashboardResponse,
    ManagerDashboardResponse,
    AdminDashboardResponse,
])
async def get_my_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Auto-resolving dashboard endpoint delivering real-time metrics
    customized for the authenticated user's active role.
    """
    if current_user.role == UserRole.REQUESTER:
        return await dashboard_service.get_requester_dashboard(db, current_user)
    elif current_user.role == UserRole.OPERATOR:
        return await dashboard_service.get_operator_dashboard(db, current_user)
    elif current_user.role == UserRole.TEAM_LEAD:
        return await dashboard_service.get_team_lead_dashboard(db, current_user)
    elif current_user.role == UserRole.MANAGER:
        return await dashboard_service.get_manager_dashboard(db, current_user)
    elif current_user.role == UserRole.ADMIN:
        return await dashboard_service.get_admin_dashboard(db, current_user)
    return await dashboard_service.get_requester_dashboard(db, current_user)


@router.get("/requester", response_model=RequesterDashboardResponse)
async def get_requester_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Requester dashboard metrics: active, waiting, and resolved cases.
    """
    return await dashboard_service.get_requester_dashboard(db, current_user)


@router.get("/operator", response_model=OperatorDashboardResponse)
async def get_operator_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(STAFF_ROLES)),
):
    """
    Operator dashboard metrics: assigned queues, SLA warnings, and tasks. Staff only.
    """
    return await dashboard_service.get_operator_dashboard(db, current_user)


@router.get("/team-lead", response_model=TeamLeadDashboardResponse)
async def get_team_lead_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(LEAD_AND_ABOVE)),
):
    """
    Team Lead dashboard metrics: operator workload, unassigned queue, and SLA compliance.
    """
    return await dashboard_service.get_team_lead_dashboard(db, current_user)


@router.get("/manager", response_model=ManagerDashboardResponse)
async def get_manager_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(MANAGER_AND_ABOVE)),
):
    """
    Manager dashboard metrics: organizational KPIs, average resolution time, and team breakdowns.
    """
    return await dashboard_service.get_manager_dashboard(db, current_user)


@router.get("/admin", response_model=AdminDashboardResponse)
async def get_admin_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN])),
):
    """
    Admin dashboard metrics: system-wide resource counts, audit logs, and AI adoption rates. Admin only.
    """
    return await dashboard_service.get_admin_dashboard(db, current_user)
