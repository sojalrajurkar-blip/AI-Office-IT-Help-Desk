import io
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.models.enums import UserRole, CasePriority, CaseSeverity, CaseStatus, NotificationType


async def register_and_login_role(client: AsyncClient, email_prefix: str, role: UserRole) -> tuple[str, int, dict]:
    unique_suffix = uuid.uuid4().hex[:6]
    email = f"{email_prefix}_{unique_suffix}@office.example.com"
    reg_payload = {
        "email": email,
        "password": "SecurePassword123!",
        "full_name": f"E2E {role.value.capitalize()} {unique_suffix}",
        "role": role.value,
        "office_location": "Floor 4, Bangalore Tech Park",
    }
    await client.post("/api/v1/auth/register", json=reg_payload)
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
    )
    data = login_res.json()
    token = data["access_token"]
    user_id = data["user_id"]
    headers = {"Authorization": f"Bearer {token}"}
    return token, user_id, headers


@pytest.mark.asyncio
async def test_full_office_it_incident_lifecycle_e2e():
    """
    Complete End-to-End Multi-Role Incident Scenario:
    Simulates a full enterprise Wi-Fi connectivity outage from initial reporting,
    AI triage, operator assignment, info request, evidence upload, task execution,
    resolution proposal, user confirmation, dynamic dashboard updates, and timeline verification.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # ----------------------------------------------------------------------
        # Setup: 5 Dedicated Personas
        # ----------------------------------------------------------------------
        _, req_id, req_headers = await register_and_login_role(client, "e2e_requester", UserRole.REQUESTER)
        _, op_id, op_headers = await register_and_login_role(client, "e2e_operator", UserRole.OPERATOR)
        _, lead_id, lead_headers = await register_and_login_role(client, "e2e_lead", UserRole.TEAM_LEAD)
        _, mgr_id, mgr_headers = await register_and_login_role(client, "e2e_manager", UserRole.MANAGER)
        _, admin_id, admin_headers = await register_and_login_role(client, "e2e_admin", UserRole.ADMIN)

        # ----------------------------------------------------------------------
        # Step 1: Requester Submits Wi-Fi Outage Ticket
        # ----------------------------------------------------------------------
        case_payload = {
            "title": "Executive Boardroom B Wi-Fi dropping connection during client demo",
            "description": "Laptops in Boardroom B on Floor 4 disconnect from 'Office-Corp-Secure'. Access point seems unresponsive.",
            "priority": "HIGH",
            "severity": "MAJOR",
            "location": "Floor 4, Boardroom B",
        }
        case_res = await client.post("/api/v1/cases/", json=case_payload, headers=req_headers)
        assert case_res.status_code == 201
        case_data = case_res.json()
        case_id = case_data["id"]
        case_number = case_data["case_number"]
        assert case_number.startswith("IT-")
        assert case_data["status"] == CaseStatus.REPORTED.value
        assert case_data["requester_id"] == req_id

        # ----------------------------------------------------------------------
        # Step 2: AI Triage Generation
        # ----------------------------------------------------------------------
        ai_res = await client.post(f"/api/v1/cases/{case_id}/ai-analysis", headers=op_headers)
        assert ai_res.status_code in [200, 201]
        ai_data = ai_res.json()
        analysis_id = ai_data["id"]
        assert "suggested_priority" in ai_data
        assert isinstance(ai_data["missing_information"], list)
        assert isinstance(ai_data["recommended_questions"], list)

        # ----------------------------------------------------------------------
        # Step 3: Operator Accepts AI Triage & Assigns Ticket
        # ----------------------------------------------------------------------
        review_res = await client.post(
            f"/api/v1/cases/{case_id}/ai-analyses/{analysis_id}/review",
            json={"is_accepted": True, "apply_suggestions": True},
            headers=op_headers,
        )
        assert review_res.status_code == 200

        # Operator assigns case to self
        assign_res = await client.post(
            f"/api/v1/cases/{case_id}/assign",
            json={"assigned_operator_id": op_id},
            headers=op_headers,
        )
        assert assign_res.status_code == 200
        assert assign_res.json()["status"] in [CaseStatus.ASSIGNED.value, CaseStatus.INVESTIGATING.value]
        assert assign_res.json()["assigned_operator_id"] == op_id

        # ----------------------------------------------------------------------
        # Step 4: Operator Requests Information from Requester (INFO_REQUEST)
        # ----------------------------------------------------------------------
        msg_req_res = await client.post(
            f"/api/v1/cases/{case_id}/messages",
            json={
                "content": "Could you check the LED indicator light on the Cisco AP mounted on the Boardroom B ceiling?",
                "message_type": "INFO_REQUEST",
            },
            headers=op_headers,
        )
        assert msg_req_res.status_code == 201

        # Check that case transitioned to WAITING_FOR_INFO
        case_check = await client.get(f"/api/v1/cases/{case_id}", headers=op_headers)
        assert case_check.status_code == 200
        assert case_check.json()["status"] == CaseStatus.WAITING_FOR_INFO.value

        # ----------------------------------------------------------------------
        # Step 5: Requester Uploads Photo Evidence & Replies (INFO_RESPONSE)
        # ----------------------------------------------------------------------
        # Requester uploads evidence
        dummy_file = io.BytesIO(b"DUMMY_IMAGE_BYTES_FOR_AP_ROUTER_LED_ORANGE")
        files = {"file": ("ap_led_status.jpg", dummy_file, "image/jpeg")}
        upload_res = await client.post(
            f"/api/v1/cases/{case_id}/attachments",
            files=files,
            headers=req_headers,
        )
        assert upload_res.status_code == 201
        attachment_id = upload_res.json()["id"]

        # Requester replies with info
        msg_resp_res = await client.post(
            f"/api/v1/cases/{case_id}/messages",
            json={
                "content": "The LED light on AP-4B-02 is blinking solid amber. I have attached a photo of the unit.",
                "message_type": "INFO_RESPONSE",
            },
            headers=req_headers,
        )
        assert msg_resp_res.status_code == 201

        # Check case transitioned back to INVESTIGATING
        case_check2 = await client.get(f"/api/v1/cases/{case_id}", headers=req_headers)
        assert case_check2.status_code == 200
        assert case_check2.json()["status"] == CaseStatus.INVESTIGATING.value

        # ----------------------------------------------------------------------
        # Step 6: Operator Adds Internal Staff Note, Tasks & Investigation Record
        # ----------------------------------------------------------------------
        # Staff-only internal note
        note_res = await client.post(
            f"/api/v1/cases/{case_id}/internal-notes",
            json={"note_text": "Checked IDF-4 switch port Gi1/0/24. PoE power delivery fluctuated due to bad RJ45 cable."},
            headers=op_headers,
        )
        assert note_res.status_code == 201

        # Requester is forbidden from reading internal notes
        req_notes = await client.get(f"/api/v1/cases/{case_id}/internal-notes", headers=req_headers)
        assert req_notes.status_code == 403

        # Operator creates diagnostic task
        task_res = await client.post(
            f"/api/v1/cases/{case_id}/tasks",
            json={
                "title": "Replace faulty Cat6 patch cable on IDF-4 Switch Port 24",
                "description": "Inspect RJ45 crimp, re-cable, and power-cycle Cisco AP-4B-02.",
                "assigned_to_id": op_id,
            },
            headers=op_headers,
        )
        assert task_res.status_code == 201
        task_id = task_res.json()["id"]

        # Operator completes task
        task_patch = await client.patch(
            f"/api/v1/tasks/{task_id}",
            json={
                "status": "COMPLETED",
                "findings": "Replaced patch cable. AP-4B-02 negotiated full PoE+ and rejoined WLC successfully.",
            },
            headers=op_headers,
        )
        assert task_patch.status_code == 200
        assert task_patch.json()["status"] == "COMPLETED"

        # Operator logs investigation record
        inv_res = await client.post(
            f"/api/v1/cases/{case_id}/investigations",
            json={
                "observations": "AP ceiling unit blinking amber, PoE negotiation intermittent on switch port.",
                "actions_taken": "Verified PoE delivery via CLI, tested cable continuity, replaced cable.",
                "findings": "Cable crimp had broken plastic retention tab.",
                "root_cause": "Damaged RJ45 clip on patch cord caused PoE drops.",
                "follow_up_required": "IDF-4 rack organized and labeled.",
            },
            headers=op_headers,
        )
        assert inv_res.status_code == 201

        # ----------------------------------------------------------------------
        # Step 7: Operator Proposes Resolution
        # ----------------------------------------------------------------------
        prop_res = await client.post(
            f"/api/v1/cases/{case_id}/resolution/propose",
            json={
                "actions_taken": "Replaced damaged Cat6 patch cable on IDF-4 port 24 and power-cycled Cisco AP-4B-02.",
                "findings": "Degraded RJ45 connector caused intermittent PoE drops on the ceiling access point.",
                "remaining_issues": "None; AP tested and verified with 50+ Mbps throughput on 5GHz band.",
            },
            headers=op_headers,
        )
        assert prop_res.status_code == 201
        assert prop_res.json()["status"] == "PROPOSED"

        # Check case transitioned to RESOLUTION_PROPOSED
        case_prop = await client.get(f"/api/v1/cases/{case_id}", headers=op_headers)
        assert case_prop.status_code == 200
        assert case_prop.json()["status"] == CaseStatus.RESOLUTION_PROPOSED.value

        # Requester receives in-app notification
        req_notifs = await client.get("/api/v1/notifications?unread_only=true", headers=req_headers)
        assert req_notifs.status_code == 200
        notif_items = req_notifs.json()["items"]
        assert any(n["notification_type"] == NotificationType.RESOLUTION.value for n in notif_items)

        # ----------------------------------------------------------------------
        # Step 8: Requester Confirms Resolution -> Case Closes
        # ----------------------------------------------------------------------
        conf_res = await client.post(
            f"/api/v1/cases/{case_id}/resolution/confirm",
            json={"feedback": "Tested Wi-Fi in Boardroom B; laptops are connecting immediately. Great job!"},
            headers=req_headers,
        )
        assert conf_res.status_code == 200
        assert conf_res.json()["status"] == "CONFIRMED"

        # Check case status transitioned to CLOSED
        case_closed = await client.get(f"/api/v1/cases/{case_id}", headers=req_headers)
        assert case_closed.status_code == 200
        assert case_closed.json()["status"] == CaseStatus.CLOSED.value
        assert case_closed.json()["closed_at"] is not None

        # ----------------------------------------------------------------------
        # Step 9: Dynamic Role-Based Dashboards Validation
        # ----------------------------------------------------------------------
        # Requester Dashboard
        req_dash = await client.get("/api/v1/dashboards/requester", headers=req_headers)
        assert req_dash.status_code == 200
        req_d = req_dash.json()
        assert req_d["active_cases_count"] == 0
        assert req_d["resolved_cases_count"] >= 1
        assert req_d["waiting_for_requester_count"] == 0

        # Operator Dashboard
        op_dash = await client.get("/api/v1/dashboards/operator", headers=op_headers)
        assert op_dash.status_code == 200
        op_d = op_dash.json()
        assert op_d["resolved_today_count"] >= 1

        # Team Lead Dashboard
        lead_dash = await client.get("/api/v1/dashboards/team-lead", headers=lead_headers)
        assert lead_dash.status_code == 200
        lead_d = lead_dash.json()
        assert "team_active_cases_count" in lead_d
        assert isinstance(lead_d["operator_workload"], list)

        # Manager Dashboard
        mgr_dash = await client.get("/api/v1/dashboards/manager", headers=mgr_headers)
        assert mgr_dash.status_code == 200
        mgr_d = mgr_dash.json()
        assert mgr_d["total_cases"] >= 1
        assert mgr_d["resolved_cases"] >= 1
        assert "sla_compliance_rate" in mgr_d
        assert "avg_resolution_time_hours" in mgr_d

        # Admin Dashboard
        admin_dash = await client.get("/api/v1/dashboards/admin", headers=admin_headers)
        assert admin_dash.status_code == 200
        admin_d = admin_dash.json()
        assert admin_d["total_cases"] >= 1
        assert admin_d["total_audit_logs"] >= 1
        assert admin_d["ai_analyses_total"] >= 1

        # ----------------------------------------------------------------------
        # Step 10: Admin Inspects Case Chronological Story Timeline
        # ----------------------------------------------------------------------
        timeline_res = await client.get(f"/api/v1/cases/{case_id}/timeline", headers=admin_headers)
        assert timeline_res.status_code == 200
        events = timeline_res.json()
        assert len(events) >= 6
        event_types = [e["event_type"] for e in events]
        
        # Verify key lifecycle milestones were logged in order
        assert "CASE_CREATED" in event_types or "CASE_REPORTED" in event_types
        assert "RESOLUTION_PROPOSED" in event_types
        assert "RESOLUTION_CONFIRMED" in event_types
        assert "CASE_CLOSED" in event_types
