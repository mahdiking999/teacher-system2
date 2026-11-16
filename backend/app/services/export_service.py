import hashlib
import html as html_mod
import io
import json
import textwrap
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

try:
    import pymupdf
except ImportError:
    pymupdf = None


def _xml_escape(val: Any) -> str:
    s = str(val if val is not None else "")
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _html_escape(val: Any) -> str:
    return html_mod.escape(str(val if val is not None else ""))


def _is_rtl_lang(lang: str) -> bool:
    return str(lang or "ar").lower().startswith(("ar", "he", "fa", "ur", "ku"))


def _format_context_banner(context_snap: Dict[str, Any]) -> str:
    subj = context_snap.get("subject") or "غير محدد"
    grade = context_snap.get("grade") or "غير محدد"
    country = context_snap.get("country") or "غير محدد"
    curr = context_snap.get("curriculumName") or "غير محدد"
    lang = context_snap.get("language") or "ar"
    year = context_snap.get("year") or "غير مدخلة"
    edition = context_snap.get("edition") or "غير مدخلة"
    return (
        f"المادة: {subj} | الصف/المرحلة: {grade} | البلد: {country} | "
        f"المنهج: {curr} | اللغة: {lang} | السنة: {year} | الطبعة: {edition}"
    )


def _format_approval_badge(plan_snap: Dict[str, Any], source_status: str) -> str:
    status = plan_snap.get("status", "draft")
    ver = plan_snap.get("version", 1)
    prov = plan_snap.get("provenanceLabel", "مثال توضيحي غير موثق من الكتاب")
    if status == "approved":
        approver = plan_snap.get("approvedBy") or plan_snap.get("teacherName") or "المعلم المراجع"
        return f"حالة الإصدار (v{ver}): معتمد تربويًا بواسطة ({approver}) | حالة المصدر: {source_status} | النسبة: {prov}"
    return f"حالة الإصدار (v{ver}): مسودة غير معتمدة ({status}) — لا تحمل ختم اعتماد رسمي | حالة المصدر: {source_status} | {prov}"


# ==============================================================================
# 1. REAL OOXML DOCX GENERATOR (.docx)
# ==============================================================================

def _w_p(text: str, rtl: bool = True, bold: bool = False, size_half_pts: int = 24, color_hex: str = "111827") -> str:
    bidi_tag = "<w:bidi/>" if rtl else ""
    jc_val = "right" if rtl else "left"
    rtl_run = "<w:rtl/>" if rtl else ""
    b_tag = "<w:b/><w:bCs/>" if bold else ""
    return (
        f"<w:p>"
        f"<w:pPr>{bidi_tag}<w:jc w:val=\"{jc_val}\"/><w:spacing w:before=\"80\" w:after=\"80\"/></w:pPr>"
        f"<w:r>"
        f"<w:rPr><w:rFonts w:ascii=\"Arial\" w:hAnsi=\"Arial\" w:cs=\"Arial\"/>"
        f"{b_tag}<w:color w:val=\"{color_hex}\"/><w:sz w:val=\"{size_half_pts}\"/><w:szCs w:val=\"{size_half_pts}\"/>{rtl_run}</w:rPr>"
        f"<w:t xml:space=\"preserve\">{_xml_escape(text)}</w:t>"
        f"</w:r>"
        f"</w:p>"
    )


def _w_table(headers: List[str], rows: List[List[str]], rtl: bool = True) -> str:
    bidi_visual = "<w:bidiVisual/>" if rtl else ""
    header_cells = "".join(
        f"<w:tc><w:tcPr><w:shd w:val=\"clear\" w:color=\"auto\" w:fill=\"154434\"/></w:tcPr>"
        f"{_w_p(h, rtl=rtl, bold=True, size_half_pts=22, color_hex='FFFFFF')}</w:tc>"
        for h in headers
    )
    body_rows = ""
    for r_idx, row in enumerate(rows):
        fill = "F6F7F5" if r_idx % 2 == 1 else "FFFFFF"
        cells = "".join(
            f"<w:tc><w:tcPr><w:shd w:val=\"clear\" w:color=\"auto\" w:fill=\"{fill}\"/></w:tcPr>"
            f"{_w_p(cell, rtl=rtl, bold=False, size_half_pts=21, color_hex='1C2520')}</w:tc>"
            for cell in row
        )
        body_rows += f"<w:tr>{cells}</w:tr>"

    return (
        f"<w:tbl>"
        f"<w:tblPr>"
        f"<w:tblW w:w=\"5000\" w:type=\"pct\"/>"
        f"{bidi_visual}"
        f"<w:tblBorders>"
        f"<w:top w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"CBD5E1\"/>"
        f"<w:bottom w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"CBD5E1\"/>"
        f"<w:left w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"CBD5E1\"/>"
        f"<w:right w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"CBD5E1\"/>"
        f"<w:insideH w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"E2E8F0\"/>"
        f"<w:insideV w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"E2E8F0\"/>"
        f"</w:tblBorders>"
        f"</w:tblPr>"
        f"<w:tr>{header_cells}</w:tr>"
        f"{body_rows}"
        f"</w:tbl>"
    )


def generate_plan_docx_bytes(
    plan_snap: Dict[str, Any],
    context_snap: Dict[str, Any],
    review_snap: Dict[str, Any],
    source_status: str = "unverified_draft",
    is_report: bool = False,
    report_summary: Optional[Dict[str, Any]] = None,
) -> bytes:
    rtl = _is_rtl_lang(context_snap.get("language", "ar"))
    body_parts: List[str] = []

    if is_report and report_summary:
        body_parts.append(_w_p("تقرير التخطيط والاكتمال للمعلم", rtl=rtl, bold=True, size_half_pts=34, color_hex="154434"))
        body_parts.append(_w_p(_format_context_banner(context_snap), rtl=rtl, bold=True, size_half_pts=20, color_hex="176B52"))
        body_parts.append(_w_p(str(report_summary.get("disclaimer") or ""), rtl=rtl, bold=False, size_half_pts=20, color_hex="B45309"))

        rep_headers = ["إجمالي الخطط", "المراجعة المكتملة", "المسودات", "الخطط المعتمدة", "حزم التصدير"]
        rep_row = [
            str(report_summary.get("totalPlans", 0)),
            str(report_summary.get("reviewedPlans", 0)),
            str(report_summary.get("draftPlans", 0)),
            str(report_summary.get("approvedPlans", 0)),
            str(report_summary.get("exportsCount", 0)),
        ]
        body_parts.append(_w_table(rep_headers, [rep_row], rtl=rtl))

        pat_rows = report_summary.get("patternSummary") or []
        if pat_rows:
            body_parts.append(_w_p("ملخص التخطيط حسب النمط:", rtl=rtl, bold=True, size_half_pts=26, color_hex="154434"))
            body_parts.append(
                _w_table(
                    ["النمط", "مخطط", "مكتمل المراجعة", "مصدّر"],
                    [[str(r.get("label", "")), str(r.get("planned", 0)), str(r.get("reviewed", 0)), str(r.get("exported", 0))] for r in pat_rows],
                    rtl=rtl,
                )
            )
        gaps = report_summary.get("documentationGaps") or []
        if gaps:
            body_parts.append(_w_p("ملاحظات وفجوات التوثيق:", rtl=rtl, bold=True, size_half_pts=26, color_hex="B45309"))
            for g in gaps:
                body_parts.append(_w_p(f"• {g}", rtl=rtl, size_half_pts=22))
    else:
        title = plan_snap.get("title") or "خطة تدريس"
        body_parts.append(_w_p(title, rtl=rtl, bold=True, size_half_pts=34, color_hex="154434"))
        body_parts.append(_w_p(_format_context_banner(context_snap), rtl=rtl, bold=True, size_half_pts=20, color_hex="176B52"))
        body_parts.append(_w_p(_format_approval_badge(plan_snap, source_status), rtl=rtl, bold=False, size_half_pts=20, color_hex="B45309"))

        meta_headers = ["المعلم", "المدرسة", "الشعبة", "التاريخ", "نوع الخطة", "الزمن المخصص"]
        periods_count = int(plan_snap.get("periodsCount") or 1)
        period_minutes = int(plan_snap.get("periodMinutes") or 45)
        if plan_snap.get("planType", "daily") != "daily" and plan_snap.get("totalAllocatedMinutes"):
            total_min = int(plan_snap.get("totalAllocatedMinutes") or (periods_count * period_minutes))
            time_desc = f"{total_min} دقيقة (موزعة على أيام التدريس)"
        else:
            total_min = periods_count * period_minutes
            time_desc = f"{periods_count} حصة × {period_minutes} د = {total_min} دقيقة"

        meta_row = [
            plan_snap.get("teacherName") or context_snap.get("teacherName") or "غير محدد",
            plan_snap.get("schoolName") or context_snap.get("schoolName") or "غير محددة",
            plan_snap.get("sectionName") or context_snap.get("sectionName") or "غير محددة",
            plan_snap.get("planningDate") or "غير محدد",
            plan_snap.get("planType") or "daily",
            time_desc,
        ]
        body_parts.append(_w_table(meta_headers, [meta_row], rtl=rtl))

        # Objectives
        body_parts.append(_w_p("الأهداف التعليمية:", rtl=rtl, bold=True, size_half_pts=26, color_hex="154434"))
        for idx, obj in enumerate(plan_snap.get("objectives") or [], start=1):
            body_parts.append(_w_p(f"{idx}. {obj}", rtl=rtl, bold=False, size_half_pts=22))

        # Prior Knowledge & Tools
        body_parts.append(_w_p(f"المتطلبات والمعارف السابقة: {plan_snap.get('priorKnowledge') or '—'}", rtl=rtl, size_half_pts=22))
        tools_str = "، ".join(plan_snap.get("teachingTools") or []) or "سبورة، أقلام"
        body_parts.append(_w_p(f"الوسائل التعليمية المتاحة: {tools_str}", rtl=rtl, size_half_pts=22))

        # Phases Table (Daily) or Schedule Days Table (Weekly / 5-Day)
        if plan_snap.get("planType", "daily") == "daily":
            body_parts.append(_w_p("جدول مراحل سير الحصة (قابل للتخصيص):", rtl=rtl, bold=True, size_half_pts=26, color_hex="154434"))
            ph_headers = ["ت", "الحصة", "المرحلة / العنصر", "المواد والمصدر", "دور المعلم (المنفّذ)", "دور المتعلم", "الهدف من العنصر", "الزمن (د)"]
            ph_rows = []
            for idx, ph in enumerate(plan_snap.get("phases") or [], start=1):
                src_ref = ph.get("sourceRef") or "المقرّر"
                mats = ph.get("materials") or ph.get("pedagogicalAids") or ""
                ph_rows.append(
                    [
                        str(idx),
                        f"الحصة {ph.get('periodNumber') or 1}",
                        str(ph.get("phaseName") or ph.get("name") or ""),
                        f"{mats} ({src_ref})" if mats else f"({src_ref})",
                        str(ph.get("teacherActivity") or ph.get("executorRole") or ph.get("teacherRole") or ""),
                        str(ph.get("studentActivity") or ph.get("studentRole") or ""),
                        str(ph.get("objective") or ""),
                        f"{ph.get('minutes', 0)} د",
                    ]
                )
            if ph_rows:
                body_parts.append(_w_table(ph_headers, ph_rows, rtl=rtl))
        else:
            body_parts.append(_w_p("جدول توزيع الأيام والحصص:", rtl=rtl, bold=True, size_half_pts=26, color_hex="154434"))
            day_headers = ["اليوم", "الحالة", "الدرس", "الأهداف والأنشطة", "التقويم", "الزمن (د)"]
            day_rows = []
            for d in plan_snap.get("scheduleDays") or []:
                day_rows.append(
                    [
                        str(d.get("dayName") or ""),
                        "عطلة" if d.get("isHoliday") else "يوم تدريس",
                        str(d.get("lessonTitle") or "—"),
                        str(d.get("activities") or "—"),
                        str(d.get("assessment") or "—"),
                        "0" if d.get("isHoliday") else str(d.get("minutes") if d.get("minutes") is not None else 45),
                    ]
                )
            if day_rows:
                body_parts.append(_w_table(day_headers, day_rows, rtl=rtl))

        # Assessment, Differentiation, Homework
        body_parts.append(_w_p("التقويم ومراعاة الفروق والواجب:", rtl=rtl, bold=True, size_half_pts=26, color_hex="154434"))
        body_parts.append(_w_p(f"• التقويم التكويني: {plan_snap.get('formativeAssessment') or 'غير مدخل (مانع اعتماد)'}", rtl=rtl, size_half_pts=22))
        body_parts.append(_w_p(f"• مراعاة الفروق الفردية (التمايز): {plan_snap.get('differentiation') or '—'}", rtl=rtl, size_half_pts=22))
        body_parts.append(_w_p(f"• الواجب المنزلي / الإثراء: {plan_snap.get('homework') or '—'}", rtl=rtl, size_half_pts=22))

        # Specialized Subject Items (with independent LTR direction for math expressions!)
        subj_items = plan_snap.get("subjectItems") or []
        if subj_items:
            body_parts.append(_w_p("المحتوى التخصصي والتمارين المتحققة:", rtl=rtl, bold=True, size_half_pts=26, color_hex="154434"))
            for item in subj_items:
                if item.get("domain") == "math":
                    expr_line = f"{item.get('expression', '')} = {item.get('expectedAnswer', '')} {item.get('unit', '')}".strip()
                    body_parts.append(_w_p(expr_line, rtl=False, bold=True, size_half_pts=22, color_hex="176B52"))
                else:
                    body_parts.append(_w_p(json.dumps(item, ensure_ascii=False), rtl=rtl, size_half_pts=20))

        # Review Defects & Warnings Summary
        findings = review_snap.get("findings") or []
        if findings:
            body_parts.append(_w_p("سجل التدقيق التربوي وتوثيق المصدر:", rtl=rtl, bold=True, size_half_pts=26, color_hex="154434"))
            rev_headers = ["الفئة", "العنوان", "التفاصيل", "الحقل المرتبط"]
            rev_rows = [
                [str(f.get("category") or ""), str(f.get("title") or ""), str(f.get("description") or ""), str(f.get("fieldTarget") or "")]
                for f in findings
            ]
            body_parts.append(_w_table(rev_headers, rev_rows, rtl=rtl))

    document_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\" "
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">"
        "<w:body>"
        + "".join(body_parts)
        + "<w:sectPr>"
        "<w:pgSz w:w=\"11906\" w:h=\"16838\"/>"
        "<w:pgMar w:top=\"1134\" w:right=\"1134\" w:bottom=\"1134\" w:left=\"1134\"/>"
        + ("<w:bidi/>" if rtl else "")
        + "</w:sectPr>"
        "</w:body></w:document>"
    )

    content_types_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
        "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
        "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
        "<Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>"
        "<Override PartName=\"/word/styles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml\"/>"
        "</Types>"
    )

    rels_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/>"
        "</Relationships>"
    )

    word_rels_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles\" Target=\"styles.xml\"/>"
        "</Relationships>"
    ).replace("officeDocument/2006/relationships/styles", "officeDocument/2006/relationships/styles")

    styles_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:styles xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
        "<w:docDefaults><w:rPrDefault><w:rPr>"
        "<w:rFonts w:ascii=\"Arial\" w:hAnsi=\"Arial\" w:cs=\"Arial\"/>"
        "<w:lang w:val=\"en-US\" w:bidi=\"ar-IQ\"/>"
        "</w:rPr></w:rPrDefault></w:docDefaults>"
        "</w:styles>"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml.encode("utf-8"))
        zf.writestr("_rels/.rels", rels_xml.encode("utf-8"))
        zf.writestr("word/_rels/document.xml.rels", word_rels_xml.encode("utf-8"))
        zf.writestr("word/styles.xml", styles_xml.encode("utf-8"))
        zf.writestr("word/document.xml", document_xml.encode("utf-8"))
    return buf.getvalue()


# ==============================================================================
# 2. REAL OOXML PPTX GENERATOR (.pptx) WITH EDITABLE TEXT SHAPES
# ==============================================================================

def _build_slide_paragraphs(lines: List[str], rtl: bool) -> str:
    alg_attr = "r" if rtl else "l"
    rtl_val = "1" if rtl else "0"
    body_paras = ""
    for line in lines:
        line_rtl = "0" if line.startswith("LTR:") else rtl_val
        line_alg = "l" if line_rtl == "0" else alg_attr
        clean_line = line[4:].strip() if line.startswith("LTR:") else line
        body_paras += (
            f"<a:p>"
            f"<a:pPr algn=\"{line_alg}\" rtl=\"{line_rtl}\"/>"
            f"<a:r>"
            f"<a:rPr lang=\"ar-IQ\" sz=\"2100\" dirty=\"0\">"
            f"<a:solidFill><a:srgbClr val=\"1C2520\"/></a:solidFill>"
            f"<a:latin typeface=\"Arial\"/><a:cs typeface=\"Arial\"/>"
            f"</a:rPr>"
            f"<a:t>{_xml_escape(clean_line)}</a:t>"
            f"</a:r>"
            f"</a:p>"
        )
    return body_paras


def _build_slide_xml(
    slide_title: str,
    slide_lines: List[str],
    footer_note: str,
    rtl: bool = True,
    slide_num: int = 1,
    total_slides: int = 5,
    layout_style: str = "title_and_content",
) -> str:
    alg_attr = "r" if rtl else "l"
    rtl_val = "1" if rtl else "0"

    if layout_style == "comparison" and len(slide_lines) >= 2:
        mid = max(1, len(slide_lines) // 2)
        right_paras = _build_slide_paragraphs(slide_lines[:mid], rtl)
        left_paras = _build_slide_paragraphs(slide_lines[mid:], rtl)
        content_shapes = (
            "<p:sp>"
            "<p:nvSpPr><p:cNvPr id=\"3\" name=\"CompareCol1\"/><p:cNvSpPr txBox=\"1\"/><p:nvPr/></p:nvSpPr>"
            "<p:spPr>"
            "<a:xfrm><a:off x=\"6200000\" y=\"1750000\"/><a:ext cx=\"5392000\" cy=\"4100000\"/></a:xfrm>"
            "<a:prstGeom prst=\"roundRect\"><a:avLst/></a:prstGeom>"
            "<a:solidFill><a:srgbClr val=\"F6F7F5\"/></a:solidFill>"
            "<a:ln w=\"12700\"><a:solidFill><a:srgbClr val=\"176B52\"/></a:solidFill></a:ln>"
            "</p:spPr>"
            "<p:txBody>"
            "<a:bodyPr wrap=\"square\" lIns=\"150000\" tIns=\"150000\" rIns=\"150000\" bIns=\"150000\"/>"
            f"<a:lstStyle/>{right_paras}</p:txBody></p:sp>"
            "<p:sp>"
            "<p:nvSpPr><p:cNvPr id=\"5\" name=\"CompareCol2\"/><p:cNvSpPr txBox=\"1\"/><p:nvPr/></p:nvSpPr>"
            "<p:spPr>"
            "<a:xfrm><a:off x=\"600000\" y=\"1750000\"/><a:ext cx=\"5392000\" cy=\"4100000\"/></a:xfrm>"
            "<a:prstGeom prst=\"roundRect\"><a:avLst/></a:prstGeom>"
            "<a:solidFill><a:srgbClr val=\"EBF5F0\"/></a:solidFill>"
            "<a:ln w=\"12700\"><a:solidFill><a:srgbClr val=\"154434\"/></a:solidFill></a:ln>"
            "</p:spPr>"
            "<p:txBody>"
            "<a:bodyPr wrap=\"square\" lIns=\"150000\" tIns=\"150000\" rIns=\"150000\" bIns=\"150000\"/>"
            f"<a:lstStyle/>{left_paras}</p:txBody></p:sp>"
        )
    else:
        body_paras = _build_slide_paragraphs(slide_lines, rtl)
        content_shapes = (
            "<p:sp>"
            "<p:nvSpPr><p:cNvPr id=\"3\" name=\"MainContent\"/><p:cNvSpPr txBox=\"1\"/><p:nvPr/></p:nvSpPr>"
            "<p:spPr>"
            "<a:xfrm><a:off x=\"600000\" y=\"1750000\"/><a:ext cx=\"10992000\" cy=\"4100000\"/></a:xfrm>"
            "<a:prstGeom prst=\"roundRect\"><a:avLst/></a:prstGeom>"
            "<a:solidFill><a:srgbClr val=\"F6F7F5\"/></a:solidFill>"
            "<a:ln w=\"12700\"><a:solidFill><a:srgbClr val=\"176B52\"/></a:solidFill></a:ln>"
            "</p:spPr>"
            "<p:txBody>"
            "<a:bodyPr wrap=\"square\" lIns=\"180000\" tIns=\"180000\" rIns=\"180000\" bIns=\"180000\"/>"
            f"<a:lstStyle/>{body_paras}</p:txBody></p:sp>"
        )

    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<p:sld xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" "
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" "
        "xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\">"
        "<p:cSld>"
        "<p:spTree>"
        "<p:nvGrpSpPr><p:cNvPr id=\"1\" name=\"\"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>"
        "<p:grpSpPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"0\" cy=\"0\"/><a:chOff x=\"0\" y=\"0\"/><a:chExt cx=\"0\" cy=\"0\"/></a:xfrm></p:grpSpPr>"
        "<p:sp>"
        "<p:nvSpPr><p:cNvPr id=\"2\" name=\"HeaderTitle\"/><p:cNvSpPr txBox=\"1\"/><p:nvPr/></p:nvSpPr>"
        "<p:spPr>"
        "<a:xfrm><a:off x=\"600000\" y=\"400000\"/><a:ext cx=\"10992000\" cy=\"1100000\"/></a:xfrm>"
        "<a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom>"
        "<a:solidFill><a:srgbClr val=\"154434\"/></a:solidFill>"
        "</p:spPr>"
        "<p:txBody>"
        "<a:bodyPr wrap=\"square\" anchor=\"ctr\"/>"
        "<a:lstStyle/>"
        f"<a:p><a:pPr algn=\"{alg_attr}\" rtl=\"{rtl_val}\"/>"
        "<a:r><a:rPr lang=\"ar-IQ\" sz=\"2800\" b=\"1\" dirty=\"0\">"
        "<a:solidFill><a:srgbClr val=\"FFFFFF\"/></a:solidFill>"
        "<a:latin typeface=\"Arial\"/><a:cs typeface=\"Arial\"/>"
        f"</a:rPr><a:t>{_xml_escape(slide_title)} ({slide_num}/{total_slides})</a:t></a:r></a:p>"
        "</p:txBody>"
        "</p:sp>"
        f"{content_shapes}"
        "<p:sp>"
        "<p:nvSpPr><p:cNvPr id=\"4\" name=\"FooterProvenance\"/><p:cNvSpPr txBox=\"1\"/><p:nvPr/></p:nvSpPr>"
        "<p:spPr>"
        "<a:xfrm><a:off x=\"600000\" y=\"6050000\"/><a:ext cx=\"10992000\" cy=\"550000\"/></a:xfrm>"
        "<a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom>"
        "<a:solidFill><a:srgbClr val=\"FEF3C7\"/></a:solidFill>"
        "</p:spPr>"
        "<p:txBody>"
        "<a:bodyPr wrap=\"square\" anchor=\"ctr\"/>"
        "<a:lstStyle/>"
        f"<a:p><a:pPr algn=\"{alg_attr}\" rtl=\"{rtl_val}\"/>"
        "<a:r><a:rPr lang=\"ar-IQ\" sz=\"1400\" dirty=\"0\">"
        "<a:solidFill><a:srgbClr val=\"B45309\"/></a:solidFill>"
        "<a:latin typeface=\"Arial\"/><a:cs typeface=\"Arial\"/>"
        f"</a:rPr><a:t>{_xml_escape(footer_note)}</a:t></a:r></a:p>"
        "</p:txBody>"
        "</p:sp>"
        "</p:spTree>"
        "</p:cSld>"
        "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>"
        "</p:sld>"
    )


def generate_plan_pptx_bytes(
    plan_snap: Dict[str, Any],
    context_snap: Dict[str, Any],
    source_status: str = "unverified_draft",
) -> bytes:
    pres_settings = plan_snap.get("presentationSettings") or {}
    dir_setting = pres_settings.get("textDirection", "rtl")
    layout_style = pres_settings.get("layoutStyle", "title_and_content")
    rtl = dir_setting != "ltr" and _is_rtl_lang(context_snap.get("language", "ar"))

    custom_slides = [s for s in (plan_snap.get("slides") or []) if isinstance(s, dict)]
    if not custom_slides:
        objs = plan_snap.get("objectives") or ["تحقيق نتاجات التعلم المحددة للدرس"]
        if plan_snap.get("planType", "daily") != "daily" and plan_snap.get("scheduleDays"):
            days = plan_snap.get("scheduleDays") or []
            custom_slides = [
                {
                    "title": plan_snap.get("title") or "جدول الخطة الأسبوعية",
                    "content": f"السياق: {_format_context_banner(context_snap)}\nالأهداف: {' | '.join(objs[:2])}",
                }
            ]
            for d in days:
                if d.get("isHoliday"):
                    continue
                custom_slides.append(
                    {
                        "title": f"{d.get('dayName', 'اليوم')}: {d.get('lessonTitle') or 'حصة تدريسية'}",
                        "content": (
                            f"• الأهداف: {d.get('objectives') or '—'}\n"
                            f"• الأنشطة: {d.get('activities') or '—'}\n"
                            f"• التقويم: {d.get('assessment') or '—'} ({d.get('minutes') if d.get('minutes') is not None else 45} د)"
                        ),
                    }
                )
        else:
            phases = plan_snap.get("phases") or []
            custom_slides = [
                {
                    "title": plan_snap.get("title") or "عنوان الدرس",
                    "content": f"السياق: {_format_context_banner(context_snap)}\nالمعلم: {plan_snap.get('teacherName') or '—'} | الشعبة: {plan_snap.get('sectionName') or '—'}",
                },
                {
                    "title": "أهداف الحصة والمتطلبات السابقة",
                    "content": "\n".join(f"• {o}" for o in objs) + f"\nالمعرفة السابقة: {plan_snap.get('priorKnowledge') or 'مراجعة المفاهيم الأساسية'}",
                },
                {
                    "title": "ناقش طريقة التفكير والتمثيل",
                    "content": "\n".join(
                        f"• {p.get('phaseName') or p.get('name') or 'مرحلة'}: {p.get('teacherActivity') or p.get('executorRole') or p.get('teacherRole') or ''} ({p.get('minutes', 0)} د)"
                        for p in phases[:3]
                    )
                    or "أدخل مهمة مناسبة للمادة بعد مراجعة المصدر، ثم اطلب من الطلاب تفسير خطواتهم.",
                },
                {
                    "title": "التدريب ومقارنة الاستراتيجيات",
                    "content": "\n".join(
                        f"• {p.get('phaseName') or p.get('name') or 'مرحلة'}: {p.get('studentActivity') or p.get('studentRole') or ''} ({p.get('minutes', 0)} د)"
                        for p in phases[2:]
                    )
                    or f"مراعاة الفروق الفردية: {plan_snap.get('differentiation') or 'تقديم دعم بصري وتدريج المهام.'}",
                },
                {
                    "title": "تقويم ختامي والواجب المنزلي",
                    "content": f"التقويم التكويني: {plan_snap.get('formativeAssessment') or 'لم يُدخل بعد'}\nالواجب: {plan_snap.get('homework') or 'يُحدده المعلم'}",
                },
            ]

    # Expand oversized slides on word boundaries so lines beyond 8 overflow cleanly into continuation slides
    expanded_slides: List[Dict[str, Any]] = []
    for idx, sld in enumerate(custom_slides, start=1):
        s_title = str(sld.get("title") or f"شريحة {idx}")
        raw_content = str(sld.get("content") or "")
        lines = [ln.strip() for ln in raw_content.splitlines() if ln.strip()] or ["محتوى تربوي قابل للتحرير في PowerPoint."]
        wrapped_lines: List[str] = []
        for ln in lines:
            if len(ln) > 90:
                wrapped_lines.extend(textwrap.wrap(ln, width=85, break_long_words=False))
            else:
                wrapped_lines.append(ln)
        for chunk_idx in range(0, len(wrapped_lines), 8):
            chunk_title = s_title if chunk_idx == 0 else f"{s_title} (تابع)"
            expanded_slides.append({"title": chunk_title, "lines": wrapped_lines[chunk_idx : chunk_idx + 8]})

    footer_note = f"{_format_context_banner(context_snap)} | {_format_approval_badge(plan_snap, source_status)}"
    total_slides = len(expanded_slides)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        override_slides = "".join(
            f"<Override PartName=\"/ppt/slides/slide{i}.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.slide+xml\"/>"
            for i in range(1, total_slides + 1)
        )
        content_types = (
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
            "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
            "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
            "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
            "<Override PartName=\"/ppt/presentation.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml\"/>"
            "<Override PartName=\"/ppt/slideMasters/slideMaster1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml\"/>"
            "<Override PartName=\"/ppt/slideLayouts/slideLayout1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml\"/>"
            f"{override_slides}"
            "</Types>"
        )
        zf.writestr("[Content_Types].xml", content_types.encode("utf-8"))

        root_rels = (
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
            "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
            "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"ppt/presentation.xml\"/>"
            "</Relationships>"
        )
        zf.writestr("_rels/.rels", root_rels.encode("utf-8"))

        sld_id_entries = "".join(
            f"<p:sldId id=\"{255 + i}\" r:id=\"rId{i + 1}\"/>" for i in range(1, total_slides + 1)
        )
        presentation_xml = (
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
            "<p:presentation xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" "
            "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" "
            "xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\">"
            "<p:sldMasterIdLst><p:sldMasterId id=\"2147483648\" r:id=\"rId1\"/></p:sldMasterIdLst>"
            f"<p:sldIdLst>{sld_id_entries}</p:sldIdLst>"
            "<p:sldSz cx=\"12192000\" cy=\"6858000\"/>"
            "<p:notesSz cx=\"6858000\" cy=\"9144000\"/>"
            "</p:presentation>"
        )
        zf.writestr("ppt/presentation.xml", presentation_xml.encode("utf-8"))

        pres_rel_entries = "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster\" Target=\"slideMasters/slideMaster1.xml\"/>"
        for i in range(1, total_slides + 1):
            pres_rel_entries += f"<Relationship Id=\"rId{i + 1}\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide\" Target=\"slides/slide{i}.xml\"/>"
        pres_rels = (
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
            f"<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">{pres_rel_entries}</Relationships>"
        )
        zf.writestr("ppt/_rels/presentation.xml.rels", pres_rels.encode("utf-8"))

        slide_master_xml = (
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
            "<p:sldMaster xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" "
            "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" "
            "xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\">"
            "<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id=\"1\" name=\"\"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>"
            "<p:grpSpPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"0\" cy=\"0\"/><a:chOff x=\"0\" y=\"0\"/><a:chExt cx=\"0\" cy=\"0\"/></a:xfrm></p:grpSpPr>"
            "</p:spTree></p:cSld>"
            "<p:clrMap bg1=\"lt1\" tx1=\"dk1\" bg2=\"lt2\" tx2=\"dk2\" accent1=\"accent1\" accent2=\"accent2\" accent3=\"accent3\" accent4=\"accent4\" accent5=\"accent5\" accent6=\"accent6\" hlink=\"hlink\" folHlink=\"folHlink\"/>"
            "<p:sldLayoutIdLst><p:sldLayoutId id=\"2147483649\" r:id=\"rId1\"/></p:sldLayoutIdLst>"
            "</p:sldMaster>"
        )
        zf.writestr("ppt/slideMasters/slideMaster1.xml", slide_master_xml.encode("utf-8"))
        zf.writestr(
            "ppt/slideMasters/_rels/slideMaster1.xml.rels",
            (
                "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
                "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
                "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout\" Target=\"../slideLayouts/slideLayout1.xml\"/>"
                "</Relationships>"
            ).encode("utf-8"),
        )

        slide_layout_xml = (
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
            "<p:sldLayout xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" "
            "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" "
            "xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\" type=\"blank\">"
            "<p:cSld name=\"Blank\"><p:spTree><p:nvGrpSpPr><p:cNvPr id=\"1\" name=\"\"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>"
            "<p:grpSpPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"0\" cy=\"0\"/><a:chOff x=\"0\" y=\"0\"/><a:chExt cx=\"0\" cy=\"0\"/></a:xfrm></p:grpSpPr>"
            "</p:spTree></p:cSld></p:sldLayout>"
        )
        zf.writestr("ppt/slideLayouts/slideLayout1.xml", slide_layout_xml.encode("utf-8"))
        zf.writestr(
            "ppt/slideLayouts/_rels/slideLayout1.xml.rels",
            (
                "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
                "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
                "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster\" Target=\"../slideMasters/slideMaster1.xml\"/>"
                "</Relationships>"
            ).encode("utf-8"),
        )

        slide_rel_xml = (
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
            "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
            "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout\" Target=\"../slideLayouts/slideLayout1.xml\"/>"
            "</Relationships>"
        )

        for idx, sld in enumerate(expanded_slides, start=1):
            s_xml = _build_slide_xml(
                sld["title"],
                sld["lines"],
                footer_note,
                rtl=rtl,
                slide_num=idx,
                total_slides=total_slides,
                layout_style=layout_style,
            )
            zf.writestr(f"ppt/slides/slide{idx}.xml", s_xml.encode("utf-8"))
            zf.writestr(f"ppt/slides/_rels/slide{idx}.xml.rels", slide_rel_xml.encode("utf-8"))

    return buf.getvalue()


# ==============================================================================
# 3. REAL PDF 1.7 GENERATOR (.pdf) WITH EMBEDDED UNICODE ARABIC SHAPING & RTL TABLES
# ==============================================================================

def generate_plan_pdf_bytes(
    plan_snap: Dict[str, Any],
    context_snap: Dict[str, Any],
    review_snap: Dict[str, Any],
    source_status: str = "unverified_draft",
    is_report: bool = False,
    report_summary: Optional[Dict[str, Any]] = None,
) -> bytes:
    """
    Produces a real A4 PDF 1.7 with embedded Unicode Arabic font shaping, RTL tables,
    multi-page flow via PyMuPDF Story, and LTR isolated math blocks.
    """
    rtl = _is_rtl_lang(context_snap.get("language", "ar"))
    dir_attr = "rtl" if rtl else "ltr"
    align = "right" if rtl else "left"

    sections: List[str] = []
    if is_report and report_summary:
        sections.append("<h1>تقرير التخطيط والاكتمال للمعلم</h1>")
        sections.append(f"<div class='banner'>{_html_escape(_format_context_banner(context_snap))}</div>")
        sections.append(
            "<div class='badge-warn'>" + _html_escape(report_summary.get("disclaimer") or "") + "</div>"
        )
        sections.append(
            "<table><tr><th>إجمالي الخطط</th><th>مكتملة المراجعة</th><th>مسودات</th><th>معتمدة</th><th>التصدير</th></tr>"
            f"<tr><td>{report_summary.get('totalPlans', 0)}</td>"
            f"<td>{report_summary.get('reviewedPlans', 0)}</td>"
            f"<td>{report_summary.get('draftPlans', 0)}</td>"
            f"<td>{report_summary.get('approvedPlans', 0)}</td>"
            f"<td>{report_summary.get('exportsCount', 0)}</td></tr></table>"
        )
        pat_rows = report_summary.get("patternSummary") or []
        if pat_rows:
            rows_html = "".join(
                f"<tr><td>{_html_escape(r.get('label'))}</td><td>{r.get('planned', 0)}</td>"
                f"<td>{r.get('reviewed', 0)}</td><td>{r.get('exported', 0)}</td></tr>"
                for r in pat_rows
            )
            sections.append(f"<h2>ملخص الأنماط</h2><table><tr><th>النمط</th><th>مخطط</th><th>مكتمل</th><th>مصدر</th></tr>{rows_html}</table>")
        gaps = report_summary.get("documentationGaps") or []
        if gaps:
            gaps_li = "".join(f"<li>{_html_escape(g)}</li>" for g in gaps)
            sections.append(f"<h2>ملاحظات التوثيق</h2><ul>{gaps_li}</ul>")
    else:
        title = plan_snap.get("title") or "خطة تدريس"
        sections.append(f"<h1>{_html_escape(title)}</h1>")
        sections.append(f"<div class='banner'>{_html_escape(_format_context_banner(context_snap))}</div>")
        sections.append(f"<div class='badge-warn'>{_html_escape(_format_approval_badge(plan_snap, source_status))}</div>")

        periods_count = int(plan_snap.get("periodsCount") or 1)
        period_minutes = int(plan_snap.get("periodMinutes") or 45)
        total_min = (
            int(plan_snap.get("totalAllocatedMinutes") or (periods_count * period_minutes))
            if plan_snap.get("planType", "daily") != "daily"
            else periods_count * period_minutes
        )
        sections.append(
            "<table><tr><th>المعلم</th><th>المدرسة</th><th>الشعبة</th><th>التاريخ</th><th>الزمن</th></tr>"
            f"<tr><td>{_html_escape(plan_snap.get('teacherName') or context_snap.get('teacherName') or '—')}</td>"
            f"<td>{_html_escape(plan_snap.get('schoolName') or context_snap.get('schoolName') or '—')}</td>"
            f"<td>{_html_escape(plan_snap.get('sectionName') or context_snap.get('sectionName') or '—')}</td>"
            f"<td><span dir='ltr'>{_html_escape(plan_snap.get('planningDate') or '—')}</span></td>"
            f"<td>{total_min} دقيقة</td></tr></table>"
        )

        objs = plan_snap.get("objectives") or []
        if objs:
            objs_li = "".join(f"<li>{_html_escape(o)}</li>" for o in objs)
            sections.append(f"<h2>الأهداف التعليمية</h2><ol>{objs_li}</ol>")

        sections.append(
            f"<p><strong>المتطلبات السابقة:</strong> {_html_escape(plan_snap.get('priorKnowledge') or '—')}</p>"
            f"<p><strong>الوسائل التعليمية:</strong> {_html_escape('، '.join(plan_snap.get('teachingTools') or []) or 'سبورة، أقلام')}</p>"
        )

        if plan_snap.get("planType", "daily") == "daily":
            ph_rows_html = ""
            for idx, ph in enumerate(plan_snap.get("phases") or [], start=1):
                mats = ph.get("materials") or ph.get("pedagogicalAids") or ""
                src_ref = ph.get("sourceRef") or "المقرّر"
                ph_rows_html += (
                    f"<tr><td>{idx}</td><td>الحصة {ph.get('periodNumber') or 1}</td>"
                    f"<td>{_html_escape(ph.get('phaseName') or ph.get('name') or '')}</td>"
                    f"<td>{_html_escape(f'{mats} ({src_ref})' if mats else src_ref)}</td>"
                    f"<td>{_html_escape(ph.get('teacherActivity') or ph.get('executorRole') or ph.get('teacherRole') or '')}</td>"
                    f"<td>{_html_escape(ph.get('studentActivity') or ph.get('studentRole') or '')}</td>"
                    f"<td>{ph.get('minutes', 0)} د</td></tr>"
                )
            if ph_rows_html:
                sections.append(
                    "<h2>جدول مراحل سير الحصة</h2>"
                    "<table><tr><th>ت</th><th>الحصة</th><th>المرحلة</th><th>المواد والمصدر</th><th>دور المعلم</th><th>دور المتعلم</th><th>الزمن</th></tr>"
                    f"{ph_rows_html}</table>"
                )
        else:
            d_rows_html = ""
            for d in plan_snap.get("scheduleDays") or []:
                mins_str = "0" if d.get("isHoliday") else str(d.get("minutes") if d.get("minutes") is not None else 45)
                d_rows_html += (
                    f"<tr><td>{_html_escape(d.get('dayName') or '')}</td>"
                    f"<td>{'عطلة' if d.get('isHoliday') else 'يوم تدريس'}</td>"
                    f"<td>{_html_escape(d.get('lessonTitle') or '—')}</td>"
                    f"<td>{_html_escape(d.get('activities') or '—')}</td>"
                    f"<td>{_html_escape(d.get('assessment') or '—')}</td>"
                    f"<td>{mins_str} د</td></tr>"
                )
            if d_rows_html:
                sections.append(
                    "<h2>جدول توزيع الأيام والحصص</h2>"
                    "<table><tr><th>اليوم</th><th>الحالة</th><th>الدرس</th><th>الأنشطة</th><th>التقويم</th><th>الزمن</th></tr>"
                    f"{d_rows_html}</table>"
                )

        sections.append(
            f"<h2>التقويم والمتابعة</h2>"
            f"<p><strong>التقويم التكويني:</strong> {_html_escape(plan_snap.get('formativeAssessment') or 'لم يُدخل بعد')}</p>"
            f"<p><strong>مراعاة الفروق الفردية:</strong> {_html_escape(plan_snap.get('differentiation') or '—')}</p>"
            f"<p><strong>الواجب المنزلي:</strong> {_html_escape(plan_snap.get('homework') or '—')}</p>"
        )

        subj_items = plan_snap.get("subjectItems") or []
        if subj_items:
            items_html = ""
            for item in subj_items:
                if item.get("domain") == "math":
                    expr_line = f"{item.get('expression', '')} = {item.get('expectedAnswer', '')} {item.get('unit', '')}".strip()
                    items_html += f"<li dir='ltr' style='text-align:left;font-weight:bold;color:#176B52'>{_html_escape(expr_line)}</li>"
                else:
                    summary = item.get("quote") or item.get("hypothesis") or item.get("topic") or json.dumps(item, ensure_ascii=False)
                    items_html += f"<li>{_html_escape(summary)}</li>"
            sections.append(f"<h2>المحتوى التخصصي</h2><ul>{items_html}</ul>")

        findings = review_snap.get("findings") or []
        if findings:
            f_rows = "".join(
                f"<tr><td>{_html_escape(f.get('category'))}</td><td>{_html_escape(f.get('title'))}</td><td>{_html_escape(f.get('description'))}</td></tr>"
                for f in findings
            )
            sections.append(f"<h2>سجل التدقيق التربوي</h2><table><tr><th>الفئة</th><th>العنوان</th><th>التفاصيل</th></tr>{f_rows}</table>")

    html_doc = f"""<!DOCTYPE html>
<html dir="{dir_attr}" lang="{_html_escape(context_snap.get('language') or 'ar')}">
<head>
<meta charset="utf-8"/>
<style>
  body {{ font-family: sans-serif; font-size: 10pt; line-height: 1.5; color: #1C2520; direction: {dir_attr}; text-align: {align}; }}
  h1 {{ color: #154434; font-size: 16pt; margin: 0 0 6px 0; border-bottom: 2px solid #154434; padding-bottom: 4px; }}
  h2 {{ color: #154434; font-size: 12pt; margin: 12px 0 4px 0; }}
  .banner {{ background-color: #EBF5F0; color: #176B52; padding: 6px 8px; font-size: 9pt; font-weight: bold; margin-bottom: 6px; border: 1px solid #B7E0CC; }}
  .badge-warn {{ background-color: #FEF3C7; color: #92400E; padding: 6px 8px; font-size: 9pt; margin-bottom: 8px; border: 1px solid #FDE68A; }}
  table {{ width: 100%; border-collapse: collapse; margin: 6px 0 10px 0; font-size: 9pt; }}
  th {{ background-color: #154434; color: #FFFFFF; padding: 5px; border: 1px solid #CBD5E1; text-align: {align}; }}
  td {{ padding: 5px; border: 1px solid #CBD5E1; text-align: {align}; vertical-align: top; }}
  ul, ol {{ margin: 4px 0 8px 0; padding-inline-start: 18px; }}
  p {{ margin: 4px 0; }}
</style>
</head>
<body>
{''.join(sections)}
</body>
</html>"""

    if pymupdf is not None:
        story = pymupdf.Story(html=html_doc)
        buf = io.BytesIO()
        mediabox = pymupdf.paper_rect("a4")
        where = mediabox + (32, 32, -32, -32)
        writer = pymupdf.DocumentWriter(buf)
        more = True
        while more:
            dev = writer.begin_page(mediabox)
            more, _ = story.place(where)
            story.draw(dev, pymupdf.Identity)
            writer.end_page()
        writer.close()

        doc = pymupdf.open(stream=buf.getvalue(), filetype="pdf")
        doc.subset_fonts()
        return doc.tobytes(garbage=3, deflate=True)

    # Minimal ASCII fallback only if PyMuPDF is absent
    minimal_stream = b"BT /F1 12 Tf 48 760 Td (Teacher System PDF Export - Install pymupdf for Arabic Unicode) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [4 0 R] /Count 1 >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents 5 0 R >>",
        f"<< /Length {len(minimal_stream)} >>\nstream\n".encode("ascii") + minimal_stream + b"\nendstream",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.7\n")
    offsets = []
    for idx, obj_b in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{idx} 0 obj\n".encode("ascii") + obj_b + b"\nendobj\n")
    xref_pos = out.tell()
    out.write(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode("ascii"))
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode("ascii"))
    out.write(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("ascii"))
    return out.getvalue()


# ==============================================================================
# 4. INDEPENDENT STRUCTURAL VERIFIER FOR GENERATED FILES
# ==============================================================================

def verify_exported_file_structure(file_bytes: bytes, export_format: str) -> Dict[str, Any]:
    sha256_hex = hashlib.sha256(file_bytes).hexdigest()

    if export_format in ("docx", "report_docx"):
        with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as zf:
            names = zf.namelist()
            if "word/document.xml" not in names or "[Content_Types].xml" not in names:
                return {"passed": False, "reason": "Missing OOXML word/document.xml"}
            doc_xml = zf.read("word/document.xml")
            root = ET.fromstring(doc_xml)
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            texts = [t.text for t in root.findall(".//w:t", ns) if t.text]
            tables = root.findall(".//w:tbl", ns)
            return {
                "passed": len(texts) > 0 and len(tables) > 0,
                "format": "OOXML_DOCX",
                "paragraphsOrRunsCount": len(texts),
                "tablesCount": len(tables),
                "sha256": sha256_hex,
                "sampleText": " | ".join(texts[:3]),
            }

    if export_format == "pptx":
        with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as zf:
            names = zf.namelist()
            slide_files = sorted([n for n in names if n.startswith("ppt/slides/slide") and n.endswith(".xml")])
            if "ppt/presentation.xml" not in names or not slide_files:
                return {"passed": False, "reason": "Missing OOXML ppt/presentation.xml or slides"}
            ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
            editable_text_runs = 0
            for sf in slide_files:
                s_root = ET.fromstring(zf.read(sf))
                editable_text_runs += len(s_root.findall(".//a:t", ns))
            return {
                "passed": len(slide_files) > 0 and editable_text_runs > 0,
                "format": "OOXML_PPTX",
                "slidesCount": len(slide_files),
                "editableTextElementsCount": editable_text_runs,
                "sha256": sha256_hex,
            }

    if export_format in ("pdf", "report_pdf"):
        has_header = file_bytes.startswith(b"%PDF-")
        has_eof = b"%%EOF" in file_bytes[-128:]
        pages_count = 0
        extracted_chars = 0
        if pymupdf is not None and has_header:
            try:
                with pymupdf.open(stream=file_bytes, filetype="pdf") as doc:
                    pages_count = len(doc)
                    extracted_chars = sum(len((p.get_text("text") or "").strip()) for p in doc)
            except Exception:
                pages_count = 0
        else:
            pages_count = 1 if b"/Type /Page" in file_bytes else 0
            extracted_chars = 1 if (b"BT " in file_bytes and b" ET" in file_bytes) else 0
        return {
            "passed": bool(has_header and has_eof and pages_count >= 1 and extracted_chars > 0),
            "format": "PDF_1_7",
            "pagesCount": pages_count,
            "hasSelectableTextStream": extracted_chars > 0,
            "sha256": sha256_hex,
        }

    if export_format == "bundle_zip":
        with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as zf:
            names = zf.namelist()
            return {
                "passed": len(names) >= 5,
                "format": "BUNDLE_ZIP",
                "files": names,
                "sha256": sha256_hex,
            }

    return {"passed": False, "reason": f"Unknown export format: {export_format}"}
