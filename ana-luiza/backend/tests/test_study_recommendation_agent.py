import logging
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import storage
from app.main import app
from app.services.study_recommendation_agent import build_safe_prompt_context
from app.services import study_recommendation_agent


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
    assert any(item["strategy_id"] in {"concrete_examples", "self_explanation"} for item in body["study_actions"])


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

def test_grouped_assessment_api_to_agent_fallback_is_auditable(client, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    discipline = create_discipline(client, total_classes=None, missed_classes=None)
    created = client.post(f"/api/disciplines/{discipline['id']}/assessments", json={"name": "mTAI", "grade": 8.9, "status": "completed", "evaluation_group_code": "AI", "evaluation_group_name": "Avaliação Individual", "group_final_weight": 40, "group_weight": 60})
    assert created.status_code == 201
    simulation = client.get(f"/api/disciplines/{discipline['id']}/academic-simulation").json()
    assert simulation["completed_weight"] == pytest.approx(.24)
    assert simulation["current_contribution"] == pytest.approx(2.136)
    assert simulation["partial_average"] == pytest.approx(8.9)
    assert simulation["current_mention"] is None
    response = client.post("/api/agent/study-recommendation", json=recommendation_payload(discipline["id"]))
    assert response.status_code == 200
    body = response.json()
    assert body["used_fallback"] is True and body["provider"] == "rules"
    assert body["used_evidence"] and body["recommended_actions"] and body["reasons"]
    assert "frequência/faltas" in body["missing_information"]
    assert "menção final: ainda não calculável" in body["grade_status"].lower()

def test_agent_context_contains_original_and_effective_group_weights():
    assessment = {"name": "mTAI", "status": "completed", "grade": 8.9, "group_final_weight": 40, "group_weight": 60}
    context = build_safe_prompt_context({"id": "1", "code": "FGA0001", "name": "Teste", "assessments": [assessment]}, {"completed_weight": .24, "remaining_weight": .76}, [], None)
    item = context["assessments"]["completed_with_grades"][0]
    assert item["group_final_weight"] == 40
    assert item["group_weight"] == 60
    assert item["effective_weight"] == pytest.approx(.24)

def test_invalid_llm_response_uses_identified_fallback(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-only")
    monkeypatch.setattr(study_recommendation_agent, "generate_google_recommendation", lambda *_args, **_kwargs: {})
    discipline = create_discipline(client)
    add_assessment(client, discipline["id"])
    body = client.post("/api/agent/study-recommendation", json=recommendation_payload(discipline["id"])).json()
    assert body["used_fallback"] is True and body["provider"] == "rules"
    assert body["used_evidence"] and body["recommended_actions"] and body["reasons"]

def test_unavailable_llm_uses_identified_fallback(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-only")
    def unavailable(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")
    monkeypatch.setattr(study_recommendation_agent, "generate_google_recommendation", unavailable)
    discipline = create_discipline(client, total_classes=None, missed_classes=None)
    body = client.post("/api/agent/study-recommendation", json=recommendation_payload(discipline["id"])).json()
    assert body["used_fallback"] is True and body["provider"] == "rules"
    assert "frequência/faltas" in body["missing_information"]

def _topic(title="Quicksort", difficulty="medium", status="in_progress"):
    return {"title": title, "difficulty": difficulty, "status": status}

def test_difficult_topic_gets_concrete_action_and_valid_strategy(client):
    discipline = create_discipline(client)
    body = client.post("/api/agent/study-recommendation", json=recommendation_payload(discipline["id"], pending_topics=[_topic(difficulty="high", status="not_started")])).json()
    ids = {item["strategy_id"] for item in body["study_actions"]}
    assert {"concrete_examples", "self_explanation"}.issubset(ids)
    assert all(item["action"] and item["reason"] and item["evidence"] and item["reference_ids"] for item in body["study_actions"])

def test_studied_topic_gets_retrieval_practice(client):
    discipline = create_discipline(client)
    body = client.post("/api/agent/study-recommendation", json=recommendation_payload(discipline["id"], pending_topics=[_topic()])).json()
    action = next(item for item in body["study_actions"] if item["strategy_id"] == "retrieval_practice")
    assert "sem consultar" in action["action"] and "lacunas" in action["action"]

def test_confirmed_assessment_with_several_days_allows_spaced_practice(client):
    discipline = create_discipline(client)
    add_assessment(client, discipline["id"], name="P1", grade=None, status="planned", date=str(date.today() + timedelta(days=7)))
    body = client.post("/api/agent/study-recommendation", json=recommendation_payload(discipline["id"], pending_topics=[_topic()])).json()
    assert any(item["strategy_id"] == "spaced_practice" for item in body["study_actions"])

def test_imminent_exam_does_not_promise_unavailable_spacing(client):
    discipline = create_discipline(client)
    add_assessment(client, discipline["id"], name="P1", grade=None, status="planned", date=str(date.today() + timedelta(days=1)))
    body = client.post("/api/agent/study-recommendation", json=recommendation_payload(discipline["id"], pending_topics=[_topic()])).json()
    assert not any(item["strategy_id"] == "spaced_practice" for item in body["study_actions"])
    assert any("não há base para prometer espaçamento ideal" in item["reason"] for item in body["study_actions"])

def _valid_llm_payload(study_actions):
    return {"dedication_level": "medium", "confidence": .7, "academic_situation_summary": "Dados cadastrados analisados.", "grade_status": "Menção final ainda não calculável.", "attendance_status": "Frequência desconhecida.", "recommended_actions": ["Cadastre conteúdo."], "reasons": ["Faltam dados."], "missing_information": ["frequência"], "study_actions": study_actions}

def test_invented_llm_strategy_or_reference_triggers_fallback(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-only")
    invented = [{"strategy_id": "magic_learning", "action": "Ação", "topic": "GQM", "reason": "Razão", "evidence": "Evidência", "reference_ids": ["invented"]}]
    monkeypatch.setattr(study_recommendation_agent, "generate_google_recommendation", lambda *_args, **_kwargs: _valid_llm_payload(invented))
    discipline = create_discipline(client)
    body = client.post("/api/agent/study-recommendation", json=recommendation_payload(discipline["id"], pending_topics=[_topic("GQM")])).json()
    assert body["used_fallback"] is True and all(item["strategy_id"] != "magic_learning" for item in body["study_actions"])

def test_invented_reference_for_valid_strategy_triggers_fallback(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-only")
    invented = [{"strategy_id": "retrieval_practice", "action": "Ação", "topic": "GQM", "reason": "Razão", "evidence": "Evidência", "reference_ids": ["invented"]}]
    monkeypatch.setattr(study_recommendation_agent, "generate_google_recommendation", lambda *_args, **_kwargs: _valid_llm_payload(invented))
    discipline = create_discipline(client)
    body = client.post("/api/agent/study-recommendation", json=recommendation_payload(discipline["id"], pending_topics=[_topic("GQM")])).json()
    assert body["used_fallback"] is True

def test_absence_of_topics_does_not_invent_topic(client):
    discipline = create_discipline(client)
    body = client.post("/api/agent/study-recommendation", json=recommendation_payload(discipline["id"], pending_topics=[])).json()
    assert body["study_actions"] == []
    assert "conteúdos cadastrados" in body["missing_information"]

def test_recommendations_never_guarantee_grade_approval_or_mastery(client):
    discipline = create_discipline(client)
    body = client.post("/api/agent/study-recommendation", json=recommendation_payload(discipline["id"], pending_topics=[_topic()])).json()
    text = " ".join(body["recommended_actions"] + [item["reason"] for item in body["study_actions"]]).lower()
    assert not any(term in text for term in ("garante aprovação", "garante nota", "garante domínio"))

def test_agent_logs_do_not_store_prompt_response_or_personal_topic(client, caplog):
    caplog.set_level(logging.INFO, logger="estudaunb.agent")
    discipline = create_discipline(client)
    marker = "CPF-000-NOME-COMPLETO"
    client.post("/api/agent/study-recommendation", json=recommendation_payload(discipline["id"], pending_topics=[_topic(marker)]))
    assert marker not in caplog.text
    assert "contexto seguro" not in caplog.text.lower()
    assert "study_actions" not in caplog.text

def test_llm_promise_of_approval_triggers_safe_fallback(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-only")
    payload = _valid_llm_payload([])
    payload["recommended_actions"] = ["Este método garante aprovação."]
    monkeypatch.setattr(study_recommendation_agent, "generate_google_recommendation", lambda *_args, **_kwargs: payload)
    discipline = create_discipline(client)
    body = client.post("/api/agent/study-recommendation", json=recommendation_payload(discipline["id"], pending_topics=[_topic()])).json()
    assert body["used_fallback"] is True
    assert all("garante aprovação" not in action.lower() for action in body["recommended_actions"])

def test_execution_mode_and_missing_configuration_reason_are_structured(client):
    discipline = create_discipline(client)
    body = client.post("/api/agent/study-recommendation", json=recommendation_payload(discipline["id"])).json()
    assert body["execution_mode"] == "deterministic_fallback"
    assert body["fallback_reason"] == "missing_api_key" and body["model"] is None

def test_configured_valid_llm_is_identified_as_llm(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-only")
    monkeypatch.setattr(study_recommendation_agent, "generate_google_recommendation", lambda *_args, **_kwargs: _valid_llm_payload([]))
    discipline = create_discipline(client)
    body = client.post("/api/agent/study-recommendation", json=recommendation_payload(discipline["id"])).json()
    assert body["execution_mode"] == "llm" and body["provider"] == "google"
    assert body["used_fallback"] is False and body["model"]

def test_timeout_reason_is_returned_and_logged(client, monkeypatch, caplog):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-only")
    def timeout(*_args, **_kwargs): raise TimeoutError("late")
    monkeypatch.setattr(study_recommendation_agent, "generate_google_recommendation", timeout)
    caplog.set_level(logging.INFO, logger="estudaunb.agent")
    discipline = create_discipline(client)
    body = client.post("/api/agent/study-recommendation", json=recommendation_payload(discipline["id"])).json()
    assert body["execution_mode"] == "deterministic_fallback" and body["fallback_reason"] == "timeout"
    assert '"error_type": "timeout"' in caplog.text

def test_complete_hierarchical_context_reaches_configured_agent(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-only")
    captured = {}
    def valid(context, timeout_seconds):
        captured.update(context)
        return _valid_llm_payload([])
    monkeypatch.setattr(study_recommendation_agent, "generate_google_recommendation", valid)
    discipline = create_discipline(client)
    root = client.post(f"/api/disciplines/{discipline['id']}/contents", json={"title": "Ordenação", "status": "in_progress"}).json()
    child = client.post(f"/api/disciplines/{discipline['id']}/contents/{root['id']}/children", json={"title": "Quicksort", "difficulty": "high"}).json()
    proof = client.post(f"/api/disciplines/{discipline['id']}/assessments", json={"name": "P1", "date": str(date.today() + timedelta(days=2)), "weight": 40, "status": "planned"}).json()
    client.put(f"/api/disciplines/{discipline['id']}/assessments/{proof['id']}/content-associations", json={"selections": [{"content_node_id": root["id"], "include_descendants": True}]})
    body = client.post("/api/agent/study-recommendation", json=recommendation_payload(discipline["id"])).json()
    assert body["execution_mode"] == "llm"
    assert captured["content_hierarchy"][0]["children"][0]["id"] == child["id"]
    group = captured["assessment_content_context"][0]
    assert group["assessment_name"] == "P1" and group["assessment_date"]
    inherited = next(item for item in group["nodes"] if item["id"] == child["id"])
    assert inherited["association_origin"] == "inherited" and inherited["difficulty"] == "high"

def test_assistant_fallback_uses_associated_context_and_explains_configuration(client, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    discipline = create_discipline(client)
    content = client.post(f"/api/disciplines/{discipline['id']}/contents", json={"title": "Quicksort", "difficulty": "high"}).json()
    proof = client.post(f"/api/disciplines/{discipline['id']}/assessments", json={"name": "P1", "date": str(date.today() + timedelta(days=2)), "weight": 40, "status": "planned"}).json()
    client.put(f"/api/disciplines/{discipline['id']}/assessments/{proof['id']}/content-associations", json={"selections": [{"content_node_id": content["id"], "include_descendants": False}]})
    body = client.post(f"/api/disciplines/{discipline['id']}/assistant/messages", json={"message": "No que devo focar?", "recent_messages": []}).json()
    assert body["execution_mode"] == "deterministic_fallback" and body["fallback_reason"] == "missing_api_key"
    assert "P1" in body["answer"] and "Quicksort" in body["answer"]
    assert any("associação direta" in evidence for evidence in body["evidence"])
