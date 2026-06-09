from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import settings

# Create database engine
engine = create_engine(
    settings.DB_URL,
    connect_args={"check_same_thread": False} if settings.DB_URL.startswith("sqlite") else {}
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()

# Import all models
from models.circuit_design import CircuitDesign
from models.design_history import DesignHistory

# Create all tables
def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


def _ensure_sqlite_columns():
    """Add v1 columns to existing local SQLite databases.

    This project does not ship Alembic migrations yet, so local users may have
    an older app.db created by the prototype. Keep this tiny compatibility shim
    scoped to SQLite; production deployments should replace it with migrations.
    """
    if not settings.DB_URL.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "circuit_designs" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("circuit_designs")}
    columns = {
        "progress": "INTEGER DEFAULT 0",
        "current_step": "VARCHAR(255)",
        "job_id": "VARCHAR(100)",
        "circuit_ir": "JSON",
        "validation": "JSON",
        "artifacts": "JSON",
    }

    with engine.begin() as conn:
        for name, definition in columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE circuit_designs ADD COLUMN {name} {definition}"))

__all__ = ["engine", "SessionLocal", "Base", "CircuitDesign", "DesignHistory", "init_db"]
