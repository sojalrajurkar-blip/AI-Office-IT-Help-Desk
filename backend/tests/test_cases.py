import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.models.enums import UserRole, CaseStatus, CasePriority


async def get_auth_token(client: AsyncClient, email_prefix: str, role: UserRole) -> tuple[str, int]:
    unique_suffix = uuid.uuid4().hex[:6]
    email = f"{email_prefix}_{unique_suffix}@example.com"
    reg_payload = {
        "email": email,
        "password": "Password123!",
        "full_name": f"User {role.value}",
        "role": role.value,
        "office_location": "Floor 3, Pune Office",
    }
    await client.post("/api/v1/auth/register", json=reg_payload)
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    data = login_res.json()
    return data["access_token"], data["user_id"]


@pytest.mark.asyncio
async def test_case_creation_and_atomic_number():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token, user_id = await get_auth_token(client, "requester_create", UserRole.REQUESTER)
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Create a case
        payload = {
            "title": "VPN connection drops every hour",
            "description": "While working remotely, Cisco AnyConnect disconnects abruptly.",
            "office_location": "Remote - Pune",
            "priority": "HIGH",
            "severity": "MAJOR",
        }
        res = await client.post("/api/v1/cases/", json=payload, headers=headers)
        assert res.status_code == 201
        data = res.json()

        assert "case_number" in data
        assert data["case_number"].startswith("IT-")
        assert data["title"] == payload["title"]
        assert data["status"] == "REPORTED"
        assert data["priority"] == "HIGH"
        assert data["requester_id"] == user_id
        # Verify SLA deadlines are calculated
        assert data["response_deadline"] is not None
        assert data["resolution_deadline"] is not None
        case_id = data["id"]

        # 2. Verify Case Timeline has CASE_CREATED event
        timeline_res = await client.get(f"/api/v1/cases/{case_id}/timeline", headers=headers)
        assert timeline_res.status_code == 200
        events = timeline_res.json()
        assert len(events) >= 1
        assert events[0]["event_type"] == "CASE_CREATED"


@pytest.mark.asyncio
async def test_case_status_lifecycle_validation():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_token, req_id = await get_auth_token(client, "req_life", UserRole.REQUESTER)
        op_token, op_id = await get_auth_token(client, "op_life", UserRole.OPERATOR)

        req_h = {"Authorization": f"Bearer {req_token}"}
        op_h = {"Authorization": f"Bearer {op_token}"}

        # 1. Requester creates case
        create_res = await client.post(
            "/api/v1/cases/",
            json={"title": "Printer Jam on Floor 2", "description": "Paper tray 2 is stuck."},
            headers=req_h,
        )
        assert create_res.status_code == 201
        case_id = create_res.json()["id"]

        # 2. Invalid jump: Try transitioning REPORTED directly to CLOSED -> Must fail 400
        bad_res = await client.post(
            f"/api/v1/cases/{case_id}/status",
            json={"new_status": "CLOSED"},
            headers=op_h,
        )
        assert bad_res.status_code == 400
        assert "Invalid status transition" in bad_res.json()["detail"]

        # 3. Valid Step 1: REPORTED -> UNDERSTOOD
        r1 = await client.post(f"/api/v1/cases/{case_id}/status", json={"new_status": "UNDERSTOOD"}, headers=op_h)
        assert r1.status_code == 200
        assert r1.json()["status"] == "UNDERSTOOD"

        # 4. Valid Step 2: UNDERSTOOD -> ASSIGNED
        r2 = await client.post(f"/api/v1/cases/{case_id}/status", json={"new_status": "ASSIGNED"}, headers=op_h)
        assert r2.status_code == 200
        assert r2.json()["status"] == "ASSIGNED"

        # 5. Valid Step 3: ASSIGNED -> INVESTIGATING
        r3 = await client.post(f"/api/v1/cases/{case_id}/status", json={"new_status": "INVESTIGATING"}, headers=op_h)
        assert r3.status_code == 200
        assert r3.json()["status"] == "INVESTIGATING"

        # 6. Valid Step 4: INVESTIGATING -> ACTION_TAKEN
        r4 = await client.post(f"/api/v1/cases/{case_id}/status", json={"new_status": "ACTION_TAKEN"}, headers=op_h)
        assert r4.status_code == 200
        assert r4.json()["status"] == "ACTION_TAKEN"

        # 7. Valid Step 5: ACTION_TAKEN -> RESOLUTION_PROPOSED
        r5 = await client.post(f"/api/v1/cases/{case_id}/status", json={"new_status": "RESOLUTION_PROPOSED"}, headers=op_h)
        assert r5.status_code == 200
        assert r5.json()["status"] == "RESOLUTION_PROPOSED"

        # 8. Valid Step 6: Requester confirms resolution -> CONFIRMED
        r6 = await client.post(f"/api/v1/cases/{case_id}/status", json={"new_status": "CONFIRMED"}, headers=req_h)
        assert r6.status_code == 200
        assert r6.json()["status"] == "CONFIRMED"

        # 9. Valid Step 7: CONFIRMED -> CLOSED
        r7 = await client.post(f"/api/v1/cases/{case_id}/status", json={"new_status": "CLOSED"}, headers=op_h)
        assert r7.status_code == 200
        assert r7.json()["status"] == "CLOSED"
        assert r7.json()["closed_at"] is not None

        # 10. Attempting any transition from CLOSED must fail 400
        closed_attempt = await client.post(
            f"/api/v1/cases/{case_id}/status",
            json={"new_status": "REOPENED"},
            headers=op_h,
        )
        assert closed_attempt.status_code == 400
        assert "terminal state" in closed_attempt.json()["detail"]


@pytest.mark.asyncio
async def test_case_assignment_and_reassignment():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_token, req_id = await get_auth_token(client, "req_assign", UserRole.REQUESTER)
        op_token, op_id = await get_auth_token(client, "op_assign", UserRole.OPERATOR)

        req_h = {"Authorization": f"Bearer {req_token}"}
        op_h = {"Authorization": f"Bearer {op_token}"}

        # Create case
        c_res = await client.post(
            "/api/v1/cases/",
            json={"title": "Monitor flickering", "description": "HDMI display flickers continuously."},
            headers=req_h,
        )
        case_id = c_res.json()["id"]

        # Requester cannot assign -> 403 Forbidden
        req_assign = await client.post(
            f"/api/v1/cases/{case_id}/assign",
            json={"assigned_operator_id": op_id},
            headers=req_h,
        )
        assert req_assign.status_code == 403

        # Operator assigns case
        op_assign = await client.post(
            f"/api/v1/cases/{case_id}/assign",
            json={"assigned_operator_id": op_id, "notes": "Taking ownership of monitor issue."},
            headers=op_h,
        )
        assert op_assign.status_code == 200
        data = op_assign.json()
        assert data["assigned_operator_id"] == op_id
        assert data["status"] == "ASSIGNED"


@pytest.mark.asyncio
async def test_case_role_based_visibility_and_search():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req1_tok, req1_id = await get_auth_token(client, "user_alpha", UserRole.REQUESTER)
        req2_tok, req2_id = await get_auth_token(client, "user_beta", UserRole.REQUESTER)
        op_tok, op_id = await get_auth_token(client, "staff_gamma", UserRole.OPERATOR)

        # Requester 1 creates case
        r1 = await client.post(
            "/api/v1/cases/",
            json={"title": "UniqueIssueAlpha Keyboard Broken", "description": "Keys sticking on laptop."},
            headers={"Authorization": f"Bearer {req1_tok}"},
        )
        c1_num = r1.json()["case_number"]

        # Requester 2 creates case
        r2 = await client.post(
            "/api/v1/cases/",
            json={"title": "UniqueIssueBeta Mouse Missing", "description": "Need a wireless mouse."},
            headers={"Authorization": f"Bearer {req2_tok}"},
        )

        # Requester 1 lists cases: must only see their own cases, NEVER Requester 2's case
        req1_list = await client.get("/api/v1/cases/", headers={"Authorization": f"Bearer {req1_tok}"})
        assert req1_list.status_code == 200
        req1_items = req1_list.json()["items"]
        for c in req1_items:
            assert c["requester_id"] == req1_id

        # Operator lists cases: can see both cases
        op_list = await client.get("/api/v1/cases/", headers={"Authorization": f"Bearer {op_tok}"})
        assert op_list.status_code == 200
        assert op_list.json()["total"] >= 2

        # Search by case_number
        search_res = await client.get(f"/api/v1/cases/?search={c1_num}", headers={"Authorization": f"Bearer {op_tok}"})
        assert search_res.status_code == 200
        assert search_res.json()["total"] == 1
        assert search_res.json()["items"][0]["case_number"] == c1_num
