import io
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.models.enums import UserRole, CaseStatus, MessageType, TaskStatus


async def get_auth_token(client: AsyncClient, email_prefix: str, role: UserRole) -> tuple[str, int]:
    unique_suffix = uuid.uuid4().hex[:6]
    email = f"{email_prefix}_{unique_suffix}@example.com"
    reg_payload = {
        "email": email,
        "password": "Password123!",
        "full_name": f"User {role.value}",
        "role": role.value,
        "office_location": "Floor 2, Mumbai Office",
    }
    await client.post("/api/v1/auth/register", json=reg_payload)
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    data = login_res.json()
    return data["access_token"], data["user_id"]


@pytest.mark.asyncio
async def test_evidence_upload_and_secure_download():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_token, req_id = await get_auth_token(client, "req_file", UserRole.REQUESTER)
        other_req_token, _ = await get_auth_token(client, "other_file", UserRole.REQUESTER)

        req_h = {"Authorization": f"Bearer {req_token}"}
        other_h = {"Authorization": f"Bearer {other_req_token}"}

        # 1. Create a case
        c_res = await client.post(
            "/api/v1/cases/",
            json={"title": "Error screen on boot", "description": "BSOD error 0x0000007E."},
            headers=req_h,
        )
        case_id = c_res.json()["id"]

        # 2. Upload screenshot evidence
        fake_image_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        files = {"file": ("blue_screen.png", io.BytesIO(fake_image_bytes), "image/png")}
        upload_res = await client.post(
            f"/api/v1/cases/{case_id}/attachments",
            files=files,
            headers=req_h,
        )
        assert upload_res.status_code == 201
        att_data = upload_res.json()
        assert att_data["file_name"] == "blue_screen.png"
        att_id = att_data["id"]

        # 3. Authorized download by requester
        dl_res = await client.get(f"/api/v1/attachments/{att_id}/download", headers=req_h)
        assert dl_res.status_code == 200
        assert dl_res.content == fake_image_bytes

        # 4. Unauthorized requester attempting to download -> 403 Forbidden
        bad_dl = await client.get(f"/api/v1/attachments/{att_id}/download", headers=other_h)
        assert bad_dl.status_code == 403


@pytest.mark.asyncio
async def test_case_communication_and_info_requests():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_token, req_id = await get_auth_token(client, "req_msg", UserRole.REQUESTER)
        op_token, op_id = await get_auth_token(client, "op_msg", UserRole.OPERATOR)

        req_h = {"Authorization": f"Bearer {req_token}"}
        op_h = {"Authorization": f"Bearer {op_token}"}

        # 1. Create case
        c_res = await client.post(
            "/api/v1/cases/",
            json={"title": "Slow internet in conference room", "description": "Cannot stream video calls."},
            headers=req_h,
        )
        case_id = c_res.json()["id"]

        # 2. Operator sends an INFO_REQUEST
        info_req_res = await client.post(
            f"/api/v1/cases/{case_id}/messages",
            json={
                "content": "Which conference room number is this? Also are you on 5GHz Wi-Fi?",
                "message_type": "INFO_REQUEST",
            },
            headers=op_h,
        )
        assert info_req_res.status_code == 201
        assert info_req_res.json()["message_type"] == "INFO_REQUEST"

        # Verify case status auto-transitions to WAITING_FOR_INFO
        case_check = await client.get(f"/api/v1/cases/{case_id}", headers=op_h)
        assert case_check.json()["status"] == "WAITING_FOR_INFO"

        # 3. Requester sends INFO_RESPONSE
        info_resp_res = await client.post(
            f"/api/v1/cases/{case_id}/messages",
            json={
                "content": "It is Conference Room B (Floor 2). Yes, connected to Corp-5G.",
                "message_type": "INFO_RESPONSE",
            },
            headers=req_h,
        )
        assert info_resp_res.status_code == 201

        # Verify case status automatically resumed
        case_resumed = await client.get(f"/api/v1/cases/{case_id}", headers=op_h)
        assert case_resumed.json()["status"] in ["UNDERSTOOD", "INVESTIGATING"]

        # 4. Verify messages are listed
        list_res = await client.get(f"/api/v1/cases/{case_id}/messages", headers=req_h)
        assert list_res.status_code == 200
        assert len(list_res.json()) >= 2


@pytest.mark.asyncio
async def test_internal_notes_staff_protection():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_token, _ = await get_auth_token(client, "req_notes", UserRole.REQUESTER)
        op_token, _ = await get_auth_token(client, "op_notes", UserRole.OPERATOR)

        req_h = {"Authorization": f"Bearer {req_token}"}
        op_h = {"Authorization": f"Bearer {op_token}"}

        # Create case
        c_res = await client.post(
            "/api/v1/cases/",
            json={"title": "Outlook crash on launch", "description": "Crashes immediately after opening."},
            headers=req_h,
        )
        case_id = c_res.json()["id"]

        # Operator adds internal staff note
        note_res = await client.post(
            f"/api/v1/cases/{case_id}/internal-notes",
            json={"note_text": "Staff private log: Outlook profile registry corrupt. Need to rebuild OST."},
            headers=op_h,
        )
        assert note_res.status_code == 201
        assert "registry corrupt" in note_res.json()["note_text"]

        # Staff can list notes
        op_notes = await client.get(f"/api/v1/cases/{case_id}/internal-notes", headers=op_h)
        assert op_notes.status_code == 200
        assert len(op_notes.json()) == 1

        # Requester cannot read internal notes -> 403 Forbidden
        req_read = await client.get(f"/api/v1/cases/{case_id}/internal-notes", headers=req_h)
        assert req_read.status_code == 403

        # Requester cannot post internal notes -> 403 Forbidden
        req_post = await client.post(
            f"/api/v1/cases/{case_id}/internal-notes",
            json={"note_text": "Unauthorized note"},
            headers=req_h,
        )
        assert req_post.status_code == 403


@pytest.mark.asyncio
async def test_case_tasks_and_investigation_records():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_token, _ = await get_auth_token(client, "req_tasks", UserRole.REQUESTER)
        op_token, op_id = await get_auth_token(client, "op_tasks", UserRole.OPERATOR)

        req_h = {"Authorization": f"Bearer {req_token}"}
        op_h = {"Authorization": f"Bearer {op_token}"}

        c_res = await client.post(
            "/api/v1/cases/",
            json={"title": "Network switch failure", "description": "Rack B switch is unpingable."},
            headers=req_h,
        )
        case_id = c_res.json()["id"]

        # 1. Create task
        task_res = await client.post(
            f"/api/v1/cases/{case_id}/tasks",
            json={
                "title": "Verify power supply on Rack B Switch",
                "description": "Check if power LED is amber or green.",
                "assigned_to_id": op_id,
            },
            headers=op_h,
        )
        assert task_res.status_code == 201
        task_id = task_res.json()["id"]
        assert task_res.json()["status"] == "PENDING"

        # 2. Update task to COMPLETED with findings
        up_res = await client.patch(
            f"/api/v1/tasks/{task_id}",
            json={"status": "COMPLETED", "findings": "PSU 1 failed. Swapped to redundant PSU 2. Switch rebooted."},
            headers=op_h,
        )
        assert up_res.status_code == 200
        assert up_res.json()["status"] == "COMPLETED"
        assert up_res.json()["completed_at"] is not None

        # 3. Record full investigation findings
        inv_res = await client.post(
            f"/api/v1/cases/{case_id}/investigations",
            json={
                "observations": "Switch port flapping and redundant PSU was offline.",
                "actions_taken": "Replaced damaged power cord and firmware upgraded to v4.2.1.",
                "findings": "Surge protector tripped on socket A4.",
                "root_cause": "Electrical surge during AC maintenance.",
                "follow_up_required": "Order replacement spare PSU.",
            },
            headers=op_h,
        )
        assert inv_res.status_code == 201
        data = inv_res.json()
        assert data["root_cause"] == "Electrical surge during AC maintenance."

        # 4. List investigations
        inv_list = await client.get(f"/api/v1/cases/{case_id}/investigations", headers=op_h)
        assert inv_list.status_code == 200
        assert len(inv_list.json()) >= 1
