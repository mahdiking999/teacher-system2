import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base


def normalize_database_url(url: str) -> str:
    """Normalize postgres:// and postgresql:// URLs to SQLAlchemy's psycopg2 driver."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


DATA_DIR = os.path.abspath(os.getenv("DATA_DIR", "."))
os.makedirs(DATA_DIR, exist_ok=True)
default_sqlite_path = os.path.join(DATA_DIR, "teacher_system.db").replace("\\", "/")

DATABASE_URL = normalize_database_url(os.getenv("DATABASE_URL", f"sqlite:///{default_sqlite_path}"))

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    connect_args["timeout"] = 15

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
