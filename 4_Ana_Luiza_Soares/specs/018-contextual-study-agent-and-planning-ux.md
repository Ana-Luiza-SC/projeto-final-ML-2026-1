# Spec 018 - Contextual Study Agent and Planning UX

## Status and purpose

This specification defines one coherent planning, calendar, study-demand, and contextual-assistant experience for EstudaUnB. It supersedes the frontend information architecture introduced incrementally by Specs 007, 013, and 017 while preserving their compatible backend data and backward-compatibility requirements.

The product must help the learner decide what deserves attention, reserve time when useful, choose an evidence-based study method when starting work, and review the outcome. These are connected steps, but they are not the same domain object.

## Current-state diagnosis

The current implementation has two competing planning surfaces:

- `/study-plan` uses the legacy Spec 007 request with manual numeric priorities, independently entered weekly hours, a maximum session duration, weekday checkboxes, and generated-session language.
- `/calendar` contains the Spec 017 availability windows, derived total, preview, and confirmation flow in addition to calendar controls.

The implementation also has these behavioral defects:

- the calendar cursor starts at the first day of the month and is reused as the planning week, so the generated preview may target a past week;
- past or completed assessments can be selected as the governing deadline;
- rejecting slots for one expired priority advances a shared slot pointer and can starve every later discipline;
- allocation has a hidden 90-minute cap and at most one block per discipline;
- unallocated items do not expose requested, usable, blocked, or deadline-constrained minutes;
- Week view is seven chronological cards, not a temporal grid;
- missing syllabus is mapped to low complexity with 25 percent confidence;
- the discipline assistant returns prose and string suggestions rather than validated contextual actions;
- the runtime study-strategy service duplicates method metadata instead of loading the canonical JSON catalog;
- live SIGAA turma search omits the dynamically named search submit control, so fixture tests pass while public enrichment can fail before a turma id is discovered.

## Product principles

1. The backend owns academic calculations, priority scores, evidence coverage, scheduling constraints, and action validation.
2. The learner controls inclusion, confirmation, method override, and every mutation.
3. Missing evidence produces uncertainty, not a favorable conclusion.
4. Priority, estimated study demand, learner-specific difficulty, workload, and method fit remain separate.
5. A planned block reserves time. A study activity records actual execution.
6. An LLM may explain or phrase validated results. It may not invent evidence, write directly to storage, or override deterministic values.
7. Every core flow works without an LLM.
8. Public SIGAA enrichment remains best-effort, auditable, cached, and limited to public pages.

## Relationship to existing specifications

### Spec 007

Spec 007 is legacy. Its `available_hours_per_week`, manual `priorities`, `max_session_minutes`, and generated-session UI are no longer part of the canonical planning experience. The legacy API may remain temporarily for compatibility, but the frontend must stop calling it.

### Spec 013

Spec 013 remains authoritative for authenticated academic-event persistence, assessment synchronization, course-plan event preview, and safe deployment. Its separate weekly agenda below the month calendar is superseded by the Month/Week switch.

### Spec 014

Spec 014 remains authoritative for deterministic priority ranking and auditable evidence. Priorities are unscheduled by default. Spec 018 permits the learner to explicitly transform selected priorities into an unconfirmed block preview. This does not make automatic scheduling mandatory.

### Spec 015

Spec 015 remains authoritative for the method catalog and learner-started study activities. A planned block may provide time and task context to method recommendation, but confirming a block does not start or complete an activity.

The canonical method source is:

```text
backend/app/knowledge/study_methods/study_methods.json
```

The PDF is the human-readable audit source and must not be embedded into the same vector collection as the JSON. The README remains the ingestion and versioning guide.

### Spec 016

Spec 016 remains authoritative for post-activity feedback and cautious method adaptation. Adaptation can influence method fit only. It must not change priority or course-level estimated demand.

### Spec 017

Spec 017 remains authoritative for availability windows, planned-block preview and confirmation, recurrence, and calendar persistence. Spec 018 moves the planning controls to `/study-plan`, strengthens capacity diagnostics, and requires a temporal Week view.

## Canonical information architecture

### Planning

Route: `/study-plan`

Responsibilities:

- manage availability windows for the selected week;
- show derived daily and weekly totals;
- show deterministic ranked priorities;
- include or exclude priorities without editing their score;
- generate an optional planned-block preview;
- explain capacity and deadline shortages;
- confirm blocks;
- navigate to the confirmed week in Calendar;
- start an on-demand study activity from a priority or confirmed block when Spec 015 activity lifecycle is available.

### Calendar

Route: `/calendar`

Responsibilities:

- show confirmed events and planned blocks in Month and Week views;
- inspect event details and conflicts;
- create manual one-time or recurring events;
- edit or move supported events and planned blocks;
- navigate to `/study-plan` through a compact `Adjust weekly plan` action.

The complete planning form must not appear on this route.

### Contextual Assistant

The assistant is available on authenticated routes through a collapsible drawer owned by `AppShell`. It receives validated structured context for the current route and returns prose plus typed suggestions.

## Domain boundaries

### Study priority

An auditable recommendation about what deserves attention. It has a backend-owned score, evidence, missing evidence, deadline status, and estimated demand. It has no calendar time until the learner requests and confirms a plan.

### Planned study block

An optional reserved interval generated within supplied availability. It stores priority snapshots and scheduling evidence. It does not define a cognitive method and does not prove that study occurred.

### Study method recommendation

A ranked choice of up to three reviewed catalog methods for a task and available duration. Method fit is separate from priority and demand.

### Study activity

The actual learner-started execution. It records selected method, timer configuration, actual duration, state, and later feedback.

### Estimated study demand

A course- or task-level estimate of the amount and breadth of work suggested by available evidence. It is not a priority score, workload-hour value, or learner diagnosis.

### Learner-specific difficulty

A cautious estimate based only on stored learner evidence such as content status, prior performance, or feedback. It remains distinct from course-level demand.

## Current-state route map

```text
/
|-- /login
|-- /register
`-- authenticated
    |-- /app
    |-- /disciplines
    |   `-- /disciplines/:id
    |       |-- catalog and complexity
    |       |-- SIGAA panel
    |       `-- discipline-local assistant chat
    |-- /study-plan
    |   `-- legacy generated-session form
    |-- /calendar
    |   |-- Month cards
    |   |-- Week day cards
    |   |-- recurring manual event form
    |   |-- complete weekly planning form
    |   `-- course-plan event extraction
    `-- /matricula-import
```

## Proposed route map

```text
/
|-- /login
|-- /register
`-- authenticated AppShell + collapsible ContextualAssistantDrawer
    |-- /app
    |-- /disciplines
    |   `-- /disciplines/:id
    |       |-- academic records and contents
    |       |-- SIGAA catalog synchronization
    |       `-- estimated study demand and evidence
    |-- /study-plan
    |   |-- weekly availability
    |   |-- ranked priorities
    |   |-- optional block preview
    |   `-- confirmation and capacity explanation
    |-- /calendar
    |   |-- Month grid
    |   |-- temporal Week grid
    |   |-- event details
    |   |-- manual/recurring event editor
    |   `-- course-plan event extraction
    `-- /matricula-import
```

The existing discipline assistant endpoint may remain during migration, but its visible page-local chat is replaced by the shared drawer once contextual parity is reached.

## Proposed component hierarchy

```text
App
`-- AppShell
    |-- Topbar
    |-- MainNavigation
    |-- RouteContent
    |   |-- StudyPlanPage
    |   |   |-- WeekSelector
    |   |   |-- AvailabilityEditor
    |   |   |   |-- DayAvailabilityGroup
    |   |   |   `-- AvailabilityWindowRow
    |   |   |-- AvailabilitySummary
    |   |   |-- PriorityList
    |   |   |   `-- PriorityItem
    |   |   |-- PlanPreview
    |   |   |   |-- PlannedBlockList
    |   |   |   `-- CapacityShortageList
    |   |   `-- PlanConfirmationBar
    |   |-- CalendarPage
    |   |   |-- CalendarToolbar
    |   |   |-- MonthCalendarGrid
    |   |   |-- WeekTimeGrid
    |   |   |-- DayEventDetails
    |   |   |-- ManualEventEditor
    |   |   `-- CoursePlanEventPreview
    |   `-- DisciplineDetailPage
    |       |-- CatalogOverview
    |       |-- StudyDemandSummary
    |       `-- SigaaComponentPanel
    `-- ContextualAssistantDrawer
        |-- AssistantHeader
        |-- ContextSummary
        |-- QuickIntentList
        |-- AssistantConversation
        |   `-- SuggestedActionButton
        `-- ActionConfirmationDialog
```

## Planning page redesign

### Weekly availability

The page defaults to the current Monday-to-Sunday week in `America/Sao_Paulo`. Changing the week is explicit and never derived from a month-calendar cursor.

Availability is a list of windows grouped by weekday. The learner can add, edit, disable, and remove windows. The UI displays daily totals and a derived weekly total.

Validation:

- end must be later than start;
- duplicates are ignored or rejected deterministically;
- overlaps are rejected with the conflicting window identified;
- disabled windows are excluded;
- at least one 30-minute usable window is required for block generation;
- local display and API values retain `America/Sao_Paulo` semantics.

Availability must be user-isolated. The backend is the source of truth for normalized totals; the frontend may calculate an immediate preview but must reconcile it with the API response.

### Automatically ranked priorities

Every priority item displays:

- discipline code and name;
- relevant assessment or objective;
- deadline and deadline state;
- assessment weight when known;
- mastery gap when known;
- priority score and band;
- concise deterministic explanation;
- evidence disclosure;
- missing-data warning;
- estimated study demand in minutes or an explicit unknown state;
- include/exclude toggle.

The learner cannot edit the score. Include/exclude changes allocation scope only.

Past, completed, or cancelled assessments must not govern an active priority. If no future dated assessment exists, the priority may still exist from unfinished content or academic risk, but it must not invent a deadline.

### Demand estimation

The first deterministic planner may use a conservative configurable baseline:

- assessment with linked unfinished content: 90 minutes;
- unfinished content without assessment linkage: 60 minutes;
- discipline-only evidence: 30 minutes and low confidence;
- no meaningful evidence: demand unknown, with a request for more data.

These are scheduling heuristics, not claims about required learning time. The algorithm version and breakdown must be returned. A later implementation may refine demand from content count, workload, prior outcomes, and assessment structure.

### Plan generation

Generation produces an unconfirmed preview. It may allocate multiple blocks to one priority when demand exceeds one usable interval. It may partially allocate demand and must return the remainder.

Rules:

- schedule only within normalized availability for the requested week;
- exclude past days when planning the current week, unless the learner explicitly requests a historical preview for audit;
- do not place preparation on or after the related assessment date;
- subtract confirmed opaque events, including existing confirmed study blocks;
- preserve at least the configured minimum useful block, default 30 minutes;
- do not impose a user-facing maximum session duration;
- a window may be used in full or split between priorities;
- use stable priority and chronological tie-breakers;
- re-check conflicts at confirmation;
- preserve manually edited confirmed blocks;
- make confirmation idempotent.

### Capacity explanation

Each priority returns a capacity record, including allocated priorities when partially fulfilled:

```json
{
  "discipline_id": "uuid",
  "priority_item_id": "stable-id",
  "requested_minutes": 90,
  "allocated_minutes": 30,
  "remaining_minutes": 60,
  "available_minutes_before_deadline": 120,
  "blocked_minutes": 90,
  "minimum_useful_block_minutes": 30,
  "deadline_at": "2026-07-14T00:00:00-03:00",
  "reason_code": "insufficient_conflict_free_capacity",
  "reason": "Qualidade de Software requires approximately 90 minutes before 14 July, but only 30 conflict-free minutes remain.",
  "blocking_events": [
    { "event_id": "uuid", "title": "Class", "blocked_minutes": 90 }
  ]
}
```

Allowed reason codes:

- `fully_allocated`;
- `partially_allocated`;
- `insufficient_conflict_free_capacity`;
- `no_window_before_deadline`;
- `fragments_below_minimum`;
- `deadline_expired`;
- `demand_unknown`;
- `excluded_by_user`;
- `conflict_introduced_after_preview`.

The backend supplies factual values and the canonical explanation. The LLM may restate it without changing numbers or reason code.

## Planning page wireframe

```text
+------------------------------------------------------------------+
| Planning                         Week: 13-19 Jul 2026  [change]   |
+------------------------------------------------------------------+
| Weekly availability                                               |
| Mon  [18:00]-[20:00] [edit] [remove]  Total 2h                   |
| Wed  [14:00]-[16:00] [edit] [remove]  Total 2h                   |
| [+ Add window]                          Weekly total 4h            |
+------------------------------------------------------------------+
| Ranked priorities                                                 |
| [on] Quality of Software   HIGH 82   Exam 14 Jul, weight 20%      |
|      Approx. demand 90 min | Why? evidence + missing evidence     |
| [on] Algorithms            MED 56    unfinished Unit 3            |
|      Approx. demand 60 min | Why?                                 |
+------------------------------------------------------------------+
| [Generate preview]                                                |
+------------------------------------------------------------------+
| Preview                                                           |
| Mon 18:00-19:30  Quality of Software                              |
| Wed 14:00-15:00  Algorithms                                       |
| Shortage: 30 min remain for Algorithms; 90 min blocked by Class   |
| [Discard] [Confirm blocks]                                        |
+------------------------------------------------------------------+
```

## Calendar redesign

### Month view

- conventional seven-column month grid;
- compact event indicators by source/type;
- selected day opens an event-details region or dialog;
- assessment, manual event, course-plan event, and study block have distinct labels and non-color cues;
- no weekly agenda is rendered below the grid;
- confirmed planned blocks appear once through the academic-event collection.

### Week view

Week view is a temporal grid:

- vertical time axis;
- seven day columns on desktop;
- separate all-day row;
- timed events positioned by start and end;
- overlapping events use side-by-side lanes or a clear stacked conflict treatment;
- configurable visible range based on events, with a practical default such as 07:00-22:00;
- current-time indicator only when the displayed week contains the current local time;
- keyboard-accessible event selection;
- event duration has a minimum visual height without changing factual time;
- study blocks, assessments, and manual events differ by icon, label, and style, not color alone.

### Responsive fallback

Below the desktop breakpoint, Week view becomes a horizontally scrollable temporal grid with a sticky time axis, or a single-day temporal view with day tabs. It must retain time position and duration; it must not degrade into undifferentiated cards.

### Calendar wireframes

Month:

```text
+------------------------------------------------------------------+
| Calendar                 [Month] [Week]       [Adjust weekly plan]|
| [previous] July 2026 [next]                  filters...           |
+------------------------------------------------------------------+
| Mon      Tue      Wed      Thu      Fri      Sat      Sun         |
|          1        2        3        4        5        6           |
| 13       14       15       16       17       18       19          |
| Study    Exam     Study                                             |
+------------------------------------------------------------------+
| Selected day: 14 July                                             |
| 09:00 Exam 1                                   [inspect]           |
+------------------------------------------------------------------+
```

Week:

```text
            Mon 13   Tue 14   Wed 15   Thu 16   Fri 17   Sat   Sun
All day     -----    Exam     -----    -----    -----    ---   ---
07:00  -------------------------------------------------------------
08:00            | Class |                                            
09:00            |       |                                            
10:00  -------------------------------------------------------------
18:00  | Study |            | Study |                                 
19:00  |       |            |       |                                 
20:00  -------------------------------------------------------------
```

## Estimated study demand redesign

Replace the current `estimated_level: low|medium|high` complexity contract with an evidence-aware response:

```json
{
  "demand_level": "insufficient_evidence",
  "confidence": 0.25,
  "evidence_coverage": 0.25,
  "evidence_used": [
    { "type": "workload", "summary": "60-hour course" }
  ],
  "missing_evidence": ["syllabus", "prerequisites", "content hierarchy", "assessment structure", "learner history"],
  "factors": {
    "conceptual_breadth": "unknown",
    "prerequisite_depth": "unknown",
    "mathematical_or_algorithmic_density": "unknown",
    "project_workload": "unknown",
    "assessment_concentration": "unknown"
  },
  "learner_specific_difficulty": {
    "level": "insufficient_evidence",
    "confidence": 0.0,
    "evidence_used": [],
    "missing_evidence": ["learner history"]
  },
  "mode": "deterministic_fallback",
  "model_or_rule_version": "study-demand-v2",
  "warnings": []
}
```

Allowed demand levels:

- `insufficient_evidence`;
- `low`;
- `moderate`;
- `high`.

Rules:

- no syllabus normally means `insufficient_evidence` unless at least two other meaningful evidence categories support a conclusion;
- confidence is deterministic evidence coverage, not LLM self-confidence;
- the LLM may explain validated factors but may not set level, confidence, or evidence lists;
- workload hours alone do not establish cognitive demand;
- learner history affects learner-specific difficulty, not the course-level demand category;
- cached v1 complexity records must be invalidated by the rule version change;
- UI label becomes `Estimated study demand` / `Demanda estimada de estudo` with a concise `Why?` disclosure.

## SIGAA syllabus synchronization

The synchronization flow must be completed and verified against a real public component before acceptance.

Requirements:

- use one `requests.Session` across public initialization, component search, turma search, and detail POST;
- dynamically parse each current ViewState;
- dynamically discover the turma-search submit control by semantic value or label such as `Buscar`;
- never hardcode `j_id4` or `j_id_jsp_*` names;
- discover the selected turma id from the matching result row;
- submit detail fields defined by the confirmed public flow;
- use configured public search scope values and report when no matching turma exists in that scope;
- persist successful syllabus into `catalog_components.syllabus` and the attached discipline payload;
- make catalog refresh bypass or invalidate `detail_unavailable` cache entries when the user explicitly refreshes;
- retain successful detail cache with parser version, source URL, fetched time, and status;
- do not replace a non-empty persisted syllabus with an empty enrichment result;
- expose a friendly source-unavailable state without raw exception data;
- keep allowlist, timeout, response-size limit, and public-only restrictions.

Verification evidence must record the component code, non-sensitive source URL, detail status, syllabus presence/length, and persistence/reload result. It must not copy an excessive amount of source text into logs or tests.

## Contextual assistant contract

### Drawer behavior

- available from authenticated pages through `AppShell`;
- fully collapsible and not a permanently reserved column;
- remembers open/closed state in local storage;
- toggle is keyboard reachable and exposes `aria-expanded` and `aria-controls`;
- focus moves into the drawer when explicitly opened and returns to the toggle when closed;
- Escape closes it unless a confirmation dialog is active;
- responsive overlay on narrow screens and non-obscuring side drawer on wide screens;
- critical page actions remain reachable while open;
- conversation history is bounded and does not contain raw document text.

### Safe structured context

The frontend sends only route and explicit selection hints. The backend reconstructs all authoritative context for the authenticated user.

```json
{
  "route": "/study-plan",
  "selected_discipline_id": "uuid-or-null",
  "selected_week_start": "2026-07-13",
  "selected_event_id": null,
  "selected_priority_id": "stable-id-or-null",
  "intent": "explain_capacity_shortage",
  "message": "Why was this not scheduled?"
}
```

Backend-reconstructed context may include:

- selected discipline;
- upcoming assessments;
- confirmed calendar events in a bounded range;
- current weekly availability;
- computed priority run and evidence;
- unconfirmed or confirmed planned blocks;
- active study-method catalog version;
- aggregate method statistics when available.

The assistant must not receive arbitrary frontend HTML, raw uploaded PDF text, credentials, auth headers, private notes, or unrelated user data.

### Response contract

```json
{
  "message": "Only 30 conflict-free minutes remain before the assessment.",
  "execution_mode": "deterministic_fallback",
  "evidence": [
    { "type": "availability", "summary": "120 minutes supplied" },
    { "type": "calendar_conflict", "source_id": "uuid", "summary": "90 minutes blocked" }
  ],
  "suggested_actions": [
    {
      "action_id": "server-signed-or-stored-id",
      "type": "create_study_block",
      "label": "Add Wednesday 18:00-18:30",
      "payload": {
        "discipline_id": "uuid",
        "start_at": "2026-07-15T18:00:00-03:00",
        "end_at": "2026-07-15T18:30:00-03:00"
      },
      "requires_confirmation": true
    }
  ],
  "warnings": [],
  "catalog_version": "1.0.0"
}
```

Allowed action types are an explicit enum:

- `navigate_to_discipline`;
- `navigate_to_planning`;
- `navigate_to_calendar_date`;
- `explain_priority`;
- `explain_capacity_shortage`;
- `recommend_study_methods`;
- `propose_study_block`;
- `create_study_block`;
- `modify_unconfirmed_plan`.

Navigation and explanation actions may execute immediately because they do not persist academic data. Every mutation requires confirmation.

### Action lifecycle

1. Assistant returns a typed suggestion with an opaque `action_id` and preview payload.
2. Frontend renders a button and opens a confirmation dialog for mutations.
3. On confirmation, frontend posts the `action_id` plus any explicitly editable safe fields.
4. Backend reloads the authenticated context, validates ownership, allowed type, deadline, availability, conflicts, method id, and expiry.
5. Backend executes the domain service, not an LLM callback.
6. Response returns the persisted object or a friendly conflict requiring a new proposal.

Rejecting a suggestion performs no mutation and may be recorded only as a non-sensitive product observation.

The LLM must never receive repository write tools, database handles, or a route that directly persists its free-form output.

### Supported assistant intents

1. Explain a deterministic priority and its evidence.
2. Recommend what to study in a specified available window.
3. Recommend up to three reviewed methods from the canonical catalog.
4. Explain method fit and uncertainty.
5. Propose a calendar block.
6. Propose changes to an unconfirmed plan.
7. Explain capacity shortage using returned numbers.
8. Open the relevant discipline, planning week, or calendar date.

### Deterministic fallback

Without an LLM, the assistant uses:

- priority explanation templates;
- capacity reason templates;
- deterministic catalog method ranking;
- validated navigation actions;
- the same action confirmation lifecycle.

Fallback is a supported execution mode, not an error. It must not expose provider exception names or bodies.

## Method recommendation behavior

Runtime method metadata must be loaded from `study_methods.json`, not maintained as a divergent hardcoded catalog.

The deterministic recommender may use:

- available duration;
- task type;
- content status or prior mastery;
- previous comparable method outcomes when Spec 016 has sufficient data;
- assessment proximity;
- catalog `recommended_for`, category, protocol, limitations, and evidence level.

It returns at most three methods and always exposes catalog version, fit evidence, limitations, and missing context.

Duration examples such as 25-40, 60-90, or two hours are product heuristics, not universal truths. Pomodoro is a configurable time-management format and must be paired with a cognitive strategy or explicit task.

## Assistant drawer interaction model

```text
Closed:  [Assistant button]

Open:
+------------------------------------+
| Study assistant              [x]   |
| Context: Planning, 13-19 Jul       |
| [Explain top priority]             |
| [Use my next free window]          |
| [Why was this not scheduled?]      |
|------------------------------------|
| Assistant response                 |
| Evidence [expand]                  |
| [Add Wed 18:00-19:00]              |
|------------------------------------|
| Ask about this page...      [Send] |
+------------------------------------+

Mutation confirmation:
+------------------------------------+
| Add planned block?                 |
| Quality of Software                |
| Wed 18:00-19:00                    |
| [Reject] [Confirm]                 |
+------------------------------------+
```

## Primary user journey

1. Learner opens `/study-plan`; the current local week is selected.
2. Learner adds availability windows and sees daily and weekly totals derived immediately and confirmed by the backend.
3. Backend ranks priorities deterministically; learner opens evidence and includes or excludes items.
4. Learner generates a preview and sees chronological blocks, partial allocations, and concrete capacity explanations.
5. Learner confirms; backend revalidates conflicts and persists idempotent `study_plan` calendar events.
6. Learner opens `/calendar`; the confirmed block appears once in Month and at its time position in Week.
7. At study time, learner starts an activity from the block, priority, or assistant suggestion.
8. Product recommends up to three catalog methods using task and duration context; learner accepts or overrides.
9. Learner configures a timer format independently from the cognitive method and studies.
10. Learner completes the activity and submits Spec 016 feedback; later recommendations may use it only after sufficient comparable evidence.

## Page and drawer states

### Loading

- availability and priorities use stable skeleton regions;
- existing form input is not cleared during preview generation;
- calendar retains the previous range while refreshing and labels it as updating;
- assistant announces response loading through `aria-live` without trapping focus.

### Empty

- no disciplines: link to discipline registration/import;
- no availability: explain that windows are required for block preview;
- no active priorities: show whether data is absent, completed, expired, or excluded;
- no calendar events: preserve grid and offer manual event creation;
- no method context: return general low-confidence options with missing-context warning.

### Error

- use product-language errors and retry actions;
- retain unsaved availability locally;
- a failed preview does not persist blocks;
- a failed assistant action does not mutate data;
- never show stack traces, provider bodies, raw exception classes, or secrets.

### Insufficient data

- priority shows missing evidence without inventing score factors;
- demand uses `insufficient_evidence` rather than `low`;
- method adaptation returns `insufficient_data` per Spec 016;
- missing syllabus offers SIGAA refresh or manual entry, while preserving existing data.

### Fallback

- deterministic priority, demand, capacity, and method rules remain available;
- assistant labels deterministic mode without presenting a system failure;
- unsupported assistant intent returns safe navigation and available deterministic actions.

### Partial

- partial allocation shows allocated and remaining minutes;
- partial SIGAA enrichment preserves code/name/workload and identifies syllabus absence;
- confirmation may persist conflict-free blocks and list skipped blocks only after explicit user confirmation of that behavior.

## Mobile and responsive behavior

- navigation and assistant drawer do not overlap each other;
- drawer is a full-height overlay below the topbar on narrow screens and closes fully;
- availability controls stack by day with time inputs remaining at least 44 CSS pixels high;
- priority cards keep score, band, include toggle, and deadline visible without horizontal scrolling;
- plan preview is chronological rather than squeezed into a seven-column layout;
- Month grid may horizontally scroll at a defined minimum width, while selected-day details remain below;
- Week grid uses sticky time axis plus horizontal day scrolling or day tabs while preserving temporal position;
- dialogs fit the viewport and remain scrollable with visible confirmation actions.

## Accessibility

- all icon buttons have accessible names and tooltips where meaning is not obvious;
- segmented Month/Week control exposes selected state;
- drawer uses dialog/complementary semantics appropriate to its mode;
- focus order follows visual order;
- opening/closing drawer and confirmation dialogs restores focus correctly;
- Escape behavior is predictable;
- event types and priority bands are not communicated by color alone;
- calendar events are reachable by keyboard and announce title, date, start, end, type, and status;
- temporal grid retains a logical DOM order by day and time;
- form errors are associated with fields and announced;
- derived totals use an `aria-live=polite` summary;
- motion respects `prefers-reduced-motion`.

## Items explicitly removed from the current UI

- manual numeric priority selectors;
- independent weekly-hours input;
- maximum session duration input;
- basic weekday checkboxes that can exist without time windows;
- generated-session terminology for planned blocks;
- complete planning form in Calendar;
- `Sem capacidade: <discipline>` without quantitative explanation;
- seven undifferentiated Week cards;
- `low complexity` result derived only from missing evidence;
- permanently embedded discipline-local chat once drawer parity is complete;
- string-only suggested actions that the learner must interpret and reproduce manually.

## API changes

### Weekly preview

Extend `POST /api/study-plans/weekly-preview` response with:

- stable priority item ids;
- estimated demand and breakdown;
- capacity analysis per priority;
- blocking event summaries;
- reason codes;
- partial allocation values;
- requested-week/current-week metadata.

The endpoint must reject or clearly mark an incorrectly aligned `week_start`. The frontend sends the selected planning week, never the calendar month cursor.

### Contextual assistant

```http
POST /api/assistant/contextual/messages
POST /api/assistant/actions/{action_id}/confirm
```

The message endpoint is read/propose only. The confirmation endpoint dispatches to allowlisted domain services after reconstructing context.

### Study demand

Keep the existing route during migration:

```http
POST /api/disciplines/{discipline_id}/complexity-analysis
```

Return the v2 demand schema and add a deprecation-compatible alias later if useful:

```http
POST /api/disciplines/{discipline_id}/study-demand-analysis
```

### SIGAA refresh

`POST /api/disciplines/{discipline_id}/catalog-refresh` must represent explicit refresh semantics and bypass stale `detail_unavailable` cache. Search may retain normal cache behavior.

## Persistence and authorization

- availability and plan previews are owned by the authenticated user;
- assistant action proposals are short-lived, user-owned, single-use or idempotent, and contain no secrets;
- action confirmation rejects expired, cross-user, altered, or unsupported payloads;
- confirmed blocks remain academic events with `source=study_plan`;
- assistant messages need not be persisted for the MVP; if persisted later, retain only bounded sanitized content and structured ids;
- study-demand v2 uses a new rule version so v1 cache cannot masquerade as current analysis;
- successful SIGAA catalog data is public shared metadata, while discipline attachment remains user-owned;
- no raw PDF is persisted by these flows.

## Observability

Structured events:

- `weekly_planning_view_loaded`;
- `weekly_plan_preview_generated`;
- `weekly_plan_capacity_shortage`;
- `weekly_plan_confirmed`;
- `study_demand_analyzed`;
- `sigaa_turma_search_submitted`;
- `sigaa_syllabus_synchronized`;
- `contextual_assistant_requested`;
- `contextual_action_proposed`;
- `contextual_action_confirmed`;
- `contextual_action_rejected`.

Log ids, route, algorithm/catalog versions, counts, reason codes, status, and latency. Do not log names, matricula, raw PDF text, full prompts, provider responses, private notes, credentials, tokens, or auth headers.

## Test requirements

### Backend

- current-week derivation in `America/Sao_Paulo`;
- explicit selected week independent of calendar cursor;
- expired, completed, and cancelled assessments do not govern active allocation;
- one rejected deadline does not consume slots for later priorities;
- deterministic ranking and stable tie-breakers;
- selected/excluded disciplines;
- demand estimates and unknown demand;
- allocation across multiple blocks;
- partial allocation;
- existing study-block conflict;
- requested, available, blocked, allocated, and remaining minute accounting;
- fragments below minimum;
- confirmation conflict revalidation and idempotency;
- capacity explanations contain no invented values;
- demand with no syllabus returns `insufficient_evidence`;
- demand confidence equals deterministic evidence coverage;
- learner-specific difficulty remains separate;
- v1 demand cache invalidation;
- dynamic SIGAA search submit discovery with changed JSF ids;
- explicit refresh bypasses failed-detail cache;
- successful syllabus persistence and reload;
- empty enrichment cannot erase a non-empty syllabus;
- contextual route/selection validation;
- backend context reconstruction and user isolation;
- allowed action enum validation;
- action expiry, tampering, and cross-user rejection;
- no mutation from message endpoint;
- confirmation required for mutations;
- deterministic assistant fallback;
- method ids and metadata loaded from `study_methods.json`;
- at most three method recommendations;
- Pomodoro pairing rule;
- no raw PDF or private context in logs.

### Frontend

- `/study-plan` has no manual priority, weekly-hours, or maximum-session controls;
- availability totals update from windows;
- overlap error identifies the conflict;
- ranked priorities expose evidence and missing data;
- include/exclude works without changing score;
- preview and confirmation work;
- concrete partial/unallocated explanations render;
- Calendar contains no complete planner;
- `Adjust weekly plan` navigates to `/study-plan`;
- Month has no duplicated weekly agenda;
- Week is a temporal grid with all-day row and positioned events;
- overlapping event treatment;
- confirmed blocks appear in Month and Week once;
- demand insufficient-evidence state;
- assistant drawer open/close persistence;
- keyboard and focus behavior;
- structured action buttons;
- reject performs no mutation;
- confirm calls action confirmation endpoint;
- fallback and safe errors;
- responsive Week view retains temporal semantics.

### Manual scenarios

1. User with no syllabus sees insufficient evidence, not low demand.
2. User refreshes a verified public SIGAA component and sees persisted syllabus after reload.
3. User supplies four hours and multiple priorities; valid future items receive blocks.
4. Capacity before a deadline is insufficient and the exact minute breakdown appears.
5. LLM is unavailable and deterministic planning, method suggestions, and assistant actions remain usable.
6. Assistant proposes a block but does not persist it.
7. User rejects the proposal and no event appears.
8. User confirms the proposal and the backend revalidates it.
9. Refresh preserves the confirmed block.
10. Week view shows the block at its correct local start and end time.

## Acceptance criteria

1. `/study-plan` no longer displays manual priority selectors.
2. `/study-plan` no longer displays maximum session duration.
3. Weekly hours are derived from availability windows.
4. Planning controls are removed from `CalendarPage`.
5. Calendar Month view has no weekly agenda below it.
6. Week view uses a temporal grid.
7. Confirmed blocks appear in both Month and Week.
8. Capacity shortages include requested, available, blocked, allocated, remaining, minimum-block, deadline, and reason values where applicable.
9. Priority ranking is deterministic and visible.
10. The assistant opens as a fully collapsible drawer.
11. The assistant receives contextual structured data reconstructed by the backend.
12. The assistant can propose but cannot directly execute mutations.
13. All mutations require confirmation and backend revalidation.
14. Method recommendations use the versioned canonical JSON knowledge base.
15. Pomodoro is a configurable time format, not a universal learning method.
16. Missing syllabus does not produce a confident low-demand result.
17. Priority, demand, workload, learner difficulty, and method fit remain separate.
18. SIGAA syllabus extraction is verified with a real public component and persists after reload.
19. The product works without an LLM.
20. No raw technical error is exposed.

## Critical review and scoped limitations

- Specs 014 and 017 appear contradictory only if block generation is automatic. This spec resolves the conflict by keeping priorities unscheduled until the learner explicitly requests an optional preview.
- Specs 015 and 017 appear contradictory only if a block is treated as actual study. This spec keeps reservation and execution separate.
- Full study-activity lifecycle and feedback remain governed by Specs 015 and 016 and may not yet exist in runtime code. The assistant can recommend methods before that lifecycle is complete, but must not fabricate completion or adaptation data.
- Drag-and-drop calendar editing is optional for this iteration; a form-based move/edit path is acceptable.
- Editing a single recurrence occurrence may remain limited as documented by Spec 017.
- The contextual assistant should remain narrow: priority explanation, capacity, method selection, block proposals, and navigation. It is not a general-purpose chatbot.
- Live SIGAA availability varies by term and department. Acceptance requires one verifiable component, not a guarantee that every component has a public current turma.

## Implementation increments and commit boundaries

1. Replace legacy planning UI and move planner state out of Calendar.
2. Correct week/deadline allocation and add capacity analysis.
3. Build temporal Month/Week calendar presentation.
4. Introduce study-demand v2 evidence semantics.
5. Complete dynamic SIGAA turma search and explicit refresh behavior.
6. Load and validate the canonical method catalog.
7. Add contextual assistant proposal/action contracts.
8. Add the accessible drawer and confirmation flow.
9. Add focused backend/frontend tests and evidence documentation.

Implementation should remain split by these coherent responsibilities and must not be delivered as one catch-all commit.
