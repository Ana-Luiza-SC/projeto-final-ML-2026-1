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


def create_discipline(client: TestClient, **overrides):
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


def add_assessment(client: TestClient, discipline_id: str, **overrides):
    payload = {"name": "P1", "weight": 100, "grade": 8.0}
    payload.update(overrides)
    response = client.post(f"/api/disciplines/{discipline_id}/assessments", json=payload)
    assert response.status_code == 201
    return response.json()


def recommendation_payload(discipline_id: str, **overrides):
    payload = {
        "discipline_id": discipline_id,
        "target_average": 5.0,
        "pending_topics": [],
        "user_goal": "quero me organizar para a próxima semana",
    }
    payload.update(overrides)
    return payload


def request_recommendation(client: TestClient, discipline_id: str, **overrides):
    response = client.post(
        "/api/agent/study-recommendation",
        json=recommendation_payload(discipline_id, **overrides),
    )
    assert response.status_code == 200
    return response.json()


def assert_common_fallback_response(body: dict, expected_dedication: str | set[str]):
    if isinstance(expected_dedication, set):
        assert body["dedication_level"] in expected_dedication
    else:
        assert body["dedication_level"] == expected_dedication
    assert body["used_fallback"] is True
    assert body["provider"] == "rules"
    assert body["reasons"]
    assert body["recommended_actions"]


def assert_no_final_approval(body: dict):
    joined = " ".join(
        [
            body["academic_situation_summary"],
            body["grade_status"],
            body["attendance_status"],
            *body["reasons"],
        ]
    ).lower()
    assert "não é possível afirmar aprovação final" in joined


def test_scenario_mm_with_adequate_attendance():
    client = TestClient(app)
    discipline = create_discipline(client, total_classes=20, missed_classes=1)
    add_assessment(client, discipline["id"], grade=5.5)

    body = request_recommendation(client, discipline["id"])

    assert_common_fallback_response(body, "low")


def test_scenario_ms_with_unknown_attendance():
    client = TestClient(app)
    discipline = create_discipline(client, total_classes=None, missed_classes=None)
    add_assessment(client, discipline["id"], grade=8.0)

    body = request_recommendation(client, discipline["id"])

    assert_common_fallback_response(body, {"low", "medium"})
    assert_no_final_approval(body)


def test_scenario_mi_with_adequate_attendance():
    client = TestClient(app)
    discipline = create_discipline(client, total_classes=20, missed_classes=1)
    add_assessment(client, discipline["id"], grade=4.0)

    body = request_recommendation(client, discipline["id"])

    assert_common_fallback_response(body, "high")


def test_scenario_frequency_below_75_percent():
    client = TestClient(app)
    discipline = create_discipline(client, total_classes=20, missed_classes=6)
    add_assessment(client, discipline["id"], grade=9.0)

    body = request_recommendation(client, discipline["id"])

    assert_common_fallback_response(body, "high")
    assert "risco por falta" in body["attendance_status"].lower()


def test_scenario_required_grade_above_10():
    client = TestClient(app)
    discipline = create_discipline(client)
    add_assessment(client, discipline["id"], weight=80, grade=1.0)
    add_assessment(client, discipline["id"], name="P2", weight=20, grade=None)

    body = request_recommendation(client, discipline["id"])

    assert_common_fallback_response(body, "high")
    assert "maior que 10" in body["grade_status"]


def test_scenario_without_registered_assessments():
    client = TestClient(app)
    discipline = create_discipline(client, total_classes=20, missed_classes=1)

    body = request_recommendation(client, discipline["id"])

    assert_common_fallback_response(body, "low")
    assert any("Cadastre mais avaliações ou pesos" in action for action in body["recommended_actions"])
    assert "avaliações com nota" in body["missing_information"]


def test_scenario_many_difficult_pending_topics():
    client = TestClient(app)
    discipline = create_discipline(client, total_classes=20, missed_classes=1)
    add_assessment(client, discipline["id"], grade=8.0)

    body = request_recommendation(
        client,
        discipline["id"],
        pending_topics=[
            {"title": "Tema difícil 1", "difficulty": "high", "status": "not_started"},
            {"title": "Tema difícil 2", "difficulty": "high", "status": "not_started"},
            {"title": "Tema difícil 3", "difficulty": "high", "status": "in_progress"},
        ],
    )

    assert_common_fallback_response(body, "high")
    assert any("difíceis" in action for action in body["recommended_actions"])


def test_scenario_missing_google_api_key_uses_fallback():
    client = TestClient(app)
    discipline = create_discipline(client, total_classes=20, missed_classes=1)
    add_assessment(client, discipline["id"], grade=8.0)

    body = request_recommendation(client, discipline["id"])

    assert_common_fallback_response(body, "low")
