from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app import storage
from app.schemas import StudyRecommendationRequest, StudyRecommendationResponse
from app.services.academic_calculator import (
    calculate_attendance,
    calculate_grade_simulation,
    classify_academic_status,
)
from app.services.study_recommendation_agent import generate_study_recommendation

router = APIRouter(prefix="/api/agent", tags=["agent"])

NOT_FOUND_RESPONSE = {"description": "Disciplina não encontrada."}
VALIDATION_RESPONSE = {"description": "Entrada inválida ou pedido fora do escopo acadêmico."}


def _is_forbidden_goal(user_goal: str | None) -> bool:
    if not user_goal:
        return False
    text = user_goal.lower()
    professor_terms = ["professor", "docente"]
    evaluation_terms = ["fácil", "facil", "difícil", "dificil", "bom", "ruim", "avaliar"]
    failure_rate_terms = ["taxa de reprovação", "reprovação por professor", "historico de reprovação", "histórico de reprovação"]
    return (
        any(term in text for term in professor_terms) and any(term in text for term in evaluation_terms)
    ) or any(term in text for term in failure_rate_terms)


@router.post(
    "/study-recommendation",
    response_model=StudyRecommendationResponse,
    summary="Gera recomendação de estudo",
    description=(
        "Gera uma recomendação de dedicação e ações de estudo usando a simulação acadêmica "
        "determinística como contexto. Se o Google/Gemini não estiver configurado ou falhar, "
        "usa fallback determinístico por regras."
    ),
    responses={404: NOT_FOUND_RESPONSE, 400: VALIDATION_RESPONSE, 422: VALIDATION_RESPONSE},
)
def study_recommendation(payload: StudyRecommendationRequest) -> StudyRecommendationResponse:
    if _is_forbidden_goal(payload.user_goal):
        raise HTTPException(
            status_code=400,
            detail="Pedido fora do escopo: o sistema não avalia professor nem taxa de reprovação sem fonte.",
        )

    discipline = storage.get_discipline(str(payload.discipline_id))
    if discipline is None:
        raise HTTPException(status_code=404, detail="Disciplina não encontrada.")

    assessments = storage.list_assessments(str(payload.discipline_id))
    try:
        grade_result = calculate_grade_simulation(assessments, payload.target_average)
        attendance = calculate_attendance(
            total_classes=discipline.get("total_classes"),
            missed_classes=discipline.get("missed_classes"),
            total_class_hours=discipline.get("total_class_hours"),
            missed_class_hours=discipline.get("missed_class_hours"),
        )
        academic_status = classify_academic_status(grade_result, attendance)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    warnings = list(
        dict.fromkeys(
            grade_result["warnings"]
            + attendance["warnings"]
            + academic_status["warnings"]
        )
    )
    simulation = {
        **grade_result,
        "attendance": attendance,
        "academic_status": academic_status,
        "warnings": warnings,
    }
    return generate_study_recommendation(
        discipline=discipline,
        simulation=simulation,
        pending_topics=payload.pending_topics,
        user_goal=payload.user_goal,
    )
