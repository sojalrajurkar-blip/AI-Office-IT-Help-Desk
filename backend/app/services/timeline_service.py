from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.timeline_audit import TimelineEvent
from app.models.user import User


class TimelineService:
    @staticmethod
    async def record_event(
        db: AsyncSession,
        case_id: int,
        event_type: str,
        summary: str,
        actor: Optional[User] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> TimelineEvent:
        event = TimelineEvent(
            case_id=case_id,
            actor_id=actor.id if actor else None,
            event_type=event_type,
            summary=summary,
            details=details or {},
        )
        db.add(event)
        return event
