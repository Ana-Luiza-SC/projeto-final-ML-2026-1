from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app import storage
from app.schemas import StudyPlanRequest, StudyPlanResponse
from app.services.study_plan_agent import (
    StudyPlanInputError,
    StudyPlanOutputError,
    generate_study_plan,
)

router = APIRouter(prefix="/api/study-plans", tags=["study-plans"])

NOT_FOUND_RESPONSE = {"description": "Disciplina não encontrada."}
VALIDATION_RESPONSE = {"description": "Entrada inválida para geração de plano semanal."}
INTERNAL_RESPONSE = {"description": "Erro interno controlado ao gerar o plano."}


@router.post(
    "/generate",
    response_model=StudyPlanResponse,
    summary="Gera plano semanal de estudos",
    description=(
        "Gera um plano semanal com algoritmo determinístico a partir das disciplinas cadastradas, "
        "disponibilidade, duração máxima e prioridades. O LLM é opcional e só pode explicar o plano."
    ),
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: INTERNAL_RESPONSE},
)
def generate(payload: StudyPlanRequest) -> StudyPlanResponse:
    try:
        return generate_study_plan(payload, storage.list_disciplines())
    except StudyPlanInputError as exc:
        message = str(exc)
        if "não encontrada" in message:
            raise HTTPException(status_code=404, detail="Disciplina não encontrada.") from exc
        raise HTTPException(status_code=422, detail=message) from exc
    except StudyPlanOutputError as exc:
        raise HTTPException(status_code=500, detail="Não foi possível validar o plano gerado.") from exc
