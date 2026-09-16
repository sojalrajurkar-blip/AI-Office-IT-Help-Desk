from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.enums import UserRole, TaskStatus
from app.models.user import User
from app.models.case import Case
from app.models.task import CaseTask, InvestigationRecord
from app.schemas.task import (
    TaskCreate,
    TaskUpdate,
    TaskResponse,
    InvestigationRecordCreate,
    InvestigationRecordResponse,
)
from app.services.timeline_service import TimelineService

router = APIRouter(tags=["Tasks & Investigation"])


@router.post("/cases/{case_id}/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    case_id: int,
    task_in: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles([UserRole.OPERATOR, UserRole.TEAM_LEAD, UserRole.MANAGER, UserRole.ADMIN])
    ),
):
    """Create a new task connected to a case."""
    stmt = select(Case).where(Case.id == case_id)
    case = (await db.execute(stmt)).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    task = CaseTask(
        case_id=case_id,
        title=task_in.title,
        description=task_in.description,
        status=TaskStatus.PENDING,
        assigned_to_id=task_in.assigned_to_id,
        created_by_id=current_user.id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(task)
    await db.flush()

    await TimelineService.record_event(
        db=db,
        case_id=case.id,
        event_type="TASK_CREATED",
        summary=f"Task '{task.title}' created by {current_user.full_name}",
        actor=current_user,
        details={"task_id": task.id, "title": task.title},
    )

    await db.commit()
    return await get_task_by_id(task.id, db)


@router.get("/cases/{case_id}/tasks", response_model=List[TaskResponse])
async def list_tasks(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all tasks associated with a case."""
    stmt = (
        select(CaseTask)
        .options(selectinload(CaseTask.assigned_to), selectinload(CaseTask.created_by))
        .where(CaseTask.case_id == case_id)
        .order_by(CaseTask.created_at.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_in: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles([UserRole.OPERATOR, UserRole.TEAM_LEAD, UserRole.MANAGER, UserRole.ADMIN])
    ),
):
    """Update task status, assignee, or findings."""
    task = await get_task_by_id(task_id, db)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    old_status = task.status

    if task_in.title is not None:
        task.title = task_in.title
    if task_in.description is not None:
        task.description = task_in.description
    if task_in.assigned_to_id is not None:
        task.assigned_to_id = task_in.assigned_to_id
    if task_in.findings is not None:
        task.findings = task_in.findings
    if task_in.status is not None:
        task.status = task_in.status
        if task_in.status == TaskStatus.COMPLETED:
            task.completed_at = datetime.now(timezone.utc)

    # Record Timeline Event if status completed
    if task_in.status and task_in.status != old_status:
        await TimelineService.record_event(
            db=db,
            case_id=task.case_id,
            event_type="TASK_UPDATED",
            summary=f"Task '{task.title}' marked as {task.status.value}",
            actor=current_user,
            details={"task_id": task.id, "old_status": old_status.value, "new_status": task.status.value},
        )

    await db.commit()
    return await get_task_by_id(task_id, db)


@router.post("/cases/{case_id}/investigations", response_model=InvestigationRecordResponse, status_code=status.HTTP_201_CREATED)
async def record_investigation(
    case_id: int,
    inv_in: InvestigationRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles([UserRole.OPERATOR, UserRole.TEAM_LEAD, UserRole.MANAGER, UserRole.ADMIN])
    ),
):
    """Record investigation observations, actions, root cause, and findings."""
    stmt = select(Case).where(Case.id == case_id)
    case = (await db.execute(stmt)).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    record = InvestigationRecord(
        case_id=case_id,
        operator_id=current_user.id,
        observations=inv_in.observations,
        actions_taken=inv_in.actions_taken,
        findings=inv_in.findings,
        root_cause=inv_in.root_cause,
        follow_up_required=inv_in.follow_up_required,
        created_at=datetime.now(timezone.utc),
    )
    db.add(record)
    await db.flush()

    await TimelineService.record_event(
        db=db,
        case_id=case.id,
        event_type="INVESTIGATION_RECORDED",
        summary=f"Investigation record submitted by {current_user.full_name}",
        actor=current_user,
        details={"record_id": record.id, "summary": inv_in.actions_taken[:100]},
    )

    await db.commit()

    stmt_full = (
        select(InvestigationRecord)
        .options(selectinload(InvestigationRecord.operator))
        .where(InvestigationRecord.id == record.id)
    )
    return (await db.execute(stmt_full)).scalar_one()


@router.get("/cases/{case_id}/investigations", response_model=List[InvestigationRecordResponse])
async def list_investigations(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles([UserRole.OPERATOR, UserRole.TEAM_LEAD, UserRole.MANAGER, UserRole.ADMIN])
    ),
):
    """List investigation updates for a case (Restricted to IT Staff)."""
    stmt = (
        select(InvestigationRecord)
        .options(selectinload(InvestigationRecord.operator))
        .where(InvestigationRecord.case_id == case_id)
        .order_by(InvestigationRecord.created_at.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_task_by_id(task_id: int, db: AsyncSession) -> CaseTask:
    stmt = (
        select(CaseTask)
        .options(selectinload(CaseTask.assigned_to), selectinload(CaseTask.created_by))
        .where(CaseTask.id == task_id)
    )
    return (await db.execute(stmt)).scalar_one_or_none()
