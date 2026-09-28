import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.users.models import User, UserRole

from .factories import assert_sql_violates, assert_violates, make_company, make_user


def _user(**values: object) -> User:
    defaults: dict[str, object] = {
        "email": "otro@example.com",
        "full_name": "Otro",
        "password_hash": "$argon2id$fake",
        "role": UserRole.ADMIN,
    }
    return User(**(defaults | values))


def test_create_user(db_session: Session) -> None:
    company = make_company(db_session)
    user = make_user(db_session, company, role=UserRole.MANAGER)

    assert user.company is company
    assert user.active is True
    assert user.last_login_at is None


def test_duplicate_email_fails_even_across_companies(db_session: Session) -> None:
    make_user(db_session, make_company(db_session), email="ana@example.com")

    assert_violates(
        db_session,
        "uq_users_email",
        _user(company_id=make_company(db_session).id, email="ana@example.com"),
    )


def test_email_must_be_lowercase(db_session: Session) -> None:
    assert_violates(
        db_session,
        "ck_users_email_lowercase",
        _user(company_id=make_company(db_session).id, email="Ana@Example.com"),
    )


def test_platform_admin_without_company_is_valid(db_session: Session) -> None:
    user = make_user(db_session, None, role=UserRole.PLATFORM_ADMIN)

    assert user.company_id is None


@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.MANAGER])
def test_company_role_without_company_fails(db_session: Session, role: UserRole) -> None:
    assert_violates(db_session, "ck_users_company_matches_role", _user(company_id=None, role=role))


def test_platform_admin_with_company_fails(db_session: Session) -> None:
    assert_violates(
        db_session,
        "ck_users_company_matches_role",
        _user(company_id=make_company(db_session).id, role=UserRole.PLATFORM_ADMIN),
    )


def test_invalid_role_is_rejected_by_database(db_session: Session) -> None:
    user = make_user(db_session, make_company(db_session))

    assert_sql_violates(
        db_session,
        "ck_users_role",
        text("UPDATE users SET role = 'SUPERUSER' WHERE id = :id"),
        {"id": user.id},
    )
