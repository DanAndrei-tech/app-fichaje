from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.db.immutability import ImmutableDataError
from app.modules.employees.models import Employee

from .factories import assert_violates, make_company, make_employee, random_digest


def _employee(company_id: object, **values: object) -> Employee:
    defaults: dict[str, object] = {
        "company_id": company_id,
        "first_name": "Luis",
        "last_name": "Pérez",
        "pin_lookup": random_digest(),
        "pin_key_version": 1,
    }
    return Employee(**(defaults | values))


def test_employee_belongs_to_company(db_session: Session) -> None:
    company = make_company(db_session)
    employee = make_employee(db_session, company)

    assert employee.company is company
    assert employee.active is True
    assert employee.pin_generated_at is not None


def test_duplicate_dni_in_same_company_fails(db_session: Session) -> None:
    company = make_company(db_session)
    make_employee(db_session, company, dni="12345678Z")

    assert_violates(db_session, "uq_employees_company_id_dni", _employee(company.id, dni="12345678Z"))


def test_same_dni_in_another_company_is_allowed(db_session: Session) -> None:
    make_employee(db_session, make_company(db_session), dni="12345678Z")
    other = make_employee(db_session, make_company(db_session), dni="12345678Z")

    assert other.dni == "12345678Z"


def test_several_employees_without_dni_are_allowed(db_session: Session) -> None:
    company = make_company(db_session)
    make_employee(db_session, company, dni=None)
    make_employee(db_session, company, dni=None)


def test_dni_must_be_normalized(db_session: Session) -> None:
    company = make_company(db_session)

    assert_violates(db_session, "ck_employees_dni_format", _employee(company.id, dni="12345678-z"))


def test_duplicate_pin_lookup_in_same_company_fails(db_session: Session) -> None:
    company = make_company(db_session)
    lookup = random_digest()
    make_employee(db_session, company, pin_lookup=lookup)

    assert_violates(
        db_session, "uq_employees_company_id_pin_lookup", _employee(company.id, pin_lookup=lookup)
    )


def test_same_pin_lookup_in_another_company_is_allowed(db_session: Session) -> None:
    # En la práctica el HMAC incluye company_id y los valores serán distintos;
    # aun así, la unicidad es por empresa, no global.
    lookup = random_digest()
    make_employee(db_session, make_company(db_session), pin_lookup=lookup)
    make_employee(db_session, make_company(db_session), pin_lookup=lookup)


def test_pin_lookup_must_be_32_bytes(db_session: Session) -> None:
    company = make_company(db_session)

    assert_violates(
        db_session, "ck_employees_pin_lookup_length", _employee(company.id, pin_lookup=b"corto")
    )


def test_pin_can_be_replaced(db_session: Session) -> None:
    """El modelo permite regenerar el PIN: se sustituyen lookup, versión y fecha."""
    employee = make_employee(db_session, make_company(db_session), pin_key_version=1)
    new_lookup = random_digest()
    regenerated_at = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)

    employee.pin_lookup = new_lookup
    employee.pin_key_version = 2
    employee.pin_generated_at = regenerated_at
    db_session.flush()
    db_session.refresh(employee)

    assert employee.pin_lookup == new_lookup
    assert employee.pin_key_version == 2
    assert employee.pin_generated_at == regenerated_at
    assert employee.active is True


def test_company_id_is_immutable(db_session: Session) -> None:
    employee = make_employee(db_session, make_company(db_session))
    employee.company_id = make_company(db_session).id

    with pytest.raises(ImmutableDataError):
        db_session.flush()
