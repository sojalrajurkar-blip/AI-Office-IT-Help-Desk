# Schemas package
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    Token,
    TokenPayload,
    UserResponse,
    UserUpdate,
)
from app.schemas.case import (
    UserSimple,
    TeamSimple,
    CategorySimple,
    CaseCreate,
    CaseUpdate,
    CaseStatusUpdate,
    CaseAssign,
    CaseResponse,
    CaseListResponse,
    TimelineEventResponse,
)

from app.schemas.ai import (
    AICaseAnalysisResponse,
    AICaseAnalysisReviewRequest,
    AIDraftMessageRequest,
    AIDraftMessageResponse,
    AIDuplicateCheckRequest,
    AIDuplicateCheckResponse,
    AIDuplicateMatch,
)

__all__ = [
    "UserRegister",
    "UserLogin",
    "Token",
    "TokenPayload",
    "UserResponse",
    "UserUpdate",
    "UserSimple",
    "TeamSimple",
    "CategorySimple",
    "CaseCreate",
    "CaseUpdate",
    "CaseStatusUpdate",
    "CaseAssign",
    "CaseResponse",
    "CaseListResponse",
    "TimelineEventResponse",
    "AICaseAnalysisResponse",
    "AICaseAnalysisReviewRequest",
    "AIDraftMessageRequest",
    "AIDraftMessageResponse",
    "AIDuplicateCheckRequest",
    "AIDuplicateCheckResponse",
    "AIDuplicateMatch",
]
