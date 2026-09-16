import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.models.enums import UserRole


@pytest.mark.asyncio
async def test_auth_registration_and_login():
    unique_suffix = uuid.uuid4().hex[:8]
    test_email = f"employee_{unique_suffix}@example.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Register a new user
        reg_payload = {
            "email": test_email,
            "password": "SecurePassword123!",
            "full_name": "Suresh Patil",
            "role": "REQUESTER",
            "department": "Sales",
            "office_location": "Floor 2, Mumbai Office",
            "phone_number": "+91 9876543210",
        }
        res = await client.post("/api/v1/auth/register", json=reg_payload)
        assert res.status_code == 201
        data = res.json()
        assert data["email"] == test_email
        assert data["full_name"] == "Suresh Patil"
        assert data["role"] == "REQUESTER"
        assert "hashed_password" not in data
        assert data["is_active"] is True

        # 2. Duplicate registration should be rejected
        res_dup = await client.post("/api/v1/auth/register", json=reg_payload)
        assert res_dup.status_code == 400
        assert "already exists" in res_dup.json()["detail"]

        # 3. Weak password should be rejected (< 6 chars)
        weak_payload = {
            "email": f"weak_{unique_suffix}@example.com",
            "password": "123",
            "full_name": "Weak User",
        }
        res_weak = await client.post("/api/v1/auth/register", json=weak_payload)
        assert res_weak.status_code == 422

        # 4. Login with correct credentials
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": test_email, "password": "SecurePassword123!"},
        )
        assert login_res.status_code == 200
        token_data = login_res.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        assert token_data["role"] == "REQUESTER"
        token = token_data["access_token"]

        # 5. Login with invalid password
        bad_login = await client.post(
            "/api/v1/auth/login",
            json={"email": test_email, "password": "WrongPassword!"},
        )
        assert bad_login.status_code == 401

        # 6. Profile /me with token
        headers = {"Authorization": f"Bearer {token}"}
        me_res = await client.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["email"] == test_email


        # 7. Profile /me without token
        unauth_res = await client.get("/api/v1/auth/me")
        assert unauth_res.status_code == 401

        # 8. Profile /me with invalid token
        invalid_res = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer fake.tampered.token"})
        assert invalid_res.status_code == 401


@pytest.mark.asyncio
async def test_rbac_all_five_roles():
    """Verify that backend RBAC strictly forbids unauthorized access across all 5 roles."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        roles_to_test = [
            ("requester_rbac@test.com", UserRole.REQUESTER),
            ("operator_rbac@test.com", UserRole.OPERATOR),
            ("teamlead_rbac@test.com", UserRole.TEAM_LEAD),
            ("manager_rbac@test.com", UserRole.MANAGER),
            ("admin_rbac@test.com", UserRole.ADMIN),
        ]

        tokens = {}
        for email, role in roles_to_test:
            reg_payload = {
                "email": email,
                "password": "Password123!",
                "full_name": f"Test {role.value}",
                "role": role.value,
            }
            # Register or ignore if already exists from prior run
            await client.post("/api/v1/auth/register", json=reg_payload)

            login_res = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "Password123!"},
            )
            assert login_res.status_code == 200
            tokens[role] = login_res.json()["access_token"]

        # Verify REQUESTER:
        req_h = {"Authorization": f"Bearer {tokens[UserRole.REQUESTER]}"}
        # Can access requester endpoint
        r = await client.get("/api/v1/auth/test/requester", headers=req_h)
        assert r.status_code == 200
        # CANNOT access operator, team-lead, manager, or admin endpoints (must return 403 Forbidden)
        assert (await client.get("/api/v1/auth/test/operator", headers=req_h)).status_code == 403
        assert (await client.get("/api/v1/auth/test/admin", headers=req_h)).status_code == 403

        # Verify OPERATOR:
        op_h = {"Authorization": f"Bearer {tokens[UserRole.OPERATOR]}"}
        assert (await client.get("/api/v1/auth/test/operator", headers=op_h)).status_code == 200
        assert (await client.get("/api/v1/auth/test/admin", headers=op_h)).status_code == 403

        # Verify TEAM_LEAD:
        tl_h = {"Authorization": f"Bearer {tokens[UserRole.TEAM_LEAD]}"}
        assert (await client.get("/api/v1/auth/test/operator", headers=tl_h)).status_code == 200
        assert (await client.get("/api/v1/auth/test/team-lead", headers=tl_h)).status_code == 200
        assert (await client.get("/api/v1/auth/test/admin", headers=tl_h)).status_code == 403

        # Verify MANAGER:
        mgr_h = {"Authorization": f"Bearer {tokens[UserRole.MANAGER]}"}
        assert (await client.get("/api/v1/auth/test/operator", headers=mgr_h)).status_code == 200
        assert (await client.get("/api/v1/auth/test/manager", headers=mgr_h)).status_code == 200
        assert (await client.get("/api/v1/auth/test/admin", headers=mgr_h)).status_code == 403

        # Verify ADMIN:
        adm_h = {"Authorization": f"Bearer {tokens[UserRole.ADMIN]}"}
        assert (await client.get("/api/v1/auth/test/operator", headers=adm_h)).status_code == 200
        assert (await client.get("/api/v1/auth/test/admin", headers=adm_h)).status_code == 200
