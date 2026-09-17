from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.notification import (
    NotificationRead,
    NotificationListResponse,
    UnreadCountResponse,
    NotificationMarkReadRequest,
)
from app.services.notification_service import (
    get_user_notifications,
    get_unread_count,
    mark_notification_as_read,
    mark_all_notifications_as_read,
)

router = APIRouter(prefix="/notifications", tags=["In-App Notifications"])


@router.get("", response_model=NotificationListResponse)
async def list_my_notifications(
    unread_only: bool = Query(False, description="Filter only unread notifications"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve in-app notifications for the currently authenticated user.
    """
    items, total, unread = await get_user_notifications(
        db=db,
        user_id=current_user.id,
        unread_only=unread_only,
        skip=skip,
        limit=limit,
    )
    return NotificationListResponse(
        items=items,
        total=total,
        unread_count=unread,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_my_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the quick unread notification count for badge rendering.
    """
    count = await get_unread_count(db=db, user_id=current_user.id)
    return UnreadCountResponse(unread_count=count)


@router.patch("/{notification_id}/read", response_model=NotificationRead)
async def mark_single_notification_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mark a specific notification as read.
    """
    notif = await mark_notification_as_read(
        db=db,
        notification_id=notification_id,
        user_id=current_user.id,
    )
    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
    await db.commit()
    return notif


@router.post("/mark-all-read")
async def mark_all_notifications_read(
    request: Optional[NotificationMarkReadRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mark all (or a specific set of) unread notifications as read.
    """
    ids = request.notification_ids if request else None
    count = await mark_all_notifications_as_read(
        db=db,
        user_id=current_user.id,
        notification_ids=ids,
    )
    await db.commit()
    return {"updated_count": count}

