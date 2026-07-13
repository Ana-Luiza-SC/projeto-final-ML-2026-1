from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from app import storage
from app.services.complexity_analysis import analyze
from app.services.sigaa_components import search_sigaa_component

router = APIRouter(tags=["catalog"])


@router.get("/api/catalog/components/{code}")
def get_component(code: str):
    item = storage.get_catalog_component(code)
    if not item:
        raise HTTPException(404, "Componente ainda não está no catálogo local.")
    return item


@router.post("/api/disciplines/{discipline_id}/catalog-refresh")
def refresh_component(discipline_id: UUID):
    discipline = storage.get_discipline(str(discipline_id))
    if not discipline:
        raise HTTPException(404, "Disciplina não encontrada.")
    response = search_sigaa_component(
        discipline.get("sigaa_code") or discipline["code"],
        force_refresh=True,
    )
    if response.status != "found" or response.component is None:
        raise HTTPException(
            503,
            "O catálogo público está indisponível; os dados cadastrados foram preservados.",
        )
    return storage.attach_sigaa_component(
        str(discipline_id), response.component.model_dump()
    )


@router.post("/api/disciplines/{discipline_id}/complexity-analysis")
def complexity(discipline_id: UUID, reanalyze: bool = Query(False)):
    try:
        return analyze(str(discipline_id), reanalyze)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
