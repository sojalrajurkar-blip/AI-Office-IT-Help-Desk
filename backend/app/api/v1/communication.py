from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.enums import UserRole, CaseStatus, MessageType, NotificationType
from app.models.user import User
from app.models.case import Case
from app.models.communication import CaseMessage, InternalNote
from app.schemas.communication import (
    MessageCreate,
    MessageResponse,
    InternalNoteCreate,
    InternalNoteResponse,
)
from app.services.timeline_service import TimelineService
from app.services.notification_service import (
    create_notification,
    create_team_notifications,
)

router = APIRouter(prefix="/cases", tags=["Case Communication & Notes"])


@router.post("/{case_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    case_id: int,
    msg_in: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a communication message on a case (Requester ↔ Operator)."""
    case = await get_case_or_404(case_id, db)
    verify_case_access(case, current_user)

    msg_type = msg_in.message_type or MessageType.COMMUNICATION

    # Create message
    message = CaseMessage(
        case_id=case_id,
        sender_id=current_user.id,
        message_type=msg_type,
        content=msg_in.content,
        created_at=datetime.now(timezone.utc),
    )
    db.add(message)
    await db.flush()

    # Automatic State Transition & Notification Handling:
    # 1. Operator requests info -> case transitions to WAITING_FOR_INFO
    if msg_type == MessageType.INFO_REQUEST and current_user.role != UserRole.REQUESTER:
        case.status = CaseStatus.WAITING_FOR_INFO
        case.updated_at = datetime.now(timezone.utc)
        await TimelineService.record_event(
            db=db,
            case_id=case.id,
            event_type="INFO_REQUESTED",
            summary=f"Operator {current_user.full_name} requested additional information",
            actor=current_user,
            details={"message_id": message.id, "preview": msg_in.content[:100]},
        )
        if case.requester_id and case.requester_id != current_user.id:
            await create_notification(
                db=db,
                user_id=case.requester_id,
                notification_type=NotificationType.REQUESTER_RESPONSE,
                title=f"Information Requested: {case.case_number}",
                message=f"IT Support requested more details on case {case.case_number}.",
                case_id=case.id,
            )

    # 2. Requester responds -> if case was WAITING_FOR_INFO, resume to INVESTIGATING / UNDERSTOOD
    elif msg_type == MessageType.INFO_RESPONSE and current_user.role == UserRole.REQUESTER:
        if case.status == CaseStatus.WAITING_FOR_INFO:
            case.status = CaseStatus.INVESTIGATING if case.assigned_operator_id else CaseStatus.UNDERSTOOD
            case.updated_at = datetime.now(timezone.utc)
        await TimelineService.record_event(
            db=db,
            case_id=case.id,
            event_type="INFO_PROVIDED",
            summary=f"Requester {current_user.full_name} provided requested information",
            actor=current_user,
            details={"message_id": message.id, "preview": msg_in.content[:100]},
        )
        if case.assigned_operator_id:
            await create_notification(
                db=db,
                user_id=case.assigned_operator_id,
                notification_type=NotificationType.REQUESTER_RESPONSE,
                title=f"Requester Response: {case.case_number}",
                message=f"Requester {current_user.full_name} provided requested information for case {case.case_number}.",
                case_id=case.id,
            )
        elif case.assigned_team_id:
            await create_team_notifications(
                db=db,
                team_id=case.assigned_team_id,
                notification_type=NotificationType.REQUESTER_RESPONSE,
                title=f"Requester Response: {case.case_number}",
                message=f"Requester {current_user.full_name} provided requested information for case {case.case_number}.",
                case_id=case.id,
            )
    else:
        await TimelineService.record_event(
            db=db,
            case_id=case.id,
            event_type="MESSAGE_SENT",
            summary=f"Message from {current_user.full_name}",
            actor=current_user,
            details={"message_id": message.id},
        )
        if current_user.role == UserRole.REQUESTER:
            if case.assigned_operator_id:
                await create_notification(
                    db=db,
                    user_id=case.assigned_operator_id,
                    notification_type=NotificationType.REQUESTER_RESPONSE,
                    title=f"New Message: {case.case_number}",
                    message=f"Requester {current_user.full_name} sent a message on case {case.case_number}.",
                    case_id=case.id,
                )
        else:
            if case.requester_id and case.requester_id != current_user.id:
                await create_notification(
                    db=db,
                    user_id=case.requester_id,
                    notification_type=NotificationType.REQUESTER_RESPONSE,
                    title=f"New Message: {case.case_number}",
                    message=f"{current_user.full_name} sent a message regarding case {case.case_number}.",
                    case_id=case.id,
                )

    await db.commit()


    # Load message with sender and attachments
    stmt = (
        select(CaseMessage)
        .options(selectinload(CaseMessage.sender), selectinload(CaseMessage.attachments))
        .where(CaseMessage.id == message.id)
    )
    return (await db.execute(stmt)).scalar_one()


@router.get("/{case_id}/messages", response_model=List[MessageResponse])
async def list_messages(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve all communication messages on a case."""
    case = await get_case_or_404(case_id, db)
    verify_case_access(case, current_user)

    stmt = (
        select(CaseMessage)
        .options(selectinload(CaseMessage.sender), selectinload(CaseMessage.attachments))
        .where(CaseMessage.case_id == case_id)
        .order_by(CaseMessage.created_at.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


# ==============================================================================
# Internal Notes (Strictly for Staff: Operator, Team Lead, Manager, Admin)
# ==============================================================================

@router.post("/{case_id}/internal-notes", response_model=InternalNoteResponse, status_code=status.HTTP_201_CREATED)
async def add_internal_note(
    case_id: int,
    note_in: InternalNoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles([UserRole.OPERATOR, UserRole.TEAM_LEAD, UserRole.MANAGER, UserRole.ADMIN])
    ),
):
    """Add an internal note visible only to IT staff."""
    case = await get_case_or_404(case_id, db)

    note = InternalNote(
        case_id=case_id,
        author_id=current_user.id,
        note_text=note_in.note_text,
        created_at=datetime.now(timezone.utc),
    )
    db.add(note)
    await db.flush()

    await TimelineService.record_event(
        db=db,
        case_id=case.id,
        event_type="INTERNAL_NOTE_ADDED",
        summary=f"Internal note added by {current_user.full_name}",
        actor=current_user,
        details={"note_id": note.id},
    )

    await db.commit()

    stmt = select(InternalNote).options(selectinload(InternalNote.author)).where(InternalNote.id == note.id)
    return (await db.execute(stmt)).scalar_one()


@router.get("/{case_id}/internal-notes", response_model=List[InternalNoteResponse])
async def list_internal_notes(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles([UserRole.OPERATOR, UserRole.TEAM_LEAD, UserRole.MANAGER, UserRole.ADMIN])
    ),
):
    """List internal notes for a case (Restricted to IT staff)."""
    await get_case_or_404(case_id, db)

    stmt = (
        select(InternalNote)
        .options(selectinload(InternalNote.author))
        .where(InternalNote.case_id == case_id)
        .order_by(InternalNote.created_at.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_case_or_404(case_id: int, db: AsyncSession) -> Case:
    stmt = select(Case).where(Case.id == case_id)
    case = (await db.execute(stmt)).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")
    return case


def verify_case_access(case: Case, user: User) -> None:
    if user.role == UserRole.REQUESTER and case.requester_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied to this case.")
