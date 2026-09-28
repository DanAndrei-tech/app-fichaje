"""Tests de la infraestructura de base de datos (sin tablas: solo SELECT 1)."""

from unittest.mock import patch

import pytest
from sqlalchemy import Engine, make_url, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db import session as db_session_module
from app.db.session import get_db


def test_tests_use_the_test_database(db_session: Session) -> None:
    database_name = db_session.scalar(text("SELECT current_database()"))

    assert database_name is not None
    assert database_name.endswith("_test")
    assert database_name != make_url(settings.database_url).database


def test_engine_connects_to_postgresql(db_engine: Engine) -> None:
    with db_engine.connect() as connection:
        assert connection.scalar(text("SELECT 1")) == 1


def test_session_executes_simple_query(db_session: Session) -> None:
    assert db_session.execute(text("SELECT 1")).scalar_one() == 1


@pytest.fixture
def get_db_uses_test_database(db_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    """Hace que get_db cree sus sesiones contra la base de datos de tests."""
    monkeypatch.setattr(
        db_session_module,
        "SessionLocal",
        sessionmaker(bind=db_engine, expire_on_commit=False),
    )


@pytest.mark.usefixtures("get_db_uses_test_database")
def test_get_db_commits_and_closes_session(db_engine: Engine) -> None:
    connections_before = db_engine.pool.checkedout()  # type: ignore[attr-defined]
    dependency = get_db()
    session = next(dependency)

    assert session.execute(text("SELECT 1")).scalar_one() == 1
    assert db_engine.pool.checkedout() == connections_before + 1  # type: ignore[attr-defined]

    with patch.object(session, "commit", wraps=session.commit) as commit:
        with pytest.raises(StopIteration):
            next(dependency)  # el endpoint termina bien

    commit.assert_called_once()
    assert not session.in_transaction()
    assert db_engine.pool.checkedout() == connections_before  # type: ignore[attr-defined]


@pytest.mark.usefixtures("get_db_uses_test_database")
def test_get_db_rolls_back_and_closes_session_on_exception(db_engine: Engine) -> None:
    connections_before = db_engine.pool.checkedout()  # type: ignore[attr-defined]
    dependency = get_db()
    session = next(dependency)
    session.execute(text("SELECT 1"))

    with (
        patch.object(session, "commit", wraps=session.commit) as commit,
        patch.object(session, "rollback", wraps=session.rollback) as rollback,
    ):
        with pytest.raises(RuntimeError, match="fallo en el endpoint"):
            dependency.throw(RuntimeError("fallo en el endpoint"))

    commit.assert_not_called()
    rollback.assert_called_once()
    assert not session.in_transaction()
    assert db_engine.pool.checkedout() == connections_before  # type: ignore[attr-defined]
