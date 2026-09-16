import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.enums import UserRole, CasePriority, CaseSeverity
from app.services.ai_service import ai_service


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


async def create_sample_case(client: AsyncClient, token: str, title: str, description: str) -> int:
    headers = {"Authorization": f"Bearer {token}"}
    res = await client.post(
        "/api/v1/cases/",
        json={
            "title": title,
            "description": description,
            "office_location": "Floor 4, Conference Room B",
            "priority": "MEDIUM",
            "severity": "MODERATE",
        },
        headers=headers,
    )
    assert res.status_code == 201
    return res.json()["id"]


@pytest.mark.asyncio
async def test_ai_triage_success_gate():
    """Gate 1: Successful AI response generates valid AICaseAnalysis."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_token, _ = await get_auth_token(client, "req_ai1", UserRole.REQUESTER)
        op_token, _ = await get_auth_token(client, "op_ai1", UserRole.OPERATOR)
        op_headers = {"Authorization": f"Bearer {op_token}"}

        case_id = await create_sample_case(
            client,
            req_token,
            "Office Wi-Fi drops every 5 minutes",
            "Cannot stay connected to corporate Wi-Fi SSID on floor 4.",
        )

        mock_gemini_json = {
            "suggested_category_name": "Wi-Fi / Network Issue",
            "suggested_priority": "HIGH",
            "suggested_severity": "MAJOR",
            "suggested_team_name": "Network Support",
            "missing_information": ["Device MAC address", "Signal strength in dBm"],
            "recommended_questions": ["Does the issue occur on other floors?", "Have you forgotten and re-added the Wi-Fi network?"],
            "related_case_numbers": [],
            "recommended_next_action": "Check AP controller channel saturation on 4th floor.",
            "case_summary": "Requester is facing unstable wireless connectivity in meeting area.",
            "risk_insight": "May interrupt client video conference.",
            "confidence_score": "0.95",
        }

        mock_response = MagicMock()
        mock_response.text = json.dumps(mock_gemini_json)

        # Mock the Gemini client call
        with patch.object(ai_service, "is_available", True), \
             patch.object(ai_service, "_client") as mock_client:
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

            res = await client.post(f"/api/v1/cases/{case_id}/ai-analysis", headers=op_headers)
            assert res.status_code == 201
            data = res.json()

            assert data["case_id"] == case_id
            assert data["suggested_priority"] == "HIGH"
            assert data["suggested_severity"] == "MAJOR"
            assert data["suggested_category_name"] == "Wi-Fi / Network Issue"
            assert data["suggested_team_name"] == "Network Support"
            assert len(data["missing_information"]) == 2
            assert len(data["recommended_questions"]) == 2
            assert data["confidence_score"] == "0.95"
            assert data["is_accepted"] is False
            assert data["is_overridden"] is False


@pytest.mark.asyncio
async def test_ai_invalid_response_resilience_gate():
    """Gate 2: Malformed or non-JSON Gemini output triggers rule-based fallback without crashing."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_token, _ = await get_auth_token(client, "req_ai2", UserRole.REQUESTER)
        op_token, _ = await get_auth_token(client, "op_ai2", UserRole.OPERATOR)
        op_headers = {"Authorization": f"Bearer {op_token}"}

        case_id = await create_sample_case(
            client,
            req_token,
            "Laptop battery drains in 15 minutes",
            "Lenovo ThinkPad battery dies almost instantly after unplugging charger.",
        )

        mock_response = MagicMock()
        mock_response.text = "I apologize, but I am unable to process this request properly at this moment."

        with patch.object(ai_service, "is_available", True), \
             patch.object(ai_service, "_client") as mock_client:
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

            res = await client.post(f"/api/v1/cases/{case_id}/ai-analysis", headers=op_headers)
            assert res.status_code == 201
            data = res.json()

            # Verify rule-based fallback activated cleanly
            assert data["suggested_category_name"] == "Laptop / PC Hardware Problem"
            assert data["suggested_team_name"] == "Hardware Support"
            assert data["suggested_priority"] == "HIGH"
            assert "0.78" in data["confidence_score"]
            assert len(data["recommended_questions"]) > 0


@pytest.mark.asyncio
async def test_ai_timeout_resilience_gate():
    """Gate 3: Gemini API timeout triggers rule-based fallback without blocking or failing."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_token, _ = await get_auth_token(client, "req_ai3", UserRole.REQUESTER)
        op_token, _ = await get_auth_token(client, "op_ai3", UserRole.OPERATOR)
        op_headers = {"Authorization": f"Bearer {op_token}"}

        case_id = await create_sample_case(
            client,
            req_token,
            "Office printer paper jam in HR department",
            "HP LaserJet printer showing error 13.00 paper jam in tray 2.",
        )

        with patch.object(ai_service, "is_available", True), \
             patch.object(ai_service, "_client") as mock_client:
            mock_client.aio.models.generate_content = AsyncMock(side_effect=asyncio.TimeoutError())

            res = await client.post(f"/api/v1/cases/{case_id}/ai-analysis", headers=op_headers)
            assert res.status_code == 201
            data = res.json()

            # Verify rule-based fallback activated on timeout
            assert data["suggested_category_name"] == "Printer & Scanner Issue"
            assert data["suggested_team_name"] == "Hardware Support"
            assert data["suggested_priority"] == "LOW"


@pytest.mark.asyncio
async def test_ai_unavailable_resilience_gate():
    """Gate 4: Gemini client completely offline or raises network error; ticketing operations unaffected."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_token, _ = await get_auth_token(client, "req_ai4", UserRole.REQUESTER)
        op_token, _ = await get_auth_token(client, "op_ai4", UserRole.OPERATOR)
        op_headers = {"Authorization": f"Bearer {op_token}"}

        # 1. Normal case creation still works 100%
        case_id = await create_sample_case(
            client,
            req_token,
            "Cannot access company VPN from home",
            "Cisco AnyConnect gives authentication failed error code 403.",
        )

        with patch.object(ai_service, "is_available", False):
            res = await client.post(f"/api/v1/cases/{case_id}/ai-analysis", headers=op_headers)
            assert res.status_code == 201
            data = res.json()

            assert data["suggested_category_name"] == "VPN / Remote Access"
            assert data["suggested_team_name"] == "Network Support"
            assert data["suggested_priority"] == "HIGH"


@pytest.mark.asyncio
async def test_human_in_the_loop_accept_and_override():
    """Human-in-the-loop: Staff can Accept (applying recommendations) or Override (logging reason)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_token, _ = await get_auth_token(client, "req_ai5", UserRole.REQUESTER)
        op_token, op_id = await get_auth_token(client, "op_ai5", UserRole.OPERATOR)
        op_headers = {"Authorization": f"Bearer {op_token}"}

        case_id = await create_sample_case(
            client,
            req_token,
            "Outlook email login prompt loops continuously",
            "Keeps prompting for Microsoft 365 password.",
        )

        # 1. Trigger analysis
        res = await client.post(f"/api/v1/cases/{case_id}/ai-analysis", headers=op_headers)
        assert res.status_code == 201
        analysis_id = res.json()["id"]

        # 2. Accept recommendations with apply_changes=True
        accept_payload = {
            "is_accepted": True,
            "is_overridden": False,
            "apply_changes": True,
        }
        accept_res = await client.post(
            f"/api/v1/cases/{case_id}/ai-analyses/{analysis_id}/review",
            json=accept_payload,
            headers=op_headers,
        )
        assert accept_res.status_code == 200
        acc_data = accept_res.json()
        assert acc_data["is_accepted"] is True
        assert acc_data["is_overridden"] is False
        assert acc_data["reviewed_by_id"] == op_id

        # Verify case priority and category were updated on the case
        case_res = await client.get(f"/api/v1/cases/{case_id}", headers=op_headers)
        assert case_res.status_code == 200
        case_data = case_res.json()
        assert case_data["priority"] == acc_data["suggested_priority"]

        # 3. Override recommendations with an audit reason
        override_payload = {
            "is_accepted": False,
            "is_overridden": True,
            "override_reason": "Executive VIP user affected; overriding to Critical severity.",
        }
        over_res = await client.post(
            f"/api/v1/cases/{case_id}/ai-analyses/{analysis_id}/review",
            json=override_payload,
            headers=op_headers,
        )
        assert over_res.status_code == 200
        over_data = over_res.json()
        assert over_data["is_overridden"] is True
        assert over_data["is_accepted"] is False
        assert over_data["override_reason"] == override_payload["override_reason"]

        # 4. Override without reason returns 400 Bad Request
        bad_res = await client.post(
            f"/api/v1/cases/{case_id}/ai-analyses/{analysis_id}/review",
            json={"is_overridden": True, "override_reason": ""},
            headers=op_headers,
        )
        assert bad_res.status_code == 400

        # 5. List analyses for case
        list_res = await client.get(f"/api/v1/cases/{case_id}/ai-analyses", headers=op_headers)
        assert list_res.status_code == 200
        assert len(list_res.json()) >= 1


@pytest.mark.asyncio
async def test_duplicate_check_and_draft_communication():
    """Tests duplicate detection and communication drafting assistance."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_token, _ = await get_auth_token(client, "req_ai6", UserRole.REQUESTER)
        op_token, _ = await get_auth_token(client, "op_ai6", UserRole.OPERATOR)
        req_headers = {"Authorization": f"Bearer {req_token}"}
        op_headers = {"Authorization": f"Bearer {op_token}"}

        # Create original case
        case_id = await create_sample_case(
            client,
            req_token,
            "Office Wi-Fi router reboot required on 4th floor",
            "Internet dropped across all access points on floor 4.",
        )

        # 1. Check duplicate detection
        dup_res = await client.post(
            "/api/v1/check-duplicates",
            json={
                "title": "Wi-Fi access point not working 4th floor",
                "description": "Cannot connect to internet via office Wi-Fi.",
            },
            headers=req_headers,
        )
        assert dup_res.status_code == 200
        dup_data = dup_res.json()
        assert dup_data["count"] >= 1
        assert any(m["case_id"] == case_id for m in dup_data["potential_duplicates"])

        # 2. Generate communication draft (INFO_REQUEST)
        draft_res = await client.post(
            f"/api/v1/cases/{case_id}/ai-draft",
            json={"draft_type": "INFO_REQUEST", "instructions": "Ask for IP and MAC address"},
            headers=op_headers,
        )
        assert draft_res.status_code == 200
        draft_data = draft_res.json()
        assert draft_data["draft_type"] == "INFO_REQUEST"
        assert len(draft_data["drafted_message"]) > 20
        assert len(draft_data["key_points"]) > 0

        # 3. Requester forbidden from drafting or analyzing
        forbid_res = await client.post(
            f"/api/v1/cases/{case_id}/ai-draft",
            json={"draft_type": "INFO_REQUEST"},
            headers=req_headers,
        )
        assert forbid_res.status_code == 403
