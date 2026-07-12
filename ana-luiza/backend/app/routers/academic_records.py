from __future__ import annotations

from uuid import UUID
from fastapi import APIRouter, HTTPException, Response

from app import storage
from app.schemas import AbsenceCreate, AbsenceRead, AssessmentRead, AssessmentUpdate, AttendanceSummary

router = APIRouter(prefix="/api/disciplines/{discipline_id}", tags=["academic-records"])


def ensure(discipline_id: UUID) -> dict:
    item = storage.get_discipline(str(discipline_id))
    if item is None:
        raise HTTPException(404, "Disciplina não encontrada.")
    return item


@router.get("/assessments", response_model=list[AssessmentRead])
def list_assessments(discipline_id: UUID):
    ensure(discipline_id)
    return storage.list_assessments(str(discipline_id))


@router.patch("/assessments/{assessment_id}", response_model=AssessmentRead)
def update_assessment(discipline_id: UUID, assessment_id: UUID, payload: AssessmentUpdate):
    ensure(discipline_id)
    current = storage.get_assessment(str(discipline_id), str(assessment_id))
    if current is None:
        raise HTTPException(404, "Avaliação não encontrada.")
    merged = {**current, **payload.model_dump(exclude_unset=True)}
    if merged.get("status") == "planned" and merged.get("grade") is not None:
        raise HTTPException(422, "Avaliação planejada não pode ter nota.")
    if merged.get("status") == "completed" and merged.get("grade") is None:
        raise HTTPException(422, "Avaliação realizada exige nota.")
    return storage.update_assessment(str(discipline_id), str(assessment_id), payload.model_dump(exclude_unset=True))


@router.delete("/assessments/{assessment_id}", status_code=204)
def delete_assessment(discipline_id: UUID, assessment_id: UUID):
    ensure(discipline_id)
    if not storage.delete_assessment(str(discipline_id), str(assessment_id)):
        raise HTTPException(404, "Avaliação não encontrada.")
    return Response(status_code=204)


@router.get("/absences", response_model=list[AbsenceRead])
def list_absences(discipline_id: UUID):
    ensure(discipline_id)
    return storage.list_absences(str(discipline_id))


@router.post("/absences", response_model=AbsenceRead, status_code=201)
def add_absence(discipline_id: UUID, payload: AbsenceCreate):
    ensure(discipline_id)
    try:
        return storage.add_absence(str(discipline_id), payload.model_dump(mode="json"))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.patch("/absences/{absence_id}", response_model=AbsenceRead)
def update_absence(discipline_id: UUID, absence_id: UUID, payload: AbsenceCreate):
    ensure(discipline_id)
    try:
        item = storage.update_absence(str(discipline_id), str(absence_id), payload.model_dump(mode="json"))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    if item is None:
        raise HTTPException(404, "Falta não encontrada.")
    return item


@router.delete("/absences/{absence_id}", status_code=204)
def delete_absence(discipline_id: UUID, absence_id: UUID):
    ensure(discipline_id)
    if not storage.delete_absence(str(discipline_id), str(absence_id)):
        raise HTTPException(404, "Falta não encontrada.")
    return Response(status_code=204)


@router.get("/attendance-summary", response_model=AttendanceSummary)
def attendance_summary(discipline_id: UUID):
    discipline = ensure(discipline_id)
    workload = discipline.get("workload_hours") or discipline.get("total_class_hours")
    missed = sum(float(item["class_hours"]) for item in storage.list_absences(str(discipline_id)))
    if workload is None:
        return {"workload_class_hours": None, "missed_class_hours": missed, "absence_limit_class_hours": None, "remaining_class_hours": None, "frequency": None, "absence_percentage": None, "risk_level": "unknown", "warnings": ["Cadastre a carga horária em horas-aula para calcular a frequência."]}
    workload = float(workload)
    if missed > workload:
        raise HTTPException(400, "Faltas não podem superar a carga horária.")
    absence = missed / workload
    risk = "high" if absence > .25 else "medium" if absence > .15 else "low"
    warnings = ["Frequência abaixo de 75%; há risco de reprovação por falta."] if risk == "high" else ["Faltas próximas do limite de 25%."] if risk == "medium" else []
    limit = workload * .25
    return {"workload_class_hours": workload, "missed_class_hours": missed, "absence_limit_class_hours": limit, "remaining_class_hours": limit - missed, "frequency": 1 - absence, "absence_percentage": absence, "risk_level": risk, "warnings": warnings}
