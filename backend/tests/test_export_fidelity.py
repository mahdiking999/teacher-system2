import io
import json
import os
import re
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pymupdf
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.models import PlanVersion
from backend.app.services.export_service import (
    _DOCX_CONTENT_WIDTH_DXA,
    _FONTS_DIR,
    generate_plan_docx_bytes,
    generate_plan_pdf_bytes,
    generate_plan_pptx_bytes,
    verify_exported_file_structure,
)
from backend.app.services.seed_service import ensure_initial_seed_data


_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_MOJIBAKE_CHARS = set("ǄǁǂƾØ")


def _norm_pdf_text(txt: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", txt)).strip()


def _rich_daily_plan_ar(num_phases: int = 5) -> tuple[dict, dict, dict]:
    phases = []
    for idx in range(1, num_phases + 1):
        phases.append(
            {
                "order": idx,
                "periodNumber": 1 if idx <= 3 else 2,
                "phaseName": f"المرحلة التفصيلية رقم {idx}",
                "materials": ["سبورة", "مسطرة", "بطاقات تعليمية"],
                "sourceRef": f"الكتاب الموثق ص {10 + idx}",
                "teacherActivity": f"شرح وتوضيح المفهوم التربوي رقم {idx} بالأمثلة الموجهة والحوار الصفي",
                "studentActivity": f"حل التمرين التفاعلي رقم {idx} ومناقشة خطوات التفكير مع الزملاء",
                "objective": f"هدف المرحلة {idx}: إتقان المهارة",
                "minutes": 5 if idx < num_phases else max(5, 45 - 5 * (num_phases - 1)),
            }
        )

    plan_snap = {
        "id": "pln_test_daily",
        "title": "خطة درس: المعادلات الخطية والتفكير البصري",
        "planType": "daily",
        "status": "approved",
        "version": 2,
        "approvedBy": "د. ليلى حسن",
        "teacherName": "د. ليلى حسن",
        "schoolName": "ثانوية المتميزات",
        "sectionName": "الشعبة أ",
        "planningDate": "2026-10-11",
        "periodsCount": 1,
        "periodMinutes": 45,
        "totalAllocatedMinutes": 45,
        "objectives": [
            "أن يحل الطالب المعادلات الخطية بدقة عالية.",
            "أن يشرح الطالب أولويات العمليات الحسابية.",
        ],
        "priorKnowledge": "العمليات الحسابية على الأعداد الصحيحة.",
        "teacherRole": "التوجيه والنمذجة وتقديم التغذية الراجعة الفورية.",
        "studentRole": "الاستكشاف النشط وحل المسائل وتبرير الخطوات.",
        "teachingTools": ["سبورة", "أقلام ملونة", "مسطرة"],
        "phases": phases,
        "formativeAssessment": "حل المسألة (15 + 9) / 3 = 8 مع شرح الخطوات.",
        "differentiation": "دعم متدرج للطلبة المحتاجين ومسائل إثرائية للمتفوقين.",
        "homework": "حل تمرينات الكتاب ص 19.",
        "homeEnrichmentMinutes": 20,
        "planningNotes": "ملاحظة التخطيط: التأكد من جاهزية البطاقات قبل الحصة.",
        "referencesNote": "الكتاب المدرسي المعتمد — الطبعة الخامسة 2026",
        "subjectItems": [
            {"domain": "math", "expression": "(15 + 9) / 3", "expectedAnswer": "8", "unit": "سم"},
            {"domain": "math", "expression": "-5 + 3", "expectedAnswer": "-2", "unit": "م"},
            {"domain": "math", "expression": "2x + 3", "expectedAnswer": "11", "unit": ""},
            {
                "domain": "literature",
                "quote": "العلم يبني بيوتاً لا عماد لها",
                "attributedTo": "أحمد شوقي",
                "rubric": "سلامة الاستشهاد ووضوح الفكرة",
            },
        ],
        "provenanceLabel": "موثّق من الكتاب المدرسي",
    }
    ctx_snap = {
        "subject": "الرياضيات",
        "grade": "الصف الأول المتوسط",
        "country": "العراق",
        "curriculumName": "منهج الرياضيات الحديث",
        "language": "ar",
        "year": "2026",
        "edition": "الخامسة",
    }
    review_snap = {
        "findings": [
            {
                "category": "PASSED",
                "title": "توزيع الزمن صحيح",
                "description": "5 + 8 + 15 + 10 + 7 = 45 دقيقة · متوافق مع 1 حصة.",
                "fieldTarget": "phases",
            },
            {
                "category": "SOURCE_WARNING",
                "title": "تنبيه مراجعة مصدر",
                "description": "يرجى مطابقة رقم الصفحة مع النسخة الورقية.",
                "fieldTarget": "referencesNote",
            },
        ]
    }
    return plan_snap, ctx_snap, review_snap


def _rich_weekly_or_five_day_ar(plan_type: str = "weekly", stale_total: int | None = 45, extra_findings: int = 2) -> tuple[dict, dict, dict]:
    days = [
        {
            "dayName": "الأحد",
            "isHoliday": False,
            "lessonTitle": "المعادلات الخطية",
            "objectives": "حل معادلة من الدرجة الأولى",
            "activities": "تمثيل بصري على السبورة",
            "assessment": "بطاقة خروج",
            "durationMinutes": 45,
        },
        {
            "dayName": "الاثنين",
            "isHoliday": False,
            "lessonTitle": "تطبيقات حياتية",
            "objectives": "نمذجة مسألة لفظية",
            "activities": "عمل تعاوني بالبطاقات",
            "assessment": "مناقشة صفية",
            "minutes": 45,
        },
        {
            "dayName": "الثلاثاء",
            "isHoliday": False,
            "lessonTitle": "المتباينات",
            "objectives": "تمثيل المتباينة على خط الأعداد",
            "activities": "ورقة عمل موجهة",
            "assessment": "تمرين فردي",
            "durationMinutes": 45,
        },
        {
            "dayName": "الأربعاء",
            "isHoliday": False,
            "lessonTitle": "حل المتباينات",
            "objectives": "مقارنة استراتيجيتين للحل",
            "activities": "نشاط ثنائي",
            "assessment": "سؤال تقويمي",
            "minutes": 45,
        },
        {
            "dayName": "الخميس",
            "isHoliday": False,
            "lessonTitle": "مراجعة شاملة",
            "objectives": "تثبيت المفاهيم الأساسية",
            "activities": "اختبار قصير وتغذية راجعة",
            "assessment": "اختبار تكويني",
            "durationMinutes": 45,
        },
    ]
    if plan_type == "weekly":
        days.extend(
            [
                {"dayName": "الجمعة", "isHoliday": True, "lessonTitle": "", "activities": "", "assessment": "", "minutes": 0},
                {"dayName": "السبت", "isHoliday": True, "lessonTitle": "", "activities": "", "assessment": "", "minutes": 0},
            ]
        )

    plan_snap = {
        "id": f"pln_{plan_type}",
        "title": "الخطة الأسبوعية الشاملة" if plan_type == "weekly" else "خطة خمسة أيام للتدريس",
        "planType": plan_type,
        "status": "reviewed",
        "version": 1,
        "teacherName": "أ. أحمد علي",
        "schoolName": "مدرسة المتفوقين",
        "sectionName": "الشعبة ب",
        "planningDate": "2026-10-12",
        "periodsCount": 1,
        "periodMinutes": 45,
        "totalAllocatedMinutes": stale_total,
        "objectives": [f"الهدف العام رقم {i}: بناء الفهم المتدرج عبر أيام الأسبوع." for i in range(1, 5)],
        "priorKnowledge": "المهارات الحسابية السابقة.",
        "teacherRole": "تيسير النقاشات اليومية ومتابعة التقويم.",
        "studentRole": "المشاركة الفاعلة في الأنشطة الصفية.",
        "teachingTools": ["سبورة", "بطاقات تعليمية"],
        "scheduleDays": days,
        "formativeAssessment": "تقويم يومي مستمر وفق محكات واضحة.",
        "differentiation": "أنشطة إثرائية ودعم فردي.",
        "homework": "تدريبات منزلية أسبوعية.",
        "homeEnrichmentMinutes": 30,
        "planningNotes": "ملاحظات الأسبوع: تخصيص 10 دقائق للمراجعة التشخيصية.",
        "referencesNote": "دليل المعلم — الفصل الأول",
        "subjectItems": [
            {
                "domain": "science",
                "hypothesis": "يزداد معدل التبخر بارتفاع درجة الحرارة",
                "variables": "درجة الحرارة / الزمن",
                "unit": "س",
                "safety": "إشراف المعلم",
            },
            {
                "domain": "history",
                "events": [
                    {"year": "622 م", "event": "الهجرة النبوية", "evidence": "الوثيقة التاريخية"},
                    {"year": "632 م", "event": "حجة الوداع", "evidence": "المصادر المعتمدة"},
                ],
            },
        ],
    }
    ctx_snap = {
        "subject": "الرياضيات",
        "grade": "الصف الأول المتوسط",
        "country": "العراق",
        "curriculumName": "المنهج الوطني",
        "language": "ar",
        "year": "2026",
        "edition": "الأولى",
    }
    findings = [
        {
            "category": "PASSED",
            "title": f"بند تدقيق رقم {i}",
            "description": f"مجموع زمن الجدول = 225 دقيقة متوافق مع الخطة رقم {i} وتوزيع المراحل المفصل.",
            "fieldTarget": "scheduleDays",
        }
        for i in range(1, extra_findings + 1)
    ]
    return plan_snap, ctx_snap, {"findings": findings}


def test_bundled_ofl_fonts_and_tounicode_cmap_clean():
    assert (_FONTS_DIR / "Tajawal-Regular.ttf").is_file()
    assert (_FONTS_DIR / "Tajawal-Bold.ttf").is_file()
    assert (_FONTS_DIR / "OFL.txt").is_file()

    plan_snap, ctx_snap, review_snap = _rich_daily_plan_ar(num_phases=5)
    plan_snap["objectives"].append("تعلّم المقرّر وتأكّد من الإسلام والإخلاص لا للأخطاء، سجل موثّق — ١٢٣٤٥.")
    pdf_bytes = generate_plan_pdf_bytes(plan_snap, ctx_snap, review_snap, "human_verified")

    chk = verify_exported_file_structure(pdf_bytes, "pdf")
    assert chk["passed"] is True
    assert chk["controlCharsCount"] == 0
    assert chk["mojibakeCharsCount"] == 0

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        font_names = " ".join(f[3] for p in doc for f in p.get_fonts())
        assert "Tajawal" in font_names

        raw_txt = "".join(p.get_text("text") or "" for p in doc)
        assert not _CONTROL_CHAR_RE.findall(raw_txt)
        assert not any(ch in raw_txt for ch in _MOJIBAKE_CHARS)

        nfkc = _norm_pdf_text(raw_txt)
        no_diac = "".join(c for c in nfkc if unicodedata.category(c) != "Mn")
        for expected in [
            "المعادلات",
            "الخطية",
            "التفكير",
            "البصري",
            "المقرر",
            "الإسلام",
            "للأخطاء",
            "موثق",
            "يشرح",
            "متدرج",
            "خارج",
            "التوجيه",
            "الاستكشاف",
            "(15 + 9) / 3 = 8",
            "2026-10-11",
            "صفحة 1 من",
        ]:
            assert expected in no_diac, f"Missing extracted token {expected!r} in:\n{no_diac}"


def test_multipage_pdfs_have_zero_ghost_fills():
    # 1. Daily RTL multi-page (18 phases -> spans multiple pages)
    daily_p, daily_c, daily_r = _rich_daily_plan_ar(num_phases=18)
    daily_pdf = generate_plan_pdf_bytes(daily_p, daily_c, daily_r, "human_verified")

    # 2. Five-day RTL multi-page (long findings push onto Page 2+)
    five_p, five_c, five_r = _rich_weekly_or_five_day_ar("five_day", stale_total=None, extra_findings=18)
    five_pdf = generate_plan_pdf_bytes(five_p, five_c, five_r, "unverified_draft")

    # 3. Weekly RTL multi-page
    weekly_p, weekly_c, weekly_r = _rich_weekly_or_five_day_ar("weekly", stale_total=45, extra_findings=18)
    weekly_pdf = generate_plan_pdf_bytes(weekly_p, weekly_c, weekly_r, "human_verified")

    # 4. Report RTL multi-page (many documentation gaps -> spills onto Page 2+)
    report_summary = {
        "totalPlans": 12,
        "reviewedPlans": 8,
        "draftPlans": 4,
        "approvedPlans": 5,
        "exportsCount": 9,
        "patternSummary": [
            {"label": f"نمط تخطيط رقم {i}", "planned": i, "reviewed": i, "exported": 1}
            for i in range(1, 10)
        ],
        "documentationGaps": [f"فجوة توثيق رقم {i}: يرجى استكمال بيانات الطبعة والمصدر المعتمد." for i in range(1, 35)],
        "disclaimer": "المؤشرات تقيس تنظيم التخطيط واكتماله للمعلم فقط.",
    }
    report_pdf = generate_plan_pdf_bytes({}, daily_c, {"findings": []}, "unverified_draft", is_report=True, report_summary=report_summary)

    for label, pdf_bytes in [
        ("daily_rtl", daily_pdf),
        ("five_day_rtl", five_pdf),
        ("weekly_rtl", weekly_pdf),
        ("report_rtl", report_pdf),
    ]:
        with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
            assert len(doc) >= 2, f"{label} expected >= 2 pages, got {len(doc)}"
            for page_idx in range(1, len(doc)):
                page = doc[page_idx]
                for dr in page.get_drawings():
                    fill = dr.get("fill")
                    if not fill:
                        continue
                    r, g, b = fill
                    # Never emit yellow banner/badge strip (#FEF3C7 or #F59E0B) on continuation pages
                    is_yellow = r > 0.85 and g > 0.55 and b < 0.85 and (r - b) > 0.1
                    assert not is_yellow, f"{label} page {page_idx + 1} has ghost yellow fill {fill}"
                    # Check dark-green #154434 (~0.082, 0.267, 0.204): only permitted if a real <th> row starts at that rect
                    is_dark_green = r < 0.15 and 0.20 < g < 0.35 and 0.15 < b < 0.28
                    if is_dark_green:
                        rect = dr.get("rect")
                        words_in_rect = [
                            w[4]
                            for w in page.get_text("words")
                            if pymupdf.Rect(w[:4]).intersects(rect)
                        ]
                        assert words_in_rect, f"{label} page {page_idx + 1} has empty ghost #154434 bar at {rect}"


def test_pdf_bidi_math_ordering_and_no_orphaned_bullet():
    plan_snap, ctx_snap, review_snap = _rich_daily_plan_ar(num_phases=5)
    pdf_bytes = generate_plan_pdf_bytes(plan_snap, ctx_snap, review_snap, "human_verified")

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        # Locate words across pages for `(15 + 9) / 3 = 8 سم`
        all_words = []
        for p in doc:
            all_words.extend(p.get_text("words"))

        norm_words = [(w[0], w[1], w[2], w[3], unicodedata.normalize("NFKC", w[4])) for w in all_words]
        # Find the line containing '(15' and '8' from the math item (y where 'سم' appears on same y)
        sm_candidates = [w for w in norm_words if w[4] == "سم"]
        assert sm_candidates, "Expected unit 'سم' in extracted PDF words"
        math_y = sm_candidates[0][1]
        row_words = sorted([w for w in norm_words if abs(w[1] - math_y) < 3.0], key=lambda w: w[0])
        tokens = [w[4] for w in row_words]

        # Visual left-to-right order on the RTL line: unit 'سم', then '(15 + 9) / 3 = 8', then '•' on right!
        assert tokens == ["سم", "(15", "+", "9)", "/", "3", "=", "8", "•"], f"Unexpected visual token order: {tokens}"
        bullet_word = row_words[-1]
        assert bullet_word[0] > 450, f"Bullet '•' should sit near right margin (>450), got x0={bullet_word[0]}"

        # Verify numbered objectives '1.' sit on right margin, not orphaned on left
        one_dots = [w for w in norm_words if w[4] in ("1.", "1") and w[0] > 450]
        assert one_dots, "Expected objective index '1' anchored near right margin (>450)"


def test_duration_consistency_weekly_and_five_day_docx_and_pdf():
    for plan_type in ("weekly", "five_day"):
        for stale_val in (None, 0, 45):
            plan_snap, ctx_snap, review_snap = _rich_weekly_or_five_day_ar(plan_type, stale_total=stale_val, extra_findings=2)

            docx_bytes = generate_plan_docx_bytes(plan_snap, ctx_snap, review_snap, "human_verified")
            with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as zf:
                doc_xml = zf.read("word/document.xml").decode("utf-8")
                assert "225 دقيقة" in doc_xml
                assert "45 دقيقة" not in doc_xml

            pdf_bytes = generate_plan_pdf_bytes(plan_snap, ctx_snap, review_snap, "human_verified")
            with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
                txt = _norm_pdf_text(doc[0].get_text("text"))
                assert "225 دقيقة" in txt
                # Top summary table must not show '45 دقيقة'
                assert "45 دقيقة" not in txt.split("الأهداف التعليمية")[0]


def test_missing_fields_and_non_math_subject_items_in_docx_and_pdf():
    plan_snap, ctx_snap, review_snap = _rich_weekly_or_five_day_ar("weekly", stale_total=0, extra_findings=2)
    daily_p, _, daily_r = _rich_daily_plan_ar(num_phases=5)

    for label, p_snap, r_snap in [("daily", daily_p, daily_r), ("weekly", plan_snap, review_snap)]:
        docx_bytes = generate_plan_docx_bytes(p_snap, ctx_snap, r_snap, "human_verified")
        with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8")
            assert p_snap["planningNotes"] in doc_xml, f"{label} DOCX missing planningNotes"
            assert p_snap["referencesNote"] in doc_xml, f"{label} DOCX missing referencesNote"
            assert p_snap["teacherRole"] in doc_xml, f"{label} DOCX missing teacherRole"
            assert p_snap["studentRole"] in doc_xml, f"{label} DOCX missing studentRole"
            assert f"{p_snap['homeEnrichmentMinutes']} دقيقة" in doc_xml, f"{label} DOCX missing homeEnrichmentMinutes"
            assert '{"domain":' not in doc_xml and "['سبورة'" not in doc_xml
            if label == "daily":
                assert "هدف المرحلة 1" in doc_xml
                assert "سبورة، مسطرة، بطاقات تعليمية" in doc_xml
            else:
                assert "حل معادلة من الدرجة الأولى" in doc_xml
                assert "يزداد معدل التبخر" in doc_xml
                assert "الهجرة النبوية" in doc_xml

        pdf_bytes = generate_plan_pdf_bytes(p_snap, ctx_snap, r_snap, "human_verified")
        with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
            full_txt = _norm_pdf_text("".join(pg.get_text("text") for pg in doc))
            assert p_snap["planningNotes"] in full_txt, f"{label} PDF missing planningNotes"
            assert p_snap["referencesNote"] in full_txt, f"{label} PDF missing referencesNote"
            assert p_snap["teacherRole"] in full_txt, f"{label} PDF missing teacherRole"
            assert p_snap["studentRole"] in full_txt, f"{label} PDF missing studentRole"
            assert f"{p_snap['homeEnrichmentMinutes']} دقيقة" in full_txt, f"{label} PDF missing homeEnrichmentMinutes"
            assert '{"domain":' not in full_txt and "['سبورة'" not in full_txt
            if label == "daily":
                assert "هدف المرحلة 1" in full_txt
                assert "referencesNote" in full_txt  # fieldTarget in audit table
            else:
                assert "حل معادلة من الدرجة الأولى" in full_txt
                assert "يزداد معدل التبخر" in full_txt
                assert "الهجرة النبوية" in full_txt


def test_docx_table_grid_and_cell_widths():
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    w_attr = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}w"
    type_attr = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type"

    plan_snap, ctx_snap, review_snap = _rich_daily_plan_ar(num_phases=5)
    for is_rtl, lang in [(True, "ar"), (False, "en")]:
        c = dict(ctx_snap, language=lang)
        docx_bytes = generate_plan_docx_bytes(plan_snap, c, review_snap, "human_verified")
        chk = verify_exported_file_structure(docx_bytes, "docx")
        assert chk["passed"] is True
        with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as zf:
            root = ET.fromstring(zf.read("word/document.xml"))
            tables = root.findall(".//w:tbl", ns)
            assert len(tables) >= 3
            for tbl in tables:
                tbl_pr = tbl.find("w:tblPr", ns)
                assert tbl_pr is not None
                has_bidi = tbl_pr.find("w:bidiVisual", ns) is not None
                assert has_bidi is is_rtl

                tbl_grid = tbl.find("w:tblGrid", ns)
                assert tbl_grid is not None
                grid_widths = [int(gc.attrib[w_attr]) for gc in tbl_grid.findall("w:gridCol", ns)]
                assert len(grid_widths) >= 2
                assert sum(grid_widths) == _DOCX_CONTENT_WIDTH_DXA

                for tr in tbl.findall("w:tr", ns):
                    tcs = tr.findall("w:tc", ns)
                    assert len(tcs) == len(grid_widths)
                    for idx, tc in enumerate(tcs):
                        tc_w = tc.find("w:tcPr/w:tcW", ns)
                        assert tc_w is not None
                        assert tc_w.attrib.get(type_attr) == "dxa"
                        assert int(tc_w.attrib[w_attr]) == grid_widths[idx]

            sect_bidi = root.find(".//w:sectPr/w:bidi", ns) is not None
            assert sect_bidi is is_rtl


def test_pptx_rtl_comparison_phases_and_holidays():
    # 1. Comparison layout with < 2 lines AND > 8 overflow lines in RTL and LTR
    for rtl_mode, lang in [(True, "ar"), (False, "en")]:
        plan_cmp = {
            "title": "Comparison Deck",
            "presentationSettings": {"textDirection": "rtl" if rtl_mode else "ltr", "layoutStyle": "comparison"},
            "slides": [
                {"title": "Single Line Slide", "content": "Only one line here"},
                {"title": "Overflow Slide", "content": "\n".join(f"Point {i}: Detailed item text" for i in range(1, 10))},
            ],
        }
        ctx = {"subject": "Math", "grade": "Grade 7", "country": "IQ", "language": lang}
        pptx_bytes = generate_plan_pptx_bytes(plan_cmp, ctx, "human_verified")
        with zipfile.ZipFile(io.BytesIO(pptx_bytes), "r") as zf:
            pres_xml = zf.read("ppt/presentation.xml").decode("utf-8")
            assert ('rtl="1"' in pres_xml) is rtl_mode

            for sf in ("ppt/slides/slide1.xml", "ppt/slides/slide2.xml", "ppt/slides/slide3.xml"):
                s_xml = zf.read(sf).decode("utf-8")
                assert "CompareCol1" in s_xml and "CompareCol2" in s_xml, f"{sf} reverted from comparison layout!"
                assert "MainContent" not in s_xml
                # Verify RTL vs LTR X-coordinates
                root = ET.fromstring(s_xml)
                ns_p = {
                    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
                    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
                }
                pos = {}
                for sp in root.findall(".//p:sp", ns_p):
                    cnv = sp.find(".//p:cNvPr", ns_p)
                    off = sp.find(".//a:xfrm/a:off", ns_p)
                    if cnv is not None and off is not None and cnv.attrib.get("name") in ("CompareCol1", "CompareCol2"):
                        pos[cnv.attrib["name"]] = int(off.attrib["x"])
                if rtl_mode:
                    assert pos["CompareCol1"] > pos["CompareCol2"]
                else:
                    assert pos["CompareCol1"] < pos["CompareCol2"]

    # 2. Auto-generated 5-phase daily PPTX has ZERO phase duplication across Slide 3 and Slide 4
    daily_p, daily_c, _ = _rich_daily_plan_ar(num_phases=5)
    daily_pptx = generate_plan_pptx_bytes(daily_p, daily_c, "human_verified")
    with zipfile.ZipFile(io.BytesIO(daily_pptx), "r") as zf:
        s3 = zf.read("ppt/slides/slide3.xml").decode("utf-8")
        s4 = zf.read("ppt/slides/slide4.xml").decode("utf-8")
        assert "المرحلة التفصيلية رقم 1" in s3 and "المرحلة التفصيلية رقم 2" in s3
        assert "المرحلة التفصيلية رقم 3" not in s3
        assert "المرحلة التفصيلية رقم 3" in s4 and "المرحلة التفصيلية رقم 4" in s4 and "المرحلة التفصيلية رقم 5" in s4
        assert "المرحلة التفصيلية رقم 2" not in s4

    # 3. Weekly PPTX renders holiday rows cleanly instead of skipping them
    weekly_p, weekly_c, _ = _rich_weekly_or_five_day_ar("weekly", stale_total=225)
    weekly_pptx = generate_plan_pptx_bytes(weekly_p, weekly_c, "human_verified")
    with zipfile.ZipFile(io.BytesIO(weekly_pptx), "r") as zf:
        all_slide_xml = "\n".join(
            zf.read(n).decode("utf-8") for n in zf.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")
        )
        assert "الجمعة" in all_slide_xml
        assert "السبت" in all_slide_xml
        assert "عطلة" in all_slide_xml


def test_localization_en_and_fr_across_docx_pptx_pdf():
    for lang, expected_footer, expected_cont in [
        ("en", "Page 1 of", "(cont.)"),
        ("fr", "Page 1 sur", "(suite)"),
    ]:
        plan_snap = {
            "title": "Linear Equations Lesson Plan",
            "planType": "daily",
            "status": "approved",
            "version": 1,
            "approvedBy": "Dr. Layla",
            "teacherName": "أ. ليلى حسن",  # Mixed Arabic teacher name inside LTR doc
            "schoolName": "Excellence High School",
            "sectionName": "Section A",
            "planningDate": "2026-10-15",
            "periodsCount": 1,
            "periodMinutes": 45,
            "objectives": ["Solve single-variable linear equations."],
            "priorKnowledge": "Basic arithmetic operations.",
            "teacherRole": "Model problem-solving steps.",
            "studentRole": "Explain reasoning in pairs.",
            "teachingTools": ["Whiteboard", "Cards"],
            "phases": [
                {
                    "order": 1,
                    "periodNumber": 1,
                    "phaseName": "Warm-up",
                    "materials": "Cards",
                    "sourceRef": "Ch. 1 p. 12",
                    "teacherActivity": "Pose diagnostic prompt",
                    "studentActivity": "Respond orally",
                    "objective": "Activate prior knowledge",
                    "minutes": 45,
                }
            ],
            "formativeAssessment": "Exit ticket problem",
            "differentiation": "Tiered worksheet",
            "homework": "Exercises 1-5",
            "homeEnrichmentMinutes": 15,
            "planningNotes": "Prepare visual cards ahead of time.",
            "referencesNote": "Official Textbook 2026",
            "subjectItems": [{"domain": "math", "expression": "(15 + 9) / 3", "expectedAnswer": "8", "unit": "cm"}],
        }
        ctx_snap = {
            "subject": "الرياضيات" if lang == "en" else "Mathématiques",
            "grade": "Grade 7",
            "country": "Iraq",
            "curriculumName": "Modern Math",
            "language": lang,
            "year": "2026",
            "edition": "1st Edition",
        }
        review_snap = {"findings": [{"category": "PASSED", "title": "Time valid", "description": "45 min", "fieldTarget": "phases"}]}

        forbidden_ar_headers = [
            "الأهداف التعليمية",
            "المحتوى التخصصي",
            "تقرير التخطيط",
            "حالة الإصدار",
            "سجل التدقيق التربوي",
            "المتطلبات السابقة",
        ]

        # PDF
        pdf_b = generate_plan_pdf_bytes(plan_snap, ctx_snap, review_snap, "human_verified")
        assert verify_exported_file_structure(pdf_b, "pdf")["passed"] is True
        with pymupdf.open(stream=pdf_b, filetype="pdf") as doc:
            txt = _norm_pdf_text("".join(p.get_text("text") for p in doc))
            assert expected_footer in txt
            assert "1st Edition" in txt
            assert "ليلى حسن" in txt
            for ar_h in forbidden_ar_headers:
                assert ar_h not in txt

        # DOCX
        docx_b = generate_plan_docx_bytes(plan_snap, ctx_snap, review_snap, "human_verified")
        with zipfile.ZipFile(io.BytesIO(docx_b), "r") as zf:
            xml = zf.read("word/document.xml").decode("utf-8")
            for ar_h in forbidden_ar_headers:
                assert ar_h not in xml

        # Report PDF & DOCX
        rep_summary = {
            "totalPlans": 3,
            "reviewedPlans": 2,
            "draftPlans": 1,
            "approvedPlans": 1,
            "exportsCount": 2,
            "patternSummary": [{"label": "Daily", "planned": 3, "reviewed": 2, "exported": 2}],
            "documentationGaps": ["None"],
        }
        rep_pdf_b = generate_plan_pdf_bytes({}, ctx_snap, {"findings": []}, "human_verified", is_report=True, report_summary=rep_summary)
        with pymupdf.open(stream=rep_pdf_b, filetype="pdf") as doc:
            rtxt = _norm_pdf_text("".join(p.get_text("text") for p in doc))
            assert expected_footer in rtxt
            for ar_h in forbidden_ar_headers:
                assert ar_h not in rtxt

        # PPTX overflow continuation suffix localization
        overflow_plan = dict(plan_snap, slides=[{"title": "Long Slide", "content": "\n".join(f"Line {i}" for i in range(1, 11))}])
        pptx_b = generate_plan_pptx_bytes(overflow_plan, ctx_snap, "human_verified")
        with zipfile.ZipFile(io.BytesIO(pptx_b), "r") as zf:
            s2 = zf.read("ppt/slides/slide2.xml").decode("utf-8")
            assert expected_cont in s2
            assert "(تابع)" not in s2


def test_seed_service_plan_version_preserves_new_fields_isolated():
    mem_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=mem_engine)
    MemSession = sessionmaker(autocommit=False, autoflush=False, bind=mem_engine)
    db = MemSession()
    try:
        ensure_initial_seed_data(db, force=True)
        for pid in ("pln_daily_demo_a", "pln_five_day_demo", "pln_weekly_demo"):
            pver = db.query(PlanVersion).filter(PlanVersion.plan_id == pid, PlanVersion.version_number == 1).first()
            assert pver is not None
            payload = pver.plan_payload
            for required_key in (
                "totalAllocatedMinutes",
                "homeEnrichmentMinutes",
                "referencesNote",
                "planningNotes",
                "teacherName",
                "schoolName",
                "sectionName",
                "teacherRole",
                "studentRole",
            ):
                assert required_key in payload, f"{pid} PlanVersion v1 missing {required_key}"

        weekly_v1 = db.query(PlanVersion).filter(PlanVersion.plan_id == "pln_weekly_demo", PlanVersion.version_number == 1).first()
        assert weekly_v1.plan_payload["totalAllocatedMinutes"] == 225
        pdf_b = generate_plan_pdf_bytes(weekly_v1.plan_payload, weekly_v1.context_snapshot, {"findings": []}, "unverified_draft")
        with pymupdf.open(stream=pdf_b, filetype="pdf") as doc:
            txt = _norm_pdf_text(doc[0].get_text("text"))
            assert "225 دقيقة" in txt
            assert "45 دقيقة" not in txt.split("الأهداف التعليمية")[0]
    finally:
        db.close()
        mem_engine.dispose()
