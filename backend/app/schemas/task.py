from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from app.models.enums import TaskStatus
from app.schemas.case import UserSimple


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    assigned_to_id: Optional[int] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    assigned_to_id: Optional[int] = None
    findings: Optional[str] = None


class TaskResponse(BaseModel):
    id: int
    case_id: int
    title: str
    description: Optional[str] = None
    status: TaskStatus
    assigned_to_id: Optional[int] = None
    created_by_id: int
    findings: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    assigned_to: Optional[UserSimple] = None
    created_by: Optional[UserSimple] = None

    model_config = ConfigDict(from_attributes=True)


class InvestigationRecordCreate(BaseModel):
    observations: str = Field(..., min_length=3)
    actions_taken: str = Field(..., min_length=3)
    findings: Optional[str] = None
    root_cause: Optional[str] = None
    follow_up_required: Optional[str] = None


class InvestigationRecordResponse(BaseModel):
    id: int
    case_id: int
    operator_id: int
    observations: str
    actions_taken: str
    findings: Optional[str] = None
    root_cause: Optional[str] = None
    follow_up_required: Optional[str] = None
    created_at: datetime

    operator: Optional[UserSimple] = None

    model_config = ConfigDict(from_attributes=True)
