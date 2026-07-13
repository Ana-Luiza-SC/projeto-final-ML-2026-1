from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4
from typing import Any

from app import storage
from app.schemas import WeeklyAvailabilityRequest, WeeklyPlanPreviewRequest

ALGORITHM_VERSION = "weekly-calendar-plan-v1"
MIN_BLOCK_MINUTES = 30
DAY_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DAY_INDEX = {day: index for index, day in enumerate(DAY_ORDER)}


class WeeklyPlanningError(ValueError):
    pass


def _minutes(value: str) -> int:
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def _hhmm(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def _local_dt(day: date, minute: int) -> str:
    return f"{day.isoformat()}T{_hhmm(minute)}:00-03:00"


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _week_day(week_start: date, weekday: str) -> date:
    return week_start + timedelta(days=DAY_INDEX[weekday])


def availability_summary(payload: WeeklyAvailabilityRequest) -> dict[str, Any]:
    windows_by_day: dict[str, list[dict[str, Any]]] = {}
    warnings: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    for window in payload.windows:
        if not window.available:
            continue
        key = (window.weekday, window.start_time, window.end_time)
        if key in seen:
            continue
        seen.add(key)
        windows_by_day.setdefault(window.weekday, []).append(window.model_dump())

    normalized = []
    daily_totals = {day: 0 for day in DAY_ORDER}
    for day, windows in windows_by_day.items():
        ordered = sorted(windows, key=lambda item: _minutes(item["start_time"]))
        previous_end = None
        for item in ordered:
            start = _minutes(item["start_time"])
            end = _minutes(item["end_time"])
            if previous_end is not None and start < previous_end:
                raise WeeklyPlanningError("Janelas de disponibilidade nao podem se sobrepor.")
            previous_end = end
            daily_totals[day] += end - start
            normalized.append(item)
    return {
        "timezone": payload.timezone,
        "daily_totals": {day: minutes for day, minutes in daily_totals.items() if minutes > 0},
        "weekly_total_minutes": sum(daily_totals.values()),
        "normalized_windows": normalized,
        "warnings": warnings,
    }


def _band(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _assessment_deadline(assessment: dict) -> datetime | None:
    value = assessment.get("date")
    if not value:
        return None
    raw = value.isoformat() if hasattr(value, "isoformat") else str(value)
    return datetime.fromisoformat(raw[:10] + "T00:00:00-03:00")


def _rank_priorities(payload: WeeklyPlanPreviewRequest) -> list[dict[str, Any]]:
    excluded = {str(item) for item in payload.excluded_discipline_ids}
    priorities: list[dict[str, Any]] = []
    for discipline in storage.list_disciplines():
        did = str(discipline["id"])
        if did in excluded:
            continue
        assessments = [item for item in storage.list_assessments(did) if item.get("status", "planned") != "cancelled"]
        planned = [(item, _assessment_deadline(item)) for item in assessments]
        planned = [(item, deadline) for item, deadline in planned if deadline is not None]
        planned.sort(key=lambda item: (item[1], -(item[0].get("weight") or item[0].get("group_weight") or 0), item[0].get("name") or ""))
        missing = []
        evidence = []
        score = 25
        assessment = None
        deadline = None
        if planned:
            assessment, deadline = planned[0]
            days = max(0, (deadline.date() - payload.week_start).days)
            deadline_score = max(0, 40 - min(days, 21) * 2)
            weight = assessment.get("weight") or assessment.get("group_weight") or 0
            score = min(100, 30 + deadline_score + min(25, int(weight or 0)))
            evidence.append({"source_type": "assessment", "source_id": str(assessment.get("id")), "summary": f"{assessment.get('name') or 'Avaliacao'} em {deadline.date().isoformat()}"})
            if weight:
                evidence.append({"source_type": "assessment", "source_id": str(assessment.get("id")), "summary": f"Peso informado: {weight:g}%"})
        else:
            missing.append("Nenhuma avaliacao futura datada foi encontrada.")
        if not discipline.get("workload_hours"):
            missing.append("Carga horaria ausente.")
        else:
            score = min(100, score + min(10, int(discipline.get("workload_hours") or 0) // 15))
            evidence.append({"source_type": "discipline", "source_id": did, "summary": f"Carga horaria: {discipline.get('workload_hours')}h"})
        reason = "Prioridade calculada por prazo, peso e dados academicos disponiveis." if evidence else "Prioridade baixa por falta de evidencias estruturadas."
        priorities.append({
            "discipline_id": did,
            "discipline_code": discipline.get("code"),
            "discipline_name": discipline.get("name") or discipline.get("code") or "Disciplina",
            "assessment_id": str(assessment.get("id")) if assessment else None,
            "assessment_name": assessment.get("name") if assessment else None,
            "deadline_at": deadline.isoformat() if deadline else None,
            "priority_score": score,
            "priority_band": _band(score),
            "evidence_used": evidence,
            "missing_evidence": missing,
            "reason": reason,
        })
    return sorted(priorities, key=lambda item: (-item["priority_score"], item.get("deadline_at") or "9999", item.get("discipline_code") or "", item["discipline_id"]))


def _busy_intervals(week_start: date, week_end: date) -> dict[str, list[tuple[int, int, str]]]:
    events = storage.list_events(start_at=f"{week_start.isoformat()}T00:00:00-03:00", end_at=f"{week_end.isoformat()}T23:59:59-03:00", status="confirmed")
    busy: dict[str, list[tuple[int, int, str]]] = {}
    for event in events:
        if event.get("source") == "study_plan":
            continue
        start = _parse_dt(event.get("start_at"))
        end = _parse_dt(event.get("end_at")) if event.get("end_at") else start + timedelta(days=1 if event.get("all_day") else 0)
        if event.get("all_day"):
            start_min, end_min = 0, 24 * 60
        else:
            start_min = start.hour * 60 + start.minute
            end_min = end.hour * 60 + end.minute
        busy.setdefault(start.date().isoformat(), []).append((start_min, end_min, event.get("title") or "Evento"))
    return busy


def _subtract_busy(start: int, end: int, busy: list[tuple[int, int, str]]) -> list[tuple[int, int]]:
    free = [(start, end)]
    for b_start, b_end, _ in sorted(busy):
        next_free = []
        for f_start, f_end in free:
            if b_end <= f_start or b_start >= f_end:
                next_free.append((f_start, f_end))
                continue
            if f_start < b_start:
                next_free.append((f_start, b_start))
            if b_end < f_end:
                next_free.append((b_end, f_end))
        free = next_free
    return [(a, b) for a, b in free if b - a >= MIN_BLOCK_MINUTES]


def _allocate(payload: WeeklyPlanPreviewRequest, priorities: list[dict[str, Any]], summary: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    week_end = payload.week_start + timedelta(days=6)
    busy = _busy_intervals(payload.week_start, week_end)
    slots: list[tuple[date, int, int]] = []
    conflicts: list[str] = []
    for window in summary["normalized_windows"]:
        day = _week_day(payload.week_start, window["weekday"])
        start = _minutes(window["start_time"])
        end = _minutes(window["end_time"])
        day_busy = busy.get(day.isoformat(), [])
        for _, _, title in day_busy:
            conflicts.append(f"{day.isoformat()}: janela ajustada por evento existente: {title}.")
        for free_start, free_end in _subtract_busy(start, end, day_busy):
            slots.append((day, free_start, free_end))
    slots.sort()
    blocks: list[dict[str, Any]] = []
    unallocated: list[dict[str, Any]] = []
    slot_index = 0
    for priority in priorities:
        allocated = False
        while slot_index < len(slots):
            day, start, end = slots[slot_index]
            duration = end - start
            if duration < MIN_BLOCK_MINUTES:
                slot_index += 1
                continue
            deadline = _parse_dt(priority["deadline_at"]) if priority.get("deadline_at") else None
            if deadline and day >= deadline.date():
                slot_index += 1
                continue
            block_end = min(end, start + max(MIN_BLOCK_MINUTES, min(90, duration)))
            slots[slot_index] = (day, block_end, end)
            blocks.append({
                "temporary_id": f"block-{len(blocks) + 1}",
                "discipline_id": priority["discipline_id"],
                "discipline_code": priority.get("discipline_code"),
                "discipline_name": priority["discipline_name"],
                "content_id": priority.get("content_id"),
                "assessment_id": priority.get("assessment_id"),
                "title": f"Estudo planejado: {priority.get('discipline_code') or priority['discipline_name']}",
                "reason": priority["reason"],
                "priority_score": priority["priority_score"],
                "priority_band": priority["priority_band"],
                "start_at": _local_dt(day, start),
                "end_at": _local_dt(day, block_end),
                "state": "planned",
            })
            allocated = True
            break
        if not allocated:
            unallocated.append(priority)
    return blocks, unallocated, list(dict.fromkeys(conflicts))


def build_weekly_preview(payload: WeeklyPlanPreviewRequest) -> dict[str, Any]:
    summary = availability_summary(payload)
    if summary["weekly_total_minutes"] < MIN_BLOCK_MINUTES:
        raise WeeklyPlanningError("Disponibilidade insuficiente para gerar blocos planejados.")
    priorities = _rank_priorities(payload)
    if not priorities:
        raise WeeklyPlanningError("Nenhuma disciplina disponivel para planejamento.")
    blocks, unallocated, conflicts = _allocate(payload, priorities, summary)
    preview = {
        "study_plan_id": str(uuid4()),
        "week_start": payload.week_start.isoformat(),
        "timezone": payload.timezone,
        "availability": summary,
        "ranked_priorities": priorities,
        "planned_blocks": blocks,
        "unallocated_priorities": unallocated,
        "conflicts": conflicts,
        "warnings": ["Capacidade insuficiente para todos os itens prioritarios."] if unallocated else [],
        "algorithm_version": ALGORITHM_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    storage.save_study_plan_preview(preview)
    return preview


def confirm_weekly_preview(study_plan_id: str) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    preview = storage.get_study_plan_preview(study_plan_id)
    if not preview:
        raise WeeklyPlanningError("Preview de planejamento nao encontrado ou expirado.")
    created: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for block in preview.get("planned_blocks", []):
        fingerprint = f"study_plan:{study_plan_id}:{block['temporary_id']}"
        existing = storage.find_event_by_fingerprint(fingerprint)
        if existing:
            created.append(storage.get_event(existing["id"]))
            continue
        event = storage.create_event({
            "discipline_id": block.get("discipline_id"),
            "assessment_id": block.get("assessment_id"),
            "title": block["title"],
            "description": block.get("reason"),
            "event_type": "study_block",
            "start_at": block["start_at"],
            "end_at": block["end_at"],
            "all_day": False,
            "timezone": "America/Sao_Paulo",
            "weight": None,
            "status": "confirmed",
            "source": "study_plan",
            "source_evidence": block.get("reason"),
            "extraction_confidence": 1.0,
            "source_fingerprint": fingerprint,
            "study_plan_id": study_plan_id,
            "content_id": block.get("content_id"),
            "priority_score": block.get("priority_score"),
            "priority_band": block.get("priority_band"),
            "priority_reason": block.get("reason"),
            "algorithm_version": preview.get("algorithm_version"),
            "generated_at": preview.get("generated_at"),
        })
        created.append(event)
    return created, skipped
