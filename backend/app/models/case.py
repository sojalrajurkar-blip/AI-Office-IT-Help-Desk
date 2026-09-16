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
)
from sqlalchemy.orm import relationship
from app.db.session import Base
from app.models.enums import CaseStatus, CasePriority, CaseSeverity


class CaseSequence(Base):
    """Stores sequential numbers to generate unique IDs like IT-10001 atomically."""
    __tablename__ = "case_sequences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    case_number = Column(String(50), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)
    office_location = Column(String(100), nullable=True, index=True)

    status = Column(Enum(CaseStatus), default=CaseStatus.REPORTED, nullable=False, index=True)
    priority = Column(Enum(CasePriority), default=CasePriority.MEDIUM, nullable=False, index=True)
    severity = Column(Enum(CaseSeverity), default=CaseSeverity.MODERATE, nullable=False, index=True)

    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    requester_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_team_id = Column(Integer, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_operator_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    response_deadline = Column(DateTime(timezone=True), nullable=True)
    resolution_deadline = Column(DateTime(timezone=True), nullable=True)
    is_sla_breached = Column(Boolean, default=False, nullable=False, index=True)
    sla_breached_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    requester = relationship("User", foreign_keys=[requester_id], backref="created_cases")
    assigned_operator = relationship("User", foreign_keys=[assigned_operator_id], backref="handled_cases")
    assigned_team = relationship("Team", back_populates="assigned_cases")
    category = relationship("Category", back_populates="cases")

    messages = relationship("CaseMessage", back_populates="case", cascade="all, delete-orphan")
    internal_notes = relationship("InternalNote", back_populates="case", cascade="all, delete-orphan")
    attachments = relationship("CaseAttachment", back_populates="case", cascade="all, delete-orphan")
    tasks = relationship("CaseTask", back_populates="case", cascade="all, delete-orphan")
    investigation_records = relationship("InvestigationRecord", back_populates="case", cascade="all, delete-orphan")
    ai_analyses = relationship("AICaseAnalysis", back_populates="case", cascade="all, delete-orphan")
    risk_records = relationship("CaseRiskRecord", back_populates="case", cascade="all, delete-orphan")
    escalations = relationship("CaseEscalation", back_populates="case", cascade="all, delete-orphan")
    resolutions = relationship("CaseResolution", back_populates="case", cascade="all, delete-orphan")
    timeline_events = relationship("TimelineEvent", back_populates="case", cascade="all, delete-orphan")
