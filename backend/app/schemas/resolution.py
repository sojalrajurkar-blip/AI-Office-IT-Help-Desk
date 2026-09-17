from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from app.models.enums import ResolutionStatus
from app.schemas.case import UserSimple


class ResolutionProposeRequest(BaseModel):
    actions_taken: str = Field(..., min_length=5, description="Detailed actions and steps taken to resolve the issue")
    findings: Optional[str] = Field(None, description="Diagnostic findings and root cause analysis")
    remaining_issues: Optional[str] = Field(None, description="Any residual notes or follow-up recommendations")


class ResolutionConfirmRequest(BaseModel):
    feedback: Optional[str] = Field(None, description="Optional feedback or comments from the requester")


class ResolutionRejectRequest(BaseModel):
    rejection_reason: str = Field(..., min_length=5, description="Reason why the proposed resolution was rejected")


class ResolutionResponse(BaseModel):
    id: int
    case_id: int
    operator_id: int
    actions_taken: str
    findings: Optional[str] = None
    remaining_issues: Optional[str] = None
    status: ResolutionStatus
    requester_feedback: Optional[str] = None
    rejection_reason: Optional[str] = None
    proposed_at: datetime
    confirmed_at: Optional[datetime] = None

    operator: Optional[UserSimple] = None

    model_config = ConfigDict(from_attributes=True)
