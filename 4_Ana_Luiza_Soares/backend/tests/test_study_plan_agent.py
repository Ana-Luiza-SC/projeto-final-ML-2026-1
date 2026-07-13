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
    storage.CONTENT_NODES.clear()
    storage.ASSESSMENT_CONTENT_LINKS.clear()
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "google")
    monkeypatch.setenv("LLM_FALLBACK_ENABLED", "true")
    yield
    storage.DISCIPLINES.clear()
    storage.ASSESSMENTS.clear()
    storage.CONTENT_NODES.clear()
    storage.ASSESSMENT_CONTENT_LINKS.clear()


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

def _content_node(client, discipline_id, title, **extra):
    response = client.post(f"/api/disciplines/{discipline_id}/contents", json={"title": title, **extra})
    assert response.status_code == 201
    return response.json()

def _future_assessment(client, discipline_id, name, assessment_date, weight=50):
    response = client.post(f"/api/disciplines/{discipline_id}/assessments", json={"name": name, "date": assessment_date.isoformat(), "weight": weight, "status": "planned"})
    assert response.status_code == 201
    return response.json()

def _associate(client, discipline_id, assessment_id, content_id, descendants=False):
    response = client.put(f"/api/disciplines/{discipline_id}/assessments/{assessment_id}/content-associations", json={"selections": [{"content_node_id": content_id, "include_descendants": descendants}]})
    assert response.status_code == 200

def test_tuesday_thursday_deadlines_reserve_monday_and_wednesday(client, monkeypatch):
    from datetime import date
    from app.services import content_map, study_plan_agent
    sunday = date(2026, 7, 12)
    monkeypatch.setattr(content_map, "local_today", lambda: sunday)
    monkeypatch.setattr(study_plan_agent, "local_today", lambda: sunday)
    urgent = create_discipline(client, "FGA-QS", "Qualidade de Software")
    undated = create_discipline(client, "FGA-GEN", "Disciplina sem prova")
    p1_content = _content_node(client, urgent["id"], "Revisão para P1", difficulty="high", status="not_started")
    p2_content = _content_node(client, urgent["id"], "Revisão para P2", status="in_progress")
    p1 = _future_assessment(client, urgent["id"], "Prova 1", date(2026, 7, 14), 40)
    p2 = _future_assessment(client, urgent["id"], "Prova 2", date(2026, 7, 16), 60)
    _associate(client, urgent["id"], p1["id"], p1_content["id"])
    _associate(client, urgent["id"], p2["id"], p2_content["id"])
    body = client.post("/api/study-plans/generate", json=plan_payload([urgent["id"], undated["id"]], availability={"available_hours_per_week": 3, "days_available": ["monday", "wednesday", "friday"]}, max_session_minutes=60, objective_text=None)).json()
    p1_sessions = [item for item in body["plan"] if item.get("assessment_name") == "Prova 1"]
    p2_sessions = [item for item in body["plan"] if item.get("assessment_name") == "Prova 2"]
    assert [(item["day"], item["scheduled_date"]) for item in p1_sessions] == [("monday", "2026-07-13")]
    assert [(item["day"], item["scheduled_date"]) for item in p2_sessions] == [("wednesday", "2026-07-15")]
    assert not any(item.get("assessment_name") for item in body["plan"] if item["day"] == "friday")
    assert any(item["discipline_id"] == undated["id"] and item["day"] == "friday" for item in body["plan"])
    assert "Prova 1 em 2026-07-14" in body["summary"] and "Prova 2 em 2026-07-16" in body["summary"]

def test_content_without_capacity_before_deadline_is_pending(client, monkeypatch):
    from datetime import date
    from app.services import content_map, study_plan_agent
    sunday = date(2026, 7, 12)
    monkeypatch.setattr(content_map, "local_today", lambda: sunday)
    monkeypatch.setattr(study_plan_agent, "local_today", lambda: sunday)
    discipline = create_discipline(client, "FGA-QS", "Qualidade")
    first = _content_node(client, discipline["id"], "A")
    second = _content_node(client, discipline["id"], "B")
    proof = _future_assessment(client, discipline["id"], "Prova terça", date(2026, 7, 14))
    _associate(client, discipline["id"], proof["id"], first["id"])
    client.put(f"/api/disciplines/{discipline['id']}/assessments/{proof['id']}/content-associations", json={"selections": [{"content_node_id": first["id"], "include_descendants": False}, {"content_node_id": second["id"], "include_descendants": False}]})
    body = client.post("/api/study-plans/generate", json=plan_payload([discipline["id"]], availability={"available_hours_per_week": 1, "days_available": ["monday", "wednesday"]}, max_session_minutes=30)).json()
    assert any("ficaram pendentes" in warning and "B" in warning for warning in body["warnings"])
    assert not any(item.get("assessment_name") and item["scheduled_date"] >= item["assessment_date"] for item in body["plan"])

def test_past_assessment_is_not_a_future_deadline(client, monkeypatch):
    from datetime import date
    from app.services import content_map, study_plan_agent
    today = date(2026, 7, 12)
    monkeypatch.setattr(content_map, "local_today", lambda: today)
    monkeypatch.setattr(study_plan_agent, "local_today", lambda: today)
    discipline = create_discipline(client)
    content = _content_node(client, discipline["id"], "Legado")
    old = _future_assessment(client, discipline["id"], "Prova passada", date(2026, 7, 10))
    _associate(client, discipline["id"], old["id"], content["id"])
    body = client.post("/api/study-plans/generate", json=plan_payload([discipline["id"]], availability={"available_hours_per_week": .5, "days_available": ["monday"]}, max_session_minutes=30)).json()
    assert all(item.get("assessment_name") is None for item in body["plan"])
    assert not body["priority_influences"]

def test_inherited_content_receives_assessment_deadline(client, monkeypatch):
    from datetime import date
    from app.services import content_map, study_plan_agent
    sunday = date(2026, 7, 12)
    monkeypatch.setattr(content_map, "local_today", lambda: sunday)
    monkeypatch.setattr(study_plan_agent, "local_today", lambda: sunday)
    discipline = create_discipline(client)
    root = _content_node(client, discipline["id"], "Ordenação", status="reviewed")
    child_response = client.post(f"/api/disciplines/{discipline['id']}/contents/{root['id']}/children", json={"title": "Quicksort", "difficulty": "high"})
    child = child_response.json()
    proof = _future_assessment(client, discipline["id"], "P1", date(2026, 7, 14))
    _associate(client, discipline["id"], proof["id"], root["id"], True)
    body = client.post("/api/study-plans/generate", json=plan_payload([discipline["id"]], availability={"available_hours_per_week": .5, "days_available": ["monday"]}, max_session_minutes=30)).json()
    session = body["plan"][0]
    assert session["content_node_id"] == child["id"] and session["association_origin"] == "inherited"
    assert session["assessment_date"] == "2026-07-14" and session["scheduled_date"] == "2026-07-13"

def test_timezone_policy_keeps_sunday_to_monday_without_shift():
    from datetime import date
    from app.services.academic_time import next_date_for_weekday
    assert next_date_for_weekday("monday", date(2026, 7, 12)) == date(2026, 7, 13)
    assert next_date_for_weekday("sunday", date(2026, 7, 12)) == date(2026, 7, 12)

def test_invalid_llm_explanation_cannot_move_session_after_deadline(client, monkeypatch):
    from datetime import date
    from app.services import content_map, study_plan_agent
    sunday = date(2026, 7, 12)
    monkeypatch.setattr(content_map, "local_today", lambda: sunday)
    monkeypatch.setattr(study_plan_agent, "local_today", lambda: sunday)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-only")
    discipline = create_discipline(client)
    content = _content_node(client, discipline["id"], "P1")
    proof = _future_assessment(client, discipline["id"], "Prova 1", date(2026, 7, 14))
    _associate(client, discipline["id"], proof["id"], content["id"])
    records = []
    from app.routers.study_plans import _effective_weight
    context = __import__("app.services.content_map", fromlist=["agent_content_context"]).agent_content_context(discipline["id"], storage.list_assessments(discipline["id"]))
    group = context["assessment_contents"][0]
    node = {**group["nodes"][0], "assessment_id": proof["id"], "assessment_name": proof["name"], "assessment_date": proof["date"], "effective_weight": _effective_weight(proof), "evidence": "P1 associada"}
    records.append({**storage.get_discipline(discipline["id"]), "assessments": [proof], "associated_contents": [node], "partial_average": None})
    response = generate_study_plan(StudyPlanRequest.model_validate(plan_payload([discipline["id"]], availability={"available_hours_per_week": 1, "days_available": ["monday", "friday"]}, max_session_minutes=30)), records, llm_client=InvalidLLM())
    assert response.source == "deterministic_fallback" and response.fallback_reason == "invalid_response"
    assert all(not item.assessment_date or item.scheduled_date < item.assessment_date for item in response.plan)

def test_assessment_tomorrow_precedes_undated_discipline(client, monkeypatch):
    from datetime import date
    from app.services import content_map, study_plan_agent
    sunday = date(2026, 7, 12)
    monkeypatch.setattr(content_map, "local_today", lambda: sunday)
    monkeypatch.setattr(study_plan_agent, "local_today", lambda: sunday)
    urgent = create_discipline(client, "URG", "Urgente")
    generic = create_discipline(client, "GEN", "Sem data")
    content = _content_node(client, urgent["id"], "Última revisão")
    proof = _future_assessment(client, urgent["id"], "Prova amanhã", date(2026, 7, 13))
    _associate(client, urgent["id"], proof["id"], content["id"])
    body = client.post("/api/study-plans/generate", json=plan_payload([generic["id"], urgent["id"]], availability={"available_hours_per_week": 1, "days_available": ["sunday", "monday"]}, max_session_minutes=30)).json()
    urgent_session = next(item for item in body["plan"] if item.get("assessment_name") == "Prova amanhã")
    assert urgent_session["day"] == "sunday" and urgent_session["scheduled_date"] == "2026-07-12"
    assert next(item for item in body["plan"] if item["discipline_id"] == generic["id"])["day"] == "monday"
