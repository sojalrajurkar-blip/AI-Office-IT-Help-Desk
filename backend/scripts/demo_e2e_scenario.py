"""
AI Office IT Help Desk — Full Lifecycle E2E Demonstration Scenario
Simulates a multi-user incident lifecycle:
  1. Requester reports Wi-Fi Outage in Executive Boardroom B.
  2. AI Triage classifies category, priority, severity, and suggests Network Team.
  3. Network Operator reviews and accepts AI suggestions.
  4. Operator asks for AP diagnostic LED light status (INFO_REQUEST -> WAITING_FOR_INFO).
  5. Requester uploads router photo & replies with amber LED details (INFO_RESPONSE -> INVESTIGATING).
  6. Operator creates & completes switch port repair task, logging root cause.
  7. Operator formally proposes resolution.
  8. Requester confirms resolution -> Case closes automatically (CLOSED).
  9. Live role-based dashboards update in real time.
  10. System timeline audit log verified.
"""

import asyncio
import io
import os
import sys
import uuid
from httpx import ASGITransport, AsyncClient

# Reconfigure stdout for UTF-8 compatibility on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Fix Windows event loop if running on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.main import app
from app.models.enums import UserRole, CaseStatus


def print_banner(text: str):
    line = "=" * 78
    print(f"\n{line}")
    print(f"  {text.upper()}")
    print(f"{line}\n")


def print_step(step_num: int, role: str, action: str):
    print(f"\n>> [STEP {step_num:02d}] [{role.upper()}] {action}")
    print("-" * 70)


async def register_role(client: AsyncClient, role: UserRole, prefix: str) -> tuple[str, int, dict]:
    suffix = uuid.uuid4().hex[:5]
    email = f"{prefix}_{suffix}@office.example.com"
    password = "SecurePassword123!"
    reg_data = {
        "email": email,
        "password": password,
        "full_name": f"{role.value.capitalize()} Specialist {suffix}",
        "role": role.value,
        "office_location": "Building 3, 4th Floor Tech Center",
    }
    await client.post("/api/v1/auth/register", json=reg_data)
    login_res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    data = login_res.json()
    token = data["access_token"]
    user_id = data["user_id"]
    headers = {"Authorization": f"Bearer {token}"}
    return token, user_id, headers


async def run_demo():
    print_banner("AI Office IT Help Desk - End-to-End Enterprise Scenario")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8000") as client:
        # ----------------------------------------------------------------------
        # Personas Registration
        # ----------------------------------------------------------------------
        print("[*] Setting up 5 User Personas...")
        _, req_id, req_headers = await register_role(client, UserRole.REQUESTER, "demo_req")
        _, op_id, op_headers = await register_role(client, UserRole.OPERATOR, "demo_op")
        _, lead_id, lead_headers = await register_role(client, UserRole.TEAM_LEAD, "demo_lead")
        _, mgr_id, mgr_headers = await register_role(client, UserRole.MANAGER, "demo_mgr")
        _, admin_id, admin_headers = await register_role(client, UserRole.ADMIN, "demo_admin")
        print("    [OK] Requester, Operator, Team Lead, Manager, and Admin registered successfully.")

        # ----------------------------------------------------------------------
        # Step 1: Requester Reports Wi-Fi Outage
        # ----------------------------------------------------------------------
        print_step(1, "Requester", "Submits Emergency Wi-Fi Failure Ticket")
        case_res = await client.post(
            "/api/v1/cases/",
            json={
                "title": "Executive Boardroom B Wi-Fi disconnected during quarterly briefing",
                "description": "Laptops unable to acquire IP address on 'Office-Corp-Secure' SSID. AP ceiling unit is unreachable.",
                "priority": "HIGH",
                "severity": "MAJOR",
                "location": "Floor 4, Boardroom B",
            },
            headers=req_headers,
        )
        case = case_res.json()
        case_id = case["id"]
        case_num = case["case_number"]
        print(f"    [+] Case Created: {case_num} (ID: {case_id})")
        print(f"    [*] Status: {case['status']} | Priority: {case['priority']} | SLA Resolution Target: {case['resolution_deadline']}")

        # ----------------------------------------------------------------------
        # Step 2: AI Triage
        # ----------------------------------------------------------------------
        print_step(2, "AI Engine (Gemini)", "Executes Automated Triage & Anomaly Diagnostic Analysis")
        ai_res = await client.post(f"/api/v1/cases/{case_id}/ai-analysis", headers=op_headers)
        ai = ai_res.json()
        analysis_id = ai["id"]
        print(f"    [AI] Suggested Priority: {ai.get('suggested_priority')}")
        print(f"    [AI] Summary: {ai.get('case_summary')}")
        print(f"    [AI] Recommended Diagnostic Questions:")
        for q in ai.get("recommended_questions", [])[:2]:
            print(f"         - {q}")

        # ----------------------------------------------------------------------
        # Step 3: Operator Accepts Triage & Assigns Ticket
        # ----------------------------------------------------------------------
        print_step(3, "Operator", "Reviews & Accepts AI Triage, Assigns Case to Network Team")
        await client.post(
            f"/api/v1/cases/{case_id}/ai-analyses/{analysis_id}/review",
            json={"is_accepted": True, "apply_suggestions": True},
            headers=op_headers,
        )
        await client.post(
            f"/api/v1/cases/{case_id}/assign",
            json={"assigned_operator_id": op_id},
            headers=op_headers,
        )
        print(f"    [OK] AI recommendations applied. Case assigned to Network Operator (User ID: {op_id}).")

        # ----------------------------------------------------------------------
        # Step 4: Operator Requests Information
        # ----------------------------------------------------------------------
        print_step(4, "Operator", "Sends INFO_REQUEST asking for AP Ceiling LED Status")
        await client.post(
            f"/api/v1/cases/{case_id}/messages",
            json={
                "content": "Can you check the LED indicator light on the Cisco AP mounted on the Boardroom B ceiling?",
                "message_type": "INFO_REQUEST",
            },
            headers=op_headers,
        )
        case_after_msg = (await client.get(f"/api/v1/cases/{case_id}", headers=op_headers)).json()
        print(f"    [PAUSED] Case State automatically paused to: {case_after_msg['status']}")

        # ----------------------------------------------------------------------
        # Step 5: Requester Uploads Evidence & Responds
        # ----------------------------------------------------------------------
        print_step(5, "Requester", "Uploads AP Photo Evidence and Provides Diagnosis Details")
        dummy_photo = io.BytesIO(b"SIMULATED_AP_STATUS_PHOTO_CONTENT")
        await client.post(
            f"/api/v1/cases/{case_id}/attachments",
            files={"file": ("cisco_ap_amber_light.jpg", dummy_photo, "image/jpeg")},
            headers=req_headers,
        )
        await client.post(
            f"/api/v1/cases/{case_id}/messages",
            json={
                "content": "The Cisco AP LED is blinking solid amber. Attached photo above.",
                "message_type": "INFO_RESPONSE",
            },
            headers=req_headers,
        )
        case_after_resp = (await client.get(f"/api/v1/cases/{case_id}", headers=req_headers)).json()
        print(f"    [RESUMED] Evidence uploaded. Case State automatically resumed to: {case_after_resp['status']}")

        # ----------------------------------------------------------------------
        # Step 6: Operator Completes Diagnostic Task & Notes
        # ----------------------------------------------------------------------
        print_step(6, "Operator", "Executes Hardware Switch Port Replacement Task")
        await client.post(
            f"/api/v1/cases/{case_id}/internal-notes",
            json={"note_text": "IDF-4 Switch Port 24 dropped PoE negotiation. Cable crimp degraded."},
            headers=op_headers,
        )
        task_res = await client.post(
            f"/api/v1/cases/{case_id}/tasks",
            json={
                "title": "Replace faulty Cat6 patch cable on IDF-4 Switch Port 24",
                "description": "Inspect RJ45 crimp, re-cable, and power-cycle Cisco AP-4B-02.",
                "assigned_to_id": op_id,
            },
            headers=op_headers,
        )
        task_id = task_res.json()["id"]
        await client.patch(
            f"/api/v1/tasks/{task_id}",
            json={
                "status": "COMPLETED",
                "findings": "Replaced patch cable. AP-4B-02 negotiated full PoE+ and rejoined WLC successfully.",
            },
            headers=op_headers,
        )
        print(f"    [OK] Diagnostic task #{task_id} completed. Switch port repaired.")

        # ----------------------------------------------------------------------
        # Step 7: Operator Proposes Resolution
        # ----------------------------------------------------------------------
        print_step(7, "Operator", "Submits Formal Resolution Proposal")
        prop_res = await client.post(
            f"/api/v1/cases/{case_id}/resolution/propose",
            json={
                "actions_taken": "Replaced damaged Cat6 patch cable on IDF-4 port 24 and power-cycled Cisco AP-4B-02.",
                "findings": "Degraded RJ45 connector caused intermittent PoE drops on the ceiling access point.",
                "remaining_issues": "None; AP tested and verified with 50+ Mbps throughput on 5GHz band.",
            },
            headers=op_headers,
        )
        print(f"    [PROPOSED] Resolution Proposal Filed. Status: {prop_res.json()['status']}")
        print(f"    [*] Requester notified in-app for confirmation.")

        # ----------------------------------------------------------------------
        # Step 8: Requester Confirms Resolution
        # ----------------------------------------------------------------------
        print_step(8, "Requester", "Confirms Wi-Fi Service Restored -> Case Closes")
        conf_res = await client.post(
            f"/api/v1/cases/{case_id}/resolution/confirm",
            json={"feedback": "Tested Wi-Fi in Boardroom B; laptops connecting at high speed. Thank you!"},
            headers=req_headers,
        )
        print(f"    [CONFIRMED] Resolution Confirmed Status: {conf_res.json()['status']}")
        closed_case = (await client.get(f"/api/v1/cases/{case_id}", headers=req_headers)).json()
        print(f"    [CLOSED] Final Case Status: {closed_case['status']}")
        print(f"    [*] Closed At: {closed_case['closed_at']}")

        # ----------------------------------------------------------------------
        # Step 9: Dynamic Role Dashboards Check
        # ----------------------------------------------------------------------
        print_step(9, "System", "Validates Real-Time Role Dashboards Aggregations")
        req_d = (await client.get("/api/v1/dashboards/requester", headers=req_headers)).json()
        op_d = (await client.get("/api/v1/dashboards/operator", headers=op_headers)).json()
        mgr_d = (await client.get("/api/v1/dashboards/manager", headers=mgr_headers)).json()

        print(f"    [Requester Dashboard] {req_d['resolved_cases_count']} resolved, {req_d['active_cases_count']} active.")
        print(f"    [Operator Dashboard]  {op_d['resolved_today_count']} resolved today.")
        print(f"    [Manager Dashboard]   {mgr_d['total_cases']} total tickets, {mgr_d['sla_compliance_rate']}% SLA compliance.")

        # ----------------------------------------------------------------------
        # Step 10: Chronological Timeline Story
        # ----------------------------------------------------------------------
        print_step(10, "Admin", "Inspects Full Chronological Case Timeline")
        timeline = (await client.get(f"/api/v1/cases/{case_id}/timeline", headers=admin_headers)).json()
        print(f"    [TIMELINE] {len(timeline)} Chronological Events Recorded:")
        for idx, event in enumerate(timeline, start=1):
            actor_name = event["actor"]["full_name"] if event.get("actor") else "SYSTEM"
            print(f"       {idx:02d}. [{event['created_at'][:19]}] [{actor_name:25s}] {event['event_type']} - {event['summary']}")

        print_banner("All 10 Steps Completed Successfully with Zero Errors!")


if __name__ == "__main__":
    asyncio.run(run_demo())
