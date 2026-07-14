# Spec 008 — Enrollment Receipt Discipline Import MVP

> Canonical language: English
> Translation: [../spec_traduzido/008-importacao-disciplinas-comprovante-matricula-mvp.md](../spec_traduzido/008-importacao-disciplinas-comprovante-matricula-mvp.md)
> Status: implemented
> Last reviewed: 2026-07-13

## Context, problem, and goal

Allow a learner to upload a SIGAA/UnB enrollment receipt PDF, review recognized disciplines, and explicitly confirm idempotent batch registration. Local extraction normalizes academic fields, optionally validates/enriches through public SIGAA, and returns auditable statuses. Upload alone never creates a discipline; manual entry remains available.

## Canonical flow

```text
PDF upload
→ file validation
→ local extraction
→ code/name identification and normalization
→ optional public SIGAA lookup
→ editable preview
→ explicit confirmation
→ idempotent batch creation
→ created/duplicate/rejected report
```

The parser separates regular disciplines from academic activities such as monitoring/advising. No SIGAA credentials/authenticated pages, raw-PDF persistence, automatic save, LLM document upload, new bulk scraper, professor/rate inference, or silent overwrite.

## Preview API

```http
POST /api/import/matricula-pdf/preview
Content-Type: multipart/form-data
```

Require exactly one bounded `.pdf`/`application/pdf` candidate but validate signature, non-empty size, page limit, encryption/corruption, and bounded streaming. Historical recommended limits were 10 MiB and 30 pages. OCR is optional only when no usable text layer exists; otherwise return a friendly manual-entry fallback.

The response includes `status`, `preview_id`, `expires_at`, `items`, summary counts, and warnings. Each item has temporary ID, `item_type`, closed `status`, selection, code/name/class/schedule, source, SIGAA lookup state, confidence, and warnings. Do not return full extracted text or personal header data.

Item statuses are:

- `recognized`: sufficient coherent code/name;
- `ambiguous`: incomplete/conflicting/low confidence and not confirmable until corrected;
- `not_found`: no public enrichment but potentially valid local discipline;
- `duplicate`: already registered or repeated in preview;
- `activity`: non-discipline academic activity;
- `rejected`: minimum validations fail.

## Edit and confirmation API

The UI may edit only `code`, `name`, `class_code`, `schedule_code`, `local`, and selection. Backend revalidates all edits and membership in the preview.

```http
POST /api/import/matricula-pdf/confirm
Content-Type: application/json
```

```json
{
  "preview_id": "uuid",
  "items": [{
    "preview_item_id": "uuid",
    "selected": true,
    "code": "FGA0000",
    "name": "Disciplina de Exemplo",
    "class_code": "01",
    "schedule_code": "24M12",
    "local": null
  }]
}
```

Only preview-owned selected valid disciplines may be created. Recheck duplicates at confirmation. Repeated confirmation is idempotent. Return `success`, `partial_success`, `no_items`, or sanitized `error`, plus created/duplicates/rejected/skipped lists, warnings, summary counts, and `request_id`.

## Local extraction and normalization

Use a local library such as pdfplumber/PyMuPDF. Prefer the main component table and code pattern `[A-Z]{3}\d{4}`; segment code blocks, rebuild multiline names without professor/status metadata, recognize `Tipo: DISCIPLINA`, exclude headers/footers/auth text and weekly schedule table from discipline candidates, and classify empty-class/schedule activities safely. Spec 010 separately interprets weekly schedule data.

Normalization is deterministic/idempotent: trim/collapse spaces, compare case-insensitively, normalize Unicode only for comparison while preserving display accents, normalize code separators without changing academic value, convert empty to null, deduplicate after normalization, and retain origin/warnings. Never let an LLM invent a name.

## Optional public SIGAA enrichment

Reuse the existing public search/cache, preferring reliable code, then name only for missing code/inconsistency. Treat `found`, `not_found`, and `error` distinctly. Only actually found public name/workload/syllabus/program fields may be proposed; do not silently replace local extraction. Timeout/unavailability never blocks local review.

## Privacy, lifecycle, guardrails, and fallback

Process in a non-public temporary area with bounded memory/streaming. Delete file/buffers in `finally` on success/error/cancel; keep only minimal TTL preview data (historically 15 minutes), then discard on confirmation/expiry. Persist only confirmed academic fields. Never log/store full text, filename with personal identity, student name/registration/CPF/verification code, auth headers, secrets, or raw PDF.

Reject absent/empty/oversized/wrong/corrupt/encrypted input, excess pages/items/time, invalid/foreign/expired preview IDs, extra fields, invalid code/name, academic activities as disciplines, and normalized duplicates. No item persists before confirmation. Partial batch failure preserves valid creations and reports the rest. PDF/parser failure, no candidates, SIGAA failure/not-found, expiry, and per-item errors all lead to explicit friendly fallback/retry/manual paths.

## Frontend behavior

Provide file selector and visible limits, loading, friendly validation, preview cards/table with fields/origin/status, eligible selection, basic edit/removal, status styling, separate disabled-until-valid confirmation, final report, manual-entry link, preview preservation on recoverable confirmation error, and list refresh only after confirmation. Never show raw JSON, full PDF text, stack trace, or unnecessary personal fields.

## Observability, tests, and acceptance criteria

Log request/preview IDs, validation/extraction/SIGAA latency, byte/page counts, item-status counts, created count, cache/fallback, error category, and final/partial result—never document content or identity.

Tests cover valid one/many disciplines, code/name/class/schedule, activity separation, invalid/corrupt/empty/oversized/no-text PDFs, normalization, ambiguity, ignored noise, non-mutating preview, expiry/foreign item, edit/removal, existing/internal duplicate, full/partial/idempotent confirmation, SIGAA outcomes/cache, temporary cleanup, log/error privacy, OpenAPI, and frontend review states using anonymized fixtures without live SIGAA. Acceptance requires preview-before-save, explicit human correction/confirmation, no duplicate overwrite, clear statuses/partial results, cleanup/privacy, continued manual/SIGAA flow, and Docker compatibility.

## Relationship

Implements Spec 001 import. Spec 010 refines readable schedules and detail enrichment; Spec 012 adds owner-isolated persistence/authentication; later specs do not remove the human-confirmation requirement.
