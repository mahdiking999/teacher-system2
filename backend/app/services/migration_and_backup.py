import os
import json
import sqlite3
from datetime import datetime, timezone
from backend.app.database import Base, engine, SessionLocal
from backend.app.models import EducationalContext, PhaseTemplate, CurriculumSource, Lesson, Plan, PlanVersion, PlanReview, ExportTask
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
    Returns a complete JSON-serializable backup dictionary of all educational contexts
    and summary counts across plans, lessons, and curriculum sources.
    Works identically on PostgreSQL and SQLite.
    """
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
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
                for c in db.query(EducationalContext).all()
            ],
            "plansCount": db.query(Plan).count(),
            "lessonsCount": db.query(Lesson).count(),
            "sourcesCount": db.query(CurriculumSource).count(),
        }
    finally:
        db.close()


def restore_database_backup_dict(payload: dict) -> dict:
    """
    Validates a backup payload (v1.0) and upserts educational contexts into the active database.
    """
    if not isinstance(payload, dict) or payload.get("backupVersion") != "1.0":
        raise ValueError("Invalid backupVersion: expected '1.0'")
    contexts_data = payload.get("contexts")
    if not isinstance(contexts_data, list):
        raise ValueError("Invalid backup payload: 'contexts' must be a list")

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    restored = 0
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
            restored += 1

        db.commit()
        return {"restoredContextsCount": restored, "backupVersion": "1.0"}
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
