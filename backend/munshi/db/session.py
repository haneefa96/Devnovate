"""
Munshi - Database session management

Engine is created once at module import.
Sessions are created per-request via get_session().
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, create_engine

from munshi.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)


if engine.dialect.name == "sqlite":

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection: object, connection_record: object) -> None:
        """Enforce foreign key constraints for the application SQLite database."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()


# Session factory — callers use get_session() rather than this directly
_SessionLocal: sessionmaker = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session,
)


def get_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency: yield a database session, always close on exit.

    Usage:
        @router.get("/items")
        def list_items(session: Session = Depends(get_session)):
            return session.exec(select(Item)).all()
    """
    session: Session = _SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def session_scope(target_engine: Engine | None = None) -> Generator[Session, None, None]:
    """
    Transactional session context manager for background tasks, scripts, and tests.
    Commits on normal exit, rolls back on exception, and closes always.
    """
    session: Session = Session(target_engine or engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(target_engine: Engine | None = None) -> None:
    """Create tables and apply safe, additive SQLite columns for existing local DBs."""
    eng = target_engine or engine
    SQLModel.metadata.create_all(bind=eng)
    if eng.dialect.name != "sqlite":
        return

    additions = {
        "invoice": {
            "invoice_gstin": "VARCHAR(15)",
            "po_amount_paise": "INTEGER",
        },
        "action": {
            "evidence": "JSON NOT NULL DEFAULT '[]'",
            "reason": "TEXT NOT NULL DEFAULT ''",
            "dedupe_key": "VARCHAR(200)",
            "handoff_opened_at": "DATETIME",
            "delivery_confirmation_source": "VARCHAR(30)",
            "delivery_confirmed_by": "VARCHAR(255)",
        },
        "risk_alert": {
            "memory_status": "VARCHAR(20) NOT NULL DEFAULT 'UNAVAILABLE'",
        },
    }
    with eng.begin() as connection:
        for table_name, columns in additions.items():
            existing_columns = {
                column["name"]
                for column in inspect(connection).get_columns(table_name)
            }
            for column_name, column_type in columns.items():
                if column_name not in existing_columns:
                    connection.execute(
                        text(
                            f'ALTER TABLE "{table_name}" ADD COLUMN '
                            f'"{column_name}" {column_type}'
                        )
                    )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_action_dedupe_key "
                "ON action (dedupe_key)"
            )
        )


def reset_db(target_engine: Engine | None = None) -> None:
    """
    Drop all tables then recreate them.
    Used in tests and simulation reset only — never call in production.
    """
    eng = target_engine or engine
    SQLModel.metadata.drop_all(bind=eng)
    SQLModel.metadata.create_all(bind=eng)
