from __future__ import annotations

import os
import tempfile
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas import MatriculaImportConfirmRequest, MatriculaImportConfirmResponse, MatriculaPdfPreviewResponse
from app.services.matricula_import import (
    ImportPreviewNotFoundError,
    ImportValidationError,
    MAX_PDF_BYTES,
    build_preview_from_pdf,
    confirm_import,
)
from app.services.sigaa_components import search_sigaa_component

router = APIRouter(prefix="/api/import/matricula-pdf", tags=["matricula-import"])

VALIDATION_RESPONSE = {"description": "Arquivo ou payload invalido."}
NOT_FOUND_RESPONSE = {"description": "Pre-visualizacao expirada ou inexistente."}


def _sigaa_lookup_enabled() -> bool:
    return os.getenv("MATRICULA_IMPORT_SIGAA_LOOKUP", "false").strip().lower() in {"1", "true", "yes", "on"}


@router.post(
    "/preview",
    response_model=MatriculaPdfPreviewResponse,
    tags=["matricula-import"],
    summary="Gera pre-visualizacao de disciplinas a partir do comprovante de matricula",
    description="Valida e processa um PDF localmente, sem cadastrar disciplinas antes da confirmacao explicita.",
    responses={422: VALIDATION_RESPONSE},
)
async def preview_matricula_pdf(file: UploadFile = File(...)) -> MatriculaPdfPreviewResponse:
    content_type = (file.content_type or "").lower()
    if content_type and content_type != "application/pdf":
        raise HTTPException(status_code=422, detail="Envie um arquivo PDF valido.")

    suffix = ".pdf" if (file.filename or "").lower().endswith(".pdf") else ".upload"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="estudaunb-import-", suffix=suffix, delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            total = 0
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_PDF_BYTES:
                    raise HTTPException(status_code=422, detail="Arquivo PDF acima do limite permitido.")
                temp_file.write(chunk)
        if temp_path.stat().st_size == 0:
            raise HTTPException(status_code=422, detail="Arquivo PDF vazio.")
        lookup = search_sigaa_component if _sigaa_lookup_enabled() else None
        return build_preview_from_pdf(temp_path, sigaa_lookup=lookup)
    except HTTPException:
        raise
    except ImportValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Nao foi possivel processar o PDF de matricula.") from exc
    finally:
        await file.close()
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


@router.post(
    "/confirm",
    response_model=MatriculaImportConfirmResponse,
    tags=["matricula-import"],
    summary="Confirma cadastro em lote de itens revisados",
    description="Cadastra somente os itens selecionados de uma pre-visualizacao valida, com relatorio por item.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE},
)
def confirm_matricula_import(payload: MatriculaImportConfirmRequest) -> MatriculaImportConfirmResponse:
    try:
        return confirm_import(payload)
    except ImportPreviewNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ImportValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Nao foi possivel confirmar a importacao.") from exc
