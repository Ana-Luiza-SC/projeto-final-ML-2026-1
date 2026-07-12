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
    assert "Não foi encontrada" in warnings[0]


def test_empty_text_requires_ocr_fallback():
    with pytest.raises(CoursePlanError):
        parse_course_plan_text("")


def test_ambiguous_assessment_requires_review():
    data, warnings = parse_course_plan_text("Disciplina: TESTE\nAvaliação: Prova sem data")
    assert data.assessments[0].status == "requires_review"
    assert warnings


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
