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

from app.schemas.sla import (
    SLAPolicyResponse,
    SLAPolicyCreate,
    SLAPolicyUpdate,
    CaseSLAStatusResponse,
    CaseRiskRecordResponse,
    CaseRiskEvaluationResponse,
    CaseEscalationCreate,
    CaseEscalationResponse,
    CaseEscalationResolveRequest,
    SLASweepSummaryResponse,
)

from app.schemas.notification import (
    NotificationBase,
    NotificationCreate,
    NotificationRead,
    NotificationListResponse,
    UnreadCountResponse,
    NotificationMarkReadRequest,
)

from app.schemas.resolution import (
    ResolutionProposeRequest,
    ResolutionConfirmRequest,
    ResolutionRejectRequest,
    ResolutionResponse,
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
    "SLAPolicyResponse",
    "SLAPolicyCreate",
    "SLAPolicyUpdate",
    "CaseSLAStatusResponse",
    "CaseRiskRecordResponse",
    "CaseRiskEvaluationResponse",
    "CaseEscalationCreate",
    "CaseEscalationResponse",
    "CaseEscalationResolveRequest",
    "SLASweepSummaryResponse",
    "NotificationBase",
    "NotificationCreate",
    "NotificationRead",
    "NotificationListResponse",
    "UnreadCountResponse",
    "NotificationMarkReadRequest",
    "ResolutionProposeRequest",
    "ResolutionConfirmRequest",
    "ResolutionRejectRequest",
    "ResolutionResponse",
]


