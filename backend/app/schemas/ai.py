from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import CasePriority, CaseSeverity


class AICaseAnalysisResponse(BaseModel):
    id: int
    case_id: int
    suggested_category_id: Optional[int] = None
    suggested_category_name: Optional[str] = None
    suggested_priority: Optional[CasePriority] = None
    suggested_severity: Optional[CaseSeverity] = None
    suggested_team_id: Optional[int] = None
    suggested_team_name: Optional[str] = None

    missing_information: List[str] = Field(default_factory=list)
    recommended_questions: List[str] = Field(default_factory=list)
    related_case_ids: List[int] = Field(default_factory=list)

    recommended_next_action: Optional[str] = None
    case_summary: Optional[str] = None
    risk_insight: Optional[str] = None
    confidence_score: Optional[str] = None

    is_accepted: bool = False
    is_overridden: bool = False
    override_reason: Optional[str] = None
    reviewed_by_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AICaseAnalysisReviewRequest(BaseModel):
    is_accepted: bool = False
    is_overridden: bool = False
    override_reason: Optional[str] = None
    apply_changes: bool = True


class AIDraftMessageRequest(BaseModel):
    draft_type: str = "INFO_REQUEST"  # INFO_REQUEST, STATUS_UPDATE, WORKAROUND, RESOLUTION_EXPLANATION
    instructions: Optional[str] = None


class AIDraftMessageResponse(BaseModel):
    draft_type: str
    subject: Optional[str] = None
    drafted_message: str
    key_points: List[str] = Field(default_factory=list)


class AIDuplicateCheckRequest(BaseModel):
    title: str
    description: str
    category_id: Optional[int] = None


class AIDuplicateMatch(BaseModel):
    case_id: int
    case_number: str
    title: str
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    reason: str


class AIDuplicateCheckResponse(BaseModel):
    potential_duplicates: List[AIDuplicateMatch] = Field(default_factory=list)
    count: int = 0
