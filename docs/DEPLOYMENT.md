# توثيق النشر والإنتاج وخدمة Python المستقلة (DEPLOYMENT)

يوثّق هذا المستند بنية تشغيل ونشر **مساعد المدرس لأي مادة ومنهج وسياق تعليمي** وفق المتطلبات المعمارية في البند 10 من المواصفة.

---

## 1. حقيقة الاستضافة وفصل الواجهة عن خدمة Python

- **الواجهة الأمامية (`frontend/`)**: مبنية بـ React 19 وNext.js 16، وتدعم العمل على خادم Node أو عبر بنية Sites/Vinext. تتصل بخدمة الخلفية عبر العنوان المحدد في `NEXT_PUBLIC_API_BASE_URL` مع إعادة توجيه `/api/*` وتمرير ترويسة `X-Active-Context-Id` لعزل السياقات.
- **خلفية Python (`backend/`)**: مبنية بـ **FastAPI** وتعمل عبر خادم ASGI (**Uvicorn**). لا تعمل داخل JavaScript Worker الخاص بـ Sites، بل تُنشر في خدمة Python مستقلة متصلة بقاعدة بيانات **PostgreSQL** دائمة للإنتاج (و**SQLite** للتطوير المحلي) مع تخزين ملفات دائم في `backend/storage/`.

---

## 2. متغيرات البيئة المطلوبة (دون كشف أسرار)

| المتغير | الوصف | القيمة الافتراضية محليًا | مثال للإنتاج |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | رابط قاعدة البيانات (SQLAlchemy) | `sqlite:///./teacher_system.db` | `postgresql+psycopg2://user:<SECRET>@db-host:5432/teacher_prod` |
| `ALLOWED_ORIGINS` | قائمة أصول CORS المسموحة مفصولة بفواصل | `http://localhost:3000,http://127.0.0.1:3000` | `https://teacher-ui.example.com` |
| `NEXT_PUBLIC_API_BASE_URL` | عنوان خدمة FastAPI للواجهة | `http://127.0.0.1:8000` | `https://teacher-api.example.com` |

> **تنبيه أمني:** لا يُوضع أي مفتاح خدمة سري أو `DATABASE_URL` داخل متغيرات `NEXT_PUBLIC_*` أو في حزمة المتصفح (frontend bundle).

---

## 3. أوامر التشغيل المقفلة وفحص الجاهزية

### أ. تشغيل الخلفية (Python FastAPI ASGI)
```powershell
# 1. تفعيل البيئة المعزولة وتثبيت الحزم المقفلة
.\.venv\Scripts\pip.exe install -r requirements.txt

# 2. تشغيل خدمة FastAPI عبر Uvicorn
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

### ب. فحص الجاهزية وقاعدة البيانات (Readiness & Health Check)
```powershell
curl http://127.0.0.1:8000/api/health
# يعيد: {"status": "ok", "service": "teacher-system-fastapi", "databaseConnected": true, "databaseDialect": "postgresql|sqlite"}
```

### ج. تشغيل الواجهة الأمامية (Next.js)
```powershell
cd frontend
npm run build
npm run start
```

---

## 4. الترحيلات والنسخ الاحتياطي والاستعادة (Migrations & Backup/Restore)

- **توليد وفحص ترحيلات PostgreSQL وSQLite:**
  يوفّر الملف [`backend/app/services/migration_and_backup.py`](../backend/app/services/migration_and_backup.py) دالة `generate_postgresql_and_sqlite_ddl()` التي تصدّر DDL الكامل المتوافق مع PostgreSQL (`TIMESTAMP WITH TIME ZONE`، `FOREIGN KEY ... ON DELETE CASCADE`، `JSON`) وSQLite، ويتم اختبارها آليًا في [`backend/tests/test_migrations_and_backup.py`](../backend/tests/test_migrations_and_backup.py).
- **النسخ الاحتياطي والاستعادة (Backup & Restore):**
  - عبر الكود: استدعاء `create_database_backup_json("backups/backup_YYYYMMDD.json")` يحفظ نسخة JSON كاملة لجميع السياقات والخطط والإصدارات والمصادر.
  - عبر واجهة API المباشرة أثناء التشغيل:
    - تنزيل نسخة احتياطية فورية: `GET /api/system/backup`
    - استعادة نسخة احتياطية: `POST /api/system/restore` (يحفظ السياقات ويعيد بناءها فورًا).

---

## 5. النشر المجاني الموحّد على Render (Render Free Tier Blueprint)

لتفادي أخطاء مهلة التشغيل البارد (502 Cold-Start) بين خدمتين مجانيتين منفصلتين والبقاء ضمن سقف **512 MB RAM** في خطة Render المجانية:
1. يجمع ملف [`Dockerfile`](../Dockerfile) كلًّا من **FastAPI (`127.0.0.1:8000`)** و**Next.js Standalone (`0.0.0.0:$PORT`)** في حاوية واحدة عبر [`scripts/start_prod.sh`](../scripts/start_prod.sh).
2. يتم تفعيل وضع **SQLite WAL** مع `busy_timeout=5000` تلقائيًا في [`backend/app/database.py`](../backend/app/database.py) وتفعيل البيانات التجريبية التلقائية عند التشغيل الأول (`ENABLE_DEMO_SEED=1`).
3. خطوات الإطلاق في 3 نقرات:
   1. ادفع التحديثات إلى فرع `main` على GitHub.
   2. افتح **Render Dashboard → Blueprints → New Blueprint Instance** واختر مستودع `mahdiking999/teacher-system2` (سيقرأ ملف [`render.yaml`](../render.yaml) تلقائيًا).
   3. اضغط **Apply** — وبمجرد جاهزية الخدمة، افتح الرابط العام للمعلمين (يمكنك تعيين `PILOT_ACCESS_PIN` في متغيرات البيئة على Render لقفل التعديلات برمز تجريبي أو تركه فارغًا للإتاحة المفتوحة).

---

## 6. حدود بيئة التنفيذ والتطوير المحلي

- تعمل بيئة التنفيذ الحالية داخل وضع معزول شبكيًا (No external cloud credentials or remote hosting tokens configured).
- لذلك تم تجهيز:
  1. خدمة Python FastAPI الكاملة مع اختبارات التكامل والترحيلات.
  2. بناء الإنتاج الكامل للواجهة الأمامية (`frontend/.next`).
  3. ملفات التصدير الحقيقية (`DOCX`, `PDF`, `PPTX`, `ZIP`) ولقطات الشاشة الفعلية في `docs/evidence/`.
- لم يتم اختلاق أي رابط سحابي خارجي؛ جميع الاختبارات وعمليات التحقق البصري أُجريت على الخوادم المحلية الفعلية (`127.0.0.1:8000` و`127.0.0.1:3000`).

