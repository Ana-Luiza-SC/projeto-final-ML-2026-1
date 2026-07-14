# Spec 002 — EstudaUnB Minimum Web Product

> Canonical language: English
> Translation: [../spec_traduzido/002-produto-web-minimo.md](../spec_traduzido/002-produto-web-minimo.md)
> Status: implemented
> Last reviewed: 2026-07-13

## Goal and problem

Create a simple React/Vite/TypeScript frontend for the existing FastAPI: check health, create/list/open disciplines, update attendance, add assessments, and display deterministic mention/attendance simulation. This closes the gap between the API and a navigable product while preserving UnB guardrails. This slice originally excluded AI, PDF, SIGAA, auth, and calendar; later specs add them without invalidating this baseline.

## User flow and frontend behavior

1. Home presents EstudaUnB and `GET /api/health` as checking/online/offline.
2. Disciplines lists records and offers manual code, name, professor, class, schedule code, location, total-class, and absence fields.
3. Detail shows basic data, attendance/class-hour input, assessment input, and simulation.
4. Simulation presents partial average, current contribution, completed/remaining weight, required grade, current/projected *menção*, grade risk, attendance, absence risk, summary, and warnings.
5. Unknown attendance is explicit and never becomes a final approval claim.

Use a light client (`fetch` or equivalent), existing styling, and no heavy calendar dependency for this slice.

## API contracts

Base URL is environment-controlled. FastAPI provides `/docs`, `/redoc`, and `/openapi.json`, with title `EstudaUnB API`, version `0.1.0`, description, and tags for health, disciplines, assessments, attendance, and academic simulation.

Consumed endpoints:

- `GET /api/health` → `{"status":"ok"}`;
- `POST /api/disciplines`, `GET /api/disciplines`, `GET /api/disciplines/{id}`;
- `PATCH /api/disciplines/{id}/attendance`;
- `POST /api/disciplines/{id}/assessments`;
- `GET /api/disciplines/{id}/academic-simulation?target_average=5.0`.

Preserve JSON identifiers such as `code`, `name`, `professor`, `class_code`, `schedule_code`, `local`, `total_classes`, `missed_classes`, `total_class_hours`, `missed_class_hours`, `weight`, `grade`, and `topics`. Expected errors include 404 for missing discipline and 400/422 for invalid absence, grade, or weight.

## Guardrails and fallback UX

- API offline: friendly retry state.
- Failed create: retain form values and show readable error.
- Missing discipline: return to list with notice.
- Grade must be 0–10; weights accept valid decimal/percentage forms; absences cannot exceed total.
- No assessments means insufficient simulation data; unknown attendance means no final approval statement.
- Never expose stack traces; use the official term *menção* prominently.

## Non-goals

For this historical slice: authentication, calendar, PDF upload/parsing, LLM agent, live SIGAA, advanced edit, analytics, professor rating, or final approval with unknown attendance.

## Tests and acceptance criteria

Frontend expectations cover health online/offline, manual create/list/detail, attendance, assessment, simulation rendering, warnings, and unknown-attendance guardrail. Backend expectations cover HTTP 200 for docs/OpenAPI and required title/tags. Acceptance requires a small navigable frontend consuming current endpoints with friendly errors and preserved OpenAPI documentation. Later implementation evidence is `frontend/src` and `backend/tests/test_openapi_docs.py`.

## Relationship

Extends Spec 001. Specs 003 and 006–018 add agent, data import/enrichment, persistence/auth, calendar, and current planning UX.
