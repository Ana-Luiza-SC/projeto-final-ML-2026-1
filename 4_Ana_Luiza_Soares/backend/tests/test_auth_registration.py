import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.auth import ensure_user, verify_password
from app.database import SessionLocal, User
from app.main import REGISTRATION_MAX_BODY_BYTES, app

TEST_EMAILS = [
    "lulu.registration@example.com",
    "case.registration@example.com",
    "login.registration@example.com",
    "demo.registration@example.com",
]


@pytest.fixture(autouse=True)
def registration_environment(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", "registration-test-secret")
    monkeypatch.setenv("AUTH_REQUIRED_IN_TESTS", "true")
    with SessionLocal() as session:
        session.execute(delete(User).where(User.email.in_(TEST_EMAILS)))
        session.commit()
    yield
    with SessionLocal() as session:
        session.execute(delete(User).where(User.email.in_(TEST_EMAILS)))
        session.commit()


@pytest.fixture
def client():
    return TestClient(app)


def valid_payload(**overrides):
    return {
        "name": "Lulu",
        "email": "lulu.registration@example.com",
        "password": "Lulu123456",
        "accepted_terms": True,
        **overrides,
    }


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "YeS", "on"])
def test_registration_status_enabled(client, monkeypatch, value):
    monkeypatch.setenv("ALLOW_REGISTRATION", value)

    response = client.get("/api/auth/registration-status")

    assert response.status_code == 200
    assert response.json() == {"enabled": True}


@pytest.mark.parametrize("value", ["false", "0", "no", "off", "", "unexpected"])
def test_registration_status_disabled(client, monkeypatch, value):
    monkeypatch.setenv("ALLOW_REGISTRATION", value)

    response = client.get("/api/auth/registration-status")

    assert response.status_code == 200
    assert response.json() == {"enabled": False}


def test_successful_registration_authenticates_and_hashes_password(
    client,
    monkeypatch,
):
    monkeypatch.setenv("ALLOW_REGISTRATION", "true")

    response = client.post("/api/auth/register", json=valid_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "lulu.registration@example.com"
    assert body["user"]["display_name"] == "Lulu"
    assert set(body["user"]) == {"id", "email", "display_name"}
    serialized = json.dumps(body)
    assert "Lulu123456" not in serialized
    assert "password" not in serialized.casefold()
    with SessionLocal() as session:
        user = session.query(User).filter_by(
            email="lulu.registration@example.com"
        ).one()
        assert user.is_active is True
        assert user.password_hash != "Lulu123456"
        assert verify_password("Lulu123456", user.password_hash)


def test_disabled_registration_returns_403_without_creating_user(
    client,
    monkeypatch,
):
    monkeypatch.setenv("ALLOW_REGISTRATION", "false")

    response = client.post("/api/auth/register", json=valid_payload())

    assert response.status_code == 403
    assert response.json() == {
        "detail": "O cadastro público não está disponível neste ambiente."
    }
    with SessionLocal() as session:
        assert (
            session.query(User)
            .filter_by(email="lulu.registration@example.com")
            .one_or_none()
            is None
        )


def test_duplicate_and_case_insensitive_duplicate_return_409(
    client,
    monkeypatch,
):
    monkeypatch.setenv("ALLOW_REGISTRATION", "true")
    first = client.post(
        "/api/auth/register",
        json=valid_payload(email="case.registration@example.com"),
    )
    duplicate = client.post(
        "/api/auth/register",
        json=valid_payload(email="  CASE.REGISTRATION@EXAMPLE.COM  "),
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "detail": "Já existe uma conta com este e-mail."
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("password", "lowercase1"),
        ("password", "UPPERCASE1"),
        ("password", "NoNumberHere"),
        ("password", "Short1A"),
        ("email", "not-an-email"),
        ("accepted_terms", False),
    ],
)
def test_invalid_registration_fields_are_rejected(
    client,
    monkeypatch,
    field,
    value,
):
    monkeypatch.setenv("ALLOW_REGISTRATION", "true")

    response = client.post(
        "/api/auth/register",
        json=valid_payload(**{field: value}),
    )

    assert response.status_code == 422
    if field == "password":
        assert value not in response.text


def test_registered_user_can_log_in(client, monkeypatch):
    monkeypatch.setenv("ALLOW_REGISTRATION", "true")
    registered = client.post(
        "/api/auth/register",
        json=valid_payload(
            email="login.registration@example.com",
            name="Login User",
        ),
    )
    login = client.post(
        "/api/auth/login",
        json={
            "email": " LOGIN.REGISTRATION@EXAMPLE.COM ",
            "password": "Lulu123456",
        },
    )

    assert registered.status_code == 201
    assert login.status_code == 200
    assert login.json()["user"]["id"] == registered.json()["user"]["id"]
    assert login.json()["user"]["display_name"] == "Login User"


def test_registration_cannot_overwrite_configured_user(client, monkeypatch):
    monkeypatch.setenv("ALLOW_REGISTRATION", "true")
    demo = ensure_user(
        "demo.registration@example.com",
        "Original123",
        user_id="demo-registration-user",
    )

    response = client.post(
        "/api/auth/register",
        json=valid_payload(
            email="demo.registration@example.com",
            password="Replacement123",
        ),
    )

    assert response.status_code == 409
    with SessionLocal() as session:
        persisted = session.get(User, demo.id)
        assert verify_password("Original123", persisted.password_hash)
        assert not verify_password("Replacement123", persisted.password_hash)


def test_registration_rejects_extra_permissions_wrong_content_type_and_size(
    client,
    monkeypatch,
):
    monkeypatch.setenv("ALLOW_REGISTRATION", "true")
    extra = client.post(
        "/api/auth/register",
        json=valid_payload(role="admin", is_active=False),
    )
    wrong_type = client.post(
        "/api/auth/register",
        content="name=Lulu",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    oversized = client.post(
        "/api/auth/register",
        content=b"{" + b" " * REGISTRATION_MAX_BODY_BYTES + b"}",
        headers={"Content-Type": "application/json"},
    )

    assert extra.status_code == 422
    assert wrong_type.status_code == 415
    assert oversized.status_code == 413
