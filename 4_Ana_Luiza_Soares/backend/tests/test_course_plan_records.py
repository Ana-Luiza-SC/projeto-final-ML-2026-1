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


def test_fga0002_fixture_extracts_full_course_plan():
    from pathlib import Path
    from app.services.course_plan import extract_pdf_text_details

    pdf = Path(__file__).resolve().parents[2] / "pdf_exemple" / "plano_ensino_fga0002.pdf"
    extracted = extract_pdf_text_details(pdf)
    data, warnings = parse_course_plan_text(extracted.layout_text or extracted.text)

    assert data.code == "FGA0002"
    assert data.name == "QUALIDADE DE SOFTWARE"
    assert data.semester == "2026.1"
    assert data.workload_hours == 60
    assert len(data.objectives) == 4
    assert "Diferenciar qualidade de produto" in data.objectives[0]
    assert len(data.contents) >= 5
    assert all(f"Unidade {index}" in data.contents[index - 1] for index in range(1, 6))
    assert len(data.schedule) == 6
    assert data.schedule[0].startswith("16/03-10/04")
    assert len(data.bibliography) == 3
    assert [item.name for item in data.assessments] == [
        "Questionário de fundamentos",
        "Plano GQM",
        "Prova parcial",
        "Relatório de avaliação",
        "Apresentação final",
    ]
    assert [item.date.isoformat() if item.date else None for item in data.assessments] == [
        "2026-04-14",
        "2026-05-19",
        "2026-06-09",
        "2026-07-14",
        "2026-07-16",
    ]
    assert [item.weight for item in data.assessments] == [10, 20, 20, 30, 20]
    assert sum(item.weight or 0 for item in data.assessments) == 100
    assert data.assessments[-1].associated_content == "Síntese da avaliação"
    assert all(item.status == "recognized" for item in data.assessments)
    assert warnings == []


def test_flattened_assessment_table_with_decimal_comma_and_missing_date():
    text = """
Código: FGA9999
Componente curricular: TESTE
Carga horária: 60 horas
5. Avaliação da aprendizagem
Avaliação
Modalidade
Data
Peso
Conteúdo associado
Prova com vírgula
Individual
10/05/2026
12,5%
Unidade 1
Entrega sem data
Grupo
20%
Unidade 2
6. Cronograma sintético
"""

    data, warnings = parse_course_plan_text(text)

    assert [item.name for item in data.assessments] == ["Prova com vírgula", "Entrega sem data"]
    assert data.assessments[0].weight == 12.5
    assert data.assessments[1].date is None
    assert data.assessments[1].requires_date is True
    assert data.assessments[1].associated_content == "Unidade 2"
    assert any("sem data" in warning for warning in warnings)


def test_decorative_pdf_artifacts_are_ignored():
    text = """
Código: FGA9999
Componente curricular: TESTE
E
T
S
Í
C
FI
O
I
2. Objetivos de aprendizagem
1. Aplicar testes.
3. Conteúdo programático
Unidade 1 - Fundamentos
E
T
4. Metodologia de ensino
5. Avaliação da aprendizagem
Prova Individual 10/05/2026 100% Unidade 1
6. Cronograma sintético
"""

    data, _ = parse_course_plan_text(text)

    assert data.objectives == ["Aplicar testes."]
    assert data.contents == ["Unidade 1 - Fundamentos"]
    assert data.assessments[0].name == "Prova"


def test_malformed_flattened_table_returns_no_invented_assessment():
    text = """
Código: FGA9999
Componente curricular: TESTE
5. Avaliação da aprendizagem
Avaliação
Modalidade
Data
Peso
Conteúdo associado
Prova sem peso
Individual
10/05/2026
Unidade 1
6. Cronograma sintético
"""

    data, warnings = parse_course_plan_text(text)

    assert data.assessments == []
    assert any("Nenhuma avaliação" in warning for warning in warnings)


def _fake_pdf_text():
    from app.services.course_plan import ExtractedPdfText
    return ExtractedPdfText(
        text="Código: FGA0002\nComponente curricular: QUALIDADE DE SOFTWARE\n5. Avaliação da aprendizagem\nProva Individual 10/05/2026 100% Unidade 1\n6. Cronograma sintético",
        layout_text="Código: FGA0002\nComponente curricular: QUALIDADE DE SOFTWARE\n5. Avaliação da aprendizagem\nProva Individual 10/05/2026 100% Unidade 1\n6. Cronograma sintético",
        page_count=1,
    )


def _preview_with_provider(monkeypatch, tmp_path, provider):
    from app.services import course_plan
    monkeypatch.setenv("GOOGLE_API_KEY", "test-only")
    monkeypatch.setenv("LLM_PROVIDER", "google")
    monkeypatch.setenv("LLM_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "20")
    monkeypatch.setattr(course_plan, "extract_pdf_text_details", lambda _path: _fake_pdf_text())
    monkeypatch.setattr(course_plan, "generate_google_json", provider)
    pdf = tmp_path / "plano.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    return course_plan.build_preview(pdf, "discipline-id", filename="plano.pdf")


def test_intelligent_extraction_success_with_mocked_provider(monkeypatch, tmp_path):
    def provider(prompt, timeout):
        assert "Código: FGA0002" in prompt
        assert timeout == 20
        return {
            "code": "FGA0002",
            "name": "QUALIDADE DE SOFTWARE",
            "semester": "2026.1",
            "workload_hours": 60,
            "objectives": [],
            "contents": [],
            "schedule": [],
            "evaluation_groups": [],
            "assessments": [{"name": "Prova", "date": "2026-05-10", "weight": 100, "associated_content": "Unidade 1", "topics": ["Unidade 1"], "status": "recognized"}],
            "bibliography": [],
        }

    response = _preview_with_provider(monkeypatch, tmp_path, provider)

    assert response.source == "gemini"
    assert response.model == "gemini-2.5-flash"
    assert response.fallback_reason is None
    assert response.data.assessments[0].associated_content == "Unidade 1"


@pytest.mark.parametrize(
    ("provider", "reason"),
    [
        (lambda _prompt, _timeout: (_ for _ in ()).throw(TimeoutError("llm_timeout")), "provider_timeout"),
        (lambda _prompt, _timeout: (_ for _ in ()).throw(RuntimeError("provider_error")), "provider_error"),
        (lambda _prompt, _timeout: "```json\n{not-json}\n```", "invalid_json"),
        (lambda _prompt, _timeout: [], "invalid_structured_response"),
        (lambda _prompt, _timeout: {"assessments": [{"name": "X", "weight": 999}]}, "schema_validation_error"),
    ],
)
def test_intelligent_extraction_failures_fall_back_safely(monkeypatch, tmp_path, provider, reason):
    response = _preview_with_provider(monkeypatch, tmp_path, provider)

    assert response.source == "local_parser"
    assert response.model is None
    assert response.fallback_reason == reason
    assert response.data.code == "FGA0002"
    assert response.data.assessments[0].name == "Prova"
    assert any("parser local" in warning for warning in response.warnings)


def test_pdf_with_no_recognizable_evaluations_warns():
    data, warnings = parse_course_plan_text("Código: FGA0001\nComponente curricular: TESTE\n2. Objetivos de aprendizagem\n1. Aprender.")

    assert data.assessments == []
    assert any("Nenhuma avaliação" in warning for warning in warnings)


def test_preview_does_not_store_raw_pdf_or_extracted_text(monkeypatch, tmp_path):
    from app.services import course_plan
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(course_plan, "extract_pdf_text_details", lambda _path: _fake_pdf_text())
    pdf = tmp_path / "plano.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    response = course_plan.build_preview(pdf, "discipline-id", filename="plano.pdf")
    stored = storage.COURSE_PLAN_PREVIEWS[str(response.preview_id)]

    assert "pdf_text" not in stored
    assert "raw_pdf" not in stored
    assert "file" not in stored
    assert stored["data"]["code"] == "FGA0002"
