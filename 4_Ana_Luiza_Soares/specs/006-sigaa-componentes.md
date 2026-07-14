# Spec 006 — Public SIGAA/UnB Component Integration

> Canonical language: English
> Translation: [../spec_traduzido/006-sigaa-componentes.md](../spec_traduzido/006-sigaa-componentes.md)
> Status: implemented
> Last reviewed: 2026-07-13

## Context, problem, and goal

Enrich manually registered disciplines with auditable public UnB curriculum-component data by code/name without login, authenticated access, or loss of manual fallback. The initial public source is `https://sigaa.unb.br/sigaa/public/componentes/busca_componentes.jsf` plus derived public detail/turma pages.

## Source constraints and non-goals

Use only public navigation and on-demand queries. Do not bypass controls, scrape the whole catalog, request credentials, collect student data, access approval/dropout history, infer professor difficulty, import PDFs, or depend on a robust new database in this original slice. JSF HTML is fragile; timeout/parser failure is expected and must degrade gracefully. Tests do not use the live network.

## Functional requirements

- backend service searches by component code or name;
- structured output includes code, name, type, unit, workload, syllabus/program when actually found, public source URL, fetch timestamp, and lookup status;
- local memory/JSON cache keyed by normalized query/component, reporting `cached`;
- `GET /api/sigaa/components/search?query=FGA0315`;
- optional `PATCH /api/disciplines/{id}/sigaa-component` association;
- OpenAPI documentation and discipline-detail UI;
- manual discipline operation remains independent of SIGAA.

Example success shape (identifiers remain canonical):

```json
{
  "status": "found",
  "source": "sigaa_public_components",
  "query": "FGA0315",
  "component": {
    "code": "FGA0315",
    "name": "QUALIDADE DE SOFTWARE 1",
    "type": "DISCIPLINA",
    "unit": "FCTE",
    "workload_hours": 60,
    "syllabus": "",
    "current_program": "",
    "source_url": "https://sigaa.unb.br/...",
    "fetched_at": "2026-07-09T23:59:59Z",
    "lookup_status": "found"
  },
  "cached": false,
  "warnings": []
}
```

`not_found` and source-unavailable/parser-failure responses return `component: null`, explicit status/warnings, and preserve manual entry. Later implementation commonly uses controlled `error`/warning variants; OpenAPI/code are authoritative.

## Technical flow and cache

Maintain a `requests.Session`, submit minimal JSF form data/ViewState, parse with BeautifulSoup, follow only public details, normalize into typed output, and persist only public academic metadata. Spec 010/018 refine semantic detail/turma submission, versioned cache completeness, and fallback. Playwright was only a future technical fallback and is not required.

Cache stores no personal data, may be discarded, has a short/configurable TTL, and cannot make the app depend on cached availability. Database catalog upsert introduced by Spec 012 is separate from the runtime request cache.

## Association and frontend behavior

Only actually found fields may update a discipline; empty external fields never erase manual values. Mark source URL/status/timestamp. The UI offers public search, syllabus/program/workload when present, cache/source indication, and friendly missing/unavailable messages without blocking manual use.

## Guardrails, fallback, and observability

Never invent syllabus, program, workload, rate, or professor judgment. Never access authentication, store student data, or bulk scrape. Record request/cache/fetch/not-found/source-unavailable/parse/attach events with query/status/source, safe discipline ID, URL, latency, and error category. Do not record credentials, sessions, student identity, or raw PDF.

## Tests and acceptance criteria

Use sanitized local fixtures for found/not-found/detail variations; mock external failure; verify cache reuse, no live-network dependency, no invented missing fields, friendly endpoint status, association preservation, and OpenAPI. Accept when only public data is used, cache/fallback/manual behavior is explicit, frontend integration exists, and no private/rating data appears. Specs 010 and 018 contain current enrichment details.
