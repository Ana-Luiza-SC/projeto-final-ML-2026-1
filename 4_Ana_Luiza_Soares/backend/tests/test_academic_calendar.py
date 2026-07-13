from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import storage
from app.auth import create_token, ensure_user
from app.database import current_user_id
from app.main import app


def headers(user):
    return {"Authorization": f"Bearer {create_token(user)}"}


@pytest.fixture(autouse=True)
def clear_storage(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", "calendar-test-secret")
    for collection in [storage.DISCIPLINES, storage.ASSESSMENTS, storage.EVENTS, storage.COURSE_PLANS]:
        collection.clear()
    storage.EVENT_EXTRACTION_PREVIEWS.clear()
    yield
    for collection in [storage.DISCIPLINES, storage.ASSESSMENTS, storage.EVENTS, storage.COURSE_PLANS]:
        collection.clear()
    storage.EVENT_EXTRACTION_PREVIEWS.clear()


@pytest.fixture
def client():
    return TestClient(app)


def create_discipline(client, code="CAL001", name="Calendário"):
    response = client.post("/api/disciplines", json={"code": code, "name": name})
    assert response.status_code == 201
    return response.json()


def test_manual_calendar_event_crud_and_filters(client):
    discipline = create_discipline(client)
    payload = {
        "discipline_id": discipline["id"],
        "title": "Entrega 1",
        "event_type": "assignment",
        "start_at": "2026-07-20T00:00:00-03:00",
        "all_day": True,
        "timezone": "America/Sao_Paulo",
    }
    created = client.post("/api/calendar/events", json=payload)
    assert created.status_code == 201
    event = created.json()
    assert event["source"] == "manual" and event["discipline_code"] == "CAL001"

    listed = client.get("/api/calendar/events", params={"start_at": "2026-07-01T00:00:00-03:00", "end_at": "2026-07-31T23:59:59-03:00", "event_type": "assignment"})
    assert listed.status_code == 200 and [item["id"] for item in listed.json()] == [event["id"]]

    updated = client.patch(f"/api/calendar/events/{event['id']}", json={"title": "Entrega final"})
    assert updated.status_code == 200 and updated.json()["title"] == "Entrega final"
    assert client.post(f"/api/calendar/events/{event['id']}/complete").json()["status"] == "completed"
    assert client.delete(f"/api/calendar/events/{event['id']}").status_code == 204


def test_assessment_sync_is_idempotent_and_updates_event(client):
    discipline = create_discipline(client)
    assessment = client.post(f"/api/disciplines/{discipline['id']}/assessments", json={"name": "Prova 1", "weight": 40, "date": "2026-07-14", "status": "planned"}).json()
    events = client.get("/api/calendar/events", params={"start_at": "2026-07-01T00:00:00-03:00", "end_at": "2026-07-31T23:59:59-03:00"}).json()
    assert len(events) == 1 and events[0]["assessment_id"] == assessment["id"] and events[0]["event_type"] == "exam"

    updated = client.patch(f"/api/disciplines/{discipline['id']}/assessments/{assessment['id']}", json={"name": "Prova corrigida", "date": "2026-07-16", "weight": 50}).json()
    assert updated["name"] == "Prova corrigida"
    events = client.get("/api/calendar/events", params={"start_at": "2026-07-01T00:00:00-03:00", "end_at": "2026-07-31T23:59:59-03:00"}).json()
    assert len(events) == 1 and events[0]["title"] == "Prova corrigida" and events[0]["start_at"].startswith("2026-07-16")

    assert client.delete(f"/api/disciplines/{discipline['id']}/assessments/{assessment['id']}").status_code == 204
    cancelled = client.get("/api/calendar/events", params={"start_at": "2026-07-01T00:00:00-03:00", "end_at": "2026-07-31T23:59:59-03:00"}).json()[0]
    assert cancelled["status"] == "cancelled"


def test_course_plan_preview_is_not_persisted_until_confirmation(client):
    discipline = create_discipline(client)
    storage.save_course_plan(discipline["id"], {
        "code": "CAL001",
        "name": "Calendário",
        "objectives": [],
        "contents": ["Unidade 1"],
        "schedule": [],
        "bibliography": [],
        "evaluation_groups": [],
        "assessments": [{"name": "Prova 1", "date": "2026-07-14", "weight": 30, "topics": ["Unidade 1"], "status": "recognized"}],
    })
    preview = client.post(f"/api/disciplines/{discipline['id']}/calendar/extract-preview")
    assert preview.status_code == 200
    body = preview.json()
    assert body["draft_events"][0]["title"] == "Prova 1"
    assert client.get("/api/calendar/events", params={"start_at": "2026-07-01T00:00:00-03:00", "end_at": "2026-07-31T23:59:59-03:00"}).json() == []

    confirmed = client.post(f"/api/disciplines/{discipline['id']}/calendar/confirm-preview", json={"preview_id": body["preview_id"], "draft_events": body["draft_events"]})
    assert confirmed.status_code == 200 and confirmed.json()["created_count"] == 1
    events = client.get("/api/calendar/events", params={"start_at": "2026-07-01T00:00:00-03:00", "end_at": "2026-07-31T23:59:59-03:00"}).json()
    assert len(events) == 1 and events[0]["source"] == "course_plan"


def test_ambiguous_preview_draft_is_skipped(client):
    discipline = create_discipline(client)
    storage.save_course_plan(discipline["id"], {"assessments": [{"name": "Prova sem data", "date": None, "weight": 30, "status": "recognized"}], "contents": [], "schedule": [], "objectives": [], "bibliography": []})
    body = client.post(f"/api/disciplines/{discipline['id']}/calendar/extract-preview").json()
    assert body["draft_events"][0]["ambiguous"] is True
    confirmed = client.post(f"/api/disciplines/{discipline['id']}/calendar/confirm-preview", json={"preview_id": body["preview_id"], "draft_events": body["draft_events"]}).json()
    assert confirmed["created_count"] == 0 and confirmed["skipped_events"]


def test_calendar_routes_are_authenticated_and_isolated(monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_IN_TESTS", "true")
    one = ensure_user("calendar-one@example.invalid", "password-one", user_id="calendar-one")
    two = ensure_user("calendar-two@example.invalid", "password-two", user_id="calendar-two")
    for user_id in [one.id, two.id]:
        token = current_user_id.set(user_id)
        try:
            storage.DISCIPLINES.clear(); storage.ASSESSMENTS.clear(); storage.EVENTS.clear(); storage.COURSE_PLANS.clear()
        finally:
            current_user_id.reset(token)
    with TestClient(app) as client:
        assert client.get("/api/calendar/events", params={"start_at": "2026-07-01T00:00:00-03:00", "end_at": "2026-07-31T23:59:59-03:00"}).status_code == 401
        created = client.post("/api/disciplines", json={"code": "ONE", "name": "Usuário 1"}, headers=headers(one)).json()
        event = client.post("/api/calendar/events", json={"discipline_id": created["id"], "title": "P1", "event_type": "exam", "start_at": "2026-07-20T00:00:00-03:00", "all_day": True, "timezone": "America/Sao_Paulo"}, headers=headers(one))
        assert event.status_code == 201
        assert len(client.get("/api/calendar/events", params={"start_at": "2026-07-01T00:00:00-03:00", "end_at": "2026-07-31T23:59:59-03:00"}, headers=headers(one)).json()) == 1
        assert client.get("/api/calendar/events", params={"start_at": "2026-07-01T00:00:00-03:00", "end_at": "2026-07-31T23:59:59-03:00"}, headers=headers(two)).json() == []
