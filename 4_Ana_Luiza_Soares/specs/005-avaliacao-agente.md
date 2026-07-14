# Spec 005 — Automated Evaluation of the EstudaUnB Agent

> Canonical language: English
> Translation: [../spec_traduzido/005-avaliacao-agente.md](../spec_traduzido/005-avaliacao-agente.md)
> Status: implemented
> Last reviewed: 2026-07-13

## Goal and context

Retroactively document the implemented automated evaluation slice required by Specs 003 and 004, preserving traceability between requirements, implementation, and results. Evaluation exercises `POST /api/agent/study-recommendation` without `GOOGLE_API_KEY` and treats deterministic rules fallback as the controlled evaluation path.

## Implemented scope

- Eight automated baseline scenarios.
- Required response-field checks.
- Unknown-attendance and absence-risk guardrails.
- Missing-key operation with `used_fallback=true` and `provider=rules`.
- Supporting documentation in `docs/avaliacao-agente.md`.

## Scenarios and metrics

1. Projected MM with adequate attendance.
2. Projected MS with unknown attendance.
3. Projected MI with adequate attendance.
4. Attendance below 75%.
5. Required grade above 10.
6. No registered assessments.
7. Several difficult pending topics.
8. Missing `GOOGLE_API_KEY`.

Tests verify `dedication_level`, `used_fallback`, `provider`, non-empty `reasons` and `recommended_actions`, no final-approval claim with unknown attendance, explicit absence risk below 75%, and successful response without a provider key.

## Guardrails

The agent does not depend on a provider key, uses deterministic fallback when absent, does not assert final approval with unknown attendance, highlights low-attendance risk, and preserves a structured actionable response.

## Evidence and historical result

Related files are `backend/tests/test_agent_evaluation_scenarios.py`, `docs/avaliacao-agente.md`, and Specs 003/004. The original result recorded 34 passing backend tests, including the eight scenarios. The current repository contains a substantially larger suite; the old count is historical and is not a current suite-size claim.

## Non-goals and limitations

No real Gemini call, external-network latency/timeout/invalid-output validation, manual UX evaluation, runtime change, SIGAA, PDF, persistence, or calendar work. Current tests mock additional provider failures elsewhere, but this slice itself evaluates the rules path. The no-assessment outcome may require review if deterministic projection rules change.

## Acceptance criteria

The spec and the eight tests exist, describe already implemented behavior without adding functionality, align with Specs 003/004, record evidence honestly, and support the final report.
