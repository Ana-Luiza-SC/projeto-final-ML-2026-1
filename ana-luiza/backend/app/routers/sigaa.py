from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app import storage
from app.schemas import DisciplineRead, SigaaComponentAttachRequest, SigaaComponentSearchResponse
from app.services.sigaa_components import search_sigaa_component

router = APIRouter(tags=["sigaa"])

NOT_FOUND_RESPONSE = {"description": "Disciplina não encontrada."}
VALIDATION_RESPONSE = {"description": "Entrada inválida."}


@router.get(
    "/api/sigaa/components/search",
    response_model=SigaaComponentSearchResponse,
    summary="Busca componente curricular público do SIGAA",
    description=(
        "Consulta a fonte pública de componentes curriculares do SIGAA/UnB por código ou nome. "
        "A consulta é best-effort e retorna fallback amigável quando a fonte não responde ou não encontra dados."
    ),
    responses={422: VALIDATION_RESPONSE},
)
def search_component(
    query: str = Query(..., min_length=1, description="Código ou nome do componente curricular.")
) -> SigaaComponentSearchResponse:
    response = search_sigaa_component(query)
    if response.status == "found" and response.component is not None:
        storage.upsert_catalog_component(response.component.model_dump())
    return response


@router.patch(
    "/api/disciplines/{discipline_id}/sigaa-component",
    response_model=DisciplineRead,
    summary="Associa dados públicos do SIGAA à disciplina",
    description=(
        "Associa a uma disciplina cadastrada os dados públicos encontrados no SIGAA, "
        "preservando os campos manuais e atualizando apenas metadados acadêmicos públicos."
    ),
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE},
)
def attach_component(discipline_id: UUID, payload: SigaaComponentAttachRequest) -> dict:
    updated = storage.attach_sigaa_component(str(discipline_id), payload.component.model_dump())
    if updated is None:
        raise HTTPException(status_code=404, detail="Disciplina não encontrada.")
    return updated
