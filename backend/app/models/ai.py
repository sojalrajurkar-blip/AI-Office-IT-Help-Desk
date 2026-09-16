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
from app.models.enums import CasePriority, CaseSeverity


class AICaseAnalysis(Base):
    __tablename__ = "ai_case_analyses"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)

    suggested_category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    suggested_priority = Column(Enum(CasePriority), nullable=True)
    suggested_severity = Column(Enum(CaseSeverity), nullable=True)
    suggested_team_id = Column(Integer, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)

    missing_information = Column(JSON, default=list, nullable=False)
    recommended_questions = Column(JSON, default=list, nullable=False)
    related_case_ids = Column(JSON, default=list, nullable=False)

    recommended_next_action = Column(Text, nullable=True)
    case_summary = Column(Text, nullable=True)
    risk_insight = Column(Text, nullable=True)
    confidence_score = Column(String(50), nullable=True)

    # Human-in-the-loop audit fields
    is_accepted = Column(Boolean, default=False, nullable=False)
    is_overridden = Column(Boolean, default=False, nullable=False)
    override_reason = Column(Text, nullable=True)
    reviewed_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    case = relationship("Case", back_populates="ai_analyses")
    suggested_category = relationship("Category", foreign_keys=[suggested_category_id])
    suggested_team = relationship("Team", foreign_keys=[suggested_team_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])
