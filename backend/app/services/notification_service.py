import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional, List, Sequence, Tuple
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import InAppNotification
from app.models.user import User
from app.models.enums import NotificationType, UserRole

logger = logging.getLogger(__name__)


# ============================================================================
# Push Notification Abstraction (Extensible for FCM, WebPush, APNs)
# ============================================================================

class BasePushNotifier(ABC):
    """
    Abstract push notification provider interface.
    Allows swappable delivery channels without modifying business logic.
    Strictly NO email / SMTP infrastructure.
    """

    @abstractmethod
    async def send_push(
        self,
        user_id: int,
        title: str,
        message: str,
        case_id: Optional[int] = None,
        notification_type: Optional[NotificationType] = None,
        payload: Optional[dict] = None,
    ) -> bool:
        pass


class LogPushNotifier(BasePushNotifier):
    """
    Standard push notifier simulating push dispatch by recording
    structured telemetry logs and preparing payload headers.
    """

    def __init__(self):
        self.dispatched_pushes: List[dict] = []

    async def send_push(
        self,
        user_id: int,
        title: str,
        message: str,
        case_id: Optional[int] = None,
        notification_type: Optional[NotificationType] = None,
        payload: Optional[dict] = None,
    ) -> bool:
        push_entry = {
            "user_id": user_id,
            "title": title,
            "message": message,
            "case_id": case_id,
            "notification_type": notification_type.value if notification_type else None,
            "payload": payload or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.dispatched_pushes.append(push_entry)
        logger.info(f"[PUSH NOTIFICATION DISPATCHED] -> User #{user_id} | Type: {notification_type} | Title: '{title}' | Case: #{case_id}")
        return True


# Global default push provider instance
default_push_notifier: BasePushNotifier = LogPushNotifier()


def get_push_notifier() -> BasePushNotifier:
    return default_push_notifier


def set_push_notifier(notifier: BasePushNotifier) -> None:
    global default_push_notifier
    default_push_notifier = notifier


# ============================================================================
# In-App Notification Service Operations
# ============================================================================

async def create_notification(
    db: AsyncSession,
    user_id: int,
    notification_type: NotificationType,
    title: str,
    message: str,
    case_id: Optional[int] = None,
    push_notifier: Optional[BasePushNotifier] = None,
) -> InAppNotification:
    """
    Creates an in-app notification record and dispatches a push notification.
    """
    notification = InAppNotification(
        user_id=user_id,
        case_id=case_id,
        notification_type=notification_type,
        title=title,
        message=message,
        is_read=False,
    )
    db.add(notification)
    await db.flush()
    await db.refresh(notification)

    notifier = push_notifier or default_push_notifier
    try:
        await notifier.send_push(
            user_id=user_id,
            title=title,
            message=message,
            case_id=case_id,
            notification_type=notification_type,
        )
    except Exception as e:
        logger.warning(f"Push notification dispatch failed for user {user_id}: {e}")

    return notification


async def create_team_notifications(
    db: AsyncSession,
    team_id: int,
    notification_type: NotificationType,
    title: str,
    message: str,
    case_id: Optional[int] = None,
    exclude_user_id: Optional[int] = None,
) -> List[InAppNotification]:
    """
    Creates notifications for all active members and team lead of a given team.
    """
    stmt = select(User).where(
        User.is_active == True,
        User.team_id == team_id,
    )
    if exclude_user_id:
        stmt = stmt.where(User.id != exclude_user_id)

    result = await db.execute(stmt)
    team_members = result.scalars().all()

    notifications: List[InAppNotification] = []
    for member in team_members:
        notif = await create_notification(
            db=db,
            user_id=member.id,
            notification_type=notification_type,
            title=title,
            message=message,
            case_id=case_id,
        )
        notifications.append(notif)

    return notifications


async def create_role_notifications(
    db: AsyncSession,
    roles: Sequence[UserRole],
    notification_type: NotificationType,
    title: str,
    message: str,
    case_id: Optional[int] = None,
    exclude_user_id: Optional[int] = None,
) -> List[InAppNotification]:
    """
    Creates notifications for all active users holding specified roles (e.g. TEAM_LEAD, MANAGER).
    """
    stmt = select(User).where(
        User.is_active == True,
        User.role.in_(roles),
    )
    if exclude_user_id:
        stmt = stmt.where(User.id != exclude_user_id)

    result = await db.execute(stmt)
    target_users = result.scalars().all()

    notifications: List[InAppNotification] = []
    for user in target_users:
        notif = await create_notification(
            db=db,
            user_id=user.id,
            notification_type=notification_type,
            title=title,
            message=message,
            case_id=case_id,
        )
        notifications.append(notif)

    return notifications


async def get_user_notifications(
    db: AsyncSession,
    user_id: int,
    unread_only: bool = False,
    skip: int = 0,
    limit: int = 50,
) -> Tuple[List[InAppNotification], int, int]:
    """
    Retrieves paginated notifications for a user, total count, and total unread count.
    """
    # Base filter
    base_filter = [InAppNotification.user_id == user_id]

    # Total count for user
    total_stmt = select(func.count(InAppNotification.id)).where(*base_filter)
    total_res = await db.execute(total_stmt)
    total_count = total_res.scalar_one() or 0

    # Unread count for user
    unread_stmt = select(func.count(InAppNotification.id)).where(
        *base_filter,
        InAppNotification.is_read == False,
    )
    unread_res = await db.execute(unread_stmt)
    unread_count = unread_res.scalar_one() or 0

    # Items query
    query = select(InAppNotification).where(*base_filter)
    if unread_only:
        query = query.where(InAppNotification.is_read == False)

    query = query.order_by(InAppNotification.created_at.desc(), InAppNotification.id.desc())
    query = query.offset(skip).limit(limit)

    items_res = await db.execute(query)
    items = list(items_res.scalars().all())

    return items, total_count, unread_count


async def get_unread_count(
    db: AsyncSession,
    user_id: int,
) -> int:
    """
    Returns unread count for badge indicators.
    """
    stmt = select(func.count(InAppNotification.id)).where(
        InAppNotification.user_id == user_id,
        InAppNotification.is_read == False,
    )
    res = await db.execute(stmt)
    return res.scalar_one() or 0


async def mark_notification_as_read(
    db: AsyncSession,
    notification_id: int,
    user_id: int,
) -> Optional[InAppNotification]:
    """
    Marks a single notification as read if it belongs to user_id.
    """
    stmt = select(InAppNotification).where(
        InAppNotification.id == notification_id,
        InAppNotification.user_id == user_id,
    )
    res = await db.execute(stmt)
    notification = res.scalar_one_or_none()

    if not notification:
        return None

    if not notification.is_read:
        notification.is_read = True
        await db.flush()
        await db.refresh(notification)

    return notification


async def mark_all_notifications_as_read(
    db: AsyncSession,
    user_id: int,
    notification_ids: Optional[List[int]] = None,
) -> int:
    """
    Marks all (or specific list of) unread notifications as read for a user.
    Returns the number of updated records.
    """
    stmt = (
        update(InAppNotification)
        .where(
            InAppNotification.user_id == user_id,
            InAppNotification.is_read == False,
        )
        .values(is_read=True)
    )
    if notification_ids:
        stmt = stmt.where(InAppNotification.id.in_(notification_ids))

    res = await db.execute(stmt)
    await db.flush()
    return res.rowcount or 0
