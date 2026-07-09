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

router = APIRouter(prefix="/api/disciplines", tags=["disciplines"])


def _ensure_discipline(discipline_id: UUID) -> dict:
    discipline = storage.get_discipline(str(discipline_id))
    if discipline is None:
        raise HTTPException(status_code=404, detail="Disciplina não encontrada.")
    return discipline


@router.post("", response_model=DisciplineRead, status_code=201)
def create_discipline(payload: DisciplineCreate) -> dict:
    return storage.create_discipline(payload.model_dump())


@router.get("", response_model=list[DisciplineRead])
def list_disciplines() -> list[dict]:
    return storage.list_disciplines()


@router.get("/{discipline_id}", response_model=DisciplineRead)
def get_discipline(discipline_id: UUID) -> dict:
    return _ensure_discipline(discipline_id)


@router.patch("/{discipline_id}/attendance", response_model=DisciplineRead)
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


@router.post("/{discipline_id}/assessments", response_model=AssessmentRead, status_code=201)
def add_assessment(discipline_id: UUID, payload: AssessmentCreate) -> dict:
    _ensure_discipline(discipline_id)
    assessment = storage.add_assessment(str(discipline_id), payload.model_dump())
    if assessment is None:
        raise HTTPException(status_code=404, detail="Disciplina não encontrada.")
    return assessment


@router.get("/{discipline_id}/academic-simulation", response_model=AcademicSimulation)
def academic_simulation(
    discipline_id: UUID,
    target_average: float = Query(default=5.0, ge=0, le=10),
) -> dict:
    discipline = _ensure_discipline(discipline_id)
    assessments = storage.list_assessments(str(discipline_id))
    try:
        grade_result = calculate_grade_simulation(assessments, target_average)
        attendance = calculate_attendance(
            total_classes=discipline.get("total_classes"),
            missed_classes=discipline.get("missed_classes"),
            total_class_hours=discipline.get("total_class_hours"),
            missed_class_hours=discipline.get("missed_class_hours"),
        )
        academic_status = classify_academic_status(grade_result, attendance)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    warnings = list(dict.fromkeys(grade_result["warnings"] + attendance["warnings"] + academic_status["warnings"]))
    return {
        **grade_result,
        "attendance": attendance,
        "academic_status": academic_status,
        "warnings": warnings,
    }
