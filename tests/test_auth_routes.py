"""Tests for authentication and subscription routes"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.plan import Plan

client = TestClient(app)


def test_auth_signup_and_login_flow(TestingSessionLocal):
    # Seed FREE plan in test database so signup can associate it
    db = TestingSessionLocal()
    free_plan = Plan(code="FREE", name="Free", price_amount=0, is_active=True)
    db.add(free_plan)
    db.commit()
    db.close()

    # 1. Signup
    signup_payload = {
        "email": "testuser@example.com",
        "username": "testuser",
        "password": "Password123!"
    }
    signup_res = client.post("/api/auth/signup", json=signup_payload)
    assert signup_res.status_code == 200, signup_res.text
    signup_data = signup_res.json()
    assert signup_data["username"] == "testuser"
    assert signup_data["email"] == "testuser@example.com"
    assert signup_data["is_active"] is True

    # 2. Duplicate signup should be rejected
    dup_res = client.post("/api/auth/signup", json=signup_payload)
    assert dup_res.status_code == 400

    # 3. Login with correct password
    login_payload = {
        "username": "testuser",
        "password": "Password123!"
    }
    login_res = client.post("/api/auth/login", json=login_payload)
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 4. Login with wrong password
    bad_login_res = client.post("/api/auth/login", json={"username": "testuser", "password": "wrong"})
    assert bad_login_res.status_code == 401

    # 5. Read /me
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["username"] == "testuser"

    # 6. Get subscriptions
    sub_res = client.get("/api/auth/subscriptions", headers=headers)
    assert sub_res.status_code == 200
    subs = sub_res.json()
    assert len(subs) == 1
    assert subs[0]["type"] == "free"
    assert subs[0]["is_active"] is True

    # 7. Get entitlements
    ent_res = client.get("/api/auth/entitlements", headers=headers)
    assert ent_res.status_code == 200
    ent_data = ent_res.json()
    assert ent_data["plan"]["code"] == "FREE"
    assert ent_data["is_free_fallback"] is False
