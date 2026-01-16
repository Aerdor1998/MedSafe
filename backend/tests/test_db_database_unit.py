from __future__ import annotations

import pytest


class _FakeResult:
    def __init__(self, fetchone_value=None, scalar_value=None):
        self._fetchone_value = fetchone_value
        self._scalar_value = scalar_value

    def fetchone(self):
        return self._fetchone_value

    def scalar(self):
        return self._scalar_value


class _FakeConn:
    def __init__(self):
        self.executed = []
        self.committed = False
        self._responses = []

    def queue_response(self, result: _FakeResult):
        self._responses.append(result)

    def execute(self, stmt):
        self.executed.append(str(stmt))
        if self._responses:
            return self._responses.pop(0)
        return _FakeResult()

    def commit(self):
        self.committed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeEngine:
    def __init__(
        self,
        url: str,
        conn: _FakeConn | None = None,
        raise_on_connect: Exception | None = None,
    ):
        self.url = url
        self._conn = conn or _FakeConn()
        self._raise = raise_on_connect

    def connect(self):
        if self._raise is not None:
            raise self._raise
        return self._conn


@pytest.fixture(autouse=True)
def _required_env(monkeypatch):
    """
    Ensure Settings() can be imported in isolation.

    These tests import `backend.app.db.database`, which imports `backend.app.config.settings`.
    When running a subset of tests directly, the root `pytest.ini` env plugin may not apply,
    so we set a minimal deterministic environment here.
    """
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-minimum-32-characters-long")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
    # Use Postgres URL so SQLAlchemy engine creation in `db/database.py` doesn't
    # reject pool args (sqlite dialect is stricter about these kwargs).
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://medsafe:test_password@localhost:5432/medsafe"
    )


def test_init_db_sqlite_calls_create_all(monkeypatch):
    from backend.app.db import database as db

    fake_conn = _FakeConn()
    fake_engine = _FakeEngine("sqlite:///:memory:", conn=fake_conn)
    monkeypatch.setattr(db, "engine", fake_engine, raising=True)

    called = {"create_all": 0, "create_indexes": 0}

    monkeypatch.setattr(
        db.Base.metadata,
        "create_all",
        lambda bind=None: called.__setitem__("create_all", called["create_all"] + 1),
    )
    monkeypatch.setattr(
        db,
        "create_indexes",
        lambda: called.__setitem__("create_indexes", called["create_indexes"] + 1),
    )

    # Force flags
    monkeypatch.setattr(db.settings, "debug", False, raising=False)
    monkeypatch.setattr(db.settings, "testing", True, raising=False)

    db.init_db()
    assert called["create_all"] == 1
    # sqlite -> indexes not created
    assert called["create_indexes"] == 0


def test_init_db_postgres_dev_creates_vector_extension_and_indexes(monkeypatch):
    from backend.app.db import database as db

    fake_conn = _FakeConn()
    # vector extension missing -> fetchone None
    fake_conn.queue_response(_FakeResult(fetchone_value=None))
    fake_engine = _FakeEngine("postgresql://example", conn=fake_conn)
    monkeypatch.setattr(db, "engine", fake_engine, raising=True)

    called = {"create_all": 0, "create_indexes": 0}
    monkeypatch.setattr(
        db.Base.metadata,
        "create_all",
        lambda bind=None: called.__setitem__("create_all", called["create_all"] + 1),
    )
    monkeypatch.setattr(
        db,
        "create_indexes",
        lambda: called.__setitem__("create_indexes", called["create_indexes"] + 1),
    )

    monkeypatch.setattr(db.settings, "debug", True, raising=False)  # dev
    monkeypatch.setattr(db.settings, "testing", False, raising=False)

    db.init_db()
    assert any("CREATE EXTENSION IF NOT EXISTS vector" in s for s in fake_conn.executed)
    assert fake_conn.committed is True
    # debug -> create_all + create_indexes
    assert called["create_all"] == 1
    assert called["create_indexes"] == 1


def test_init_db_postgres_prod_missing_vector_raises(monkeypatch):
    from backend.app.db import database as db

    fake_conn = _FakeConn()
    fake_conn.queue_response(_FakeResult(fetchone_value=None))  # missing vector
    fake_engine = _FakeEngine("postgresql://example", conn=fake_conn)
    monkeypatch.setattr(db, "engine", fake_engine, raising=True)

    monkeypatch.setattr(db.settings, "debug", False, raising=False)  # prod-ish
    monkeypatch.setattr(db.settings, "testing", False, raising=False)

    with pytest.raises(RuntimeError):
        db.init_db()


def test_check_db_health_true_and_false(monkeypatch):
    from backend.app.db import database as db

    ok_engine = _FakeEngine("sqlite:///:memory:", conn=_FakeConn())
    monkeypatch.setattr(db, "engine", ok_engine, raising=True)
    assert db.check_db_health() is True

    bad_engine = _FakeEngine(
        "sqlite:///:memory:", raise_on_connect=RuntimeError("nope")
    )
    monkeypatch.setattr(db, "engine", bad_engine, raising=True)
    assert db.check_db_health() is False


def test_get_db_stats_returns_empty_on_failure(monkeypatch):
    from backend.app.db import database as db

    bad_engine = _FakeEngine(
        "postgresql://example", raise_on_connect=RuntimeError("boom")
    )
    monkeypatch.setattr(db, "engine", bad_engine, raising=True)
    assert db.get_db_stats() == {}
