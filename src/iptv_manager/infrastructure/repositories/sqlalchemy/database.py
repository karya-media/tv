"""Database engine and session factory setup.

Uses a synchronous SQLAlchemy engine/session rather than an async
driver: SQLite (the default) gains little from async I/O, and keeping
this layer synchronous avoids adding an aiosqlite/asyncpg dependency
just for a handful of small, infrequent writes. Callers that need this
from async code (the FastAPI app) wrap calls in asyncio.to_thread -
see SQLAlchemyPipelineRunRepository.
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker

from iptv_manager.infrastructure.repositories.sqlalchemy.models import Base


def create_db_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


def init_db(engine: Engine) -> None:
    """Create all tables that don't already exist. Safe to call every
    startup (idempotent)."""
    Base.metadata.create_all(engine)


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)
