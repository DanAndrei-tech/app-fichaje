"""La migración y los modelos deben coincidir, y la migración debe poder revertirse."""

from alembic import command
from sqlalchemy import Engine, inspect

from tests.conftest import TEST_DATABASE_URL, alembic_config

BUSINESS_TABLES = {
    "companies",
    "users",
    "employees",
    "terminals",
    "clock_events",
    "work_sessions",
    "work_breaks",
    "audit_logs",
}


def _tables(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


def test_models_match_migrations(db_engine: Engine) -> None:
    # Falla si algún modelo tiene cambios que no están en ninguna migración.
    command.check(alembic_config(TEST_DATABASE_URL))

    assert _tables(db_engine) == BUSINESS_TABLES


def test_migration_downgrade_and_upgrade(db_engine: Engine) -> None:
    config = alembic_config(TEST_DATABASE_URL)

    command.downgrade(config, "base")
    assert _tables(db_engine) == set()

    command.upgrade(config, "head")
    assert _tables(db_engine) == BUSINESS_TABLES
