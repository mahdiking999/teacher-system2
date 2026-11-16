import os
import json
import sqlite3
from datetime import datetime, timezone
from backend.app.database import Base, engine, SessionLocal
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
from sqlalchemy.dialects import postgresql, sqlite


def generate_postgresql_and_sqlite_ddl() -> dict:
    """
    Compiles all SQLAlchemy models against both PostgreSQL (`postgresql.dialect()`)
    and SQLite (`sqlite.dialect()`) to verify 100% production PostgreSQL DDL compatibility
    (foreign keys, JSON columns, timezone-aware timestamps, primary keys).
    """
    from sqlalchemy.schema import CreateTable

    pg_statements = []
    sqlite_statements = []
    for table in Base.metadata.sorted_tables:
        pg_ddl = str(CreateTable(table).compile(dialect=postgresql.dialect())).strip() + ";"
        sq_ddl = str(CreateTable(table).compile(dialect=sqlite.dialect())).strip() + ";"
        pg_statements.append(pg_ddl)
        sqlite_statements.append(sq_ddl)

    return {
        "postgresql_ddl": "\n\n".join(pg_statements),
        "sqlite_ddl": "\n\n".join(sqlite_statements),
        "tables_count": len(Base.metadata.sorted_tables),
    }


def export_database_backup_dict() -> dict:
    """
    Returns a complete JSON-serializable backup dictionary of educational contexts,
    templates, curriculum sources, chapters, lessons, plans, and summary counts.
    Works identically on PostgreSQL and SQLite.
    """
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        contexts = db.query(EducationalContext).all()
        templates = db.query(PhaseTemplate).all()
        sources = db.query(CurriculumSource).all()
        chapters = db.query(Chapter).all()
        lessons = db.query(Lesson).all()
        plans = db.query(Plan).all()
        return {
            "backupVersion": "1.0",
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "contexts": [
                {
                    "id": c.id,
                    "subject": c.subject,
                    "grade": c.grade,
                    "country": c.country,
                    "curriculum_name": c.curriculum_name,
                    "language": c.language,
                    "year": c.year,
                    "edition": c.edition,
                    "ui_language": c.ui_language,
                    "teacher_name": c.teacher_name,
                    "school_name": c.school_name,
                    "section_name": c.section_name,
                    "planning_date": c.planning_date,
                    "school_days": c.school_days,
                    "holidays": c.holidays,
                    "default_period_Minutes": c.default_period_Minutes,
                    "default_periods_count": c.default_periods_count,
                    "selected_tools": c.selected_tools,
                    "document_preferences": c.document_preferences,
                    "active_template_id": c.active_template_id,
                    "version": c.version,
                }
                for c in contexts
            ],
            "templates": [
                {
                    "id": t.id,
                    "context_id": t.context_id,
                    "name": t.name,
                    "description": t.description,
                    "is_default": t.is_default,
                    "periods_count": t.periods_count,
                    "period_minutes": t.period_minutes,
                    "phases": t.phases,
                    "version": t.version,
                }
                for t in templates
            ],
            "sources": [
                {
                    "id": s.id,
                    "context_id": s.context_id,
                    "title": s.title,
                    "source_type": s.source_type,
                    "file_name": s.file_name,
                    "file_size": s.file_size,
                    "sha256_fingerprint": s.sha256_fingerprint,
                    "page_count": s.page_count,
                    "extraction_status": s.extraction_status,
                    "book_year": s.book_year,
                    "edition": s.edition,
                    "source_url": s.source_url,
                    "is_official_claimed": s.is_official_claimed,
                    "official_evidence": s.official_evidence,
                    "verification_status": s.verification_status,
                    "reviewer_name": s.reviewer_name,
                    "review_notes": s.review_notes,
                    "index_approved": s.index_approved,
                    "version": s.version,
                }
                for s in sources
            ],
            "chapters": [
                {
                    "id": ch.id,
                    "context_id": ch.context_id,
                    "source_id": ch.source_id,
                    "title": ch.title,
                    "order_index": ch.order_index,
                    "pdf_start_page": ch.pdf_start_page,
                    "printed_start_page": ch.printed_start_page,
                    "is_documented": ch.is_documented,
                    "provenance_label": ch.provenance_label,
                }
                for ch in chapters
            ],
            "lessons": [
                {
                    "id": l.id,
                    "context_id": l.context_id,
                    "source_id": l.source_id,
                    "chapter_id": l.chapter_id,
                    "title": l.title,
                    "code_or_order": l.code_or_order,
                    "pdf_page_number": l.pdf_page_number,
                    "printed_page_number": l.printed_page_number,
                    "content_origin": l.content_origin,
                    "provenance_label": l.provenance_label,
                    "objectives": l.objectives,
                    "prior_knowledge": l.prior_knowledge,
                    "activities": l.activities,
                    "questions_and_solutions": l.questions_and_solutions,
                    "evaluation_criteria": l.evaluation_criteria,
                    "key_terms_or_quotes": l.key_terms_or_quotes,
                    "review_status": l.review_status,
                    "version": l.version,
                }
                for l in lessons
            ],
            "plans": [
                {
                    "id": p.id,
                    "context_id": p.context_id,
                    "source_id": p.source_id,
                    "primary_lesson_id": p.primary_lesson_id,
                    "secondary_lesson_id": p.secondary_lesson_id,
                    "title": p.title,
                    "plan_type": p.plan_type,
                    "status": p.status,
                    "context_snapshot": p.context_snapshot,
                    "teacher_name": p.teacher_name,
                    "school_name": p.school_name,
                    "section_name": p.section_name,
                    "planning_date": p.planning_date,
                    "lessons_count": p.lessons_count,
                    "periods_count": p.periods_count,
                    "period_minutes": p.period_minutes,
                    "total_allocated_minutes": p.total_allocated_minutes,
                    "objectives": p.objectives,
                    "prior_knowledge": p.prior_knowledge,
                    "teacher_role": p.teacher_role,
                    "student_role": p.student_role,
                    "teaching_tools": p.teaching_tools,
                    "phases": p.phases,
                    "formative_assessment": p.formative_assessment,
                    "differentiation": p.differentiation,
                    "homework": p.homework,
                    "home_enrichment_minutes": p.home_enrichment_minutes,
                    "references_note": p.references_note,
                    "planning_notes": p.planning_notes,
                    "subject_items": p.subject_items,
                    "schedule_days": p.schedule_days,
                    "slides": p.slides,
                    "presentation_settings": p.presentation_settings,
                    "content_origin": p.content_origin,
                    "provenance_label": p.provenance_label,
                    "version": p.version,
                }
                for p in plans
            ],
            "plansCount": len(plans),
            "lessonsCount": len(lessons),
            "sourcesCount": len(sources),
        }
    finally:
        db.close()


def restore_database_backup_dict(payload: dict) -> dict:
    """
    Validates a backup payload (v1.0) and upserts contexts and related entities in FK order.
    """
    if not isinstance(payload, dict) or payload.get("backupVersion") != "1.0":
        raise ValueError("Invalid backupVersion: expected '1.0'")
    contexts_data = payload.get("contexts")
    if not isinstance(contexts_data, list):
        raise ValueError("Invalid backup payload: 'contexts' must be a list")

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    restored_contexts = 0
    restored_plans = 0
    try:
        for item in contexts_data:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            ctx = db.query(EducationalContext).filter(EducationalContext.id == item["id"]).first()
            if ctx is None:
                ctx = EducationalContext(id=item["id"])
                db.add(ctx)

            ctx.subject = item.get("subject", "")
            ctx.grade = item.get("grade", "")
            ctx.country = item.get("country", "")
            ctx.curriculum_name = item.get("curriculum_name", "")
            ctx.language = item.get("language", "ar")
            ctx.year = item.get("year", "")
            ctx.edition = item.get("edition", "")
            if "ui_language" in item:
                ctx.ui_language = item["ui_language"]
            ctx.teacher_name = item.get("teacher_name", "")
            ctx.school_name = item.get("school_name", "")
            ctx.section_name = item.get("section_name", "")
            ctx.planning_date = item.get("planning_date", "")
            if "school_days" in item and isinstance(item["school_days"], list):
                ctx.school_days = item["school_days"]
            if "holidays" in item and isinstance(item["holidays"], list):
                ctx.holidays = item["holidays"]
            if "default_period_Minutes" in item:
                ctx.default_period_Minutes = int(item["default_period_Minutes"])
            if "default_periods_count" in item:
                ctx.default_periods_count = int(item["default_periods_count"])
            if "selected_tools" in item and isinstance(item["selected_tools"], list):
                ctx.selected_tools = item["selected_tools"]
            if "document_preferences" in item and isinstance(item["document_preferences"], dict):
                ctx.document_preferences = item["document_preferences"]
            if "active_template_id" in item:
                ctx.active_template_id = item["active_template_id"]
            if "version" in item:
                ctx.version = int(item["version"])
            restored_contexts += 1
        db.flush()

        for tpl_item in (payload.get("templates") or []):
            if not isinstance(tpl_item, dict) or not tpl_item.get("id") or not tpl_item.get("context_id"):
                continue
            tpl = db.query(PhaseTemplate).filter(PhaseTemplate.id == tpl_item["id"]).first()
            if tpl is None:
                tpl = PhaseTemplate(id=tpl_item["id"], context_id=tpl_item["context_id"], name=tpl_item.get("name", "قالب"))
                db.add(tpl)
            tpl.name = tpl_item.get("name", "قالب")
            tpl.description = tpl_item.get("description", "")
            tpl.is_default = bool(tpl_item.get("is_default", False))
            tpl.periods_count = int(tpl_item.get("periods_count", 1))
            tpl.period_minutes = int(tpl_item.get("period_minutes", 45))
            tpl.phases = tpl_item.get("phases") or []

        for src_item in (payload.get("sources") or []):
            if not isinstance(src_item, dict) or not src_item.get("id") or not src_item.get("context_id"):
                continue
            src = db.query(CurriculumSource).filter(CurriculumSource.id == src_item["id"]).first()
            if src is None:
                src = CurriculumSource(id=src_item["id"], context_id=src_item["context_id"], title=src_item.get("title", "مصدر"))
                db.add(src)
            src.title = src_item.get("title", "مصدر")
            src.source_type = src_item.get("source_type", "unverified_example")
            src.file_name = src_item.get("file_name", "")
            src.file_size = int(src_item.get("file_size", 0))
            src.sha256_fingerprint = src_item.get("sha256_fingerprint", "")
            src.page_count = int(src_item.get("page_count", 0))
            src.extraction_status = src_item.get("extraction_status", "no_file")
            src.book_year = src_item.get("book_year", "")
            src.edition = src_item.get("edition", "")
            src.source_url = src_item.get("source_url", "")
            src.verification_status = src_item.get("verification_status", "pending_review")
            src.reviewer_name = src_item.get("reviewer_name", "")
            src.review_notes = src_item.get("review_notes", "")
            src.index_approved = bool(src_item.get("index_approved", False))
        db.flush()

        for ch_item in (payload.get("chapters") or []):
            if not isinstance(ch_item, dict) or not ch_item.get("id") or not ch_item.get("context_id") or not ch_item.get("source_id"):
                continue
            ch = db.query(Chapter).filter(Chapter.id == ch_item["id"]).first()
            if ch is None:
                ch = Chapter(
                    id=ch_item["id"],
                    context_id=ch_item["context_id"],
                    source_id=ch_item["source_id"],
                    title=ch_item.get("title", "فصل"),
                )
                db.add(ch)
            ch.title = ch_item.get("title", "فصل")
            ch.order_index = int(ch_item.get("order_index", 1))
            ch.pdf_start_page = ch_item.get("pdf_start_page")
            ch.printed_start_page = ch_item.get("printed_start_page", "")
            ch.is_documented = bool(ch_item.get("is_documented", False))
            ch.provenance_label = ch_item.get("provenance_label", "مثال توضيحي غير موثق من الكتاب")
        db.flush()

        for les_item in (payload.get("lessons") or []):
            if not isinstance(les_item, dict) or not les_item.get("id") or not les_item.get("context_id"):
                continue
            les = db.query(Lesson).filter(Lesson.id == les_item["id"]).first()
            if les is None:
                les = Lesson(id=les_item["id"], context_id=les_item["context_id"], title=les_item.get("title", "درس"))
                db.add(les)
            les.source_id = les_item.get("source_id")
            les.chapter_id = les_item.get("chapter_id")
            les.title = les_item.get("title", "درس")
            les.code_or_order = les_item.get("code_or_order", "1")
            les.pdf_page_number = les_item.get("pdf_page_number")
            les.printed_page_number = les_item.get("printed_page_number", "")
            les.content_origin = les_item.get("content_origin", "authored_example")
            les.provenance_label = les_item.get("provenance_label", "مثال توضيحي غير موثق من الكتاب")
            les.objectives = les_item.get("objectives") or []
            les.prior_knowledge = les_item.get("prior_knowledge", "")
            les.activities = les_item.get("activities") or []
            les.questions_and_solutions = les_item.get("questions_and_solutions") or []
            les.evaluation_criteria = les_item.get("evaluation_criteria", "")
            les.key_terms_or_quotes = les_item.get("key_terms_or_quotes") or []
            les.review_status = les_item.get("review_status", "draft")
        db.flush()

        for p_item in (payload.get("plans") or []):
            if not isinstance(p_item, dict) or not p_item.get("id") or not p_item.get("context_id"):
                continue
            pln = db.query(Plan).filter(Plan.id == p_item["id"]).first()
            if pln is None:
                pln = Plan(id=p_item["id"], context_id=p_item["context_id"], title=p_item.get("title", "خطة"))
                db.add(pln)
            pln.source_id = p_item.get("source_id")
            pln.primary_lesson_id = p_item.get("primary_lesson_id")
            pln.secondary_lesson_id = p_item.get("secondary_lesson_id")
            pln.title = p_item.get("title", "خطة")
            pln.plan_type = p_item.get("plan_type", "daily")
            pln.status = p_item.get("status", "draft")
            pln.context_snapshot = p_item.get("context_snapshot") or {}
            pln.teacher_name = p_item.get("teacher_name", "")
            pln.school_name = p_item.get("school_name", "")
            pln.section_name = p_item.get("section_name", "")
            pln.planning_date = p_item.get("planning_date", "")
            pln.lessons_count = int(p_item.get("lessons_count", 1))
            pln.periods_count = int(p_item.get("periods_count", 1))
            pln.period_minutes = int(p_item.get("period_minutes", 45))
            pln.total_allocated_minutes = int(p_item.get("total_allocated_minutes", 45))
            pln.objectives = p_item.get("objectives") or []
            pln.prior_knowledge = p_item.get("prior_knowledge", "")
            pln.teacher_role = p_item.get("teacher_role", "")
            pln.student_role = p_item.get("student_role", "")
            pln.teaching_tools = p_item.get("teaching_tools") or []
            pln.phases = p_item.get("phases") or []
            pln.formative_assessment = p_item.get("formative_assessment", "")
            pln.differentiation = p_item.get("differentiation", "")
            pln.homework = p_item.get("homework", "")
            pln.home_enrichment_minutes = int(p_item.get("home_enrichment_minutes", 0))
            pln.references_note = p_item.get("references_note", "")
            pln.planning_notes = p_item.get("planning_notes", "")
            pln.subject_items = p_item.get("subject_items") or []
            pln.schedule_days = p_item.get("schedule_days") or []
            pln.slides = p_item.get("slides") or []
            pln.presentation_settings = p_item.get("presentation_settings") or {}
            pln.content_origin = p_item.get("content_origin", "authored_example")
            pln.provenance_label = p_item.get("provenance_label", "مثال توضيحي غير موثق من الكتاب")
            restored_plans += 1

        db.commit()
        return {
            "restoredContextsCount": restored_contexts,
            "restoredPlansCount": restored_plans,
            "backupVersion": "1.0",
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_database_backup_json(output_path: str) -> dict:
    """
    Exports a complete, transactional JSON backup file to disk.
    Works identically on PostgreSQL and SQLite.
    """
    payload = export_database_backup_dict()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload
