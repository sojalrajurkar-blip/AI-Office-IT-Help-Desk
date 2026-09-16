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
from app.models.enums import MessageType


class CaseMessage(Base):
    """Messages exchanged between requester and operator on a case."""
    __tablename__ = "case_messages"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    message_type = Column(Enum(MessageType), default=MessageType.COMMUNICATION, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    case = relationship("Case", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id])
    attachments = relationship("CaseAttachment", back_populates="message")


class InternalNote(Base):
    """Internal notes visible only to staff (Operator, Team Lead, Manager, Admin)."""
    __tablename__ = "internal_notes"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    note_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    case = relationship("Case", back_populates="internal_notes")
    author = relationship("User", foreign_keys=[author_id])
