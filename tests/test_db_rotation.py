"""The Postgres engine re-reads the secret and retries once when login fails after a password rotation."""
import psycopg
import pytest
from sqlalchemy import create_engine

from app import db


def _connect_once(engine):
    (listener,) = list(engine.dialect.dispatch.do_connect)
    return listener(engine.dialect, None, [], {"host": "db.internal"})


def test_retries_with_fresh_credentials(monkeypatch):
    calls = []

    def fake_creds(force_refresh=False):
        calls.append(force_refresh)
        return ("app", "new-pass" if force_refresh else "old-pass")

    def fake_connect(*_args, **params):
        if params["password"] == "old-pass":
            raise psycopg.OperationalError("password authentication failed")
        return "connection"

    monkeypatch.setattr(db, "get_db_credentials", fake_creds)
    engine = create_engine("postgresql+psycopg://db.internal/businessapi")
    db._use_rotating_credentials(engine)
    monkeypatch.setattr(engine.dialect, "connect", fake_connect)

    assert _connect_once(engine) == "connection"
    assert calls == [False, True]


def test_gives_up_after_second_failure(monkeypatch):
    monkeypatch.setattr(db, "get_db_credentials", lambda force_refresh=False: ("app", "bad"))
    engine = create_engine("postgresql+psycopg://db.internal/businessapi")
    db._use_rotating_credentials(engine)

    def always_fail(*_a, **_k):
        raise psycopg.OperationalError("password authentication failed")

    monkeypatch.setattr(engine.dialect, "connect", always_fail)
    with pytest.raises(psycopg.OperationalError):
        _connect_once(engine)
