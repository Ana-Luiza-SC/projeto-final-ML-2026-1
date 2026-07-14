# Spec 009 — Course Plan, Future Assessments, and Attendance by Discipline

> Canonical language: English
> Translation: [../spec_traduzido/009-plano-ensino-avaliacoes-frequencia.md](../spec_traduzido/009-plano-ensino-avaliacoes-frequencia.md)
> Status: implemented
> Last reviewed: 2026-07-13

> **Historical notice:** The in-memory persistence statement was superseded by Spec 012. Planning priority and session language was subsequently refined by Specs 014, 017, and 018.

## 1. Goal

Organize each discipline into overview, assessments, attendance, course plan, and recommendations, including import of a course-plan PDF with human review before structured data is persisted.

## 2. Scope

- preview and confirm data explicitly present in a course plan;
- store confirmed structured data, never the raw PDF;
- distinguish `planned`, `completed`, and `cancelled` assessments;
- permit a future assessment without a grade and later completion with a grade;
- record absences by occurrence and by cumulative adjustment;
- use confirmed future assessments as a deterministic weekly-planning priority factor;
- preserve existing manual entry, SIGAA, simulation, and recommendation flows.

OCR is only an optional fallback for a document without usable text. Missing OCR support must produce a friendly error.

## 3. Academic unit

The product uses **class-hour** (*hora-aula*) for workload and absence because the existing model contains `total_class_hours` and `missed_class_hours`. `workload_hours` is interpreted as class-hours.

Do not convert class-hours to clock hours, meetings, or credits. A 30-class-hour discipline allows exactly `30 × 0.25 = 7.5` class-hours of absence. Preserve decimal values.

Show weekly workload only when `term_weeks` is explicitly supplied: `workload_hours / term_weeks`.

## 4. Course plan

`POST /api/disciplines/{id}/course-plan/preview` accepts a PDF, validates size/signature, extracts its local text layer, and returns a TTL-bound preview.

Possible fields are code, name, term, workload, goals, contents, schedule, explicit assessments, and bibliography. Missing fields remain null or empty. An assessment without sufficient date or weight receives `requires_review`.

`POST /api/disciplines/{id}/course-plan/confirm` revalidates the edited preview and persists structured data only. `GET` retrieves and `DELETE` removes structured data. Temporary files are removed in `finally`.

## 5. Assessments

Each assessment has name, date, optional weight, optional grade, topics, notes, origin (`manual` or `course_plan`), and status.

- `planned`: grade must be empty;
- `completed`: grade is required;
- `cancelled`: excluded from simulation;
- only graded assessments contribute to current contribution;
- a missing weight means information is incomplete;
- a total other than 100% produces a warning.

Endpoints support list, create, update, complete, and delete.

## 6. Attendance

An occurrence has date, a positive class-hour quantity, and optional notes. Identical date + quantity pairs cannot repeat. A manual cumulative adjustment is an explicit alternative to occurrences.

The summary uses confirmed workload and the absence sum: limit = workload × 25%; attendance = `1 - absences / workload`; balance = limit - absences, without silent rounding. Above 15% requires attention; above 25% is high risk. Without workload, status is unknown.

## 7. Planning and AI

Legacy effective priority equaled user priority plus a deterministic bonus, capped at 5:

- confirmed assessment within 7 days: +2;
- within 8–14 days: +1;
- otherwise: +0.

Cancelled, completed, ambiguous, or undated assessments do not influence that legacy rule. It does not remove another discipline's minimum session when capacity is sufficient. Specs 014, 017, and 018 replace user-entered priority and rigid-session UX with backend priority, estimated study demand, capacity analysis, and confirmed planned blocks.

An LLM never changes planned blocks. It may only explain confirmed data. Without a key or valid response, planning and recommendations use deterministic fallback.

## 8. Privacy and persistence

The original slice used in-memory storage; Spec 012 replaced it with SQLAlchemy persistence. Still do not persist a raw PDF, full extracted text, full prompt, or full LLM response. Logs contain IDs, counts, mode, and latency only.

## 9. Frontend behavior

The discipline page uses Overview, Assessments, Attendance, Course Plan, Contents, and Recommendations surfaces. Forms open on demand. Temporary and confirmed data have distinct states.

## 10. Tests and acceptance criteria

Cover explicit extraction, documents without assessments/text, review, temporary cleanup, assessment lifecycle, incomplete weights, the exact 30-class-hour limit, absence CRUD/duplication, unknown unit, deterministic deadline influence, fallback, and API contracts. Validate relevant Docker/browser flows without personal data.
