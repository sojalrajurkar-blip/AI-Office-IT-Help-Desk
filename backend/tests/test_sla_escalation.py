import uuid
from datetime import datetime, timezone, timedelta
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.main import app
from app.models.case import Case
from app.models.enums import UserRole, CasePriority, CaseSeverity, CaseStatus, RiskLevel, EscalationStatus


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


async def create_sample_case(client: AsyncClient, token: str, priority: str = "HIGH", severity: str = "MAJOR") -> int:
    headers = {"Authorization": f"Bearer {token}"}
    res = await client.post(
        "/api/v1/cases/",
        json={
            "title": f"VPN latency issues - {uuid.uuid4().hex[:4]}",
            "description": "High packet loss observed across executive floor during call.",
            "office_location": "Floor 4, Conference Room B",
            "priority": priority,
            "severity": severity,
        },
        headers=headers,
    )
    assert res.status_code == 201
    return res.json()["id"]


@pytest.mark.asyncio
async def test_sla_policies_list_and_create():
    """Verify seeded SLA policies and Admin-only creation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin_token, _ = await get_auth_token(client, "admin_sla", UserRole.ADMIN)
        req_token, _ = await get_auth_token(client, "req_sla", UserRole.REQUESTER)
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        req_headers = {"Authorization": f"Bearer {req_token}"}

        # 1. List policies
        res = await client.get("/api/v1/sla/policies", headers=req_headers)
        assert res.status_code == 200
        policies = res.json()
        assert len(policies) >= 4
        priorities = [p["priority"] for p in policies]
        assert "CRITICAL" in priorities
        assert "HIGH" in priorities

        # 2. Requester cannot create SLA policies
        bad_res = await client.post(
            "/api/v1/sla/policies",
            json={"name": "Custom SLA", "priority": "LOW", "response_time_hours": 2, "resolution_time_hours": 6},
            headers=req_headers,
        )
        assert bad_res.status_code == 403


@pytest.mark.asyncio
async def test_gate_create_at_risk_case_and_verify_detection(db_session):
    """
    Phase 7 Gate Requirement:
    Create an at-risk case locally and verify correct detection and display.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_token, _ = await get_auth_token(client, "req_gate7", UserRole.REQUESTER)
        op_token, _ = await get_auth_token(client, "op_gate7", UserRole.OPERATOR)
        op_headers = {"Authorization": f"Bearer {op_token}"}

        # 1. Create a critical severity case
        case_id = await create_sample_case(client, req_token, priority="CRITICAL", severity="CRITICAL")

        # 2. Simulate aging / approaching deadline: set deadline so 80% of window has passed
        now = datetime.now(timezone.utc)
        case = await db_session.get(Case, case_id)
        assert case is not None
        case.created_at = now - timedelta(hours=3, minutes=15)
        case.response_deadline = now - timedelta(minutes=15)  # Breached response deadline
        case.resolution_deadline = now + timedelta(minutes=45)  # 80% elapsed
        await db_session.commit()

        # 3. Verify SLA status displays at-risk and warning
        sla_res = await client.get(f"/api/v1/cases/{case_id}/sla-status", headers=op_headers)
        assert sla_res.status_code == 200
        sla_data = sla_res.json()
        assert sla_data["is_at_risk"] is True
        assert sla_data["is_sla_breached"] is True
        assert sla_data["warning_message"] is not None

        # 4. Verify multi-factor risk engine detects and explains risk reasons
        risk_res = await client.get(f"/api/v1/cases/{case_id}/risk", headers=op_headers)
        assert risk_res.status_code == 200
        risk_data = risk_res.json()
        assert risk_data["is_at_risk"] is True
        assert risk_data["risk_level"] in ["HIGH", "CRITICAL"]
        assert len(risk_data["reasons"]) >= 1
        assert any("SLA" in r or "Critical" in r for r in risk_data["reasons"])


@pytest.mark.asyncio
async def test_sla_breach_detection_and_flag(db_session):
    """Verify overdue resolution deadline triggers automated breach recording."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_token, _ = await get_auth_token(client, "req_breach", UserRole.REQUESTER)
        op_token, _ = await get_auth_token(client, "op_breach", UserRole.OPERATOR)
        op_headers = {"Authorization": f"Bearer {op_token}"}

        case_id = await create_sample_case(client, req_token, priority="HIGH", severity="MAJOR")

        # Artificially set resolution deadline in the past
        now = datetime.now(timezone.utc)
        case = await db_session.get(Case, case_id)
        assert case is not None
        case.resolution_deadline = now - timedelta(hours=1)
        await db_session.commit()

        # Query SLA status - should detect breach and persist flag
        res = await client.get(f"/api/v1/cases/{case_id}/sla-status", headers=op_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["is_sla_breached"] is True
        assert data["is_resolution_breached"] is True

        # Verify case in DB now has is_sla_breached=True
        await db_session.refresh(case)
        assert case.is_sla_breached is True
        assert case.sla_breached_at is not None


@pytest.mark.asyncio
async def test_case_escalation_lifecycle_and_team_lead_intervention():
    """
    Verify escalation lifecycle:
    Operator escalates -> Case status becomes ESCALATED -> Team Lead resolves with notes -> Case status returns to INVESTIGATING.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_token, _ = await get_auth_token(client, "req_esc", UserRole.REQUESTER)
        op_token, op_id = await get_auth_token(client, "op_esc", UserRole.OPERATOR)
        lead_token, lead_id = await get_auth_token(client, "lead_esc", UserRole.TEAM_LEAD)
        req_headers = {"Authorization": f"Bearer {req_token}"}
        op_headers = {"Authorization": f"Bearer {op_token}"}
        lead_headers = {"Authorization": f"Bearer {lead_token}"}

        case_id = await create_sample_case(client, req_token)

        # 1. Requester cannot escalate
        forbid_res = await client.post(
            f"/api/v1/cases/{case_id}/escalate",
            json={"reason": "Need manager attention immediately"},
            headers=req_headers,
        )
        assert forbid_res.status_code == 403

        # 2. Operator escalates case to Team Lead
        esc_res = await client.post(
            f"/api/v1/cases/{case_id}/escalate",
            json={
                "reason": "Core router switch appears fried; requiring hardware replacement authorization.",
                "target_role": "TEAM_LEAD",
            },
            headers=op_headers,
        )
        assert esc_res.status_code == 201
        esc_data = esc_res.json()
        assert esc_data["case_id"] == case_id
        assert esc_data["status"] == "PENDING"
        assert esc_data["target_role"] == "TEAM_LEAD"
        escalation_id = esc_data["id"]

        # 3. Verify case status changed to ESCALATED
        case_res = await client.get(f"/api/v1/cases/{case_id}", headers=op_headers)
        assert case_res.json()["status"] == "ESCALATED"

        # 4. Operator cannot resolve escalation (only Team Lead, Manager, Admin can)
        forbid_resolve = await client.post(
            f"/api/v1/escalations/{escalation_id}/resolve",
            json={"resolution_notes": "Trying to resolve myself"},
            headers=op_headers,
        )
        assert forbid_resolve.status_code == 403

        # 5. Team Lead intervenes and resolves escalation
        lead_res = await client.post(
            f"/api/v1/escalations/{escalation_id}/resolve",
            json={
                "resolution_notes": "Replacement router approved and dispatched from inventory. Proceed with swap.",
                "next_status": "INVESTIGATING",
            },
            headers=lead_headers,
        )
        assert lead_res.status_code == 200
        lead_data = lead_res.json()
        assert lead_data["status"] == "RESOLVED"
        assert lead_data["resolved_by_id"] == lead_id
        assert "Replacement router approved" in lead_data["resolution_notes"]

        # 6. Verify case status restored to INVESTIGATING
        case_res_after = await client.get(f"/api/v1/cases/{case_id}", headers=op_headers)
        assert case_res_after.json()["status"] == "INVESTIGATING"

        # 7. Check escalation list endpoint
        list_res = await client.get(f"/api/v1/cases/{case_id}/escalations", headers=op_headers)
        assert list_res.status_code == 200
        assert len(list_res.json()) >= 1


@pytest.mark.asyncio
async def test_lightweight_sla_and_risk_sweep():
    """Verify lightweight sweep engine scans active tickets and produces summary report."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_token, _ = await get_auth_token(client, "req_swp", UserRole.REQUESTER)
        op_token, _ = await get_auth_token(client, "op_swp", UserRole.OPERATOR)
        op_headers = {"Authorization": f"Bearer {op_token}"}

        # Create at least one case
        await create_sample_case(client, req_token)

        # Trigger sweep
        res = await client.post("/api/v1/sla/sweep", headers=op_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total_scanned"] >= 1
        assert isinstance(data["breaches_detected"], int)
        assert isinstance(data["at_risk_detected"], int)
        assert isinstance(data["updated_cases"], list)
