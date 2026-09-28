import uuid

import pytest
from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from app.db.immutability import ImmutableDataError
from app.modules.audit.models import AuditAction, AuditActorType, AuditLog

from .factories import assert_sql_violates, assert_violates, make_company, make_user


def _audit(**values: object) -> AuditLog:
    defaults: dict[str, object] = {
        "entity_type": "work_session",
        "entity_id": uuid.uuid4(),
        "action": AuditAction.SESSION_CORRECTED,
    }
    return AuditLog(**(defaults | values))


def test_system_action_without_actor_user(db_session: Session) -> None:
    company = make_company(db_session)
    log = _audit(company_id=company.id, actor_type=AuditActorType.SYSTEM, actor_user_id=None)
    db_session.add(log)
    db_session.flush()

    assert log.actor_user_id is None
    assert log.created_at is not None


def test_user_action_with_values_and_reason(db_session: Session) -> None:
    company = make_company(db_session)
    user = make_user(db_session, company)
    log = _audit(
        company_id=company.id,
        actor_type=AuditActorType.USER,
        actor_user_id=user.id,
        old_value={"ended_at": None, "status": "NEEDS_REVIEW"},
        new_value={"ended_at": "2026-09-29T04:00:00Z", "status": "CLOSED"},
        reason="El empleado olvidó fichar la salida",
        request_id=uuid.uuid4(),
    )
    db_session.add(log)
    db_session.flush()
    db_session.expire(log)

    assert log.new_value == {"ended_at": "2026-09-29T04:00:00Z", "status": "CLOSED"}
    assert log.old_value == {"ended_at": None, "status": "NEEDS_REVIEW"}


def test_platform_action_without_company(db_session: Session) -> None:
    db_session.add(_audit(company_id=None, actor_type=AuditActorType.SYSTEM, entity_type="company"))
    db_session.flush()


def test_pin_regenerated_is_recorded_without_values(db_session: Session) -> None:
    company = make_company(db_session)
    user = make_user(db_session, company)
    log = _audit(
        company_id=company.id,
        actor_type=AuditActorType.USER,
        actor_user_id=user.id,
        entity_type="employee",
        action=AuditAction.PIN_REGENERATED,
    )
    db_session.add(log)
    db_session.flush()

    assert log.old_value is None
    assert log.new_value is None


@pytest.mark.parametrize("actor_type", [AuditActorType.USER, AuditActorType.SYSTEM])
def test_actor_user_must_match_actor_type(db_session: Session, actor_type: AuditActorType) -> None:
    company = make_company(db_session)
    # USER sin usuario, o SYSTEM con usuario: ambos inválidos.
    actor_user_id = None if actor_type is AuditActorType.USER else make_user(db_session, company).id

    assert_violates(
        db_session,
        "ck_audit_logs_actor_user_matches_type",
        _audit(company_id=company.id, actor_type=actor_type, actor_user_id=actor_user_id),
    )


def test_invalid_actor_type_is_rejected_by_database(db_session: Session) -> None:
    log = _audit(actor_type=AuditActorType.SYSTEM)
    db_session.add(log)
    db_session.flush()

    assert_sql_violates(
        db_session,
        "ck_audit_logs_actor_type",
        text("UPDATE audit_logs SET actor_type = 'ROBOT' WHERE id = :id"),
        {"id": log.id},
    )


def test_audit_log_cannot_be_modified_or_deleted(db_session: Session) -> None:
    log = _audit(actor_type=AuditActorType.SYSTEM)
    db_session.add(log)
    db_session.flush()

    with pytest.raises(ImmutableDataError), db_session.begin_nested():
        log.reason = "otro motivo"
        db_session.flush()

    with pytest.raises(ImmutableDataError), db_session.begin_nested():
        db_session.delete(log)
        db_session.flush()

    with pytest.raises(ImmutableDataError):
        db_session.execute(delete(AuditLog))

    assert db_session.get(AuditLog, log.id) is log
    assert log.reason is None
