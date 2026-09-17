from datetime import datetime, timedelta, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.enums import UserRole, CaseStatus, CasePriority, CaseSeverity, NotificationType
from app.models.user import User, Team
from app.models.category import Category
from app.models.case import Case, CaseSequence
from app.models.sla import SLAPolicy
from app.models.timeline_audit import TimelineEvent, AuditLog
from app.schemas.case import (
    CaseCreate,
    CaseUpdate,
    CaseStatusUpdate,
    CaseAssign,
    CaseResponse,
    CaseListResponse,
    TimelineEventResponse,
)
from app.services.case_lifecycle import CaseLifecycleService
from app.services.timeline_service import TimelineService
from app.services.notification_service import (
    create_notification,
    create_team_notifications,
    create_role_notifications,
)


router = APIRouter(prefix="/cases", tags=["Case Management"])


@router.post("/", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    case_in: CaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new IT support case with atomic sequential case number and SLA deadlines."""
    # 1. Resolve Category and priority
    category = None
    default_team_id = None
    priority = case_in.priority

    if case_in.category_id:
        stmt = select(Category).where(Category.id == case_in.category_id)
        category = (await db.execute(stmt)).scalar_one_or_none()
        if not category:
            raise HTTPException(status_code=400, detail="Invalid category_id specified.")
        if not priority:
            priority = category.default_priority
        default_team_id = category.default_team_id

    if not priority:
        priority = CasePriority.MEDIUM

    severity = case_in.severity or CaseSeverity.MODERATE

    # 2. Atomic Case Number generation (IT-10001)
    seq = CaseSequence()
    db.add(seq)
    await db.flush()
    case_number = f"IT-{10000 + seq.id}"

    # 3. Calculate SLA deadlines based on priority
    now = datetime.now(timezone.utc)
    response_deadline = None
    resolution_deadline = None

    sla_stmt = select(SLAPolicy).where(SLAPolicy.priority == priority, SLAPolicy.is_active.is_(True))
    sla_policy = (await db.execute(sla_stmt)).scalar_one_or_none()
    if sla_policy:
        response_deadline = now + timedelta(hours=sla_policy.response_time_hours)
        resolution_deadline = now + timedelta(hours=sla_policy.resolution_time_hours)

    # 4. Instantiate Case
    case = Case(
        case_number=case_number,
        title=case_in.title,
        description=case_in.description,
        office_location=case_in.office_location or current_user.office_location,
        status=CaseStatus.REPORTED,
        priority=priority,
        severity=severity,
        category_id=category.id if category else None,
        requester_id=current_user.id,
        assigned_team_id=default_team_id,
        response_deadline=response_deadline,
        resolution_deadline=resolution_deadline,
        created_at=now,
        updated_at=now,
    )
    db.add(case)
    await db.flush()

    # 5. Record Timeline Event and Audit Log
    await TimelineService.record_event(
        db=db,
        case_id=case.id,
        event_type="CASE_CREATED",
        summary=f"Case reported by {current_user.full_name}",
        actor=current_user,
        details={"case_number": case_number, "priority": priority.value, "severity": severity.value},
    )

    audit = AuditLog(
        actor_id=current_user.id,
        action="CREATE_CASE",
        entity_type="Case",
        entity_id=str(case.id),
        new_state={"case_number": case_number, "title": case.title, "status": "REPORTED"},
    )
    db.add(audit)

    # 6. Dispatch Notifications
    if default_team_id:
        await create_team_notifications(
            db=db,
            team_id=default_team_id,
            notification_type=NotificationType.NEW_CASE,
            title=f"New Case: {case_number}",
            message=f"A new case '{case.title}' has been submitted and routed to your team.",
            case_id=case.id,
            exclude_user_id=current_user.id,
        )
    else:
        await create_role_notifications(
            db=db,
            roles=[UserRole.OPERATOR, UserRole.TEAM_LEAD, UserRole.MANAGER],
            notification_type=NotificationType.NEW_CASE,
            title=f"New Case: {case_number}",
            message=f"A new unassigned case '{case.title}' has been reported.",
            case_id=case.id,
            exclude_user_id=current_user.id,
        )

    await db.commit()

    # Return refreshed case with eager relations
    return await get_case_by_id(case.id, db)



@router.get("/", response_model=CaseListResponse)
async def list_cases(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[CaseStatus] = None,
    priority: Optional[CasePriority] = None,
    category_id: Optional[int] = None,
    assigned_team_id: Optional[int] = None,
    assigned_operator_id: Optional[int] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List cases with role-based visibility and comprehensive filtering."""
    query = select(Case).options(
        selectinload(Case.requester),
        selectinload(Case.assigned_operator),
        selectinload(Case.assigned_team),
        selectinload(Case.category),
    )

    # Role Visibility: Requesters only see their own cases
    if current_user.role == UserRole.REQUESTER:
        query = query.where(Case.requester_id == current_user.id)

    # Optional Filters
    if status:
        query = query.where(Case.status == status)
    if priority:
        query = query.where(Case.priority == priority)
    if category_id:
        query = query.where(Case.category_id == category_id)
    if assigned_team_id:
        query = query.where(Case.assigned_team_id == assigned_team_id)
    if assigned_operator_id:
        query = query.where(Case.assigned_operator_id == assigned_operator_id)

    # Search query in case_number, title, or description
    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                Case.case_number.ilike(search_pattern),
                Case.title.ilike(search_pattern),
                Case.description.ilike(search_pattern),
                Case.office_location.ilike(search_pattern),
            )
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate and order by newest first
    offset = (page - 1) * size
    query = query.order_by(Case.created_at.desc()).offset(offset).limit(size)
    results = (await db.execute(query)).scalars().all()

    return CaseListResponse(items=list(results), total=total, page=page, size=size)


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve detailed case information with full relations."""
    case = await get_case_by_id(case_id, db)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    # Requesters can only access their own cases
    if current_user.role == UserRole.REQUESTER and case.requester_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied to this case.")

    return case


@router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: int,
    case_in: CaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update case details."""
    case = await get_case_by_id(case_id, db)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    if current_user.role == UserRole.REQUESTER:
        if case.requester_id != current_user.id:
            raise HTTPException(status_code=403, detail="Cannot edit cases belonging to others.")
        if case.status not in {CaseStatus.REPORTED, CaseStatus.WAITING_FOR_INFO}:
            raise HTTPException(status_code=400, detail="Cannot edit case details after investigation has begun.")

    if case_in.title is not None:
        case.title = case_in.title
    if case_in.description is not None:
        case.description = case_in.description
    if case_in.office_location is not None:
        case.office_location = case_in.office_location
    if case_in.category_id is not None:
        case.category_id = case_in.category_id
    if case_in.priority is not None and current_user.role != UserRole.REQUESTER:
        case.priority = case_in.priority
    if case_in.severity is not None and current_user.role != UserRole.REQUESTER:
        case.severity = case_in.severity

    case.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return await get_case_by_id(case_id, db)


@router.post("/{case_id}/status", response_model=CaseResponse)
async def update_case_status(
    case_id: int,
    status_in: CaseStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Execute a validated case status transition in the lifecycle engine."""
    case = await get_case_by_id(case_id, db)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    old_status = case.status
    new_status = status_in.new_status

    # Validate transition through CaseLifecycleService
    CaseLifecycleService.validate_transition(case=case, new_status=new_status, actor=current_user)

    case.status = new_status
    case.updated_at = datetime.now(timezone.utc)
    if new_status == CaseStatus.CLOSED:
        case.closed_at = datetime.now(timezone.utc)

    # Record Timeline Event
    summary = f"Status changed from {old_status.value} to {new_status.value}"
    if status_in.notes:
        summary += f" ({status_in.notes})"

    await TimelineService.record_event(
        db=db,
        case_id=case.id,
        event_type="STATUS_CHANGED",
        summary=summary,
        actor=current_user,
        details={"old_status": old_status.value, "new_status": new_status.value, "notes": status_in.notes},
    )

    # Record Audit Log
    audit = AuditLog(
        actor_id=current_user.id,
        action="STATUS_CHANGE",
        entity_type="Case",
        entity_id=str(case.id),
        previous_state={"status": old_status.value},
        new_state={"status": new_status.value},
        context_notes=status_in.notes,
    )
    db.add(audit)

    await db.commit()
    return await get_case_by_id(case.id, db)


@router.post("/{case_id}/assign", response_model=CaseResponse)
async def assign_case(
    case_id: int,
    assign_in: CaseAssign,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles([UserRole.OPERATOR, UserRole.TEAM_LEAD, UserRole.MANAGER, UserRole.ADMIN])
    ),
):
    """Assign or reassign a case to an IT team and/or operator."""
    case = await get_case_by_id(case_id, db)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    old_team_id = case.assigned_team_id
    old_operator_id = case.assigned_operator_id
    is_reassignment = old_team_id is not None or old_operator_id is not None

    if assign_in.assigned_team_id is not None:
        case.assigned_team_id = assign_in.assigned_team_id
    if assign_in.assigned_operator_id is not None:
        case.assigned_operator_id = assign_in.assigned_operator_id

    # If case was REPORTED or UNDERSTOOD, auto-transition to ASSIGNED
    if case.status in {CaseStatus.REPORTED, CaseStatus.UNDERSTOOD}:
        case.status = CaseStatus.ASSIGNED

    case.updated_at = datetime.now(timezone.utc)

    event_type = "CASE_REASSIGNED" if is_reassignment else "CASE_ASSIGNED"
    summary = f"Case assigned by {current_user.full_name}"
    if assign_in.notes:
        summary += f" ({assign_in.notes})"

    await TimelineService.record_event(
        db=db,
        case_id=case.id,
        event_type=event_type,
        summary=summary,
        actor=current_user,
        details={
            "old_team_id": old_team_id,
            "new_team_id": case.assigned_team_id,
            "old_operator_id": old_operator_id,
            "new_operator_id": case.assigned_operator_id,
            "notes": assign_in.notes,
        },
    )

    audit = AuditLog(
        actor_id=current_user.id,
        action="ASSIGN_CASE",
        entity_type="Case",
        entity_id=str(case.id),
        previous_state={"team_id": old_team_id, "operator_id": old_operator_id},
        new_state={"team_id": case.assigned_team_id, "operator_id": case.assigned_operator_id},
        context_notes=assign_in.notes,
    )
    db.add(audit)

    # Dispatch assignment notification
    if case.assigned_operator_id and (case.assigned_operator_id != old_operator_id or old_operator_id is None):
        await create_notification(
            db=db,
            user_id=case.assigned_operator_id,
            notification_type=NotificationType.ASSIGNMENT,
            title=f"Case Assigned: {case.case_number}",
            message=f"You have been assigned to case {case.case_number}: {case.title}.",
            case_id=case.id,
        )
    elif case.assigned_team_id and (case.assigned_team_id != old_team_id or old_team_id is None):
        await create_team_notifications(
            db=db,
            team_id=case.assigned_team_id,
            notification_type=NotificationType.ASSIGNMENT,
            title=f"Team Case Assigned: {case.case_number}",
            message=f"Case {case.case_number} has been assigned to your team.",
            case_id=case.id,
            exclude_user_id=current_user.id,
        )

    await db.commit()
    return await get_case_by_id(case.id, db)



@router.get("/{case_id}/timeline", response_model=List[TimelineEventResponse])
async def get_case_timeline(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve chronological timeline story of a case."""
    case = await get_case_by_id(case_id, db)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    if current_user.role == UserRole.REQUESTER and case.requester_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied to this case timeline.")

    stmt = (
        select(TimelineEvent)
        .options(selectinload(TimelineEvent.actor))
        .where(TimelineEvent.case_id == case_id)
        .order_by(TimelineEvent.created_at.asc())
    )
    events = (await db.execute(stmt)).scalars().all()
    return list(events)


async def get_case_by_id(case_id: int, db: AsyncSession) -> Optional[Case]:
    stmt = (
        select(Case)
        .options(
            selectinload(Case.requester),
            selectinload(Case.assigned_operator),
            selectinload(Case.assigned_team),
            selectinload(Case.category),
        )
        .where(Case.id == case_id)
    )
    return (await db.execute(stmt)).scalar_one_or_none()
