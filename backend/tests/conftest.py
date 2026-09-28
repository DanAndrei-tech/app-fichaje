"""Infraestructura común de los tests.

Base de datos de tests
----------------------
Los tests NUNCA usan la base de datos de desarrollo. Usan una base de datos
propia en el mismo servidor PostgreSQL:

- la de TEST_DATABASE_URL, si está definida;
- si no, la de DATABASE_URL con el sufijo "_test" (fichaje -> fichaje_test).

Se crea automáticamente si no existe. Por seguridad, si su nombre no termina
en "_test", los tests se detienen antes de conectarse.

Aislamiento entre tests
-----------------------
Cada test que usa `db_session` (o `client`) trabaja dentro de una transacción
que se deshace al terminar: nada de lo que haga queda guardado. Los commits
de la aplicación se convierten en SAVEPOINTs dentro de esa transacción.

Cuando existan modelos, la fixture `db_engine` aplicará las migraciones
(alembic upgrade head) sobre la base de datos de tests.
"""

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL, Engine, create_engine, make_url, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.main import app


def _test_database_url() -> URL:
    raw_url = os.environ.get("TEST_DATABASE_URL")
    if raw_url:
        url = make_url(raw_url)
    else:
        dev_url = make_url(settings.database_url)
        url = dev_url.set(database=f"{dev_url.database}_test")

    if not (url.database or "").endswith("_test"):
        raise RuntimeError(
            f"La base de datos de tests debe terminar en '_test' (se obtuvo '{url.database}')."
        )
    return url


TEST_DATABASE_URL = _test_database_url()


def _create_database_if_missing(url: URL) -> None:
    # CREATE DATABASE no puede ir dentro de una transacción: AUTOCOMMIT.
    admin_engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": url.database},
            )
            if not exists:
                quoted_name = connection.dialect.identifier_preparer.quote(url.database)
                connection.execute(text(f"CREATE DATABASE {quoted_name}"))
    finally:
        admin_engine.dispose()


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    """Engine conectado a la base de datos de tests (uno para toda la sesión de tests)."""
    _create_database_if_missing(TEST_DATABASE_URL)
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    """Sesión dentro de una transacción que se deshace al terminar el test."""
    with db_engine.connect() as connection:
        transaction = connection.begin()
        session = Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    """Cliente HTTP de la API cuyos endpoints usan la sesión de tests."""

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
