import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.models.enums import UserRole, CasePriority, CaseSeverity


async def get_auth_token(client: AsyncClient, email_prefix: str, role: UserRole, team_id: int = None) -> tuple[str, int]:
    unique_suffix = uuid.uuid4().hex[:6]
    email = f"{email_prefix}_{unique_suffix}@example.com"
    reg_payload = {
        "email": email,
        "password": "Password123!",
        "full_name": f"User {role.value} {unique_suffix}",
        "role": role.value,
        "office_location": "Floor 4, Bangalore Tech Park",
    }
    await client.post("/api/v1/auth/register", json=reg_payload)
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    data = login_res.json()
    return data["access_token"], data["user_id"]


@pytest.mark.asyncio
async def test_gate_real_actions_mutate_dashboard_data():
    """
    Gate Test:
    Verify that real ticket actions (creation, assignment, task creation, resolution, closure)
    dynamically update the live metrics of Requester and Operator dashboards.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_token, req_id = await get_auth_token(client, "dash_gate_req", UserRole.REQUESTER)
        op_token, op_id = await get_auth_token(client, "dash_gate_op", UserRole.OPERATOR)
        lead_token, _ = await get_auth_token(client, "dash_gate_lead", UserRole.TEAM_LEAD)

        req_headers = {"Authorization": f"Bearer {req_token}"}
        op_headers = {"Authorization": f"Bearer {op_token}"}
        lead_headers = {"Authorization": f"Bearer {lead_token}"}

        # 1. Initial Requester Dashboard check (0 active)
        req_d0 = await client.get("/api/v1/dashboards/me", headers=req_headers)
        assert req_d0.status_code == 200
        assert req_d0.json()["active_cases_count"] == 0

        # 2. Requester creates a case -> active count increments to 1
        case_res = await client.post(
            "/api/v1/cases/",
            json={
                "title": "VoIP desk phone no dial tone",
                "description": "Cisco IP Phone 8845 shows ethernet disconnected.",
                "priority": "HIGH",
                "severity": "MODERATE",
            },
            headers=req_headers,
        )
        assert case_res.status_code == 201
        case_id = case_res.json()["id"]

        req_d1 = await client.get("/api/v1/dashboards/me", headers=req_headers)
        assert req_d1.status_code == 200
        assert req_d1.json()["active_cases_count"] == 1
        assert len(req_d1.json()["recent_cases"]) == 1

        # 3. Initial Operator Dashboard check (0 assigned)
        op_d0 = await client.get("/api/v1/dashboards/me", headers=op_headers)
        assert op_d0.status_code == 200
        assert op_d0.json()["assigned_open_cases_count"] == 0

        # 4. Lead assigns case to Operator -> Operator assigned count becomes 1
        await client.post(
            f"/api/v1/cases/{case_id}/assign",
            json={"assigned_operator_id": op_id},
            headers=lead_headers,
        )

        op_d1 = await client.get("/api/v1/dashboards/me", headers=op_headers)
        assert op_d1.status_code == 200
        assert op_d1.json()["assigned_open_cases_count"] == 1
        assert op_d1.json()["high_priority_cases_count"] == 1

        # 5. Lead creates a task for Operator -> Operator pending_tasks_count becomes 1
        await client.post(
            f"/api/v1/cases/{case_id}/tasks",
            json={"title": "Test switch port PoE power output", "assigned_to_id": op_id},
            headers=lead_headers,
        )

        op_d2 = await client.get("/api/v1/dashboards/me", headers=op_headers)
        assert op_d2.json()["pending_tasks_count"] == 1

        # 6. Operator proposes resolution -> Requester waiting_for_requester_count becomes 1
        await client.post(
            f"/api/v1/cases/{case_id}/resolution/propose",
            json={"actions_taken": "Re-punched RJ45 jack on wall port 4B and verified PoE power delivery."},
            headers=op_headers,
        )

        req_d2 = await client.get("/api/v1/dashboards/me", headers=req_headers)
        assert req_d2.json()["waiting_for_requester_count"] == 1

        # 7. Requester confirms resolution -> Requester active count becomes 0, resolved count becomes 1
        await client.post(
            f"/api/v1/cases/{case_id}/resolution/confirm",
            json={"feedback": "Dial tone restored."},
            headers=req_headers,
        )

        req_d3 = await client.get("/api/v1/dashboards/me", headers=req_headers)
        assert req_d3.json()["active_cases_count"] == 0
        assert req_d3.json()["resolved_cases_count"] == 1

        # 8. Operator dashboard reflects resolved_today_count == 1 and assigned_open == 0
        op_d3 = await client.get("/api/v1/dashboards/me", headers=op_headers)
        assert op_d3.json()["assigned_open_cases_count"] == 0
        assert op_d3.json()["resolved_today_count"] == 1


@pytest.mark.asyncio
async def test_requester_dashboard_isolation():
    """Verify Requesters strictly only see metrics and cases belonging to themselves."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_a_token, _ = await get_auth_token(client, "req_iso_dash_a", UserRole.REQUESTER)
        req_b_token, _ = await get_auth_token(client, "req_iso_dash_b", UserRole.REQUESTER)

        headers_a = {"Authorization": f"Bearer {req_a_token}"}
        headers_b = {"Authorization": f"Bearer {req_b_token}"}

        # User A creates 2 cases
        await client.post("/api/v1/cases/", json={"title": "Case A1", "description": "Desc A1"}, headers=headers_a)
        await client.post("/api/v1/cases/", json={"title": "Case A2", "description": "Desc A2"}, headers=headers_a)

        # User B creates 1 case
        await client.post("/api/v1/cases/", json={"title": "Case B1", "description": "Desc B1"}, headers=headers_b)

        # Inspect User A dashboard
        res_a = await client.get("/api/v1/dashboards/requester", headers=headers_a)
        assert res_a.status_code == 200
        data_a = res_a.json()
        assert data_a["active_cases_count"] == 2
        titles_a = [c["title"] for c in data_a["recent_cases"]]
        assert "Case A1" in titles_a
        assert "Case A2" in titles_a
        assert "Case B1" not in titles_a

        # Inspect User B dashboard
        res_b = await client.get("/api/v1/dashboards/requester", headers=headers_b)
        assert res_b.status_code == 200
        data_b = res_b.json()
        assert data_b["active_cases_count"] == 1
        titles_b = [c["title"] for c in data_b["recent_cases"]]
        assert "Case B1" in titles_b
        assert "Case A1" not in titles_b


@pytest.mark.asyncio
async def test_team_lead_dashboard_workload():
    """Verify Team Lead dashboard dynamically reflects operator workload and priority breakdown."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        lead_token, lead_id = await get_auth_token(client, "lead_wl", UserRole.TEAM_LEAD)
        op1_token, op1_id = await get_auth_token(client, "op_wl_1", UserRole.OPERATOR)
        op2_token, op2_id = await get_auth_token(client, "op_wl_2", UserRole.OPERATOR)
        req_token, _ = await get_auth_token(client, "req_wl", UserRole.REQUESTER)

        lead_headers = {"Authorization": f"Bearer {lead_token}"}
        req_headers = {"Authorization": f"Bearer {req_token}"}

        # Create 2 cases and assign to op1, 1 case to op2
        c1 = (await client.post("/api/v1/cases/", json={"title": "Lead Case 1", "description": "Desc 1", "priority": "CRITICAL"}, headers=req_headers)).json()["id"]
        c2 = (await client.post("/api/v1/cases/", json={"title": "Lead Case 2", "description": "Desc 2", "priority": "HIGH"}, headers=req_headers)).json()["id"]
        c3 = (await client.post("/api/v1/cases/", json={"title": "Lead Case 3", "description": "Desc 3", "priority": "LOW"}, headers=req_headers)).json()["id"]

        await client.post(f"/api/v1/cases/{c1}/assign", json={"assigned_operator_id": op1_id}, headers=lead_headers)
        await client.post(f"/api/v1/cases/{c2}/assign", json={"assigned_operator_id": op1_id}, headers=lead_headers)
        await client.post(f"/api/v1/cases/{c3}/assign", json={"assigned_operator_id": op2_id}, headers=lead_headers)

        # Team Lead dashboard check
        tl_res = await client.get("/api/v1/dashboards/team-lead", headers=lead_headers)
        assert tl_res.status_code == 200
        tl_data = tl_res.json()
        assert "priority_breakdown" in tl_data
        assert "operator_workload" in tl_data
        assert "team_active_cases_count" in tl_data


@pytest.mark.asyncio
async def test_manager_and_admin_dashboard_metrics():
    """Verify Manager and Admin dashboards compute organization KPIs and system-wide totals."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        mgr_token, _ = await get_auth_token(client, "mgr_metric", UserRole.MANAGER)
        admin_token, _ = await get_auth_token(client, "admin_metric", UserRole.ADMIN)

        mgr_headers = {"Authorization": f"Bearer {mgr_token}"}
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Manager Dashboard
        mgr_res = await client.get("/api/v1/dashboards/manager", headers=mgr_headers)
        assert mgr_res.status_code == 200
        mgr_data = mgr_res.json()
        assert mgr_data["total_cases"] >= 1
        assert "sla_compliance_rate" in mgr_data
        assert "avg_resolution_time_hours" in mgr_data
        assert isinstance(mgr_data["team_performance"], list)
        assert isinstance(mgr_data["category_breakdown"], list)

        # Admin Dashboard
        admin_res = await client.get("/api/v1/dashboards/admin", headers=admin_headers)
        assert admin_res.status_code == 200
        admin_data = admin_res.json()
        assert admin_data["total_users"] >= 1
        assert admin_data["total_teams"] >= 1
        assert admin_data["total_categories"] >= 1
        assert admin_data["active_sla_policies"] >= 1
        assert admin_data["total_cases"] >= 1
        assert "users_by_role" in admin_data
        assert "ai_analyses_total" in admin_data


@pytest.mark.asyncio
async def test_dashboard_role_authorization_guards():
    """Verify RBAC access controls on dashboard endpoints."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_token, _ = await get_auth_token(client, "req_guard_dash", UserRole.REQUESTER)
        op_token, _ = await get_auth_token(client, "op_guard_dash", UserRole.OPERATOR)

        req_headers = {"Authorization": f"Bearer {req_token}"}
        op_headers = {"Authorization": f"Bearer {op_token}"}

        # Requester forbidden from Operator, Team Lead, Manager, Admin dashboards
        assert (await client.get("/api/v1/dashboards/operator", headers=req_headers)).status_code == 403
        assert (await client.get("/api/v1/dashboards/team-lead", headers=req_headers)).status_code == 403
        assert (await client.get("/api/v1/dashboards/manager", headers=req_headers)).status_code == 403
        assert (await client.get("/api/v1/dashboards/admin", headers=req_headers)).status_code == 403

        # Operator forbidden from Admin and Manager dashboards
        assert (await client.get("/api/v1/dashboards/manager", headers=op_headers)).status_code == 403
        assert (await client.get("/api/v1/dashboards/admin", headers=op_headers)).status_code == 403
