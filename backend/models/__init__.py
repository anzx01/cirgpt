"""Backend SQLAlchemy models.

The concrete ``CircuitDesign`` and ``DesignHistory`` model classes live in
``circuit_design.py`` and ``design_history.py`` respectively. They import
the shared ``Base`` from this module, so this ``__init__`` only needs to
expose the declarative base plus a small ``init_db`` helper that brings
the SQLite schema in line with the current model definitions.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

from models.circuit_design import CircuitDesign
from models.design_history import DesignHistory


_engine = None
_SessionLocal: Optional[sessionmaker] = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.DB_URL,
            connect_args={"check_same_thread": False} if settings.DB_URL.startswith("sqlite") else {},
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _SessionLocal


def SessionLocal():
    return get_session_factory()()


def init_db() -> None:
    """Create all tables and apply forward-only column additions.

    Safe to call repeatedly. For SQLite, ``ALTER TABLE ADD COLUMN`` has no
    ``IF NOT EXISTS`` form, so we issue each addition and swallow the
    "duplicate column" error if the column is already there.
    """
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    if engine.dialect.name != "sqlite":
        return

    forward_columns = {
        "circuit_designs": [
            ("schematic_pages", "TEXT"),
            ("schematic_png", "TEXT"),
            ("simulation_status", "VARCHAR(50)"),
        ],
    }
    raw_conn = engine.connect()
    try:
        for table, cols in forward_columns.items():
            for col_name, col_type in cols:
                stmt = f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"
                try:
                    raw_conn.exec_driver_sql(stmt)
                except Exception as exc:  # noqa: BLE001 - duplicate column is the expected no-op
                    msg = str(exc).lower()
                    if "duplicate column" in msg or "already exists" in msg:
                        continue
                    raise
    finally:
        raw_conn.close()


__all__ = [
    "Base",
    "CircuitDesign",
    "DesignHistory",
    "SessionLocal",
    "get_engine",
    "get_session_factory",
    "init_db",
]
