import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.models.enums import UserRole, CaseStatus, ResolutionStatus


async def get_auth_token(client: AsyncClient, email_prefix: str, role: UserRole) -> tuple[str, int]:
    unique_suffix = uuid.uuid4().hex[:6]
    email = f"{email_prefix}_{unique_suffix}@example.com"
    reg_payload = {
        "email": email,
        "password": "Password123!",
        "full_name": f"User {role.value} {unique_suffix}",
        "role": role.value,
        "office_location": "Floor 3, Pune Tech Park",
    }
    await client.post("/api/v1/auth/register", json=reg_payload)
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    data = login_res.json()
    return data["access_token"], data["user_id"]


@pytest.mark.asyncio
async def test_gate_resolution_confirmation_flow():
    """
    Gate Test A:
    Operator resolves -> Requester confirms -> Case Closed.
    Verifies state transitions, timestamps, timeline logs, and in-app notifications.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_token, req_id = await get_auth_token(client, "req_conf", UserRole.REQUESTER)
        op_token, op_id = await get_auth_token(client, "op_conf", UserRole.OPERATOR)
        lead_token, _ = await get_auth_token(client, "lead_conf", UserRole.TEAM_LEAD)

        req_headers = {"Authorization": f"Bearer {req_token}"}
        op_headers = {"Authorization": f"Bearer {op_token}"}
        lead_headers = {"Authorization": f"Bearer {lead_token}"}

        # 1. Requester creates case
        case_res = await client.post(
            "/api/v1/cases/",
            json={
                "title": "Dual monitor display resolution resetting",
                "description": "Upon reboot, the secondary 4K monitor falls back to 1080p resolution.",
                "priority": "MEDIUM",
                "severity": "MODERATE",
            },
            headers=req_headers,
        )
        assert case_res.status_code == 201
        case_id = case_res.json()["id"]
        case_num = case_res.json()["case_number"]

        # 2. Assign case to operator
        await client.post(
            f"/api/v1/cases/{case_id}/assign",
            json={"assigned_operator_id": op_id},
            headers=lead_headers,
        )

        # 3. Operator marks INVESTIGATING
        await client.patch(
            f"/api/v1/cases/{case_id}/status",
            json={"new_status": "INVESTIGATING", "notes": "Diagnosing GPU driver settings."},
            headers=op_headers,
        )

        # 4. Operator proposes resolution
        prop_res = await client.post(
            f"/api/v1/cases/{case_id}/resolution/propose",
            json={
                "actions_taken": "Updated DisplayLink docking station firmware and reinstalled NVIDIA Quadro drivers v550.40.",
                "findings": "Firmware handshake timing out on DisplayPort 1.4.",
                "remaining_issues": "None observed during multi-reboot test cycles.",
            },
            headers=op_headers,
        )
        assert prop_res.status_code == 201
        prop_data = prop_res.json()
        assert prop_data["status"] == "PROPOSED"
        assert prop_data["operator_id"] == op_id
        assert prop_data["proposed_at"] is not None

        # Verify case status transitioned to RESOLUTION_PROPOSED
        case_get = await client.get(f"/api/v1/cases/{case_id}", headers=req_headers)
        assert case_get.json()["status"] == "RESOLUTION_PROPOSED"

        # Verify Requester received RESOLUTION notification
        req_notifs = await client.get("/api/v1/notifications", headers=req_headers)
        res_notif = [n for n in req_notifs.json()["items"] if n["notification_type"] == "RESOLUTION"]
        assert len(res_notif) >= 1
        assert case_num in res_notif[0]["title"] or case_num in res_notif[0]["message"]

        # 5. Requester confirms resolution
        conf_res = await client.post(
            f"/api/v1/cases/{case_id}/resolution/confirm",
            json={"feedback": "Both monitors now stay at native 4K across restarts. Thank you!"},
            headers=req_headers,
        )
        assert conf_res.status_code == 200
        conf_data = conf_res.json()
        assert conf_data["status"] == "CONFIRMED"
        assert conf_data["confirmed_at"] is not None
        assert "native 4K" in conf_data["requester_feedback"]

        # Verify case is now CLOSED
        case_closed = await client.get(f"/api/v1/cases/{case_id}", headers=req_headers)
        assert case_closed.json()["status"] == "CLOSED"
        assert case_closed.json()["closed_at"] is not None

        # 6. Verify Timeline events recorded
        timeline_res = await client.get(f"/api/v1/cases/{case_id}/timeline", headers=req_headers)
        events = timeline_res.json()
        event_types = [e["event_type"] for e in events]
        assert "RESOLUTION_PROPOSED" in event_types
        assert "RESOLUTION_CONFIRMED" in event_types
        assert "CASE_CLOSED" in event_types


@pytest.mark.asyncio
async def test_gate_resolution_rejection_reopen_flow():
    """
    Gate Test B:
    Operator resolves -> Requester rejects -> Case Reopened -> Operator fixes -> Requester confirms -> Closed.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_token, req_id = await get_auth_token(client, "req_rej", UserRole.REQUESTER)
        op_token, op_id = await get_auth_token(client, "op_rej", UserRole.OPERATOR)

        req_headers = {"Authorization": f"Bearer {req_token}"}
        op_headers = {"Authorization": f"Bearer {op_token}"}

        # 1. Create and assign case
        case_res = await client.post(
            "/api/v1/cases/",
            json={
                "title": "Slack desktop notifications not appearing",
                "description": "Direct messages do not display banner popups.",
                "priority": "LOW",
            },
            headers=req_headers,
        )
        case_id = case_res.json()["id"]

        await client.post(
            f"/api/v1/cases/{case_id}/assign",
            json={"assigned_operator_id": op_id},
            headers=op_headers,
        )

        # 2. Operator proposes first resolution (e.g. premature or incomplete fix)
        await client.post(
            f"/api/v1/cases/{case_id}/resolution/propose",
            json={"actions_taken": "Toggled notification toggle inside Slack preferences."},
            headers=op_headers,
        )

        # 3. Requester tests and rejects resolution
        rej_res = await client.post(
            f"/api/v1/cases/{case_id}/resolution/reject",
            json={"rejection_reason": "Still not working. Windows Focus Assist was blocking all notifications."},
            headers=req_headers,
        )
        assert rej_res.status_code == 200
        rej_data = rej_res.json()
        assert rej_data["status"] == "REJECTED"
        assert "Focus Assist" in rej_data["rejection_reason"]

        # Verify case is now REOPENED
        case_reopened = await client.get(f"/api/v1/cases/{case_id}", headers=req_headers)
        assert case_reopened.json()["status"] == "REOPENED"

        # Verify Operator received REOPENED in-app notification
        op_notifs = await client.get("/api/v1/notifications", headers=op_headers)
        reopened_notif = [n for n in op_notifs.json()["items"] if n["notification_type"] == "REOPENED"]
        assert len(reopened_notif) >= 1

        # 4. Operator investigates again and proposes correct fix
        await client.patch(
            f"/api/v1/cases/{case_id}/status",
            json={"new_status": "INVESTIGATING", "notes": "Configuring OS Focus Assist priority rules."},
            headers=op_headers,
        )

        prop_res2 = await client.post(
            f"/api/v1/cases/{case_id}/resolution/propose",
            json={"actions_taken": "Disabled Windows Focus Assist quiet hours and added Slack to priority list."},
            headers=op_headers,
        )
        assert prop_res2.status_code == 201

        # 5. Requester confirms second resolution
        conf_res2 = await client.post(
            f"/api/v1/cases/{case_id}/resolution/confirm",
            json={"feedback": "Now working perfectly! Popups appear promptly."},
            headers=req_headers,
        )
        assert conf_res2.status_code == 200

        # Verify final CLOSED status
        final_case = await client.get(f"/api/v1/cases/{case_id}", headers=req_headers)
        assert final_case.json()["status"] == "CLOSED"

        # 6. Verify list of resolutions has both attempts (one REJECTED, one CONFIRMED)
        res_list = await client.get(f"/api/v1/cases/{case_id}/resolutions", headers=req_headers)
        assert res_list.status_code == 200
        resolutions = res_list.json()
        assert len(resolutions) == 2
        statuses = [r["status"] for r in resolutions]
        assert "REJECTED" in statuses
        assert "CONFIRMED" in statuses


@pytest.mark.asyncio
async def test_resolution_rbac_and_isolation():
    """Verify authorization checks: Requesters cannot propose; other users cannot confirm/reject."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_a_token, req_a_id = await get_auth_token(client, "req_iso_a", UserRole.REQUESTER)
        req_b_token, req_b_id = await get_auth_token(client, "req_iso_b", UserRole.REQUESTER)
        op_token, op_id = await get_auth_token(client, "op_iso", UserRole.OPERATOR)

        headers_a = {"Authorization": f"Bearer {req_a_token}"}
        headers_b = {"Authorization": f"Bearer {req_b_token}"}
        headers_op = {"Authorization": f"Bearer {op_token}"}

        # 1. User A creates case
        case_res = await client.post(
            "/api/v1/cases/",
            json={"title": "Keyboard spacebar stuck", "description": "Mechanical keyboard key jam."},
            headers=headers_a,
        )
        case_id = case_res.json()["id"]

        # 2. Requester A tries to propose resolution -> 403 Forbidden (Staff only)
        prop_fail = await client.post(
            f"/api/v1/cases/{case_id}/resolution/propose",
            json={"actions_taken": "I cleaned it myself with compressed air."},
            headers=headers_a,
        )
        assert prop_fail.status_code == 403

        # 3. Operator proposes resolution
        await client.post(
            f"/api/v1/cases/{case_id}/resolution/propose",
            json={"actions_taken": "Replaced key switch and cleaned socket."},
            headers=headers_op,
        )

        # 4. User B tries to confirm User A's case -> 403 Forbidden
        conf_fail = await client.post(
            f"/api/v1/cases/{case_id}/resolution/confirm",
            json={"feedback": "Looks good from user B perspective."},
            headers=headers_b,
        )
        assert conf_fail.status_code == 403

        # 5. User B tries to reject User A's case -> 403 Forbidden
        rej_fail = await client.post(
            f"/api/v1/cases/{case_id}/resolution/reject",
            json={"rejection_reason": "Malicious reject attempt from user B."},
            headers=headers_b,
        )
        assert rej_fail.status_code == 403


@pytest.mark.asyncio
async def test_resolution_invalid_state_guards():
    """Verify validation guards: Cannot confirm without proposal; cannot propose on closed case."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_token, _ = await get_auth_token(client, "req_guard", UserRole.REQUESTER)
        op_token, _ = await get_auth_token(client, "op_guard", UserRole.OPERATOR)

        req_headers = {"Authorization": f"Bearer {req_token}"}
        op_headers = {"Authorization": f"Bearer {op_token}"}

        # 1. Create case (status: REPORTED)
        case_res = await client.post(
            "/api/v1/cases/",
            json={"title": "Printer paper feed error", "description": "Tray 2 misfeeding."},
            headers=req_headers,
        )
        case_id = case_res.json()["id"]

        # 2. Trying to confirm while in REPORTED -> 400 Bad Request
        conf_bad = await client.post(
            f"/api/v1/cases/{case_id}/resolution/confirm",
            json={"feedback": "Premature confirm."},
            headers=req_headers,
        )
        assert conf_bad.status_code == 400

        # 3. Propose resolution -> Confirm -> Closed
        await client.post(
            f"/api/v1/cases/{case_id}/resolution/propose",
            json={"actions_taken": "Replaced feed rollers in Tray 2."},
            headers=op_headers,
        )
        await client.post(
            f"/api/v1/cases/{case_id}/resolution/confirm",
            json={"feedback": "Prints cleanly now."},
            headers=req_headers,
        )

        # 4. Trying to propose resolution on already CLOSED case -> 400 Bad Request
        prop_closed = await client.post(
            f"/api/v1/cases/{case_id}/resolution/propose",
            json={"actions_taken": "Another fix attempt on closed case."},
            headers=op_headers,
        )
        assert prop_closed.status_code == 400
