import os
import fitz
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import Base, engine, SessionLocal
from backend.app.models import EducationalContext
from backend.app.services.pdf_service import inspect_and_extract_pdf, render_pdf_page_to_png_bytes


def _build_real_arabic_pdf_bytes() -> bytes:
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text((72, 72), "Chapter 1: Algebraic Equations & Fractions\n3/4 + 1/2 = 5/4\n2026", fontsize=14)
    page2 = doc.new_page()
    # Use insert_htmlbox so Arabic shaping/Unicode embeds properly via PyMuPDF
    page2.insert_htmlbox(
        fitz.Rect(50, 50, 500, 300),
        "<div dir='rtl' style='font-size:16px'>الفصل الثاني: المعادلات الخطية<br/>الدرس الأول: حل معادلات الدرجة الأولى في متغير واحد</div>",
    )
    return doc.tobytes()


def test_pymupdf_real_extraction_and_png_rendering():
    pdf_bytes = _build_real_arabic_pdf_bytes()
    res = inspect_and_extract_pdf(pdf_bytes, "arabic_math_textbook.pdf")

    assert res["pageCount"] == 2
    assert res["extractionStatus"] == "extracted_text"
    assert len(res["pages"]) == 2
    assert "Algebraic Equations" in res["pages"][0]["extractedText"]
    assert "متغير واحد" in res["pages"][1]["extractedText"]
    assert "درس" in res["pages"][1]["extractedText"]

    png1 = render_pdf_page_to_png_bytes(pdf_bytes, 1)
    assert png1 is not None and png1.startswith(b"\x89PNG")
    png2 = render_pdf_page_to_png_bytes(pdf_bytes, 2)
    assert png2 is not None and png2.startswith(b"\x89PNG")


def test_ai_endpoints_and_source_extraction_pipeline(monkeypatch):
    monkeypatch.setenv("ENABLE_DEMO_SEED", "0")
    monkeypatch.setenv("PILOT_ACCESS_PIN", "test-pin")
    # Force fast deterministic fallback inside unit test so test never depends on external network latency
    monkeypatch.setenv("OMNIROUTE_BASE_URL", "")
    monkeypatch.delenv("NVIDIA_API_KEYS", raising=False)
    Base.metadata.create_all(bind=engine)

    created_ctx_id = None
    uploaded_file_path = None
    try:
        with TestClient(app, headers={"X-Pilot-Pin": "test-pin"}) as client:
            status_res = client.get("/api/ai/status")
            assert status_res.status_code == 200
            assert status_res.json() == {
                "available": False,
                "textGenerationReady": False,
                "visionGenerationReady": False,
                "fallbackAvailable": True,
            }

            ctx_res = client.post(
                "/api/contexts",
                json={"subject": "الرياضيات", "grade": "الأول المتوسط", "country": "العراق", "teacherName": "أ. مصطفى"},
            )
            assert ctx_res.status_code == 201
            created_ctx_id = ctx_res.json()["id"]
            headers = {"X-Active-Context-Id": created_ctx_id}

            # 1. Upload real PDF built with PyMuPDF
            pdf_bytes = _build_real_arabic_pdf_bytes()
            up_res = client.post(
                "/api/sources/upload",
                headers=headers,
                data={"contextId": created_ctx_id, "title": "كتاب الرياضيات المنهجي"},
                files={"file": ("math_book.pdf", pdf_bytes, "application/pdf")},
            )
            assert up_res.status_code == 201
            src_data = up_res.json()
            assert src_data["extractionStatus"] == "extracted_text"
            assert src_data["pageCount"] == 2
            page_id = src_data["pages"][1]["id"]

            # 2. Run Vision OCR endpoint on page 2
            ocr_res = client.post(
                f"/api/sources/{src_data['id']}/pages/{page_id}/ai-ocr",
                headers=headers,
                json={"contextId": created_ctx_id},
            )
            assert ocr_res.status_code == 200
            assert "متغير واحد" in ocr_res.json()["page"]["extractedText"]

            # 3. Extract Chapters & Lessons into DB
            struct_res = client.post(
                f"/api/sources/{src_data['id']}/ai-extract-structure",
                headers=headers,
                json={"contextId": created_ctx_id},
            )
            assert struct_res.status_code == 200
            assert struct_res.json()["chaptersCreated"] >= 1
            assert struct_res.json()["lessonsCreated"] >= 1

            # 4. Create plan, auto-draft via AI, and generate 6 slides
            pln_res = client.post(
                "/api/plans",
                headers=headers,
                json={
                    "contextId": created_ctx_id,
                    "sourceId": src_data["id"],
                    "title": "حل معادلات الدرجة الأولى",
                    "planType": "daily",
                    "periodsCount": 1,
                    "periodMinutes": 45,
                },
            )
            assert pln_res.status_code == 201
            plan_id = pln_res.json()["id"]

            ai_plan_res = client.post(
                f"/api/plans/{plan_id}/ai-generate-plan",
                headers=headers,
                json={"contextId": created_ctx_id, "lessonTitle": "حل معادلات الدرجة الأولى"},
            )
            assert ai_plan_res.status_code == 200
            ai_plan = ai_plan_res.json()["plan"]
            assert ai_plan_res.json()["audit"]["blockersCount"] == 0
            assert sum(p["minutes"] for p in ai_plan["phases"] if not p.get("isHomeEnrichment")) == 45

            slides_res = client.post(
                f"/api/plans/{plan_id}/ai-generate-slides",
                headers=headers,
                json={"contextId": created_ctx_id, "slidesCount": 6, "customInstructions": "أضف أمثلة حياتية"},
            )
            assert slides_res.status_code == 200
            assert slides_res.json()["slidesCount"] == 6
            assert len(slides_res.json()["plan"]["slides"]) == 6
    finally:
        if created_ctx_id:
            db = SessionLocal()
            try:
                from backend.app.models import CurriculumSource
                for s in db.query(CurriculumSource).filter(CurriculumSource.context_id == created_ctx_id).all():
                    uploaded_file_path = s.file_path
                    if uploaded_file_path and os.path.isfile(uploaded_file_path):
                        os.remove(uploaded_file_path)
                db.query(EducationalContext).filter(EducationalContext.id == created_ctx_id).delete()
                db.commit()
            finally:
                db.close()
