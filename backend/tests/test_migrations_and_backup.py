import os
import tempfile
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import Base, engine, SessionLocal, normalize_database_url
from backend.app.models import EducationalContext, ExportTask
from backend.app.services.migration_and_backup import (
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
        assert res["backupVersion"] == "1.0"


def test_backup_and_restore_roundtrip_api(monkeypatch):
    monkeypatch.setenv("ENABLE_DEMO_SEED", "0")
    monkeypatch.delenv("PILOT_ACCESS_PIN", raising=False)
    Base.metadata.create_all(bind=engine)

    created_id = None
    try:
        with TestClient(app) as client:
            create_res = client.post(
                "/api/contexts",
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

            backup_res = client.get("/api/system/backup")
            assert backup_res.status_code == 200
            backup_payload = backup_res.json()
            assert backup_payload["backupVersion"] == "1.0"
            assert any(c["id"] == created_id for c in backup_payload["contexts"])

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

            restore_res = client.post("/api/system/restore", json=backup_payload)
            assert restore_res.status_code == 200
            assert restore_res.json()["restoredContextsCount"] >= 1

            get_res = client.get(f"/api/contexts/{created_id}")
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


def test_pilot_access_pin_middleware(monkeypatch):
    monkeypatch.setenv("ENABLE_DEMO_SEED", "0")
    monkeypatch.setenv("PILOT_ACCESS_PIN", "2026")
    Base.metadata.create_all(bind=engine)

    created_id = None
    try:
        with TestClient(app) as client:
            # Read-only endpoints remain open
            assert client.get("/api/health").status_code == 200
            backup_res = client.get("/api/system/backup")
            assert backup_res.status_code == 200

            # Mutating POST endpoints without PIN are rejected with 401 PILOT_PIN_REQUIRED
            no_pin = client.post("/api/contexts", json={"subject": "الفيزياء", "grade": "الرابع"})
            assert no_pin.status_code == 401
            assert no_pin.json()["code"] == "PILOT_PIN_REQUIRED"

            restore_no_pin = client.post("/api/system/restore", json=backup_res.json())
            assert restore_no_pin.status_code == 401
            assert restore_no_pin.json()["code"] == "PILOT_PIN_REQUIRED"

            # Wrong PIN rejected
            wrong_pin = client.post(
                "/api/contexts",
                headers={"X-Pilot-Pin": "9999"},
                json={"subject": "الفيزياء", "grade": "الرابع"},
            )
            assert wrong_pin.status_code == 401

            # Matching header PIN allowed
            ok_pin = client.post(
                "/api/contexts",
                headers={"X-Pilot-Pin": "2026"},
                json={"subject": "الفيزياء", "grade": "الرابع"},
            )
            assert ok_pin.status_code == 201
            created_id = ok_pin.json()["id"]

            # Matching query param PIN allowed on restore
            restore_ok = client.post("/api/system/restore?pin=2026", json=backup_res.json())
            assert restore_ok.status_code == 200
    finally:
        if created_id:
            db = SessionLocal()
            try:
                db.query(EducationalContext).filter(EducationalContext.id == created_id).delete()
                db.commit()
            finally:
                db.close()


def test_database_url_normalization():
    assert normalize_database_url("postgres://u:p@host:5432/db") == "postgresql+psycopg2://u:p@host:5432/db"
    assert normalize_database_url("postgresql://u:p@host:5432/db") == "postgresql+psycopg2://u:p@host:5432/db"
    assert normalize_database_url("sqlite:///./teacher_system.db") == "sqlite:///./teacher_system.db"


def test_export_download_self_healing_after_disk_reset(monkeypatch):
    monkeypatch.setenv("ENABLE_DEMO_SEED", "0")
    monkeypatch.delenv("PILOT_ACCESS_PIN", raising=False)
    Base.metadata.create_all(bind=engine)

    created_ctx_id = None
    export_file_path = None
    try:
        with TestClient(app) as client:
            ctx_res = client.post(
                "/api/contexts",
                json={"subject": "الأحياء", "grade": "السادس العلمي", "teacherName": "أ. نور"},
            )
            assert ctx_res.status_code == 201
            created_ctx_id = ctx_res.json()["id"]

            plan_res = client.post(
                "/api/plans",
                headers={"X-Active-Context-Id": created_ctx_id},
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
                headers={"X-Active-Context-Id": created_ctx_id},
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

            dl_res = client.get(dl_url)
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
