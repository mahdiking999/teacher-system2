import os
import tempfile
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import Base, engine, SessionLocal, normalize_database_url
from backend.app.models import (
    EducationalContext,
    PhaseTemplate,
    CurriculumSource,
    SourcePage,
    Chapter,
    Lesson,
    Plan,
    PlanVersion,
    PlanReview,
    ExportTask,
)
from backend.app.services.migration_and_backup import (
    export_database_backup_dict,
    restore_database_backup_dict,
    generate_postgresql_and_sqlite_ddl,
    create_database_backup_json,
)


def test_postgresql_and_sqlite_ddl_compilation():
    res = generate_postgresql_and_sqlite_ddl()
    assert res["tables_count"] == 10
    assert "CREATE TABLE educational_contexts" in res["postgresql_ddl"]
    assert "FOREIGN KEY(context_id) REFERENCES educational_contexts (id) ON DELETE CASCADE" in res["postgresql_ddl"]
    assert "TIMESTAMP WITH TIME ZONE" in res["postgresql_ddl"]


def test_backup_creation():
    with tempfile.TemporaryDirectory() as tmpdir:
        b_path = os.path.join(tmpdir, "backup_test.json")
        res = create_database_backup_json(b_path)
        assert os.path.isfile(b_path)
        assert res["backupVersion"] == "2.0"


def test_backup_and_restore_roundtrip_api(monkeypatch):
    monkeypatch.setenv("ENABLE_DEMO_SEED", "0")
    monkeypatch.setenv("PILOT_ACCESS_PIN", "2026")
    Base.metadata.create_all(bind=engine)

    created_id = None
    try:
        with TestClient(app, headers={"X-Pilot-Pin": "2026"}) as client:
            create_res = client.post(
                "/api/contexts",
                headers={"X-Pilot-Pin": "2026"},
                json={
                    "subject": "الكيمياء",
                    "grade": "الخامس العلمي",
                    "country": "العراق",
                    "curriculumName": "منهج الكيمياء",
                    "language": "ar",
                    "year": "2026",
                    "edition": "الأولى",
                    "teacherName": "أ. حيدر",
                },
            )
            assert create_res.status_code == 201
            created_id = create_res.json()["id"]

            backup_res = client.get("/api/system/backup", headers={"X-Pilot-Pin": "2026"})
            assert backup_res.status_code == 200
            backup_payload = backup_res.json()
            assert backup_payload["backupVersion"] == "2.0"
            assert any(c["id"] == created_id for c in backup_payload["contexts"])
            assert len(backup_payload["export_tasks"]) == backup_payload["exportTasksCount"]
            for key in ("contexts", "templates", "sources", "source_pages", "chapters", "lessons", "plans", "plan_versions", "plan_reviews", "export_tasks"):
                assert isinstance(backup_payload[key], list)

            # Delete context from DB, modify teacher_name in backup payload, and restore via API
            db = SessionLocal()
            try:
                db.query(EducationalContext).filter(EducationalContext.id == created_id).delete()
                db.commit()
            finally:
                db.close()

            for item in backup_payload["contexts"]:
                if item["id"] == created_id:
                    item["teacher_name"] = "أ. حيدر (مستعاد)"

            restore_res = client.post("/api/system/restore", headers={"X-Pilot-Pin": "2026"}, json=backup_payload)
            assert restore_res.status_code == 200
            assert restore_res.json()["restoredContextsCount"] >= 1

            get_res = client.get(f"/api/contexts/{created_id}", headers={"X-Pilot-Pin": "2026"})
            assert get_res.status_code == 200
            assert get_res.json()["teacherName"] == "أ. حيدر (مستعاد)"
    finally:
        if created_id:
            db = SessionLocal()
            try:
                db.query(EducationalContext).filter(EducationalContext.id == created_id).delete()
                db.commit()
            finally:
                db.close()


def test_backup_v2_rejects_missing_entity_groups():
    try:
        restore_database_backup_dict({"backupVersion": "2.0", "contexts": []})
    except ValueError as exc:
        assert "missing entity groups" in str(exc)
    else:
        raise AssertionError("Incomplete v2 backup must be rejected")


def test_pilot_access_pin_middleware(monkeypatch):
    monkeypatch.setenv("ENABLE_DEMO_SEED", "0")
    monkeypatch.setenv("PILOT_ACCESS_PIN", "2026")
    Base.metadata.create_all(bind=engine)

    created_id = None
    try:
        with TestClient(app, headers={"X-Pilot-Pin": "2026"}) as client:
            health = client.get("/api/health")
            assert health.status_code == 200
            assert health.json() == {"status": "ok"}
            assert client.get("/docs").status_code == 404
            assert client.get("/openapi.json").status_code == 404
            assert client.get("/api/contexts", headers={"X-Pilot-Pin": "9999"}).status_code == 401
            assert client.get("/api/contexts", headers={"X-Pilot-Pin": ""}).status_code == 401
            assert client.get("/api/system/backup", headers={"X-Pilot-Pin": ""}).status_code == 401
            assert client.get("/api/system/backup?pin=2026", headers={"X-Pilot-Pin": ""}).status_code == 401
            assert client.post("/api/system/restore", headers={"X-Pilot-Pin": ""}, json={}).status_code == 401
            assert client.get("/api/contexts", headers={"X-Pilot-Pin": "2026"}).status_code == 200

            no_pin = client.post("/api/contexts", headers={"X-Pilot-Pin": ""}, json={"subject": "الفيزياء", "grade": "الرابع"})
            assert no_pin.status_code == 401
            assert no_pin.json()["code"] == "PILOT_PIN_REQUIRED"

            query_pin = client.post("/api/contexts?pin=2026", headers={"X-Pilot-Pin": ""}, json={"subject": "الفيزياء", "grade": "الرابع"})
            assert query_pin.status_code == 401

            restore_no_pin = client.post("/api/system/restore", headers={"X-Pilot-Pin": "2026"}, json={})
            assert restore_no_pin.status_code == 400

            wrong_pin = client.post(
                "/api/contexts",
                headers={"X-Pilot-Pin": "9999"},
                json={"subject": "الفيزياء", "grade": "الرابع"},
            )
            assert wrong_pin.status_code == 401

            ok_pin = client.post(
                "/api/contexts",
                headers={"X-Pilot-Pin": "2026"},
                json={"subject": "الفيزياء", "grade": "الرابع"},
            )
            assert ok_pin.status_code == 201
            created_id = ok_pin.json()["id"]

            restore_ok = client.post("/api/system/restore", headers={"X-Pilot-Pin": "2026"}, json={"backupVersion": "1.0", "contexts": []})
            assert restore_ok.status_code == 200
    finally:
        if created_id:
            db = SessionLocal()
            try:
                db.query(EducationalContext).filter(EducationalContext.id == created_id).delete()
                db.commit()
            finally:
                db.close()


def test_pilot_access_pin_fails_closed_when_unconfigured(monkeypatch):
    monkeypatch.setenv("ENABLE_DEMO_SEED", "0")
    monkeypatch.setenv("PILOT_ACCESS_PIN", "")

    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        response = client.get("/api/contexts")

    assert response.status_code == 503
    assert response.json()["code"] == "PILOT_PIN_NOT_CONFIGURED"


def test_backup_v2_roundtrip_all_relational_entities_is_idempotent_and_rollback_safe():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    ctx_id = "ctx_backup_v2_test"
    stale_id = "ctx_backup_v2_stale"
    try:
        db.query(EducationalContext).filter(EducationalContext.id == stale_id).delete()
        db.commit()
        source_id = "src_backup_v2_test"
        page_id = "pg_backup_v2_test"
        chapter_id = "ch_backup_v2_test"
        lesson_id = "les_backup_v2_test"
        plan_id = "pln_backup_v2_test"
        export_id = "exp_backup_v2_test"
        db.add(EducationalContext(id=ctx_id, subject="الرياضيات", grade="السابع", teacher_name="أ. اختبار"))
        db.add(EducationalContext(id=stale_id, subject="سياق قديم", grade="الأول", teacher_name="أ. قديم"))
        db.flush()
        db.add(PhaseTemplate(id="tpl_backup_v2_test", context_id=ctx_id, name="قالب اختبار", description="وصف القالب", phases=[{"phaseName": "التمهيد"}]))
        db.add(CurriculumSource(id=source_id, context_id=ctx_id, title="مصدر اختبار", file_path="/not-restored/source.pdf", book_year="2026", edition="الثانية"))
        db.flush()
        db.add(SourcePage(id=page_id, source_id=source_id, pdf_page_number=1, printed_page_number="٣", extracted_text="نص اختباري", corrected_text="نص مصحح", human_reviewed=True))
        db.add(Chapter(id=chapter_id, context_id=ctx_id, source_id=source_id, title="فصل اختباري", order_index=3, printed_start_page="١٠"))
        db.flush()
        db.add(Lesson(id=lesson_id, context_id=ctx_id, source_id=source_id, chapter_id=chapter_id, title="درس اختباري", objectives=["هدف اختبار"], activities=[{"name": "نشاط"}]))
        db.flush()
        db.add(Plan(id=plan_id, context_id=ctx_id, primary_lesson_id=lesson_id, title="خطة اختبار", objectives=["هدف خطة"], formative_assessment="تقويم اختبار"))
        db.flush()
        db.add(PlanVersion(id="pver_backup_v2_test", plan_id=plan_id, context_id=ctx_id, version_number=1, plan_payload={"title": "خطة اختبار", "objectives": ["هدف نسخة"]}, content_sha256="sha-test", reviewer_name="مراجع اختبار"))
        db.add(PlanReview(id="rev_backup_v2_test", plan_id=plan_id, context_id=ctx_id, plan_version=1, overall_status="reviewed", findings=[{"code": "TEST"}], passed_count=1))
        db.add(ExportTask(id=export_id, context_id=ctx_id, plan_id=plan_id, plan_version=1, export_format="docx", file_name="test.docx", file_path="/not-restored/test.docx", file_size=42, content_sha256="export-sha", review_status_snapshot="reviewed", source_verification_snapshot="human_verified", structural_check_passed=True, structural_check_details={"passed": True}))
        db.commit()

        payload = export_database_backup_dict()
        assert payload["backupVersion"] == "2.0"
        assert {key for key in ("contexts", "templates", "sources", "source_pages", "chapters", "lessons", "plans", "plan_versions", "plan_reviews", "export_tasks") if key in payload} == {
            "contexts", "templates", "sources", "source_pages", "chapters", "lessons", "plans", "plan_versions", "plan_reviews", "export_tasks"
        }
        assert next(row for row in payload["sources"] if row["id"] == source_id)["book_year"] == "2026"
        assert next(row for row in payload["source_pages"] if row["id"] == page_id)["corrected_text"] == "نص مصحح"
        assert next(row for row in payload["templates"] if row["id"] == "tpl_backup_v2_test")["phases"] == [{"phaseName": "التمهيد"}]
        assert next(row for row in payload["chapters"] if row["id"] == chapter_id)["order_index"] == 3
        assert next(row for row in payload["lessons"] if row["id"] == lesson_id)["activities"] == [{"name": "نشاط"}]
        assert next(row for row in payload["plans"] if row["id"] == plan_id)["formative_assessment"] == "تقويم اختبار"
        assert next(row for row in payload["plan_versions"] if row["id"] == "pver_backup_v2_test")["content_sha256"] == "sha-test"
        assert next(row for row in payload["plan_reviews"] if row["id"] == "rev_backup_v2_test")["findings"] == [{"code": "TEST"}]
        assert next(row for row in payload["export_tasks"] if row["id"] == export_id)["content_sha256"] == "export-sha"

        db.query(EducationalContext).filter(EducationalContext.id == ctx_id).delete()
        db.commit()

        first = restore_database_backup_dict(payload)
        assert first["backupVersion"] == "2.0"
        assert first["mergeSemantics"]
        assert first["restoredCounts"]["contexts"] >= 2

        second = restore_database_backup_dict(payload)
        assert second["restoredCounts"] == first["restoredCounts"]

        db = SessionLocal()
        try:
            assert db.query(EducationalContext).filter(EducationalContext.id == ctx_id).count() == 1
            assert db.query(EducationalContext).filter(EducationalContext.id == stale_id).count() == 1
            restored_source = db.get(CurriculumSource, source_id)
            assert restored_source.file_path == ""
            assert restored_source.extraction_status == "no_file"
            restored_page = db.get(SourcePage, page_id)
            assert restored_page.extracted_text == "نص اختباري"
            assert restored_page.corrected_text == "نص مصحح"
            assert restored_page.human_reviewed is True
            assert db.get(PhaseTemplate, "tpl_backup_v2_test").phases == [{"phaseName": "التمهيد"}]
            assert db.get(Chapter, chapter_id).order_index == 3
            assert db.get(Lesson, lesson_id).activities == [{"name": "نشاط"}]
            restored_plan = db.get(Plan, plan_id)
            assert restored_plan.objectives == ["هدف خطة"]
            assert restored_plan.formative_assessment == "تقويم اختبار"
            restored_version = db.get(PlanVersion, "pver_backup_v2_test")
            assert restored_version.plan_payload == {"title": "خطة اختبار", "objectives": ["هدف نسخة"]}
            assert restored_version.content_sha256 == "sha-test"
            restored_review = db.get(PlanReview, "rev_backup_v2_test")
            assert restored_review.overall_status == "reviewed"
            assert restored_review.findings == [{"code": "TEST"}]
            restored_export = db.get(ExportTask, export_id)
            assert restored_export.file_path == ""
            assert restored_export.file_size == 0
            assert restored_export.content_sha256 == "export-sha"
            assert restored_export.structural_check_details["artifactAvailable"] is False
        finally:
            db.close()

        invalid = dict(payload)
        invalid["contexts"] = [{"id": "ctx_invalid", "default_periods_count": "not-an-int"}]
        try:
            restore_database_backup_dict(invalid)
        except Exception:
            pass
        else:
            raise AssertionError("Invalid payload should fail and roll back")

        db = SessionLocal()
        try:
            assert db.query(EducationalContext).filter(EducationalContext.id == "ctx_invalid").count() == 0
        finally:
            db.close()
    finally:
        db = SessionLocal()
        try:
            db.query(EducationalContext).filter(EducationalContext.id.in_([ctx_id, stale_id, "ctx_invalid"])).delete(synchronize_session=False)
            db.query(EducationalContext).filter(EducationalContext.id == stale_id).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()


def test_database_url_normalization():
    assert normalize_database_url("postgres://u:p@host:5432/db") == "postgresql+psycopg2://u:p@host:5432/db"
    assert normalize_database_url("postgresql://u:p@host:5432/db") == "postgresql+psycopg2://u:p@host:5432/db"
    assert normalize_database_url("sqlite:///./teacher_system.db") == "sqlite:///./teacher_system.db"


def test_export_download_self_healing_after_disk_reset(monkeypatch):
    monkeypatch.setenv("ENABLE_DEMO_SEED", "0")
    monkeypatch.setenv("PILOT_ACCESS_PIN", "test-pin")
    Base.metadata.create_all(bind=engine)

    created_ctx_id = None
    export_file_path = None
    try:
        with TestClient(app) as client:
            ctx_res = client.post(
                "/api/contexts",
                headers={"X-Pilot-Pin": "test-pin"},
                json={"subject": "الأحياء", "grade": "السادس العلمي", "teacherName": "أ. نور"},
            )
            assert ctx_res.status_code == 201
            created_ctx_id = ctx_res.json()["id"]

            plan_res = client.post(
                "/api/plans",
                headers={"X-Active-Context-Id": created_ctx_id, "X-Pilot-Pin": "test-pin"},
                json={
                    "contextId": created_ctx_id,
                    "title": "خطة التمثيل الضوئي",
                    "planType": "daily",
                    "periodsCount": 1,
                    "periodMinutes": 45,
                    "objectives": ["أن يفسر الطالب معادلة البناء الضوئي."],
                    "formativeAssessment": "سؤال تقويمي ختامي",
                },
            )
            assert plan_res.status_code == 201
            plan_id = plan_res.json()["id"]

            exp_res = client.post(
                "/api/exports",
                headers={"X-Active-Context-Id": created_ctx_id, "X-Pilot-Pin": "test-pin"},
                json={"contextId": created_ctx_id, "planId": plan_id, "exportFormat": "docx"},
            )
            assert exp_res.status_code == 201
            exp_id = exp_res.json()["id"]
            dl_url = exp_res.json()["downloadUrl"]

            db = SessionLocal()
            try:
                task = db.query(ExportTask).filter(ExportTask.id == exp_id).first()
                assert task is not None
                export_file_path = task.file_path
                assert os.path.isfile(export_file_path)
                os.remove(export_file_path)
                assert not os.path.isfile(export_file_path)
            finally:
                db.close()

            dl_res = client.get(dl_url, headers={"X-Pilot-Pin": "test-pin"})
            assert dl_res.status_code == 200
            assert len(dl_res.content) > 500
            assert dl_res.content[:2] == b"PK"  # Valid OOXML ZIP header
            assert os.path.isfile(export_file_path)
    finally:
        if export_file_path and os.path.isfile(export_file_path):
            try:
                os.remove(export_file_path)
            except OSError:
                pass
        if created_ctx_id:
            db = SessionLocal()
            try:
                db.query(EducationalContext).filter(EducationalContext.id == created_ctx_id).delete()
                db.commit()
            finally:
                db.close()
