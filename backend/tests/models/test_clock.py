import uuid
from datetime import timedelta

import pytest
from sqlalchemy import text, update
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from app.db.immutability import ImmutableDataError
from app.modules.clock.models import (
    ClockEvent,
    ClockEventType,
    WorkBreak,
    WorkSession,
    WorkSessionStatus,
)

from .factories import (
    T0,
    WORK_DATE,
    assert_sql_violates,
    assert_violates,
    make_clock_event,
    make_company,
    make_employee,
    make_terminal,
    make_work_session,
)

# ---------------------------------------------------------------- jornadas


def test_work_session_belongs_to_employee_of_same_company(db_session: Session) -> None:
    employee = make_employee(db_session, make_company(db_session))
    work_session = make_work_session(db_session, employee)

    assert work_session.employee is employee
    assert employee.work_sessions == [work_session]
    assert work_session.company_id == employee.company_id


def test_work_session_with_employee_of_another_company_fails(db_session: Session) -> None:
    employee = make_employee(db_session, make_company(db_session))
    other_company = make_company(db_session)

    assert_violates(
        db_session,
        "fk_work_sessions_company_id_employee_id_employees",
        WorkSession(
            company_id=other_company.id,
            employee_id=employee.id,
            work_date=WORK_DATE,
            started_at=T0,
        ),
    )


def test_only_one_open_session_per_employee(db_session: Session) -> None:
    employee = make_employee(db_session, make_company(db_session))
    make_work_session(db_session, employee)

    assert_violates(
        db_session,
        "uq_work_sessions_employee_id_open",
        WorkSession(
            company_id=employee.company_id,
            employee_id=employee.id,
            work_date=WORK_DATE,
            started_at=T0 + timedelta(hours=1),
        ),
    )


def test_open_session_allowed_alongside_closed_and_needs_review(db_session: Session) -> None:
    employee = make_employee(db_session, make_company(db_session))
    make_work_session(
        db_session,
        employee,
        status=WorkSessionStatus.CLOSED,
        started_at=T0 - timedelta(days=2),
        ended_at=T0 - timedelta(days=2) + timedelta(hours=8),
    )
    # Salida olvidada: NEEDS_REVIEW sin ended_at no bloquea una nueva entrada.
    make_work_session(
        db_session, employee, status=WorkSessionStatus.NEEDS_REVIEW, started_at=T0 - timedelta(days=1)
    )
    make_work_session(db_session, employee, status=WorkSessionStatus.OPEN)


def test_session_crossing_midnight_is_a_single_session(db_session: Session) -> None:
    employee = make_employee(db_session, make_company(db_session))
    work_session = make_work_session(
        db_session,
        employee,
        status=WorkSessionStatus.CLOSED,
        started_at=T0,  # 28/09 20:00 UTC (22:00 en Madrid)
        ended_at=T0 + timedelta(hours=8),  # 29/09
    )

    assert work_session.work_date == WORK_DATE


@pytest.mark.parametrize(
    ("status", "ended_offset", "constraint"),
    [
        (WorkSessionStatus.CLOSED, None, "ck_work_sessions_closed_has_end"),
        (WorkSessionStatus.OPEN, timedelta(hours=8), "ck_work_sessions_open_has_no_end"),
        (WorkSessionStatus.CLOSED, timedelta(hours=-1), "ck_work_sessions_ended_after_started"),
        (WorkSessionStatus.CLOSED, timedelta(0), "ck_work_sessions_ended_after_started"),
    ],
)
def test_session_status_and_end_must_be_consistent(
    db_session: Session,
    status: WorkSessionStatus,
    ended_offset: timedelta | None,
    constraint: str,
) -> None:
    employee = make_employee(db_session, make_company(db_session))

    assert_violates(
        db_session,
        constraint,
        WorkSession(
            company_id=employee.company_id,
            employee_id=employee.id,
            work_date=WORK_DATE,
            started_at=T0,
            ended_at=None if ended_offset is None else T0 + ended_offset,
            status=status,
        ),
    )


def test_invalid_status_is_rejected(db_session: Session) -> None:
    employee = make_employee(db_session, make_company(db_session))
    work_session = make_work_session(db_session, employee)

    # En el ORM, antes de llegar a la base de datos.
    with pytest.raises(StatementError):
        with db_session.begin_nested():
            work_session.status = "PAUSED"  # type: ignore[assignment]
            db_session.flush()
    db_session.expire(work_session)

    # En PostgreSQL, aunque se salte el ORM.
    assert_sql_violates(
        db_session,
        "ck_work_sessions_status",
        text("UPDATE work_sessions SET status = 'PAUSED' WHERE id = :id"),
        {"id": work_session.id},
    )


def test_session_with_clock_events_cannot_be_deleted(db_session: Session) -> None:
    company = make_company(db_session)
    work_session = make_work_session(db_session, make_employee(db_session, company))
    make_clock_event(db_session, work_session, make_terminal(db_session, company))

    with pytest.raises(IntegrityError) as exc_info:
        with db_session.begin_nested():
            db_session.delete(work_session)
            db_session.flush()

    assert (
        exc_info.value.orig.diag.constraint_name  # type: ignore[union-attr]
        == "fk_clock_events_company_id_employee_id_work_session_id"
    )


# ------------------------------------------------------------------ pausas


def test_break_belongs_to_its_session(db_session: Session) -> None:
    work_session = make_work_session(db_session, make_employee(db_session, make_company(db_session)))
    work_break = WorkBreak(
        company_id=work_session.company_id,
        work_session_id=work_session.id,
        started_at=T0 + timedelta(hours=2),
        ended_at=T0 + timedelta(hours=2, minutes=15),
    )
    db_session.add(work_break)
    db_session.flush()
    db_session.expire(work_session, ["breaks"])

    assert work_break.work_session is work_session
    assert work_session.breaks == [work_break]


def test_break_with_session_of_another_company_fails(db_session: Session) -> None:
    work_session = make_work_session(db_session, make_employee(db_session, make_company(db_session)))

    assert_violates(
        db_session,
        "fk_work_breaks_company_id_work_session_id_work_sessions",
        WorkBreak(
            company_id=make_company(db_session).id,
            work_session_id=work_session.id,
            started_at=T0 + timedelta(hours=1),
        ),
    )


def test_only_one_open_break_per_session(db_session: Session) -> None:
    work_session = make_work_session(db_session, make_employee(db_session, make_company(db_session)))
    db_session.add(
        WorkBreak(
            company_id=work_session.company_id,
            work_session_id=work_session.id,
            started_at=T0 + timedelta(hours=1),
        )
    )
    db_session.flush()

    assert_violates(
        db_session,
        "uq_work_breaks_work_session_id_open",
        WorkBreak(
            company_id=work_session.company_id,
            work_session_id=work_session.id,
            started_at=T0 + timedelta(hours=2),
        ),
    )


def test_break_must_end_after_it_starts(db_session: Session) -> None:
    work_session = make_work_session(db_session, make_employee(db_session, make_company(db_session)))

    assert_violates(
        db_session,
        "ck_work_breaks_ended_after_started",
        WorkBreak(
            company_id=work_session.company_id,
            work_session_id=work_session.id,
            started_at=T0 + timedelta(hours=2),
            ended_at=T0 + timedelta(hours=1),
        ),
    )


# ----------------------------------------------------------------- eventos


def test_clock_event_with_terminal_of_another_company_fails(db_session: Session) -> None:
    work_session = make_work_session(db_session, make_employee(db_session, make_company(db_session)))
    foreign_terminal = make_terminal(db_session, make_company(db_session))

    assert_violates(
        db_session,
        "fk_clock_events_company_id_terminal_id_terminals",
        ClockEvent(
            company_id=work_session.company_id,
            employee_id=work_session.employee_id,
            terminal_id=foreign_terminal.id,
            work_session_id=work_session.id,
            event_type=ClockEventType.CLOCK_IN,
            idempotency_key=uuid.uuid4(),
        ),
    )


def test_clock_event_occurred_at_is_set_by_database(db_session: Session) -> None:
    company = make_company(db_session)
    work_session = make_work_session(db_session, make_employee(db_session, company))
    event = make_clock_event(db_session, work_session, make_terminal(db_session, company))

    assert event.occurred_at is not None
    assert event.occurred_at.tzinfo is not None
    assert event.client_reported_at is None


def test_idempotency_key_prevents_duplicate_events(db_session: Session) -> None:
    company = make_company(db_session)
    work_session = make_work_session(db_session, make_employee(db_session, company))
    terminal = make_terminal(db_session, company)
    key = uuid.uuid4()
    make_clock_event(db_session, work_session, terminal, idempotency_key=key)

    assert_violates(
        db_session,
        "uq_clock_events_terminal_id_idempotency_key_event_type",
        ClockEvent(
            company_id=company.id,
            employee_id=work_session.employee_id,
            terminal_id=terminal.id,
            work_session_id=work_session.id,
            event_type=ClockEventType.CLOCK_IN,
            idempotency_key=key,
        ),
    )


def test_same_idempotency_key_allows_break_end_and_clock_out(db_session: Session) -> None:
    """"Finalizar pausa y salir": dos eventos con la misma clave de petición."""
    company = make_company(db_session)
    work_session = make_work_session(db_session, make_employee(db_session, company))
    terminal = make_terminal(db_session, company)
    key = uuid.uuid4()

    make_clock_event(db_session, work_session, terminal, event_type=ClockEventType.BREAK_END, idempotency_key=key)
    make_clock_event(db_session, work_session, terminal, event_type=ClockEventType.CLOCK_OUT, idempotency_key=key)


def test_invalid_event_type_is_rejected_by_database(db_session: Session) -> None:
    company = make_company(db_session)
    work_session = make_work_session(db_session, make_employee(db_session, company))
    event = make_clock_event(db_session, work_session, make_terminal(db_session, company))

    assert_sql_violates(
        db_session,
        "ck_clock_events_event_type",
        text("UPDATE clock_events SET event_type = 'LUNCH' WHERE id = :id"),
        {"id": event.id},
    )


def test_clock_event_cannot_be_modified_or_deleted(db_session: Session) -> None:
    company = make_company(db_session)
    work_session = make_work_session(db_session, make_employee(db_session, company))
    event = make_clock_event(db_session, work_session, make_terminal(db_session, company))

    with pytest.raises(ImmutableDataError), db_session.begin_nested():
        event.event_type = ClockEventType.CLOCK_OUT
        db_session.flush()

    with pytest.raises(ImmutableDataError), db_session.begin_nested():
        db_session.delete(event)
        db_session.flush()

    with pytest.raises(ImmutableDataError):
        db_session.execute(update(ClockEvent).values(client_reported_at=T0))

    assert db_session.get(ClockEvent, event.id) is event
    assert event.event_type is ClockEventType.CLOCK_IN


# ------------------------------------ evento, empleado y jornada coherentes

EVENT_SESSION_FK = "fk_clock_events_company_id_employee_id_work_session_id"


def _event(company_id: object, employee_id: object, terminal_id: object, work_session_id: object) -> ClockEvent:
    return ClockEvent(
        company_id=company_id,
        employee_id=employee_id,
        terminal_id=terminal_id,
        work_session_id=work_session_id,
        event_type=ClockEventType.CLOCK_IN,
        idempotency_key=uuid.uuid4(),
    )


def test_event_with_own_employee_and_session_is_valid(db_session: Session) -> None:
    company = make_company(db_session)
    employee = make_employee(db_session, company)
    work_session = make_work_session(db_session, employee)
    terminal = make_terminal(db_session, company)

    event = _event(company.id, employee.id, terminal.id, work_session.id)
    db_session.add(event)
    db_session.flush()

    assert event.work_session is work_session
    assert event.employee is employee


def test_event_of_employee_a_with_session_of_employee_b_fails(db_session: Session) -> None:
    company = make_company(db_session)
    employee_a = make_employee(db_session, company)
    employee_b = make_employee(db_session, company)
    session_b = make_work_session(db_session, employee_b)
    terminal = make_terminal(db_session, company)

    assert_violates(db_session, EVENT_SESSION_FK, _event(company.id, employee_a.id, terminal.id, session_b.id))


def test_event_of_employee_b_with_session_of_employee_a_fails(db_session: Session) -> None:
    company = make_company(db_session)
    employee_a = make_employee(db_session, company)
    employee_b = make_employee(db_session, company)
    session_a = make_work_session(db_session, employee_a)
    terminal = make_terminal(db_session, company)

    assert_violates(db_session, EVENT_SESSION_FK, _event(company.id, employee_b.id, terminal.id, session_a.id))


def test_event_of_company_a_with_session_of_company_b_fails(db_session: Session) -> None:
    company_a = make_company(db_session)
    employee_a = make_employee(db_session, company_a)
    terminal_a = make_terminal(db_session, company_a)
    session_b = make_work_session(db_session, make_employee(db_session, make_company(db_session)))

    assert_violates(db_session, EVENT_SESSION_FK, _event(company_a.id, employee_a.id, terminal_a.id, session_b.id))


def test_events_of_several_employees_with_their_own_sessions_are_valid(db_session: Session) -> None:
    company = make_company(db_session)
    terminal = make_terminal(db_session, company)
    for _ in range(3):
        work_session = make_work_session(db_session, make_employee(db_session, company))
        make_clock_event(db_session, work_session, terminal, event_type=ClockEventType.CLOCK_IN)
        make_clock_event(db_session, work_session, terminal, event_type=ClockEventType.BREAK_START)
