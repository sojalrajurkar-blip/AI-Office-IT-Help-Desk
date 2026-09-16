import pytest
from sqlalchemy import select
from app.models.enums import UserRole, CaseStatus, CasePriority, CaseSeverity, MessageType
from app.models.user import User, Team
from app.models.category import Category
from app.models.case import Case, CaseSequence
from app.models.communication import CaseMessage, InternalNote
from app.models.task import CaseTask
from app.models.timeline_audit import AuditLog


@pytest.mark.asyncio
async def test_database_models_and_relationships(db_session):
    session = db_session

    # 1. Verify seeded teams and categories exist
    stmt = select(Team).where(Team.name == "Network Support")
    network_team = (await session.execute(stmt)).scalar_one_or_none()
    assert network_team is not None

    stmt = select(Category).where(Category.name == "Wi-Fi / Network Issue")
    wifi_category = (await session.execute(stmt)).scalar_one_or_none()
    assert wifi_category is not None

    # 2. Create test requester
    test_email = "test_user_phase2@example.com"
    stmt = select(User).where(User.email == test_email)
    existing_user = (await session.execute(stmt)).scalar_one_or_none()
    if not existing_user:
        requester = User(
            email=test_email,
            hashed_password="mock_hashed_password",
            full_name="Rajesh Sharma",
            role=UserRole.REQUESTER,
            office_location="Floor 3, Pune Office",
        )
        session.add(requester)
        await session.flush()
    else:
        requester = existing_user

    # 3. Create case with sequence number
    seq = CaseSequence()
    session.add(seq)
    await session.flush()
    case_num = f"IT-{10000 + seq.id}"

    test_case = Case(
        case_number=case_num,
        title="Wi-Fi disconnecting repeatedly",
        description="Laptop keeps losing Wi-Fi connection every 10 minutes.",
        office_location="Floor 3, Desk 42",
        status=CaseStatus.REPORTED,
        priority=CasePriority.HIGH,
        severity=CaseSeverity.MODERATE,
        category_id=wifi_category.id,
        requester_id=requester.id,
        assigned_team_id=network_team.id,
    )
    session.add(test_case)
    await session.flush()
    assert test_case.id is not None
    assert test_case.case_number.startswith("IT-")

    # 4. Add communication message and internal note
    msg = CaseMessage(
        case_id=test_case.id,
        sender_id=requester.id,
        message_type=MessageType.COMMUNICATION,
        content="Is there an update on this issue?",
    )
    note = InternalNote(
        case_id=test_case.id,
        author_id=requester.id,
        note_text="Staff note: Checked AP-302 logs, channel interference observed.",
    )
    session.add_all([msg, note])
    await session.flush()
    assert msg.id is not None
    assert note.id is not None

    # 5. Add a task
    task = CaseTask(
        case_id=test_case.id,
        title="Inspect Access Point AP-302",
        description="Check signal strength and reboot if needed.",
        created_by_id=requester.id,
    )
    session.add(task)
    await session.flush()
    assert task.id is not None

    # 6. Add an audit log entry
    audit = AuditLog(
        actor_id=requester.id,
        action="CREATE_CASE",
        entity_type="Case",
        entity_id=str(test_case.id),
        new_state={"case_number": case_num, "status": "REPORTED"},
    )
    session.add(audit)
    await session.commit()

    # 7. Query back to verify persistence
    query_case = (await session.execute(select(Case).where(Case.id == test_case.id))).scalar_one()
    assert query_case.case_number == case_num
    assert query_case.title == "Wi-Fi disconnecting repeatedly"
