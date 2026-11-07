"""
Munshi - Database session management

Engine is created once at module import.
Sessions are created per-request via get_session().
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import event
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
    """Create all tables (idempotent — safe to call on startup)."""
    SQLModel.metadata.create_all(bind=target_engine or engine)


def reset_db(target_engine: Engine | None = None) -> None:
    """
    Drop all tables then recreate them.
    Used in tests and simulation reset only — never call in production.
    """
    eng = target_engine or engine
    SQLModel.metadata.drop_all(bind=eng)
    SQLModel.metadata.create_all(bind=eng)
