import pytest
from fastapi.testclient import TestClient

from app import storage
from app.main import app
from app.schemas import StudyPlanRequest
from app.services.study_plan_agent import generate_study_plan


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


def create_discipline(client, code="FGA0001", name="Disciplina"):
    response = client.post("/api/disciplines", json={"code": code, "name": name})
    assert response.status_code == 201
    return response.json()


def plan_payload(ids, **overrides):
    payload = {
        "discipline_ids": ids,
        "availability": {
            "available_hours_per_week": 4,
            "days_available": ["monday", "wednesday"],
        },
        "max_session_minutes": 90,
        "priorities": [],
        "objective_text": "organizar a semana",
    }
    payload.update(overrides)
    return payload


def test_endpoint_generates_deterministic_fallback_without_key(client):
    first = create_discipline(client, "FGA0001", "Algoritmos")
    second = create_discipline(client, "FGA0002", "Qualidade")

    response = client.post("/api/study-plans/generate", json=plan_payload([first["id"], second["id"]]))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["source"] == "deterministic_fallback"
    assert body["plan"]
    assert {item["discipline_id"] for item in body["plan"]} <= {first["id"], second["id"]}
    assert sum(item["duration_minutes"] for item in body["plan"]) <= body["metrics"]["requested_minutes"]
    assert all(item["start_time"] is None and item["end_time"] is None for item in body["plan"])


def test_same_input_produces_same_plan(client):
    first = create_discipline(client, "FGA0001", "Algoritmos")
    second = create_discipline(client, "FGA0002", "Qualidade")
    payload = plan_payload([first["id"], second["id"]])

    first_response = client.post("/api/study-plans/generate", json=payload).json()
    second_response = client.post("/api/study-plans/generate", json=payload).json()

    assert first_response["plan"] == second_response["plan"]
    assert first_response["metrics"] == second_response["metrics"]


def test_priority_weights_allocate_more_time(client):
    first = create_discipline(client, "FGA0001", "Alta")
    second = create_discipline(client, "FGA0002", "Baixa")
    payload = plan_payload(
        [first["id"], second["id"]],
        availability={"available_hours_per_week": 3, "days_available": ["monday", "wednesday"]},
        priorities=[
            {"discipline_id": first["id"], "priority": 5},
            {"discipline_id": second["id"], "priority": 1},
        ],
    )

    body = client.post("/api/study-plans/generate", json=payload).json()
    totals = {}
    for item in body["plan"]:
        totals[item["discipline_id"]] = totals.get(item["discipline_id"], 0) + item["duration_minutes"]

    assert totals[first["id"]] > totals[second["id"]]


def test_insufficient_availability_prioritizes_and_warns(client):
    first = create_discipline(client, "FGA0001", "Alta")
    second = create_discipline(client, "FGA0002", "Baixa")
    payload = plan_payload(
        [first["id"], second["id"]],
        availability={"available_hours_per_week": 0.5, "days_available": ["monday"]},
        priorities=[
            {"discipline_id": first["id"], "priority": 5},
            {"discipline_id": second["id"], "priority": 1},
        ],
    )

    response = client.post("/api/study-plans/generate", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert len(body["plan"]) == 1
    assert body["plan"][0]["discipline_id"] == first["id"]
    assert body["warnings"]


def test_windows_generate_real_times_and_respect_max_session(client):
    discipline = create_discipline(client, "FGA0001", "Algoritmos")
    payload = plan_payload(
        [discipline["id"]],
        availability={
            "available_hours_per_week": 3,
            "days_available": ["monday"],
            "time_windows": [{"day": "monday", "start_time": "18:00", "end_time": "21:00"}],
        },
        max_session_minutes=60,
    )

    body = client.post("/api/study-plans/generate", json=payload).json()

    assert len(body["plan"]) == 3
    assert all(item["start_time"] and item["end_time"] for item in body["plan"])
    assert all(item["duration_minutes"] <= 60 for item in body["plan"])
    assert body["plan"][0]["start_time"] == "18:00"
    assert body["plan"][-1]["end_time"] == "21:00"


def test_overlapping_windows_fail_validation(client):
    discipline = create_discipline(client)
    payload = plan_payload(
        [discipline["id"]],
        availability={
            "available_hours_per_week": 3,
            "days_available": ["monday"],
            "time_windows": [
                {"day": "monday", "start_time": "18:00", "end_time": "20:00"},
                {"day": "monday", "start_time": "19:00", "end_time": "21:00"},
            ],
        },
    )

    response = client.post("/api/study-plans/generate", json=payload)

    assert response.status_code == 422


def test_missing_discipline_returns_404(client):
    response = client.post(
        "/api/study-plans/generate",
        json=plan_payload(["00000000-0000-0000-0000-000000000000"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Disciplina não encontrada."


def test_duplicate_discipline_id_returns_422(client):
    discipline = create_discipline(client)
    response = client.post(
        "/api/study-plans/generate",
        json=plan_payload([discipline["id"], discipline["id"]]),
    )

    assert response.status_code == 422


def test_invalid_hours_and_max_session_return_422(client):
    discipline = create_discipline(client)

    invalid_hours = client.post(
        "/api/study-plans/generate",
        json=plan_payload([discipline["id"]], availability={"available_hours_per_week": 0, "days_available": ["monday"]}),
    )
    invalid_session = client.post(
        "/api/study-plans/generate",
        json=plan_payload([discipline["id"]], max_session_minutes=45),
    )

    assert invalid_hours.status_code == 422
    assert invalid_session.status_code == 422


class ValidLLM:
    def generate_explanation(self, context, timeout_seconds):
        return {"summary": "Plano explicado sem alterar a grade.", "discipline_ids": context["discipline_ids"]}


class TimeoutLLM:
    def generate_explanation(self, context, timeout_seconds):
        raise TimeoutError("timeout")


class InvalidLLM:
    def generate_explanation(self, context, timeout_seconds):
        return {"summary": ""}


class InventingLLM:
    def generate_explanation(self, context, timeout_seconds):
        return {"summary": "Inclui disciplina extra.", "discipline_ids": ["00000000-0000-0000-0000-000000000999"]}


def request_model(discipline_id):
    return StudyPlanRequest.model_validate(plan_payload([discipline_id]))


def test_valid_llm_can_assist_explanation(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
    discipline = create_discipline(client)

    response = generate_study_plan(request_model(discipline["id"]), storage.list_disciplines(), llm_client=ValidLLM())

    assert response.source == "llm_assisted"
    assert response.summary == "Plano explicado sem alterar a grade."


@pytest.mark.parametrize("fake_client", [TimeoutLLM(), InvalidLLM(), InventingLLM()])
def test_llm_failures_use_deterministic_fallback(client, fake_client, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
    discipline = create_discipline(client)

    response = generate_study_plan(request_model(discipline["id"]), storage.list_disciplines(), llm_client=fake_client)

    assert response.source == "deterministic_fallback"
    assert response.plan
    assert response.warnings


def test_openapi_contains_study_plan_endpoint(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/api/study-plans/generate" in response.json()["paths"]
