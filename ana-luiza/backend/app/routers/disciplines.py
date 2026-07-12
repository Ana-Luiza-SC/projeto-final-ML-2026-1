from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app import storage
from app.schemas import (
    AcademicSimulation,
    AssessmentCreate,
    AssessmentRead,
    AttendanceUpdate,
    DisciplineCreate,
    DisciplineRead,
)
from app.services.academic_calculator import (
    calculate_attendance,
    calculate_grade_simulation,
    classify_academic_status,
)

router = APIRouter(prefix="/api/disciplines")

NOT_FOUND_RESPONSE = {"description": "Disciplina não encontrada."}
VALIDATION_RESPONSE = {"description": "Entrada inválida, como nota fora de 0 a 10, peso inválido ou faltas maiores que o total."}
INSUFFICIENT_DATA_RESPONSE = {"description": "Dados insuficientes para simulação completa; a resposta inclui warnings."}



def _attendance_from_absences(discipline_id: UUID, discipline: dict) -> dict:
    workload = discipline.get("workload_hours") or discipline.get("total_class_hours")
    missed = sum(float(item["class_hours"]) for item in storage.list_absences(str(discipline_id)))
    if workload is not None:
        workload = float(workload)
        if workload <= 0:
            raise ValueError("Carga horária deve ser positiva.")
        if missed > workload:
            raise ValueError("Faltas não podem superar a carga horária.")
        absence_percentage = missed / workload
        risk = "high" if absence_percentage > 0.25 else "medium" if absence_percentage > 0.15 else "low"
        status = "risk_of_failure_by_attendance" if risk == "high" else "attention" if risk == "medium" else "ok"
        warnings = ["Frequência abaixo de 75%; há risco de reprovação por falta."] if risk == "high" else ["Faltas próximas do limite de 25%."] if risk == "medium" else []
        return {"status": status, "source": "absence_occurrences", "frequency": 1 - absence_percentage, "absence_percentage": absence_percentage, "risk_level": risk, "warnings": warnings}
    return calculate_attendance(
        total_classes=discipline.get("total_classes"),
        missed_classes=discipline.get("missed_classes"),
        total_class_hours=discipline.get("total_class_hours"),
        missed_class_hours=discipline.get("missed_class_hours"),
    )

def _ensure_discipline(discipline_id: UUID) -> dict:
    discipline = storage.get_discipline(str(discipline_id))
    if discipline is None:
        raise HTTPException(status_code=404, detail="Disciplina não encontrada.")
    return discipline


@router.post(
    "",
    response_model=DisciplineRead,
    status_code=201,
    tags=["disciplines"],
    summary="Cria disciplina manualmente",
    description="Cadastra uma disciplina informada pelo estudante, sem depender de PDF ou SIGAA.",
    responses={422: VALIDATION_RESPONSE},
)
def create_discipline(payload: DisciplineCreate) -> dict:
    return storage.create_discipline(payload.model_dump())


@router.get(
    "",
    response_model=list[DisciplineRead],
    tags=["disciplines"],
    summary="Lista disciplinas",
    description="Retorna todas as disciplinas cadastradas no armazenamento em memória.",
)
def list_disciplines() -> list[dict]:
    return storage.list_disciplines()


@router.get(
    "/{discipline_id}",
    response_model=DisciplineRead,
    tags=["disciplines"],
    summary="Obtém uma disciplina",
    description="Retorna os dados básicos de uma disciplina cadastrada.",
    responses={404: NOT_FOUND_RESPONSE},
)
def get_discipline(discipline_id: UUID) -> dict:
    return _ensure_discipline(discipline_id)


@router.patch(
    "/{discipline_id}/attendance",
    response_model=DisciplineRead,
    tags=["attendance"],
    summary="Atualiza faltas e frequência",
    description="Atualiza total de aulas/horas e faltas registradas para cálculo determinístico de frequência.",
    responses={400: VALIDATION_RESPONSE, 404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE},
)
def update_attendance(discipline_id: UUID, payload: AttendanceUpdate) -> dict:
    _ensure_discipline(discipline_id)
    try:
        updated = storage.update_attendance(
            str(discipline_id), payload.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="Disciplina não encontrada.")
    return updated


@router.post(
    "/{discipline_id}/assessments",
    response_model=AssessmentRead,
    status_code=201,
    tags=["assessments"],
    summary="Adiciona avaliação",
    description="Cadastra avaliação com nome, peso, nota opcional, data opcional e tópicos relacionados.",
    responses={400: VALIDATION_RESPONSE, 404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE},
)
def add_assessment(discipline_id: UUID, payload: AssessmentCreate) -> dict:
    _ensure_discipline(discipline_id)
    assessment = storage.add_assessment(str(discipline_id), payload.model_dump())
    if assessment is None:
        raise HTTPException(status_code=404, detail="Disciplina não encontrada.")
    return assessment


@router.get(
    "/{discipline_id}/academic-simulation",
    response_model=AcademicSimulation,
    tags=["academic-simulation"],
    summary="Calcula simulação acadêmica",
    description=(
        "Calcula média parcial, contribuição atual, nota necessária, menção, frequência, "
        "risco por nota, risco por falta e situação acadêmica resumida. O cálculo é determinístico."
    ),
    responses={
        200: INSUFFICIENT_DATA_RESPONSE,
        400: VALIDATION_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        422: VALIDATION_RESPONSE,
    },
)
def academic_simulation(
    discipline_id: UUID,
    target_average: float = Query(
        default=5.0,
        ge=0,
        le=10,
        description="Média alvo para calcular a nota necessária nas avaliações restantes.",
    ),
) -> dict:
    discipline = _ensure_discipline(discipline_id)
    assessments = storage.list_assessments(str(discipline_id))
    try:
        grade_result = calculate_grade_simulation(assessments, target_average)
        attendance = _attendance_from_absences(discipline_id, discipline)
        academic_status = classify_academic_status(grade_result, attendance)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    warnings = grade_result["warnings"]
    return {
        **grade_result,
        "attendance": attendance,
        "academic_status": academic_status,
        "warnings": warnings,
    }
