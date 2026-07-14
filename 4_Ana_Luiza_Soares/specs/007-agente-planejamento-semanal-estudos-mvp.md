# Spec 007 — Weekly Study Planning Agent MVP

> Canonical language: English
> Translation: [../spec_traduzido/007-agente-planejamento-semanal-estudos-mvp.md](../spec_traduzido/007-agente-planejamento-semanal-estudos-mvp.md)
> Status: superseded
> Last reviewed: 2026-07-13

> **Legacy notice:** This specification contains legacy behavior superseded by Specs 014, 017, and 018. Manual numeric priority, `available_hours_per_week`, `max_session_minutes`, and rigid generated sessions are not the canonical planning UX. Refer to Spec 018; the legacy API may remain for backward compatibility.

## Historical goal and problem

The first weekly planner transformed registered disciplines and learner-supplied weekly availability, optional priorities, maximum session duration, and a short goal into a deterministic, auditable weekly plan. An LLM could explain but never change plan structure. This addressed manual allocation across partial/irregular availability and preserved a useful missing-LLM fallback.

## Legacy API contract

```http
POST /api/study-plans/generate
```

```json
{
  "discipline_ids": ["uuid-da-disciplina-1"],
  "availability": {
    "available_hours_per_week": 12,
    "days_available": ["monday", "tuesday"],
    "time_windows": [{"day":"monday","start_time":"18:00","end_time":"20:00"}]
  },
  "max_session_minutes": 90,
  "priorities": [{"discipline_id":"uuid-da-disciplina-1","priority":5}],
  "objective_text": "quero revisar para a prova da próxima semana"
}
```

The response contained `status`, `source` (`llm_assisted` or `deterministic_fallback`), structured `plan`, `summary`, `warnings`, audit `metrics`, and `request_id`. Each legacy plan item used day, sequence, discipline identifiers, duration, activity, and optional real start/end time. Errors were 422 invalid, 404 unknown discipline, 400 out of scope, or sanitized unrecoverable 500.

## Historical deterministic algorithm

1. Validate typed input and registered disciplines.
2. Normalize availability to 30-minute blocks.
3. When windows exist, they are authoritative; never schedule outside them. Without windows, never invent clock times.
4. Assign explicit 1–5 priority (neutral if omitted), reserve one minimum block when capacity permits, distribute remaining blocks proportionally, and resolve remainders stably by priority/context/code/ID.
5. Split allocations by `max_session_minutes`, allowed days/windows, and total capacity; never create zero/negative duration.
6. Validate output before any optional explanation.

Insufficient capacity either rejects when no minimum block fits or prioritizes deterministically and names uncovered disciplines. The current canonical algorithm instead derives priority and estimated demand, analyzes conflicts/deadlines/capacity, and produces confirmable planned blocks.

## Agent responsibility and fallback

Small typed functions list registered disciplines, build/validate the base plan, and generate a short explanation. The LLM may phrase distribution, interpret the bounded goal, and explain already verified limitations. It cannot create disciplines, change days/duration/priority, invent times, or contradict the base plan. Missing key, timeout, provider error, empty/invalid/schema-breaking/invented output invokes the same-contract deterministic fallback.

## Guardrails

Reject empty/duplicate/unknown discipline lists, zero/implausible hours, empty/duplicate days, invalid/non-multiple duration, invalid/overlapping windows, extra fields, excessive text, or text attempting to introduce an unselected discipline. Before response, verify selected existing disciplines, allowed days, duration bounds, capacity, window compliance, schema, and explanation consistency.

Logs may record request ID, total/LLM duration, tool names, discipline/session counts, requested/allocated minutes, validation/fallback category, model and tokens when available. Never record key, auth headers, full prompt, chain-of-thought, student identity, registration, or raw PDF.

## Legacy frontend and tests

The historical UI selected disciplines, weekly hours/days/windows, maximum session duration, numeric priorities, and goal; rendered grouped generated sessions, warnings, source, loading/errors; and retained form state after failure. Tests covered one/many disciplines, priority allocation, stable tie-breaking, allowed days/windows, max duration, block rounding, insufficient capacity, validation, LLM/fallback variants, invented discipline, API contract, sanitized errors, metrics, and UI states.

## Backward compatibility and relationship

The legacy schemas/service/tests may remain to avoid breaking callers, but new frontend code must not call this flow. Specs 009/013 added deadlines; Spec 014 replaced user priority/rigid sessions; Spec 017 added planned-block preview/confirmation and recurrence; Spec 018 owns the unified `/study-plan` UX and distinguishes planned blocks from actual study activities.
