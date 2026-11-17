import io
import os
import shutil
import zipfile
from unittest.mock import patch

import fitz
import pytest
from fastapi.testclient import TestClient

from backend.app.database import Base, engine, SessionLocal
from backend.app.main import app
from backend.app.models import (
    CurriculumSource,
    EducationalContext,
    ExportTask,
    Plan,
    PlanVersion,
)
from backend.app.services.audit_service import audit_plan_and_context, run_subject_tool


def _make_valid_pdf_bytes(text: str = "", blank: bool = False) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    if not blank and text:
        page.insert_text((72, 72), text, fontsize=14)
    return doc.tobytes()


def _cleanup_context(ctx_id: str | None):
    if not ctx_id:
        return
    db = SessionLocal()
    try:
        for src in db.query(CurriculumSource).filter(CurriculumSource.context_id == ctx_id).all():
            if src.file_path and os.path.isfile(src.file_path):
                try:
                    os.remove(src.file_path)
                except OSError:
                    pass
        for exp in db.query(ExportTask).filter(ExportTask.context_id == ctx_id).all():
            if exp.file_path and os.path.isfile(exp.file_path):
                try:
                    os.remove(exp.file_path)
                except OSError:
                    pass
        db.query(EducationalContext).filter(EducationalContext.id == ctx_id).delete()
        db.commit()
    finally:
        db.close()


def _full_ctx_dict() -> dict:
    return {
        "subject": "الرياضيات",
        "grade": "الأول المتوسط",
        "country": "العراق",
        "curriculumName": "المنهج الحديث",
        "language": "ar",
        "year": "2026",
        "edition": "الأولى",
    }


def test_weekly_and_five_day_audit_blocks_blank_assessment_zero_duration_and_all_holidays(monkeypatch):
    monkeypatch.setenv("PILOT_ACCESS_PIN", "test-pin")
    Base.metadata.create_all(bind=engine)

    # 1. All-holiday weekly plan -> NO_TEACHING_DAYS
    all_holiday = audit_plan_and_context(
        {
            "planType": "weekly",
            "objectives": ["هدف أسبوعي"],
            "formativeAssessment": "تقويم عام",
            "scheduleDays": [
                {"dayName": "الجمعة", "isHoliday": True, "lessonTitle": "عطلة", "assessment": "", "minutes": 0},
                {"dayName": "السبت", "isHoliday": True, "lessonTitle": "عطلة", "assessment": "", "minutes": 0},
            ],
        },
        _full_ctx_dict(),
    )
    assert all_holiday["canApprove"] is False
    holiday_codes = [f["code"] for f in all_holiday["findings"] if f["category"] == "BLOCKER"]
    assert "NO_TEACHING_DAYS" in holiday_codes

    # 2. Weekly with blank assessment and zero minutes -> MISSING_DAY_ASSESSMENT + ZERO_SCHEDULE_DURATION
    weekly_defective = audit_plan_and_context(
        {
            "planType": "weekly",
            "objectives": ["هدف أسبوعي"],
            "formativeAssessment": "تقويم عام",
            "scheduleDays": [
                {"dayName": "الأحد", "isHoliday": False, "lessonTitle": "درس 1", "assessment": "", "minutes": 45},
                {"dayName": "الاثنين", "isHoliday": False, "lessonTitle": "درس 2", "assessment": "اختبار قصير", "minutes": 0},
                {"dayName": "الثلاثاء", "isHoliday": False, "lessonTitle": "درس 3", "assessment": "   ", "durationMinutes": 0},
                {"dayName": "الجمعة", "isHoliday": True, "lessonTitle": "عطلة", "assessment": "", "minutes": 0},
            ],
        },
        _full_ctx_dict(),
    )
    assert weekly_defective["canApprove"] is False
    w_codes = [f["code"] for f in weekly_defective["findings"] if f["category"] == "BLOCKER"]
    assert w_codes.count("MISSING_DAY_ASSESSMENT") == 2
    assert w_codes.count("ZERO_SCHEDULE_DURATION") == 2
    assert "SCHEDULE_DAYS_VALID" not in [f["code"] for f in weekly_defective["findings"]]

    # 3. Five-day with 4/5 blank assessments -> BLOCKED on API /approve too
    ctx_id = None
    try:
        with TestClient(app, headers={"X-Pilot-Pin": "test-pin"}) as client:
            ctx_id = client.post("/api/contexts", json={"subject": "الرياضيات", "grade": "الأول"}).json()["id"]
            headers = {"X-Active-Context-Id": ctx_id}
            five_days = [
                {"dayNumber": i, "dayName": f"يوم {i}", "isHoliday": False, "lessonTitle": f"درس {i}", "assessment": "سؤال ختامي" if i == 1 else "", "minutes": 45}
                for i in range(1, 6)
            ]
            p_res = client.post(
                "/api/plans",
                headers=headers,
                json={
                    "contextId": ctx_id,
                    "title": "خطة خمسة أيام ناقصة التقويم",
                    "planType": "five_day",
                    "objectives": ["هدف"],
                    "formativeAssessment": "تقويم عام",
                    "scheduleDays": five_days,
                },
            )
            assert p_res.status_code == 201
            plan = p_res.json()
            blocker_codes = [f["code"] for f in plan["latestReview"]["findings"] if f["category"] == "BLOCKER"]
            assert blocker_codes.count("MISSING_DAY_ASSESSMENT") == 4

            app_res = client.post(f"/api/plans/{plan['id']}/approve?contextId={ctx_id}", headers=headers)
            assert app_res.status_code == 400
            assert app_res.json()["code"] == "APPROVAL_BLOCKED_BY_DEFECTS"

            # Fix all 5 day assessments -> approval succeeds!
            for d in five_days:
                d["assessment"] = "سؤال ختامي"
            upd = client.put(
                f"/api/plans/{plan['id']}",
                headers=headers,
                json={
                    "contextId": ctx_id,
                    "title": plan["title"],
                    "planType": "five_day",
                    "objectives": ["هدف"],
                    "formativeAssessment": "تقويم عام",
                    "scheduleDays": five_days,
                    "expectedVersion": plan["version"],
                },
            )
            assert upd.status_code == 200
            assert upd.json()["latestReview"]["blockersCount"] == 0
            ok_app = client.post(f"/api/plans/{plan['id']}/approve?contextId={ctx_id}", headers=headers)
            assert ok_app.status_code == 200
            assert ok_app.json()["status"] == "approved"
    finally:
        _cleanup_context(ctx_id)


def test_unknown_subject_tool_rejected_in_engine_and_api(monkeypatch):
    monkeypatch.setenv("PILOT_ACCESS_PIN", "test-pin")
    Base.metadata.create_all(bind=engine)

    with pytest.raises(ValueError):
        run_subject_tool("الرياضيات", "non_existent_tool", "عنوان", {})

    ctx_id = None
    try:
        with TestClient(app, headers={"X-Pilot-Pin": "test-pin"}) as client:
            ctx_id = client.post("/api/contexts", json={"subject": "العلوم", "grade": "الثاني"}).json()["id"]
            headers = {"X-Active-Context-Id": ctx_id}

            bad = client.post(
                "/api/tools/execute",
                headers=headers,
                json={"contextId": ctx_id, "toolType": "totally_bogus_tool", "title": "اختبار", "inputs": {}},
            )
            assert bad.status_code in (400, 422)
            assert bad.json()["code"] == "UNKNOWN_TOOL_TYPE"

            good = client.post(
                "/api/tools/execute",
                headers=headers,
                json={"contextId": ctx_id, "toolType": "worksheet_generator", "title": "ورقة عمل", "inputs": {}},
            )
            assert good.status_code == 200
            assert good.json()["valid"] is True
    finally:
        _cleanup_context(ctx_id)


def test_post_backup_v2_restore_export_download_self_heals_and_bundle_filenames(monkeypatch):
    monkeypatch.setenv("PILOT_ACCESS_PIN", "test-pin")
    Base.metadata.create_all(bind=engine)

    ctx_id = None
    try:
        with TestClient(app, headers={"X-Pilot-Pin": "test-pin"}) as client:
            ctx_id = client.post(
                "/api/contexts",
                json={"subject": "الفيزياء", "grade": "الرابع", "teacherName": "أ. سارة"},
            ).json()["id"]
            headers = {"X-Active-Context-Id": ctx_id}

            weekly_days = [
                {"dayName": "الأحد", "isHoliday": False, "lessonTitle": "الحركة", "assessment": "تمرين", "minutes": 45},
                {"dayName": "الجمعة", "isHoliday": True, "lessonTitle": "عطلة", "assessment": "—", "minutes": 0},
            ]
            pln = client.post(
                "/api/plans",
                headers=headers,
                json={
                    "contextId": ctx_id,
                    "title": "خطة أسبوعية فيزياء",
                    "planType": "weekly",
                    "objectives": ["فهم الحركة"],
                    "formativeAssessment": "تقويم أسبوعي",
                    "scheduleDays": weekly_days,
                    "homeEnrichmentMinutes": 20,
                    "referencesNote": "دليل الفيزياء",
                    "planningNotes": "ملاحظات التخطيط الأسبوعي",
                },
            ).json()

            # Create docx and bundle_zip exports
            exp_docx = client.post(
                "/api/exports",
                headers=headers,
                json={"contextId": ctx_id, "planId": pln["id"], "exportFormat": "docx"},
            )
            assert exp_docx.status_code == 201
            docx_id = exp_docx.json()["id"]

            exp_zip = client.post(
                "/api/exports",
                headers=headers,
                json={"contextId": ctx_id, "planId": pln["id"], "exportFormat": "bundle_zip"},
            )
            assert exp_zip.status_code == 201
            zip_id = exp_zip.json()["id"]

            # Verify weekly bundle uses plan-type-aware filenames
            zip_dl = client.get(f"/api/exports/{zip_id}/download?contextId={ctx_id}")
            assert zip_dl.status_code == 200
            with zipfile.ZipFile(io.BytesIO(zip_dl.content), "r") as zf:
                names = zf.namelist()
                assert "1_weekly_plan_editable.docx" in names
                assert "2_weekly_plan_printable.pdf" in names
                assert "1_daily_plan_editable.docx" not in names

            # Take backup v2, delete context + files from disk, then restore backup v2
            backup_payload = client.get("/api/system/backup").json()
            assert backup_payload["backupVersion"] == "2.0"

            db = SessionLocal()
            try:
                for exp in db.query(ExportTask).filter(ExportTask.context_id == ctx_id).all():
                    if exp.file_path and os.path.isfile(exp.file_path):
                        os.remove(exp.file_path)
                db.query(EducationalContext).filter(EducationalContext.id == ctx_id).delete()
                db.commit()
            finally:
                db.close()

            restore_res = client.post("/api/system/restore", json=backup_payload)
            assert restore_res.status_code == 200

            # Verify ExportTask has empty file_path right after restore, and /api/exports shows artifactAvailable=False
            exports_before = client.get(f"/api/exports?contextId={ctx_id}", headers=headers).json()["items"]
            restored_docx_meta = next(item for item in exports_before if item["id"] == docx_id)
            assert restored_docx_meta["artifactAvailable"] is False
            assert restored_docx_meta["structuralCheckDetails"]["artifactAvailable"] is False

            # Now download MUST self-heal with 200 (never 500 FileNotFoundError!)
            healed_dl = client.get(f"/api/exports/{docx_id}/download?contextId={ctx_id}")
            assert healed_dl.status_code == 200
            assert healed_dl.content[:2] == b"PK"

            healed_zip_dl = client.get(f"/api/exports/{zip_id}/download?contextId={ctx_id}")
            assert healed_zip_dl.status_code == 200
            with zipfile.ZipFile(io.BytesIO(healed_zip_dl.content), "r") as zf:
                assert "1_weekly_plan_editable.docx" in zf.namelist()

            # Verify DB task is persisted and subsequent listing/download sees artifactAvailable=True
            exports_after = client.get(f"/api/exports?contextId={ctx_id}", headers=headers).json()["items"]
            healed_meta = next(item for item in exports_after if item["id"] == docx_id)
            assert healed_meta["artifactAvailable"] is True
            assert healed_meta["fileSize"] == len(healed_dl.content)
            assert healed_meta["structuralCheckDetails"]["artifactAvailable"] is True

            second_dl = client.get(f"/api/exports/{docx_id}/download?contextId={ctx_id}")
            assert second_dl.status_code == 200
            assert second_dl.content == healed_dl.content
    finally:
        _cleanup_context(ctx_id)


def test_copy_to_context_rescales_phases_and_preserves_version_metadata(monkeypatch):
    monkeypatch.setenv("PILOT_ACCESS_PIN", "test-pin")
    Base.metadata.create_all(bind=engine)

    ctx_src_id = ctx_dst_id = None
    try:
        with TestClient(app, headers={"X-Pilot-Pin": "test-pin"}) as client:
            ctx_src_id = client.post(
                "/api/contexts",
                json={"subject": "الكيمياء", "grade": "الثالث", "defaultPeriodMinutes": 45},
            ).json()["id"]
            ctx_dst_id = client.post(
                "/api/contexts",
                json={"subject": "الكيمياء", "grade": "الرابع", "defaultPeriodMinutes": 50},
            ).json()["id"]

            h_src = {"X-Active-Context-Id": ctx_src_id}
            phases_45 = [
                {"order": 1, "phaseName": "تهيئة", "minutes": 5, "isHomeEnrichment": False},
                {"order": 2, "phaseName": "تدريس", "minutes": 15, "isHomeEnrichment": False},
                {"order": 3, "phaseName": "تدريب", "minutes": 12, "isHomeEnrichment": False},
                {"order": 4, "phaseName": "تقويم", "minutes": 8, "isHomeEnrichment": False},
                {"order": 5, "phaseName": "توسعة", "minutes": 5, "isHomeEnrichment": False},
                {"order": 6, "phaseName": "واجب منزلي", "minutes": 15, "isHomeEnrichment": True},
            ]
            orig_res = client.post(
                "/api/plans",
                headers=h_src,
                json={
                    "contextId": ctx_src_id,
                    "title": "خطة التفاعلات",
                    "planType": "daily",
                    "periodsCount": 1,
                    "periodMinutes": 45,
                    "objectives": ["فهم التفاعلات الكيميائية"],
                    "phases": phases_45,
                    "formativeAssessment": "بطاقة خروج",
                    "homeEnrichmentMinutes": 15,
                    "referencesNote": "كتاب الكيمياء ص 12",
                    "planningNotes": "ملاحظات المعلم الهامة",
                },
            )
            assert orig_res.status_code == 201
            orig_plan = orig_res.json()

            # Check PlanVersion.plan_payload preserves all 4 metadata fields
            db = SessionLocal()
            try:
                pver = (
                    db.query(PlanVersion)
                    .filter(PlanVersion.plan_id == orig_plan["id"], PlanVersion.version_number == 1)
                    .first()
                )
                assert pver is not None
                assert pver.plan_payload["totalAllocatedMinutes"] == 45
                assert pver.plan_payload["homeEnrichmentMinutes"] == 15
                assert pver.plan_payload["referencesNote"] == "كتاب الكيمياء ص 12"
                assert pver.plan_payload["planningNotes"] == "ملاحظات المعلم الهامة"
            finally:
                db.close()

            # Copy to 50-minute context -> phases must rescale cleanly to 50 (home enrichment stays 15)
            copy_res = client.post(
                f"/api/plans/{orig_plan['id']}/copy-to-context",
                headers=h_src,
                json={"sourceContextId": ctx_src_id, "targetContextId": ctx_dst_id, "reviewerNote": "منقولة"},
            )
            assert copy_res.status_code == 201
            copied = copy_res.json()
            assert copied["periodMinutes"] == 50
            assert copied["totalAllocatedMinutes"] == 50
            in_class_sum = sum(p["minutes"] for p in copied["phases"] if not p.get("isHomeEnrichment"))
            home_mins = sum(p["minutes"] for p in copied["phases"] if p.get("isHomeEnrichment"))
            assert in_class_sum == 50
            assert home_mins == 15

            finding_codes = [f["code"] for f in copied["latestReview"]["findings"]]
            assert "TIME_DISTRIBUTION_MISMATCH" not in finding_codes
            assert "TIME_DISTRIBUTION_VALID" in finding_codes
            assert copied["latestReview"]["blockersCount"] == 0
    finally:
        _cleanup_context(ctx_src_id)
        _cleanup_context(ctx_dst_id)


def test_read_side_active_context_header_guard(monkeypatch):
    monkeypatch.setenv("PILOT_ACCESS_PIN", "test-pin")
    Base.metadata.create_all(bind=engine)

    ctx1_id = ctx2_id = None
    try:
        with TestClient(app, headers={"X-Pilot-Pin": "test-pin"}) as client:
            ctx1_id = client.post("/api/contexts", json={"subject": "أحياء", "grade": "الأول"}).json()["id"]
            ctx2_id = client.post("/api/contexts", json={"subject": "جغرافيا", "grade": "الأول"}).json()["id"]
            h1 = {"X-Active-Context-Id": ctx1_id}
            h_stale = {"X-Active-Context-Id": ctx2_id}

            pln = client.post(
                "/api/plans",
                headers=h1,
                json={
                    "contextId": ctx1_id,
                    "title": "خطة أحياء",
                    "planType": "daily",
                    "objectives": ["هدف"],
                    "formativeAssessment": "تقويم",
                },
            ).json()
            exp = client.post(
                "/api/exports",
                headers=h1,
                json={"contextId": ctx1_id, "planId": pln["id"], "exportFormat": "docx"},
            ).json()

            pdf_bytes = _make_valid_pdf_bytes("Sample Biology Page")
            src = client.post(
                "/api/sources/upload",
                headers=h1,
                data={"contextId": ctx1_id, "title": "كتاب الأحياء"},
                files={"file": ("bio.pdf", pdf_bytes, "application/pdf")},
            ).json()
            page_id = src["pages"][0]["id"]

            guarded_urls = [
                f"/api/contexts/{ctx1_id}",
                f"/api/templates?contextId={ctx1_id}",
                f"/api/sources?contextId={ctx1_id}",
                f"/api/sources/{src['id']}/pages/{page_id}/image?contextId={ctx1_id}",
                f"/api/lessons?contextId={ctx1_id}",
                f"/api/plans?contextId={ctx1_id}",
                f"/api/plans/{pln['id']}?contextId={ctx1_id}",
                f"/api/dashboard?contextId={ctx1_id}",
                f"/api/reports?contextId={ctx1_id}",
                f"/api/exports?contextId={ctx1_id}",
                f"/api/exports/{exp['id']}/download?contextId={ctx1_id}",
            ]

            for url in guarded_urls:
                # Mismatched header -> 409 STALE_CONTEXT_READ_BLOCKED
                res_bad = client.get(url, headers=h_stale)
                assert res_bad.status_code == 409, f"Expected 409 for stale header on {url}, got {res_bad.status_code}"
                assert res_bad.json()["code"] == "STALE_CONTEXT_READ_BLOCKED"

                # Matching header -> 200
                res_match = client.get(url, headers=h1)
                assert res_match.status_code == 200, f"Expected 200 for matching header on {url}"

                # Omitted header -> 200
                res_omit = client.get(url)
                assert res_omit.status_code == 200, f"Expected 200 for omitted header on {url}"

            # Global routes must NOT reject even if stale header is sent
            for global_url in ["/api/health", "/api/contexts", "/api/ai/status", "/api/system/backup"]:
                assert client.get(global_url, headers=h_stale).status_code == 200
    finally:
        _cleanup_context(ctx1_id)
        _cleanup_context(ctx2_id)


def test_corrupt_pdf_upload_source_page_image_and_offline_ocr_state_integrity(monkeypatch):
    monkeypatch.setenv("PILOT_ACCESS_PIN", "test-pin")
    monkeypatch.setenv("OMNIROUTE_BASE_URL", "")
    monkeypatch.delenv("NVIDIA_API_KEYS", raising=False)
    Base.metadata.create_all(bind=engine)

    ctx1_id = ctx2_id = None
    try:
        with TestClient(app, headers={"X-Pilot-Pin": "test-pin"}) as client:
            ctx1_id = client.post("/api/contexts", json={"subject": "رياضيات", "grade": "السابع"}).json()["id"]
            ctx2_id = client.post("/api/contexts", json={"subject": "تاريخ", "grade": "السابع"}).json()["id"]
            h1 = {"X-Active-Context-Id": ctx1_id}

            # 1. Corrupt PDF body with %PDF-1.4 header returns 422 CORRUPT_PDF & creates no source
            corrupt_res = client.post(
                "/api/sources/upload",
                headers=h1,
                data={"contextId": ctx1_id, "title": "ملف تالف"},
                files={"file": ("corrupt.pdf", b"%PDF-1.4\nGARBAGE_UNREADABLE_BODY", "application/pdf")},
            )
            assert corrupt_res.status_code == 422
            assert corrupt_res.json()["code"] == "CORRUPT_PDF"
            assert client.get(f"/api/sources?contextId={ctx1_id}", headers=h1).json()["items"] == []

            # 2. Blank scanned PDF -> requires_ocr_or_manual
            blank_pdf = _make_valid_pdf_bytes(blank=True)
            scan_res = client.post(
                "/api/sources/upload",
                headers=h1,
                data={"contextId": ctx1_id, "title": "كتاب ممسوح ضوئيا"},
                files={"file": ("scan.pdf", blank_pdf, "application/pdf")},
            )
            assert scan_res.status_code == 201
            src = scan_res.json()
            assert src["extractionStatus"] == "requires_ocr_or_manual"
            page_id = src["pages"][0]["id"]

            # 3. Page PNG image endpoint: valid PNG, PIN-protected, context-ownership protected
            img_ok = client.get(f"/api/sources/{src['id']}/pages/{page_id}/image?contextId={ctx1_id}", headers=h1)
            assert img_ok.status_code == 200
            assert img_ok.headers["content-type"].startswith("image/png")
            assert img_ok.content.startswith(b"\x89PNG")

            img_wrong_ctx = client.get(
                f"/api/sources/{src['id']}/pages/{page_id}/image?contextId={ctx2_id}",
                headers={"X-Active-Context-Id": ctx2_id},
            )
            assert img_wrong_ctx.status_code == 404

            # Without PIN -> 401
            with TestClient(app) as unauth_client:
                assert unauth_client.get(f"/api/sources/{src['id']}/pages/{page_id}/image?contextId={ctx1_id}").status_code == 401

            # 4. Offline OCR (extracted=False) must NOT corrupt text or flip extractionStatus
            offline_ocr = client.post(
                f"/api/sources/{src['id']}/pages/{page_id}/ai-ocr",
                headers=h1,
                json={"contextId": ctx1_id},
            )
            assert offline_ocr.status_code == 200
            off_body = offline_ocr.json()
            assert off_body["extracted"] is False
            assert off_body["extractionStatus"] == "requires_ocr_or_manual"
            assert off_body["page"]["extractedText"] == ""
            assert off_body["page"]["correctedText"] == ""
            assert len(off_body["page"]["ocrAmbiguities"]) >= 1
            assert off_body["page"]["ocrAmbiguities"][0]["type"] == "scanned_or_empty_page"

            # Confirm persisted DB status stayed requires_ocr_or_manual
            src_check = client.get(f"/api/sources?contextId={ctx1_id}", headers=h1).json()["items"][0]
            assert src_check["extractionStatus"] == "requires_ocr_or_manual"

            # 5. Successful Vision OCR (extracted=True) updates text, recomputes ambiguities, flips extractionStatus
            with patch(
                "backend.app.main.ocr_pdf_page_with_ai",
                return_value={
                    "extracted": True,
                    "extractedText": "المعادلة: 3/4 + 1/4 = 1",
                    "printedPageNumber": "14",
                    "notes": "تم الاستخراج بنجاح",
                    "modelUsed": "mock-vision-model",
                },
            ):
                live_ocr = client.post(
                    f"/api/sources/{src['id']}/pages/{page_id}/ai-ocr",
                    headers=h1,
                    json={"contextId": ctx1_id},
                )
            assert live_ocr.status_code == 200
            live_body = live_ocr.json()
            assert live_body["extracted"] is True
            assert live_body["extractionStatus"] == "extracted_text"
            assert live_body["page"]["extractedText"] == "المعادلة: 3/4 + 1/4 = 1"
            assert live_body["page"]["correctedText"] == "المعادلة: 3/4 + 1/4 = 1"
            assert live_body["page"]["printedPageNumber"] == "14"
            assert any(a["type"] == "math_symbols_and_fractions" for a in live_body["page"]["ocrAmbiguities"])
    finally:
        _cleanup_context(ctx1_id)
        _cleanup_context(ctx2_id)
