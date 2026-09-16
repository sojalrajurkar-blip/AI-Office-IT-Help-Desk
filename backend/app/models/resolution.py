from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    Enum,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship
from app.db.session import Base
from app.models.enums import ResolutionStatus


class CaseResolution(Base):
    __tablename__ = "case_resolutions"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    operator_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    actions_taken = Column(Text, nullable=False)
    findings = Column(Text, nullable=True)
    remaining_issues = Column(Text, nullable=True)

    status = Column(Enum(ResolutionStatus), default=ResolutionStatus.PROPOSED, nullable=False, index=True)
    requester_feedback = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)

    proposed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    case = relationship("Case", back_populates="resolutions")
    operator = relationship("User", foreign_keys=[operator_id])
