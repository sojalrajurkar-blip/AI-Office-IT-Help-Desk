from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from app.models.enums import MessageType
from app.schemas.case import UserSimple


class AttachmentResponse(BaseModel):
    id: int
    case_id: int
    message_id: Optional[int] = None
    uploaded_by_id: int
    file_name: str
    file_size_bytes: int
    content_type: str
    is_resolution_evidence: bool
    created_at: datetime
    uploaded_by: Optional[UserSimple] = None

    model_config = ConfigDict(from_attributes=True)


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1)
    message_type: Optional[MessageType] = MessageType.COMMUNICATION


class MessageResponse(BaseModel):
    id: int
    case_id: int
    sender_id: int
    message_type: MessageType
    content: str
    created_at: datetime
    sender: Optional[UserSimple] = None
    attachments: List[AttachmentResponse] = []

    model_config = ConfigDict(from_attributes=True)


class InternalNoteCreate(BaseModel):
    note_text: str = Field(..., min_length=1)


class InternalNoteResponse(BaseModel):
    id: int
    case_id: int
    author_id: int
    note_text: str
    created_at: datetime
    author: Optional[UserSimple] = None

    model_config = ConfigDict(from_attributes=True)
