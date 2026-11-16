# Teacher-Readiness Audit & Hardening Report

- **Date:** 2026-11-17
- **Repository:** `https://github.com/mahdiking999/teacher-system2` (`main`)
- **Live URL:** `https://teachersys.onrender.com`
- **Audit Scope:** Full-stack audit and remediation across Backend FastAPI APIs, Export Engines (`PDF`/`DOCX`/`PPTX`), PDF Extraction (`PyMuPDF`), OmniRoute / NVIDIA NIM AI workflows, Live Render Production (`7bd209a` baseline), and all 13 Next.js Frontend screens.

---

## 1. Executive Verdict

Following multi-agent testing and remediation across backend, exports, AI workflows, and frontend UX:
- **Backend Automated Verification (`pytest backend/tests/ -v`):** **26 / 26 passed in 1.79s** (including 5 new regression tests in `backend/tests/test_regressions_audit.py`).
- **Frontend TypeScript Check (`npx tsc --noEmit`):** **Passed (exit code `0`)**.
- **Frontend Production Build (`npm run build` with `NODE_OPTIONS="--max-old-space-size=400"`):** **15 / 15 Next.js App Router pages built cleanly (exit code `0`, compiled in `262ms`)**.
- **Readiness Status:** Ready for pilot teacher onboarding locally and on Render once changes are deployed from `origin/main` and optional production environment variables are confirmed.

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
  - Expanded `export_database_backup_dict` and `restore_database_backup_dict` to export and upsert `templates`, `sources`, `chapters`, `lessons`, and `plans` in foreign-key order while retaining `backupVersion == "1.0"`.
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

All automated checks were executed after all edits and appended to `handoff/verification_test_output.log`:

| Check | Command | Result |
| :--- | :--- | :--- |
| Backend Full Test Suite | `.\.venv\Scripts\python.exe -m pytest backend/tests/ -v` | **26 passed in 1.79s** (`PYTEST_EXIT=0`) |
| Frontend TypeScript | `cd frontend && npx tsc --noEmit` | **Passed** (`TSC_EXIT=0`) |
| Frontend Production Build | `cd frontend && NODE_OPTIONS="--max-old-space-size=400" npm run build` | **15 / 15 static pages built cleanly in 226ms** (`EXIT_CODE=0`) |

> [!NOTE]
> `next build` reported a Next.js `16.4.2` security advisory notice (`next upgrade --agent=security` recommended for a follow-up upgrade).

---

## 5. Remaining Operator / Deployment Items

1. **Deploy Updated Commit to Render:** Pushing these fixes to `origin/main` triggers automatic Render Docker rebuild and deployment to `https://teachersys.onrender.com`.
2. **OmniRoute / AI Environment Variables on Render:** Verify `TAILSCALE_AUTHKEY` is current and valid on Render (`TAILSCALE_HTTP_PROXY=http://127.0.0.1:1055`, targeting `http://100.120.103.82:20128/v1`), and optionally set `NVIDIA_API_KEYS` as direct fallback when Tailscale/OmniRoute is offline.
3. **Optional Teacher Gate (`PILOT_ACCESS_PIN`):** Populate `PILOT_ACCESS_PIN` in Render Environment Variables when sharing `https://teachersys.onrender.com` with teachers prior to Batch 6 multi-user authentication.
