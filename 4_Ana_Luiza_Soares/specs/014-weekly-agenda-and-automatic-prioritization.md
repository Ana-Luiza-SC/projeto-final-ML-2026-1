# Spec 014 - Weekly Agenda and Automatic Study Prioritization

> Canonical language: English
> Translation: [../spec_traduzido/014-weekly-agenda-and-automatic-prioritization.md](../spec_traduzido/014-weekly-agenda-and-automatic-prioritization.md)
> Status: superseded
> Last reviewed: 2026-07-13

> **Relationship notice:** Spec 017 supersedes the unscheduled-only planning direction with previewed and confirmed planned study blocks. Spec 018 is canonical for the current planning UX. Automatic deterministic priority remains authoritative.

## Problem statement

The current product can store academic events and generate weekly study sessions. That model is too rigid for the next product direction because it turns recommendations into a pre-scheduled calendar that the learner may not actually follow.

The product must shift to a weekly academic agenda with:

- confirmed academic events, exams, assignments, presentations and deadlines;
- a prioritized queue of unscheduled study items for the week;
- deterministic backend-owned priority scores;
- optional LLM explanations that never define or overwrite authoritative scores.

The learner should decide when to study. The system should tell the learner what deserves attention and why.

## Scope

This spec defines:

- weekly calendar and agenda view;
- academic events and deadlines as scheduled items;
- unscheduled study priorities as a queue;
- removal or deprecation of rigid generated study sessions;
- deterministic priority calculation owned by the backend;
- priority explanation with evidence;
- user override without replacing the authoritative audit record;
- backend schemas, service boundaries, API contracts and persistence changes;
- migration strategy for existing generated sessions;
- frontend states for events, top priorities, overdue or blocked items and insufficient-data warnings;
- tests, authorization, observability and rollout.

## Out of scope

- Google Calendar, Outlook, email, push notifications or external calendar sync.
- Login to SIGAA or authenticated scraping.
- Inventing deadlines, weights, grades, mastery, content or prerequisite relationships.
- Monthly or daily productivity automation beyond the existing simple calendar.
- LLM-defined priority, difficulty or academic risk.
- Automatic creation of study activities. Study activities are covered by Spec 015.
- Method adaptation. That is covered by Spec 016.

## Terminology

- Academic event: a scheduled academic item such as exam, assignment, presentation, class activity or deadline.
- Deadline: the latest relevant date for a study item, assessment or deliverable.
- Study priority: an unscheduled recommendation about what to study next.
- Priority score: deterministic backend score used for ordering what to study.
- Estimated difficulty: separate estimate about how hard the task appears. It must not be merged with priority score.
- Evidence: structured data that supports a recommendation, such as assessment date, assessment weight, content status, grade simulation, attendance risk or confirmed course plan data.
- Blocked item: a content or assessment that cannot be prioritized safely because required data is missing or contradictory.
- Override: learner action that changes display order, hides an item or pins an item, without modifying the authoritative priority audit record.

## User stories

- As a learner, I want to see this week's academic events and deadlines so that I know what is fixed in time.
- As a learner, I want a top-priority study queue so that I can choose what to study when I am available.
- As a learner, I want every priority explained with evidence so that I can trust or challenge it.
- As a learner, I want to override the displayed order without erasing the system's original score.
- As a learner, I want warnings when the system lacks dates, weights, grades, content or frequency data.
- As an evaluator, I want deterministic priority tests so that the product is auditable without an LLM.
- As a developer, I want a migration path from generated sessions to unscheduled priorities without breaking existing routes immediately.

## Functional requirements

### Weekly agenda

- The weekly view must cover Monday to Sunday in `America/Sao_Paulo`.
- The backend must accept an explicit `week_start` date or derive the current local week.
- Scheduled academic events must be shown in their date/time positions.
- Study priorities must remain unscheduled and displayed as a queue, not as calendar sessions.
- The weekly UI must clearly separate:
  - events;
  - top study priorities;
  - overdue or blocked items;
  - insufficient-data warnings.

### Events and deadlines

- The system must use existing `academic_events` for exams, assignments, presentations, deadlines and manual academic events.
- Events synced from assessments remain authoritative only when the assessment exists and belongs to the current user.
- Cancelled or completed events must not produce active study priorities unless there is another future relevant assessment.
- Study recommendations must not be produced after the relevant assessment date.
- A priority tied to an assessment dated before the week start must be marked `overdue_or_expired` and must not be shown as a normal active recommendation.

### Deterministic priority calculation

The backend must own an auditable priority service. The LLM may explain priority but may not define, modify or overwrite scores.

The initial score must be deterministic and use only available structured data:

- deadline proximity;
- assessment weight;
- current mastery gap;
- prerequisite dependency, only when explicitly confirmed by the user or future domain model;
- unfinished content;
- previous performance;
- academic risk;
- available evidence.

The first implementation may use a normalized product heuristic:

```text
priority_score =
  deadline_component +
  weight_component +
  mastery_gap_component +
  prerequisite_component +
  unfinished_content_component +
  previous_performance_component +
  academic_risk_component +
  evidence_quality_component
```

Rules:

- Score range: `0` to `100`.
- Priority bands: `low` 0-39, `medium` 40-69, `high` 70-100.
- Missing data must not be invented. Missing high-value data should reduce confidence and create warnings.
- An item with no evidence must not receive a high priority.
- Deadline proximity must be capped so that expired assessments do not keep generating active study recommendations.
- Estimated difficulty must be stored and displayed separately.
- Academic risk must come from deterministic academic simulation and attendance calculation.
- Mastery gap must come from stored content status, self-test fields, grades or confirmed feedback, never from LLM guesswork.

### Evidence and explanations

- Every priority item must include evidence objects.
- Evidence must identify the source type, source id when available, human-readable summary and timestamp.
- LLM explanations are optional and must be validated against the deterministic score and evidence list.
- If the LLM is unavailable, explanations must be generated by deterministic templates.
- The UI must show enough evidence for audit, without exposing technical stack traces or sensitive document text.

### User override

- The learner may pin, hide, snooze or manually raise/lower display order.
- Overrides affect display only.
- Overrides must not replace the authoritative priority score or audit trail.
- The API must return both `priority_score` and `display_rank`.
- Overrides are observations for later product learning, not errors.

## Non-functional requirements

- The system must remain usable without an LLM.
- Backend remains authoritative for scores, filters and data isolation.
- Priority generation should finish within 500 ms for a normal week without LLM.
- LLM explanation, when enabled, must have timeout and fallback.
- Logs must omit names, matricula, PDF text, prompts, credentials and auth headers.
- All academic routes must preserve the current authentication model and user isolation.
- Tests must not depend on external network or SIGAA availability.

## Domain model

### Existing entities reused

- `Discipline`
- `Assessment`
- `AcademicEvent`
- `ContentNode`
- `AssessmentContentAssociation`
- academic simulation and attendance summaries

### New or changed entities

`StudyPriorityRun`

- `id`
- `user_id`
- `week_start`
- `algorithm_version`
- `generated_at`
- `input_snapshot_hash`
- `item_count`
- `used_llm_explanation`
- `fallback_reason`

`StudyPriorityItem`

- `id`
- `run_id`
- `user_id`
- `discipline_id`
- `content_node_id`
- `assessment_id`
- `event_id`
- `title`
- `task_type`
- `priority_score`
- `priority_band`
- `estimated_difficulty`
- `confidence`
- `deadline_at`
- `expired_after`
- `status`
- `display_rank`
- `score_breakdown`
- `evidence`
- `warnings`

`StudyPriorityOverride`

- `id`
- `user_id`
- `priority_item_id`
- `override_type`: `pin`, `hide`, `snooze`, `manual_rank`, `dismiss`
- `value`
- `reason`
- `created_at`

`PriorityEvidence`

- `source_type`: `assessment`, `event`, `content`, `simulation`, `attendance`, `course_plan`, `feedback`
- `source_id`
- `summary`
- `observed_at`

## Service boundaries

- `calendar_events`: CRUD, sync and extraction of scheduled academic events.
- `priority_calculator`: deterministic score calculation and score breakdown.
- `priority_explainer`: deterministic explanation templates plus optional LLM explanation.
- `priority_repository`: persistence of runs, items and overrides.
- `study_activity`: not implemented here; Spec 015 starts activities from priority items.
- `recommendation_agent`: may consume priority context but cannot calculate priority.

Spec 014 must pass only task context, priority evidence and stable ids to Spec 015.
It must not select study methods, embed the study-method knowledge base or create study
activities. Method ids and catalog evidence belong to Spec 015.

## API contracts

### Get weekly agenda

```http
GET /api/agenda/weekly?week_start=2026-07-13
```

Response:

```json
{
  "week_start": "2026-07-13",
  "timezone": "America/Sao_Paulo",
  "events": [],
  "top_study_priorities": [],
  "overdue_or_blocked_items": [],
  "insufficient_data_warnings": [],
  "generated_at": "2026-07-13T10:00:00-03:00",
  "algorithm_version": "priority-v1"
}
```

### Generate or refresh priorities

```http
POST /api/study-priorities/weekly
```

Request:

```json
{
  "week_start": "2026-07-13",
  "discipline_ids": ["uuid"],
  "explain_with_llm": false
}
```

Response:

```json
{
  "run_id": "uuid",
  "week_start": "2026-07-13",
  "items": [
    {
      "id": "uuid",
      "discipline_id": "uuid",
      "content_node_id": "uuid",
      "assessment_id": "uuid",
      "event_id": "uuid",
      "title": "Review content linked to Exam 1",
      "task_type": "retrieval_review",
      "priority_score": 82,
      "priority_band": "high",
      "estimated_difficulty": "medium",
      "confidence": 0.78,
      "deadline_at": "2026-07-16T00:00:00-03:00",
      "status": "active",
      "display_rank": 1,
      "score_breakdown": {
        "deadline_proximity": 25,
        "assessment_weight": 18,
        "mastery_gap": 15,
        "unfinished_content": 12,
        "previous_performance": 5,
        "academic_risk": 7,
        "available_evidence": 0
      },
      "evidence": [],
      "warnings": []
    }
  ],
  "warnings": [],
  "used_fallback": true,
  "provider": "rules"
}
```

### Override display

```http
POST /api/study-priorities/{priority_item_id}/override
```

Request:

```json
{
  "override_type": "pin",
  "value": true,
  "reason": "I want to study this first today."
}
```

The response must return the override and the unchanged authoritative `priority_score`.

## Frontend behavior

- Replace "Gerar agenda semanal" behavior with "Atualizar prioridades da semana".
- Keep the calendar for academic events and deadlines.
- Show a separate "Top study priorities" queue with score, band, deadline and evidence.
- Do not place study priorities as scheduled blocks on the calendar.
- Provide actions: `Start study`, `Pin`, `Snooze`, `Hide`, `View evidence`.
- Show blocked items when dates, weights, content links or simulation data are missing.
- Show expired items separately when their assessment date has passed.
- If the backend is offline, keep current events visible if already loaded and show a retry state.
- If no LLM is configured, show deterministic explanation status without treating it as failure.

## Migrations

- Add tables for priority runs, priority items and overrides.
- Keep existing `academic_events`.
- Keep existing `StudyPlanSession` contracts temporarily as legacy.
- Existing generated sessions should not be silently deleted. Migration should either:
  - mark them as `legacy_generated_session`; or
  - stop rendering them in the weekly agenda while keeping API compatibility until removed.
- Add nullable fields first, backfill from events and assessments, then enforce constraints where safe.
- Migration must be user-isolated by `user_id`.

## Guardrails

- No recommendation after the relevant assessment date.
- No invented deadlines, weights, grades, content, mastery or prerequisite dependency.
- No professor difficulty or historical failure-rate claims.
- No assertion of final approval when frequency is unknown.
- No LLM overwrite of `priority_score`, `score_breakdown`, `status` or `display_rank`.
- No cross-user events, disciplines, contents, assessments or priority items.
- No technical error messages exposed to the frontend.

## Fallback behavior

- If LLM is missing, invalid or slow, use deterministic explanations.
- If an assessment lacks date, show blocked/insufficient-data warning.
- If a weight is missing, calculate priority without the weight component and lower confidence.
- If mastery is unknown, avoid high-confidence claims about mastery gap.
- If no content is linked to a future assessment, prioritize the assessment only if date and weight evidence exist, and recommend linking content as the action.
- If there are no events or assessments, show an empty agenda plus data-entry guidance.

## Logging and metrics

Events:

- `weekly_agenda_requested`
- `study_priority_run_started`
- `study_priority_item_scored`
- `study_priority_run_completed`
- `study_priority_llm_explanation_failed`
- `study_priority_override_created`
- `study_priority_expired_item_filtered`

Metrics:

- priority generation latency;
- item count;
- high/medium/low count;
- blocked item count;
- expired item count;
- override rate;
- LLM fallback rate;
- insufficient-data warning count.

Logs must not include names, matricula, PDF text, prompts, tokens, auth headers or secrets.

## Acceptance criteria

- Weekly agenda returns events and unscheduled priorities separately.
- Deterministic tests verify stable priority ordering.
- LLM cannot alter scores or order.
- Recommendations after assessment date are filtered or marked expired.
- Every priority has evidence or an insufficient-data warning.
- Priority score and estimated difficulty are separate fields.
- User override changes display order without changing score audit.
- Existing generated sessions have a backward-compatibility or migration path.
- Authenticated users cannot access other users' priorities or events.
- Frontend shows events, top priorities, overdue/blocked items and insufficient-data warnings.

## Unit test scenarios

- deadline proximity increases priority before the assessment date;
- expired assessment does not produce active recommendation;
- high assessment weight increases priority when weight is known;
- missing weight lowers confidence and creates warning;
- unfinished high-risk content outranks reviewed content with same deadline;
- academic risk influences score using deterministic simulation only;
- difficulty does not overwrite priority;
- override does not mutate `priority_score`;
- LLM explanation attempting to change score is rejected.

## Integration test scenarios

- weekly agenda uses authenticated user's events only;
- assessment-event sync feeds priority calculation;
- course plan extracted events appear in the agenda after confirmation only;
- missing date produces blocked item;
- legacy study-plan endpoint still responds during migration;
- priority refresh creates auditable run and item records.

## End-to-end test scenarios

- user logs in, opens calendar, sees events and top priorities;
- user refreshes priorities without `GOOGLE_API_KEY` and receives deterministic explanations;
- user pins a priority and sees changed display order with unchanged score;
- user tries to study after an assessment date and sees the item expired or blocked;
- user with no assessments receives insufficient-data guidance.

## Risks and limitations

- The initial priority formula is a product heuristic, not a validated psychometric model.
- Mastery gap may be weak until feedback from Spec 016 exists.
- Prerequisite dependency must remain absent unless explicitly modeled or confirmed.
- Existing UI copy may need careful migration because "agenda" currently includes generated study sessions.

## Evidence expected from implementation

- Deterministic test report for priority calculation.
- API contract tests for agenda and overrides.
- Migration test proving existing academic events remain intact.
- User-isolation tests for priority data.
- Frontend screenshots or smoke tests showing separate event and priority sections.
- Logs showing fallback without sensitive data.

## Rollout and backward-compatibility plan

1. Add priority tables and service behind new endpoints.
2. Add weekly agenda response while keeping old study-plan endpoint.
3. Update calendar UI to show priorities as a queue.
4. Mark generated sessions as legacy in UI and docs.
5. Deprecate rigid generated-session creation after Spec 015 provides on-demand activities.
6. Remove or archive legacy session UI only after tests and demo scripts are updated.
