from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import storage
from app.main import app
from app.services.academic_calculator import calculate_grade_simulation
from app.services.course_plan import CoursePlanError, parse_course_plan_text


@pytest.fixture(autouse=True)
def clear():
    storage.DISCIPLINES.clear(); storage.ASSESSMENTS.clear(); storage.ABSENCES.clear()
    storage.COURSE_PLANS.clear(); storage.COURSE_PLAN_PREVIEWS.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def discipline(client):
    return client.post("/api/disciplines", json={"code": "FGA0001", "name": "TESTE", "workload_hours": 30}).json()


PLAN = """Disciplina: TESTE
Código: FGA0001
Semestre: 2026.1
Carga horária: 30
Objetivos:
- Aplicar técnicas
Conteúdos:
- Unidade 1
- Unidade 2
Avaliação: Prova 1 | Data: 20/07/2026 | Peso: 40% | Conteúdos: Unidade 1
Bibliografia:
- Referência A
"""


def test_explicit_course_plan_fields():
    data, warnings = parse_course_plan_text(PLAN)
    assert data.code == "FGA0001"
    assert data.workload_hours == 30
    assert data.assessments[0].name == "Prova 1"
    assert data.assessments[0].weight == 40
    assert data.assessments[0].topics == ["Unidade 1"]
    assert warnings == []


def test_plan_without_assessment_is_explicit():
    data, warnings = parse_course_plan_text("Disciplina: TESTE\nCódigo: FGA0001")
    assert data.assessments == []
    assert "Nenhuma avaliação foi identificada" in warnings[0]


def test_empty_text_requires_ocr_fallback():
    with pytest.raises(CoursePlanError):
        parse_course_plan_text("")


def test_assessment_without_date_is_recognized_and_kept():
    data, warnings = parse_course_plan_text("Disciplina: TESTE\nAvaliação: Prova sem data | Peso: 30% | Conteúdos: Unidade 1")
    assert data.assessments[0].status == "recognized"
    assert data.assessments[0].date is None
    assert "sem data" in warnings[0]


def test_ambiguous_assessment_requires_review():
    data, warnings = parse_course_plan_text("Disciplina: TESTE\nAvaliação: ")
    assert data.assessments[0].status == "requires_review"
    assert any("ambíguas" in item for item in warnings)


def test_future_assessment_without_grade(client, discipline):
    response = client.post(f"/api/disciplines/{discipline['id']}/assessments", json={"name": "P1", "weight": 30, "date": "2026-07-20", "status": "planned"})
    assert response.status_code == 201
    assert response.json()["grade"] is None


def test_completed_assessment_requires_grade(client, discipline):
    response = client.post(f"/api/disciplines/{discipline['id']}/assessments", json={"name": "P1", "weight": 30, "status": "completed"})
    assert response.status_code == 422


def test_transition_to_completed(client, discipline):
    created = client.post(f"/api/disciplines/{discipline['id']}/assessments", json={"name": "P1", "weight": 30}).json()
    response = client.patch(f"/api/disciplines/{discipline['id']}/assessments/{created['id']}", json={"status": "completed", "grade": 8})
    assert response.status_code == 200
    assert response.json()["grade"] == 8


def test_incomplete_weights_warning():
    result = calculate_grade_simulation([{"name": "P1", "weight": None, "grade": None, "status": "planned"}])
    assert any("sem peso" in item for item in result["warnings"])


def test_workload_30_has_exact_75_hour_limit(client, discipline):
    response = client.get(f"/api/disciplines/{discipline['id']}/attendance-summary").json()
    assert response["absence_limit_class_hours"] == 7.5
    assert response["remaining_class_hours"] == 7.5


def test_absence_crud_and_duplicate(client, discipline):
    url = f"/api/disciplines/{discipline['id']}/absences"
    created = client.post(url, json={"date": "2026-07-10", "class_hours": 2}).json()
    assert client.post(url, json={"date": "2026-07-10", "class_hours": 2}).status_code == 409
    assert client.patch(f"{url}/{created['id']}", json={"date": "2026-07-10", "class_hours": 3}).json()["class_hours"] == 3
    assert client.get(f"/api/disciplines/{discipline['id']}/attendance-summary").json()["missed_class_hours"] == 3
    assert client.delete(f"{url}/{created['id']}").status_code == 204


def test_discipline_without_workload_is_unknown(client):
    item = client.post("/api/disciplines", json={"code": "FGA0002", "name": "SEM CARGA"}).json()
    assert client.get(f"/api/disciplines/{item['id']}/attendance-summary").json()["risk_level"] == "unknown"


def test_course_plan_contracts_in_openapi(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/disciplines/{discipline_id}/course-plan/preview" in paths
    assert "/api/disciplines/{discipline_id}/absences" in paths
    assert "/api/disciplines/{discipline_id}/assessments/{assessment_id}" in paths


def test_confirm_rejects_uncertain_course_plan_assessment(client, discipline):
    preview_id = "11111111-1111-1111-1111-111111111111"
    storage.COURSE_PLAN_PREVIEWS[preview_id] = {
        "discipline_id": discipline["id"],
        "expires_at": storage.utc_now() + timedelta(minutes=15),
        "data": {},
    }
    response = client.post(
        f"/api/disciplines/{discipline['id']}/course-plan/confirm",
        json={
            "preview_id": preview_id,
            "data": {
                "code": "FGA0001",
                "name": "TESTE",
                "objectives": [],
                "contents": [],
                "schedule": [],
                "bibliography": [],
                "assessments": [{"name": "Prova incerta", "status": "requires_review"}],
            },
        },
    )
    assert response.status_code == 422
    assert storage.COURSE_PLANS == {}


def test_complete_endpoint_adds_grade_and_recalculates(client, discipline):
    created = client.post(
        f"/api/disciplines/{discipline['id']}/assessments",
        json={"name": "P1", "weight": 40, "date": "2026-07-20", "status": "planned"},
    ).json()
    completed = client.post(
        f"/api/disciplines/{discipline['id']}/assessments/{created['id']}/complete",
        json={"grade": 8.5, "date": "2026-07-20", "topics": ["Unidade 1"]},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    simulation = client.get(f"/api/disciplines/{discipline['id']}/academic-simulation").json()
    assert simulation["completed_weight"] == pytest.approx(0.4)
    assert simulation["partial_average"] == pytest.approx(8.5)


def test_absence_occurrences_drive_academic_simulation(client, discipline):
    client.post(f"/api/disciplines/{discipline['id']}/absences", json={"date": "2026-07-10", "class_hours": 8})
    simulation = client.get(f"/api/disciplines/{discipline['id']}/academic-simulation").json()
    assert simulation["attendance"]["source"] == "absence_occurrences"
    assert simulation["attendance"]["risk_level"] == "high"


def test_study_plan_reports_assessment_priority_influence(client, discipline):
    client.post(
        f"/api/disciplines/{discipline['id']}/assessments",
        json={"name": "P1", "weight": 30, "date": str(date.today() + timedelta(days=3)), "status": "planned"},
    )
    response = client.post(
        "/api/study-plans/generate",
        json={
            "discipline_ids": [discipline["id"]],
            "availability": {"available_hours_per_week": 2, "days_available": ["monday"]},
            "max_session_minutes": 60,
            "priorities": [{"discipline_id": discipline["id"], "priority": 2}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["priority_influences"][0]["assessment_name"] == "P1"
    assert body["priority_influences"][0]["bonus"] == 2


def test_recommendation_reports_structured_evidence(client, discipline, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    client.post(
        f"/api/disciplines/{discipline['id']}/assessments",
        json={"name": "P1", "weight": 30, "date": "2026-07-20", "status": "planned"},
    )
    response = client.post(
        "/api/agent/study-recommendation",
        json={"discipline_id": discipline["id"], "target_average": 5, "pending_topics": [], "user_goal": "priorizar a próxima avaliação"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["used_fallback"] is True
    assert any("avaliações" in item for item in body["used_evidence"])
    assert "P1" in body["influencing_assessments"]


def test_assistant_complete_context_returns_evidence(client, discipline, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    client.post(f"/api/disciplines/{discipline['id']}/assessments", json={"name": "Prova 3", "weight": 50, "date": "2026-07-17", "topics": ["Unidade 1"], "status": "planned"})
    response = client.post(f"/api/disciplines/{discipline['id']}/assistant/messages", json={"message": "No que devo focar esta semana?", "recent_messages": []})
    assert response.status_code == 200
    assert response.json()["source"] == "fallback"
    assert "Prova 3" in response.json()["answer"]
    assert response.json()["evidence"]


def test_assistant_without_assessments_or_plan_is_explicit(client, discipline, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    response = client.post(f"/api/disciplines/{discipline['id']}/assistant/messages", json={"message": "Quais conteúdos devo revisar?", "recent_messages": []})
    assert response.json()["answer"] == "Não há dados suficientes cadastrados para responder com segurança."
    assert response.json()["evidence"] == []


def test_assistant_uses_confirmed_course_plan_content(client, discipline, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    storage.save_course_plan(discipline["id"], {"code": "FGA0001", "name": "TESTE", "contents": ["Grafos"], "schedule": [], "assessments": [], "objectives": [], "bibliography": []})
    response = client.post(f"/api/disciplines/{discipline['id']}/assistant/messages", json={"message": "Quais conteúdos devo revisar?", "recent_messages": []})
    assert "Grafos" in response.json()["answer"]
    assert "plano de ensino confirmado" in response.json()["evidence"][0]


def test_assistant_invalid_gemini_output_uses_fallback(client, discipline, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-only")
    monkeypatch.setattr("app.services.study_recommendation_agent.generate_google_json", lambda *_args, **_kwargs: {"answer": "Inventado", "evidence": []})
    client.post(f"/api/disciplines/{discipline['id']}/assessments", json={"name": "P1", "date": "2026-07-17", "status": "planned"})
    response = client.post(f"/api/disciplines/{discipline['id']}/assistant/messages", json={"message": "Analisar próxima avaliação", "recent_messages": []})
    assert response.json()["source"] == "fallback"
    assert "P1" in response.json()["answer"]


def test_confirm_course_plan_assessment_without_date(client, discipline):
    preview_id = "22222222-2222-2222-2222-222222222222"
    storage.COURSE_PLAN_PREVIEWS[preview_id] = {"discipline_id": discipline["id"], "expires_at": storage.utc_now() + timedelta(minutes=15), "data": {}}
    response = client.post(f"/api/disciplines/{discipline['id']}/course-plan/confirm", json={"preview_id": preview_id, "data": {"code": "FGA0001", "name": "TESTE", "objectives": [], "contents": ["Unidade 1"], "schedule": [], "bibliography": [], "assessments": [{"name": "Prova final", "date": None, "weight": 40, "topics": ["Unidade 1"], "status": "recognized"}]}})
    assert response.status_code == 200
    saved = client.get(f"/api/disciplines/{discipline['id']}/assessments").json()[0]
    assert saved["date"] is None
    assert saved["grade"] is None
    assert saved["status"] == "planned"


def test_define_date_after_confirmation_enables_proximity(client, discipline):
    created = client.post(f"/api/disciplines/{discipline['id']}/assessments", json={"name": "P sem data", "weight": 30, "status": "planned"}).json()
    plan_payload = {"discipline_ids": [discipline["id"]], "availability": {"available_hours_per_week": 2, "days_available": ["monday"]}, "max_session_minutes": 60, "priorities": [{"discipline_id": discipline["id"], "priority": 2}]}
    before = client.post("/api/study-plans/generate", json=plan_payload).json()
    assert before["priority_influences"] == []
    target_date = str(date.today() + timedelta(days=3))
    updated = client.patch(f"/api/disciplines/{discipline['id']}/assessments/{created['id']}", json={"date": target_date})
    assert updated.json()["date"] == target_date
    after = client.post("/api/study-plans/generate", json=plan_payload).json()
    assert after["priority_influences"][0]["assessment_name"] == "P sem data"


def test_assistant_reports_undated_assessment_without_inventing_date(client, discipline, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    client.post(f"/api/disciplines/{discipline['id']}/assessments", json={"name": "Prova sem data", "weight": 30, "source": "course_plan", "status": "planned"})
    response = client.post(f"/api/disciplines/{discipline['id']}/assistant/messages", json={"message": "Qual é a próxima avaliação?", "recent_messages": []}).json()
    assert response["answer"] == "Foi identificada uma avaliação no plano de ensino, mas a data ainda não foi informada."
    assert "data não informada" in response["evidence"][0]
    assert "2026" not in response["answer"]


def test_future_assessment_without_date_does_not_change_current_average(client, discipline):
    response = client.post(f"/api/disciplines/{discipline['id']}/assessments", json={"name": "Atividade futura", "weight": 25, "status": "planned"})
    assert response.status_code == 201
    simulation = client.get(f"/api/disciplines/{discipline['id']}/academic-simulation").json()
    assert simulation["partial_average"] is None
    assert simulation["current_contribution"] == 0

QUALITY_EVALUATION_TEXT = """[PAGE 6]
AVALIAÇÃO
Avaliação Individual — AI: 40%
Testes de Avaliação Individual — mTAI: 60%
Teste de Avaliação Final — TAF: 40%
Avaliação em Equipe — AE: 45%
Entrega 1 — AE1: 10%
Entrega 2 — AE2: 30%
Entrega 3 — AE3: 45%
Ponto de Controle 2 — PC2: 5%
Ponto de Controle 3 — PC3: 10%
[PAGE 7]
Avaliação Cruzada — AC: 15%
Avaliação Cruzada Individual — AC: 100%
[PAGE 9]
O cronograma dos eventos deve ser consultado no Aprender 3.
"""


def test_quality_plan_extracts_three_groups_and_eight_components():
    data, warnings = parse_course_plan_text(QUALITY_EVALUATION_TEXT)
    assert [(group.code, group.final_weight) for group in data.evaluation_groups] == [("AI", 40), ("AE", 45), ("AC", 15)]
    assert len(data.assessments) == 8
    assert all(item.date is None and item.requires_date for item in data.assessments)
    assert {item.code: item.group_weight for item in data.assessments if item.code != "AC"} == {"mTAI": 60, "TAF": 40, "AE1": 10, "AE2": 30, "AE3": 45, "PC2": 5, "PC3": 10}
    assert "Aprender 3" in data.schedule[0]
    assert any("8 componente" in warning for warning in warnings)


def test_hierarchical_grade_uses_internal_then_final_weight():
    result = calculate_grade_simulation([
        {"name": "mTAI", "grade": 8, "group_final_weight": 40, "group_weight": 60, "status": "completed"},
        {"name": "TAF", "grade": 6, "group_final_weight": 40, "group_weight": 40, "status": "completed"},
    ])
    assert result["completed_weight"] == pytest.approx(.4)
    assert result["current_contribution"] == pytest.approx(2.88)
    assert result["partial_average"] == pytest.approx(7.2)


def test_taf_uses_16_percent_global_weight_and_expected_projection():
    result = calculate_grade_simulation([
        {"name": "TAF", "code": "TAF", "grade": 8.9, "group_final_weight": 40, "group_weight": 40, "evaluation_group_code": "AI", "evaluation_group_name": "Avaliação Individual", "status": "completed"},
        {"name": "mTAI", "code": "mTAI", "grade": None, "group_final_weight": 40, "group_weight": 60, "evaluation_group_code": "AI", "evaluation_group_name": "Avaliação Individual", "status": "planned"},
    ])
    assert result["current_contribution"] == pytest.approx(1.424)
    assert result["completed_weight"] == pytest.approx(.16)
    assert result["remaining_weight"] == pytest.approx(.84)
    assert result["partial_average"] == pytest.approx(8.9)
    assert result["required_average_on_remaining"] == pytest.approx(4.257142857)
    assert result["group_results"][0]["status"] == "insufficient_data"


def test_mtai_and_items_from_different_groups_keep_effective_weights():
    result = calculate_grade_simulation([
        {"name": "mTAI", "grade": 10, "group_final_weight": 40, "group_weight": 60, "evaluation_group_code": "AI", "status": "completed"},
        {"name": "AE1", "grade": 8, "group_final_weight": 45, "group_weight": 10, "evaluation_group_code": "AE", "status": "completed"},
        {"name": "futura", "grade": None, "group_final_weight": 15, "group_weight": 100, "evaluation_group_code": "AC", "status": "planned"},
    ])
    assert result["completed_weight"] == pytest.approx(.285)
    assert result["current_contribution"] == pytest.approx(2.76)
