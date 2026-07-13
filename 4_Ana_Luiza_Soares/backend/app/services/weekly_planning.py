from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app import storage
from app.schemas import WeeklyAvailabilityRequest, WeeklyPlanPreviewRequest

ALGORITHM_VERSION = "weekly-calendar-plan-v2"
MIN_BLOCK_MINUTES = 30
DAY_ORDER = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]
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
    seen: set[tuple[str, str, str]] = set()
    for window in payload.windows:
        if not window.available:
            continue
        key = (window.weekday, window.start_time, window.end_time)
        if key in seen:
            continue
        seen.add(key)
        windows_by_day.setdefault(window.weekday, []).append(window.model_dump())

    normalized: list[dict[str, Any]] = []
    daily_totals = {day: 0 for day in DAY_ORDER}
    for day, windows in windows_by_day.items():
        ordered = sorted(windows, key=lambda item: _minutes(item["start_time"]))
        previous = None
        for item in ordered:
            start = _minutes(item["start_time"])
            end = _minutes(item["end_time"])
            if previous is not None and start < previous["end"]:
                raise WeeklyPlanningError(
                    "A janela "
                    f"{item['start_time']}-{item['end_time']} se sobrepoe a "
                    f"{previous['start_text']}-{previous['end_text']} em {day}."
                )
            previous = {
                "end": end,
                "start_text": item["start_time"],
                "end_text": item["end_time"],
            }
            daily_totals[day] += end - start
            normalized.append(item)
    return {
        "timezone": payload.timezone,
        "daily_totals": {
            day: minutes for day, minutes in daily_totals.items() if minutes > 0
        },
        "weekly_total_minutes": sum(daily_totals.values()),
        "normalized_windows": normalized,
        "warnings": [],
    }


def _band(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _assessment_deadline(assessment: dict[str, Any]) -> datetime | None:
    value = assessment.get("date")
    if not value:
        return None
    raw = value.isoformat() if hasattr(value, "isoformat") else str(value)
    return datetime.fromisoformat(raw[:10] + "T00:00:00-03:00")


def _unfinished_content(discipline_id: str) -> list[dict[str, Any]]:
    nodes = storage.CONTENT_NODES.get(discipline_id, {})
    values = list(nodes.values()) if isinstance(nodes, dict) else list(nodes or [])
    return [
        node
        for node in values
        if node.get("status", "not_started") not in {"studied", "reviewed"}
    ]


def _demand(
    assessment: dict[str, Any] | None,
    unfinished: list[dict[str, Any]],
    workload_hours: float | int | None,
) -> tuple[int, float, str]:
    if assessment and unfinished:
        return (
            90,
            0.75,
            "Estimativa baseada em avaliacao futura e conteudos ainda nao concluidos.",
        )
    if unfinished:
        return 60, 0.55, "Estimativa baseada em conteudos ainda nao concluidos."
    if assessment:
        return 60, 0.5, "Estimativa conservadora baseada em avaliacao futura sem conteudo vinculado."
    if workload_hours:
        return 30, 0.25, "Estimativa minima baseada apenas na carga horaria da disciplina."
    return 30, 0.15, "Estimativa minima por falta de evidencias academicas estruturadas."


def _rank_priorities(payload: WeeklyPlanPreviewRequest) -> list[dict[str, Any]]:
    excluded = {str(item) for item in payload.excluded_discipline_ids}
    priorities: list[dict[str, Any]] = []
    for discipline in storage.list_disciplines():
        discipline_id = str(discipline["id"])
        if discipline_id in excluded:
            continue

        future_assessments: list[tuple[dict[str, Any], datetime]] = []
        for assessment in storage.list_assessments(discipline_id):
            if assessment.get("status", "planned") != "planned":
                continue
            deadline = _assessment_deadline(assessment)
            if deadline and deadline.date() > payload.week_start:
                future_assessments.append((assessment, deadline))
        future_assessments.sort(
            key=lambda item: (
                item[1],
                -(item[0].get("weight") or item[0].get("group_weight") or 0),
                item[0].get("name") or "",
            )
        )

        assessment, deadline = future_assessments[0] if future_assessments else (None, None)
        unfinished = _unfinished_content(discipline_id)
        missing: list[str] = []
        evidence: list[dict[str, Any]] = []
        score = 20

        if assessment and deadline:
            days = max(1, (deadline.date() - payload.week_start).days)
            deadline_score = max(0, 42 - min(days, 21) * 2)
            weight = assessment.get("weight") or assessment.get("group_weight") or 0
            score = min(100, 28 + deadline_score + min(25, int(weight or 0)))
            evidence.append(
                {
                    "source_type": "assessment",
                    "source_id": str(assessment.get("id")),
                    "summary": f"{assessment.get('name') or 'Avaliacao'} em {deadline.date().isoformat()}",
                }
            )
            if weight:
                evidence.append(
                    {
                        "source_type": "assessment",
                        "source_id": str(assessment.get("id")),
                        "summary": f"Peso informado: {weight:g}%",
                    }
                )
            else:
                missing.append("Peso da avaliacao ausente.")
        else:
            missing.append("Nenhuma avaliacao futura planejada e datada foi encontrada.")

        if unfinished:
            score = min(100, score + min(18, 6 + len(unfinished) * 3))
            evidence.append(
                {
                    "source_type": "content",
                    "source_id": str(unfinished[0].get("id")),
                    "summary": f"{len(unfinished)} conteudo(s) ainda nao concluido(s).",
                }
            )
        else:
            missing.append("Nenhum conteudo pendente estruturado foi encontrado.")

        workload = discipline.get("workload_hours")
        if workload:
            score = min(100, score + min(10, int(workload) // 15))
            evidence.append(
                {
                    "source_type": "discipline",
                    "source_id": discipline_id,
                    "summary": f"Carga horaria: {workload}h",
                }
            )
        else:
            missing.append("Carga horaria ausente.")

        requested_minutes, demand_confidence, demand_reason = _demand(
            assessment, unfinished, workload
        )
        reason = (
            f"{assessment.get('name') or 'Avaliacao'} se aproxima; prazo, peso e "
            "conteudos pendentes foram considerados."
            if assessment
            else "Prioridade conservadora calculada com os dados academicos disponiveis."
        )
        priority_item_id = (
            f"priority:{discipline_id}:"
            f"{assessment.get('id') if assessment else 'general'}:{payload.week_start.isoformat()}"
        )
        priorities.append(
            {
                "priority_item_id": priority_item_id,
                "discipline_id": discipline_id,
                "discipline_code": discipline.get("code"),
                "discipline_name": discipline.get("name")
                or discipline.get("code")
                or "Disciplina",
                "assessment_id": str(assessment.get("id")) if assessment else None,
                "assessment_name": assessment.get("name") if assessment else None,
                "deadline_at": deadline.isoformat() if deadline else None,
                "priority_score": score,
                "priority_band": _band(score),
                "evidence_used": evidence,
                "missing_evidence": missing,
                "reason": reason,
                "estimated_demand_minutes": requested_minutes,
                "demand_confidence": demand_confidence,
                "demand_reason": demand_reason,
            }
        )
    return sorted(
        priorities,
        key=lambda item: (
            -item["priority_score"],
            item.get("deadline_at") or "9999",
            item.get("discipline_code") or "",
            item["discipline_id"],
        ),
    )


def _busy_intervals(
    week_start: date, week_end: date
) -> dict[str, list[dict[str, Any]]]:
    events = storage.list_events(
        start_at=f"{week_start.isoformat()}T00:00:00-03:00",
        end_at=f"{week_end.isoformat()}T23:59:59-03:00",
        status="confirmed",
    )
    busy: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        start = _parse_dt(event["start_at"])
        end = (
            _parse_dt(event["end_at"])
            if event.get("end_at")
            else start + timedelta(days=1 if event.get("all_day") else 0)
        )
        start_min = 0 if event.get("all_day") else start.hour * 60 + start.minute
        end_min = 24 * 60 if event.get("all_day") else end.hour * 60 + end.minute
        busy.setdefault(start.date().isoformat(), []).append(
            {
                "start": start_min,
                "end": end_min,
                "id": str(event["id"]),
                "title": event.get("title") or "Evento",
            }
        )
    return busy


def _subtract_busy(
    start: int, end: int, busy: list[dict[str, Any]]
) -> list[tuple[int, int]]:
    free = [(start, end)]
    for event in sorted(busy, key=lambda item: (item["start"], item["end"])):
        next_free: list[tuple[int, int]] = []
        for free_start, free_end in free:
            if event["end"] <= free_start or event["start"] >= free_end:
                next_free.append((free_start, free_end))
                continue
            if free_start < event["start"]:
                next_free.append((free_start, event["start"]))
            if event["end"] < free_end:
                next_free.append((event["end"], free_end))
        free = next_free
    return free


def _overlap(start: int, end: int, other_start: int, other_end: int) -> int:
    return max(0, min(end, other_end) - max(start, other_start))


def _window_records(
    payload: WeeklyPlanPreviewRequest, summary: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    busy_by_date = _busy_intervals(payload.week_start, payload.week_start + timedelta(days=6))
    windows: list[dict[str, Any]] = []
    conflicts: list[str] = []
    for item in summary["normalized_windows"]:
        day = _week_day(payload.week_start, item["weekday"])
        start, end = _minutes(item["start_time"]), _minutes(item["end_time"])
        busy = busy_by_date.get(day.isoformat(), [])
        raw_free = _subtract_busy(start, end, busy)
        usable_free = [
            interval
            for interval in raw_free
            if interval[1] - interval[0] >= MIN_BLOCK_MINUTES
        ]
        blockers = []
        for event in busy:
            blocked = _overlap(start, end, event["start"], event["end"])
            if blocked:
                blockers.append({**event, "blocked_minutes": blocked})
                conflicts.append(
                    f"{day.isoformat()}: {blocked} min bloqueados por {event['title']}."
                )
        windows.append(
            {
                "day": day,
                "start": start,
                "end": end,
                "raw_free": raw_free,
                "usable_free": usable_free,
                "blockers": blockers,
            }
        )
    return windows, list(dict.fromkeys(conflicts))


def _eligible(day: date, deadline: datetime | None) -> bool:
    return deadline is None or day < deadline.date()


def _capacity_reason(
    priority: dict[str, Any],
    requested: int | None,
    allocated: int,
    available: int,
    usable: int,
    raw_free: int,
) -> tuple[str, str]:
    name = priority["discipline_name"]
    deadline = (
        f" antes de {priority['deadline_at'][:10]}"
        if priority.get("deadline_at")
        else ""
    )
    if requested is None:
        return "demand_unknown", f"{name} nao foi agendada porque a demanda de estudo e desconhecida."
    remaining = max(0, requested - allocated)
    if remaining == 0:
        return "fully_allocated", f"{name} recebeu {allocated} minutos no plano."
    if allocated:
        return (
            "partially_allocated",
            f"{name} recebeu {allocated} de aproximadamente {requested} minutos{deadline}; "
            f"ainda faltam {remaining} minutos.",
        )
    if available == 0:
        return (
            "no_window_before_deadline",
            f"{name} nao foi agendada: nao ha janela de disponibilidade{deadline}.",
        )
    if usable == 0 and raw_free > 0:
        return (
            "fragments_below_minimum",
            f"{name} nao foi agendada: os {raw_free} minutos livres{deadline} estao em "
            f"fragmentos menores que o minimo util de {MIN_BLOCK_MINUTES} minutos.",
        )
    return (
        "insufficient_conflict_free_capacity",
        f"{name} requer aproximadamente {requested} minutos{deadline}, mas nao restou "
        "um bloco livre suficiente depois dos eventos e prioridades anteriores.",
    )


def _allocate(
    payload: WeeklyPlanPreviewRequest,
    priorities: list[dict[str, Any]],
    summary: dict[str, Any],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[str],
    list[dict[str, Any]],
]:
    windows, conflicts = _window_records(payload, summary)
    slots: list[dict[str, Any]] = []
    for window in windows:
        for start, end in window["usable_free"]:
            slots.append({"day": window["day"], "start": start, "end": end})
    slots.sort(key=lambda item: (item["day"], item["start"]))

    blocks: list[dict[str, Any]] = []
    unallocated: list[dict[str, Any]] = []
    capacity: list[dict[str, Any]] = []

    for priority in priorities:
        deadline = (
            _parse_dt(priority["deadline_at"]) if priority.get("deadline_at") else None
        )
        requested = priority.get("estimated_demand_minutes")
        available = sum(
            window["end"] - window["start"]
            for window in windows
            if _eligible(window["day"], deadline)
        )
        raw_free = sum(
            end - start
            for window in windows
            if _eligible(window["day"], deadline)
            for start, end in window["raw_free"]
        )
        usable = sum(
            end - start
            for window in windows
            if _eligible(window["day"], deadline)
            for start, end in window["usable_free"]
        )
        remaining_before = sum(
            slot["end"] - slot["start"]
            for slot in slots
            if _eligible(slot["day"], deadline)
        )
        remaining_demand = requested
        allocated = 0

        if remaining_demand is not None:
            for slot in slots:
                if remaining_demand <= 0:
                    break
                if not _eligible(slot["day"], deadline):
                    continue
                duration = slot["end"] - slot["start"]
                if duration < MIN_BLOCK_MINUTES or remaining_demand < MIN_BLOCK_MINUTES:
                    continue
                block_minutes = min(remaining_demand, duration)
                if 0 < duration - block_minutes < MIN_BLOCK_MINUTES:
                    block_minutes = duration
                if block_minutes < MIN_BLOCK_MINUTES:
                    continue
                block_start = slot["start"]
                block_end = block_start + block_minutes
                slot["start"] = block_end
                blocks.append(
                    {
                        "temporary_id": f"block-{len(blocks) + 1}",
                        "discipline_id": priority["discipline_id"],
                        "discipline_code": priority.get("discipline_code"),
                        "discipline_name": priority["discipline_name"],
                        "content_id": priority.get("content_id"),
                        "assessment_id": priority.get("assessment_id"),
                        "title": "Estudo planejado: "
                        f"{priority.get('discipline_code') or priority['discipline_name']}",
                        "reason": priority["reason"],
                        "priority_score": priority["priority_score"],
                        "priority_band": priority["priority_band"],
                        "start_at": _local_dt(slot["day"], block_start),
                        "end_at": _local_dt(slot["day"], block_end),
                        "state": "planned",
                    }
                )
                allocated += block_minutes
                remaining_demand = max(0, remaining_demand - block_minutes)

        reason_code, reason = _capacity_reason(
            priority, requested, allocated, available, usable, raw_free
        )
        if requested is None or allocated < requested:
            unallocated.append(priority)

        blocker_totals: dict[str, dict[str, Any]] = {}
        for window in windows:
            if not _eligible(window["day"], deadline):
                continue
            for blocker in window["blockers"]:
                current = blocker_totals.setdefault(
                    blocker["id"],
                    {
                        "event_id": blocker["id"],
                        "title": blocker["title"],
                        "blocked_minutes": 0,
                    },
                )
                current["blocked_minutes"] += blocker["blocked_minutes"]

        capacity.append(
            {
                "priority_item_id": priority["priority_item_id"],
                "discipline_id": priority["discipline_id"],
                "discipline_name": priority["discipline_name"],
                "requested_minutes": requested,
                "allocated_minutes": allocated,
                "remaining_minutes": (
                    None if requested is None else max(0, requested - allocated)
                ),
                "available_minutes_before_deadline": available,
                "usable_minutes_before_deadline": usable,
                "blocked_minutes": max(0, available - raw_free),
                "allocated_to_higher_priorities_minutes": max(
                    0, usable - remaining_before
                ),
                "minimum_useful_block_minutes": MIN_BLOCK_MINUTES,
                "deadline_at": priority.get("deadline_at"),
                "reason_code": reason_code,
                "reason": reason,
                "blocking_events": list(blocker_totals.values()),
            }
        )
    return blocks, unallocated, conflicts, capacity


def build_weekly_preview(payload: WeeklyPlanPreviewRequest) -> dict[str, Any]:
    summary = availability_summary(payload)
    if summary["weekly_total_minutes"] < MIN_BLOCK_MINUTES:
        raise WeeklyPlanningError(
            "Disponibilidade insuficiente para gerar blocos planejados."
        )
    priorities = _rank_priorities(payload)
    if not priorities:
        raise WeeklyPlanningError("Nenhuma disciplina disponivel para planejamento.")
    blocks, unallocated, conflicts, capacity = _allocate(payload, priorities, summary)
    preview = {
        "study_plan_id": str(uuid4()),
        "week_start": payload.week_start.isoformat(),
        "timezone": payload.timezone,
        "availability": summary,
        "ranked_priorities": priorities,
        "planned_blocks": blocks,
        "unallocated_priorities": unallocated,
        "capacity_analysis": capacity,
        "conflicts": conflicts,
        "warnings": (
            ["A capacidade informada nao cobre toda a demanda estimada."]
            if unallocated
            else []
        ),
        "algorithm_version": ALGORITHM_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    storage.save_study_plan_preview(preview)
    return preview


def _block_conflicts(block: dict[str, Any]) -> dict[str, Any] | None:
    start = _parse_dt(block["start_at"])
    end = _parse_dt(block["end_at"])
    events = storage.list_events(
        start_at=f"{start.date().isoformat()}T00:00:00-03:00",
        end_at=f"{start.date().isoformat()}T23:59:59-03:00",
        status="confirmed",
    )
    for event in events:
        event_start = _parse_dt(event["start_at"])
        event_end = (
            _parse_dt(event["end_at"])
            if event.get("end_at")
            else event_start + timedelta(days=1 if event.get("all_day") else 0)
        )
        if start < event_end and event_start < end:
            return event
    return None


def confirm_weekly_preview(
    study_plan_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
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
        conflict = _block_conflicts(block)
        if conflict:
            skipped.append(
                {
                    "temporary_id": block["temporary_id"],
                    "reason": "Um evento confirmado passou a ocupar este horario. Gere um novo preview.",
                }
            )
            continue
        event = storage.create_event(
            {
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
            }
        )
        created.append(event)
    return created, skipped
