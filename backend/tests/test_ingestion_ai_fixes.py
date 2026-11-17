import io
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import fitz
import pytest

from backend.app.services import ai_service
from backend.app.services.pdf_service import (
    _detect_printed_page_number,
    _extract_text_from_pdf_stream,
    detect_ocr_ambiguities,
    inspect_and_extract_pdf,
    normalize_indesign_arabic_ligatures,
)


def _make_image_only_pdf_bytes(num_pages: int = 3, img_format: str = "png") -> bytes:
    """Builds a real PDF with embedded raster images and zero text layer."""
    doc = fitz.open()
    # Create a tiny raster pixmap and encode it
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 120, 120), False)
    pix.set_rect(pix.irect, (210, 180, 140))
    if img_format == "jpeg":
        img_bytes = pix.tobytes("jpeg")
    else:
        img_bytes = pix.tobytes("png")
    for _ in range(num_pages):
        page = doc.new_page(width=400, height=600)
        page.insert_image(fitz.Rect(20, 20, 380, 580), stream=img_bytes)
    return doc.tobytes()


def test_scanned_image_only_pdfs_have_zero_binary_garbage_and_corrupt_raises():
    # 1. Multi-page PNG scan and 1-page JPEG scan -> requires_ocr_or_manual, empty text
    for pages_n, fmt in [(3, "png"), (1, "jpeg")]:
        scan_bytes = _make_image_only_pdf_bytes(num_pages=pages_n, img_format=fmt)
        res = inspect_and_extract_pdf(scan_bytes, f"scan_{fmt}.pdf")
        assert res["pageCount"] == pages_n
        assert res["extractionStatus"] == "requires_ocr_or_manual"
        assert len(res["pages"]) == pages_n
        for pg in res["pages"]:
            assert pg["extractedText"] == ""
            assert pg["correctedText"] == ""
            assert pg["needsOcrReview"] is True
            assert pg["ocrAmbiguities"][0]["type"] == "scanned_or_empty_page"

    # 2. Direct stream extractor must reject binary pixel garbage and accept valid BT/ET text
    binary_junk = b"\xff\xd8\xff\xe0(garbage\x00\x01binary)<deadbeef>\x89PNG\r\n"
    assert _extract_text_from_pdf_stream(binary_junk) == ""
    valid_stream = b"BT /F1 12 Tf 72 720 Td (Lesson One Algebra) Tj ET"
    assert "Lesson One Algebra" in _extract_text_from_pdf_stream(valid_stream)

    # 3. Corrupt %PDF- body must raise ValueError instead of silent requires_ocr_or_manual
    corrupt_pdf = b"%PDF-1.4\nThis is definitely corrupt binary garbage without valid xref or objects!!!"
    with pytest.raises(ValueError) as exc_corrupt:
        inspect_and_extract_pdf(corrupt_pdf, "corrupt.pdf")
    assert "تالف" in str(exc_corrupt.value) or "غير قابل" in str(exc_corrupt.value)

    # 4. Non-PDF file must still raise %PDF- signature ValueError
    with pytest.raises(ValueError) as exc_sig:
        inspect_and_extract_pdf(b"<html>not pdf</html>", "fake.pdf")
    assert "%PDF-" in str(exc_sig.value)


def test_indesign_lam_alef_normalization_without_corrupting_valid_words():
    corrupted_sample = (
        "األعداد النسبية واإلجابة الصحيحة باإلضافة إلى اآلتية واآلن "
        "المشكالت والمعادالت والعالقة بين األضالع على اإلطالق مثاالً "
        "الالزمة والالعب بااللتزام االلمنيوم االنعكاس االحتماالت مستقالن نالحظ"
    )
    repaired = normalize_indesign_arabic_ligatures(corrupted_sample)
    expected_tokens = [
        "الأعداد",
        "الإجابة",
        "بالإضافة",
        "الآتية",
        "والآن",
        "المشكلات",
        "المعادلات",
        "العلاقة",
        "الأضلاع",
        "الإطلاق",
        "مثالاً",
        "اللازمة",
        "واللاعب",
        "بالالتزام",
        "الالمنيوم",
        "الانعكاس",
        "الاحتمالات",
        "مستقلان",
        "نلاحظ",
    ]
    for tok in expected_tokens:
        assert tok in repaired, f"Expected repaired token {tok!r} in {repaired!r}"

    # Must be idempotent and never corrupt valid Arabic words
    valid_sample = (
        "الأستاذ يشرح الاتحاد والمعادلات والعلاقات والرياضيات وقالت الطالبة "
        "في الدرس الثالث والزاوية الثالثة بالطريقة وبالطرح مع الحلّ برتقالتين "
        "والوالدة في العالم والبالينية"
    )
    assert normalize_indesign_arabic_ligatures(valid_sample) == valid_sample
    assert normalize_indesign_arabic_ligatures(repaired) == repaired


def test_printed_page_number_detection_handles_diacritics_framing_and_sanity_bounds():
    # Diacritics on header page number + math integer in footer
    assert _detect_printed_page_number("40ً\nتدرب وحل مسائل حياتية\n5", 40, total_pages=196) == "40"
    assert _detect_printed_page_number("109ْ\nفكر\n3000", 109, total_pages=196) == "109"
    # Framing symbols & Arabic-Indic digits
    assert _detect_printed_page_number("الدرس الأول\n- ١٥ -", 15, total_pages=100) == "15"
    assert _detect_printed_page_number("[ 7 ]\nمحتوى الدرس", 7, total_pages=100) == "7"
    assert _detect_printed_page_number("صفحة 24\nنص الدرس", 24, total_pages=100) == "24"
    # Reject year numbers and cover grade metadata
    assert _detect_printed_page_number("مقدمة\n2024", 2, total_pages=100) == "2"
    cover_txt = "جمهورية العراق\nوزارة التربية\nتنقيح\nللصف الثاني المتوسط\n8"
    assert _detect_printed_page_number(cover_txt, 1, total_pages=196) == "1"


def test_math_ocr_ambiguity_detector_precision():
    # Clean prose with lesson codes, years, normal dates, and English slashes -> zero ambiguities
    clean_prose = (
        "الفصل الأول: الدرس [1-1] والدرس 2-3 و]1-4[ "
        "للعام الدراسي 2025-2026 وتاريخ 12/05/2025 "
        "باستعمال 1000 متر و 1848 خطوة (and/or km/h)."
    )
    assert detect_ocr_ambiguities(clean_prose) == []

    # Genuine math notation -> flagged as math_symbols_and_fractions
    for expr in [
        "احسب قيمة 3/4 + 1/2 = 5/4",
        "الكتابة العلمية: 2.39 × 10^5",
        "ناتج القسمة 15 ÷ 3 = 5",
        "مساحة الدائرة πr^2 حيث √25 = 5",
        r"الكسر \frac{a}{b} مع رمز ÷ ؟",
    ]:
        ambs = detect_ocr_ambiguities(expr)
        types = {a["type"] for a in ambs}
        assert "math_symbols_and_fractions" in types, f"Expected math ambiguity for {expr!r}, got {ambs}"

    # Scrambled cover date -> flagged as dates_and_chronology
    date_ambs = detect_ocr_ambiguities("الطبعة السابعة م202٥/ ٤٤١هـ7")
    assert any(a["type"] == "dates_and_chronology" for a in date_ambs)


def test_ocr_pdf_page_with_ai_no_placeholder_when_offline(monkeypatch):
    monkeypatch.setenv("OMNIROUTE_BASE_URL", "")
    monkeypatch.setenv("OMNIROUTE_API_KEY", "")
    monkeypatch.setenv("OMNIROUTE_ALLOW_KEYLESS", "0")
    monkeypatch.delenv("NVIDIA_API_KEYS", raising=False)

    # 1. Empty fallback + offline AI -> extracted=False and extractedText=""
    empty_res = ai_service.ocr_pdf_page_with_ai(
        image_png_bytes=b"\x89PNG\r\n\x1a\n",
        fallback_text="",
        page_number=1,
        context_snap={"subject": "الرياضيات", "grade": "الثاني المتوسط"},
    )
    assert empty_res["extracted"] is False
    assert empty_res["extractedText"] == ""
    assert "[" not in empty_res["extractedText"]

    # 2. Non-empty fallback + offline AI -> preserves fallback_text and sets extracted=False
    preserved_res = ai_service.ocr_pdf_page_with_ai(
        image_png_bytes=None,
        fallback_text="  نص مستخرج مسبقاً من الصفحة  ",
        page_number=2,
        context_snap={"subject": "الرياضيات"},
    )
    assert preserved_res["extracted"] is False
    assert preserved_res["extractedText"] == "نص مستخرج مسبقاً من الصفحة"

    # 3. Mock live Vision OCR success -> extracted=True
    monkeypatch.setattr(
        ai_service,
        "call_llm_json",
        lambda *args, **kwargs: (
            {"extractedText": "حل المعادلة س + 3 = 7", "printedPageNumber": "14", "notes": "واضح"},
            "nv-nemotron-3-5-super-vl-120b",
        ),
    )
    live_res = ai_service.ocr_pdf_page_with_ai(
        image_png_bytes=b"png",
        fallback_text="",
        page_number=14,
        context_snap={"subject": "الرياضيات"},
    )
    assert live_res["extracted"] is True
    assert live_res["extractedText"] == "حل المعادلة س + 3 = 7"
    assert live_res["printedPageNumber"] == "14"


def test_toc_prompt_budget_not_truncated_and_offline_fallback_parses_7_chapters(monkeypatch):
    # Construct a padded end-of-book TOC mirroring the 196-page Iraqi textbook layout (>2500 raw chars)
    pad = " " * 70
    toc_p195 = "\n".join([
        "195",
        f"Content{pad}الـمحتويــات",
        "73", "75", "79", "83", "87", "91",
        f"4{pad}: األعداد النسبية1 الفصل",
        f"6{pad}.الـدرس االول : ترتيب العمليات على االعداد النسبية",
        f"10{pad}.الدرس الثاني : القوى (االسس) السالبة والصورة العلمية للعدد",
        f"14{pad}.)الدرس الثالث : خصائص القوى (االسس",
        f"18{pad}.)الدرس الرابع : الكسور العشرية الدورية والصورة العلمية للعدد (استعمال الحاسبة",
        f"22{pad}.الدرس الخامس : تبسيط الجمل العددية الكسرية",
        f"27{pad}: األعداد الحقيقية2 الفصل",
        f"29{pad}.الـدرس االول : مفهوم األعداد الحقيقية وتمثيلها على مستقيم األعداد",
        f"33{pad}.الدرس الثاني : خصائص األعداد الحقيقية",
        f"37{pad}.الدرس الثالث : تبسيط الجمل العددية التي تحتوي على جذور تربيعية",
        f"41{pad}.الدرس الرابع : تطبيقات على نظرية فيثاغورس",
        f"45{pad}.الدرس الخامس : المستوى االحداثي",
        f"{pad}: المعادالت والمتباينات4 الفصل",
        f"{pad}. R الـدرس االول : حل معادالت من الدرجة االولى بمتغير واحد بخطوتين في",
        f"{pad}. R الدرس الثاني : حل معادالت من الدرجة االولى بمتغير واحد بعدة خطوات في",
        f"{pad}. R الدرس الثالث : حل معادالت من الدرجة الثانية بمتغير واحد في",
        f"{pad}. R الدرس الرابع : حل المتباينات الجبرية ذات الخطوتين في",
        f"{pad}. R الدرس الخامس : حل المتباينات الجبرية متعدِّدٍة الخطوات في",
        f"50{pad}: الحدوديات3 الفصل",
        f"52{pad}.الـدرس االول : جمع المقادير الجبرية وطرحها",
        f"56{pad}.الدرس الثاني : ضرب حد جبري في مقدار جبري",
        f"60{pad}.الدرس الثالث : ضرب المقادير الجبرية",
        f"64{pad}.الدرس الرابع : قسمة مقدار جبري على حد جبري",
        f"68{pad}.الدرس الخامس : تحليل المقادير الجبرية",
    ])
    toc_p196 = "\n".join([
        "196",
        f"Content{pad}الـمحتويــات",
        f"96{pad}: الهندسة والقياس5 الفصل",
        f"98{pad})الـدرس االول : عالقة الزوايا والمستقيمات ( نظريات",
        f"102{pad}الدرس الثاني : تطابق المثلثات",
        f"106{pad})الدرس الثالث : خواص المثلثات (متساوي الساقين، متساوي االضالع ، قائم الزاوية",
        f"110{pad}الدرس الرابع : متوازي األضالع والمعين وشبه المنحرف",
        f"114{pad}) الدرس الخامس : االسطوانة والكرة ( الخصائص ، المساحة السطحية ، الحجم",
        f"118{pad}الدرس السادس : مساحة االشكال المركبة المنتظمة وغير المنتظمة",
        f"123{pad}: الهندسة اإلحداثية6 الفصل",
        f"125{pad}الـدرس االول : تمثيل جدول دالة محددة في المستوي االحداثي",
        f"129{pad}الدرس الثاني : مقدمة في الدوال",
        f"133{pad}الدرس الثالث : الدوال الخطية",
        f"137{pad}الدرس الرابع : االنعكاس والدوران في المستوي االحداثي",
        f"141{pad}الدرس الخامس : االنسحاب في المستوي االحداثي",
        f"146{pad}: األحصاء واألحتماالت7الفصل",
        f"148{pad}مقياس النزعة المركزية والمدى : الـدرس االول",
        f"152{pad}تمثيل البيانات ببيان الشاربين : الدرس الثاني",
        f"156{pad}التجربة العشوائية : الدرس الثالث",
        f"160{pad}الحدث : الدرس الرابع",
        f"164{pad}األحتماالت : الدرس الخامس",
        f"168{pad}األحتمال التجريبي واألحتمال النظري : الدرس السادس",
        f"172{pad})خطة حل المسألة (تمثيل المسألة : الدرس السابع",
    ])
    assert len(toc_p195) > 2500 and len(toc_p196) > 2000

    pages_payload = [{"pdfPageNumber": i, "printedPageNumber": str(i), "text": f"صفحة {i}"} for i in range(1, 195)]
    pages_payload.append({"pdfPageNumber": 195, "printedPageNumber": "195", "text": toc_p195})
    pages_payload.append({"pdfPageNumber": 196, "printedPageNumber": "196", "text": toc_p196})

    # 1. Verify LLM prompt preserves end of both TOC pages (Chapters 3, 4, 6-5, and 7)
    captured: Dict[str, str] = {}

    def _fake_llm(system_prompt: str, user_prompt: str, **kwargs):
        captured["user_prompt"] = user_prompt
        return None, "deterministic_fallback"

    monkeypatch.setattr(ai_service, "call_llm_json", _fake_llm)
    res = ai_service.extract_chapters_and_lessons_with_ai(
        pages_payload,
        {"subject": "الرياضيات", "grade": "الثاني المتوسط"},
        "كتاب الرياضيات",
    )

    prompt = captured["user_prompt"]
    assert "تحليل المقادير الجبرية" in prompt
    assert "االنسحاب في المستوي االحداثي" in prompt
    assert "خطة حل المسألة" in prompt

    # 2. Verify offline deterministic fallback parses all 7 chapters and 38 lessons in order
    chs = res["chapters"]
    assert len(chs) == 7
    assert sum(len(c["lessons"]) for c in chs) == 38
    assert [c["pdfStartPage"] for c in chs] == [4, 27, 50, 73, 96, 123, 146]
    assert "الحدوديات" in chs[2]["title"]
    assert "المعادلات والمتباينات" in chs[3]["title"]
    assert chs[3]["lessons"][0]["pdfPageNumber"] == 75
    assert "الحدث" in chs[6]["lessons"][3]["title"]


def test_ai_status_modes_keyless_omniroute_and_render_yaml(monkeypatch):
    # 1. Fallback mode when unconfigured
    monkeypatch.setenv("OMNIROUTE_BASE_URL", "http://100.120.103.82:20128/v1")
    monkeypatch.setenv("OMNIROUTE_API_KEY", "")
    monkeypatch.setenv("OMNIROUTE_ALLOW_KEYLESS", "0")
    monkeypatch.delenv("NVIDIA_API_KEYS", raising=False)
    st_off = ai_service.get_ai_status()
    assert st_off["available"] is False
    assert st_off["mode"] == "fallback"
    assert st_off["fallbackAvailable"] is True

    # 2. Live mode with OMNIROUTE_API_KEY
    monkeypatch.setenv("OMNIROUTE_API_KEY", "sk-test-123")
    st_key = ai_service.get_ai_status()
    assert st_key["available"] is True
    assert st_key["mode"] == "live"

    # 3. Live mode with OMNIROUTE_ALLOW_KEYLESS=1 and empty OMNIROUTE_API_KEY
    monkeypatch.setenv("OMNIROUTE_API_KEY", "")
    monkeypatch.setenv("OMNIROUTE_ALLOW_KEYLESS", "1")
    st_keyless = ai_service.get_ai_status()
    assert st_keyless["available"] is True
    assert st_keyless["mode"] == "live"

    seen_calls: List[Dict[str, Any]] = []

    class _FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": json.dumps({"ok": True})}}]}

    class _FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json=None, headers=None):
            seen_calls.append({"url": url, "headers": headers})
            return _FakeResp()

    monkeypatch.setattr(ai_service.httpx, "Client", _FakeClient)
    parsed, model_used = ai_service.call_llm_json("sys", "usr")
    assert parsed == {"ok": True}
    assert model_used == ai_service.TEXT_MODELS[0]
    assert seen_calls and "Authorization" not in seen_calls[0]["headers"]

    # 4. render.yaml includes OMNIROUTE_API_KEY (sync: false) and OMNIROUTE_ALLOW_KEYLESS
    repo_root = Path(__file__).resolve().parents[2]
    render_yaml = (repo_root / "render.yaml").read_text(encoding="utf-8")
    assert "OMNIROUTE_API_KEY" in render_yaml
    assert "OMNIROUTE_ALLOW_KEYLESS" in render_yaml
