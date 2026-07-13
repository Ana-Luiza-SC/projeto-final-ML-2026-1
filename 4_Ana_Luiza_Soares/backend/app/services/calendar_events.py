from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import date, datetime, time as dt_time, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from app import storage
from app.schemas import CalendarDraftEvent, CalendarExtractionPreviewResponse

logger = logging.getLogger("estudaunb.calendar")
TZ = ZoneInfo("America/Sao_Paulo")
DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")


class CalendarExtractionError(ValueError):
    pass


def _now_ms() -> float:
    return time.perf_counter() * 1000


def _duration_ms(start: float) -> float:
    return round(_now_ms() - start, 2)


def _log(event: str, **fields: Any) -> None:
    logger.info(json.dumps({"event": event, **fields}, ensure_ascii=False))


def _event_type(name: str) -> str:
    value = name.casefold()
    if any(word in value for word in ["prova", "teste", "taf", "mtai"]):
        return "exam"
    if any(word in value for word in ["entrega", "trabalho", "relatório", "relatorio"]):
        return "assignment"
    if any(word in value for word in ["apresent", "semin"]):
        return "presentation"
    if any(word in value for word in ["prazo", "deadline"]):
        return "deadline"
    return "activity"


def _start_at(value: date | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        parsed = date.fromisoformat(value[:10])
    else:
        parsed = value
    return datetime.combine(parsed, dt_time(0, 0), TZ)


def _fingerprint(discipline_id: str, title: str, start_at: datetime | None, evidence: str) -> str:
    basis = f"{discipline_id}|{title}|{start_at.isoformat() if start_at else 'no-date'}|{evidence}"
    return "course-plan:" + hashlib.sha256(basis.encode()).hexdigest()[:32]


def _draft_from_assessment(discipline_id: str, index: int, assessment: dict[str, Any]) -> CalendarDraftEvent:
    title = str(assessment.get("name") or f"Evento {index}")[:160]
    start = _start_at(assessment.get("date"))
    evidence_parts = [title]
    if assessment.get("date"):
        evidence_parts.append(str(assessment["date"]))
    if assessment.get("weight") is not None:
        evidence_parts.append(f"peso {assessment['weight']}%")
    if assessment.get("description"):
        evidence_parts.append(str(assessment["description"])[:120])
    evidence = " — ".join(evidence_parts)
    warnings = []
    ambiguous = False
    confidence = 0.96
    if start is None:
        warnings.append("A avaliação foi identificada sem data explícita; corrija antes de confirmar.")
        ambiguous = True
        confidence = 0.55
    return CalendarDraftEvent.model_validate({
        "temporary_id": f"event-{index}",
        "title": title,
        "event_type": _event_type(title),
        "start_at": start,
        "all_day": True,
        "timezone": "America/Sao_Paulo",
        "weight": assessment.get("weight") or assessment.get("group_weight"),
        "description": assessment.get("description"),
        "source_evidence": evidence,
        "confidence": confidence,
        "warnings": warnings,
        "ambiguous": ambiguous,
        "source_fingerprint": _fingerprint(discipline_id, title, start, evidence),
    })


def build_event_extraction_preview(discipline_id: str) -> CalendarExtractionPreviewResponse:
    start = _now_ms()
    plan = storage.COURSE_PLANS.get(discipline_id)
    if not plan:
        raise CalendarExtractionError("Confirme um plano de ensino antes de extrair eventos.")

    warnings: list[str] = []
    drafts: list[CalendarDraftEvent] = []
    assessments = list(plan.get("assessments") or [])
    for index, assessment in enumerate(assessments, 1):
        try:
            drafts.append(_draft_from_assessment(discipline_id, index, assessment))
        except Exception:
            warnings.append(f"Uma avaliação do plano não pôde ser convertida em rascunho de evento ({index}).")

    if not drafts:
        warnings.append("Nenhum evento explícito foi encontrado no plano confirmado.")

    preview_id = str(uuid4())
    expires_at = storage.utc_now() + timedelta(minutes=20)
    payload = {
        "preview_id": preview_id,
        "discipline_id": discipline_id,
        "expires_at": expires_at,
        "draft_events": [item.model_dump(mode="json") for item in drafts],
    }
    storage.save_event_extraction_preview(payload)
    response = CalendarExtractionPreviewResponse.model_validate({
        "preview_id": preview_id,
        "expires_at": expires_at,
        "draft_events": drafts,
        "warnings": warnings,
        "source": "course_plan" if drafts else "fallback",
        "used_fallback": not bool(drafts),
        "fallback_reason": None if drafts else "no_explicit_events",
        "latency_ms": _duration_ms(start),
    })
    _log("calendar_extract_preview", discipline_id=discipline_id, draft_count=len(drafts), warning_count=len(warnings), latency_ms=response.latency_ms)
    return response


def confirm_event_preview(discipline_id: str, preview_id: str, draft_events: list[CalendarDraftEvent]) -> tuple[list[dict], list[dict[str, str]]]:
    preview = storage.get_event_extraction_preview(preview_id)
    if not preview or preview.get("discipline_id") != discipline_id:
        raise CalendarExtractionError("Pré-visualização expirada ou inexistente.")
    created: list[dict] = []
    skipped: list[dict[str, str]] = []
    for draft in draft_events:
        if draft.start_at is None or draft.ambiguous:
            skipped.append({"temporary_id": draft.temporary_id, "reason": "Evento ambíguo ou sem data explícita."})
            continue
        fingerprint = draft.source_fingerprint or _fingerprint(discipline_id, draft.title, draft.start_at, draft.source_evidence)
        existing = storage.find_event_by_fingerprint(fingerprint)
        if existing:
            skipped.append({"temporary_id": draft.temporary_id, "reason": "Evento já confirmado anteriormente."})
            continue
        event = storage.create_event({
            "discipline_id": discipline_id,
            "assessment_id": None,
            "title": draft.title,
            "description": draft.description,
            "event_type": draft.event_type,
            "start_at": draft.start_at.isoformat(),
            "end_at": draft.end_at.isoformat() if draft.end_at else None,
            "all_day": draft.all_day,
            "timezone": draft.timezone,
            "weight": draft.weight,
            "status": "confirmed",
            "source": "course_plan",
            "source_evidence": draft.source_evidence,
            "extraction_confidence": draft.confidence,
            "source_fingerprint": fingerprint,
        })
        created.append(event)
    storage.delete_event_extraction_preview(preview_id)
    _log("calendar_preview_confirmed", discipline_id=discipline_id, created_count=len(created), skipped_count=len(skipped))
    return created, skipped
