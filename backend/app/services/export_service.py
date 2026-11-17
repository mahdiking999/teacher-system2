import hashlib
import html as html_mod
import io
import re
import textwrap
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import pymupdf
except ImportError:
    pymupdf = None


_FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_REGULAR_FONT_FILE = "Tajawal-Regular.ttf"
_BOLD_FONT_FILE = "Tajawal-Bold.ttf"

# A4 portrait in OOXML twips (11906 - 2 * 1134 = 9638)
_DOCX_CONTENT_WIDTH_DXA = 9638

_ARABIC_RUN_RE = re.compile(
    r"([\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+"
    r"(?:[\s\u060C\u061B\u061F\-—·،؛.:]+[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+)*)"
)
_RTL_LTR_TOKEN_RE = re.compile(
    r"(?:\b\d{4}-\d{2}-\d{2}\b"
    r"|(?<![A-Za-z0-9])\([^()\n]+\)\s*(?:[+\-*/=<>÷×]|!=)\s*[\d\s()+\-*/.=<>÷×]+"
    r"|(?<![A-Za-z0-9])\d+(?:\.\d+)?(?:\s+(?:[+\-*/=<>÷×]|!=)\s+\d+(?:\.\d+)?)+)"
)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_CMAP_MOJIBAKE_CHARS = set("Ǆǁǂƾ")


_I18N: Dict[str, Dict[str, Any]] = {
    "ar": {
        "not_specified": "غير محدد",
        "not_specified_f": "غير محددة",
        "not_entered": "غير مدخلة",
        "default_provenance": "مثال توضيحي غير موثق من الكتاب",
        "source_status": {
            "human_verified": "موثّق بشريًا",
            "unverified_draft": "مسودة غير موثّقة",
            "pending_review": "قيد المراجعة",
        },
        "plan_status": {
            "approved": "معتمد",
            "reviewed": "مكتمل المراجعة",
            "draft": "مسودة",
            "needs_revision": "بحاجة إلى تعديل",
        },
        "plan_type": {
            "daily": "خطة يومية",
            "weekly": "خطة أسبوعية",
            "five_day": "خطة خمسة أيام",
        },
        "banner_fmt": (
            "المادة: {subject} | الصف/المرحلة: {grade} | البلد: {country} | "
            "المنهج: {curriculum} | اللغة: {lang} | السنة: {year} | الطبعة: {edition}"
        ),
        "approval_approved": "حالة الإصدار (v{ver}): معتمد تربويًا بواسطة ({approver}) | حالة المصدر: {src_status} | النسبة: {prov}",
        "approval_draft": "حالة الإصدار (v{ver}): مسودة غير معتمدة ({status}) — لا تحمل ختم اعتماد رسمي | حالة المصدر: {src_status} | {prov}",
        "report_title": "تقرير التخطيط والاكتمال للمعلم",
        "report_disclaimer_default": "المؤشرات تقيس تنظيم التخطيط واكتماله للمعلم فقط. لا توجد بيانات متعلمين ولا نسب نجاح طلاب مفترضة.",
        "report_headers": ["إجمالي الخطط", "المراجعة المكتملة", "المسودات", "الخطط المعتمدة", "حزم التصدير"],
        "pattern_heading": "ملخص التخطيط حسب النمط:",
        "pattern_headers": ["النمط", "مخطط", "مكتمل المراجعة", "مصدّر"],
        "doc_gaps_heading": "ملاحظات وفجوات التوثيق:",
        "default_plan_title": "خطة تدريس",
        "meta_headers": ["المعلم", "المدرسة", "الشعبة", "التاريخ", "نوع الخطة", "الزمن المخصص"],
        "minutes_unit": "دقيقة",
        "minutes_short": "د",
        "periods_time_fmt": "{periods} {period_word} × {period_mins} د = {total} دقيقة",
        "period_word_single": "حصة",
        "period_word_plural": "حصص",
        "multi_day_time_fmt": "{total} دقيقة (موزعة على أيام التدريس)",
        "objectives_heading": "الأهداف التعليمية:",
        "prior_knowledge_label": "المتطلبات والمعارف السابقة:",
        "teaching_tools_label": "الوسائل التعليمية المتاحة:",
        "default_tools": "سبورة، أقلام",
        "roles_heading": "الأدوار التربوية:",
        "teacher_role_label": "دور المعلم العام:",
        "student_role_label": "دور المتعلم العام:",
        "phases_heading": "جدول مراحل سير الحصة (قابل للتخصيص):",
        "phases_headers": ["ت", "الحصة", "المرحلة / العنصر", "المواد والمصدر", "دور المعلم (المنفّذ)", "دور المتعلم", "الهدف من العنصر", "الزمن (د)"],
        "default_source_ref": "المقرّر",
        "period_prefix": "الحصة",
        "schedule_heading": "جدول توزيع الأيام والحصص:",
        "schedule_headers": ["اليوم", "الحالة", "الدرس", "الأهداف", "الأنشطة", "التقويم", "الزمن (د)"],
        "holiday_label": "عطلة",
        "teaching_day_label": "يوم تدريس",
        "holiday_row_note": "عطلة / استراحة رسمية",
        "assessment_heading": "التقويم ومراعاة الفروق والواجب:",
        "formative_label": "التقويم التكويني:",
        "missing_formative_label": "غير مدخل (مانع اعتماد)",
        "diff_label": "مراعاة الفروق الفردية (التمايز):",
        "homework_label": "الواجب المنزلي / الإثراء:",
        "home_enrichment_fmt": "زمن الإثراء المنزلي: {mins} دقيقة (خارج مجموع زمن الحصة)",
        "notes_heading": "ملاحظات التخطيط والمصادر:",
        "planning_notes_label": "ملاحظات التخطيط:",
        "references_note_label": "المصادر والمراجع:",
        "subject_items_heading": "المحتوى التخصصي والتمارين المتحققة:",
        "audit_heading": "سجل التدقيق التربوي وتوثيق المصدر:",
        "audit_headers": ["الفئة", "العنوان", "التفاصيل", "الحقل المرتبط"],
        "page_footer_fmt": "صفحة {page} من {total}",
        "slide_fallback_title_fmt": "شريحة {idx}",
        "slide_fallback_body": "محتوى تربوي قابل للتحرير في PowerPoint.",
        "slide_cont_suffix": "(تابع)",
        "slide_compare_companion": "نقاط المقارنة والتطبيق العملي",
        "slide_weekly_title": "جدول الخطة الأسبوعية",
        "slide_context_prefix": "السياق:",
        "slide_objectives_prefix": "الأهداف:",
        "slide_schedule_overview_title": "نظرة عامة على توزيع الأيام والعطل",
        "slide_day_default": "اليوم",
        "slide_lesson_default": "حصة تدريسية",
        "slide_daily_obj_title": "أهداف الحصة والمتطلبات السابقة",
        "slide_phases_part1_title": "التمهيد وبناء المفهوم (الجزء الأول)",
        "slide_phases_part2_title": "التدريب والتقويم والإثراء (الجزء الثاني)",
        "slide_closing_title": "التقويم الختامي والواجب المنزلي",
        "slide_teacher_label": "المعلم:",
        "slide_section_label": "الشعبة:",
        "slide_prior_label": "المعرفة السابقة:",
        "slide_default_prior": "مراجعة المفاهيم الأساسية",
        "slide_default_phase": "مرحلة",
        "slide_default_phase_prompt": "أدخل مهمة مناسبة للمادة بعد مراجعة المصدر، ثم اطلب من الطلاب تفسير خطواتهم.",
        "slide_default_diff_prompt": "مراعاة الفروق الفردية: تقديم دعم بصري وتدريج المهام.",
        "slide_default_formative": "لم يُدخل بعد",
        "slide_default_homework": "يُحدده المعلم",
        "slide_default_obj": "تحقيق نتاجات التعلم المحددة للدرس",
    },
    "en": {
        "not_specified": "Not specified",
        "not_specified_f": "Not specified",
        "not_entered": "Not entered",
        "default_provenance": "Illustrative example — not verified against textbook",
        "source_status": {
            "human_verified": "Human verified",
            "unverified_draft": "Unverified draft",
            "pending_review": "Pending review",
        },
        "plan_status": {
            "approved": "Approved",
            "reviewed": "Reviewed",
            "draft": "Draft",
            "needs_revision": "Needs revision",
        },
        "plan_type": {
            "daily": "Daily Plan",
            "weekly": "Weekly Plan",
            "five_day": "Five-Day Plan",
        },
        "banner_fmt": (
            "Subject: {subject} | Grade: {grade} | Country: {country} | "
            "Curriculum: {curriculum} | Language: {lang} | Year: {year} | Edition: {edition}"
        ),
        "approval_approved": "Version Status (v{ver}): Pedagogically approved by ({approver}) | Source: {src_status} | Provenance: {prov}",
        "approval_draft": "Version Status (v{ver}): Unapproved draft ({status}) — No official approval stamp | Source: {src_status} | {prov}",
        "report_title": "Teacher Planning & Completion Report",
        "report_disclaimer_default": "Indicators measure teacher planning organization and completeness only. No student grades or assumed student outcomes.",
        "report_headers": ["Total Plans", "Reviewed", "Drafts", "Approved", "Export Packages"],
        "pattern_heading": "Planning Summary by Pattern:",
        "pattern_headers": ["Pattern", "Planned", "Reviewed", "Exported"],
        "doc_gaps_heading": "Documentation Notes & Gaps:",
        "default_plan_title": "Lesson Plan",
        "meta_headers": ["Teacher", "School", "Section", "Date", "Plan Type", "Allocated Time"],
        "minutes_unit": "min",
        "minutes_short": "min",
        "periods_time_fmt": "{periods} {period_word} × {period_mins} min = {total} min",
        "period_word_single": "period",
        "period_word_plural": "periods",
        "multi_day_time_fmt": "{total} min (distributed across teaching days)",
        "objectives_heading": "Learning Objectives:",
        "prior_knowledge_label": "Prior Knowledge & Prerequisites:",
        "teaching_tools_label": "Available Teaching Tools:",
        "default_tools": "Whiteboard, markers",
        "roles_heading": "Pedagogical Roles:",
        "teacher_role_label": "General Teacher Role:",
        "student_role_label": "General Student Role:",
        "phases_heading": "Lesson Phases Schedule (Editable):",
        "phases_headers": ["#", "Period", "Phase / Stage", "Materials & Source", "Teacher Role", "Student Role", "Objective", "Duration"],
        "default_source_ref": "Curriculum",
        "period_prefix": "Period",
        "schedule_heading": "Days & Schedule Distribution:",
        "schedule_headers": ["Day", "Status", "Lesson", "Objectives", "Activities", "Assessment", "Duration"],
        "holiday_label": "Holiday",
        "teaching_day_label": "Teaching Day",
        "holiday_row_note": "Official Holiday / Break",
        "assessment_heading": "Assessment, Differentiation & Homework:",
        "formative_label": "Formative Assessment:",
        "missing_formative_label": "Missing (approval blocker)",
        "diff_label": "Differentiation:",
        "homework_label": "Homework / Enrichment:",
        "home_enrichment_fmt": "Home enrichment time: {mins} min (excluded from class period total)",
        "notes_heading": "Planning Notes & References:",
        "planning_notes_label": "Planning Notes:",
        "references_note_label": "References:",
        "subject_items_heading": "Specialized Subject Content & Verified Items:",
        "audit_heading": "Pedagogical Audit & Source Verification Log:",
        "audit_headers": ["Category", "Title", "Details", "Target Field"],
        "page_footer_fmt": "Page {page} of {total}",
        "slide_fallback_title_fmt": "Slide {idx}",
        "slide_fallback_body": "Editable pedagogical content in PowerPoint.",
        "slide_cont_suffix": "(cont.)",
        "slide_compare_companion": "Comparison & Practice Notes",
        "slide_weekly_title": "Weekly Plan Schedule",
        "slide_context_prefix": "Context:",
        "slide_objectives_prefix": "Objectives:",
        "slide_schedule_overview_title": "Schedule & Holidays Overview",
        "slide_day_default": "Day",
        "slide_lesson_default": "Teaching Session",
        "slide_daily_obj_title": "Lesson Objectives & Prerequisites",
        "slide_phases_part1_title": "Warm-Up & Concept Instruction (Part 1)",
        "slide_phases_part2_title": "Guided Practice, Assessment & Enrichment (Part 2)",
        "slide_closing_title": "Formative Assessment & Homework",
        "slide_teacher_label": "Teacher:",
        "slide_section_label": "Section:",
        "slide_prior_label": "Prior Knowledge:",
        "slide_default_prior": "Review core prerequisite concepts",
        "slide_default_phase": "Phase",
        "slide_default_phase_prompt": "Add a subject-appropriate task from the verified source and ask students to explain their reasoning.",
        "slide_default_diff_prompt": "Differentiation: Provide visual scaffolding and tiered tasks.",
        "slide_default_formative": "Not entered yet",
        "slide_default_homework": "Assigned by teacher",
        "slide_default_obj": "Achieve the defined learning outcomes for the lesson",
    },
    "fr": {
        "not_specified": "Non spécifié",
        "not_specified_f": "Non spécifiée",
        "not_entered": "Non renseignée",
        "default_provenance": "Exemple illustratif — non vérifié dans le manuel",
        "source_status": {
            "human_verified": "Vérifié humainement",
            "unverified_draft": "Brouillon non vérifié",
            "pending_review": "En attente de révision",
        },
        "plan_status": {
            "approved": "Approuvé",
            "reviewed": "Révisé",
            "draft": "Brouillon",
            "needs_revision": "À réviser",
        },
        "plan_type": {
            "daily": "Plan quotidien",
            "weekly": "Plan hebdomadaire",
            "five_day": "Plan sur 5 jours",
        },
        "banner_fmt": (
            "Matière : {subject} | Niveau : {grade} | Pays : {country} | "
            "Programme : {curriculum} | Langue : {lang} | Année : {year} | Édition : {edition}"
        ),
        "approval_approved": "Statut (v{ver}) : Approuvé pédagogiquement par ({approver}) | Source : {src_status} | Provenance : {prov}",
        "approval_draft": "Statut (v{ver}) : Brouillon non approuvé ({status}) — Sans validation officielle | Source : {src_status} | {prov}",
        "report_title": "Rapport de planification et de complétude",
        "report_disclaimer_default": "Les indicateurs mesurent uniquement l'organisation et la complétude du plan enseignant.",
        "report_headers": ["Total plans", "Révisés", "Brouillons", "Approuvés", "Exports"],
        "pattern_heading": "Résumé par modèle :",
        "pattern_headers": ["Modèle", "Planifiés", "Révisés", "Exportés"],
        "doc_gaps_heading": "Notes et lacunes de documentation :",
        "default_plan_title": "Fiche pédagogique",
        "meta_headers": ["Enseignant", "Établissement", "Classe", "Date", "Type de plan", "Durée allouée"],
        "minutes_unit": "min",
        "minutes_short": "min",
        "periods_time_fmt": "{periods} {period_word} × {period_mins} min = {total} min",
        "period_word_single": "séance",
        "period_word_plural": "séances",
        "multi_day_time_fmt": "{total} min (réparties sur les jours de cours)",
        "objectives_heading": "Objectifs pédagogiques :",
        "prior_knowledge_label": "Prérequis :",
        "teaching_tools_label": "Supports pédagogiques :",
        "default_tools": "Tableau, marqueurs",
        "roles_heading": "Rôles pédagogiques :",
        "teacher_role_label": "Rôle de l'enseignant :",
        "student_role_label": "Rôle de l'apprenant :",
        "phases_heading": "Déroulement de la séance :",
        "phases_headers": ["#", "Séance", "Phase", "Supports et source", "Rôle enseignant", "Rôle élève", "Objectif", "Durée"],
        "default_source_ref": "Programme",
        "period_prefix": "Séance",
        "schedule_heading": "Répartition des jours et séances :",
        "schedule_headers": ["Jour", "Statut", "Leçon", "Objectifs", "Activités", "Évaluation", "Durée"],
        "holiday_label": "Congé",
        "teaching_day_label": "Jour de cours",
        "holiday_row_note": "Congé / Pause officielle",
        "assessment_heading": "Évaluation, différenciation et devoirs :",
        "formative_label": "Évaluation formative :",
        "missing_formative_label": "Manquante (bloquant)",
        "diff_label": "Différenciation pédagogique :",
        "homework_label": "Devoir à domicile / Enrichissement :",
        "home_enrichment_fmt": "Enrichissement à domicile : {mins} min (hors temps de classe)",
        "notes_heading": "Notes et références :",
        "planning_notes_label": "Notes de planification :",
        "references_note_label": "Références :",
        "subject_items_heading": "Contenu disciplinaire vérifié :",
        "audit_heading": "Journal d'audit pédagogique et de source :",
        "audit_headers": ["Catégorie", "Titre", "Détails", "Champ ciblé"],
        "page_footer_fmt": "Page {page} sur {total}",
        "slide_fallback_title_fmt": "Diapositive {idx}",
        "slide_fallback_body": "Contenu pédagogique modifiable dans PowerPoint.",
        "slide_cont_suffix": "(suite)",
        "slide_compare_companion": "Points de comparaison et pratique",
        "slide_weekly_title": "Emploi du temps hebdomadaire",
        "slide_context_prefix": "Contexte :",
        "slide_objectives_prefix": "Objectifs :",
        "slide_schedule_overview_title": "Aperçu des jours et congés",
        "slide_day_default": "Jour",
        "slide_lesson_default": "Séance de cours",
        "slide_daily_obj_title": "Objectifs et prérequis",
        "slide_phases_part1_title": "Mise en route et enseignement (Partie 1)",
        "slide_phases_part2_title": "Pratique, évaluation et enrichissement (Partie 2)",
        "slide_closing_title": "Évaluation finale et devoir",
        "slide_teacher_label": "Enseignant :",
        "slide_section_label": "Classe :",
        "slide_prior_label": "Prérequis :",
        "slide_default_prior": "Révision des notions de base",
        "slide_default_phase": "Phase",
        "slide_default_phase_prompt": "Ajoutez une tâche adaptée au programme et demandez aux élèves d'expliquer leur démarche.",
        "slide_default_diff_prompt": "Différenciation : soutien visuel et tâches progressives.",
        "slide_default_formative": "Non renseignée",
        "slide_default_homework": "Défini par l'enseignant",
        "slide_default_obj": "Atteindre les objectifs d'apprentissage du cours",
    },
}


def _lang_code(lang: Any) -> str:
    val = str(lang or "ar").strip().lower()
    if val.startswith("en"):
        return "en"
    if val.startswith("fr"):
        return "fr"
    return "ar"


def _tr(lang: str, key: str) -> Any:
    return _I18N.get(_lang_code(lang), _I18N["ar"])[key]


def _ooxml_lang_tag(lang: str) -> str:
    code = _lang_code(lang)
    if code == "en":
        return "en-US"
    if code == "fr":
        return "fr-FR"
    return "ar-IQ"


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


def _join_text_list(val: Any, sep: str = "، ") -> str:
    if isinstance(val, list):
        parts = [str(x).strip() for x in val if x is not None and str(x).strip()]
        return sep.join(parts)
    if val is None:
        return ""
    return str(val).strip()


def _get_day_minutes(day: Dict[str, Any]) -> int:
    if day.get("isHoliday"):
        return 0
    raw = day.get("durationMinutes")
    if raw is None:
        raw = day.get("minutes")
    if raw is None:
        return 0
    try:
        return max(0, int(float(raw)))
    except (ValueError, TypeError):
        return 0


def _compute_allocated_minutes(plan_snap: Dict[str, Any]) -> int:
    plan_type = plan_snap.get("planType", "daily")
    periods_count = int(plan_snap.get("periodsCount") or 1)
    period_minutes = int(plan_snap.get("periodMinutes") or 45)
    if plan_type == "daily":
        return periods_count * period_minutes

    days = [d for d in (plan_snap.get("scheduleDays") or []) if isinstance(d, dict)]
    active_days = [d for d in days if not d.get("isHoliday")]
    days_sum = sum(_get_day_minutes(d) for d in active_days)
    if days and days_sum > 0:
        return days_sum

    explicit = plan_snap.get("totalAllocatedMinutes")
    try:
        explicit_int = int(explicit) if explicit is not None else 0
    except (ValueError, TypeError):
        explicit_int = 0
    if explicit_int > 0:
        return explicit_int

    if active_days:
        return len(active_days) * periods_count * period_minutes
    if plan_type == "five_day":
        return 5 * periods_count * period_minutes
    return periods_count * period_minutes


def _format_time_description(plan_snap: Dict[str, Any], lang: str) -> str:
    plan_type = plan_snap.get("planType", "daily")
    periods_count = int(plan_snap.get("periodsCount") or 1)
    period_minutes = int(plan_snap.get("periodMinutes") or 45)
    total_min = _compute_allocated_minutes(plan_snap)
    if plan_type != "daily":
        return _tr(lang, "multi_day_time_fmt").format(total=total_min)
    period_word = _tr(lang, "period_word_single") if periods_count == 1 else _tr(lang, "period_word_plural")
    return _tr(lang, "periods_time_fmt").format(
        periods=periods_count,
        period_word=period_word,
        period_mins=period_minutes,
        total=total_min,
    )


def _localize_provenance(prov: Any, lang: str) -> str:
    raw = str(prov or "").strip()
    ar_default = _I18N["ar"]["default_provenance"]
    if not raw:
        return _tr(lang, "default_provenance")
    if _lang_code(lang) != "ar" and raw == ar_default:
        return _tr(lang, "default_provenance")
    return raw


def _format_context_banner(context_snap: Dict[str, Any], lang_override: Optional[str] = None) -> str:
    lang_val = lang_override or context_snap.get("language") or "ar"
    code = _lang_code(lang_val)
    ns = _tr(code, "not_specified")
    ne = _tr(code, "not_entered")
    return _tr(code, "banner_fmt").format(
        subject=context_snap.get("subject") or ns,
        grade=context_snap.get("grade") or ns,
        country=context_snap.get("country") or ns,
        curriculum=context_snap.get("curriculumName") or ns,
        lang=context_snap.get("language") or code,
        year=context_snap.get("year") or ne,
        edition=context_snap.get("edition") or ne,
    )


def _format_approval_badge(plan_snap: Dict[str, Any], source_status: str, lang: str = "ar") -> str:
    code = _lang_code(lang)
    status = str(plan_snap.get("status") or "draft")
    ver = plan_snap.get("version", 1)
    prov = _localize_provenance(plan_snap.get("provenanceLabel"), code)
    src_label = _tr(code, "source_status").get(source_status, source_status)
    status_label = _tr(code, "plan_status").get(status, status)
    if status == "approved":
        default_approver = "المعلم المراجع" if code == "ar" else ("Reviewing Teacher" if code == "en" else "Enseignant réviseur")
        approver = plan_snap.get("approvedBy") or plan_snap.get("teacherName") or default_approver
        return _tr(code, "approval_approved").format(
            ver=ver,
            approver=approver,
            src_status=src_label,
            prov=prov,
        )
    return _tr(code, "approval_draft").format(
        ver=ver,
        status=status_label,
        src_status=src_label,
        prov=prov,
    )


def _format_subject_item(item: Any, lang: str = "ar") -> Tuple[bool, str, str, str]:
    """
    Formats a subject item as (is_math, full_text, math_core, unit).
    Never dumps raw JSON braces/quotes for non-math domains.
    """
    code = _lang_code(lang)
    if not isinstance(item, dict):
        return False, str(item or ""), "", ""

    domain = str(item.get("domain") or "").lower().strip()
    if domain == "math":
        expr = str(item.get("expression") or "").strip()
        ans = str(item.get("expectedAnswer") or item.get("computedValue") or item.get("claimedAnswer") or "").strip()
        unit = str(item.get("unit") or "").strip()
        math_core = f"{expr} = {ans}" if (expr and ans) else (expr or ans)
        full_text = f"{math_core} {unit}".strip()
        return True, full_text, math_core, unit

    if domain == "literature":
        quote = str(item.get("quote") or "").strip()
        attr = str(item.get("attributedTo") or "").strip()
        rubric = str(item.get("rubric") or "").strip()
        if code == "en":
            parts = []
            if quote:
                parts.append(f'Quote: "{quote}"')
            parts.append(f"Attribution: {attr or 'Unattributed training example'}")
            if rubric:
                parts.append(f"Rubric: {rubric}")
            return False, " | ".join(parts), "", ""
        if code == "fr":
            parts = []
            if quote:
                parts.append(f"Citation : « {quote} »")
            parts.append(f"Source : {attr or 'Exemple non attribué'}")
            if rubric:
                parts.append(f"Critère : {rubric}")
            return False, " | ".join(parts), "", ""
        parts = []
        if quote:
            parts.append(f"الشاهد/النص: «{quote}»")
        parts.append(f"النسبة/المصدر: {attr or 'مثال تدريبي غير منسوب'}")
        if rubric:
            parts.append(f"محك التقييم: {rubric}")
        return False, " | ".join(parts), "", ""

    if domain == "history":
        events = item.get("events") or []
        ev_strs = []
        for ev in events:
            if isinstance(ev, dict):
                yr = str(ev.get("year") or "").strip()
                title = str(ev.get("event") or "").strip()
                evid = str(ev.get("evidence") or "").strip()
                if code == "en":
                    s = f"[{yr}] {title}" + (f" (Evidence: {evid})" if evid else "")
                elif code == "fr":
                    s = f"[{yr}] {title}" + (f" (Preuve : {evid})" if evid else "")
                else:
                    s = f"[{yr}] {title}" + (f" (الشاهد: {evid})" if evid else "")
                ev_strs.append(s.strip())
        if ev_strs:
            prefix = "Timeline: " if code == "en" else ("Chronologie : " if code == "fr" else "الخط الزمني: ")
            return False, prefix + " ؛ ".join(ev_strs) if code == "ar" else prefix + "; ".join(ev_strs), "", ""

    if domain == "science":
        hyp = str(item.get("hypothesis") or "").strip()
        vars_ = str(item.get("variables") or "").strip()
        unit = str(item.get("unit") or "").strip()
        safety = str(item.get("safety") or "").strip()
        if code == "en":
            parts = [f"Hypothesis: {hyp or '—'}"]
            if vars_:
                parts.append(f"Variables: {vars_}")
            if unit:
                parts.append(f"Unit: {unit}")
            if safety:
                parts.append(f"Safety: {safety}")
            return False, " | ".join(parts), "", ""
        if code == "fr":
            parts = [f"Hypothèse : {hyp or '—'}"]
            if vars_:
                parts.append(f"Variables : {vars_}")
            if unit:
                parts.append(f"Unité : {unit}")
            if safety:
                parts.append(f"Sécurité : {safety}")
            return False, " | ".join(parts), "", ""
        parts = [f"الفرضية: {hyp or '—'}"]
        if vars_:
            parts.append(f"المتغيرات: {vars_}")
        if unit:
            parts.append(f"الوحدة: {unit}")
        if safety:
            parts.append(f"السلامة: {safety}")
        return False, " | ".join(parts), "", ""

    # General or custom subject items: readable key-value summary (never raw JSON)
    parts = []
    topic = item.get("topic") or item.get("title") or item.get("question")
    if topic:
        lbl = "Topic" if code == "en" else ("Sujet" if code == "fr" else "الموضوع")
        parts.append(f"{lbl}: {topic}")
    if item.get("rubric"):
        lbl = "Rubric" if code == "en" else ("Critère" if code == "fr" else "محك التقييم")
        parts.append(f"{lbl}: {item['rubric']}")
    if item.get("solution"):
        lbl = "Solution" if code == "en" else ("Solution" if code == "fr" else "الحل")
        parts.append(f"{lbl}: {item['solution']}")
    if not parts:
        skip_keys = {"domain", "provenance"}
        for k, v in item.items():
            if k not in skip_keys and v not in (None, "", []):
                parts.append(f"{k}: {_join_text_list(v, ', ') if isinstance(v, list) else v}")
    prov = item.get("provenance")
    if prov:
        parts.append(_localize_provenance(prov, code))
    return False, " | ".join(parts) if parts else "—", "", ""


def _format_pdf_text(val: Any, rtl: bool) -> str:
    """
    Applies directional embedding markers that MuPDF Story obeys cleanly:
    - In LTR docs: wraps embedded Arabic runs in LRM + RLE..PDF + LRM so Arabic phrases don't scramble English punctuation/columns.
    - In RTL docs: wraps ISO dates (YYYY-MM-DD) and multi-term arithmetic expressions in LRE..PDF so hyphens/operators never flip.
    """
    s = str(val if val is not None else "")
    if not s:
        return s
    if not rtl:
        if _ARABIC_RUN_RE.search(s):
            return _ARABIC_RUN_RE.sub(lambda m: f"\u200E\u202B{m.group(0)}\u202C\u200E", s)
        return s
    return _RTL_LTR_TOKEN_RE.sub(lambda m: f"\u202A{m.group(0)}\u202C", s)


def _format_pdf_math_line(math_core: str, unit: str, rtl: bool) -> str:
    """
    Keeps mathematical formulas strictly LTR inside RTL bullet items without flipping
    bullet alignment or splitting Arabic units across the line.
    """
    if rtl:
        # \u200F anchors the bullet item RTL; \u202A..\u202C renders math LTR cleanly in MuPDF Story.
        base = f"\u200F\u202A{math_core}\u202C" if math_core else "\u200F"
        if unit:
            if _ARABIC_RUN_RE.search(unit):
                return f"{base} \u200F{unit}"
            return f"\u200F\u202A{math_core} {unit}\u202C"
        return base
    full = f"{math_core} {unit}".strip()
    return _format_pdf_text(full, rtl=False)


# ==============================================================================
# 1. REAL OOXML DOCX GENERATOR (.docx)
# ==============================================================================

def _w_p(
    text: str,
    rtl: bool = True,
    bold: bool = False,
    size_half_pts: int = 24,
    color_hex: str = "111827",
    lang_tag: str = "ar-IQ",
) -> str:
    bidi_tag = "<w:bidi/>" if rtl else ""
    jc_val = "right" if rtl else "left"
    rtl_run = "<w:rtl/>" if rtl else ""
    b_tag = "<w:b/><w:bCs/>" if bold else ""
    return (
        f"<w:p>"
        f"<w:pPr>{bidi_tag}<w:jc w:val=\"{jc_val}\"/><w:spacing w:before=\"80\" w:after=\"80\"/></w:pPr>"
        f"<w:r>"
        f"<w:rPr><w:rFonts w:ascii=\"Arial\" w:hAnsi=\"Arial\" w:cs=\"Arial\"/>"
        f"{b_tag}<w:color w:val=\"{color_hex}\"/><w:sz w:val=\"{size_half_pts}\"/><w:szCs w:val=\"{size_half_pts}\"/>"
        f"<w:lang w:val=\"{lang_tag}\" w:bidi=\"ar-IQ\"/>{rtl_run}</w:rPr>"
        f"<w:t xml:space=\"preserve\">{_xml_escape(text)}</w:t>"
        f"</w:r>"
        f"</w:p>"
    )


def _normalize_dxa_widths(num_cols: int, weights: Optional[List[int]] = None) -> List[int]:
    if num_cols <= 0:
        return []
    if not weights or len(weights) != num_cols:
        weights = [1] * num_cols
    safe_w = [max(1, int(w)) for w in weights]
    total_w = sum(safe_w)
    widths = [max(400, (_DOCX_CONTENT_WIDTH_DXA * w) // total_w) for w in safe_w]
    diff = _DOCX_CONTENT_WIDTH_DXA - sum(widths)
    if widths:
        widths[-1] += diff
    return widths


def _w_table(
    headers: List[str],
    rows: List[List[str]],
    rtl: bool = True,
    col_weights: Optional[List[int]] = None,
    lang_tag: str = "ar-IQ",
) -> str:
    num_cols = len(headers)
    col_widths = _normalize_dxa_widths(num_cols, col_weights)
    # In OOXML with <w:bidiVisual/>, Word/LibreOffice displays logical column 0 on the right.
    # Both <w:gridCol> and per-cell <w:tcW> are aligned in logical order 0..N-1.
    grid_cols = "".join(f"<w:gridCol w:w=\"{w}\"/>" for w in col_widths)
    bidi_visual = "<w:bidiVisual/>" if rtl else ""

    header_cells = "".join(
        f"<w:tc><w:tcPr><w:tcW w:w=\"{col_widths[idx]}\" w:type=\"dxa\"/>"
        f"<w:shd w:val=\"clear\" w:color=\"auto\" w:fill=\"154434\"/></w:tcPr>"
        f"{_w_p(h, rtl=rtl, bold=True, size_half_pts=22, color_hex='FFFFFF', lang_tag=lang_tag)}</w:tc>"
        for idx, h in enumerate(headers)
    )
    body_rows = ""
    for r_idx, row in enumerate(rows):
        fill = "F6F7F5" if r_idx % 2 == 1 else "FFFFFF"
        padded = list(row[:num_cols]) + [""] * max(0, num_cols - len(row))
        cells = "".join(
            f"<w:tc><w:tcPr><w:tcW w:w=\"{col_widths[c_idx]}\" w:type=\"dxa\"/>"
            f"<w:shd w:val=\"clear\" w:color=\"auto\" w:fill=\"{fill}\"/></w:tcPr>"
            f"{_w_p(cell, rtl=rtl, bold=False, size_half_pts=21, color_hex='1C2520', lang_tag=lang_tag)}</w:tc>"
            for c_idx, cell in enumerate(padded)
        )
        body_rows += f"<w:tr>{cells}</w:tr>"

    return (
        f"<w:tbl>"
        f"<w:tblPr>"
        f"<w:tblW w:w=\"{_DOCX_CONTENT_WIDTH_DXA}\" w:type=\"dxa\"/>"
        f"{bidi_visual}"
        f"<w:tblLayout w:type=\"fixed\"/>"
        f"<w:tblBorders>"
        f"<w:top w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"CBD5E1\"/>"
        f"<w:bottom w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"CBD5E1\"/>"
        f"<w:left w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"CBD5E1\"/>"
        f"<w:right w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"CBD5E1\"/>"
        f"<w:insideH w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"E2E8F0\"/>"
        f"<w:insideV w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"E2E8F0\"/>"
        f"</w:tblBorders>"
        f"</w:tblPr>"
        f"<w:tblGrid>{grid_cols}</w:tblGrid>"
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
    lang = _lang_code(context_snap.get("language", "ar"))
    rtl = _is_rtl_lang(context_snap.get("language", "ar"))
    lang_tag = _ooxml_lang_tag(lang)
    body_parts: List[str] = []

    if is_report and report_summary:
        body_parts.append(_w_p(_tr(lang, "report_title"), rtl=rtl, bold=True, size_half_pts=34, color_hex="154434", lang_tag=lang_tag))
        body_parts.append(_w_p(_format_context_banner(context_snap, lang), rtl=rtl, bold=True, size_half_pts=20, color_hex="176B52", lang_tag=lang_tag))
        disclaimer = str(report_summary.get("disclaimer") or _tr(lang, "report_disclaimer_default"))
        body_parts.append(_w_p(disclaimer, rtl=rtl, bold=False, size_half_pts=20, color_hex="B45309", lang_tag=lang_tag))

        rep_headers = _tr(lang, "report_headers")
        rep_row = [
            str(report_summary.get("totalPlans", 0)),
            str(report_summary.get("reviewedPlans", 0)),
            str(report_summary.get("draftPlans", 0)),
            str(report_summary.get("approvedPlans", 0)),
            str(report_summary.get("exportsCount", 0)),
        ]
        body_parts.append(_w_table(rep_headers, [rep_row], rtl=rtl, col_weights=[1, 1, 1, 1, 1], lang_tag=lang_tag))

        pat_rows = report_summary.get("patternSummary") or []
        if pat_rows:
            body_parts.append(_w_p(_tr(lang, "pattern_heading"), rtl=rtl, bold=True, size_half_pts=26, color_hex="154434", lang_tag=lang_tag))
            body_parts.append(
                _w_table(
                    _tr(lang, "pattern_headers"),
                    [[str(r.get("label", "")), str(r.get("planned", 0)), str(r.get("reviewed", 0)), str(r.get("exported", 0))] for r in pat_rows],
                    rtl=rtl,
                    col_weights=[4, 2, 2, 2],
                    lang_tag=lang_tag,
                )
            )
        gaps = report_summary.get("documentationGaps") or []
        if gaps:
            body_parts.append(_w_p(_tr(lang, "doc_gaps_heading"), rtl=rtl, bold=True, size_half_pts=26, color_hex="B45309", lang_tag=lang_tag))
            for g in gaps:
                body_parts.append(_w_p(f"• {g}", rtl=rtl, size_half_pts=22, lang_tag=lang_tag))
    else:
        title = plan_snap.get("title") or _tr(lang, "default_plan_title")
        body_parts.append(_w_p(title, rtl=rtl, bold=True, size_half_pts=34, color_hex="154434", lang_tag=lang_tag))
        body_parts.append(_w_p(_format_context_banner(context_snap, lang), rtl=rtl, bold=True, size_half_pts=20, color_hex="176B52", lang_tag=lang_tag))
        body_parts.append(_w_p(_format_approval_badge(plan_snap, source_status, lang), rtl=rtl, bold=False, size_half_pts=20, color_hex="B45309", lang_tag=lang_tag))

        raw_type = str(plan_snap.get("planType") or "daily")
        plan_type_label = _tr(lang, "plan_type").get(raw_type, raw_type)
        time_desc = _format_time_description(plan_snap, lang)
        ns = _tr(lang, "not_specified")
        ns_f = _tr(lang, "not_specified_f")

        meta_headers = _tr(lang, "meta_headers")
        meta_row = [
            plan_snap.get("teacherName") or context_snap.get("teacherName") or ns,
            plan_snap.get("schoolName") or context_snap.get("schoolName") or ns_f,
            plan_snap.get("sectionName") or context_snap.get("sectionName") or ns_f,
            plan_snap.get("planningDate") or ns,
            plan_type_label,
            time_desc,
        ]
        body_parts.append(_w_table(meta_headers, [meta_row], rtl=rtl, col_weights=[18, 20, 13, 14, 15, 20], lang_tag=lang_tag))

        # Objectives
        body_parts.append(_w_p(_tr(lang, "objectives_heading"), rtl=rtl, bold=True, size_half_pts=26, color_hex="154434", lang_tag=lang_tag))
        for idx, obj in enumerate(plan_snap.get("objectives") or [], start=1):
            body_parts.append(_w_p(f"{idx}. {obj}", rtl=rtl, bold=False, size_half_pts=22, lang_tag=lang_tag))

        # Prior Knowledge & Tools
        body_parts.append(_w_p(f"{_tr(lang, 'prior_knowledge_label')} {plan_snap.get('priorKnowledge') or '—'}", rtl=rtl, size_half_pts=22, lang_tag=lang_tag))
        tools_str = _join_text_list(plan_snap.get("teachingTools"), "، " if lang == "ar" else ", ") or _tr(lang, "default_tools")
        body_parts.append(_w_p(f"{_tr(lang, 'teaching_tools_label')} {tools_str}", rtl=rtl, size_half_pts=22, lang_tag=lang_tag))

        # General Teacher & Student Roles (when present)
        t_role = str(plan_snap.get("teacherRole") or "").strip()
        s_role = str(plan_snap.get("studentRole") or "").strip()
        if t_role or s_role:
            body_parts.append(_w_p(_tr(lang, "roles_heading"), rtl=rtl, bold=True, size_half_pts=26, color_hex="154434", lang_tag=lang_tag))
            if t_role:
                body_parts.append(_w_p(f"• {_tr(lang, 'teacher_role_label')} {t_role}", rtl=rtl, size_half_pts=22, lang_tag=lang_tag))
            if s_role:
                body_parts.append(_w_p(f"• {_tr(lang, 'student_role_label')} {s_role}", rtl=rtl, size_half_pts=22, lang_tag=lang_tag))

        # Phases Table (Daily) or Schedule Days Table (Weekly / 5-Day)
        if raw_type == "daily":
            body_parts.append(_w_p(_tr(lang, "phases_heading"), rtl=rtl, bold=True, size_half_pts=26, color_hex="154434", lang_tag=lang_tag))
            ph_headers = _tr(lang, "phases_headers")
            ph_rows = []
            for idx, ph in enumerate(plan_snap.get("phases") or [], start=1):
                src_ref = ph.get("sourceRef") or _tr(lang, "default_source_ref")
                mats = _join_text_list(ph.get("materials") or ph.get("pedagogicalAids") or "", "، " if lang == "ar" else ", ")
                ph_rows.append(
                    [
                        str(idx),
                        f"{_tr(lang, 'period_prefix')} {ph.get('periodNumber') or 1}",
                        str(ph.get("phaseName") or ph.get("name") or ""),
                        f"{mats} ({src_ref})" if mats else f"({src_ref})",
                        str(ph.get("teacherActivity") or ph.get("executorRole") or ph.get("teacherRole") or ""),
                        str(ph.get("studentActivity") or ph.get("studentRole") or ""),
                        str(ph.get("objective") or "—"),
                        f"{ph.get('minutes', 0)} {_tr(lang, 'minutes_short')}",
                    ]
                )
            if ph_rows:
                body_parts.append(_w_table(ph_headers, ph_rows, rtl=rtl, col_weights=[5, 9, 14, 15, 19, 16, 15, 7], lang_tag=lang_tag))
        else:
            body_parts.append(_w_p(_tr(lang, "schedule_heading"), rtl=rtl, bold=True, size_half_pts=26, color_hex="154434", lang_tag=lang_tag))
            day_headers = _tr(lang, "schedule_headers")
            day_rows = []
            for d in plan_snap.get("scheduleDays") or []:
                is_holiday = bool(d.get("isHoliday"))
                day_mins = _get_day_minutes(d)
                day_obj = _join_text_list(d.get("objectives"), "؛ " if lang == "ar" else "; ") or "—"
                day_act = _join_text_list(d.get("activities"), "؛ " if lang == "ar" else "; ") or "—"
                day_rows.append(
                    [
                        str(d.get("dayName") or ""),
                        _tr(lang, "holiday_label") if is_holiday else _tr(lang, "teaching_day_label"),
                        str(d.get("lessonTitle") or (_tr(lang, "holiday_row_note") if is_holiday else "—")),
                        "—" if is_holiday and day_obj == "—" else day_obj,
                        "—" if is_holiday and day_act == "—" else day_act,
                        str(d.get("assessment") or "—"),
                        str(day_mins),
                    ]
                )
            if day_rows:
                body_parts.append(_w_table(day_headers, day_rows, rtl=rtl, col_weights=[10, 10, 17, 21, 18, 16, 8], lang_tag=lang_tag))

        # Assessment, Differentiation, Homework & Home Enrichment
        body_parts.append(_w_p(_tr(lang, "assessment_heading"), rtl=rtl, bold=True, size_half_pts=26, color_hex="154434", lang_tag=lang_tag))
        body_parts.append(_w_p(f"• {_tr(lang, 'formative_label')} {plan_snap.get('formativeAssessment') or _tr(lang, 'missing_formative_label')}", rtl=rtl, size_half_pts=22, lang_tag=lang_tag))
        body_parts.append(_w_p(f"• {_tr(lang, 'diff_label')} {plan_snap.get('differentiation') or '—'}", rtl=rtl, size_half_pts=22, lang_tag=lang_tag))
        body_parts.append(_w_p(f"• {_tr(lang, 'homework_label')} {plan_snap.get('homework') or '—'}", rtl=rtl, size_half_pts=22, lang_tag=lang_tag))
        home_enr = int(plan_snap.get("homeEnrichmentMinutes") or 0)
        if home_enr > 0:
            body_parts.append(_w_p(f"• {_tr(lang, 'home_enrichment_fmt').format(mins=home_enr)}", rtl=rtl, size_half_pts=22, color_hex="176B52", lang_tag=lang_tag))

        # Planning Notes & References
        p_notes = str(plan_snap.get("planningNotes") or "").strip()
        ref_note = str(plan_snap.get("referencesNote") or "").strip()
        if p_notes or ref_note:
            body_parts.append(_w_p(_tr(lang, "notes_heading"), rtl=rtl, bold=True, size_half_pts=26, color_hex="154434", lang_tag=lang_tag))
            if p_notes:
                body_parts.append(_w_p(f"• {_tr(lang, 'planning_notes_label')} {p_notes}", rtl=rtl, size_half_pts=22, lang_tag=lang_tag))
            if ref_note:
                body_parts.append(_w_p(f"• {_tr(lang, 'references_note_label')} {ref_note}", rtl=rtl, size_half_pts=22, lang_tag=lang_tag))

        # Specialized Subject Items
        subj_items = plan_snap.get("subjectItems") or []
        if subj_items:
            body_parts.append(_w_p(_tr(lang, "subject_items_heading"), rtl=rtl, bold=True, size_half_pts=26, color_hex="154434", lang_tag=lang_tag))
            for item in subj_items:
                is_math, formatted, math_core, unit = _format_subject_item(item, lang)
                if is_math:
                    line = _format_pdf_math_line(math_core, unit, rtl=rtl) if rtl else formatted
                    body_parts.append(_w_p(f"• {line}", rtl=rtl, bold=True, size_half_pts=22, color_hex="176B52", lang_tag=lang_tag))
                else:
                    body_parts.append(_w_p(f"• {formatted}", rtl=rtl, size_half_pts=21, lang_tag=lang_tag))

        # Review Defects & Warnings Summary
        findings = review_snap.get("findings") or []
        if findings:
            body_parts.append(_w_p(_tr(lang, "audit_heading"), rtl=rtl, bold=True, size_half_pts=26, color_hex="154434", lang_tag=lang_tag))
            rev_headers = _tr(lang, "audit_headers")
            rev_rows = [
                [str(f.get("category") or ""), str(f.get("title") or ""), str(f.get("description") or ""), str(f.get("fieldTarget") or "—")]
                for f in findings
            ]
            body_parts.append(_w_table(rev_headers, rev_rows, rtl=rtl, col_weights=[16, 24, 42, 18], lang_tag=lang_tag))

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
    )

    styles_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:styles xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
        "<w:docDefaults><w:rPrDefault><w:rPr>"
        "<w:rFonts w:ascii=\"Arial\" w:hAnsi=\"Arial\" w:cs=\"Arial\"/>"
        f"<w:lang w:val=\"{lang_tag}\" w:bidi=\"ar-IQ\"/>"
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

def _build_slide_paragraphs(lines: List[str], rtl: bool, lang_tag: str = "ar-IQ") -> str:
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
            f"<a:rPr lang=\"{lang_tag}\" sz=\"2100\" dirty=\"0\">"
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
    lang: str = "ar",
) -> str:
    alg_attr = "r" if rtl else "l"
    rtl_val = "1" if rtl else "0"
    lang_tag = _ooxml_lang_tag(lang)

    if layout_style == "comparison":
        if len(slide_lines) >= 2:
            mid = (len(slide_lines) + 1) // 2
            col1_lines = slide_lines[:mid]
            col2_lines = slide_lines[mid:]
        elif len(slide_lines) == 1:
            col1_lines = slide_lines
            col2_lines = [_tr(lang, "slide_compare_companion")]
        else:
            col1_lines = [_tr(lang, "slide_fallback_body")]
            col2_lines = [_tr(lang, "slide_compare_companion")]

        col1_paras = _build_slide_paragraphs(col1_lines, rtl, lang_tag=lang_tag)
        col2_paras = _build_slide_paragraphs(col2_lines, rtl, lang_tag=lang_tag)
        # RTL starts CompareCol1 on the right (x=6200000) and CompareCol2 on the left (x=600000);
        # LTR places CompareCol1 on the left (x=600000) and CompareCol2 on the right (x=6200000).
        col1_x = "6200000" if rtl else "600000"
        col2_x = "600000" if rtl else "6200000"
        content_shapes = (
            "<p:sp>"
            "<p:nvSpPr><p:cNvPr id=\"3\" name=\"CompareCol1\"/><p:cNvSpPr txBox=\"1\"/><p:nvPr/></p:nvSpPr>"
            "<p:spPr>"
            f"<a:xfrm><a:off x=\"{col1_x}\" y=\"1750000\"/><a:ext cx=\"5392000\" cy=\"4100000\"/></a:xfrm>"
            "<a:prstGeom prst=\"roundRect\"><a:avLst/></a:prstGeom>"
            "<a:solidFill><a:srgbClr val=\"F6F7F5\"/></a:solidFill>"
            "<a:ln w=\"12700\"><a:solidFill><a:srgbClr val=\"176B52\"/></a:solidFill></a:ln>"
            "</p:spPr>"
            "<p:txBody>"
            "<a:bodyPr wrap=\"square\" lIns=\"150000\" tIns=\"150000\" rIns=\"150000\" bIns=\"150000\"/>"
            f"<a:lstStyle/>{col1_paras}</p:txBody></p:sp>"
            "<p:sp>"
            "<p:nvSpPr><p:cNvPr id=\"5\" name=\"CompareCol2\"/><p:cNvSpPr txBox=\"1\"/><p:nvPr/></p:nvSpPr>"
            "<p:spPr>"
            f"<a:xfrm><a:off x=\"{col2_x}\" y=\"1750000\"/><a:ext cx=\"5392000\" cy=\"4100000\"/></a:xfrm>"
            "<a:prstGeom prst=\"roundRect\"><a:avLst/></a:prstGeom>"
            "<a:solidFill><a:srgbClr val=\"EBF5F0\"/></a:solidFill>"
            "<a:ln w=\"12700\"><a:solidFill><a:srgbClr val=\"154434\"/></a:solidFill></a:ln>"
            "</p:spPr>"
            "<p:txBody>"
            "<a:bodyPr wrap=\"square\" lIns=\"150000\" tIns=\"150000\" rIns=\"150000\" bIns=\"150000\"/>"
            f"<a:lstStyle/>{col2_paras}</p:txBody></p:sp>"
        )
    else:
        body_paras = _build_slide_paragraphs(slide_lines, rtl, lang_tag=lang_tag)
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
        f"<a:r><a:rPr lang=\"{lang_tag}\" sz=\"2800\" b=\"1\" dirty=\"0\">"
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
        f"<a:r><a:rPr lang=\"{lang_tag}\" sz=\"1400\" dirty=\"0\">"
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
    lang = _lang_code(context_snap.get("language", "ar"))
    pres_settings = plan_snap.get("presentationSettings") or {}
    dir_setting = pres_settings.get("textDirection", "rtl" if _is_rtl_lang(lang) else "ltr")
    layout_style = pres_settings.get("layoutStyle", "title_and_content")
    rtl = dir_setting != "ltr" and _is_rtl_lang(context_snap.get("language", "ar"))

    custom_slides = [s for s in (plan_snap.get("slides") or []) if isinstance(s, dict)]
    if not custom_slides:
        objs = plan_snap.get("objectives") or [_tr(lang, "slide_default_obj")]
        if plan_snap.get("planType", "daily") != "daily" and plan_snap.get("scheduleDays"):
            days = plan_snap.get("scheduleDays") or []
            schedule_rows_lines = []
            for d in days:
                day_name = d.get("dayName") or _tr(lang, "slide_day_default")
                if d.get("isHoliday"):
                    schedule_rows_lines.append(
                        f"• {day_name}: {_tr(lang, 'holiday_row_note')} (0 {_tr(lang, 'minutes_short')})"
                    )
                else:
                    mins = _get_day_minutes(d)
                    lesson_t = d.get("lessonTitle") or _tr(lang, "slide_lesson_default")
                    schedule_rows_lines.append(
                        f"• {day_name}: {lesson_t} ({mins} {_tr(lang, 'minutes_short')})"
                    )

            custom_slides = [
                {
                    "title": plan_snap.get("title") or _tr(lang, "slide_weekly_title"),
                    "content": (
                        f"{_tr(lang, 'slide_context_prefix')} {_format_context_banner(context_snap, lang)}\n"
                        f"{_tr(lang, 'slide_objectives_prefix')} {' | '.join(objs[:2])}"
                    ),
                },
                {
                    "title": _tr(lang, "slide_schedule_overview_title"),
                    "content": "\n".join(schedule_rows_lines) or _tr(lang, "slide_fallback_body"),
                },
            ]
            for d in days:
                day_name = d.get("dayName") or _tr(lang, "slide_day_default")
                if d.get("isHoliday"):
                    custom_slides.append(
                        {
                            "title": f"{day_name}: {_tr(lang, 'holiday_label')}",
                            "content": f"• {_tr(lang, 'holiday_row_note')}\n• {_tr(lang, 'schedule_headers')[-1]}: 0 {_tr(lang, 'minutes_short')}",
                        }
                    )
                    continue
                mins = _get_day_minutes(d)
                day_obj = _join_text_list(d.get("objectives"), "؛ " if lang == "ar" else "; ") or "—"
                day_act = _join_text_list(d.get("activities"), "؛ " if lang == "ar" else "; ") or "—"
                custom_slides.append(
                    {
                        "title": f"{day_name}: {d.get('lessonTitle') or _tr(lang, 'slide_lesson_default')}",
                        "content": (
                            f"• {_tr(lang, 'objectives_heading')} {day_obj}\n"
                            f"• {_tr(lang, 'schedule_headers')[4]}: {day_act}\n"
                            f"• {_tr(lang, 'schedule_headers')[5]}: {d.get('assessment') or '—'} ({mins} {_tr(lang, 'minutes_short')})"
                        ),
                    }
                )
        else:
            phases = plan_snap.get("phases") or []
            split_idx = max(1, len(phases) // 2)
            part1_phases = phases[:split_idx]
            part2_phases = phases[split_idx:]
            mins_s = _tr(lang, "minutes_short")
            def_ph = _tr(lang, "slide_default_phase")
            custom_slides = [
                {
                    "title": plan_snap.get("title") or _tr(lang, "default_plan_title"),
                    "content": (
                        f"{_tr(lang, 'slide_context_prefix')} {_format_context_banner(context_snap, lang)}\n"
                        f"{_tr(lang, 'slide_teacher_label')} {plan_snap.get('teacherName') or '—'} | "
                        f"{_tr(lang, 'slide_section_label')} {plan_snap.get('sectionName') or '—'}"
                    ),
                },
                {
                    "title": _tr(lang, "slide_daily_obj_title"),
                    "content": "\n".join(f"• {o}" for o in objs)
                    + f"\n{_tr(lang, 'slide_prior_label')} {plan_snap.get('priorKnowledge') or _tr(lang, 'slide_default_prior')}",
                },
                {
                    "title": _tr(lang, "slide_phases_part1_title"),
                    "content": "\n".join(
                        f"• {p.get('phaseName') or p.get('name') or def_ph}: "
                        f"{p.get('teacherActivity') or p.get('executorRole') or p.get('teacherRole') or ''} ({p.get('minutes', 0)} {mins_s})"
                        for p in part1_phases
                    )
                    or _tr(lang, "slide_default_phase_prompt"),
                },
                {
                    "title": _tr(lang, "slide_phases_part2_title"),
                    "content": "\n".join(
                        f"• {p.get('phaseName') or p.get('name') or def_ph}: "
                        f"{p.get('studentActivity') or p.get('studentRole') or ''} ({p.get('minutes', 0)} {mins_s})"
                        for p in part2_phases
                    )
                    or (f"{_tr(lang, 'diff_label')} {plan_snap.get('differentiation')}" if plan_snap.get("differentiation") else _tr(lang, "slide_default_diff_prompt")),
                },
                {
                    "title": _tr(lang, "slide_closing_title"),
                    "content": (
                        f"{_tr(lang, 'formative_label')} {plan_snap.get('formativeAssessment') or _tr(lang, 'slide_default_formative')}\n"
                        f"{_tr(lang, 'homework_label')} {plan_snap.get('homework') or _tr(lang, 'slide_default_homework')}"
                    ),
                },
            ]

    wrap_width = 55 if layout_style == "comparison" else 85
    cont_suffix = _tr(lang, "slide_cont_suffix")
    expanded_slides: List[Dict[str, Any]] = []
    for idx, sld in enumerate(custom_slides, start=1):
        s_title = str(sld.get("title") or _tr(lang, "slide_fallback_title_fmt").format(idx=idx))
        raw_content = str(sld.get("content") or "")
        lines = [ln.strip() for ln in raw_content.splitlines() if ln.strip()] or [_tr(lang, "slide_fallback_body")]
        wrapped_lines: List[str] = []
        for ln in lines:
            if len(ln) > wrap_width + 5:
                wrapped_lines.extend(textwrap.wrap(ln, width=wrap_width, break_long_words=False))
            else:
                wrapped_lines.append(ln)
        for chunk_idx in range(0, len(wrapped_lines), 8):
            chunk_title = s_title if chunk_idx == 0 else f"{s_title} {cont_suffix}"
            expanded_slides.append({"title": chunk_title, "lines": wrapped_lines[chunk_idx : chunk_idx + 8]})

    footer_note = f"{_format_context_banner(context_snap, lang)} | {_format_approval_badge(plan_snap, source_status, lang)}"
    total_slides = len(expanded_slides)
    pres_rtl_attr = ' rtl="1"' if rtl else ""

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
            f"xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\"{pres_rtl_attr}>"
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
                lang=lang,
            )
            zf.writestr(f"ppt/slides/slide{idx}.xml", s_xml.encode("utf-8"))
            zf.writestr(f"ppt/slides/_rels/slide{idx}.xml.rels", slide_rel_xml.encode("utf-8"))

    return buf.getvalue()


# ==============================================================================
# 3. REAL PDF 1.7 GENERATOR (.pdf) WITH BUNDLED OFL FONT & CLEAN TOUNICODE CMAP
# ==============================================================================

def _build_pdf_table(
    headers: List[str],
    rows: List[List[str]],
    rtl: bool,
    col_pcts: Optional[List[int]] = None,
) -> str:
    """
    Renders an HTML table safe for MuPDF Story multi-page flow:
    - Uses `border-collapse: separate; border-spacing: 0;` to eliminate ghost header bars on page 2+.
    - Reverses cell order visually when `rtl=True` so Column 1 appears on the right in MuPDF Story.
    """
    num_cols = len(headers)
    idx_order = list(range(num_cols - 1, -1, -1)) if rtl else list(range(num_cols))

    th_html = ""
    for col_idx in idx_order:
        w_style = f" style=\"width:{col_pcts[col_idx]}%\"" if (col_pcts and len(col_pcts) == num_cols) else ""
        th_html += f"<th{w_style}>{_html_escape(_format_pdf_text(headers[col_idx], rtl))}</th>"

    rows_html = ""
    for row in rows:
        padded = list(row[:num_cols]) + [""] * max(0, num_cols - len(row))
        tds = ""
        for col_idx in idx_order:
            cell_txt = _format_pdf_text(padded[col_idx], rtl)
            tds += f"<td>{_html_escape(cell_txt)}</td>"
        rows_html += f"<tr>{tds}</tr>"

    return f"<table><tr>{th_html}</tr>{rows_html}</table>"


def _build_pdf_archive() -> Optional[Any]:
    if pymupdf is None:
        return None
    if (_FONTS_DIR / _REGULAR_FONT_FILE).is_file() and (_FONTS_DIR / _BOLD_FONT_FILE).is_file():
        return pymupdf.Archive(str(_FONTS_DIR))
    return None


def generate_plan_pdf_bytes(
    plan_snap: Dict[str, Any],
    context_snap: Dict[str, Any],
    review_snap: Dict[str, Any],
    source_status: str = "unverified_draft",
    is_report: bool = False,
    report_summary: Optional[Dict[str, Any]] = None,
) -> bytes:
    """
    Produces a real A4 PDF 1.7 with bundled OFL Tajawal Arabic+Latin TTFs,
    clean ToUnicode CMap extraction, RTL/LTR layout fidelity, multi-page flow
    without ghost fills, and isolated LTR mathematical equations.
    """
    lang = _lang_code(context_snap.get("language", "ar"))
    rtl = _is_rtl_lang(context_snap.get("language", "ar"))
    dir_attr = "rtl" if rtl else "ltr"
    accent_side = "border-right" if rtl else "border-left"

    def p_esc(val: Any) -> str:
        return _html_escape(_format_pdf_text(val, rtl))

    sections: List[str] = []
    doc_footer_label = ""
    if is_report and report_summary:
        doc_footer_label = _tr(lang, "report_title")
        sections.append(f"<h1>{p_esc(_tr(lang, 'report_title'))}</h1>")
        sections.append(f"<div class='banner'>{p_esc(_format_context_banner(context_snap, lang))}</div>")
        disclaimer = str(report_summary.get("disclaimer") or _tr(lang, "report_disclaimer_default"))
        sections.append(f"<div class='badge-warn'>{p_esc(disclaimer)}</div>")
        sections.append(
            _build_pdf_table(
                _tr(lang, "report_headers"),
                [[
                    str(report_summary.get("totalPlans", 0)),
                    str(report_summary.get("reviewedPlans", 0)),
                    str(report_summary.get("draftPlans", 0)),
                    str(report_summary.get("approvedPlans", 0)),
                    str(report_summary.get("exportsCount", 0)),
                ]],
                rtl=rtl,
                col_pcts=[20, 20, 20, 20, 20],
            )
        )
        pat_rows = report_summary.get("patternSummary") or []
        if pat_rows:
            sections.append(f"<h2>{p_esc(_tr(lang, 'pattern_heading').rstrip(':'))}</h2>")
            sections.append(
                _build_pdf_table(
                    _tr(lang, "pattern_headers"),
                    [[str(r.get("label", "")), str(r.get("planned", 0)), str(r.get("reviewed", 0)), str(r.get("exported", 0))] for r in pat_rows],
                    rtl=rtl,
                    col_pcts=[46, 18, 18, 18],
                )
            )
        gaps = report_summary.get("documentationGaps") or []
        if gaps:
            gaps_li = "".join(f"<li>• {p_esc(g)}</li>" for g in gaps)
            sections.append(f"<h2>{p_esc(_tr(lang, 'doc_gaps_heading').rstrip(':'))}</h2><ul class='clean'>{gaps_li}</ul>")
    else:
        title = str(plan_snap.get("title") or _tr(lang, "default_plan_title"))
        doc_footer_label = title
        sections.append(f"<h1>{p_esc(title)}</h1>")
        sections.append(f"<div class='banner'>{p_esc(_format_context_banner(context_snap, lang))}</div>")
        sections.append(f"<div class='badge-warn'>{p_esc(_format_approval_badge(plan_snap, source_status, lang))}</div>")

        raw_type = str(plan_snap.get("planType") or "daily")
        plan_type_label = _tr(lang, "plan_type").get(raw_type, raw_type)
        total_min = _compute_allocated_minutes(plan_snap)
        time_display = f"{total_min} {_tr(lang, 'minutes_unit')}"
        ns = _tr(lang, "not_specified")
        ns_f = _tr(lang, "not_specified_f")

        sections.append(
            _build_pdf_table(
                _tr(lang, "meta_headers"),
                [[
                    str(plan_snap.get("teacherName") or context_snap.get("teacherName") or ns),
                    str(plan_snap.get("schoolName") or context_snap.get("schoolName") or ns_f),
                    str(plan_snap.get("sectionName") or context_snap.get("sectionName") or ns_f),
                    str(plan_snap.get("planningDate") or "—"),
                    plan_type_label,
                    time_display,
                ]],
                rtl=rtl,
                col_pcts=[18, 22, 13, 13, 16, 18],
            )
        )

        objs = plan_snap.get("objectives") or []
        if objs:
            rlm_prefix = "\u200F" if rtl else ""
            objs_li = "".join(
                f"<li>{rlm_prefix}{idx}. {p_esc(o)}</li>"
                for idx, o in enumerate(objs, start=1)
            )
            sections.append(f"<h2>{p_esc(_tr(lang, 'objectives_heading').rstrip(':'))}</h2><ol class='clean'>{objs_li}</ol>")

        tools_str = _join_text_list(plan_snap.get("teachingTools"), "، " if lang == "ar" else ", ") or _tr(lang, "default_tools")
        sections.append(
            f"<p><strong>{p_esc(_tr(lang, 'prior_knowledge_label'))}</strong> {p_esc(plan_snap.get('priorKnowledge') or '—')}</p>"
            f"<p><strong>{p_esc(_tr(lang, 'teaching_tools_label'))}</strong> {p_esc(tools_str)}</p>"
        )

        t_role = str(plan_snap.get("teacherRole") or "").strip()
        s_role = str(plan_snap.get("studentRole") or "").strip()
        if t_role or s_role:
            sections.append(f"<h2>{p_esc(_tr(lang, 'roles_heading').rstrip(':'))}</h2>")
            if t_role:
                sections.append(f"<p><strong>{p_esc(_tr(lang, 'teacher_role_label'))}</strong> {p_esc(t_role)}</p>")
            if s_role:
                sections.append(f"<p><strong>{p_esc(_tr(lang, 'student_role_label'))}</strong> {p_esc(s_role)}</p>")

        if raw_type == "daily":
            ph_rows = []
            for idx, ph in enumerate(plan_snap.get("phases") or [], start=1):
                mats = _join_text_list(ph.get("materials") or ph.get("pedagogicalAids") or "", "، " if lang == "ar" else ", ")
                src_ref = ph.get("sourceRef") or _tr(lang, "default_source_ref")
                ph_rows.append([
                    str(idx),
                    f"{_tr(lang, 'period_prefix')} {ph.get('periodNumber') or 1}",
                    str(ph.get("phaseName") or ph.get("name") or ""),
                    f"{mats} ({src_ref})" if mats else src_ref,
                    str(ph.get("teacherActivity") or ph.get("executorRole") or ph.get("teacherRole") or ""),
                    str(ph.get("studentActivity") or ph.get("studentRole") or ""),
                    str(ph.get("objective") or "—"),
                    f"{ph.get('minutes', 0)} {_tr(lang, 'minutes_short')}",
                ])
            if ph_rows:
                sections.append(f"<h2>{p_esc(_tr(lang, 'phases_heading').rstrip(':'))}</h2>")
                sections.append(
                    _build_pdf_table(
                        _tr(lang, "phases_headers"),
                        ph_rows,
                        rtl=rtl,
                        col_pcts=[4, 8, 13, 14, 20, 17, 16, 8],
                    )
                )
        else:
            d_rows = []
            for d in plan_snap.get("scheduleDays") or []:
                is_holiday = bool(d.get("isHoliday"))
                day_mins = _get_day_minutes(d)
                day_obj = _join_text_list(d.get("objectives"), "؛ " if lang == "ar" else "; ") or "—"
                day_act = _join_text_list(d.get("activities"), "؛ " if lang == "ar" else "; ") or "—"
                d_rows.append([
                    str(d.get("dayName") or ""),
                    _tr(lang, "holiday_label") if is_holiday else _tr(lang, "teaching_day_label"),
                    str(d.get("lessonTitle") or (_tr(lang, "holiday_row_note") if is_holiday else "—")),
                    "—" if is_holiday and day_obj == "—" else day_obj,
                    "—" if is_holiday and day_act == "—" else day_act,
                    str(d.get("assessment") or "—"),
                    f"{day_mins} {_tr(lang, 'minutes_short')}",
                ])
            if d_rows:
                sections.append(f"<h2>{p_esc(_tr(lang, 'schedule_heading').rstrip(':'))}</h2>")
                sections.append(
                    _build_pdf_table(
                        _tr(lang, "schedule_headers"),
                        d_rows,
                        rtl=rtl,
                        col_pcts=[10, 10, 16, 21, 18, 17, 8],
                    )
                )

        home_enr = int(plan_snap.get("homeEnrichmentMinutes") or 0)
        enrichment_html = (
            f"<p><strong>{_html_escape(_tr(lang, 'home_enrichment_fmt').format(mins=home_enr))}</strong></p>"
            if home_enr > 0
            else ""
        )
        sections.append(
            f"<h2>{p_esc(_tr(lang, 'assessment_heading').rstrip(':'))}</h2>"
            f"<p><strong>{p_esc(_tr(lang, 'formative_label'))}</strong> {p_esc(plan_snap.get('formativeAssessment') or _tr(lang, 'missing_formative_label'))}</p>"
            f"<p><strong>{p_esc(_tr(lang, 'diff_label'))}</strong> {p_esc(plan_snap.get('differentiation') or '—')}</p>"
            f"<p><strong>{p_esc(_tr(lang, 'homework_label'))}</strong> {p_esc(plan_snap.get('homework') or '—')}</p>"
            f"{enrichment_html}"
        )

        p_notes = str(plan_snap.get("planningNotes") or "").strip()
        ref_note = str(plan_snap.get("referencesNote") or "").strip()
        if p_notes or ref_note:
            sections.append(f"<h2>{p_esc(_tr(lang, 'notes_heading').rstrip(':'))}</h2>")
            if p_notes:
                sections.append(f"<p><strong>{p_esc(_tr(lang, 'planning_notes_label'))}</strong> {p_esc(p_notes)}</p>")
            if ref_note:
                sections.append(f"<p><strong>{p_esc(_tr(lang, 'references_note_label'))}</strong> {p_esc(ref_note)}</p>")

        subj_items = plan_snap.get("subjectItems") or []
        if subj_items:
            items_html = ""
            for item in subj_items:
                is_math, formatted, math_core, unit = _format_subject_item(item, lang)
                if is_math:
                    safe_math = _html_escape(_format_pdf_math_line(math_core, unit, rtl))
                    bullet = "\u200F• " if rtl else "• "
                    items_html += f"<li class='math-item'>{bullet}{safe_math}</li>"
                else:
                    bullet = "\u200F• " if rtl else "• "
                    items_html += f"<li>{bullet}{p_esc(formatted)}</li>"
            sections.append(f"<h2>{p_esc(_tr(lang, 'subject_items_heading').rstrip(':'))}</h2><ul class='clean'>{items_html}</ul>")

        findings = review_snap.get("findings") or []
        if findings:
            f_rows = [
                [str(f.get("category") or ""), str(f.get("title") or ""), str(f.get("description") or ""), str(f.get("fieldTarget") or "—")]
                for f in findings
            ]
            sections.append(f"<h2>{p_esc(_tr(lang, 'audit_heading').rstrip(':'))}</h2>")
            sections.append(
                _build_pdf_table(
                    _tr(lang, "audit_headers"),
                    f_rows,
                    rtl=rtl,
                    col_pcts=[15, 24, 43, 18],
                )
            )

    archive = _build_pdf_archive()
    font_face_css = (
        f"@font-face {{ font-family: 'Tajawal'; src: url('{_REGULAR_FONT_FILE}'); font-weight: normal; font-style: normal; }}\n"
        f"@font-face {{ font-family: 'Tajawal'; src: url('{_BOLD_FONT_FILE}'); font-weight: bold; font-style: normal; }}"
        if archive is not None
        else ""
    )
    font_family_rule = "'Tajawal', sans-serif" if archive is not None else "sans-serif"

    # Note: MuPDF Story treats `text-align: start;` as right-aligned under `dir="rtl"` and left-aligned under `dir="ltr"`.
    # Block divs (.banner, .badge-warn) intentionally avoid `background-color` and tables use `border-collapse: separate`
    # so MuPDF Story never emits ghost fill bars on continuation pages.
    html_doc = f"""<!DOCTYPE html>
<html dir="{dir_attr}" lang="{_html_escape(lang)}">
<head>
<meta charset="utf-8"/>
<style>
  {font_face_css}
  body {{ font-family: {font_family_rule}; font-size: 9.5pt; line-height: 1.5; color: #1C2520; direction: {dir_attr}; text-align: start; }}
  h1, h2, p, div, ul, ol, li, th, td {{ direction: {dir_attr}; text-align: start; }}
  h1 {{ color: #154434; font-size: 15pt; margin: 0 0 6px 0; border-bottom: 2px solid #154434; padding-bottom: 4px; page-break-after: avoid; }}
  h2 {{ color: #154434; font-size: 11.5pt; margin: 11px 0 4px 0; page-break-after: avoid; }}
  .banner {{ color: #154434; padding: 6px 8px; font-size: 8.8pt; font-weight: bold; margin-bottom: 6px; border: 1px solid #B7E0CC; {accent_side}: 4px solid #176B52; }}
  .badge-warn {{ color: #92400E; padding: 6px 8px; font-size: 8.8pt; margin-bottom: 8px; border: 1px solid #F59E0B; {accent_side}: 4px solid #B45309; }}
  table {{ width: 100%; border-collapse: separate; border-spacing: 0; margin: 6px 0 10px 0; font-size: 8.6pt; border-top: 1px solid #CBD5E1; border-left: 1px solid #CBD5E1; }}
  th {{ background-color: #154434; color: #FFFFFF; padding: 5px; border-right: 1px solid #CBD5E1; border-bottom: 1px solid #CBD5E1; font-weight: bold; }}
  td {{ padding: 5px; border-right: 1px solid #CBD5E1; border-bottom: 1px solid #CBD5E1; vertical-align: top; }}
  ul.clean, ol.clean {{ list-style-type: none; margin: 4px 0 8px 0; padding: 0; }}
  ul.clean li, ol.clean li {{ margin: 2px 0; }}
  li.math-item {{ font-weight: bold; color: #176B52; }}
  p {{ margin: 4px 0; }}
</style>
</head>
<body>
{''.join(sections)}
</body>
</html>"""

    if pymupdf is not None:
        story = pymupdf.Story(html=html_doc, archive=archive) if archive is not None else pymupdf.Story(html=html_doc)
        buf = io.BytesIO()
        mediabox = pymupdf.paper_rect("a4")
        where = mediabox + (32, 32, -32, -46)
        writer = pymupdf.DocumentWriter(buf)
        more = True
        while more:
            dev = writer.begin_page(mediabox)
            more, _ = story.place(where)
            story.draw(dev, pymupdf.Identity)
            writer.end_page()
        writer.close()

        doc = pymupdf.open(stream=buf.getvalue(), filetype="pdf")
        total_pages = len(doc)
        footer_css = font_face_css
        for page_idx, page in enumerate(doc, start=1):
            page_label = _tr(lang, "page_footer_fmt").format(page=page_idx, total=total_pages)
            footer_txt = _format_pdf_text(f"{page_label} — {doc_footer_label[:60]}", rtl)
            footer_rect = pymupdf.Rect(32, mediabox.height - 34, mediabox.width - 32, mediabox.height - 14)
            footer_html = (
                f"<div dir=\"{dir_attr}\" style=\"font-family: {font_family_rule}; font-size: 8pt; "
                f"color: #64748B; text-align: center; border-top: 1px solid #CBD5E1; padding-top: 3px;\">"
                f"{_html_escape(footer_txt)}</div>"
            )
            if archive is not None:
                page.insert_htmlbox(footer_rect, footer_html, css=footer_css, archive=archive)
            else:
                page.insert_htmlbox(footer_rect, footer_html)

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
            grids = root.findall(".//w:tblGrid", ns)
            return {
                "passed": len(texts) > 0 and len(tables) > 0 and len(grids) == len(tables),
                "format": "OOXML_DOCX",
                "paragraphsOrRunsCount": len(texts),
                "tablesCount": len(tables),
                "tableGridsCount": len(grids),
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
        control_chars_count = 0
        mojibake_chars_count = 0
        if pymupdf is not None and has_header:
            try:
                with pymupdf.open(stream=file_bytes, filetype="pdf") as doc:
                    pages_count = len(doc)
                    full_txt = "".join(p.get_text("text") or "" for p in doc)
                    extracted_chars = len(full_txt.strip())
                    control_chars_count = len(_CONTROL_CHAR_RE.findall(full_txt))
                    mojibake_chars_count = sum(1 for ch in full_txt if ch in _CMAP_MOJIBAKE_CHARS)
            except Exception:
                pages_count = 0
        else:
            pages_count = 1 if b"/Type /Page" in file_bytes else 0
            extracted_chars = 1 if (b"BT " in file_bytes and b" ET" in file_bytes) else 0
        return {
            "passed": bool(
                has_header
                and has_eof
                and pages_count >= 1
                and extracted_chars > 0
                and control_chars_count == 0
                and mojibake_chars_count == 0
            ),
            "format": "PDF_1_7",
            "pagesCount": pages_count,
            "hasSelectableTextStream": extracted_chars > 0,
            "controlCharsCount": control_chars_count,
            "mojibakeCharsCount": mojibake_chars_count,
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
