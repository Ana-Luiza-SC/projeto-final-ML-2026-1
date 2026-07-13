# Spec 016 - Study Feedback and Method Adaptation

## Problem statement

After a learner completes a study activity, the product needs a short evaluation that can improve future method recommendations. This adaptation must be deterministic, auditable and cautious.

The system must not infer fixed learning styles, diagnose the learner or identify a preferred method after a single activity. Priority determines what to study. Method adaptation determines how to study. These scores must remain separate.

## Scope

This spec defines:

- short post-study evaluation;
- required feedback fields or justified equivalents;
- deterministic baseline adaptation algorithm;
- confidence and insufficient-data states;
- separation of subjective preference and objective performance;
- API contracts, persistence, frontend behavior, guardrails, logs and tests.

## Out of scope

- Clinical or psychological diagnosis.
- Fixed learning-style classification.
- LLM-only adaptation.
- Merging method adaptation score with study priority score.
- Automatic grade prediction.
- Professor difficulty or historical failure-rate claims.
- External wearable, biometric or health data.

## Terminology

- Feedback: learner-submitted post-activity evaluation.
- Method adaptation: deterministic adjustment of future method ranking based on comparable activity outcomes.
- Comparable observation: feedback for the same user, task type and sufficiently similar context.
- Subjective preference: learner perception, such as focus, fatigue, effectiveness and method fit.
- Objective performance: measured or self-test-based outcome, such as immediate or delayed recall score.
- Confidence: how much evidence supports an adaptation result.
- Insufficient data: state where no method preference should be claimed.

Method ids must come from the active Spec 015 catalog, whose canonical source is
`backend/app/knowledge/study_methods/study_methods.json`. The initial ids are
`retrieval_practice`, `distributed_practice`, `interleaving`, `worked_examples`,
`self_explanation` and `pomodoro`. Feedback for unknown or retired methods must be
rejected or quarantined for migration instead of being included in adaptation scores.

## User stories

- As a learner, I want to complete a short evaluation after studying.
- As a learner, I want the system to learn from what worked without locking me into one method.
- As a learner, I want to override recommendations at any time.
- As an evaluator, I want a deterministic adaptation algorithm that works without an LLM.
- As a developer, I want feedback and adaptation separated from priority scoring.

## Functional requirements

### Post-study evaluation

The evaluation must be short and optional only where noted. Required fields or justified equivalents:

- `focus_rating`;
- `fatigue_rating`;
- `perceived_effectiveness`;
- `method_fit`;
- `completion_ratio`;
- `actual_minutes`;
- `interruptions`;
- `task_type`;
- `difficulty_before`;
- `difficulty_after`;
- optional `immediate_self_test_score`;
- optional `delayed_recall_score`;
- optional `note`.

Rating scales:

- Prefer 1 to 5 integer scales for focus, fatigue, perceived effectiveness, method fit and perceived difficulty.
- `completion_ratio` range: 0 to 1.
- `actual_minutes` must be positive for completed activity.
- `interruptions` must be zero or greater.
- Self-test scores should use 0 to 1 or 0 to 10 consistently and be normalized by the backend.

### Adaptation requirements

- Do not identify a preferred method after a single activity.
- Require a minimum number of comparable observations before ranking a method as preferred.
- Keep subjective preference separate from objective performance.
- Compare methods by task type and context.
- Expose confidence and insufficient-data states.
- Do not infer fixed learning styles.
- Do not make clinical or psychological diagnoses.
- Learner may always override a recommendation.
- Overrides are observations, not errors.
- Priority determines what to study.
- Method adaptation determines how to study.
- Do not merge these two scores.
- The adaptation guardrails in `study_methods.json` are normative inputs for this policy.

### Minimum comparable observations

Initial policy:

- At least 3 completed activities for the same `method_id` and `task_type` before scoring that method as observed.
- At least 2 observed methods in the same `task_type` before showing comparative ranking.
- At least 5 total comparable observations before showing medium confidence.
- Delayed recall must not be required, but when present it should carry more weight than immediate perception.

If the minimum is not met, the API must return `insufficient_data` with next data needed.

## Non-functional requirements

- Adaptation must work without LLM.
- Algorithm must be deterministic and versioned.
- Feedback submission must be fast and idempotent per activity.
- Authenticated users must only access their own feedback and adaptation summaries.
- Logs must not include private notes by default.
- The algorithm must be labeled as a product heuristic, not a validated psychometric scale.

## Domain model

`StudyActivityFeedback`

- `id`
- `user_id`
- `study_activity_id`
- `discipline_id`
- `content_node_id`
- `assessment_id`
- `priority_item_id`
- `method_id`
- `catalog_version`
- `task_type`
- `focus_rating`
- `fatigue_rating`
- `perceived_effectiveness`
- `method_fit`
- `completion_ratio`
- `actual_minutes`
- `interruptions`
- `difficulty_before`
- `difficulty_after`
- `immediate_self_test_score`
- `delayed_recall_score`
- `note`
- `submitted_at`

`MethodAdaptationSnapshot`

- `id`
- `user_id`
- `task_type`
- `context_key`
- `algorithm_version`
- `generated_at`
- `method_scores`
- `subjective_scores`
- `objective_scores`
- `confidence`
- `status`: `insufficient_data`, `low_confidence`, `medium_confidence`, `high_confidence`
- `warnings`

`MethodAdaptationObservation`

- `id`
- `user_id`
- `feedback_id`
- `method_id`
- `task_type`
- `context_key`
- `normalized_indicators`
- `included_in_snapshot_id`

## Baseline adaptation algorithm

The initial algorithm is deterministic and works without an LLM. It is a product heuristic, not a validated psychometric scale.

For each comparable feedback observation:

```text
completion_score = completion_ratio
focus_score = normalize_1_to_5(focus_rating)
fit_score = normalize_1_to_5(method_fit)
fatigue_score = 1 - normalize_1_to_5(fatigue_rating)
difficulty_delta_score = clamp((difficulty_before - difficulty_after + 4) / 8, 0, 1)
immediate_score = normalized immediate_self_test_score, if present
delayed_score = normalized delayed_recall_score, if present
```

Objective component:

```text
objective_score =
  0.55 * delayed_score when present
  + 0.25 * immediate_score when present
  + 0.20 * completion_score
```

If delayed or immediate score is missing, redistribute its weight to completion and difficulty delta, but reduce confidence.

Subjective component:

```text
subjective_score =
  0.35 * focus_score
  + 0.30 * fit_score
  + 0.20 * perceived_effectiveness
  + 0.15 * fatigue_score
```

Combined method-fit heuristic:

```text
method_adaptation_score =
  0.60 * objective_score
  + 0.30 * subjective_score
  + 0.10 * difficulty_delta_score
```

Rules:

- Clamp scores to 0-1.
- Store score breakdown, not just final score.
- Do not calculate a comparative preference until minimum comparable observations are met.
- Do not use priority score in this calculation.
- Do not use method adaptation score to change priority score.
- Use stable tie breakers: more observations, higher delayed evidence coverage, method id.

## Confidence model

Initial confidence:

- `insufficient_data`: below minimum observations.
- `low_confidence`: minimum observations met, but no delayed recall or fewer than 5 total comparable observations.
- `medium_confidence`: at least 5 comparable observations and at least one objective measure for the top method.
- `high_confidence`: reserved for future use; not shown in MVP unless there are at least 10 comparable observations with delayed recall coverage for multiple methods.

The UI must show confidence and must not overstate adaptation.

## Service boundaries

- `study_activity_service`: owns completed activity records.
- `feedback_service`: validates and stores feedback.
- `method_adaptation_service`: computes deterministic adaptation snapshots.
- `method_recommender`: uses adaptation as one signal for method ranking.
- `priority_service`: remains separate and does not consume adaptation score as priority.

## API contracts

### Submit feedback

```http
POST /api/study-activities/{activity_id}/feedback
```

Request:

```json
{
  "focus_rating": 4,
  "fatigue_rating": 2,
  "perceived_effectiveness": 4,
  "method_fit": 5,
  "completion_ratio": 0.9,
  "actual_minutes": 38,
  "interruptions": 1,
  "task_type": "problem_solving",
  "difficulty_before": 4,
  "difficulty_after": 3,
  "immediate_self_test_score": 0.75,
  "delayed_recall_score": null,
  "note": "Worked examples helped me start faster."
}
```

Response:

```json
{
  "feedback_id": "uuid",
  "study_activity_id": "uuid",
  "status": "recorded",
  "adaptation_status": "insufficient_data",
  "warnings": [
    "More comparable observations are needed before adapting method recommendations."
  ]
}
```

### Get adaptation summary

```http
GET /api/study-methods/adaptation?task_type=problem_solving
```

Response:

```json
{
  "task_type": "problem_solving",
  "algorithm_version": "method-adaptation-v1",
  "status": "low_confidence",
  "confidence": 0.42,
  "method_scores": [
    {
      "method_id": "worked_examples",
      "observation_count": 3,
      "method_adaptation_score": 0.71,
      "objective_score": 0.66,
      "subjective_score": 0.78,
      "delayed_recall_coverage": 0.0,
      "warnings": ["No delayed recall score has been recorded yet."]
    }
  ],
  "insufficient_data": [],
  "warnings": [
    "This is a product heuristic, not a validated psychometric scale."
  ]
}
```

### Record delayed recall later

```http
PATCH /api/study-feedback/{feedback_id}/delayed-recall
```

Request:

```json
{
  "delayed_recall_score": 0.7
}
```

## Frontend behavior

- After completing a study activity, show a short feedback form.
- Keep the form compact and easy to skip only for optional note and optional self-test scores.
- Display adaptation status as:
  - not enough data;
  - early signal;
  - more evidence needed;
  - recommendation adjusted.
- Never show "your learning style is..." language.
- Keep priority and method adaptation visually separate.
- Show method recommendation overrides as valid learner choices.
- If feedback cannot be submitted, keep the completed activity and allow retry.
- Do not display stack traces or raw JSON.

## Migrations

- Add feedback table with `user_id` and `study_activity_id` uniqueness constraint.
- Add adaptation snapshot table or compute snapshots on demand with cache.
- Add delayed recall update path.
- Add indexes by `user_id`, `task_type`, `method_id`, `study_activity_id` and `submitted_at`.
- Existing study activities without feedback remain valid.

## Guardrails

- No preferred method after one activity.
- No adaptation score for a method outside the active Spec 015 catalog.
- No fixed learning-style inference.
- No clinical, psychological or health diagnosis.
- No grade guarantee, approval guarantee or mastery guarantee.
- No mixing of priority score with method adaptation score.
- No cross-user feedback access.
- No notes in logs by default.
- LLM cannot compute or overwrite adaptation score.

## Fallback behavior

- If adaptation data is insufficient, return `insufficient_data`.
- If self-test scores are absent, calculate with lower confidence.
- If delayed recall arrives later, recompute affected snapshots.
- If activity is cancelled, do not require feedback and do not include it in adaptation unless product later defines cancellation analysis separately.
- If feedback is partially invalid, return friendly validation errors and preserve completed activity.

## Logging and metrics

Events:

- `study_feedback_submitted`
- `study_feedback_validation_failed`
- `delayed_recall_recorded`
- `method_adaptation_snapshot_generated`
- `method_adaptation_insufficient_data`

Metrics:

- feedback submission rate;
- feedback completion latency after activity;
- method override rate;
- comparable observation count by task type;
- delayed recall coverage;
- confidence distribution;
- cancellation and interruption rates by method.

Logs may include ids, method id, task type, rating presence and latency. Logs must not include feedback note text, prompts, private document text, names, matricula, auth headers or secrets.

## Acceptance criteria

- Completed activity can receive one feedback record.
- Required feedback fields are validated.
- Optional self-test and delayed recall fields are supported.
- Adaptation works without LLM.
- Preferred method is not shown after one activity.
- Comparative ranking requires minimum comparable observations.
- Subjective and objective scores are exposed separately.
- Confidence and insufficient-data states are visible.
- Learner can override recommendations after adaptation.
- Priority score and method adaptation score remain separate in API and UI.
- Tests prove no fixed learning-style language is generated.

## Unit test scenarios

- normalization of 1-5 ratings;
- completion ratio bounds;
- actual minutes validation;
- feedback cannot be submitted for another user's activity;
- one observation returns insufficient data;
- three observations for one method still do not compare without another observed method;
- objective and subjective scores are calculated separately;
- missing delayed recall lowers confidence;
- delayed recall update recomputes score;
- priority score is not read by adaptation algorithm.

## Integration test scenarios

- complete activity, submit feedback, retrieve adaptation summary;
- recommendation service uses adaptation only as method-fit signal;
- cancelled activity is excluded from adaptation;
- override is stored as observation and not treated as error;
- cross-user feedback read/write is rejected;
- deterministic snapshots are stable across repeated runs.

## End-to-end test scenarios

- learner completes activity and submits feedback;
- learner sees "not enough data" after first feedback;
- after multiple comparable activities, learner sees low-confidence method signal;
- learner records delayed recall later and sees confidence update;
- learner overrides adapted recommendation and can still complete activity.

## Risks and limitations

- Self-reported feedback is noisy and subjective.
- Immediate self-test scores may not represent durable learning.
- Delayed recall is optional, so early confidence will often be low.
- The heuristic may be useful for product adaptation but is not a psychometric instrument.
- Context similarity may need refinement after real usage.

## Evidence expected from implementation

- Unit tests for deterministic scoring.
- API tests for feedback and delayed recall.
- User isolation tests.
- UI smoke test for completion feedback flow.
- Test fixture proving insufficient-data state after one activity.
- Logs showing metrics without note text or private data.

## Rollout and backward-compatibility plan

1. Add feedback persistence after Spec 015 activity completion.
2. Return insufficient-data summaries by default.
3. Enable deterministic adaptation as a method recommendation signal only after minimum observations exist.
4. Keep learner override available at all times.
5. Add delayed recall later without breaking initial feedback records.
6. Document clearly that the algorithm is a product heuristic.
