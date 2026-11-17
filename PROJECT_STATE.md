# حالة المشروع (PROJECT_STATE)

- **آخر تحديث:** 2026-11-17
- **الحالة العامة:**
  - اكتملت الدفعات **0–5.5**، وتليها معالجة محلية للأمان والوصول المشترك، والنسخ الاحتياطي العلائقي، والتحقق من المصادر، والواجهة. **حالة الإطلاق التجريبي: محجوب/غير متحقق** حتى اختبار PostgreSQL والتحقق من إعداد Render والخدمة المنشورة؛ لا تعتبر نتائج الإطلاق السابقة إثباتًا للحالة الحالية. التفاصيل في [`docs/PILOT_TEST_REPORT.md`](docs/PILOT_TEST_REPORT.md).
- **حالة الاختبارات والتحقق (المثبتة محليًا في 2026-11-17):**
  - **أحدث معالجة محلية:** اختبارات الخلفية (`pytest backend/tests -q`): **31/31 ناجحًا في 1.70s** (3 تحذيرات إهمال) باستخدام SQLite مؤقتة ومعزولة.
  - فحص TypeScript (`tsc --noEmit`): **ناجح**.
  - بناء الإنتاج (`npm run build`): **نجح**، وولّد 15 صفحة ومسارات التطبيق الـ13.
  - فحوص النشر على PostgreSQL وRender، ورحلات المتصفح، وتدوير الاعتماد المكشوف تاريخيًا **لم تُنفذ/لم تُتحقق**. سجل الأدلة: [`docs/evidence/local-remediation-checks-2026-11-17.json`](docs/evidence/local-remediation-checks-2026-11-17.json).
  - **الدفعة 5 — مرحلة سابقة مكتملة (`handoff/verification_test_output.log`):**
    - اختبارات الخلفية والتدقيق واستخراج PDF العربي والذكاء الاصطناعي (`pytest backend/tests/ -v`): **21/21 اختبارًا ناجحًا (`21 passed in 1.34s`)**.
    - التحقق الحي عبر **OmniRoute / NVIDIA NIM**: نجاح توليد 5 شرائح عربية حية عبر `nv-nemotron-3-5-bolt-e4b`، ونجاح استخراج النص العربي والكسور عبر Vision OCR (`nv-nemotron-3-nano-omni-30b`) من صفحة PDF محوّلة إلى PNG عبر `PyMuPDF`.
    - بناء الواجهة الإنتاجي المستقل (`NODE_OPTIONS=--max-old-space-size=400 npm run build` في `frontend/`): **15/15 مسار Next.js مبني بنجاح** مع توليد `frontend/.next/standalone/server.js`.
  - **الدفعة 4 — الإطلاق السحابي وPostgreSQL (`handoff/verification_test_output.log`):**
    - محاكاة الإنتاج الموحّد: فحص `/api/health`، تفعيل التهيئة التلقائية (`ENABLE_DEMO_SEED=1`) بسياقين تجريبيين و4 خطط، التحقق من `PRAGMA journal_mode=WAL` في SQLite المحلي، والتحقق من `/api/system/backup`، وعمل بروكسي Next.js Standalone إلى FastAPI (`/`, `/api/health`, `/api/contexts`) ونجاح الفحص البنيوي لملفات التصدير (`.docx`, `.pdf`, `.pptx`, `.zip`).
  - **الدفعة 3 — التحقق البصري والمستندات المصدّرة (2026-10-31):**
    - تدقيق التجاوب وأبعاد الـ Viewport (`docs/evidence/viewport_audit_report.json`): **34/34 لقطة شاشة بدون أي فيضان أفقي (`hasHorizontalOverflow: false`) عبر المقاسات `1440x900` و`768x1024` و`390x844` و`320x800`**.
    - التحقق البنيوي من المستندات الحقيقية (`docs/evidence/export_verification_report.json`): **5/5 مستندات حقيقية قابلة للفتح والتحرير (`.docx`, `.pdf`, `.pptx`, `report_pdf`, `.zip`)**.

---

## 1. ملخص ما تم إنجازه (الدفعات 0 إلى 4)

### الدفعة 0: قراءة المشروع القائم وتحليل الصور المرجعية الـ 13 (2026-10-31)
- فحص الصور المرجعية الـ 13 في مساحة العمل (`مراجعة الخطة.png` بوصفها المرجع الرئيسي عند التعارض، و`photo_2026-10-31_15-58-11.jpg` مرجع دورة التعلّم الخماسية والحصتين، وبقية صور الشاشات).
- توثيق الألوان والخطوط والمسافات وحل التعارض بين الصور في `docs/VISUAL_COMPARISON_AND_DESIGN_DECISIONS.md`.

### الدفعة 1: خلفية Python FastAPI وقاعدة البيانات ومحرك التدقيق وتوليد المستندات (2026-10-31)
- بناء النماذج العلائقية الـ 10 في `backend/app/models.py` و`backend/app/database.py` لدعم SQLite محليًا وPostgreSQL إنتاجيًا.
- تنفيذ عزل السياقات السبعة `{subject, grade, country, curriculumName, language, year, edition}` عبر `contextId` وحارس `X-Active-Context-Id` لمنع الكتابة المتأخرة أو الربط العابر للسياقات.
- بناء محرك التدقيق التخصصي والرياضي (`backend/app/services/audit_service.py`) الذي يفصل صراحةً بين عوائق الاعتماد (`BLOCKER`) وتحذيرات المصادر (`SOURCE_WARNING`) وفحوص الاكتمال الناجحة (`PASSED`).
- بناء خدمة استيراد وفحص PDF (`backend/app/services/pdf_service.py`) ومحرك توليد المستندات الحقيقية (`backend/app/services/export_service.py`) لملفات DOCX وPPTX وPDF وحزمة التصدير الشاملة (ZIP).

### الدفعة 2: تطبيق الواجهة React / Next.js والشاشات الاثنتا عشرة (2026-10-31 / 2026-11-02)
- تنفيذ جميع المسارات الـ 12 المطلوبة + مسار تصدير الحزمة الشاملة في `frontend/src/app/` مع `frontend/src/components/AppShell.tsx` و`frontend/src/app/globals.css`:
  1. `/` — لوحة المعلم (Dashboard)
  2. `/curriculum` — المنهج (Curriculum)
  3. `/lessons` — اختيار الدرس وإدارته (Lessons)
  4. `/tools` — الوسائل التعليمية وأدوات المدرس التخصصية (Teacher Tools)
  5. `/settings` — إعداد الخطة والسياق (Settings & Context)
  6. `/daily-plan` — الخطة اليومية لدرس أو درسين وحصة أو حصتين (Daily Plan)
  7. `/weekly-plan` — الخطة الأسبوعية الفعلية مع العطل والربط بالخطط اليومية (Weekly Plan)
  8. `/five-day-plan` — خطة خمسة أيام تدريسية متميزة (Five-Day Plan)
  9. `/review` — مراجعة الخطة النهائية وبوابة الاعتماد (Final Plan Review)
  10. `/reports` — التقارير الفعلية بدون نسب نجاح طلاب مفترضة (Reports)
  11. `/presentations` — العروض التقديمية القابلة للتحرير (Presentations)
  12. `/sources` — استيراد كتاب المنهج والتحقق البشري (Sources & PDF Verification)
  13. `/export-package` — تصدير الحزمة الشاملة (Export Package)
- إضافة دعم البدء النظيف الاختياري (`ENABLE_DEMO_SEED`) والوصول عبر الشبكة المحلية (LAN CORS regex) في التحديث `cd0e87e` بتاريخ 2026-11-02.

### الدفعة 3: التدقيق المستقل، التحقق البصري بـ 4 مقاسات، وحزمة النشر (2026-10-31)
- توليد وفحص عينات المستندات الحقيقية في `docs/evidence/sample_exports/` وتوثيق بصماتها في `docs/evidence/export_verification_report.json`.
- التقاط 34 لقطة شاشة عبر بروتوكول Chrome DevTools في `docs/evidence/screenshots/` وتوثيق أبعاد الـ Viewport في `docs/evidence/viewport_audit_report.json`.
- إعداد دليل التشغيل والنشر والنسخ الاحتياطي في `docs/DEPLOYMENT.md` وسجل التدقيق المستقل في `docs/SECURITY_AND_QA_AUDIT.md`.

### الدفعة 4: الإطلاق الإنتاجي السحابي على Render Free Tier + PostgreSQL الدائمة (`teachersys.onrender.com`) (2026-11-16)
- **توحيد الخلفية والواجهة في حاوية Docker واحدة:** تشغيل FastAPI (`127.0.0.1:8000`) وخادم Next.js Standalone (`0.0.0.0:$PORT`) معًا عبر [`Dockerfile`](Dockerfile) و[`scripts/start_prod.sh`](scripts/start_prod.sh) وتفعيل `output: "standalone"` وبروكسي `/api/*` في [`frontend/next.config.mjs`](frontend/next.config.mjs) لتفادي أخطاء مهلة الإقلاع البارد بين خدمات منفصلة.
- **ربط Render PostgreSQL الدائمة (`teacher-system2-db`):** إعداد [`render.yaml`](render.yaml) بخدمة الويب `teachersys` وقاعدة البيانات المجانية `teacher-system2-db` وتمرير `DATABASE_URL` تلقائيًا، مع تطبيع روابط `postgres://` و`postgresql://` إلى `postgresql+psycopg2://` عبر `normalize_database_url()` في [`backend/app/database.py`](backend/app/database.py) مع بقاء دعم **SQLite WAL** (`busy_timeout=5000`) للتشغيل المحلي.
- **التهيئة التلقائية والأمان التجريبي والنسخ الاحتياطي والتعافي الذاتي للتصدير:**
  - تفعيل التهيئة التلقائية للبيانات التجريبية عند الإقلاع (`ENABLE_DEMO_SEED=1`) في [`backend/app/main.py`](backend/app/main.py).
  - إضافة حارس الوصول الاختياري `PILOT_ACCESS_PIN` عبر ترويسة `X-Pilot-Pin` لحماية طلبات التعديل (`POST`/`PUT`/`PATCH`/`DELETE`) على `/api/*`.
  - توفير نقاط النسخ الاحتياطي والاستعادة `GET /api/system/backup` و`POST /api/system/restore` عبر [`backend/app/services/migration_and_backup.py`](backend/app/services/migration_and_backup.py).
  - تفعيل إعادة توليد ملفات التصدير ذاتيًا عبر `/api/exports/{export_id}/download` (`_build_export_bytes()`) من لقطات قاعدة البيانات عند إعادة تشغيل القرص المؤقت للحاوية.
- **بنية التسليم (`handoff/`):** إنشاء مجلد `handoff/` ([`GO_LIVE_PLAN.md`](handoff/GO_LIVE_PLAN.md)، [`EXECUTION_LOG.md`](handoff/EXECUTION_LOG.md)، [`verification_test_output.log`](handoff/verification_test_output.log)) لتنسيق التسليم والإطلاق بين **Antigravity** و**Kilo Code** وتحديث [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).
- **نتائج التحقق المعتمدة للدفعة 4:** **19/19 اختبار `pytest` ناجح** + **15/15 مسار Next.js مبني بنجاح** + التحقق من عمل البروكسي والتصدير والنسخ الاحتياطي في محاكاة الإنتاج.

---

## 2. أحدث ما تم إنجازه — الدفعة 5 (مكتملة ومُتحقق منها 2026-11-17)

### الدفعة 5: الاستخراج الحقيقي لملفات PDF العربية وتوليد الشرائح والخطط عبر OmniRoute / NVIDIA NIM
- **ترقية استخراج ملفات PDF العربية:** ترقية [`backend/app/services/pdf_service.py`](backend/app/services/pdf_service.py) باستخدام مكتبة **PyMuPDF (`pymupdf>=1.25.0,<2.0`)** مع تطبيع Unicode (`NFKC`) لاستخراج النصوص العربية الحقيقية، وكشف أرقام الصفحات المطبوعة، وتحويل الصفحات الممسوحة ضوئيًا إلى صور PNG (`render_pdf_page_to_png_bytes`) مع إضافتها إلى [`Dockerfile`](Dockerfile) و[`requirements.txt`](requirements.txt).
- **محرك الذكاء الاصطناعي السريع (`backend/app/services/ai_service.py`):** إضافة خدمة الذكاء الاصطناعي المتصلة عبر **OmniRoute / Tailscale** (`OMNIROUTE_BASE_URL`) أو مباشرة بـ **NVIDIA NIM** (`NVIDIA_API_KEYS`) باستخدام نماذج NVIDIA السريعة:
  - `nv-nemotron-3-5-bolt-e4b` (وسلسلة `nv-nemotron-3-5-super-vl-120b` / `nv-nemotron-3-nano-omni-30b`) لتوليد النصوص والخطط والشرائح مع توازن تلقائي لزمن الحصة يضمن صفر عوائق تدقيق.
  - `nv-nemotron-3-5-super-vl-120b` و`nv-nemotron-3-nano-omni-30b` للرؤية الذكية واستخراج النصوص (Vision OCR).
- **نقاط النهاية الجديدة في الخلفية (`backend/app/main.py` & `schemas.py`):** `GET /api/ai/status`، `POST /api/plans/{id}/ai-generate-slides`، `POST /api/plans/{id}/ai-generate-plan`، `POST /api/sources/{id}/pages/{page_id}/ai-ocr`، و`POST /api/sources/{id}/ai-extract-structure`.
- **تحديث شاشات الواجهة لتوليد المحتوى بالذكاء الاصطناعي:**
  - `/presentations`: بطاقة توليد الشرائح الذكي مع تحديد عدد الشرائح والتوجيهات المخصصة.
  - `/sources`: أزرار استخراج النص بالرؤية الذكية (Vision OCR) وبناء الفصول والدروس تلقائيًا من الكتاب المنهجي.
  - `/daily-plan`: شريط صياغة الخطة والأنشطة اليومية بالذكاء الاصطناعي (NVIDIA NIM).
- **نتائج التحقق المعتمدة للدفعة 5:** **21/21 اختبار `pytest` ناجح في 1.34s** + **15/15 مسار Next.js Standalone مبني بنجاح** + تحقق حي مباشر مع OmniRoute لتوليد الشرائح والرؤية الذكية OCR.

### معالجة التحقق المحلي والأمان (2026-11-17; تتجاوز سجل Batch 5.5 أعلاه):
- إضافة حارس PIN مشترك مطلوب لجميع `/api/*` عدا `/api/health`، مع تعطيل OpenAPI/docs، وتعطيل CORS LAN regex افتراضيًا، وجعل `ENABLE_DEMO_SEED=0` وإزالة الاعتماد المضمّن من الشيفرة/إعداد Render. هذا الحارس ليس حسابات مستخدمين أو عزل مستأجرين.
- إضافة نسخ احتياطي/استعادة JSON v2 لعشر مجموعات علائقية مع upsert غير هدّام، واستمرار دعم استعادة v1؛ ملفات PDF والتصدير الثنائية غير مضمنة.
- إصلاح حفظ بيانات تحقق المصدر في حقول السياق الفعلية وإعادة تدقيق الخطط المرتبطة، والبحث غير الحساس لحالة الأحرف، وإخفاء بيانات إعداد AI، وتمرير PIN لتنزيلات الواجهة.
- **نتائج التحقق المحلي الأحدث:** 31/31 اختبار خلفية ناجح على SQLite مؤقتة (3 تحذيرات إهمال)، فحص TypeScript ناجح، وبناء Next.js ناجح مع 15 صفحة. لا يثبت ذلك توافق PostgreSQL أو النشر أو سلوك المتصفح.
- **بوابة الإطلاق التجريبي:** محجوب/غير متحقق حتى اختبار PostgreSQL معزول والتحقق من إعداد Render وPIN والخدمة المنشورة، ومعالجة تدوير الاعتماد المكشوف تاريخيًا والتخزين الدائم. راجع [`docs/PILOT_TEST_REPORT.md`](docs/PILOT_TEST_REPORT.md).

### تدقيق جاهزية المعلم والإصلاحات الشاملة (Batch 5.5 — 2026-11-17; سجل تاريخي):
- **تغطية التدقيق متعدد الوكلاء (`docs/TEACHER_READINESS_AUDIT.md`):**
  - تدقيق الخلفية والتصدير ومحرك الذكاء الاصطناعي (`pytest`, 30+ نقطة API، 5 أدوات تخصصية، 6 صيغ تصدير، OmniRoute الحي).
  - تدقيق الإنتاج الحي على Render (`https://teachersys.onrender.com` على `7bd209a`).
  - تدقيق جميع شاشات الواجهة الأمامية الـ 13 وسير عمل المعلم الفعلي.
- **الإصلاحات المنفذة:**
  - تصدير PDF عربي فعلي عبر `pymupdf.Story` + `subset_fonts()` بدون تشويه WinAnsi، وإصلاح شرائح المقارنة واستمرارية `(تابع)` في PPTX وتقارير `report_docx`.
  - تقوية `_extract_json_from_text` و `_normalize_phases_minutes` و `_sanitize_slides` في `ai_service.py`، ورفع حد `PyMuPDF` إلى `MAX_PDF_PAGES` (`600`) مع `NFKC`.
  - دعم الأرقام الهندية `٠-٩` والكسور وتاريخ `ق.م` وقيود 5 أيام في `audit_service.py`، وعزل السياقات وتوسيع النسخ الاحتياطي FK-ordered في `main.py` و `migration_and_backup.py`.
  - إصلاحات الواجهة عبر جميع الـ 13 مسارًا (`NAV_ITEMS` مع `/sources`, `Suspense`, عزل السياق، حفظ النماذج، وأخطاء `blocker-banner`).
- **نتائج التحقق النهائية المعتمدة:** **26/26 اختبار `pytest` ناجح في 1.79s** + **`npx tsc --noEmit` (`exit 0`)** + **15/15 مسار Next.js مبني بنجاح (`exit 0`)**.

---

## 3. المرحلة القادمة المخططة — الدفعة 6

- **حسابات المعلمين وعزل المساحات:** بناء نظام حسابات المعلمين وتسجيل الدخول (`username/password` + JWT/Session) وعزل مساحة وبيانات كل معلم عبر `owner_id` في قاعدة بيانات PostgreSQL.
- **ربط الذكاء الاصطناعي في الإنتاج:** ربط OmniRoute عبر Tailscale Funnel أو تهيئة متغيرات `NVIDIA_API_KEYS` في بيئة الإنتاج على Render.
- **التنسيق البصري المتقدم للطباعة:** تحسين التنسيق البصري المتقدم لملفات PDF المصدّرة (جداول مدرسية منسقة ومطبوعات رسمية).
