from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import CasePriority, CaseStatus, EscalationStatus, RiskLevel, UserRole


class SLAPolicyResponse(BaseModel):
    id: int
    name: str
    priority: CasePriority
    response_time_hours: int
    resolution_time_hours: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SLAPolicyCreate(BaseModel):
    name: str
    priority: CasePriority
    response_time_hours: int = Field(..., ge=1)
    resolution_time_hours: int = Field(..., ge=1)


class SLAPolicyUpdate(BaseModel):
    response_time_hours: Optional[int] = Field(None, ge=1)
    resolution_time_hours: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None


class CaseSLAStatusResponse(BaseModel):
    case_id: int
    case_number: str
    priority: CasePriority
    response_deadline: Optional[datetime] = None
    resolution_deadline: Optional[datetime] = None
    response_time_remaining_minutes: Optional[float] = None
    resolution_time_remaining_minutes: Optional[float] = None
    percentage_time_elapsed: float = 0.0
    is_response_breached: bool = False
    is_resolution_breached: bool = False
    is_sla_breached: bool = False
    sla_breached_at: Optional[datetime] = None
    is_at_risk: bool = False
    warning_message: Optional[str] = None


class CaseRiskRecordResponse(BaseModel):
    id: int
    case_id: int
    risk_level: RiskLevel
    reasons: List[str] = Field(default_factory=list)
    is_resolved: bool
    detected_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CaseRiskEvaluationResponse(BaseModel):
    case_id: int
    case_number: str
    risk_level: RiskLevel
    reasons: List[str] = Field(default_factory=list)
    is_at_risk: bool = False
    summary: str


class CaseEscalationCreate(BaseModel):
    reason: str = Field(..., min_length=5, max_length=1000)
    target_role: UserRole = UserRole.TEAM_LEAD


class CaseEscalationResponse(BaseModel):
    id: int
    case_id: int
    escalated_by_id: int
    escalated_by_name: Optional[str] = None
    target_role: UserRole
    reason: str
    status: EscalationStatus
    resolution_notes: Optional[str] = None
    resolved_by_id: Optional[int] = None
    resolved_by_name: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CaseEscalationResolveRequest(BaseModel):
    resolution_notes: str = Field(..., min_length=5, max_length=2000)
    next_status: Optional[CaseStatus] = None


class SLASweepSummaryResponse(BaseModel):
    total_scanned: int = 0
    breaches_detected: int = 0
    at_risk_detected: int = 0
    updated_cases: List[str] = Field(default_factory=list)
