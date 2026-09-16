from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.models.enums import CaseStatus, CasePriority, CaseSeverity, UserRole


class UserSimple(BaseModel):
    id: int
    full_name: str
    email: str
    role: UserRole
    office_location: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class TeamSimple(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class CategorySimple(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    default_priority: CasePriority
    model_config = ConfigDict(from_attributes=True)


class CaseCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=5)
    office_location: Optional[str] = None
    category_id: Optional[int] = None
    priority: Optional[CasePriority] = None
    severity: Optional[CaseSeverity] = CaseSeverity.MODERATE


class CaseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = Field(None, min_length=5)
    office_location: Optional[str] = None
    category_id: Optional[int] = None
    priority: Optional[CasePriority] = None
    severity: Optional[CaseSeverity] = None


class CaseStatusUpdate(BaseModel):
    new_status: CaseStatus
    notes: Optional[str] = None


class CaseAssign(BaseModel):
    assigned_team_id: Optional[int] = None
    assigned_operator_id: Optional[int] = None
    notes: Optional[str] = None


class CaseResponse(BaseModel):
    id: int
    case_number: str
    title: str
    description: str
    office_location: Optional[str] = None
    status: CaseStatus
    priority: CasePriority
    severity: CaseSeverity
    category_id: Optional[int] = None
    requester_id: int
    assigned_team_id: Optional[int] = None
    assigned_operator_id: Optional[int] = None
    response_deadline: Optional[datetime] = None
    resolution_deadline: Optional[datetime] = None
    is_sla_breached: bool
    sla_breached_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None

    requester: Optional[UserSimple] = None
    assigned_operator: Optional[UserSimple] = None
    assigned_team: Optional[TeamSimple] = None
    category: Optional[CategorySimple] = None

    model_config = ConfigDict(from_attributes=True)


class CaseListResponse(BaseModel):
    items: List[CaseResponse]
    total: int
    page: int
    size: int


class TimelineEventResponse(BaseModel):
    id: int
    case_id: int
    event_type: str
    summary: str
    details: Dict[str, Any]
    created_at: datetime
    actor: Optional[UserSimple] = None

    model_config = ConfigDict(from_attributes=True)
