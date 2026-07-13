from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app import storage
from app.schemas import StudyPlanRequest, StudyPlanResponse
from app.services.academic_calculator import calculate_grade_simulation
from app.services.content_map import agent_content_context
from app.services.study_plan_agent import StudyPlanInputError, StudyPlanOutputError, generate_study_plan

router = APIRouter(prefix="/api/study-plans", tags=["study-plans"])
NOT_FOUND_RESPONSE = {"description": "Disciplina não encontrada."}
VALIDATION_RESPONSE = {"description": "Entrada inválida para geração de plano semanal."}
INTERNAL_RESPONSE = {"description": "Erro interno controlado ao gerar o plano."}


def _normalized_weight(value):
    if value is None:
        return None
    parsed = float(value)
    return parsed / 100 if parsed > 1 else parsed


def _effective_weight(assessment: dict):
    group = _normalized_weight(assessment.get("group_final_weight"))
    internal = _normalized_weight(assessment.get("group_weight"))
    if group is not None and internal is not None:
        return group * internal
    return _normalized_weight(assessment.get("weight"))


@router.post(
    "/generate",
    response_model=StudyPlanResponse,
    summary="Gera plano semanal de estudos",
    description="Gera plano determinístico dentro da disponibilidade e antes dos prazos; o LLM só explica o plano validado.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: INTERNAL_RESPONSE},
)
def generate(payload: StudyPlanRequest) -> StudyPlanResponse:
    try:
        records = []
        for item in storage.list_disciplines():
            assessments = storage.list_assessments(str(item["id"]))
            content_context = agent_content_context(str(item["id"]), assessments)
            assessment_by_id = {assessment["id"]: assessment for assessment in assessments}
            associated_by_node = {}
            for group in content_context["assessment_contents"]:
                assessment = assessment_by_id[group["assessment_id"]]
                for node in group["nodes"]:
                    associated_by_node.setdefault(node["id"], {
                        **node,
                        "assessment_id": group["assessment_id"],
                        "assessment_name": group["assessment_name"],
                        "assessment_date": group["assessment_date"],
                        "effective_weight": _effective_weight(assessment),
                        "evidence": content_context["evidence_by_title"].get(node["title"]),
                    })
            simulation = calculate_grade_simulation(assessments)
            records.append({
                **item,
                "assessments": assessments,
                "associated_contents": list(associated_by_node.values()),
                "partial_average": simulation.get("partial_average"),
            })
        return generate_study_plan(payload, records)
    except StudyPlanInputError as exc:
        message = str(exc)
        if "não encontrada" in message:
            raise HTTPException(status_code=404, detail="Disciplina não encontrada.") from exc
        raise HTTPException(status_code=422, detail=message) from exc
    except StudyPlanOutputError as exc:
        raise HTTPException(status_code=500, detail="Não foi possível validar o plano gerado.") from exc
