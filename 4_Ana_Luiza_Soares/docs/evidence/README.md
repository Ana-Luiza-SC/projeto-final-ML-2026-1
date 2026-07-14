# Evidence index

Reviewed: 2026-07-13. Historical command results are labeled as repository evidence; only commands explicitly reported in the final task report were rerun during this documentation task.

## Available evidence

- Tests: `backend/tests/` covers calculations, recommendations, PDF import, course plans, content hierarchy, public SIGAA fixtures, persistence/auth, calendar, recurrence, planning, and contextual actions.
- Historical build/deploy evidence: [`../evidencias/spec-013/README.md`](../evidencias/spec-013/README.md), including prior backend suite, frontend build, migrations, Compose, and HTTP smoke results.
- Agent scenarios: [`../avaliacao-agente.md`](../avaliacao-agente.md) and `backend/tests/test_agent_evaluation_scenarios.py`.
- Fixture extraction evidence: sanitized SIGAA HTML fixtures and example PDFs under `pdf_exemple/`; these are test inputs, not production student evidence.
- Screenshots: none found in the tracked documentation tree.
- Deployment instructions: [`../deploy.md`](../deploy.md), `render.yaml`, Dockerfiles, and `docker-compose.yml`.
- API contracts: FastAPI routes and generated `/docs`, `/redoc`, `/openapi.json`; canonical contracts are indexed in [`../../specs/README.md`](../../specs/README.md).
- Fallback scenarios: agent, course-plan/content extraction, SIGAA, and planning tests.
- Guardrail scenarios: schema/evidence, privacy, ownership, deadline, conflict, and confirmation tests.
- Migrations: `backend/alembic/versions/001_persistence_catalog.py` and `002_academic_calendar.py`.
- Diagrams: [`../diagrams/README.md`](../diagrams/README.md) and reusable `.mmd` sources.
- Traceability: [`../spec-traceability.md`](../spec-traceability.md).

## Evidence requiring manual production

- Final deployment smoke test and verified application URL.
- Measured p50/p95 latency and error rate.
- Fallback-rate summary and provider cost, if a provider is enabled.
- Final guardrail/jailbreak evaluation report.
- Final desktop/mobile screenshots and accessibility inspection.
- Representative usability/task-completion results.
- Demonstration video and public report URL.
- Confirmation of data-source terms/licenses.
