from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from app.models.enums import NotificationType


class NotificationBase(BaseModel):
    notification_type: NotificationType
    title: str
    message: str
    case_id: Optional[int] = None


class NotificationCreate(NotificationBase):
    user_id: int


class NotificationRead(BaseModel):
    id: int
    user_id: int
    case_id: Optional[int] = None
    notification_type: NotificationType
    title: str
    message: str
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    items: List[NotificationRead]
    total: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    unread_count: int


class NotificationMarkReadRequest(BaseModel):
    notification_ids: Optional[List[int]] = None
