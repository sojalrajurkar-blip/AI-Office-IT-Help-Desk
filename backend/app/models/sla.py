from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship
from app.db.session import Base
from app.models.enums import CasePriority, RiskLevel, EscalationStatus, UserRole


class SLAPolicy(Base):
    __tablename__ = "sla_policies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    priority = Column(Enum(CasePriority), unique=True, nullable=False, index=True)
    response_time_hours = Column(Integer, nullable=False)
    resolution_time_hours = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class CaseRiskRecord(Base):
    __tablename__ = "case_risk_records"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    risk_level = Column(Enum(RiskLevel), default=RiskLevel.LOW, nullable=False, index=True)
    reasons = Column(JSON, default=list, nullable=False)
    is_resolved = Column(Boolean, default=False, nullable=False)
    detected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    case = relationship("Case", back_populates="risk_records")


class CaseEscalation(Base):
    __tablename__ = "case_escalations"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    escalated_by_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_role = Column(Enum(UserRole), default=UserRole.TEAM_LEAD, nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(Enum(EscalationStatus), default=EscalationStatus.PENDING, nullable=False, index=True)
    resolution_notes = Column(Text, nullable=True)
    resolved_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    case = relationship("Case", back_populates="escalations")
    escalated_by = relationship("User", foreign_keys=[escalated_by_id])
    resolved_by = relationship("User", foreign_keys=[resolved_by_id])
