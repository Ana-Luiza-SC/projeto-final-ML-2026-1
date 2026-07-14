# EstudaUnB diagrams

Reviewed: 2026-07-13.

Mermaid source lives in `src/`. Rendered output belongs in `rendered/`; no SVG is committed in this review because Mermaid CLI (`mmdc`) was not available. GitHub-readable copies are embedded below and in the report where useful.

Regenerate when Mermaid CLI is installed:

```bash
for file in docs/diagrams/src/*.mmd; do mmdc -i "$file" -o "docs/diagrams/rendered/$(basename "${file%.mmd}").svg"; done
```

| Diagram | Source | Related specs | Embedded here |
| --- | --- | --- | --- |
| System context | [`src/system-context.mmd`](src/system-context.mmd) | 004, 006, 012, 013, 018 | Yes |
| Containers/services | [`src/container-architecture.mmd`](src/container-architecture.mmd) | 001–018 | Yes |
| Agent decision flow | [`src/agent-decision-flow.mmd`](src/agent-decision-flow.mmd) | 003, 005, 015, 018 | Yes |
| Weekly planning | [`src/weekly-planning-flow.mmd`](src/weekly-planning-flow.mmd) | 014, 017, 018 | Yes |
| Course-plan import | [`src/course-plan-import.mmd`](src/course-plan-import.mmd) | 009, 018 | No |
| SIGAA enrichment | [`src/sigaa-enrichment.mmd`](src/sigaa-enrichment.mmd) | 006, 010, 018 | No |
| Data model | [`src/data-model.mmd`](src/data-model.mmd) | 009, 011–013, 017 | No |
| Deployment | [`src/deployment.mmd`](src/deployment.mmd) | 004, 013 | Yes |
| Specification evolution | [`src/spec-evolution.mmd`](src/spec-evolution.mmd) | 007, 013, 014, 017, 018 | Yes |

## System context

```mermaid
flowchart LR
  Student[Student] --> FE[EstudaUnB web app]
  FE --> API[EstudaUnB API]
  API --> DB[(PostgreSQL / Neon)]
  API -. optional .-> Gemini[Gemini API]
  API -. public only .-> SIGAA[Public SIGAA pages]
  Render[Render deployment] --- FE
  Render --- API
```

## Container architecture

```mermaid
flowchart TB
  FE[React + Vite SPA] --> API[FastAPI]
  API --> Auth[Authentication and ownership]
  API --> Academic[Disciplines and deterministic calculators]
  API --> Import[PDF extraction and review]
  API --> Sigaa[Public SIGAA integration]
  API --> Planning[Priority and weekly planning]
  API --> Agent[Recommendation and contextual assistant]
  Agent --> KB[Canonical study-method JSON]
  Agent -. optional .-> LLM[Gemini]
  Agent --> Fallback[Deterministic fallback]
  Auth --> DB[(SQLite / PostgreSQL)]
  Academic --> DB
  Planning --> DB
```

## Agent decision flow

```mermaid
flowchart TD
  Input[User request and selected IDs] --> Context[Rebuild owner-scoped context]
  Context --> Facts[Deterministic facts and evidence]
  Facts --> InGuard[Input guardrails]
  InGuard --> Attempt{Configured LLM available?}
  Attempt -->|yes| LLM[LLM explanation attempt]
  Attempt -->|no| Fallback[Deterministic fallback]
  LLM --> Validate{Schema and evidence valid?}
  Validate -->|no| Fallback
  Validate -->|yes| Response[Response and typed suggested actions]
  Fallback --> Response
  Response --> Confirm{Mutation proposed?}
  Confirm -->|yes| Revalidate[Human confirmation and server revalidation]
  Confirm -->|no| Done[Read-only result]
  Revalidate --> Done
```

## Weekly planning flow

```mermaid
flowchart LR
  Windows[Availability windows] --> Rank[Deterministic priority and demand]
  Events[Academic events and assessments] --> Rank
  Rank --> Allocate[Conflict/deadline-aware block allocation]
  Allocate --> Preview[Preview with capacity analysis]
  Preview --> Confirm{Student confirms?}
  Confirm -->|yes| Persist[Persist planned blocks as calendar events]
  Confirm -->|no| Discard[No mutation]
```

## Deployment

```mermaid
flowchart LR
  Browser --> Static[Render Static Site: React build]
  Static --> Service[Render Web Service: FastAPI]
  Service --> Neon[(Neon PostgreSQL)]
  Service -. optional .-> Gemini[Gemini API]
  Service -. public pages .-> SIGAA[SIGAA/UnB]
```

## Specification evolution

```mermaid
flowchart LR
  S007[007 manual priority and generated sessions] --> S014[014 automatic priority and unscheduled agenda]
  S013[013 calendar and temporal constraints] --> S017[017 confirmed planned blocks and recurrence]
  S014 --> S017
  S017 --> S018[018 unified planning UX and contextual assistant]
  S015[015 methods and study activities] -. partial dependency .-> S018
  S016[016 feedback adaptation: planned] -. future .-> S018
```
