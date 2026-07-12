from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.schemas import StudyPlanRequest, StudyPlanResponse, StudyPlanSession

logger = logging.getLogger("estudaunb.study_plan")

BLOCK_MINUTES = 30
DAY_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


class StudyPlanInputError(ValueError):
    pass


class StudyPlanOutputError(RuntimeError):
    pass


class StudyPlanLLMClient(Protocol):
    def generate_explanation(self, context: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class RegisteredDiscipline:
    id: str
    code: str
    name: str
    priority: int
    priority_influences: list[dict[str, Any]]


def _now_ms() -> float:
    return time.perf_counter() * 1000


def _duration_ms(start_ms: float) -> float:
    return round(_now_ms() - start_ms, 2)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_timeout() -> float:
    try:
        return max(1.0, float(os.getenv("LLM_TIMEOUT_SECONDS", "8")))
    except ValueError:
        return 8.0


def _safe_text(value: Any, limit: int = 240) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").strip()[:limit]


def _log_event(event: str, **fields: Any) -> None:
    safe_fields = {
        key: value
        for key, value in fields.items()
        if key not in {"prompt", "api_key", "GOOGLE_API_KEY", "objective_text"}
    }
    logger.info(json.dumps({"event": event, **safe_fields}, ensure_ascii=False))


def _parse_minutes(value: str) -> int:
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def _format_minutes(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def _floor_block(minutes: int) -> int:
    return (minutes // BLOCK_MINUTES) * BLOCK_MINUTES


def _window_minutes(window: Any) -> int:
    return _floor_block(_parse_minutes(window.end_time) - _parse_minutes(window.start_time))


def _ordered_days(days: list[str]) -> list[str]:
    selected = set(days)
    return [day for day in DAY_ORDER if day in selected]


def list_registered_disciplines(
    requested_ids: list[UUID],
    registered_records: list[dict[str, Any]],
    priorities: dict[str, int],
) -> list[RegisteredDiscipline]:
    records_by_id = {str(item.get("id")): item for item in registered_records}
    missing = [str(item) for item in requested_ids if str(item) not in records_by_id]
    if missing:
        raise StudyPlanInputError("Disciplina não encontrada.")

    disciplines = []
    for discipline_id in requested_ids:
        record = records_by_id[str(discipline_id)]
        base_priority = priorities.get(str(discipline_id), 3)
        bonus = 0
        priority_influences: list[dict[str, Any]] = []
        for assessment in record.get("assessments", []):
            if assessment.get("status") != "planned" or not assessment.get("date"):
                continue
            if assessment.get("weight") is None and not assessment.get("topics"):
                continue
            assessment_date = assessment["date"] if isinstance(assessment["date"], date) else date.fromisoformat(str(assessment["date"]))
            days = (assessment_date - date.today()).days
            assessment_bonus = 2 if 0 <= days <= 7 else 1 if 8 <= days <= 14 else 0
            if assessment_bonus:
                bonus = max(bonus, assessment_bonus)
                priority_influences.append({
                    "discipline_id": str(discipline_id),
                    "assessment_id": assessment.get("id"),
                    "assessment_name": _safe_text(assessment.get("name"), 120),
                    "assessment_date": assessment_date,
                    "weight": assessment.get("weight"),
                    "bonus": assessment_bonus,
                    "reason": "Avaliação confirmada em até 7 dias." if assessment_bonus == 2 else "Avaliação confirmada em 8 a 14 dias.",
                })
        code = _safe_text(record.get("code"), 40)
        name = _safe_text(record.get("name"), 120)
        disciplines.append(
            RegisteredDiscipline(
                id=str(discipline_id),
                code=code,
                name=name,
                priority=min(5, base_priority + bonus),
                priority_influences=priority_influences,
            )
        )
    return disciplines


def _discipline_sort_key(item: RegisteredDiscipline) -> tuple[int, str, str]:
    return (-item.priority, item.code, item.id)


def _availability_minutes(payload: StudyPlanRequest) -> tuple[int, list[str]]:
    warnings: list[str] = []
    requested = _floor_block(round(payload.availability.available_hours_per_week * 60))
    if requested < BLOCK_MINUTES:
        raise StudyPlanInputError("Disponibilidade insuficiente para uma sessão mínima de 30 minutos.")

    if not payload.availability.time_windows:
        return requested, warnings

    windows_total = sum(_window_minutes(window) for window in payload.availability.time_windows)
    if windows_total < BLOCK_MINUTES:
        raise StudyPlanInputError("Janelas informadas não comportam uma sessão mínima de 30 minutos.")
    if windows_total > requested + BLOCK_MINUTES:
        raise StudyPlanInputError("A soma das janelas excede a disponibilidade semanal informada.")
    if windows_total < requested:
        warnings.append(
            "A soma das janelas é menor que as horas semanais informadas; o plano usou as janelas como limite real."
        )
    return min(requested, windows_total), warnings


def _allocate_blocks(
    disciplines: list[RegisteredDiscipline], total_minutes: int
) -> tuple[dict[str, int], list[str]]:
    total_blocks = total_minutes // BLOCK_MINUTES
    allocations = {discipline.id: 0 for discipline in disciplines}
    warnings: list[str] = []
    ordered = sorted(disciplines, key=_discipline_sort_key)

    if total_blocks < len(disciplines):
        for discipline in ordered[:total_blocks]:
            allocations[discipline.id] = BLOCK_MINUTES
        for discipline in ordered[total_blocks:]:
            warnings.append(
                f"{discipline.code} não recebeu sessão porque a disponibilidade não cobre todas as disciplinas selecionadas."
            )
        return allocations, warnings

    for discipline in disciplines:
        allocations[discipline.id] = BLOCK_MINUTES
    remaining_blocks = total_blocks - len(disciplines)
    if remaining_blocks <= 0:
        return allocations, warnings

    total_weight = sum(discipline.priority for discipline in disciplines)
    shares: list[tuple[RegisteredDiscipline, int, float]] = []
    assigned = 0
    for discipline in disciplines:
        raw = remaining_blocks * discipline.priority / total_weight
        whole = int(raw)
        assigned += whole
        shares.append((discipline, whole, raw - whole))

    for discipline, whole, _ in shares:
        allocations[discipline.id] += whole * BLOCK_MINUTES

    leftover = remaining_blocks - assigned
    for discipline, _, _ in sorted(
        shares,
        key=lambda item: (-item[2], -item[0].priority, item[0].code, item[0].id),
    )[:leftover]:
        allocations[discipline.id] += BLOCK_MINUTES

    return allocations, warnings


def _activity_for(discipline: RegisteredDiscipline) -> str:
    return "Revisão guiada e resolução de exercícios" if discipline.priority >= 4 else "Revisão e organização dos conteúdos"


def _build_plan_without_windows(
    disciplines: list[RegisteredDiscipline],
    allocations: dict[str, int],
    payload: StudyPlanRequest,
) -> list[dict[str, Any]]:
    days = _ordered_days([str(day) for day in payload.availability.days_available])
    sequence_by_day = {day: 0 for day in days}
    day_index = 0
    plan: list[dict[str, Any]] = []

    for discipline in sorted(disciplines, key=_discipline_sort_key):
        remaining = allocations[discipline.id]
        while remaining > 0:
            duration = min(payload.max_session_minutes, remaining)
            duration = _floor_block(duration)
            if duration <= 0:
                break
            day = days[day_index % len(days)]
            day_index += 1
            sequence_by_day[day] += 1
            plan.append(
                {
                    "day": day,
                    "sequence": sequence_by_day[day],
                    "discipline_id": discipline.id,
                    "discipline_code": discipline.code,
                    "discipline_name": discipline.name,
                    "duration_minutes": duration,
                    "activity": _activity_for(discipline),
                    "start_time": None,
                    "end_time": None,
                }
            )
            remaining -= duration
    return plan


def _window_sort_key(window: Any) -> tuple[int, int]:
    return (DAY_ORDER.index(window.day), _parse_minutes(window.start_time))


def _build_plan_with_windows(
    disciplines: list[RegisteredDiscipline],
    allocations: dict[str, int],
    payload: StudyPlanRequest,
) -> list[dict[str, Any]]:
    windows = sorted(payload.availability.time_windows, key=_window_sort_key)
    window_states = [
        {
            "day": str(window.day),
            "cursor": _parse_minutes(window.start_time),
            "end": _parse_minutes(window.end_time),
        }
        for window in windows
    ]
    sequence_by_day = {day: 0 for day in DAY_ORDER}
    plan: list[dict[str, Any]] = []
    window_index = 0

    for discipline in sorted(disciplines, key=_discipline_sort_key):
        remaining = allocations[discipline.id]
        while remaining > 0:
            while window_index < len(window_states):
                state = window_states[window_index]
                available = _floor_block(state["end"] - state["cursor"])
                if available >= BLOCK_MINUTES:
                    break
                window_index += 1
            if window_index >= len(window_states):
                raise StudyPlanOutputError("O plano excedeu as janelas disponíveis.")

            state = window_states[window_index]
            available = _floor_block(state["end"] - state["cursor"])
            duration = min(payload.max_session_minutes, remaining, available)
            duration = _floor_block(duration)
            if duration < BLOCK_MINUTES:
                window_index += 1
                continue
            start = state["cursor"]
            end = start + duration
            state["cursor"] = end
            sequence_by_day[state["day"]] += 1
            plan.append(
                {
                    "day": state["day"],
                    "sequence": sequence_by_day[state["day"]],
                    "discipline_id": discipline.id,
                    "discipline_code": discipline.code,
                    "discipline_name": discipline.name,
                    "duration_minutes": duration,
                    "activity": _activity_for(discipline),
                    "start_time": _format_minutes(start),
                    "end_time": _format_minutes(end),
                }
            )
            remaining -= duration
    return plan


def build_baseline_study_plan(
    payload: StudyPlanRequest, disciplines: list[RegisteredDiscipline]
) -> tuple[list[dict[str, Any]], list[str], int]:
    total_minutes, warnings = _availability_minutes(payload)
    allocations, allocation_warnings = _allocate_blocks(disciplines, total_minutes)
    warnings.extend(allocation_warnings)

    if payload.availability.time_windows:
        plan = _build_plan_with_windows(disciplines, allocations, payload)
    else:
        plan = _build_plan_without_windows(disciplines, allocations, payload)

    if not plan:
        raise StudyPlanInputError("Disponibilidade insuficiente para gerar plano de estudos.")
    return plan, warnings, total_minutes


def _session_within_window(session: dict[str, Any], payload: StudyPlanRequest) -> bool:
    if session.get("start_time") is None or session.get("end_time") is None:
        return False
    start = _parse_minutes(session["start_time"])
    end = _parse_minutes(session["end_time"])
    for window in payload.availability.time_windows:
        if window.day != session["day"]:
            continue
        if _parse_minutes(window.start_time) <= start and end <= _parse_minutes(window.end_time):
            return True
    return False


def validate_study_plan(
    plan: list[dict[str, Any]],
    payload: StudyPlanRequest,
    disciplines: list[RegisteredDiscipline],
    total_minutes: int,
) -> None:
    selected = {discipline.id for discipline in disciplines}
    allowed_days = {str(day) for day in payload.availability.days_available}
    allocated = 0
    intervals_by_day: dict[str, list[tuple[int, int]]] = {}

    for session in plan:
        if str(session.get("discipline_id")) not in selected:
            raise StudyPlanOutputError("Plano contém disciplina não selecionada.")
        if session.get("day") not in allowed_days:
            raise StudyPlanOutputError("Plano contém dia não permitido.")
        duration = int(session.get("duration_minutes", 0))
        if duration <= 0:
            raise StudyPlanOutputError("Plano contém sessão sem duração válida.")
        if duration > payload.max_session_minutes:
            raise StudyPlanOutputError("Plano contém sessão acima da duração máxima.")
        allocated += duration

        has_times = session.get("start_time") is not None or session.get("end_time") is not None
        if payload.availability.time_windows:
            if not _session_within_window(session, payload):
                raise StudyPlanOutputError("Plano contém horário fora das janelas disponíveis.")
            start = _parse_minutes(session["start_time"])
            end = _parse_minutes(session["end_time"])
            intervals_by_day.setdefault(session["day"], []).append((start, end))
        elif has_times:
            raise StudyPlanOutputError("Plano inventou horário sem janelas disponíveis.")

    if allocated > total_minutes:
        raise StudyPlanOutputError("Plano excede a disponibilidade informada.")

    for intervals in intervals_by_day.values():
        ordered = sorted(intervals)
        for previous, current in zip(ordered, ordered[1:]):
            if current[0] < previous[1]:
                raise StudyPlanOutputError("Plano contém sessões sobrepostas.")

    try:
        [StudyPlanSession.model_validate(item) for item in plan]
    except ValidationError as exc:
        raise StudyPlanOutputError("Plano não segue o schema esperado.") from exc


def _build_fallback_summary(plan: list[dict[str, Any]], warnings: list[str]) -> str:
    if warnings:
        return "Plano semanal gerado por regras determinísticas com avisos sobre a disponibilidade informada."
    return "Plano semanal gerado por regras determinísticas a partir das disciplinas e disponibilidade informadas."


def _validate_llm_explanation(data: dict[str, Any], selected_ids: set[str]) -> str:
    if not isinstance(data, dict):
        raise ValueError("Resposta do LLM não é objeto JSON.")
    summary = _safe_text(data.get("summary"), 500)
    if not summary:
        raise ValueError("Resposta do LLM veio sem resumo.")
    returned_ids = data.get("discipline_ids")
    if returned_ids is not None and any(str(item) not in selected_ids for item in returned_ids):
        raise ValueError("Resposta do LLM inventou disciplina.")
    return summary


class GoogleStudyPlanLLMClient:
    def generate_explanation(self, context: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("missing_api_key")
        model = os.getenv("LLM_MODEL", "gemini-2.5-flash")
        prompt = (
            "Explique brevemente o plano semanal do EstudaUnB. "
            "Não altere disciplinas, dias, horários ou duração. "
            "Responda apenas JSON com summary e discipline_ids. Contexto: "
            + json.dumps(context, ensure_ascii=False)
        )
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            + model
            + ":generateContent?key="
            + api_key
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json", "temperature": 0.2},
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except TimeoutError as exc:
            raise TimeoutError("llm_timeout") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("llm_failed") from exc

        try:
            text = response_payload["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("llm_invalid_response") from exc


def _build_llm_context(
    payload: StudyPlanRequest,
    disciplines: list[RegisteredDiscipline],
    plan: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "discipline_ids": [discipline.id for discipline in disciplines],
        "disciplines": [
            {"id": discipline.id, "code": discipline.code, "priority": discipline.priority, "priority_influences": discipline.priority_influences}
            for discipline in disciplines
        ],
        "plan": [
            {
                "day": item["day"],
                "discipline_id": item["discipline_id"],
                "duration_minutes": item["duration_minutes"],
                "sequence": item["sequence"],
            }
            for item in plan
        ],
        "objective_text": _safe_text(payload.objective_text, 500),
        "warnings": warnings,
    }


def generate_plan_explanation(
    payload: StudyPlanRequest,
    disciplines: list[RegisteredDiscipline],
    plan: list[dict[str, Any]],
    warnings: list[str],
    llm_client: StudyPlanLLMClient | None = None,
) -> tuple[str, str, list[str], str | None, float | None]:
    provider = os.getenv("LLM_PROVIDER", "google").strip().lower()
    fallback_enabled = _env_bool("LLM_FALLBACK_ENABLED", True)
    if provider != "google":
        return _build_fallback_summary(plan, warnings), "deterministic_fallback", ["A personalização por IA não estava disponível."], "unsupported_provider", None
    if not os.getenv("GOOGLE_API_KEY") and llm_client is None:
        return _build_fallback_summary(plan, warnings), "deterministic_fallback", ["A personalização por IA não estava disponível."], "missing_api_key", None

    client = llm_client or GoogleStudyPlanLLMClient()
    llm_start = _now_ms()
    context = _build_llm_context(payload, disciplines, plan, warnings)
    selected_ids = {discipline.id for discipline in disciplines}
    try:
        raw = client.generate_explanation(context, timeout_seconds=_env_timeout())
        summary = _validate_llm_explanation(raw, selected_ids)
        return summary, "llm_assisted", [], None, _duration_ms(llm_start)
    except TimeoutError:
        if not fallback_enabled:
            raise
        return _build_fallback_summary(plan, warnings), "deterministic_fallback", ["A personalização por IA demorou demais e foi substituída pelo fallback determinístico."], "timeout", _duration_ms(llm_start)
    except Exception as exc:
        if not fallback_enabled:
            raise
        return _build_fallback_summary(plan, warnings), "deterministic_fallback", ["A personalização por IA não pôde ser validada e foi substituída pelo fallback determinístico."], type(exc).__name__, _duration_ms(llm_start)


def generate_study_plan(
    payload: StudyPlanRequest,
    registered_records: list[dict[str, Any]],
    llm_client: StudyPlanLLMClient | None = None,
) -> StudyPlanResponse:
    request_id = str(uuid4())
    start = _now_ms()
    priority_map = {str(item.discipline_id): item.priority for item in payload.priorities}
    _log_event(
        "study_plan_requested",
        request_id=request_id,
        discipline_count=len(payload.discipline_ids),
        provider=os.getenv("LLM_PROVIDER", "google"),
    )

    disciplines = list_registered_disciplines(payload.discipline_ids, registered_records, priority_map)
    plan, warnings, total_minutes = build_baseline_study_plan(payload, disciplines)
    validate_study_plan(plan, payload, disciplines, total_minutes)

    summary, source, explanation_warnings, fallback_reason, llm_latency = generate_plan_explanation(
        payload, disciplines, plan, warnings, llm_client=llm_client
    )
    warnings = list(dict.fromkeys(warnings + explanation_warnings))
    allocated = sum(item["duration_minutes"] for item in plan)
    response = StudyPlanResponse.model_validate(
        {
            "status": "success",
            "source": source,
            "plan": plan,
            "summary": summary,
            "warnings": warnings,
            "priority_influences": [influence for discipline in disciplines for influence in discipline.priority_influences],
            "metrics": {
                "requested_minutes": total_minutes,
                "allocated_minutes": allocated,
                "unallocated_minutes": max(0, total_minutes - allocated),
                "session_count": len(plan),
                "discipline_count": len(disciplines),
            },
            "request_id": request_id,
        }
    )
    _log_event(
        "study_plan_generated",
        request_id=request_id,
        source=response.source,
        latency_ms=_duration_ms(start),
        llm_latency_ms=llm_latency,
        fallback_reason=fallback_reason,
        discipline_count=len(disciplines),
        session_count=len(plan),
        requested_minutes=total_minutes,
        allocated_minutes=allocated,
        model=os.getenv("LLM_MODEL", "gemini-2.5-flash") if source == "llm_assisted" else None,
    )
    return response
