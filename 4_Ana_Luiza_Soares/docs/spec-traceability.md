# Specification traceability

Reviewed: 2026-07-13. Status refers to the current `main` checkout. Public URLs have a point-in-time HTTP check; implementation status is still based on repository evidence.

| Capability | Specs | Backend | Frontend | Tests/evidence | Status |
| --- | --- | --- | --- | --- | --- |
| Authentication and registration | 012 | `app/auth.py`, `app/routers/auth.py`, Alembic 001 | `LoginPage.tsx`, `RegisterPage.tsx` | `test_persistence_auth_catalog.py`, `test_auth_registration.py`, `RegisterPage.test.tsx` | Implemented; registration controlled by `ALLOW_REGISTRATION` |
| Discipline management | 001, 002, 012 | `routers/disciplines.py`, `storage.py` | discipline pages/components | academic, persistence, and API tests | Implemented |
| Academic calculations | 001–003, 009 | `services/academic_calculator.py`, `routers/academic_records.py` | simulation, assessment, attendance panels | `test_academic_calculator.py`, course-plan tests | Implemented |
| Public SIGAA data | 006, 010, 018 | `services/sigaa_components.py`, SIGAA/catalog routers | `SigaaComponentPanel.tsx`, catalog overview | SIGAA fixtures and `test_sigaa_components.py` | Implemented, best effort |
| Enrollment PDF import | 001, 008, 010 | `services/matricula_import.py`, import router | `MatriculaImportPage.tsx` | `test_matricula_import.py` | Implemented with human confirmation |
| Course-plan PDF extraction | 009, 018 | `services/course_plan.py`, course-plan router | discipline detail | `test_course_plan_records.py` | Implemented; intelligent attempt has local fallback |
| Content hierarchy | 011 | content map/extraction services and router | `ContentTreePanel.tsx` | `test_content_map.py` | Implemented |
| Study recommendation agent | 003, 005, 009, 011 | `study_recommendation_agent.py`, agent router | `StudyRecommendationPanel.tsx` | recommendation and evaluation tests | Implemented with deterministic fallback |
| Weekly planning | 007, 014, 017, 018 | legacy `study_plan_agent.py`; canonical `weekly_planning.py` | `StudyPlanPage.tsx` | planning and calendar-integrated tests | Implemented; 007/014 behavior is legacy/superseded |
| Academic calendar | 013, 017, 018 | calendar services/router, Alembic 002 | `CalendarPage.tsx` | academic calendar/planning tests; Spec 013 evidence | Implemented |
| Recurring events | 017 | recurrence schemas/storage expansion | calendar recurrence form | recurring-range test | Implemented for manual events |
| Study-method knowledge base / retrieval | 015, 018 | canonical JSON, `study_method_catalog.py` | contextual assistant | catalog/assistant tests; audit PDF | Partial: direct JSON recommendations implemented; RAG/vector retrieval and activity lifecycle absent |
| Contextual assistant | 018 | contextual service/router | `ContextualAssistantDrawer.tsx` | `test_contextual_assistant.py` | Implemented; mutation requires confirmation |
| Guardrails | 001, 003–018 | schema validation, evidence checks, ownership checks | friendly error/fallback states | tests across agent, import, content, calendar, auth | Implemented for tested flows; manual jailbreak evaluation pending |
| Deterministic fallback | 003–005, 007, 009, 011, 015, 018 | agent, extraction, planning, complexity services | fallback labels/messages | mocked failure and missing-key tests | Implemented |
| Monitoring | 003–005, 007–018 | structured/semi-structured application logs | fallback indicators | existing tests inspect selected log safety | Partial; no aggregated production metrics |
| Deployment | 004, 013 | Dockerfile, startup migrations | static nginx container | `render.yaml`, Compose, Spec 013 evidence, public HTTP check | Public frontend and Swagger respond; authenticated persistence smoke and operational metrics pending |

## Domain distinctions

- A **planned study block** is a confirmed `academic_event` with `event_type=study_block`; it reserves calendar time.
- A **study activity** records actual execution. Spec 015 defines it, but the lifecycle is not implemented.
- An **assessment** is graded academic work; an **academic event** is its temporal projection or another scheduled item.
- An **availability window** is user-provided candidate time used by planning.
- **Priority** is backend-derived urgency/order; **estimated study demand** is a separate evidence-qualified time estimate.
- **Learner-specific difficulty** is distinct from course demand/complexity.
- A **study method** comes from the canonical JSON catalog.
- A **fallback** is a deterministic degraded path; a **guardrail** validates or blocks unsafe input/output/action.

## Known evidence boundaries

The provided product and Swagger URLs responded HTTP 200 on 2026-07-13. No evidence yet establishes measured p95 latency, provider cost, fallback rate, usability outcome, final screenshots, demonstration video, deployment SLA, or an independently verified Neon configuration.
