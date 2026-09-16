import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.models.case import Case
from app.models.attachment import CaseAttachment
from app.schemas.communication import AttachmentResponse
from app.services.storage_service import StorageService
from app.services.timeline_service import TimelineService

router = APIRouter(tags=["Evidence & Attachments"])


@router.post("/cases/{case_id}/attachments", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    case_id: int,
    file: UploadFile = File(...),
    message_id: Optional[int] = Form(None),
    is_resolution_evidence: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload evidence/attachment connected to a case."""
    stmt = select(Case).where(Case.id == case_id)
    case = (await db.execute(stmt)).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    # Requesters can only upload to their own cases
    if current_user.role == UserRole.REQUESTER and case.requester_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied to this case.")

    # Save file to disk
    file_name, file_path, file_size, content_type = await StorageService.save_file(file)

    attachment = CaseAttachment(
        case_id=case_id,
        message_id=message_id,
        uploaded_by_id=current_user.id,
        file_name=file_name,
        file_path=file_path,
        file_size_bytes=file_size,
        content_type=content_type,
        is_resolution_evidence=is_resolution_evidence,
    )
    db.add(attachment)
    await db.flush()

    summary = f"Evidence '{file_name}' uploaded by {current_user.full_name}"
    if is_resolution_evidence:
        summary = f"Resolution evidence '{file_name}' uploaded by {current_user.full_name}"

    await TimelineService.record_event(
        db=db,
        case_id=case.id,
        event_type="ATTACHMENT_UPLOADED",
        summary=summary,
        actor=current_user,
        details={"attachment_id": attachment.id, "file_name": file_name, "size_bytes": file_size},
    )

    await db.commit()

    stmt_full = (
        select(CaseAttachment)
        .options(selectinload(CaseAttachment.uploaded_by))
        .where(CaseAttachment.id == attachment.id)
    )
    return (await db.execute(stmt_full)).scalar_one()


@router.get("/cases/{case_id}/attachments", response_model=List[AttachmentResponse])
async def list_attachments(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all attachments for a case."""
    stmt = select(Case).where(Case.id == case_id)
    case = (await db.execute(stmt)).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    if current_user.role == UserRole.REQUESTER and case.requester_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied to this case.")

    stmt_att = (
        select(CaseAttachment)
        .options(selectinload(CaseAttachment.uploaded_by))
        .where(CaseAttachment.case_id == case_id)
        .order_by(CaseAttachment.created_at.asc())
    )
    return list((await db.execute(stmt_att)).scalars().all())


@router.get("/attachments/{attachment_id}/download")
async def download_attachment(
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Securely download an attachment after verifying user authorization on the case."""
    stmt = select(CaseAttachment).where(CaseAttachment.id == attachment_id)
    att = (await db.execute(stmt)).scalar_one_or_none()
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found.")

    # Check parent case authorization
    case_stmt = select(Case).where(Case.id == att.case_id)
    case = (await db.execute(case_stmt)).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Parent case not found.")

    if current_user.role == UserRole.REQUESTER and case.requester_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied to this file.")

    if not os.path.exists(att.file_path):
        raise HTTPException(status_code=404, detail="File content not found on server disk.")

    return FileResponse(
        path=att.file_path,
        filename=att.file_name,
        media_type=att.content_type,
    )
