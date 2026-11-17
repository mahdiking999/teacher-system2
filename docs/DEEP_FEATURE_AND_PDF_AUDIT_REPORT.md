# Deep Feature, UI & Visual PDF/Document Verification Report (`Teacher-Sys`)

**Repository:** `E:\AISHIT\Antigravity_and_Freebuff\MohCollabs\Teacher-Sys`  
**Audit Date:** 2026-11-17  
**Baseline Commit Inspected:** `bb3939f2e8b00a581c460b12503075463ad577e0` (`main`)  
**Audit Mode:** Read-only across application source (`git status` clean across tracked app files; all scratch scripts, exported documents, rendered PDF page PNGs, and browser screenshots stored in the conversation scratch directory `.../scratch/deep_audit/`).

---

## 1. Executive Summary & Audit Methodology

### 1.1 Baseline Comparison (`local-remediation-checks`, `PILOT_TEST_REPORT.md`, `PROMISED_FEATURES.md`)
- **`docs/evidence/local-remediation-checks-2026-11-17.json` & `docs/PILOT_TEST_REPORT.md`** established a clean local baseline on `8a3f996`/`bb3939f`: `31` backend tests passing against an isolated SQLite DB, clean TypeScript `tsc --noEmit`, `13`-app-route (`15` Next.js build pages) production build, shared `PILOT_ACCESS_PIN` gating, credential-pattern scan cleanup, and backup v2 support across 10 tables — while explicitly flagging that **no PostgreSQL runtime, no interactive browser journeys across the 13 routes, and no visual/structural content inspection of generated PDFs under real workflows** had been executed.
- **`PROMISED_FEATURES.md`** inventoried every capability promised across roadmaps, the 13 root design mockups, all 36 FastAPI routes, and all 13 Next.js screens.

### 1.2 What This Deep Audit Actually Tested (4 Parallel Audit Tracks)
| Audit Track | Scope Exercised | Headline Result |
| :--- | :--- | :--- |
| **1. Deep Exports & Visual PDF/DOCX/PPTX Inspection** | Inspected committed `docs/evidence/sample_exports/*`, plus generated & visually viewed 150-DPI PNGs of all pages across `docx`, `pdf`, `pptx`, `report_pdf`, `report_docx`, `bundle_zip` for `daily`, `weekly`, `five_day`, `approved`, `unverified_draft`, and `en`/LTR scenarios + OOXML/CMap dumps. | **4 Critical / High Visual & Data-Integrity Defects Found** (multi-page PDF ghost green bars/banner bleed, reversed math formulas `(15+9)/3=8` -> `8 = 3 / (9+15)`, corrupted `ToUnicode` CMap `Ǆ/ƾ/ǁ/ǂ`, stale WinAnsi sample PDFs, and silent omission of `totalAllocatedMinutes` + `planningNotes` + `homeEnrichmentMinutes` + `referencesNote` + per-day `objectives`). |
| **2. Real Textbook PDF & AI Pipeline Audit** | Ingested the real 196-page Iraqi 2nd Intermediate Math textbook PDF (`media_1794868054105_41184d7e.pdf`), rendered & visually inspected key pages (`cover`, `pretest p.5`, `TOC p.195`), tested synthetic PNG/JPEG image-only scans and invalid PDFs, probed live OmniRoute (`100.120.103.82:20128`) & tested all 4 AI endpoints. | **Critical Scanned-PDF & Offline-OCR State Bugs Found** (image-only scans misclassified as `extracted_text` with 26KB+ of binary garbage; offline `ai-ocr` flips `requires_ocr_or_manual` to `extracted_text` using error text; `[:1400]` truncates real TOC Ch. 3, 4 & 7; 3,133+ Lam-Alef reversals; post-`bb3939f` empty `OMNIROUTE_API_KEY` skips reachable OmniRoute). |
| **3. Backend API, Audit Engine, Tools, Backup v2 & Security** | Re-ran full pytest suite (`31 passed, 3 warnings in 1.51s`), probed **all 36 / 36 FastAPI routes**, tested 23 subject-tool inputs, probed Backup v1/v2 restore recovery, and tested `weekly`/`five_day` audit & approval edge cases. | **Critical Post-Restore Download Crash (`500`) & Audit Bypasses Found** (after Backup v2 restore sets `ExportTask.file_path=""`, `/api/exports/{id}/download` crashes with `500`; `five_day` & `weekly` plans approve cleanly with blank per-day `assessment` or `0` minutes; unset `PILOT_ACCESS_PIN` locks out local dev/Render with `503`; `copy-to-context` triggers `TIME_DISTRIBUTION_MISMATCH`). |
| **4. Live 13-Screen Frontend & Real Chrome CDP Journey** | Booted Next.js `16.4.2` (`next start` on `127.0.0.1:3011`) + FastAPI (`127.0.0.1:8000` with `PILOT_ACCESS_PIN=1234`), drove headless Chrome across all 13 routes at `1440x900`, `390x844`, `320x800` + live interactive flows, and visually inspected screenshots. | **`0` uncaught JS exceptions & `0` horizontal overflow**, PIN gate works end-to-end — **but found `401` `<a href>` fallback download links** on `/daily-plan`, `/presentations`, `/reports`, broken `scripts/generate_evidence_and_screenshots.py`, stale sidebar after `/sources` verification, unsaved state wipe in `/presentations`, build-time `INTERNAL_API_URL` baking, and mixed LTR-Arabic when language=`en`. |

---

## 2. Deep Visual & Structural Inspection of Exported PDFs, DOCX, PPTX & Bundles

### 2.1 Visually Verified PDF Defects (`backend/app/services/export_service.py:663–841`)

1. **[P0 CRITICAL — Visual Defect] Multi-Page PDF Ghost Table Header Bars & Banner Bleed (`pymupdf.Story`):**
   - **Observed Visually:** On pages 2 and 3 of multi-page PDFs (`02_daily_approved_pdf_p2.png`, `02_daily_approved_pdf_p3.png`, `01_daily_draft_pdf_p2.png`, `03b_weekly_draft_pdf_p2.png`, `04_five_day_draft_pdf_p2.png`, `05_en_ltr_pdf_p2.png`), dark-green (`#154434`) horizontal fill strips slice straight across Row 4 (`المرحلة التفصيلية رقم 4` / `الكتاب الموثق ص 18`) and body paragraphs (`مراعاة الفروق الفردية: دعم متدرج...`), alongside a pale-yellow `#FEF3C7` strip at the top of continuation pages.
   - **Root Cause:** MuPDF `1.28.2` `pymupdf.Story` paired with CSS `border-collapse: collapse;` (`export_service.py:813`) and `.banner`/`.badge-warn` `background-color` (`lines 811–812`) re-emits background fill rectangles at Page-1 Y-coordinates during subsequent `story.place()` / `story.draw()` page passes. Verified in isolation (`check_story_quirks.py`) that switching to `border-collapse: separate; border-spacing: 0;` and eliminating block `div` `background-color` (e.g., border-left accent or wrapper `<table>`) eliminates page-2 ghost fills (`p2_fills = []`).

2. **[P0 CRITICAL — Math Meaning Reversed] RTL Math Expressions Rendered Backwards (`export_service.py:789`):**
   - **Observed Visually (`02_daily_approved_pdf_p2.png`, `09_repro_math_fixes.png`):** Line 789 emits `<li dir='ltr' style='text-align:left;font-weight:bold;color:#176B52'>{expr_line}</li>`. MuPDF `Story` ignores `<li dir="ltr">` inside an RTL `body`, leaving the `•` bullet orphaned on the right margin while evaluating the math expression under RTL UAX #9 bidi order — rendering `(15 + 9) / 3 = 8 سم` visually backwards as **`سم 8 = 3 / (9 + 15)`** (swapping dividend and divisor and reversing the equation). Verified that explicit Unicode directional isolation (`\u202A...\u202C` / `\u2066...\u2069`) preserves `(15 + 9) / 3 = 8`.

3. **[P0 CRITICAL — Corrupted Copy/Paste & Extraction] Built-in `Noto Naskh Arabic` `ToUnicode` CMap Corruption (`export_service.py:808, 826–841`):**
   - **Observed in `page.get_text("text")` across ALL generated PDFs:** `pymupdf.Story(html=html_doc)` defaults `font-family: sans-serif` to MuPDF's built-in `Noto Naskh Arabic Regular`, whose `ToUnicode` CMap maps Arabic `ل` glyphs to Latin Extended-B `Ǆ` (`U+01C4`, ×407 in `02_daily_approved_pdf.pdf`), `ǁ` (`U+01C1`, ×130), `ǂ` (`U+01C2`, ×19) and `لا/لأ/لإ` ligatures to `ƾ` (`U+01BE`, ×43) + raw ASCII control bytes (`\x06`, `\x09`, `\x0c`, `\x15`). Copy-pasting or extracting text from any exported PDF yields strings such as `ﺍǄﻤﻌﺎﺩƾ\x06ﺕ ﺍǄﺨﻄﻴﺔ`.
   - **Why Automated Tests Missed This:** `verify_exported_file_structure` (`export_service.py:911–932`) only verifies `len(doc) >= 1` and `extracted_chars > 0`, and `test_regressions_audit.py:42` only asserts `"Ø" not in txt`.
   - **Controlled Proof:** Passing a system/bundled Arabic TTF (e.g., Windows `arial.ttf` via `pymupdf.Archive(...)` + `@font-face`) both with and without `doc.subset_fonts()` produced **`0` suspicious characters, `0` control bytes, and `17/17` exact Arabic words after `NFKC`**.

4. **[P1 HIGH — Stale Broken Repository Artifacts] Mojibake PDFs & Mismatched Checksums in `docs/evidence/sample_exports/`:**
   - Visually inspecting [`docs/evidence/sample_exports/sample_daily_plan.pdf`](file:///E:/AISHIT/Antigravity_and_Freebuff/MohCollabs/Teacher-Sys/docs/evidence/sample_exports/sample_daily_plan.pdf), [`docs/evidence/sample_exports/sample_planning_report.pdf`](file:///E:/AISHIT/Antigravity_and_Freebuff/MohCollabs/Teacher-Sys/docs/evidence/sample_exports/sample_planning_report.pdf), and `2_daily_plan_printable.pdf` / `4_planning_completion_report.pdf` inside `sample_full_bundle.zip` confirms all of them are **unreadable legacy `Helvetica` / `WinAnsiEncoding` mojibake PDFs** (`Ø¯Ø±Ø³ ØªØ¬Ø±ÙŠØ¨ÙŠ` + `þÿ` UTF-16BE BOM bytes).
   - Furthermore, their on-disk sizes (`10,381` B and `5,393` B) and SHA-256 hashes do **not** match [`docs/evidence/export_verification_report.json`](file:///E:/AISHIT/Antigravity_and_Freebuff/MohCollabs/Teacher-Sys/docs/evidence/export_verification_report.json) (`10,314` B and `5,342` B).

5. **[P1 HIGH — Silent Data Loss & Time Contradiction] Fields Dropped Between DB, `PlanVersion`, and Exports:**
   - `_save_plan_version_and_review` (`backend/app/main.py:1057–1084`) omits **`totalAllocatedMinutes`**, **`homeEnrichmentMinutes`**, **`referencesNote`**, and **`planningNotes`** (where `/tools` saves verified outputs!) from `PlanVersion.plan_payload`, and `seed_service.py:529–548` omits the same plus teacher/school metadata from seeded v1 snapshots.
   - **Visible Contradiction on Exported Weekly & Five-Day PDFs/DOCX (`03_weekly_approved_pdf_p1.png`, `04_five_day_draft_pdf_p1.png`):** Because `totalAllocatedMinutes` is `None` in `PlanVersion.plan_payload`, the summary table falls back to `periods_count * period_minutes = 45 دقيقة`, directly contradicting the audit findings row `225 دقيقة` on the exact same page.
   - **Additional Omissions in `export_service.py`:** `planningNotes`, `homeEnrichmentMinutes`, `referencesNote`, `teacherRole`, `studentRole` are never read anywhere in `export_service.py`; `scheduleDays[i].objectives` is omitted from DOCX/PDF (`export_service.py:219, 759`); PDF omits phase `objective` (7 cols vs DOCX's 8 cols) and finding `fieldTarget`; DOCX prints raw `json.dumps(item)` for non-math `subjectItems` (`line 250`).

6. **[P1/P2 — English (`language="en"`), OOXML DOCX & PPTX Structure Bugs]:**
   - **`language="en"` Exports (`05_en_ltr_pdf_p1.png`, DOCX, PPTX):** All section headers, banners, table columns, and status labels remain hardcoded Arabic, scrambling mixed strings (`"1الطبعة: ... st Edition"`) and hardcoding `<w:lang w:bidi="ar-IQ"/>` / `lang="ar-IQ"`.
   - **DOCX (`export_service.py:99–114`):** `<w:tbl>` lacks required ECMA-376 `<w:tblGrid>` / `<w:gridCol>` and cell `<w:tcW>` widths, forcing equal column widths.
   - **PPTX (`export_service.py:360–539` & Bundle ZIP):** `comparison` layout silently reverts to 1-column `MainContent` on slides with `< 2` lines or `(تابع)` 1-line overflow chunks, hardcodes `CompareCol1` on right / `CompareCol2` on left even in LTR, omits `rtl="1"` on `<p:presentation>`, omits holidays from weekly auto-slides, duplicates `phases[2]` across slides 3–4, and `bundle_zip` (`main.py:1900–1901`) hardcodes `1_daily_plan_editable.docx` / `2_daily_plan_printable.pdf` even for weekly/5-day plans.

---

## 3. Real Textbook PDF Ingestion, Page Preview & AI Pipeline Audit

### 3.1 Real 196-Page Iraqi 2nd Intermediate Math Textbook Results (`pdf_service.py`)
- **Ingested File:** `media_1794868054105_41184d7e.pdf` (`9.07 MB`, `196` pages, Adobe InDesign CS5.5, `0` embedded PDF bookmarks). Upload took `1.061 s` (`HTTP 201`), extracting text across all `196/196` pages.
- **Visual Comparison (`page_005.png`, `page_195.png` vs extracted text):**
  1. **[P1 HIGH] Systematic Lam-Alef (`لا/لأ/لإ/لآ`) Reversal:** Every Adobe InDesign Lam-Alef ligature extracts reversed (`المشكالتِ`, `األعداد`, `اإلطالق` — **3,133+** occurrences across 196 pages). Because `pdf_service.py:178` only runs `NFKC`, substring search in `main.py:2330–2338` fails to match normal Arabic lesson titles against extracted textbook pages.
  2. **[P2 MEDIUM] Math Notation & BiDi Extraction Loss:** Stacked fractions lose fraction bars and detach numerators from questions (`Pretest` p.5); vector radical signs (`√`, `∛`) vanish (`√50` -> `50`); exponents collapse inline (`10^-1` -> `10-1`); `[1-1]` lesson codes extract as `]1-1[` on `43` pages; Cover date `١٤٤٧ هـ / ٢٠٢٥ م` scrambles into `م202٥/ ٤٤١هـ7`.
  3. **[P2 MEDIUM] `printedPageNumber` & `ocrAmbiguities` Precision:** `21 / 196` pages (`10.7%`) get wrong `printedPageNumber` (e.g., p.1 -> `"8"`, p.109 -> `"3000"`, p.192 -> `"0"`). `needsOcrReview` fires on `124/196` pages, with **`90/118` math flags triggered falsely on `1-1` lesson codes** and `14/14` date flags triggered on math integers (`1000`, `1666`), while missing `45` actual math expression pages (`=`, `×`, `\u2212`, stacked fractions).

### 3.2 Critical Scanned PDF, `[:1400]` TOC Truncation & AI Pipeline Defects
1. **[P0 CRITICAL — Garbage Storage] Image-Only Scanned PDFs Classified as `"extracted_text"` (`pdf_service.py:83–105, 198–205`):** `_extract_text_from_pdf_stream` runs regexes over **all** PDF streams including `/Image` XObjects. Both a 3-page PNG scan (`0` text layer) and a 1-page JPEG scan were marked `extractionStatus: "extracted_text"` with up to `26,711` chars of random binary pixel bytes stored as `extractedText`. Meanwhile, a corrupt body with a valid `%PDF-1.4` header is silently swallowed (`lines 182–190`) into `"requires_ocr_or_manual"` instead of raising `ValueError`.
2. **[P0 CRITICAL — False Verification State] Offline `ai-ocr` Clears `SOURCE_REQUIRES_OCR_REVIEW` (`ai_service.py:510`, `main.py:2222–2228`):** When Vision OCR falls back offline on an image/empty page, it writes `"[صفحة 1: لم يتسنّ الاستخراج التلقائي — يرجى المراجعة اليدوية]"` into `extractedText` and **upgrades `CurriculumSource.extraction_status` from `"requires_ocr_or_manual"` to `"extracted_text"`**, erasing the audit warning without extracting any real text, while also overwriting `printedPageNumber` and failing to recompute `ocrAmbiguities`.
3. **[P1 HIGH] `[:1400]` Prompt Truncation Drops Chapters 3, 4 & 7 (`ai_service.py:552`):** Because `TEXT_PRESERVE_WHITESPACE` pads TOC rows on p.195 (`2,545` chars) and p.196 (`2,497` chars), slicing each page at `[:1400]` cuts off mid-way through Lesson 2-5 and Lesson 6-5, omitting **Chapters 3, 4, Lesson 6-5, and all of Chapter 7** before sending the TOC to the LLM.
4. **[P1 HIGH] Post-`bb3939f` `OMNIROUTE_API_KEY` Short-Circuit vs UI Promises (`ai_service.py:10, 45–54, 149`, `render.yaml`):** Live OmniRoute at `100.120.103.82:20128` is TCP-reachable (`1.79 ms`) and responds HTTP `200` (`888.62 ms`) when `Authorization: Bearer <non-empty>` is sent. However, commit `bb3939f` defaulted `OMNIROUTE_API_KEY=""` (and omitted it from `render.yaml`). When unset, `GET /api/ai/status` returns `{"available": false, "fallbackAvailable": true}` and `call_llm_json` returns `deterministic_fallback` in `0.01 ms`, while **no frontend page calls `/api/ai/status`** and `/presentations`, `/daily-plan`, and `/sources` still report `"تم توليد 6 شرائح ذكية بنجاح عبر (deterministic_fallback)"`.
5. **[P1 HIGH] `deterministic_fallback` Quality & Missing Scanned-Page Viewer:** On the 196-page textbook, fallback structure extraction skips the TOC completely and creates 1 bogus chapter + 10 junk lessons (`"تنقيح"`, `"10 5"`, `"10ُ"`), while `main.py:2322–2338` rewrites `"تنقيح"` to PDF page 6; fallback daily plan ignores `source_excerpt` completely; fallback Slide 3 displays only `"[صفحة 4]"` (or binary garbage on scans); and `/sources` has **no HTTP image endpoint** wrapping `render_pdf_page_to_png_bytes` so teachers cannot view scanned pages while typing manual OCR corrections.

---

## 4. Backend API, Audit Engine, Subject Tools, Backup v2 & Security Audit

### 4.1 Test Suite & 36-Route Coverage
- **Pytest Re-run (`.venv\Scripts\python.exe -m pytest backend/tests/ -v`):** **31 passed, 3 warnings in 1.51s** (`exit code 0`). All **36 / 36** HTTP routes in `backend/app/main.py` were exercised cleanly.

### 4.2 Audit Engine Bypasses & Logic Bugs (`backend/app/services/audit_service.py`, `main.py`)
1. **[P0 CRITICAL — UI vs Audit Divergence] `five_day` & `weekly` Plans Approve With Blank Per-Day Assessments or `0` Minutes:**
   - On `/five-day-plan`, when a teaching day has a lesson but blank `assessment`, the UI renders red `تقويم ناقص` and `"⛔ قبل اكتمال الخطة: أضف تقويم الأيام الناقصة"`.
   - Yet `audit_plan_and_context` (`audit_service.py:429–530`) only checks `INCOMPLETE_FIVE_DAY_COUNT`, `UNSCHEDULED_TEACHING_DAYS`, and `NEGATIVE_SCHEDULE_DURATION` for `five_day` — it **never checks per-day `assessment` or `minutes == 0`** in either `five_day` or `weekly`, and never checks teaching-day count/all-holidays in `weekly`. Both incomplete `five_day` (4/5 days missing assessment) and `weekly` plans (only 2 teaching days, `0` min, blank assessments, or 100% holidays) return `blockersCount: 0` (`status: "reviewed"`) and succeed on `POST /api/plans/{id}/approve` (`200 OK`, `status: "approved"`).
2. **[P1 HIGH — Post-Restore Crash] `GET /api/exports/{id}/download` Returns `500` After Backup v2 Restore:**
   - `_restore_version_two` (`migration_and_backup.py:147–153`) clears `ExportTask.file_path = ""` and sets `artifactAvailable: False`. Calling `GET /api/exports/{id}/download` afterward (`main.py:1996–2012`) runs `_build_export_bytes(...)` and then crashes with **`500 INTERNAL_SERVER_ERROR`** when attempting `open(task.file_path, "wb")` on `""`! (By contrast, deleting the file on disk without a restore self-heals cleanly with `200 OK`.)
3. **[P2 MEDIUM] `copy-to-context` Triggers `TIME_DISTRIBUTION_MISMATCH` (`main.py:1466–1535`):** Copying a 45-min plan into a context with `default_period_Minutes: 50` updates `period_minutes=50` / `total_allocated_minutes=50` while copying 45-min `phases` unchanged, creating a broken `needs_revision` plan.
4. **Subject Tools & Remaining API Notes:**
   - All 5 tools (`math_solver`, `text_analysis`, `historical_timeline`, `science_experiment`, `worksheet_generator`) passed 23 test cases accurately; unknown `toolType` silently falls through to `worksheet_generator` (`audit_service.py:295`).
   - Verified `update_source_metadata` (`main.py:683–758`) copies verified `book_year`/`edition`/`curriculum_name` into empty context fields and re-audits unapproved linked plans, leaving already-`approved` plans untouched.
   - Verified `0` `DELETE` endpoints exist across the entire API (`405` on `/contexts/{id}`, `/plans/{id}`, `/sources/{id}`, `/lessons/{id}`; `404` on `/chapters/{id}`, `/templates/{id}`, `/exports/{id}`), and `GET /api/chapters`, `PUT /api/chapters/{id}`, `PUT /api/templates/{id}` do not exist.

### 4.3 Security & Deployment Gate Findings
- **`PILOT_ACCESS_PIN` Fail-Closed Behavior (`main.py:138–157`, `render.yaml:33–34`, `scripts/start_prod.sh`):** Setting a non-empty `PILOT_ACCESS_PIN` enforces header `X-Pilot-Pin` via `hmac.compare_digest` on all `/api/*` routes except minimal `GET /api/health` (`{"status": "ok"}`), disables `/docs`, `/redoc`, `/openapi.json` (`404`), and blocks `?pin=` query bypass attempts (`401`). However, when `PILOT_ACCESS_PIN` is empty/unset, **every `/api/*` endpoint except `/api/health` returns `503 PILOT_PIN_NOT_CONFIGURED`**, causing `scripts/start_prod.sh` (or Render if unsynced `PILOT_ACCESS_PIN` is left blank) to report healthy `/api/health` (`200`) while locking out the entire application!
- **Read-Side `X-Active-Context-Id` Asymmetry:** All 20 mutating endpoints enforce `verify_active_context_guard` (`409` on mismatch, though omitted header `None` still passes), while all 10 tested `GET` routes ignore mismatched `X-Active-Context-Id` headers and return `200 OK` whenever query `contextId` matches.

---

## 5. 13-Screen Frontend & Live Browser Journey Audit

Verified live using Node CDP against Next.js `next start` (`127.0.0.1:3011`) + FastAPI (`127.0.0.1:8000`, `PILOT_ACCESS_PIN=1234`) across all 13 routes at `1440x900`, `390x844`, and `320x800`:

1. **[P0 CRITICAL — Broken Downloads Under PIN Gate] Fallback Download `<a href>` Links Return `401`:**
   - Commit `bb3939f` switched [`export-package/page.tsx:190,407`](file:///E:/AISHIT/Antigravity_and_Freebuff/MohCollabs/Teacher-Sys/frontend/src/app/export-package/page.tsx#L190) and [`page.tsx:400`](file:///E:/AISHIT/Antigravity_and_Freebuff/MohCollabs/Teacher-Sys/frontend/src/app/page.tsx#L400) to `downloadFile(...)` with `X-Pilot-Pin`, **but missed the banner `lastExportLink` `<a href={lastExportLink.url}>` links in [`daily-plan/page.tsx:578`](file:///E:/AISHIT/Antigravity_and_Freebuff/MohCollabs/Teacher-Sys/frontend/src/app/daily-plan/page.tsx#L578), [`presentations/page.tsx:299`](file:///E:/AISHIT/Antigravity_and_Freebuff/MohCollabs/Teacher-Sys/frontend/src/app/presentations/page.tsx#L299), and [`reports/page.tsx:175`](file:///E:/AISHIT/Antigravity_and_Freebuff/MohCollabs/Teacher-Sys/frontend/src/app/reports/page.tsx#L175)** — clicking them triggers unauthenticated browser navigation and fails with `401 PILOT_PIN_REQUIRED`.
2. **[P1 HIGH — Tooling Regression] `scripts/generate_evidence_and_screenshots.py` Is Broken Under `bb3939f`:**
   - Spawns `uvicorn` without `PILOT_ACCESS_PIN` (`lines 206–211`) and navigates without setting `sessionStorage.agy_pilot_pin`, causing every screenshot to capture the locked `#pilot-access-pin` screen due to `503 PILOT_PIN_NOT_CONFIGURED`.
3. **[P1 HIGH — Stale UI State] Sidebar Remains Stale After Source Verification on `/sources` (`19_sources_verified_stale_sidebar.png`):**
   - [`sources/page.tsx:190–226`](file:///E:/AISHIT/Antigravity_and_Freebuff/MohCollabs/Teacher-Sys/frontend/src/app/sources/page.tsx#L190-L226) (`handleSaveMetadata`) does not call `refreshContexts()` after verification, so `activeContext` in [`AppShell.tsx`](file:///E:/AISHIT/Antigravity_and_Freebuff/MohCollabs/Teacher-Sys/frontend/src/components/AppShell.tsx) keeps showing outdated missing-field warnings and `"بانتظار رفع ملف كتاب المنهج لتوثيقه."` until a full browser reload — and checking `edition && year` rather than `CurriculumSource.verificationStatus` misrepresents sources that omit metadata vs unverified uploaded PDFs.
4. **[P1 HIGH — State Loss] `handleAiGenerateSlides` Overwrites Unsaved Column-3 Settings (`presentations/page.tsx:242`):**
   - Generating AI slides calls `loadPlans(currentPlan.id, 0)` -> `bindPlanSlides(...)`, discarding unsaved changes to `layoutStyle` (`مقارنة`), `presTitle`, and `textDirection`.
5. **[P2 MEDIUM — Concurrency Race] `/tools` `toggleAid` Collides on Rapid Clicks (`tools/page.tsx:92–120`):**
   - No disabled/pending lock during `PUT /api/contexts/{id}` + `refreshContexts()`, so rapid clicks send duplicate `expectedVersion` requests, collide with `409 VERSION_CONFLICT`, and roll back the selection.
6. **[P2 MEDIUM — Build Config] `INTERNAL_API_URL` Baked at Build Time (`frontend/next.config.mjs:12–20`):**
   - Running `next start` with a different runtime `INTERNAL_API_URL` ignores the runtime variable because `rewrites()` bakes `http://127.0.0.1:8000` into `.next/routes-manifest.json` during `npm run build` (switching to a Next.js App Router Route Handler proxy solves runtime URL overrides cleanly).
7. **[P2 MEDIUM — Localization & Polish]:**
   - Selecting `language: "en"` flips `<html dir="ltr" lang="en">` and translates sidebar links, while all 13 page bodies stay hardcoded Arabic (`20_settings_lang_en_mixed_ltr.png`).
   - `GET /favicon.ico` returns `404` on every load.
   - Literal Markdown backticks render in Arabic prose (`export-package/page.tsx:360`, `sources/page.tsx:340, 430`), `"أستاذ د. ليلى حسن"` double-title greeting in `page.tsx:96`, and raw `"deterministic_fallback"` identifier surfaced to teachers.
   - Confirmed absent UI features listed in [`PROMISED_FEATURES.md`](file:///E:/AISHIT/Antigravity_and_Freebuff/MohCollabs/Teacher-Sys/PROMISED_FEATURES.md): scanned-PDF image viewer on `/sources`, Admin backup/restore UI (`/api/system/backup`, `/restore`), AI status badge (`/api/ai/status`), copy-plan UI (`/api/plans/{id}/copy-to-context`), dynamic/refreshable suggestions in `/daily-plan`, UI editors for `Lesson.activities`/`questionsAndSolutions`/`keyTermsOrQuotes`, `Plan.teacherRole`/`studentRole`/`referencesNote`, `FiveDayPlan` per-day `objectives`, `dashboard.activityTimeline` (`[]`), notification bell, and delete actions.

---

## 6. Prioritized Actionable Fix List

### P0 — Critical (Fix Before Any Teacher / Pilot Use)
1. **Fix Multi-Page PDF Ghost Headers, Banner Bleed, Math Direction & `ToUnicode` CMap (`backend/app/services/export_service.py:785–841`):**
   - Bundle an open Arabic TTF font (e.g., `NotoNaskhArabic-Regular.ttf` / `Amiri` / system font) inside the repo/Docker image and pass `pymupdf.Archive(...)` + `@font-face` CSS to `pymupdf.Story` so `ToUnicode` CMap extraction/copy-paste is 100% clean across Windows & Linux Docker containers (never rely on MuPDF's built-in OTF `Noto Naskh Arabic` fallback).
   - Replace `border-collapse: collapse;` with `border-collapse: separate; border-spacing: 0;` and style `.banner`/`.badge-warn` without block `div` `background-color` (use CSS table/border styling) so Page 2+ never paints dark-green bars or yellow strips over text.
   - Wrap LTR math equations inside RTL lists with explicit Unicode isolates (`\u2066...\u2069` or `\u202A...\u202C`) instead of `<li dir="ltr">` so `(15 + 9) / 3 = 8` never flips to `8 = 3 / (9 + 15)`.
2. **Preserve All Exported Fields & Fix `45 دقيقة` vs `225 دقيقة` Contradiction (`backend/app/main.py:1057–1084`, `seed_service.py:529–548`, `export_service.py`):**
   - Include `totalAllocatedMinutes`, `homeEnrichmentMinutes`, `referencesNote`, `planningNotes`, `teacherRole`, `studentRole`, and `presentationSettings` in `_save_plan_version_and_review` and `seed_service.py`.
   - Render `planningNotes`, `homeEnrichmentMinutes`, `referencesNote`, per-day `objectives`, PDF phase `objective`, and clean non-math `subjectItems` formatting in `export_service.py`.
3. **Prevent Scanned-PDF Binary Garbage & False `"extracted_text"` Upgrades (`backend/app/services/pdf_service.py:83–105, 198–205`, `ai_service.py:510`, `main.py:2222–2228`):**
   - Never apply `_extract_text_from_pdf_stream` regexes to non-text PDF streams (`/Subtype /Image`, binary XObjects); filter extracted fallback text for printable language characters. Raise `ValueError` when `fitz.open` fails to parse a corrupt `%PDF-` body.
   - When Vision OCR falls back offline without real extracted text, return an explicit fallback/unextracted flag instead of writing an error string into `extracted_text` and flipping `CurriculumSource.extraction_status` to `"extracted_text"`.
4. **Fix Post-Restore Export Download Crash (`backend/app/main.py:1996–2012`):**
   - When `task.file_path` is empty (`""`) after Backup v2 restore, assign a valid canonical target path inside `EXPORTS_DIR` before regenerating & writing bytes, and update `task.file_path`, `file_size`, and `structural_check_details["artifactAvailable"] = True`.
5. **Close `weekly` & `five_day` Audit Approval Bypasses (`backend/app/services/audit_service.py:429–530`):**
   - Align `audit_plan_and_context` with `/five-day-plan` and `/weekly-plan`: block approval when any non-holiday day lacks `lessonTitle` or `assessment`, or has `minutes <= 0`, or when a `weekly` plan has `0` active teaching days.
6. **Fix Authenticated Fallback Download Links (`frontend/src/app/daily-plan/page.tsx:578`, `presentations/page.tsx:299`, `reports/page.tsx:175`):**
   - Replace plain `<a href={lastExportLink.url}>` with `<button onClick={() => downloadFile(lastExportLink.url, lastExportLink.fileName)}>`.

### P1 — High Priority
7. **Fix `[:1400]` TOC Truncation & AI Connectivity Handling (`backend/app/services/ai_service.py:552`, `render.yaml`, `sources/page.tsx`):**
   - Strip redundant whitespace from PDF text before AI prompting and give detected TOC/index pages (`195–196`) sufficient budget (e.g., `4,000–6,000` chars) so Chapters 3, 4 & 7 aren't clipped.
   - Support keyless local/Tailscale OmniRoute or add `OMNIROUTE_API_KEY` (`sync: false`) to `render.yaml` + check `/api/ai/status` in frontend so fallback runs are clearly badged `"مسودة قوالب دون ذكاء اصطناعي حي"` rather than pretending NVIDIA NIM ran.
   - Add `GET /api/sources/{source_id}/pages/{page_id}/image` (using `render_pdf_page_to_png_bytes`) and render page thumbnails on `/sources` so teachers can read scanned pages while correcting OCR text.
8. **Regenerate Committed `docs/evidence/sample_exports/` & Fix Evidence Script (`scripts/generate_evidence_and_screenshots.py`):**
   - Pass/configure `PILOT_ACCESS_PIN` + inject `sessionStorage.agy_pilot_pin` in `generate_evidence_and_screenshots.py`, regenerate all `sample_exports/*` PDFs/ZIP cleanly after fixing `export_service.py`, and re-sync `export_verification_report.json`.
9. **Fix Live Frontend State Sync Bugs (`sources/page.tsx:190–226`, `presentations/page.tsx:225–251`):**
   - Call `await refreshContexts()` inside `handleSaveMetadata` on `/sources` and check actual source verification status in the sidebar card.
   - Preserve unsaved `presTitle` / `textDirection` / `layoutStyle` edits across `handleAiGenerateSlides` in `/presentations`.
10. **Decide Local/Startup Behavior for Unset `PILOT_ACCESS_PIN` (`scripts/start_prod.sh`, `render.yaml`):**
    - Add a clear startup check/warning in `scripts/start_prod.sh` / local docs when `PILOT_ACCESS_PIN` is empty so operators understand `/api/health` (`200`) will mask a locked-out `503` API unless the Render secret is populated.

### P2 — Medium Priority
11. **Normalize Adobe InDesign Arabic Lam-Alef Ligatures & Improve Math/Printed-Page Detection (`pdf_service.py`):** Repair CMap-reversed `ال`/`أل`/`إل`/`آل` inside Arabic tokens (`المشكالت` -> `المشكلات`, etc.), refine `ocrAmbiguities` regexes to ignore `1-1` chapter-lesson codes while catching `×`/`=`/`÷`/`\u2212`, and handle trailing Arabic diacritics in `_detect_printed_page_number`.
12. **Fix Remaining DOCX `<w:tblGrid>`, PPTX `comparison` LTR/Overflow & Bundle Filenames (`export_service.py`, `main.py`):** Add `<w:tblGrid>`/`<w:tcW>`, preserve 2-column layout across `(تابع)` slides and flip LTR `comparison` coordinates, remove phase 3 overlap, include holidays in weekly slides, use plan-type-aware bundle filenames, and scale `phases` minutes when `copy-to-context` changes `periodMinutes`.
13. **Harden Read-Side Context Guard, UI Race/Localization & Polish:** Add `verify_active_context_guard` to `GET` endpoints (when header is supplied), add `savingAid` lock in `/tools`, replace `next.config.mjs` build-time rewrite with a runtime API route proxy, add `favicon.ico`, strip literal Markdown backticks from UI copy, add tests inspecting exported PDF `get_text("text")` & `ToUnicode` validity + page-2 fills, and add UI controls for remaining schema/backend features (`copy-to-context`, backup/restore, `teacherRole`/`studentRole`/`referencesNote`, 5-day `objectives`, delete endpoints).

### P3 — Batch 6 Roadmap (Deferred Architectural Work)
- Teacher registration/login (`username`/`password` + JWT/Session) + per-teacher PostgreSQL `owner_id` tenant isolation (`models.py:35`), plus official ministry letterhead/timetable PDF templates.
