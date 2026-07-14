# Spec 004 — EstudaUnB Deployment, Monitoring, and Evaluation

> Canonical language: English
> Translation: [../spec_traduzido/004-deploy-monitoramento-avaliacao.md](../spec_traduzido/004-deploy-monitoramento-avaliacao.md)
> Status: partial
> Last reviewed: 2026-07-13

## Goal and problem

Make the MVP reproducible, demonstrable, reliable, and evaluable through Docker/Compose, environment configuration, safe logs, agent/API/UX evaluation, edge cases, and a demo script. Local deployment is required by this slice; public cloud deployment was optional. Current Render/Neon preparation comes from Spec 013, but no verified public deployment evidence exists.

## Local deployment

```bash
docker compose up --build
```

Expected services are FastAPI at `http://localhost:8000`, frontend at `http://localhost:5173`, and Swagger at `http://localhost:8000/docs`. The complete flow must support health, discipline, attendance, assessment, simulation, recommendation, and missing-key fallback.

Backend uses a stable Python image, installs `requirements.txt`, listens on 8000, reads server-side LLM variables, and works without a key. Frontend uses a Node build/static-serving strategy, publishes the documented port, uses `VITE_API_BASE_URL`/`VITE_API_URL`, and never receives `GOOGLE_API_KEY`. Compose starts both, maps ports, accepts an ignored local `.env`, and does not require a provider key.

## Configuration and public deployment guardrails

```env
LLM_PROVIDER=google
GOOGLE_API_KEY=
LLM_MODEL=gemini-2.5-flash
LLM_TIMEOUT_SECONDS=8
LLM_FALLBACK_ENABLED=true
VITE_API_BASE_URL=http://localhost:8000
```

Never commit `.env`, expose the key through logs/OpenAPI/frontend/errors, use unrestricted CORS without justification, retain raw PDFs, or put real personal data in fixtures/logs. Render configuration now separates a Docker Web Service and Static Site; PostgreSQL/Neon uses `DATABASE_URL`. Public verification remains manual.

## Monitoring and observability

Expected events include discipline/assessment creation, attendance update, simulation, agent request, LLM call/failure/timeout, fallback, and result. Record timestamp/event, latency, provider, fallback flag/category, status/error type, safe discipline ID, topic count, and dedication where relevant. Never record API keys, student identity/registration, raw PDF, verification code, or full sensitive prompt.

## Agent evaluation

Use controlled, non-personal scenarios:

1. projected MM + adequate attendance;
2. projected MS + unknown attendance;
3. projected MI + adequate attendance;
4. attendance below 75%;
5. required grade above 10;
6. no assessments;
7. several difficult pending topics;
8. missing `GOOGLE_API_KEY`.

Check dedication, grade/absence explanation, improper approval claims, actionable output, fallback flag/provider, and approximate latency. Spec 005 records automated fallback coverage; `docs/avaliacao-agente.md` contains historical outcomes.

## API and UX evaluation

Verify health/docs/OpenAPI, manual discipline, assessment, attendance, academic simulation, agent fallback, validation errors, missing discipline, and graceful provider failure. Required metrics were mean agent latency, fallback rate, API error rate, non-empty action/reason rate, and scenario accuracy; repository evidence does not contain final production aggregates.

The UX study should time the end-to-end task and assess friendly errors, no stack traces, simulation labeling, approval uncertainty, visible fallback, and discoverable Swagger. A final representative usability result remains manual.

## Edge cases and guardrails

Exercise empty/invalid/oversized input, invalid `difficulty`/`status`, missing discipline, provider unavailable/timeout/invalid output, offline backend, professor/rate requests, empty topics, unknown/low attendance, and required grade above 10. Never invent public data, expose secrets, rate professors, or claim final approval without final grade and attendance.

## Acceptance criteria and evidence expected

Accept when Dockerfiles/Compose/config exist, services start, Swagger/front-to-back flow works, missing-key fallback remains complete, logs are safe, and evaluation is documented. Current repository has the files and historical local evidence, but measured operational metrics, public deployment smoke, final UX study, screenshots, and video are still missing; therefore status is `partial`.

## Relationship

Specs 005 and 013 implement major evaluation/deployment preparation. Specs 017/018 replace the legacy planning-demo flow with priority, capacity, planned-block confirmation, calendar Month/Week views, and contextual actions.
