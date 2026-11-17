# Teacher-Readiness Audit & Hardening Report

- **Date:** 2026-11-17
- **Repository:** `https://github.com/mahdiking999/teacher-system2` (`main`)
- **Live URL:** `https://teachersys.onrender.com`
- **Audit Scope:** Full-stack audit and remediation across Backend FastAPI APIs, Export Engines (`PDF`/`DOCX`/`PPTX`), PDF Extraction (`PyMuPDF`), OmniRoute / NVIDIA NIM AI workflows, Live Render Production (`7bd209a` baseline), and all 13 Next.js Frontend screens.

---

## 1. Executive Verdict

> **Superseded (2026-11-17, later audit pass).** The `26 / 26` and "Ready for pilot" verdict below is historical and no longer current. The latest local evidence is in [`PILOT_TEST_REPORT.md`](./PILOT_TEST_REPORT.md): **31 backend tests passed** on isolated SQLite, frontend typecheck passed, and the production build emitted all 15 pages. PostgreSQL runtime behavior, browser journeys, Render configuration, and the deployed service remain **unverified**. Pilot status is **BLOCKED / UNVERIFIED**.

Historical result from this earlier pass (backend/exports/AI/frontend UX):
- **Backend Automated Verification (`pytest backend/tests/ -v`):** **26 / 26 passed** at that time (superseded by the current 31-test suite).
- **Frontend TypeScript Check (`npx tsc --noEmit`):** **Passed (exit code `0`)**.
- **Frontend Production Build (`npm run build`):** **15 / 15 Next.js App Router pages built** (exit code `0`).
- **Readiness Status at the time:** not deployable — the subsequent audit pass found unauthenticated read APIs and a tracked credential, which are now addressed in source but still require Render configuration and isolated PostgreSQL validation.

---

## 2. Three-Agent Audit Scope & Findings Summary

### A. Backend API, Export & AI Engine Audit (`da994274`)
- Exercised 30+ FastAPI endpoints, 5 subject tools, 6 export formats, Arabic `PyMuPDF` PDF extraction, and live OmniRoute models:
  - `nv-nemotron-3-5-bolt-e4b`: `0.85s` text response verified.
  - `nv-nemotron-3-5-super-vl-120b`: `6.42s` Vision OCR response verified.
  - `nv-nemotron-3-nano-omni-30b`: Vision request timed out at `20s` (use `bolt` / `super-vl` models for production defaults).
- Identified gaps fixed in this pass:
  - PDF exporter emitted WinAnsi mojibake for Arabic text.
  - PPTX comparison layouts, schedule day fallback for weekly/5-day plans, word-boundary wrapping, and overflow continuation slides (`(تابع)`) needed proper handling.
  - AI JSON extraction needed `<think>...</think>` stripping and robust `raw_decode`, plus proportional minute normalization and slide sanitization.
  - Subject tools and 5-day plan auditor needed Arabic-Indic numeral normalization (`٠-٩`), fractions (`3/4`), BCE (`ق.م`) timeline handling, null guards, and negative duration / `< 5` days checks.
  - Backup/restore needed full foreign-key coverage for `templates`, `sources`, `chapters`, `lessons`, and `plans` plus `ValueError`/`TypeError` -> HTTP `400` mapping.
  - Cross-context ownership and active-context guard enforcement on lessons, plans, audits, tools, and source updates.

### B. Live Render Production & DB Persistence Audit (`2b692867`)
- Audited `https://teachersys.onrender.com` live on commit `7bd209a`:
  - `GET /api/health` -> `200 OK` (`databaseDialect: "postgresql"`, `databaseConnected: true`).
  - `GET /api/ai/status` -> `200 OK` (`tailscaleAuthKeyConfigured: true`, `tailscaleProxy: "http://127.0.0.1:1055"`, `directNvidiaConfigured: false`).
  - All read-only endpoints returned `200 OK`; `POST /api/tools/execute` returned `200 OK`; `POST /api/exports` (`docx`) returned `201` + download `200 OK`.
  - All 13 Next.js routes + 8 static assets returned `200 OK`.
  - Flagged PDF WinAnsi mojibake (`exp_761011763298`) on live before fixes — now resolved in `backend/app/services/export_service.py` via `pymupdf.Story` + `subset_fonts()`.

### C. Frontend 13-Screen UX & Teacher Workflow Audit (`c5b80294`)
- Audited `AppShell.tsx`, `globals.css`, `layout.tsx`, and all 13 `frontend/src/app/**/page.tsx` routes.
- Identified and resolved navigation gaps (`/sources` missing from sidebar, mobile sidebar scroll & close button), RTL localization (`uiIsRtl` for `ar`/`ku`/`fa`/`he`), context-switching stale state, browser `alert()`/`prompt()` dialogs, async `<Link onClick>` race conditions, missing `Suspense` wrappers around `useSearchParams()`, and page-specific form/persistence bugs.

---

## 3. Summary of Fixes Implemented

### Backend (`backend/`)
- `backend/app/services/export_service.py`:
  - Rewrote `generate_plan_pdf_bytes` using `pymupdf.Story` + `pymupdf.DocumentWriter` + `subset_fonts()` (`%PDF-1.7`, embedded Arabic Unicode RTL HTML/CSS tables, LTR math blocks, zero WinAnsi mojibake).
  - Updated `verify_exported_file_structure` to inspect PDF pages and extracted text characters via `pymupdf`.
  - Added `is_report` & `report_summary` rendering in `generate_plan_docx_bytes` (`report_docx`).
  - Updated `generate_plan_pptx_bytes` with `comparison` two-column shape layout, `scheduleDays` fallback, `textwrap` word-boundary wrapping, `(تابع)` continuation slides beyond 8 lines, and explicit `None` guards.
- `backend/app/services/ai_service.py`:
  - Updated `_extract_json_from_text` to strip `<think>...</think>` blocks and run `json.JSONDecoder().raw_decode` across `{`/`[` indices.
  - Rewrote `_normalize_phases_minutes` for exact iterative proportional balancing to `total_minutes`.
  - Added `_sanitize_slides` in `generate_daily_plan_with_ai`.
- `backend/app/services/audit_service.py`:
  - Added `_normalize_digits` (`٠-٩` -> `0-9`) and fraction support (`3/4`) in `math_solver`.
  - Added null-coercion guards (`or ""`) across tools & `audit_plan_and_context`.
  - Added `len(events) >= 2` and `"ق.م"` BCE handling in `historical_timeline`.
  - Added safe numeric parsing on phases and negative duration / `< 5` teaching days checks on `five_day` plans.
- `backend/app/services/pdf_service.py`:
  - Raised extraction page limit from `100` to `MAX_PDF_PAGES` (`600`) with `pymupdf` (`import pymupdf as fitz`) and `unicodedata.normalize("NFKC", ...)`.
- `backend/app/services/migration_and_backup.py`:
  - In this earlier pass, backup/restore was limited to `contexts`, `templates`, `sources`, `chapters`, `lessons`, and `plans` under `backupVersion == "1.0"`.
  - **Now:** backup v2 exports all ten relational groups (contexts, templates, sources, source pages, chapters, lessons, plans, plan versions, plan reviews, export tasks). Restore is non-destructive upsert; omitted rows are retained, PDF/export bytes are not included, and restored file paths are cleared/marked unavailable. v1 payload restore remains supported. See [`PILOT_TEST_REPORT.md`](./PILOT_TEST_REPORT.md).
- `backend/app/main.py`:
  - Returned `"version"` in `create_template`.
  - Enforced `expectedVersion` `409` concurrency check and automatic re-audit of linked unapproved plans in `update_source_metadata`.
  - Added `chapterId` cross-context validation in `create_lesson`/`update_lesson`.
  - Enforced `verify_active_context_guard` + `404` checks in `execute_subject_tool`, `run_plan_audit_endpoint`, and `copy_plan_to_another_context`.
  - Added `_compute_total_allocated_minutes` for `weekly`/`five_day` plans and `primaryLessonId`/`secondaryLessonId` context ownership checks in `update_plan`.
  - Removed post-audit `pln.context_snapshot` overwrite in `approve_plan_version`.
  - Routed `dashboard.todayTasks[].targetRoute` by `plan_type` and added `"activityTimeline": []`.
  - Filtered `exportsCount` & added `"approvedPlans"` in `get_reports_summary`.
  - Preserved historical `pver` `approvedBy`, loaded `first_pln` `context_snapshot`/`PlanReview`, and passed `is_report=True` for `report_docx` in `_build_export_bytes`.
  - Caught `(ValueError, TypeError)` -> HTTP `400` in `post_system_restore`.
  - Set `pln.status = "draft"` in `ai_generate_slides_for_plan` and added `_safe_int` + title deduplication in `ai_extract_source_structure`.
- `backend/tests/test_regressions_audit.py`:
  - Added 5 regression tests covering PDF Arabic/no-mojibake, PPTX comparison + overflow continuation, AI JSON extraction + phase normalization, subject tools/5-day edge cases, and security/revocation/isolation/`report_docx`/invalid-restore handling.

### Frontend (`frontend/`)
- `frontend/src/components/AppShell.tsx` & `frontend/src/app/globals.css`:
  - Added `/sources` to `NAV_ITEMS` (localized via `uiIsRtl`), aligned `uiIsRtl` for `ar`/`ku`/`fa`/`he`, updated 10-step `WORKFLOW_STEPS`, added `.app-sidebar` `overflow-y: auto` + mobile `✕` close button, improved `refreshContexts()` error banner + `localStorage` sync + modal reset/spinner (replacing native `alert()`/`prompt()` dialogs).
- All 13 App Routes (`frontend/src/app/**/page.tsx`):
  - Separated `errorMsg` (`blocker-banner`) across all 13 pages.
  - Cleared stale IDs/state on context switching (`/export-package`, `/curriculum`, empty contexts).
  - Wrapped `useSearchParams()` in `<Suspense>` for `?planId=` / `?lessonId=` deep-linking across 7 pages.
  - Replaced async `<Link onClick>` navigation races with awaited saves + `router.push`.
  - Enhanced `/daily-plan` (`title`, `sourceId`, `primaryLessonId`, `+ خطة جديدة`, `homeEnrichmentMinutes`, phase delete/reorder, `planningNotes`, `subjectItems`), `/weekly-plan` & `/five-day-plan` (activities/lesson/minutes), `/review` (auto-audit on load, `approverName`, dynamic blocker targets), `/lessons` (`contentOrigin` safety fix), `/tools` (`worksheet_generator` + `science_experiment` inputs, `expectedVersion` rollback), `/settings` (`schoolName` + `documentPreferences` persistence), `/presentations` (`layoutStyle` live comparison preview & settings restore), `/sources` (drag-drop, extracted structure links, unsaved page warning), and `/reports` (filter sync).

---

## 4. Verification Results

> These rows are historical results from the earlier pass and are **not** the current validation. See [`PILOT_TEST_REPORT.md`](./PILOT_TEST_REPORT.md) for the current evidence, which must be re-run after any further edits.

| Check | Command | Result (earlier pass) |
| :--- | :--- | :--- |
| Backend Full Test Suite | `.\.venv\Scripts\python.exe -m pytest backend/tests/ -v` | **26 passed** (`PYTEST_EXIT=0`) — superseded by the current 31-test run |
| Frontend TypeScript | `cd frontend && npx tsc --noEmit` | **Passed** (`TSC_EXIT=0`) |
| Frontend Production Build | `cd frontend && NODE_OPTIONS="--max-old-space-size=400" npm run build` | **15 / 15 static pages built** (`EXIT_CODE=0`) |

> [!NOTE]
> `next build` reported a Next.js `16.4.2` security advisory notice (`next upgrade --agent=security` recommended for a follow-up upgrade).
>
> `next.config.mjs` sets `typescript.ignoreBuildErrors: true`, so the build does not type-check. The explicit `tsc --noEmit` run is mandatory evidence; a successful build alone is not.
>
> These checks ran against isolated SQLite only. No PostgreSQL instance, Docker stack, browser suite, or deployed Render request was exercised.

---

## 5. Remaining Operator / Deployment Items

Pilot exposure is **blocked** until all of the following are completed by an authorized operator:

1. **Configure the access gate:** set a non-empty `PILOT_ACCESS_PIN` in the Render secret store. All `/api/*` routes except `/api/health` now return `503 PILOT_PIN_NOT_CONFIGURED` when the pin is unset and `401 PILOT_PIN_REQUIRED` for a missing/wrong pin, so an unset pin makes the app unusable rather than open. Do not record the value in source, logs, or evidence.
2. **Rotate the exposed credential:** the formerly hard-coded AI key must be revoked externally and a replacement supplied through Render secrets, or AI left disabled (deterministic fallback only). Git-history exposure is unchanged by the working-tree removal; history remediation needs separate authorization.
3. **Validate on isolated PostgreSQL:** search case-insensitivity, migrations, and v2 backup/restore round-trip are proven on SQLite only. Never substitute the production database.
4. **Resolve the deployed 503 and verify readiness read-only:** service status, environment configuration, seed-off status (`ENABLE_DEMO_SEED=0`), `/api/health`, and PIN denial behavior are all unverified; the 503 cause is unresolved.
5. **Treat Render local storage as non-durable:** uploaded source PDFs and generated export binaries are not covered by the JSON DB backup and are lost on container replacement; exports self-heal only when their metadata and source data still exist.
6. **Run the deferred audits:** browser journeys across all 13 routes with a pinned Playwright dependency, and a redacted history/secret review, remain outstanding.
7. **Gate deployment:** deploy only after the isolated PostgreSQL and browser gates pass. Deployed checks must stay read-only (no uploads, AI generation, exports, restores, or data mutation).
