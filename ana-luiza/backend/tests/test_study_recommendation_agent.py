import logging

import pytest
from fastapi.testclient import TestClient

from app import storage
from app.main import app


@pytest.fixture(autouse=True)
def clear_storage(monkeypatch):
    storage.DISCIPLINES.clear()
    storage.ASSESSMENTS.clear()
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "google")
    monkeypatch.setenv("LLM_FALLBACK_ENABLED", "true")
    yield
    storage.DISCIPLINES.clear()
    storage.ASSESSMENTS.clear()


@pytest.fixture
def client():
    return TestClient(app)


def create_discipline(client, **overrides):
    payload = {
        "code": "FGA0000",
        "name": "Disciplina de Teste",
        "total_classes": 20,
        "missed_classes": 1,
    }
    payload.update(overrides)
    response = client.post("/api/disciplines", json=payload)
    assert response.status_code == 201
    return response.json()


def add_assessment(client, discipline_id, **overrides):
    payload = {"name": "P1", "weight": 100, "grade": 8.0}
    payload.update(overrides)
    response = client.post(f"/api/disciplines/{discipline_id}/assessments", json=payload)
    assert response.status_code == 201
    return response.json()


def recommendation_payload(discipline_id, **overrides):
    payload = {
        "discipline_id": discipline_id,
        "target_average": 5.0,
        "pending_topics": [],
        "user_goal": "quero me organizar para a próxima semana",
    }
    payload.update(overrides)
    return payload


def test_missing_google_api_key_uses_fallback(client):
    discipline = create_discipline(client)
    add_assessment(client, discipline["id"])

    response = client.post(
        "/api/agent/study-recommendation",
        json=recommendation_payload(discipline["id"]),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["used_fallback"] is True
    assert body["provider"] == "rules"
    assert body["recommended_actions"]
    assert body["reasons"]


def test_missing_discipline_returns_friendly_error(client):
    response = client.post(
        "/api/agent/study-recommendation",
        json=recommendation_payload("00000000-0000-0000-0000-000000000000"),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Disciplina não encontrada."


def test_projected_mi_generates_high_dedication(client):
    discipline = create_discipline(client)
    add_assessment(client, discipline["id"], grade=4.0)

    response = client.post(
        "/api/agent/study-recommendation",
        json=recommendation_payload(discipline["id"]),
    )

    assert response.status_code == 200
    assert response.json()["dedication_level"] == "high"


def test_frequency_below_75_generates_high_dedication(client):
    discipline = create_discipline(client, total_classes=20, missed_classes=6)
    add_assessment(client, discipline["id"], grade=9.0)

    response = client.post(
        "/api/agent/study-recommendation",
        json=recommendation_payload(discipline["id"]),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dedication_level"] == "high"
    assert "falta" in body["attendance_status"].lower()


def test_unknown_frequency_does_not_assert_final_approval(client):
    discipline = create_discipline(client, total_classes=None, missed_classes=None)
    add_assessment(client, discipline["id"], grade=9.0)

    response = client.post(
        "/api/agent/study-recommendation",
        json=recommendation_payload(discipline["id"]),
    )

    assert response.status_code == 200
    body = response.json()
    joined = " ".join(
        [
            body["academic_situation_summary"],
            body["grade_status"],
            body["attendance_status"],
        ]
    ).lower()
    assert "não é possível afirmar aprovação final" in joined


def test_required_grade_above_10_generates_strong_alert(client):
    discipline = create_discipline(client)
    add_assessment(client, discipline["id"], weight=80, grade=1.0)
    add_assessment(client, discipline["id"], name="P2", weight=20, grade=None)

    response = client.post(
        "/api/agent/study-recommendation",
        json=recommendation_payload(discipline["id"], target_average=5.0),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dedication_level"] == "high"
    assert "maior que 10" in body["grade_status"]


def test_difficult_pending_topic_increases_priority(client):
    discipline = create_discipline(client)
    add_assessment(client, discipline["id"], grade=8.0)
    topics = [
        {"title": "Tema difícil 1", "difficulty": "high", "status": "not_started"},
        {"title": "Tema difícil 2", "difficulty": "high", "status": "not_started"},
        {"title": "Tema difícil 3", "difficulty": "high", "status": "in_progress"},
    ]

    response = client.post(
        "/api/agent/study-recommendation",
        json=recommendation_payload(discipline["id"], pending_topics=topics),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dedication_level"] == "high"
    assert any("difíceis" in action for action in body["recommended_actions"])


def test_invalid_difficulty_fails(client):
    discipline = create_discipline(client)
    response = client.post(
        "/api/agent/study-recommendation",
        json=recommendation_payload(
            discipline["id"],
            pending_topics=[{"title": "GQM", "difficulty": "urgent", "status": "not_started"}],
        ),
    )

    assert response.status_code == 422


def test_invalid_status_fails(client):
    discipline = create_discipline(client)
    response = client.post(
        "/api/agent/study-recommendation",
        json=recommendation_payload(
            discipline["id"],
            pending_topics=[{"title": "GQM", "difficulty": "medium", "status": "todo"}],
        ),
    )

    assert response.status_code == 422


def test_final_response_always_contains_reasons_and_actions(client):
    discipline = create_discipline(client)

    response = client.post(
        "/api/agent/study-recommendation",
        json=recommendation_payload(discipline["id"]),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["reasons"]
    assert body["recommended_actions"]


def test_logs_do_not_include_google_api_key_value(client, monkeypatch, caplog):
    monkeypatch.setenv("GOOGLE_API_KEY", "dummy-test-key")
    monkeypatch.setenv("LLM_PROVIDER", "rules")
    caplog.set_level(logging.INFO, logger="estudaunb.agent")
    discipline = create_discipline(client)

    response = client.post(
        "/api/agent/study-recommendation",
        json=recommendation_payload(discipline["id"]),
    )

    assert response.status_code == 200
    assert "dummy-test-key" not in caplog.text
    assert "GOOGLE_API_KEY" not in caplog.text


def test_openapi_contains_agent_endpoint(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert "/api/agent/study-recommendation" in schema["paths"]
