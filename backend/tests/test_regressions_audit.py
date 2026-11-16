import io
import json
import zipfile
import pymupdf
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import Base, engine, SessionLocal
from backend.app.models import EducationalContext
from backend.app.services.ai_service import _extract_json_from_text, _normalize_phases_minutes
from backend.app.services.audit_service import audit_plan_and_context, run_subject_tool, safe_eval_math_expression
from backend.app.services.export_service import (
    generate_plan_docx_bytes,
    generate_plan_pdf_bytes,
    generate_plan_pptx_bytes,
    verify_exported_file_structure,
)


def test_pdf_export_preserves_arabic_and_no_mojibake():
    plan_snap = {
        "title": "خطة درس: المعادلات الخطية",
        "planType": "daily",
        "status": "reviewed",
        "version": 1,
        "periodsCount": 1,
        "periodMinutes": 45,
        "objectives": ["أن يحل الطالب المعادلات الخطية بدقة."],
        "phases": [
            {"order": 1, "periodNumber": 1, "phaseName": "التهيئة", "teacherActivity": "مراجعة سريعة", "studentActivity": "يجيب", "minutes": 45}
        ],
        "formativeAssessment": "بطاقة خروج",
        "subjectItems": [{"domain": "math", "expression": "2 + 3", "expectedAnswer": "5", "unit": "سم"}],
    }
    ctx_snap = {"subject": "الرياضيات", "grade": "الأول المتوسط", "country": "العراق", "language": "ar", "curriculumName": "منهج العراق"}
    pdf_bytes = generate_plan_pdf_bytes(plan_snap, ctx_snap, {"findings": []}, "unverified_draft")
    assert pdf_bytes.startswith(b"%PDF-1.7")
    chk = verify_exported_file_structure(pdf_bytes, "pdf")
    assert chk["passed"] is True
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        txt = "".join(p.get_text("text") for p in doc)
        assert "Ø" not in txt  # Zero WinAnsi mojibake
        assert len(txt.strip()) > 30


def test_pptx_comparison_layout_and_overflow_continuation():
    long_content = "\n".join(f"بند رقم {i}: شرح تفصيلي واضح لمفهوم الدرس" for i in range(1, 13))
    plan_snap = {
        "title": "عرض متعدد الشرائح",
        "presentationSettings": {"textDirection": "rtl", "layoutStyle": "comparison"},
        "slides": [{"title": "مقارنة شاملة", "content": long_content}],
    }
    ctx_snap = {"subject": "العلوم", "grade": "الخامس", "country": "العراق", "language": "ar"}
    pptx_bytes = generate_plan_pptx_bytes(plan_snap, ctx_snap)
    chk = verify_exported_file_structure(pptx_bytes, "pptx")
    assert chk["passed"] is True
    assert chk["slidesCount"] == 2  # Lines 9-12 spill to continuation slide
    with zipfile.ZipFile(io.BytesIO(pptx_bytes), "r") as zf:
        s1 = zf.read("ppt/slides/slide1.xml").decode("utf-8")
        s2 = zf.read("ppt/slides/slide2.xml").decode("utf-8")
        assert "CompareCol1" in s1 and "CompareCol2" in s1
        assert "(تابع)" in s2
        assert "بند رقم 12" in s2


def test_ai_json_extractor_and_phase_minutes_normalization():
    raw = '<think>reasoning {foo}</think>\n{"slides": [{"order": 1, "title": "س"}]}\nملاحظة {غير مهمة}'
    parsed = _extract_json_from_text(raw)
    assert parsed is not None and parsed["slides"][0]["title"] == "س"

    phases = [{"phaseName": f"P{i}", "minutes": 20} for i in range(5)]  # sum = 100 -> target 45
    norm = _normalize_phases_minutes(phases, 45)
    assert sum(p["minutes"] for p in norm) == 45
    assert all(p["minutes"] >= 1 for p in norm)


def test_audit_and_subject_tools_edge_cases():
    # Arabic-Indic numerals + fraction claimed answer
    assert safe_eval_math_expression("١٥ + ٥") == 20.0
    m_res = run_subject_tool("الرياضيات", "math_solver", "", {"expression": "3 / 4", "claimedAnswer": "3/4"})
    assert m_res["valid"] is True

    # Null coercion prevention
    assert run_subject_tool("العلوم", "science_experiment", "", {"hypothesis": None})["valid"] is False
    assert run_subject_tool("الأدب", "text_analysis", "", {"passage": None})["valid"] is False

    # Timeline >= 2 events & BCE ("ق.م")
    assert run_subject_tool("التاريخ", "historical_timeline", "", {"events": [{"year": "622", "event": "الهجرة"}]})["valid"] is False
    bce_res = run_subject_tool(
        "التاريخ",
        "historical_timeline",
        "",
        {"events": [{"year": "500 ق.م", "event": "حدث قديم"}, {"year": "100 م", "event": "حدث أحدث"}]},
    )
    assert bce_res["valid"] is True

    # Five-day plan < 5 teaching days & negative minutes blocked
    res_5d = audit_plan_and_context(
        {
            "planType": "five_day",
            "formativeAssessment": "تقويم",
            "objectives": ["هدف"],
            "scheduleDays": [{"dayName": "الأحد", "lessonTitle": "درس", "minutes": -10}],
        },
        {"subject": "العلوم", "grade": "الأول", "country": "العراق", "curriculumName": "منهج", "language": "ar", "year": "2026", "edition": "1"},
    )
    codes = {f["code"] for f in res_5d["findings"] if f["category"] == "BLOCKER"}
    assert "NEGATIVE_SCHEDULE_DURATION" in codes


def test_security_revocation_isolation_and_report_docx(monkeypatch):
    monkeypatch.setenv("ENABLE_DEMO_SEED", "0")
    monkeypatch.delenv("PILOT_ACCESS_PIN", raising=False)
    monkeypatch.setenv("OMNIROUTE_BASE_URL", "")
    monkeypatch.delenv("NVIDIA_API_KEYS", raising=False)
    Base.metadata.create_all(bind=engine)

    ctx1_id = ctx2_id = None
    try:
        with TestClient(app) as client:
            c1 = client.post("/api/contexts", json={"subject": "الرياضيات", "grade": "الأول", "year": "2025", "edition": "1"}).json()
            c2 = client.post("/api/contexts", json={"subject": "الفيزياء", "grade": "الثاني", "year": "2026", "edition": "1"}).json()
            ctx1_id, ctx2_id = c1["id"], c2["id"]
            h1, h2 = {"X-Active-Context-Id": ctx1_id}, {"X-Active-Context-Id": ctx2_id}

            # Cross-context chapter in lesson -> 400
            src1 = client.post(
                "/api/sources/upload",
                headers=h1,
                data={"contextId": ctx1_id, "title": "مصدر 1"},
                files={"file": ("s1.pdf", b"%PDF-1.7\n1 0 obj<<>>endobj\n", "application/pdf")},
            ).json()
            ch1 = client.post("/api/chapters", headers=h1, json={"contextId": ctx1_id, "sourceId": src1["id"], "title": "فصل 1"}).json()
            les1 = client.post("/api/lessons", headers=h1, json={"contextId": ctx1_id, "sourceId": src1["id"], "chapterId": ch1["id"], "title": "درس 1"}).json()

            cross_ch = client.post("/api/lessons", headers=h2, json={"contextId": ctx2_id, "chapterId": ch1["id"], "title": "درس عابر"}).status_code
            assert cross_ch == 400

            # Source optimistic concurrency expectedVersion -> 409
            src_upd = client.put(
                f"/api/sources/{src1['id']}",
                headers=h1,
                json={"contextId": ctx1_id, "title": "معدل", "expectedVersion": 999},
            )
            assert src_upd.status_code == 409

            # Stale header blocked on /tools/execute
            assert client.post("/api/tools/execute", headers=h2, json={"contextId": ctx1_id, "toolType": "math_solver", "inputs": {"expression": "1+1"}}).status_code == 409

            # Create plan in ctx1, cross-context primaryLessonId in update -> 400
            p1 = client.post(
                "/api/plans",
                headers=h1,
                json={
                    "contextId": ctx1_id,
                    "title": "خطة أ",
                    "planType": "daily",
                    "periodsCount": 1,
                    "periodMinutes": 45,
                    "objectives": ["هدف 1"],
                    "formativeAssessment": "تقويم",
                },
            ).json()
            p2 = client.post("/api/plans", headers=h2, json={"contextId": ctx2_id, "title": "خطة ب", "planType": "daily", "periodsCount": 1, "periodMinutes": 45}).json()
            p2_cross = client.put(
                f"/api/plans/{p2['id']}",
                headers=h2,
                json={"contextId": ctx2_id, "primaryLessonId": les1["id"], "title": "خطة ب", "planType": "daily", "expectedVersion": p2["version"]},
            )
            assert p2_cross.status_code == 400

            # Approve p1, then edit slides via AI -> must revoke approved status
            app_res = client.post(f"/api/plans/{p1['id']}/approve?contextId={ctx1_id}", headers=h1)
            assert app_res.status_code == 200 and app_res.json()["status"] == "approved"
            sld_res = client.post(f"/api/plans/{p1['id']}/ai-generate-slides", headers=h1, json={"contextId": ctx1_id, "slidesCount": 5})
            assert sld_res.status_code == 200 and sld_res.json()["plan"]["status"] != "approved"

            # report_docx includes patternSummary & documentationGaps
            exp_rep = client.post("/api/exports", headers=h1, json={"contextId": ctx1_id, "exportFormat": "report_docx"})
            assert exp_rep.status_code == 201
            dl_rep = client.get(exp_rep.json()["downloadUrl"])
            assert dl_rep.status_code == 200
            with zipfile.ZipFile(io.BytesIO(dl_rep.content), "r") as zf:
                doc_xml = zf.read("word/document.xml").decode("utf-8")
                assert "ملخص التخطيط حسب النمط" in doc_xml

            # Invalid restore payload -> 400 (not 500)
            bad_restore = client.post("/api/system/restore", json={"backupVersion": "1.0", "contexts": "not-a-list"})
            assert bad_restore.status_code == 400
    finally:
        import os
        from backend.app.models import CurriculumSource, ExportTask
        db = SessionLocal()
        try:
            for cid in (ctx1_id, ctx2_id):
                if cid:
                    for s in db.query(CurriculumSource).filter(CurriculumSource.context_id == cid).all():
                        if s.file_path and os.path.isfile(s.file_path):
                            os.remove(s.file_path)
                    for e in db.query(ExportTask).filter(ExportTask.context_id == cid).all():
                        if e.file_path and os.path.isfile(e.file_path):
                            os.remove(e.file_path)
                    db.query(EducationalContext).filter(EducationalContext.id == cid).delete()
            db.commit()
        finally:
            db.close()
