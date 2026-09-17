import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.enums import UserRole, NotificationType
from app.services.notification_service import (
    create_notification,
    set_push_notifier,
    LogPushNotifier,
)


async def get_auth_token(client: AsyncClient, email_prefix: str, role: UserRole) -> tuple[str, int]:
    unique_suffix = uuid.uuid4().hex[:6]
    email = f"{email_prefix}_{unique_suffix}@example.com"
    reg_payload = {
        "email": email,
        "password": "Password123!",
        "full_name": f"User {role.value} {unique_suffix}",
        "role": role.value,
        "office_location": "Floor 2, Mumbai HQ",
    }
    await client.post("/api/v1/auth/register", json=reg_payload)
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    data = login_res.json()
    return data["access_token"], data["user_id"]


@pytest.mark.asyncio
async def test_notification_endpoints_and_read_state(db_session: AsyncSession):
    """Test listing notifications, unread count badge, marking one read, and batch marking all read."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token, user_id = await get_auth_token(client, "notif_user", UserRole.REQUESTER)
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Initially 0 notifications
        res = await client.get("/api/v1/notifications", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 0
        assert data["unread_count"] == 0
        assert data["items"] == []

        # 2. Add 2 test notifications via service directly
        n1 = await create_notification(
            db=db_session,
            user_id=user_id,
            notification_type=NotificationType.NEW_CASE,
            title="Case Reported",
            message="Your case has been logged in the system.",
        )
        n2 = await create_notification(
            db=db_session,
            user_id=user_id,
            notification_type=NotificationType.ASSIGNMENT,
            title="Case Assigned",
            message="Technician assigned to your case.",
        )
        await db_session.commit()
        n1_id = n1.id
        n2_id = n2.id

        # 3. Check unread count endpoint
        count_res = await client.get("/api/v1/notifications/unread-count", headers=headers)
        assert count_res.status_code == 200
        assert count_res.json()["unread_count"] == 2

        # 4. List notifications
        list_res = await client.get("/api/v1/notifications", headers=headers)
        assert list_res.status_code == 200
        list_data = list_res.json()
        assert list_data["total"] == 2
        assert list_data["unread_count"] == 2
        assert len(list_data["items"]) == 2

        # 5. Mark n1 as read
        patch_res = await client.patch(f"/api/v1/notifications/{n1_id}/read", headers=headers)
        assert patch_res.status_code == 200
        assert patch_res.json()["is_read"] is True

        # Unread count should now be 1
        count_res = await client.get("/api/v1/notifications/unread-count", headers=headers)
        assert count_res.json()["unread_count"] == 1

        # 6. Filter unread only
        unread_res = await client.get("/api/v1/notifications?unread_only=true", headers=headers)
        assert unread_res.status_code == 200
        assert len(unread_res.json()["items"]) == 1
        assert unread_res.json()["items"][0]["id"] == n2_id

        # 7. Mark all read
        mark_all_res = await client.post("/api/v1/notifications/mark-all-read", headers=headers)
        assert mark_all_res.status_code == 200
        assert mark_all_res.json()["updated_count"] >= 1

        # Now unread count is 0
        count_res = await client.get("/api/v1/notifications/unread-count", headers=headers)
        assert count_res.json()["unread_count"] == 0


@pytest.mark.asyncio
async def test_user_notification_isolation(db_session: AsyncSession):
    """Ensure user notifications are strictly isolated; users cannot see or mutate other users' notifications."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token_a, user_a_id = await get_auth_token(client, "user_iso_a", UserRole.REQUESTER)
        token_b, user_b_id = await get_auth_token(client, "user_iso_b", UserRole.REQUESTER)

        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Create notification for User A
        n_a = await create_notification(
            db=db_session,
            user_id=user_a_id,
            notification_type=NotificationType.NEW_CASE,
            title="Confidential User A Alert",
            message="Only for user A",
        )
        await db_session.commit()
        n_a_id = n_a.id

        # User B lists notifications -> empty
        b_list = await client.get("/api/v1/notifications", headers=headers_b)
        assert b_list.status_code == 200
        assert b_list.json()["total"] == 0

        # User B tries to mark User A's notification as read -> 404 Not Found
        b_patch = await client.patch(f"/api/v1/notifications/{n_a_id}/read", headers=headers_b)
        assert b_patch.status_code == 404
        assert b_patch.json()["detail"] == "Notification not found"


@pytest.mark.asyncio
async def test_gate_case_assignment_trigger():
    """Gate test: Assigning a case triggers ASSIGNMENT in-app notification for the operator."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_token, req_id = await get_auth_token(client, "req_assign", UserRole.REQUESTER)
        op_token, op_id = await get_auth_token(client, "op_assign", UserRole.OPERATOR)
        lead_token, lead_id = await get_auth_token(client, "lead_assign", UserRole.TEAM_LEAD)

        req_headers = {"Authorization": f"Bearer {req_token}"}
        op_headers = {"Authorization": f"Bearer {op_token}"}
        lead_headers = {"Authorization": f"Bearer {lead_token}"}

        # 1. Requester creates case
        case_res = await client.post(
            "/api/v1/cases/",
            json={
                "title": "Monitor flickering in Conference Room B",
                "description": "The secondary display turns on and off during video meetings.",
                "priority": "MEDIUM",
                "severity": "MODERATE",
            },
            headers=req_headers,
        )
        assert case_res.status_code == 201
        case_id = case_res.json()["id"]
        case_number = case_res.json()["case_number"]

        # 2. Team Lead assigns case to Operator
        assign_res = await client.post(
            f"/api/v1/cases/{case_id}/assign",
            json={"assigned_operator_id": op_id, "notes": "Please check HDMI cabling and monitor drivers"},
            headers=lead_headers,
        )
        assert assign_res.status_code == 200

        # 3. Operator checks notifications -> ASSIGNMENT notification received
        op_notif_res = await client.get("/api/v1/notifications", headers=op_headers)
        assert op_notif_res.status_code == 200
        items = op_notif_res.json()["items"]
        matching = [n for n in items if n["case_id"] == case_id and n["notification_type"] == "ASSIGNMENT"]
        assert len(matching) >= 1
        assert case_number in matching[0]["title"] or case_number in matching[0]["message"]


@pytest.mark.asyncio
async def test_gate_requester_response_trigger():
    """Gate test: Requester responding triggers REQUESTER_RESPONSE notification for the assigned operator."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_token, req_id = await get_auth_token(client, "req_resp", UserRole.REQUESTER)
        op_token, op_id = await get_auth_token(client, "op_resp", UserRole.OPERATOR)

        req_headers = {"Authorization": f"Bearer {req_token}"}
        op_headers = {"Authorization": f"Bearer {op_token}"}

        # 1. Create and assign case
        case_res = await client.post(
            "/api/v1/cases/",
            json={
                "title": "Unable to connect to shared network drive",
                "description": "Drive Z: shows network path not found.",
                "priority": "HIGH",
            },
            headers=req_headers,
        )
        case_id = case_res.json()["id"]

        # Assign to operator
        await client.post(
            f"/api/v1/cases/{case_id}/assign",
            json={"assigned_operator_id": op_id},
            headers=op_headers,
        )

        # 2. Operator asks for info
        await client.post(
            f"/api/v1/cases/{case_id}/messages",
            json={"message_type": "INFO_REQUEST", "content": "Can you provide your machine IP address?"},
            headers=op_headers,
        )

        # 3. Requester provides info
        await client.post(
            f"/api/v1/cases/{case_id}/messages",
            json={"message_type": "INFO_RESPONSE", "content": "My IP is 192.168.1.145."},
            headers=req_headers,
        )

        # 4. Operator receives REQUESTER_RESPONSE notification
        op_notif_res = await client.get("/api/v1/notifications", headers=op_headers)
        assert op_notif_res.status_code == 200
        items = op_notif_res.json()["items"]
        matching = [n for n in items if n["case_id"] == case_id and n["notification_type"] == "REQUESTER_RESPONSE"]
        assert len(matching) >= 1


@pytest.mark.asyncio
async def test_gate_task_and_escalation_triggers():
    """Gate test: Task assignment creates NEW_TASK notification; escalation creates ESCALATION notification."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_token, _ = await get_auth_token(client, "req_task_esc", UserRole.REQUESTER)
        op_token, op_id = await get_auth_token(client, "op_task_esc", UserRole.OPERATOR)
        lead_token, lead_id = await get_auth_token(client, "lead_task_esc", UserRole.TEAM_LEAD)

        req_headers = {"Authorization": f"Bearer {req_token}"}
        op_headers = {"Authorization": f"Bearer {op_token}"}
        lead_headers = {"Authorization": f"Bearer {lead_token}"}

        # 1. Create case
        case_res = await client.post(
            "/api/v1/cases/",
            json={
                "title": "Core database access latency spike",
                "description": "Queries taking > 30 seconds across departments.",
                "priority": "CRITICAL",
                "severity": "CRITICAL",
            },
            headers=req_headers,
        )
        case_id = case_res.json()["id"]

        # 2. Lead creates task assigned to Operator
        task_res = await client.post(
            f"/api/v1/cases/{case_id}/tasks",
            json={
                "title": "Check database connection pool metrics",
                "description": "Inspect active vs idle connections on primary node.",
                "assigned_to_id": op_id,
            },
            headers=lead_headers,
        )
        assert task_res.status_code == 201

        # Operator receives NEW_TASK notification
        op_notifs = await client.get("/api/v1/notifications", headers=op_headers)
        assert op_notifs.status_code == 200
        task_notif = [n for n in op_notifs.json()["items"] if n["notification_type"] == "NEW_TASK"]
        assert len(task_notif) >= 1

        # 3. Operator escalates case to TEAM_LEAD
        esc_res = await client.post(
            f"/api/v1/cases/{case_id}/escalate",
            json={
                "target_role": "TEAM_LEAD",
                "reason": "Production outage requiring infrastructure team intervention.",
            },
            headers=op_headers,
        )
        assert esc_res.status_code == 201

        # Team Lead receives ESCALATION notification
        lead_notifs = await client.get("/api/v1/notifications", headers=lead_headers)
        assert lead_notifs.status_code == 200
        esc_notif = [n for n in lead_notifs.json()["items"] if n["notification_type"] == "ESCALATION"]
        assert len(esc_notif) >= 1


@pytest.mark.asyncio
async def test_push_notification_abstraction(db_session: AsyncSession):
    """Verify push notification provider logs and receives dispatched alerts."""
    test_notifier = LogPushNotifier()
    set_push_notifier(test_notifier)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        _, user_id = await get_auth_token(client, "push_user", UserRole.OPERATOR)

        await create_notification(
            db=db_session,
            user_id=user_id,
            notification_type=NotificationType.SLA_WARNING,
            title="SLA Risk Warning",
            message="Resolution window 85% elapsed.",
            case_id=None,
        )
        await db_session.commit()

        # Verify push record in test notifier
        assert len(test_notifier.dispatched_pushes) >= 1
        last_push = test_notifier.dispatched_pushes[-1]
        assert last_push["user_id"] == user_id
        assert last_push["title"] == "SLA Risk Warning"
        assert last_push["case_id"] is None
        assert last_push["notification_type"] == "SLA_WARNING"
