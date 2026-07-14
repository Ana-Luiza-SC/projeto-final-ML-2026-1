# Spec 010 — SIGAA Enrichment and Readable Schedules

> Canonical language: English
> Translation: [../spec_traduzido/010-enriquecimento-sigaa-horarios-legiveis.md](../spec_traduzido/010-enriquecimento-sigaa-horarios-legiveis.md)
> Status: implemented
> Last reviewed: 2026-07-13

## Problem and root cause

The public SIGAA search originally found the component row but did not enrich it from its detail page. The confirmed cause in `sigaa_components.py` was that `_extract_component_values_from_row` selected the first non-empty row link and `parse_component_results` passed listing HTML to `parse_sigaa_component_details`; no detail request occurred. The cache stored this empty result without version, TTL, or enrichment marker.

For enrollment receipt import, `extract_candidates_from_table` recognized only the main table and discarded the weekly schedule table. The contract retained only `schedule_code`, displayed as the primary schedule.

## Flow

1. A pure listing parser extracts code, name, type, unit, available workload, and the semantically selected detail URL.
2. Infrastructure reuses the same `requests.Session`, resolves relative URLs, sends `Referer`, applies a timeout, and follows redirects only within public SIGAA paths.
3. A pure detail parser recognizes syllabus/description, program, and theoretical, practical, and total workload.
4. Detail failure preserves basic fields and adds a manual-review warning.
5. A versioned TTL cache ignores legacy/incomplete entries.
6. Enrollment import interprets the weekly table before compact-code fallback. Explicit slots prevail; consecutive slots are grouped and conflicts produce warnings.
7. The frontend presents `schedule_display`; the raw code remains secondary and editable for audit.

## Data contracts

`SigaaComponent` retains existing fields and adds `details_processed` and optional theoretical/practical workloads. The response remains backward compatible.

Discipline and preview items retain `schedule_code` and add:

- `schedule_slots`: `{day, start_time, end_time, source}` entries;
- `schedule_display`: Portuguese user-facing text;
- `schedule_source`: `receipt_table`, `sigaa_tooltip`, `decoded_code`, or `unresolved`.

Older data without these fields remains valid. Confirmation accepts manual correction of the structured representation.

## Guardrails and fallback

- allow only public SIGAA host/paths; reject login, authentication, and private redirects;
- no credentials, bulk scraping, or invented syllabus/schedule;
- timeout/detail error never removes code/name;
- explicit table data prevails over code; report conflicts;
- preserve unknown codes with `schedule_source=unresolved` and a warning;
- never store/log raw PDF, full text, or personal data;
- preserve manual entry/correction.

## Acceptance criteria

- request the actual public detail in the same session and render a real syllabus when present;
- choose the link by name/detail-action semantics, not position;
- preserve basic fields on detail failure without invention;
- do not let old/incomplete cache hide a new lookup;
- convert weekly tables and known codes to explicit readable Portuguese schedules;
- do not use raw code as primary presentation;
- accept legacy contracts and pass validations.

## Test strategy and impact

Sanitized fixtures cover listing, detail, `Ementa/Descrição`, missing syllabus, moderate HTML changes, and login redirect. Unit tests avoid the network and check pure parsing, session/headers, cache, fallback, and no invention. Schedule fixtures cover explicit slots, grouping, multiple days/shifts, unknown/missing codes, and conflicts. Backend parser/infrastructure, frontend presentation, cache envelope, and audit display are affected.
