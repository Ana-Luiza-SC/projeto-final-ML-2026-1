# Spec 011 — Hierarchical Content and Assisted Extraction

> Canonical language: English
> Translation: [../spec_traduzido/011-conteudos-hierarquicos-extracao-assistida.md](../spec_traduzido/011-conteudos-hierarquicos-extracao-assistida.md)
> Status: implemented
> Last reviewed: 2026-07-13

> **Historical notice:** The in-memory and no-calendar limitations were superseded by Specs 012 and 013. The hierarchy and human-confirmation rules remain authoritative.

## Problem

The project had a minimal content tree, CRUD, assessment associations, and agent/planning use without one cohesive specification. It also needed a safe flow to turn confirmed course-plan content into an editable proposal; automatic persistence would mix model interpretation with student-confirmed data.

## Flow

1. The learner confirms structured course-plan data.
2. `POST /api/disciplines/{discipline_id}/contents/extract-preview` uses only that confirmed data.
3. The agent proposes a hierarchy. Validation failure invokes a local fallback that proposes root nodes without inventing relations.
4. The frontend presents title, description, parent, evidence, confidence, and warnings for edit/removal.
5. `POST /api/disciplines/{discipline_id}/contents/confirm-preview` revalidates the complete proposal.
6. Only human confirmation persists nodes with initial state `not_started`.

Manual entry, assessment associations, recommendations, and planning remain available independently.

## Domain model and API contracts

`ContentNode` belongs to one discipline, may reference another node in the same discipline, and has title, description, difficulty, and state. Maximum depth is five and maximum size is 100 nodes per discipline.

A preview has `preview_id`, expiry, `draft_nodes`, `warnings`, `source`, `model`, `used_fallback`, and `latency_ms`. Each draft has temporary self/parent IDs, title, optional description, short literal course-plan evidence, confidence from 0 to 1, and warnings. Confirmation sends the `preview_id` and edited list; temporary IDs exist only for preview.

Assessment content selection preserves originally selected nodes and resolves effective descendants with `association_origin=direct|inherited` and `selected_ancestor_id`. Overlaps are deduplicated.

## Guardrails

- no extraction without a confirmed plan and no persistence during preview;
- send only the requested discipline's data;
- evidence must match confirmed structured course-plan text;
- reject HTML, empty titles, external references, cycles, missing parents, and excess depth/size;
- inferred relations do not become persisted prerequisites;
- the model does not define difficulty, state, dates, or weights;
- logs contain only IDs, counts, provider/model, latency, and fallback category—not descriptions, prompt, or full response.

## Deterministic fallback

Without a key, on timeout/unavailability, or for invalid JSON, create an identified local preview with each confirmed `contents` item as a root. Do not invent subtopics/relations. If no explicit contents exist, return a friendly warning and empty list; manual entry remains available.

## Acceptance criteria and tests

- functional Contents UI; validated CRUD, movement, limits, isolation, and safe delete;
- preview does not alter persisted nodes;
- valid agent output is validated/editable; invalid/unavailable output or unsupported evidence invokes identified fallback;
- confirmation reapplies cycle/depth/size/sanitization/ownership checks;
- direct/inherited associations remain auditable;
- agent/planning use only the requested discipline, and general content is not represented as confirmed exam content;
- targeted API tests cover plan absence, fallback/LLM outcomes, preview non-persistence, edit/confirm/expiry, evidence, cycles, missing parents, depth/size, and log privacy.

## Temporal integration

Use `America/Sao_Paulo`. A preparation block must have `scheduled_date < assessment_date`. For content linked to several assessments, use the nearest future deadline. Deterministic ordering considers deadline, association presence, effective weight, state, difficulty, performance, priority, and stable IDs. Content without pre-deadline capacity remains pending with a warning. An LLM cannot change day, date, minutes, or deadline.

Historical validation counts in the Portuguese source are preserved as historical evidence, not rerun results: 62 targeted tests; 197 passed and 1 skipped in the then-current backend suite; frontend/Docker build and HTTP/Compose smoke reported successful.
