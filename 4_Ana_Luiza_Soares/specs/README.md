# EstudaUnB canonical specifications

`specs/` is the canonical source of truth for implementation. Canonical specifications are written in English as a project decision to standardize interpretation by the AI-assisted development workflow and to seek consistent token efficiency in that workflow. This is not a claim that English is always cheaper for every model.

Before implementing a change, read [`../AGENTS.md`](../AGENTS.md), the relevant repository skills under `../.agents/skills/`, and the applicable canonical specification. The Portuguese files in [`../spec_traduzido/`](../spec_traduzido/README.md) support human and academic review; they are secondary and must never override the English source.

## Status vocabulary

- `implemented`: the repository contains the principal behavior and supporting tests.
- `partial`: part of the contract exists, but material requirements remain unimplemented or unevaluated.
- `planned`: no material implementation evidence was found.
- `deprecated`: retained for history but should not guide new implementation.
- `superseded`: a newer specification replaces its canonical product behavior; compatible history may remain in code.

Status describes the current `main` checkout as reviewed on 2026-07-13. Public endpoint availability is documented separately from implementation completeness.

## Authoring and synchronization

1. Allocate the next number and use a descriptive kebab-case filename.
2. Write the canonical English specification here, using stable requirement and acceptance-criterion identifiers where applicable.
3. Add the metadata fields `Canonical language`, `Translation`, `Status`, and `Last reviewed` near the title.
4. Create the exact same filename under `../spec_traduzido/` and translate every technical requirement without changing identifiers, routes, JSON keys, code, enums, filenames, commands, or Mermaid node IDs.
5. Update both indexes and this traceability table. Validate links and compare filenames.
6. When behavior is replaced, keep the historical spec, mark it `superseded` or `deprecated`, add an explicit relationship notice, and point to the newer canonical behavior. Do not rewrite history silently.

Requirement IDs, tables, API payloads, acceptance-criterion numbering, links, and references must remain synchronized between languages. A canonical edit and its translation should be reviewed together. If the two diverge, the English file prevails.

## Specification index

| Spec | Title | Status | Translation | Implementation evidence | Relationship |
| --- | --- | --- | --- | --- | --- |
| 001 | EstudaUnB MVP | partial | [Português](../spec_traduzido/001-mvp-planejador-estudos-unb.md) | `backend/app`, `frontend/src`, backend tests | Foundation; later specs refine most domains |
| 002 | Minimum Web Product | implemented | [Português](../spec_traduzido/002-produto-web-minimo.md) | `frontend/src`, `backend/tests/test_openapi_docs.py` | Extends 001 |
| 003 | Study Recommendation Agent | implemented | [Português](../spec_traduzido/003-agente-recomendacao-estudos.md) | `backend/app/services/study_recommendation_agent.py`, agent tests | Extended by 005, 009, 011, 018 |
| 004 | Deployment, Monitoring, and Evaluation | partial | [Português](../spec_traduzido/004-deploy-monitoramento-avaliacao.md) | Dockerfiles, Compose, Render blueprint, agent evaluation, public HTTP check | Operational metrics and authenticated deployment smoke remain manual |
| 005 | Automated Agent Evaluation | implemented | [Português](../spec_traduzido/005-avaliacao-agente.md) | `backend/tests/test_agent_evaluation_scenarios.py` | Evaluates 003/004 |
| 006 | Public SIGAA Components | implemented | [Português](../spec_traduzido/006-sigaa-componentes.md) | `sigaa_components.py`, fixtures and tests | Refined by 010 and 018 |
| 007 | Weekly Study Planning Agent MVP | superseded | [Português](../spec_traduzido/007-agente-planejamento-semanal-estudos-mvp.md) | Legacy `study_plan_agent.py` and tests | Superseded by 014, 017, and 018 |
| 008 | Enrollment Receipt PDF Import | implemented | [Português](../spec_traduzido/008-importacao-disciplinas-comprovante-matricula-mvp.md) | `matricula_import.py`, import page and tests | Extends 001 |
| 009 | Course Plan, Assessments, and Attendance | implemented | [Português](../spec_traduzido/009-plano-ensino-avaliacoes-frequencia.md) | course-plan/academic-record routers and tests | Persistence statement superseded by 012 |
| 010 | SIGAA Enrichment and Readable Schedules | implemented | [Português](../spec_traduzido/010-enriquecimento-sigaa-horarios-legiveis.md) | SIGAA and schedule normalizer services/tests | Refines 006/008 |
| 011 | Hierarchical Content and Assisted Extraction | implemented | [Português](../spec_traduzido/011-conteudos-hierarquicos-extracao-assistida.md) | content services, UI and tests | Persistence/calendar limitations superseded by 012/013 |
| 012 | Persistence, Authentication, and Catalog | implemented | [Português](../spec_traduzido/012-persistencia-autenticacao-catalogo-academico.md) | SQLAlchemy, Alembic 001, auth/catalog/registration tests | Public registration is controlled by `ALLOW_REGISTRATION` |
| 013 | Academic Calendar, Temporal Planning, and Deployment Preparation | implemented | [Português](../spec_traduzido/013-calendario-academico-planejamento-deploy.md) | calendar migration/router/page/tests | Planning UX refined by 017/018 |
| 014 | Weekly Agenda and Automatic Study Prioritization | superseded | [Português](../spec_traduzido/014-weekly-agenda-and-automatic-prioritization.md) | priority concepts incorporated into `weekly_planning.py` | Refined/superseded by 017/018 |
| 015 | Study Method Catalog and On-Demand Study | partial | [Português](../spec_traduzido/015-study-method-catalog-and-on-demand-study.md) | canonical JSON and loader; assistant recommendations | Activity lifecycle/timer not implemented |
| 016 | Study Feedback and Method Adaptation | planned | [Português](../spec_traduzido/016-study-feedback-and-method-adaptation.md) | Specification only | Depends on 015 activity lifecycle |
| 017 | Calendar-Integrated Weekly Planning and Recurrence | implemented | [Português](../spec_traduzido/017-calendar-integrated-weekly-planning-and-recurrence.md) | `weekly_planning.py`, calendar recurrence, tests | Frontend architecture refined by 018 |
| 018 | Contextual Study Agent and Planning UX | implemented | [Português](../spec_traduzido/018-contextual-study-agent-and-planning-ux.md) | contextual assistant, unified planning, calendar/SIGAA fixes and tests | Current canonical planning UX |

See [`../docs/spec-traceability.md`](../docs/spec-traceability.md) for capability-to-code traceability.
