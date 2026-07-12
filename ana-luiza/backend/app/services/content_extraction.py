from __future__ import annotations

import json
import logging
import os
import time
from datetime import timedelta
from typing import Any, Callable
from uuid import uuid4

from pydantic import ValidationError

from app import storage
from app.schemas import ContentDraftNode, ContentExtractionPreviewResponse
from app.services import content_map
from app.services.study_recommendation_agent import generate_google_json

logger = logging.getLogger("estudaunb.content_extraction")
PREVIEW_TTL_MINUTES = 15


class ContentExtractionError(ValueError):
    pass


def _duration_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


def _source_lines(plan: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for value in plan.get("contents", []):
        clean = " ".join(str(value).split())
        if clean and clean not in result:
            result.append(clean[:300])
    return result[: content_map.MAX_NODES]


def validate_draft_structure(nodes: list[ContentDraftNode]) -> None:
    if len(nodes) > content_map.MAX_NODES:
        raise ContentExtractionError("A proposta excede o limite de 100 conteúdos.")
    by_id = {node.temporary_id: node for node in nodes}
    if len(by_id) != len(nodes):
        raise ContentExtractionError("Há identificadores temporários duplicados.")
    for node in nodes:
        if node.parent_temporary_id == node.temporary_id:
            raise ContentExtractionError("Um conteúdo não pode ser seu próprio pai.")
        if node.parent_temporary_id and node.parent_temporary_id not in by_id:
            raise ContentExtractionError("A proposta referencia um conteúdo pai inexistente.")
        depth, current, seen = 1, node, set()
        while current.parent_temporary_id:
            if current.temporary_id in seen:
                raise ContentExtractionError("A proposta contém um ciclo.")
            seen.add(current.temporary_id)
            current = by_id[current.parent_temporary_id]
            depth += 1
            if depth > content_map.MAX_DEPTH:
                raise ContentExtractionError("A proposta excede a profundidade máxima de 5 níveis.")


def _local_drafts(lines: list[str]) -> list[ContentDraftNode]:
    return [
        ContentDraftNode(
            temporary_id=f"node-{index}",
            parent_temporary_id=None,
            title=line[:120],
            description=None,
            source_evidence=line,
            confidence=1.0,
            warnings=["Estrutura plana produzida pelo fallback; revise a hierarquia."],
        )
        for index, line in enumerate(lines, 1)
    ]


def _prompt(lines: list[str]) -> str:
    contract = {
        "draft_nodes": [{
            "temporary_id": "node-1",
            "parent_temporary_id": None,
            "title": "título explícito",
            "description": None,
            "source_evidence": "um item literal da lista fornecida",
            "confidence": 0.0,
            "warnings": [],
        }]
    }
    return (
        "Organize somente os conteúdos confirmados abaixo em uma árvore de até 5 níveis. "
        "Não invente tópicos, pré-requisitos, dificuldade, estado, avaliações, datas ou pesos. "
        "source_evidence deve copiar exatamente um item fornecido. Relações não explicitamente "
        "declaradas devem receber aviso de que são apenas proposta para revisão humana. Retorne JSON "
        f"no contrato {json.dumps(contract, ensure_ascii=False)}. Conteúdos confirmados: "
        + json.dumps(lines, ensure_ascii=False)
    )


def _validated_llm_drafts(raw: dict[str, Any], lines: list[str]) -> list[ContentDraftNode]:
    values = raw.get("draft_nodes")
    if not isinstance(values, list):
        raise ContentExtractionError("Resposta do agente sem lista de conteúdos.")
    nodes = [ContentDraftNode.model_validate(value) for value in values]
    validate_draft_structure(nodes)
    allowed = set(lines)
    if any(node.source_evidence not in allowed for node in nodes):
        raise ContentExtractionError("A resposta contém evidência ausente no plano confirmado.")
    if len({node.source_evidence for node in nodes}) > len(lines):
        raise ContentExtractionError("A resposta contém evidência incompatível.")
    return nodes


def build_extraction_preview(
    discipline_id: str,
    llm_generator: Callable[[str, float], dict[str, Any]] | None = None,
) -> ContentExtractionPreviewResponse:
    start = time.perf_counter()
    plan = storage.COURSE_PLANS.get(discipline_id)
    if not plan:
        raise ContentExtractionError("Confirme um plano de ensino antes de extrair conteúdos.")
    lines = _source_lines(plan)
    source, model, used_fallback, fallback_reason = "local_fallback", None, True, None
    warnings: list[str] = []
    drafts: list[ContentDraftNode]
    if not lines:
        drafts = []
        fallback_reason = "no_explicit_content"
        warnings.append("O plano confirmado não contém conteúdos explícitos. Adicione-os manualmente.")
    elif not os.getenv("GOOGLE_API_KEY") or os.getenv("LLM_PROVIDER", "google").lower() != "google":
        drafts = _local_drafts(lines)
        fallback_reason = "missing_api_key"
        warnings.append("A extração inteligente não está configurada; foi gerada uma proposta plana para revisão.")
    else:
        generator = llm_generator or generate_google_json
        try:
            raw = generator(_prompt(lines), max(1.0, float(os.getenv("LLM_TIMEOUT_SECONDS", "8"))))
            drafts = _validated_llm_drafts(raw, lines)
            source, model, used_fallback = "gemini", os.getenv("LLM_MODEL", "gemini-2.5-flash"), False
        except TimeoutError:
            drafts, fallback_reason = _local_drafts(lines), "timeout"
            warnings.append("A extração inteligente excedeu o tempo; foi usada uma proposta local para revisão.")
        except (ContentExtractionError, ValidationError, TypeError, ValueError, KeyError):
            drafts, fallback_reason = _local_drafts(lines), "invalid_response"
            warnings.append("A resposta inteligente não pôde ser validada; foi usada uma proposta local para revisão.")
        except Exception:
            drafts, fallback_reason = _local_drafts(lines), "unavailable"
            warnings.append("A extração inteligente está indisponível; foi usada uma proposta local para revisão.")

    preview_id = str(uuid4())
    expires_at = storage.utc_now() + timedelta(minutes=PREVIEW_TTL_MINUTES)
    latency_ms = _duration_ms(start)
    storage.CONTENT_EXTRACTION_PREVIEWS[preview_id] = {
        "discipline_id": discipline_id,
        "expires_at": expires_at,
        "allowed": {node.temporary_id: node.source_evidence for node in drafts},
    }
    logger.info(
        "content_extraction_preview discipline_id=%s source=%s model=%s latency_ms=%.2f used_fallback=%s fallback_reason=%s node_count=%d",
        discipline_id, source, model, latency_ms, used_fallback, fallback_reason, len(drafts),
    )
    return ContentExtractionPreviewResponse(
        preview_id=preview_id,
        expires_at=expires_at,
        draft_nodes=drafts,
        warnings=warnings,
        source=source,
        model=model,
        used_fallback=used_fallback,
        fallback_reason=fallback_reason,
        latency_ms=latency_ms,
    )


def confirm_extraction_preview(discipline_id: str, preview_id: str, nodes: list[ContentDraftNode]) -> list[dict]:
    preview = storage.get_content_extraction_preview(preview_id)
    if not preview or preview["discipline_id"] != discipline_id:
        raise ContentExtractionError("Pré-visualização expirada ou inexistente.")
    allowed: dict[str, str] = preview["allowed"]
    if any(node.temporary_id not in allowed or node.source_evidence != allowed[node.temporary_id] for node in nodes):
        raise ContentExtractionError("A confirmação contém item ou evidência que não pertence à pré-visualização.")
    validate_draft_structure(nodes)
    if len(storage.CONTENT_NODES.get(discipline_id, {})) + len(nodes) > content_map.MAX_NODES:
        raise ContentExtractionError("A confirmação excede o limite de 100 conteúdos da disciplina.")

    created: list[dict] = []
    real_ids: dict[str, str] = {}
    pending = list(nodes)
    try:
        while pending:
            ready = [node for node in pending if node.parent_temporary_id is None or node.parent_temporary_id in real_ids]
            if not ready:
                raise ContentExtractionError("Não foi possível ordenar a hierarquia proposta.")
            for node in ready:
                record = content_map.create_node(discipline_id, {
                    "parent_id": real_ids.get(node.parent_temporary_id),
                    "title": node.title,
                    "description": node.description,
                    "difficulty": None,
                    "status": "not_started",
                })
                real_ids[node.temporary_id] = record["id"]
                created.append(record)
                pending.remove(node)
    except Exception:
        for record in reversed(created):
            storage.CONTENT_NODES[discipline_id].pop(record["id"], None)
        raise
    storage.delete_content_extraction_preview(preview_id)
    logger.info("content_extraction_confirmed discipline_id=%s preview_id=%s node_count=%d", discipline_id, preview_id, len(created))
    return created
