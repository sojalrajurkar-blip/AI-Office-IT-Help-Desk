from typing import Set, Dict
from fastapi import HTTPException, status
from app.models.enums import CaseStatus, UserRole
from app.models.user import User
from app.models.case import Case


class CaseLifecycleService:
    """Controls and validates valid case state transitions in accordance with AGENTS.md and SRS."""

    VALID_TRANSITIONS: Dict[CaseStatus, Set[CaseStatus]] = {
        CaseStatus.REPORTED: {
            CaseStatus.UNDERSTOOD,
            CaseStatus.ASSIGNED,
            CaseStatus.WAITING_FOR_INFO,
            CaseStatus.DUPLICATE,
            CaseStatus.CANCELLED,
        },
        CaseStatus.UNDERSTOOD: {
            CaseStatus.ASSIGNED,
            CaseStatus.INVESTIGATING,
            CaseStatus.WAITING_FOR_INFO,
            CaseStatus.DUPLICATE,
            CaseStatus.CANCELLED,
        },
        CaseStatus.ASSIGNED: {
            CaseStatus.INVESTIGATING,
            CaseStatus.WAITING_FOR_INFO,
            CaseStatus.ESCALATED,
            CaseStatus.CANCELLED,
        },
        CaseStatus.INVESTIGATING: {
            CaseStatus.ACTION_TAKEN,
            CaseStatus.WAITING_FOR_INFO,
            CaseStatus.ESCALATED,
            CaseStatus.CANCELLED,
        },
        CaseStatus.ACTION_TAKEN: {
            CaseStatus.RESOLUTION_PROPOSED,
            CaseStatus.INVESTIGATING,
            CaseStatus.WAITING_FOR_INFO,
            CaseStatus.ESCALATED,
        },
        CaseStatus.RESOLUTION_PROPOSED: {
            CaseStatus.CONFIRMED,
            CaseStatus.REOPENED,
            CaseStatus.INVESTIGATING,
        },
        CaseStatus.CONFIRMED: {
            CaseStatus.CLOSED,
        },
        CaseStatus.CLOSED: set(),
        CaseStatus.WAITING_FOR_INFO: {
            CaseStatus.REPORTED,
            CaseStatus.UNDERSTOOD,
            CaseStatus.ASSIGNED,
            CaseStatus.INVESTIGATING,
            CaseStatus.CANCELLED,
        },
        CaseStatus.ESCALATED: {
            CaseStatus.INVESTIGATING,
            CaseStatus.ASSIGNED,
            CaseStatus.ACTION_TAKEN,
        },
        CaseStatus.REOPENED: {
            CaseStatus.INVESTIGATING,
            CaseStatus.ASSIGNED,
            CaseStatus.WAITING_FOR_INFO,
        },
        CaseStatus.DUPLICATE: set(),
        CaseStatus.CANCELLED: set(),
    }

    @classmethod
    def validate_transition(cls, case: Case, new_status: CaseStatus, actor: User) -> None:
        current_status = case.status

        # 1. No-op if status is identical
        if current_status == new_status:
            return

        # 2. Check if current status is terminal
        if current_status in {CaseStatus.CLOSED, CaseStatus.DUPLICATE, CaseStatus.CANCELLED}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot transition case '{case.case_number}' from terminal state '{current_status.value}'.",
            )

        # 3. Check if transition is valid in the state machine
        allowed_targets = cls.VALID_TRANSITIONS.get(current_status, set())
        if new_status not in allowed_targets:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid status transition for case '{case.case_number}' from '{current_status.value}' to '{new_status.value}'. "
                    f"Allowed transitions are: {[s.value for s in allowed_targets]}"
                ),
            )

        # 4. RBAC authorization for specific transitions
        if actor.role == UserRole.REQUESTER:
            # Requesters can only confirm resolution, reject (reopen), or cancel their own open cases
            if new_status == CaseStatus.CANCELLED:
                if case.requester_id != actor.id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You can only cancel cases that you reported.",
                    )
            elif new_status in {CaseStatus.CONFIRMED, CaseStatus.REOPENED}:
                if case.requester_id != actor.id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Only the case requester can confirm or reopen a proposed resolution.",
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Requesters are not authorized to transition cases to '{new_status.value}'.",
                )
