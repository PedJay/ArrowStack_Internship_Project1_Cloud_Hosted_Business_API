from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_db_credentials, get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    url = settings.database_url
    if url.get_backend_name() == "sqlite":
        engine = create_engine(url, connect_args={"check_same_thread": False})

        # SQLite ignores foreign keys unless asked; keep behaviour identical to Postgres.
        @event.listens_for(engine, "connect")
        def _enable_fk(dbapi_conn, _record):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        return engine

    engine = create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5, pool_recycle=1800)
    if settings.db_secret_arn:
        _use_rotating_credentials(engine)
    return engine


def _use_rotating_credentials(engine: Engine) -> None:
    """Inject credentials from Secrets Manager on every new DB connection.

    If login fails (password was just rotated), re-read the secret once and retry.
    """

    @event.listens_for(engine, "do_connect")
    def _connect(dialect, _conn_rec, cargs, cparams):
        for attempt in (1, 2):
            cparams["user"], cparams["password"] = get_db_credentials(force_refresh=attempt == 2)
            try:
                return dialect.connect(*cargs, **cparams)
            except dialect.loaded_dbapi.OperationalError:
                if attempt == 2:
                    raise


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    session = _session_factory()()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    from app import models  # noqa: F401  (registers tables on Base.metadata)

    engine = get_engine()
    if engine.dialect.name != "postgresql":
        Base.metadata.create_all(engine)
        return
    # Several uvicorn workers start at once; serialize schema creation with an advisory lock.
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(724001)"))
        Base.metadata.create_all(conn)
