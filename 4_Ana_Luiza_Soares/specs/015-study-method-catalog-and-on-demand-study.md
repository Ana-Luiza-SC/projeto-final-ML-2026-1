# Spec 015 - Study Method Catalog and On-Demand Study Flow

## Problem statement

The product should not force a pre-scheduled study session. After the weekly agenda identifies what deserves attention, the learner should manually start a study activity when ready.

At activity start, the system should recommend suitable study methods from a local, versioned and auditable catalog. The learner may accept a recommendation or override it. The activity must support timer recovery, interruption, cancellation and completion.

## Source note

The study-method knowledge base is already present in the repository at:

```text
backend/app/knowledge/study_methods/
```

Files and roles:

- `backend/app/knowledge/study_methods/study_methods.json`: canonical machine-readable ingestion source for retrieval and method metadata.
- `backend/app/knowledge/study_methods/evidence_based_study_methods_rag.pdf`: human-readable and auditable evidence source.
- `backend/app/knowledge/study_methods/README.md`: ingestion, checksum and versioning guide.

Critical ingestion rule:

- The PDF and JSON must not both be embedded into the same vector collection.
- They contain equivalent catalog content, so embedding both would duplicate chunks and distort retrieval ranking.
- The default retrieval collection must ingest `study_methods.json` only, one chunk per method.
- The PDF must be retained as the human-readable evidence source for audit and review.
- The README must be used as the guide for idempotent upsert keys, metadata and checksums.

Current-code compatibility note:

- The existing `backend/app/services/study_strategy_catalog.py` is a legacy study-action catalog used by the current recommendation panel.
- It uses older ids such as `spaced_practice` and `concrete_examples`.
- Spec 015 defines the new on-demand study-method catalog and must use the ids from `study_methods.json`.
- Any future runtime migration must either keep APIs versioned or explicitly map `spaced_practice` to `distributed_practice` and `concrete_examples` to `worked_examples`; this spec does not implement that migration.

## Scope

This spec defines:

- local versioned study method catalog;
- allowed initial methods;
- method recommendation for on-demand study;
- manual start of a study activity;
- configurable timer and lifecycle;
- pause, resume, interruption, cancellation and completion;
- persistent activity records;
- safe recovery after browser refresh or backend restart;
- API contracts, frontend behavior, migrations, guardrails, logs and tests.

## Out of scope

- Automatic scheduling of study activities.
- External calendar integration.
- Clinical, psychological or learning-style diagnosis.
- Universal enforcement of the 25/5 Pomodoro pattern.
- LLM-defined catalog entries without local review.
- Storing private document text, prompts or PDF text in logs.
- Method adaptation from feedback. That is covered by Spec 016.

## Terminology

- Study method: a cognitive learning strategy or a time-management format used during an activity.
- Method catalog: local, versioned, auditable list of allowed methods, evidence summaries and constraints.
- Study activity: one learner-initiated study attempt with method, timer and completion data.
- Task context: discipline, content, assessment, task type, priority item and available time.
- Pomodoro: a time-management format, not a complete cognitive learning strategy.
- Cognitive activity: the actual learning task, such as retrieval, problem solving, self-explanation or worked-example study.

## Initial allowed methods

The catalog must initially allow only:

- `retrieval_practice`;
- `distributed_practice`;
- `interleaving`;
- `worked_examples`;
- `self_explanation`;
- `pomodoro`.

Critical rule:

- Pomodoro is a time-management format, not a complete cognitive learning strategy.
- A Pomodoro or configurable focus-break cycle must be paired with an activity such as retrieval, problem solving, reading with self-explanation or worked-example study.
- The UI and API must not display Pomodoro as if it were sufficient by itself.

## User stories

- As a learner, I want to start studying when I am ready, not when the system scheduled a block.
- As a learner, I want up to three recommended methods that fit the current task and time.
- As a learner, I want to override the method recommendation.
- As a learner, I want to pause, resume, cancel or complete an activity safely.
- As a learner, I want the timer to recover after refresh or backend restart.
- As an evaluator, I want the catalog to be local, versioned and auditable.

## Functional requirements

### Method catalog

- The catalog must be local to the backend and versioned.
- Each method must have a stable identifier.
- Each catalog version must record the JSON source file, PDF evidence source, README guide, checksums when available and reviewed timestamp.
- The implementation must derive machine-readable method descriptions and limitations from `study_methods.json`.
- The implementation must use `evidence_based_study_methods_rag.pdf` for human audit, not as a second retrieval ingestion source.
- The catalog must not be marked production-ready unless the JSON, PDF and README are present and their checksums match the README or an explicitly reviewed replacement.
- The catalog must expose only reviewed methods.
- The LLM may rank or explain methods from the catalog but may not invent a new method id.

Catalog fields:

- `method_id`
- `catalog_version`
- `name`
- `method_type`: `learning_strategy` or `time_management_format`
- `summary`
- `suitable_task_types`
- `requires_pairing`
- `allowed_pairings`
- `minimum_time_minutes`
- `recommended_time_range_minutes`
- `evidence_summary`
- `limitations`
- `source_references`
- `active`

### On-demand method recommendation

- The backend recommends up to three suitable methods.
- Recommendation depends on:
  - task type;
  - prior mastery;
  - previous attempts;
  - available time;
  - discipline/content/assessment context;
  - current priority item, when present.
- Recommendation must work without an LLM.
- The deterministic fallback must return ranked methods with evidence and warnings.
- If the LLM is used, it may explain or rank within allowed methods only.
- User override is allowed and must be recorded.

### Study activity lifecycle

The learner starts a study activity explicitly.

Lifecycle states:

- `draft`: created but not started;
- `active`: timer running or activity in progress;
- `paused`: temporarily stopped;
- `interrupted`: system detected recovery issue or user marked interruption;
- `cancelled`: learner ended without completion;
- `completed`: learner finished and may submit feedback;
- `expired`: stale active activity recovered after too long.

Rules:

- Only one active activity per user is allowed unless product explicitly changes that rule later.
- A study activity must link to a discipline and should link to content, assessment or priority item when available.
- Planned duration and actual duration must be stored separately.
- Method identifier and catalog version must be stored on each activity.
- Timer configuration must be stored with the activity.
- Completion must record actual minutes even when the timer was paused or interrupted.

### Timer

- Timer must be configurable.
- No universal 25/5 enforcement.
- Supported modes:
  - simple elapsed timer;
  - countdown focus block;
  - configurable focus-break cycle.
- Focus and break durations must be positive and bounded.
- Pomodoro-like cycles must still require a paired cognitive activity.
- Pauses must not count as active study time.
- Refresh or backend restart must recover from persisted timestamps and state.

## Non-functional requirements

- Backend remains authoritative for allowed methods and activity lifecycle.
- Activity state changes must be idempotent where possible.
- Timer recovery must not rely only on frontend memory.
- Activity endpoints must preserve current authentication and user isolation.
- No secrets, raw PDF text, private document text or prompts in logs.
- Tests must not require external network or LLM.

## Domain model

`StudyMethodCatalogVersion`

- `id`
- `version`
- `canonical_ingestion_source`
- `canonical_ingestion_source_sha256`
- `audit_source`
- `audit_source_sha256`
- `ingestion_guide`
- `ingestion_policy`
- `created_at`
- `reviewed_by`
- `status`: `draft`, `active`, `retired`

`StudyMethod`

- `id`
- `catalog_version`
- `method_id`
- `name`
- `method_type`
- `summary`
- `suitable_task_types`
- `requires_pairing`
- `allowed_pairings`
- `minimum_time_minutes`
- `recommended_time_range_minutes`
- `evidence_summary`
- `limitations`
- `source_references`
- `active`

`StudyActivity`

- `id`
- `user_id`
- `discipline_id`
- `content_node_id`
- `assessment_id`
- `priority_item_id`
- `task_type`
- `status`
- `method_id`
- `catalog_version`
- `method_source`: `recommended`, `override`, `manual`
- `recommendation_id`
- `planned_minutes`
- `actual_minutes`
- `timer_mode`
- `focus_minutes`
- `break_minutes`
- `cycle_count`
- `started_at`
- `paused_at`
- `resumed_at`
- `completed_at`
- `cancelled_at`
- `interruption_count`
- `created_at`
- `updated_at`

`StudyMethodRecommendation`

- `id`
- `user_id`
- `priority_item_id`
- `discipline_id`
- `content_node_id`
- `assessment_id`
- `task_type`
- `available_minutes`
- `catalog_version`
- `recommended_methods`
- `selected_method_id`
- `override_reason`
- `used_fallback`
- `provider`
- `created_at`

## Service boundaries

- `study_method_catalog`: loads and validates local catalog.
- `method_recommender`: deterministic ranking and optional LLM explanation.
- `study_activity_service`: lifecycle, timer state and recovery.
- `priority_service`: supplies what to study, not how to study.
- `feedback_service`: receives post-study evaluation in Spec 016.

## API contracts

### List catalog

```http
GET /api/study-methods/catalog
```

Response:

```json
{
  "catalog_version": "study-methods-v1",
  "canonical_ingestion_source": "backend/app/knowledge/study_methods/study_methods.json",
  "audit_source": "backend/app/knowledge/study_methods/evidence_based_study_methods_rag.pdf",
  "ingestion_guide": "backend/app/knowledge/study_methods/README.md",
  "ingestion_policy": {
    "embed_json": true,
    "embed_pdf": false,
    "reason": "Avoid duplicated chunks and distorted retrieval ranking."
  },
  "sources_available": true,
  "methods": []
}
```

### Recommend methods

```http
POST /api/study-methods/recommend
```

Request:

```json
{
  "priority_item_id": "uuid",
  "discipline_id": "uuid",
  "content_node_id": "uuid",
  "assessment_id": "uuid",
  "task_type": "problem_solving",
  "available_minutes": 45,
  "prior_mastery": "low"
}
```

Response:

```json
{
  "recommendation_id": "uuid",
  "catalog_version": "study-methods-v1",
  "recommended_methods": [
    {
      "method_id": "worked_examples",
      "rank": 1,
      "fit_score": 0.82,
      "reason": "The content is not started and the task is problem solving.",
      "required_pairing": null,
      "warnings": []
    }
  ],
  "warnings": [],
  "used_fallback": true,
  "provider": "rules"
}
```

### Start activity

```http
POST /api/study-activities
```

Request:

```json
{
  "recommendation_id": "uuid",
  "priority_item_id": "uuid",
  "discipline_id": "uuid",
  "content_node_id": "uuid",
  "assessment_id": "uuid",
  "task_type": "problem_solving",
  "method_id": "worked_examples",
  "catalog_version": "study-methods-v1",
  "method_source": "recommended",
  "planned_minutes": 45,
  "timer_mode": "focus_cycle",
  "focus_minutes": 20,
  "break_minutes": 5,
  "cycle_count": 2
}
```

Response includes the persisted activity with `status: active` and `started_at`.

### Activity lifecycle

```http
GET /api/study-activities/active
POST /api/study-activities/{activity_id}/pause
POST /api/study-activities/{activity_id}/resume
POST /api/study-activities/{activity_id}/interrupt
POST /api/study-activities/{activity_id}/cancel
POST /api/study-activities/{activity_id}/complete
```

Completion request:

```json
{
  "actual_minutes": 38,
  "completion_ratio": 0.85
}
```

Feedback fields are defined in Spec 016 and may be submitted immediately after completion.

## Frontend behavior

- The weekly priority queue has a `Start study` action.
- Starting study opens a method selection view.
- The view shows up to three recommended methods and an override option.
- Pomodoro/focus cycle controls are separate from cognitive method selection.
- If a time-management format is selected, the UI requires a paired cognitive activity.
- The timer view must show start, pause, resume, interrupt, cancel and complete.
- Refresh must restore active activity state from the backend.
- If recovery detects stale activity, show a clear choice: resume, mark interrupted or cancel.
- Do not show raw JSON, stack traces, prompt text or PDF text.

## Migrations

- Add catalog version and method tables or a versioned local JSON catalog mirrored into the database.
- Add study activity table with user isolation.
- Add recommendation table or equivalent auditable record.
- Add indexes by `user_id`, `status`, `discipline_id`, `priority_item_id` and `started_at`.
- Existing generated study sessions are not converted into activities automatically. The learner must start activities manually.

## Guardrails

- No method id outside the active catalog.
- No Pomodoro-only activity without paired cognitive task.
- No universal 25/5 enforcement.
- No LLM-created methods, source references or evidence claims.
- No embedding of both `study_methods.json` and `evidence_based_study_methods_rag.pdf` into the same vector collection.
- No activity for another user's discipline, content, assessment or priority item.
- No storage of raw PDF text, prompt or private document text in logs.
- No claim that a method guarantees a grade, approval or mastery.

## Fallback behavior

- Missing LLM: deterministic method ranking.
- Missing `study_methods.json`: catalog ingestion must fail closed and keep the catalog inactive.
- Missing PDF or README: catalog may be inspected structurally but must not be marked audited or production-ready.
- Missing task type: return general methods with low confidence and warning.
- Missing time estimate: use allowed methods that can run in a short default activity, with warning.
- Backend restart: recover active activity from persisted timestamps.
- Frontend refresh: reload active activity through `GET /active`.

## Logging and metrics

Events:

- `study_method_catalog_loaded`
- `study_method_recommendation_requested`
- `study_method_recommendation_generated`
- `study_activity_started`
- `study_activity_paused`
- `study_activity_resumed`
- `study_activity_interrupted`
- `study_activity_cancelled`
- `study_activity_completed`
- `study_activity_recovered`

Metrics:

- recommendation latency;
- selected method distribution;
- override rate;
- cancellation rate;
- interruption count;
- planned versus actual minutes;
- fallback rate;
- active activity recovery count.

Logs must include ids, counts, method ids and latency only. They must not include secrets, raw PDF text, prompts, notes or private document content.

## Acceptance criteria

- Catalog is local, versioned and auditable.
- Catalog ingestion uses `backend/app/knowledge/study_methods/study_methods.json` as the canonical machine-readable source.
- Catalog audit uses `backend/app/knowledge/study_methods/evidence_based_study_methods_rag.pdf` as the human-readable evidence source.
- Catalog versioning and checksum behavior follow `backend/app/knowledge/study_methods/README.md`.
- Tests or documentation prove that JSON and PDF are not embedded into the same vector collection.
- Initial methods are limited to the allowed list.
- Pomodoro is represented as a time-management format requiring a paired cognitive task.
- User can start an activity on demand from a priority item.
- Backend persists method id, catalog version, planned minutes and actual minutes.
- Pause, resume, interruption, cancellation and completion work through API.
- Refresh and backend restart recover activity state.
- Application works without LLM.
- User isolation tests prevent cross-user activity access.

## Unit test scenarios

- catalog rejects unknown method id;
- catalog ids match `study_methods.json`;
- ingestion configuration embeds JSON only and does not embed the PDF into the same collection;
- Pomodoro-only payload is rejected;
- deterministic recommender returns at most three methods;
- short available time filters methods below minimum duration;
- override records selected method without treating it as error;
- pause excludes paused time from actual active minutes;
- complete requires valid actual minutes;
- stale active activity can be recovered or interrupted.

## Integration test scenarios

- priority item starts a study activity for the same user;
- method recommendation uses content status and task type;
- activity survives backend restart with persisted state;
- activity endpoints reject another user's discipline or activity;
- missing LLM uses rules fallback;
- catalog source missing keeps activation warning visible.

## End-to-end test scenarios

- learner opens weekly priorities, starts study, accepts recommended method, pauses, resumes and completes;
- learner overrides recommended method and the override is stored;
- learner chooses a focus-break cycle and must pair it with retrieval or another cognitive activity;
- browser refresh during active timer restores state;
- backend unavailable produces friendly error without losing already persisted activity.

## Risks and limitations

- If the JSON and PDF drift, retrieval may remain machine-readable but auditability is weakened until the mismatch is reviewed.
- The initial deterministic recommender is a product heuristic, not a validated personal learning model.
- Timer recovery can approximate elapsed time but cannot know whether the learner actually studied while offline.
- Method fit depends on quality of task type, content status and feedback data.

## Evidence expected from implementation

- Catalog source checksums, ingestion policy and reviewed catalog version.
- Unit tests for catalog validation and Pomodoro pairing.
- API contract tests for activity lifecycle.
- Recovery test after backend restart.
- Frontend smoke test for start, pause, resume and completion.
- Logs proving no raw PDF text, prompts or secrets are emitted.

## Rollout and backward-compatibility plan

1. Add catalog as draft from `study_methods.json` and validate it against the PDF audit source and README checksums.
2. Add activity persistence and lifecycle endpoints.
3. Connect weekly priority queue to `Start study`.
4. Keep legacy generated-session endpoint available but stop presenting it as the primary study flow.
5. Add feedback collection from Spec 016 after completion.
6. Retire rigid generated sessions from the UI after on-demand activity is stable.
