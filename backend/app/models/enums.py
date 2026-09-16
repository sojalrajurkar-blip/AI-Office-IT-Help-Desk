import enum


class UserRole(str, enum.Enum):
    REQUESTER = "REQUESTER"
    OPERATOR = "OPERATOR"
    TEAM_LEAD = "TEAM_LEAD"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"


class CaseStatus(str, enum.Enum):
    # Primary lifecycle
    REPORTED = "REPORTED"
    UNDERSTOOD = "UNDERSTOOD"
    ASSIGNED = "ASSIGNED"
    INVESTIGATING = "INVESTIGATING"
    ACTION_TAKEN = "ACTION_TAKEN"
    RESOLUTION_PROPOSED = "RESOLUTION_PROPOSED"
    CONFIRMED = "CONFIRMED"
    CLOSED = "CLOSED"

    # Alternate / Temporary states
    WAITING_FOR_INFO = "WAITING_FOR_INFO"
    ESCALATED = "ESCALATED"
    DUPLICATE = "DUPLICATE"
    REOPENED = "REOPENED"
    CANCELLED = "CANCELLED"


class CasePriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CaseSeverity(str, enum.Enum):
    MINOR = "MINOR"
    MODERATE = "MODERATE"
    MAJOR = "MAJOR"
    CRITICAL = "CRITICAL"


class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"


class MessageType(str, enum.Enum):
    COMMUNICATION = "COMMUNICATION"
    INFO_REQUEST = "INFO_REQUEST"
    INFO_RESPONSE = "INFO_RESPONSE"


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EscalationStatus(str, enum.Enum):
    PENDING = "PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


class ResolutionStatus(str, enum.Enum):
    PROPOSED = "PROPOSED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class NotificationType(str, enum.Enum):
    NEW_CASE = "NEW_CASE"
    ASSIGNMENT = "ASSIGNMENT"
    REQUESTER_RESPONSE = "REQUESTER_RESPONSE"
    NEW_TASK = "NEW_TASK"
    SLA_WARNING = "SLA_WARNING"
    ESCALATION = "ESCALATION"
    RESOLUTION = "RESOLUTION"
    REOPENED = "REOPENED"
