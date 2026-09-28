"""Factorías mínimas para los tests del modelo de datos.

Crean filas válidas con valores por defecto razonables; cada test cambia
solo lo que le interesa. Los PIN y tokens son bytes aleatorios de 32 bytes:
aquí no se genera ningún PIN real.
"""

import secrets
import uuid
from datetime import UTC, date, datetime
from typing import Any

import pytest
from sqlalchemy import TextClause
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.clock.models import ClockEvent, ClockEventType, WorkSession, WorkSessionStatus
from app.modules.companies.models import Company
from app.modules.employees.models import Employee
from app.modules.terminals.models import Terminal
from app.modules.users.models import User, UserRole

T0 = datetime(2026, 9, 28, 20, 0, tzinfo=UTC)
WORK_DATE = date(2026, 9, 28)


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


def random_digest() -> bytes:
    """32 bytes, como un HMAC-SHA256 o un SHA-256."""
    return secrets.token_bytes(32)


def make_company(session: Session, **overrides: Any) -> Company:
    values: dict[str, Any] = {"name": "Empresa de prueba", "slug": f"empresa-{_suffix()}"}
    company = Company(**(values | overrides))
    session.add(company)
    session.flush()
    return company


def make_user(session: Session, company: Company | None, **overrides: Any) -> User:
    values: dict[str, Any] = {
        "company_id": company.id if company else None,
        "email": f"admin-{_suffix()}@example.com",
        "full_name": "Admin de prueba",
        "password_hash": "$argon2id$v=19$m=65536,t=3,p=4$fake$fake",
        "role": UserRole.ADMIN,
    }
    user = User(**(values | overrides))
    session.add(user)
    session.flush()
    return user


def make_employee(session: Session, company: Company, **overrides: Any) -> Employee:
    values: dict[str, Any] = {
        "company_id": company.id,
        "first_name": "Ana",
        "last_name": "García",
        "pin_lookup": random_digest(),
        "pin_key_version": 1,
    }
    employee = Employee(**(values | overrides))
    session.add(employee)
    session.flush()
    return employee


def make_terminal(session: Session, company: Company, **overrides: Any) -> Terminal:
    values: dict[str, Any] = {
        "company_id": company.id,
        "name": f"Tablet {_suffix()}",
        "token_hash": random_digest(),
    }
    terminal = Terminal(**(values | overrides))
    session.add(terminal)
    session.flush()
    return terminal


def make_work_session(session: Session, employee: Employee, **overrides: Any) -> WorkSession:
    values: dict[str, Any] = {
        "company_id": employee.company_id,
        "employee_id": employee.id,
        "work_date": WORK_DATE,
        "started_at": T0,
        "status": WorkSessionStatus.OPEN,
    }
    work_session = WorkSession(**(values | overrides))
    session.add(work_session)
    session.flush()
    return work_session


def make_clock_event(
    session: Session, work_session: WorkSession, terminal: Terminal, **overrides: Any
) -> ClockEvent:
    values: dict[str, Any] = {
        "company_id": work_session.company_id,
        "employee_id": work_session.employee_id,
        "terminal_id": terminal.id,
        "work_session_id": work_session.id,
        "event_type": ClockEventType.CLOCK_IN,
        "idempotency_key": uuid.uuid4(),
    }
    event = ClockEvent(**(values | overrides))
    session.add(event)
    session.flush()
    return event


def assert_violates(session: Session, constraint_name: str, *objects: object) -> None:
    """Comprueba que insertar `objects` viola exactamente `constraint_name`.

    Se ejecuta en un SAVEPOINT para que el error no invalide la sesión del test.
    """
    with pytest.raises(IntegrityError) as exc_info:
        with session.begin_nested():
            session.add_all(objects)
            session.flush()
    assert exc_info.value.orig.diag.constraint_name == constraint_name  # type: ignore[union-attr]


def assert_sql_violates(
    session: Session, constraint_name: str, statement: TextClause, params: dict[str, Any]
) -> None:
    """Igual que assert_violates, pero con SQL directo (salta las validaciones del ORM)."""
    with pytest.raises(IntegrityError) as exc_info:
        with session.begin_nested():
            session.execute(statement, params)
    assert exc_info.value.orig.diag.constraint_name == constraint_name  # type: ignore[union-attr]
