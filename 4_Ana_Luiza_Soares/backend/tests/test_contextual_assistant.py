from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import storage
from app.auth import create_token, ensure_user
from app.database import current_user_id
from app.main import app
from app.services.study_method_catalog import (
    load_study_method_catalog,
    recommend_study_methods,
)


@pytest.fixture(autouse=True)
def clear_state(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", "assistant-test-secret")
    for collection in [storage.DISCIPLINES, storage.ASSESSMENTS, storage.EVENTS]:
        collection.clear()
    storage.STUDY_PLAN_PREVIEWS.clear()
    storage.ASSISTANT_ACTIONS.clear()
    yield
    for collection in [storage.DISCIPLINES, storage.ASSESSMENTS, storage.EVENTS]:
        collection.clear()
    storage.STUDY_PLAN_PREVIEWS.clear()
    storage.ASSISTANT_ACTIONS.clear()


@pytest.fixture
def client():
    return TestClient(app)


def _headers(user):
    return {"Authorization": f"Bearer {create_token(user)}"}


def _preview(client, headers=None):
    discipline = client.post(
        "/api/disciplines",
        json={
            "code": "CTX001",
            "name": "Programação aplicada",
            "workload_hours": 60,
        },
        headers=headers,
    ).json()
    client.post(
        f"/api/disciplines/{discipline['id']}/assessments",
        json={
            "name": "Projeto",
            "date": "2026-07-17",
            "weight": 40,
            "status": "planned",
        },
        headers=headers,
    )
    preview = client.post(
        "/api/study-plans/weekly-preview",
        json={
            "week_start": "2026-07-13",
            "windows": [
                {
                    "weekday": "wednesday",
                    "start_time": "18:00",
                    "end_time": "20:00",
                }
            ],
        },
        headers=headers,
    )
    assert preview.status_code == 200, preview.text
    return discipline, preview.json()


def test_catalog_uses_canonical_json_and_limits_recommendations():
    catalog = load_study_method_catalog()
    result = recommend_study_methods("programming", 90)

    assert catalog["canonical_ingestion_source"] == "study_methods.json"
    assert catalog["ingestion_policy"]["embed_json"] is True
    assert catalog["ingestion_policy"]["embed_pdf"] is False
    assert result["catalog_version"] == catalog["schema_version"]
    assert 1 <= len(result["methods"]) <= 3
    pomodoro = next(
        method for method in catalog["methods"] if method["id"] == "pomodoro"
    )
    assert pomodoro["category"] == "time_management_format"


def test_method_response_has_structured_catalog_evidence(client):
    discipline, _ = _preview(client)
    response = client.post(
        "/api/assistant/contextual/messages",
        json={
            "route": "discipline",
            "selected_discipline_id": discipline["id"],
            "message": "Qual método devo usar para programar?",
            "intent": "recommend_methods",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["execution_mode"] == "deterministic_fallback"
    assert body["study_method_catalog_version"] == "1.0.0"
    assert 2 <= len(body["evidence"]) <= 4
    assert all(
        item["source_type"] == "study_method_catalog"
        for item in body["evidence"]
    )


def test_proposal_is_read_only_until_confirmation_and_idempotent(client):
    discipline, _ = _preview(client)
    response = client.post(
        "/api/assistant/contextual/messages",
        json={
            "route": "study-plan",
            "selected_discipline_id": discipline["id"],
            "message": "Proponha um bloco no calendário.",
            "intent": "propose_study_block",
        },
    )

    assert response.status_code == 200
    action = next(
        item
        for item in response.json()["suggested_actions"]
        if item["type"] == "create_study_block"
    )
    assert action["requires_confirmation"] is True
    assert [
        event
        for event in storage.EVENTS.values()
        if event.get("event_type") == "study_block"
    ] == []

    first = client.post(
        f"/api/assistant/actions/{action['action_id']}/confirm"
    )
    second = client.post(
        f"/api/assistant/actions/{action['action_id']}/confirm"
    )

    assert first.status_code == 200
    assert first.json()["status"] == "executed"
    assert second.json()["status"] == "already_executed"
    events = [
        event
        for event in storage.EVENTS.values()
        if event.get("event_type") == "study_block"
    ]
    assert len(events) == 1
    assert events[0]["source"] == "study_plan"
    assert events[0]["discipline_id"] == discipline["id"]


def test_confirmation_revalidates_new_calendar_conflict(client):
    discipline, preview = _preview(client)
    response = client.post(
        "/api/assistant/contextual/messages",
        json={
            "route": "study-plan",
            "selected_discipline_id": discipline["id"],
            "message": "Reserve o bloco.",
            "intent": "propose_study_block",
        },
    ).json()
    action = next(
        item
        for item in response["suggested_actions"]
        if item["type"] == "create_study_block"
    )
    block = preview["planned_blocks"][0]
    created = client.post(
        "/api/calendar/events",
        json={
            "title": "Conflito novo",
            "event_type": "other",
            "start_at": block["start_at"],
            "end_at": block["end_at"],
            "all_day": False,
            "timezone": "America/Sao_Paulo",
        },
    )
    assert created.status_code == 201

    confirmation = client.post(
        f"/api/assistant/actions/{action['action_id']}/confirm"
    )
    assert confirmation.status_code == 409
    assert [
        event
        for event in storage.EVENTS.values()
        if event.get("event_type") == "study_block"
    ] == []


def test_expired_action_is_rejected(client):
    discipline, _ = _preview(client)
    response = client.post(
        "/api/assistant/contextual/messages",
        json={
            "route": "study-plan",
            "selected_discipline_id": discipline["id"],
            "message": "Reserve o bloco.",
            "intent": "propose_study_block",
        },
    ).json()
    action = next(
        item
        for item in response["suggested_actions"]
        if item["type"] == "create_study_block"
    )
    storage.ASSISTANT_ACTIONS[action["action_id"]]["expires_at"] = (
        storage.utc_now() - timedelta(seconds=1)
    )

    confirmation = client.post(
        f"/api/assistant/actions/{action['action_id']}/confirm"
    )
    assert confirmation.status_code == 409
    assert [
        event
        for event in storage.EVENTS.values()
        if event.get("event_type") == "study_block"
    ] == []


def test_action_and_context_are_isolated_by_user(client, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_IN_TESTS", "true")
    one = ensure_user(
        "assistant-one@example.invalid",
        "password-one",
        user_id="assistant-one",
    )
    two = ensure_user(
        "assistant-two@example.invalid",
        "password-two",
        user_id="assistant-two",
    )
    for user_id in [one.id, two.id]:
        token = current_user_id.set(user_id)
        try:
            storage.DISCIPLINES.clear()
            storage.ASSESSMENTS.clear()
            storage.EVENTS.clear()
        finally:
            current_user_id.reset(token)

    discipline, _ = _preview(client, _headers(one))
    response = client.post(
        "/api/assistant/contextual/messages",
        json={
            "route": "study-plan",
            "selected_discipline_id": discipline["id"],
            "message": "Reserve o bloco.",
            "intent": "propose_study_block",
        },
        headers=_headers(one),
    ).json()
    action = next(
        item
        for item in response["suggested_actions"]
        if item["type"] == "create_study_block"
    )

    assert (
        client.post(
            f"/api/assistant/actions/{action['action_id']}/confirm",
            headers=_headers(two),
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/assistant/contextual/messages",
            json={
                "route": "discipline",
                "selected_discipline_id": discipline["id"],
                "message": "Explique.",
            },
            headers=_headers(two),
        ).status_code
        == 422
    )
