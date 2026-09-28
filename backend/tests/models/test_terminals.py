from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.modules.terminals.models import Terminal

from .factories import assert_violates, make_company, make_terminal, random_digest


def test_create_terminal(db_session: Session) -> None:
    terminal = make_terminal(db_session, make_company(db_session), name="Tablet recepción")

    assert terminal.active is True
    assert terminal.revoked_at is None
    assert terminal.last_used_at is None


def test_duplicate_name_in_same_company_fails(db_session: Session) -> None:
    company = make_company(db_session)
    make_terminal(db_session, company, name="Tablet recepción")

    assert_violates(
        db_session,
        "uq_terminals_company_id_name",
        Terminal(company_id=company.id, name="Tablet recepción", token_hash=random_digest()),
    )


def test_same_name_in_another_company_is_allowed(db_session: Session) -> None:
    make_terminal(db_session, make_company(db_session), name="Tablet recepción")
    make_terminal(db_session, make_company(db_session), name="Tablet recepción")


def test_duplicate_token_hash_fails(db_session: Session) -> None:
    token_hash = random_digest()
    make_terminal(db_session, make_company(db_session), token_hash=token_hash)

    assert_violates(
        db_session,
        "uq_terminals_token_hash",
        Terminal(company_id=make_company(db_session).id, name="Otro", token_hash=token_hash),
    )


def test_revoked_terminal_cannot_be_active(db_session: Session) -> None:
    assert_violates(
        db_session,
        "ck_terminals_revoked_is_inactive",
        Terminal(
            company_id=make_company(db_session).id,
            name="Robada",
            token_hash=random_digest(),
            active=True,
            revoked_at=datetime(2026, 9, 28, tzinfo=UTC),
        ),
    )
