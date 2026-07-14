# Spec 012 — Persistence, Restricted Authentication, and Academic Catalog

> Canonical language: English
> Translation: [../spec_traduzido/012-persistencia-autenticacao-catalogo-academico.md](../spec_traduzido/012-persistencia-autenticacao-catalogo-academico.md)
> Status: implemented
> Last reviewed: 2026-07-13

> **Evolution notice:** The original restricted-authentication slice was later extended on `main` with configuration-controlled public registration. `ALLOW_REGISTRATION` is now the backend authority for enabling or disabling account creation.

## Problem statement

In-memory storage lost disciplines, assessments, course plans, absences, contents, and associations on restart, and academic routes had no user identity. Public SIGAA enrichment also needed a persistent catalog separate from personal selections.

## Architecture and persistence

- SQLAlchemy uses `DATABASE_URL`, with local SQLite and PostgreSQL compatibility.
- Alembic creates users, catalog, user disciplines, assessments, absences, course plans, contents, associations, complexity analyses, and—through Spec 013—academic events.
- Compatible facades replace old dictionaries; the database is the academic source of truth. TTL previews remain temporary.
- Middleware authenticates academic routes using a signed token. `EMAIL_TESTE`/`SENHA_TESTE` idempotently seed the restricted user.
- Public catalog results receive idempotent upserts. A learner's selection references/copies auditable catalog data without sharing personal data.

## API contracts

- `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`.
- `GET /api/catalog/components/{code}` plus on-demand refresh through the existing SIGAA flow.
- `POST /api/disciplines/{id}/complexity-analysis` analyzes only the selected discipline, persists the result, and permits explicit reanalysis.
- Existing academic responses remain backward compatible.

## Guardrails and fallback

- PBKDF2 salted passwords; HMAC tokens with environment secret and expiry;
- never log password, token, full prompt, or full syllabus;
- mandatory `user_id` isolation;
- `ALLOW_REGISTRATION` is the backend authority for enabling account creation; disabled registration must not affect existing login;
- bounded/sanitized syllabus;
- public scraper timeout, cache, limited retry, and authentication blocking;
- complexity is an estimate, never objective difficulty, prerequisite, or exam content;
- invalid/unavailable LLM uses an identified local rule.

## Local files and Git

The runtime SQLite database resolves to `backend/data/estudaunb.db` regardless of current directory; Docker uses `/data/estudaunb.db` in a volume. Ignore the database and `-wal`, `-shm`, `-journal` companions, including the legacy `backend/estudaunb.db` path. Keep `backend/data/.gitkeep`. Never hide Alembic, models, import scripts, sanitized fixtures, or `.env.example`.

## Public landing and authentication UX

- `/` is public and does not redirect automatically; `/login` and `/register` are public while academic routes are protected.
- An unauthenticated protected route preserves a safe destination, redirects to login, and restores it after authentication.
- Login provides accessible validation/loading/friendly errors. Logout removes the local session.
- Registration reads `GET /api/auth/registration-status`; when enabled, `POST /api/auth/register` validates the account, creates an isolated user, and returns the same token contract as login.
- When `ALLOW_REGISTRATION=false`, the complete registration form is not offered and account creation remains disabled without affecting login.
- No demo credential is bundled. Operators provide `EMAIL_TESTE`/`SENHA_TESTE` values.

## Acceptance criteria

Validate empty-database migration, restart persistence, idempotent demo user, protected/isolated routes, catalog/syllabus upsert, on-demand cached analysis, ignored runtime databases, public/auth routes, disabled and enabled registration states, unique normalized email, safe redirect restoration, fixture-only scraper tests, backend/frontend/Compose smoke, and absence of bundled credentials.

## Limitations and historical evidence

There is no password recovery, social login, distributed rate limiting, startup-wide catalog sync, or batch analysis. Public registration can be disabled per environment. Calendar limitations in the original slice were superseded by Spec 013.

Historical repository evidence records Alembic 001 on empty SQLite, correct database path/ignore rules, authenticated persistence smoke, `214 passed, 1 skipped`, frontend build, Compose, public/auth route checks, and enabled/disabled registration tests. These results were not automatically re-created by this documentation task.
