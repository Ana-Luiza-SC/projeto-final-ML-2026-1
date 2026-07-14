# Spec 003 — EstudaUnB Study Recommendation Agent

> Canonical language: English
> Translation: [../spec_traduzido/003-agente-recomendacao-estudos.md](../spec_traduzido/003-agente-recomendacao-estudos.md)
> Status: implemented
> Last reviewed: 2026-07-13

## Context, problem, and goals

Transform structured discipline data and backend-owned academic simulation into a clear, auditable, safe recommendation. The agent explains the academic situation, classifies recommended dedication as `low`, `medium`, or `high`, and suggests weekly actions. It never freely recalculates grade, mention, or attendance.

## Scope and non-goals

Implement an agent service, optional Google/Gemini integration, `POST /api/agent/study-recommendation`, `GOOGLE_API_KEY`, deterministic rules fallback, input/output guardrails, safe logs, structured JSON, and the discipline-detail recommendation panel.

Do not add PDF/SIGAA/calendar/persistence/auth history in this slice; do not train/fine-tune a model, rate professors, claim failure rates, integrate Google Calendar, or change deterministic academic calculations.

## Input and context retrieval

The endpoint accepts:

```json
{
  "discipline_id": "uuid",
  "target_average": 5.0,
  "pending_topics": [{"title":"GQM","difficulty":"medium","status":"not_started"}],
  "user_goal": "quero me organizar para a próxima semana"
}
```

The backend retrieves the discipline, assessments, attendance, deterministic simulation, and persisted content when applicable. Context may include code/name/class/schedule/location, partial average, contribution, completed/remaining weight, required grade, current/projected mention, grade/absence risk, attendance, warnings, confirmed content, and the bounded goal. Do not send unnecessary personal data.

## Response contract

```json
{
  "dedication_level": "low | medium | high",
  "confidence": 0.0,
  "academic_situation_summary": "",
  "grade_status": "",
  "attendance_status": "",
  "recommended_actions": [],
  "reasons": [],
  "missing_information": [],
  "used_fallback": false,
  "provider": "google | rules",
  "latency_ms": 0
}
```

Dedication is closed-enum; confidence is 0–1; actions/reasons are non-empty; missing information is explicit; provider/mode and end-to-end latency are reported. LLM failure must not cause 500 when fallback is enabled.

## Provider and prompting

```env
LLM_PROVIDER=google
GOOGLE_API_KEY=
LLM_MODEL=gemini-2.5-flash
LLM_TIMEOUT_SECONDS=8
LLM_FALLBACK_ENABLED=true
```

`GOOGLE_API_KEY` is the only official Google key variable and stays server-side, empty in `.env.example`, absent from logs/errors/frontend. Missing key, provider error, timeout, or invalid response invokes fallback.

The prompt contains bounded structured academic facts, pending content, goal, UnB mention/attendance rules, JSON-only instruction, and schema. It excludes student name/registration, verification code, raw PDF, secrets, and unnecessary personal data. The model treats deterministic facts as immutable, prioritizes absence risk, declares uncertainty, and refuses professor evaluation, unsupported failure-rate prediction, or out-of-scope requests.

## Deterministic baseline and fallback

Fallback returns the same schema with `used_fallback=true` and `provider=rules`.

High dedication conditions include attendance below 75%, high absence risk/over 25% absence, projected MI/II/SR, required remaining grade above 8 or 10, several difficult pending topics, or an imminent high-weight assessment. Medium includes medium grade risk, 15–25% absence, required grade 6–8, some pending topics, or medium deadline. Low requires compatible passing projection, comfortable attendance, low grade risk, few pending topics, and no imminent assessment. Missing data reduces certainty and is named.

## Guardrails

Validate discipline ownership/existence, `difficulty`, `status`, `target_average`, text size, and scope. Sanitize text. Validate LLM JSON/schema, closed enums, confidence, evidence fidelity, non-empty actions/reasons, and prohibited claims. Never assert final approval with pending or unknown attendance; never invent SIGAA/syllabus/rates; never rate a professor. Invalid output falls back.

## Frontend and observability

The discipline detail provides a bounded weekly goal, pending topics, loading/error/fallback states, dedication, summary, grade/attendance status, actions, reasons, and missing information. Do not show provider internals/secrets/stack traces.

Log events such as `agent_recommendation_requested`, `llm_called`, failure/timeout/invalid response, `fallback_used`, and generation. Log provider, mode, latency, error category, discipline ID, topic count, and dedication—not key, full sensitive prompt, student identity, raw PDF, or verification code.

## Test scenarios and acceptance criteria

Cover missing key, timeout, invalid JSON/schema, absent discipline, passing/MI projections, attendance below 75%/unknown, required grade above 10, difficult pending content, professor request refusal, secret-safe logs, and complete actions/reasons. Accept when the endpoint uses the exact key variable, deterministic facts, fallback, guardrails, safe observability, structured API, and frontend integration. Specs 005, 009, 011, 015, and 018 later extend evaluation/evidence/context without changing these safety principles.
