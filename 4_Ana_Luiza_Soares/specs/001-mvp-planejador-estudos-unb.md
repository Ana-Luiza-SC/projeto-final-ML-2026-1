# Spec 001 — EstudaUnB MVP

> Canonical language: English
> Translation: [../spec_traduzido/001-mvp-planejador-estudos-unb.md](../spec_traduzido/001-mvp-planejador-estudos-unb.md)
> Status: partial
> Last reviewed: 2026-07-13

## Title and context

EstudaUnB — Academic Planning Agent for UnB Students. The product helps a learner organize disciplines, content, assessments, grades, attendance, and study actions from fragmented SIGAA, PDF, note, and calendar information.

## Problem statement and stakeholders

The central problem is turning a schedule and assessments into an actionable, auditable study plan. Stakeholders are UnB students, the evaluating course team, and project developers. The primary user is a currently enrolled UnB student.

## Goals and success criteria

A learner should import or manually register at least one discipline, add an assessment, and receive a study recommendation in under five minutes. Historical target metrics defined by this spec were: at least 80% correct code/name/schedule extraction over the test PDF set; recommendation API average below 10 seconds; friendly handling of all invalid inputs; manual fallback for PDF/scraping failure; and logging of latency, error, and fallback. These are targets, not measured final results.

## MVP scope

1. Enrollment-certificate PDF upload, extraction preview, and human review.
2. Manual discipline registration fallback.
3. Study-content, assessment, weight, and grade registration.
4. Deterministic partial average and required-grade calculations.
5. AI-assisted dedication classification and weekly study recommendations.
6. Friendly fallback when PDF, public scraping, or AI fails.

## Non-goals

No SIGAA login/authenticated scraping, professor failure history/rating, Google Calendar, native mobile app, complex trained prediction model, or permanent raw-PDF storage. The original complete monthly/daily-calendar non-goal was superseded by Specs 013, 017, and 018.

## Data sources and privacy

Allowed inputs are learner-uploaded enrollment PDF, manually entered disciplines, study content, assessments/weights/grades, and target average. External data is limited to public SIGAA/UnB component and, when technically viable, public turma pages. Do not depend on unconfirmed professor failure-rate data. Raw enrollment PDFs are not stored by default.

## Domain model

- `Discipline`: `id`, `code`, `name`, `class_code`, `professor`, `schedule`, `syllabus`, `source_url`, timestamps.
- `StudyTopic`: discipline, title, description, `status` (`not_started`, `in_progress`, `reviewed`), `difficulty` (`low`, `medium`, `high`), due date.
- `Assessment`: discipline, name, weight, grade, date, topics.
- `GradeSimulation`: current average, completed/remaining weight, target and required remaining average, risk.
- `StudyRecommendation`: discipline, dedication, confidence, evidence reasons, actions, timestamp.

Later specs refine `StudyTopic` into hierarchical `ContentNode`, introduce `academic_events`, and distinguish planned study blocks from actual study activities.

## API contracts

Historical minimum endpoints were PDF import, confirm import, discipline CRUD, topics, assessments, grade simulation, and `POST /api/agent/study-recommendation`. Current routes are authoritative where names evolved; see OpenAPI and later specs.

PDF failure must remain friendly and identify manual entry:

```json
{
  "status": "error",
  "message": "Não foi possível extrair disciplinas do PDF. Cadastre manualmente.",
  "fallback": "manual_entry"
}
```

The recommendation receives a `discipline_id` and `target_average` and returns `dedication_level`, `confidence`, evidence-based `reasons`, and `recommended_actions`. Literal Portuguese UI strings remain Portuguese.

## UnB academic rules

- Mentions are SS, MS, MM, MI, II, and SR; SS/MS/MM pass and MI/II/SR fail.
- Minimum attendance is 75%; absence above 25% is serious failure risk.
- Attendance risk must be reported even with a good grade.
- Do not assert final approval when attendance is unknown.
- Grade, mention, and attendance calculations are deterministic; an AI explains/recommends but does not freely calculate them.

The historical formulas are:

```text
partial_average = sum(grade * weight) / sum(completed_weights)
current_contribution = sum(grade * weight)
required_remaining = (target_average - current_contribution) / remaining_weight
```

Normalize percentage weights to 0–1. Validate grades from 0–10 and weights from 0–100%. Historical grade-risk bands were low at required ≤ 6, medium at > 6 and ≤ 8, and high above 8; imminent high-weight assessments or many difficult pending topics may add recommendation urgency.

## Agent responsibilities, guardrails, and fallback

Use pending content, learner-specific difficulty, confirmed assessment dates/weights, deterministic academic results, and public syllabus/workload when present. Return dedication, confidence, reasons, and actions; declare missing evidence. Do not invent SIGAA data, rates, dates, grades, content, or professor assessments.

Reject empty/non-PDF input, invalid disciplines, weights, and grades. If PDF parsing fails, keep manual entry; if SIGAA fails, keep the discipline without invented syllabus; if AI fails, use deterministic rules; if calculation lacks fields, name them.

## Frontend and acceptance criteria

The original pages were Home, Import, Disciplines, and Discipline Detail. Later specs add protected planning/calendar/assistant surfaces. Acceptance requires runnable backend/frontend, manual discipline entry, PDF extraction preview with edit/confirm, assessment entry, deterministic simulation, explained recommendation, invalid-PDF fallback, SIGAA-independent operation, and Docker/Compose execution. Cloud deployment, measured targets, Spec 015 activity lifecycle, and Spec 016 feedback adaptation remain incomplete, so the overall foundation is `partial`.

## Relationship to other specs

Specs 002–013 implement/refine the MVP domains. Specs 014, 017, and 018 supersede manual priority and rigid generated-session planning. Spec 015 is partial and Spec 016 is planned.
