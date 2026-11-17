# Pilot Test Report — Teacher System

**Audit date:** 2026-11-17  
**Repository:** `Teacher-Sys`  
**Branch / baseline commit:** `main` / `8a3f99604bbb9c4df359a5043db6883c1c78d1bb`  
**Scope:** Local source audit and isolated SQLite regression tests. No production or deployed-service requests were made.

## Executive summary

Local remediation covers the shared PIN gate, credential removal from tracked source/config, source verification field updates and linked-plan re-audit, case-insensitive lesson search, AI status sanitization, and v2 relational backup/restore. Final local checks: **31 backend tests passed** (3 deprecation warnings), frontend typecheck passed, and production build generated all 15 pages. No PostgreSQL or deployed checks are included.

**Pilot/deployment status: BLOCKED / UNVERIFIED.** This audit did not validate PostgreSQL, browser journeys, Render configuration, the deployed service, its reported 503, or its PIN setting. The shared PIN is a deployment gate, not user identity or tenant isolation. Do not interpret historic live results in this report as current verification.

## Current local evidence

- Backend tests use a disposable temporary SQLite database and storage directory (`backend/tests/conftest.py`); demo seeding is disabled and test PIN is configured. The final rerun recorded in [`evidence/local-remediation-checks-2026-11-17.json`](evidence/local-remediation-checks-2026-11-17.json) passed all 31 tests.
- PIN regression coverage checks protected reads, writes, backup/restore, denial without a header (including query-string bypass attempts), and docs/OpenAPI disablement. Download tests send the PIN header.
- Lesson-search regression covers mixed-case English, Arabic text, and no-match results on SQLite. PostgreSQL behavior is not proven.
- Source-verification regression checks verified year/edition updates on the context and removal of the pending-verification finding on a linked plan.
- Backup v2 covers ten relational groups: contexts, templates, sources, source pages, chapters, lessons, plans, plan versions, plan reviews, and export tasks. Its restore semantics are upsert-only; missing rows are retained. Tests exercise representative field fidelity, repeated restore, rollback of invalid data, and marking source/export files unavailable.
- JSON backup excludes uploaded PDF and generated export bytes. Restored paths are cleared; exports are marked unavailable. This is not a complete filesystem backup.
- Source code/config scan found no credential-pattern matches. A redacted Git-history scan found one matching commit, so current-tree removal does not remove historical exposure. External revocation/rotation is unverified. `render.yaml` declares the shared PIN as an unsynced secret and disables demo seeding; actual Render values are unknown.
- AI status returns readiness booleans rather than provider URLs, model names, or credential configuration. Its PIN gate is covered by the general API middleware.
- Frontend PIN flow, authenticated API calls, and authenticated binary downloads have been implemented. `npm exec tsc -- --noEmit` passed; `npm run build` generated all 15 pages (the build skips type validation, hence the separate check). No Playwright or interactive browser test was run.

## Unverified checks and deployment blockers

- **PostgreSQL:** No local Docker, PostgreSQL server/client, or `pg_isready` tool was available. SQLite tests do not establish PostgreSQL runtime behavior, including `ilike`, migrations, or full backup/restore.
- **Render/deployed service:** Render CLI/credentials were unavailable. No deployed request was sent, so current health, database dialect, PIN enforcement, environment configuration, and the previously reported HTTP 503 cause are unknown.
- **Credential response:** Removing a key from current files does not revoke it or erase Git history. Authorized external rotation/revocation and any separately approved history remediation remain outstanding.
- **Browser/feature audit:** No browser automation across all 13 routes was performed. Existing static/fallback behaviors and absent UI/API features remain gaps, not verified journeys.
- **Storage durability:** Render local storage is not established as durable by this audit; source/export bytes require separately managed persistent storage/backups.

## Required gates before pilot exposure

1. Rerun backend tests, frontend typecheck/build, redacted credential scan, and final diff review after all edits.
2. Validate the application against an isolated PostgreSQL service, including search and backup/restore integrity; do not substitute production data.
3. Have an authorized operator set a non-empty Render PIN and verify deployment configuration, seed-off status, startup/readiness, and the deployed API gate. Determine the 503 cause from authorized, read-only evidence.
4. Confirm exposed credential revocation/rotation and secret-store configuration without recording secret values.
5. Review CORS configuration, Render storage limits/durability, and rollback conditions. Keep deployed checks read-only and avoid production writes, uploads, AI, exports, restores, or cleanup.

No deployment or production mutation was performed as part of this audit.