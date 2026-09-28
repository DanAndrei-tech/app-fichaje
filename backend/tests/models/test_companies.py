import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.immutability import ImmutableDataError
from app.modules.companies.models import Company

from .factories import assert_violates, make_company, make_employee


def test_create_company_with_defaults(db_session: Session) -> None:
    company = make_company(db_session, name="De Tapas", slug="detapas")

    assert company.id is not None
    assert company.timezone == "Europe/Madrid"
    assert company.max_shift_hours == 16
    assert company.active is True
    assert company.created_at.tzinfo is not None


def test_duplicate_slug_fails(db_session: Session) -> None:
    make_company(db_session, slug="detapas")

    assert_violates(db_session, "uq_companies_slug", Company(name="Otra", slug="detapas"))


@pytest.mark.parametrize(
    ("slug", "constraint"),
    [
        ("DeTapas", "ck_companies_slug_format"),
        ("de tapas", "ck_companies_slug_format"),
        ("de_tapas", "ck_companies_slug_format"),
        ("-detapas", "ck_companies_slug_format"),
        ("detapas-", "ck_companies_slug_format"),
        ("de--tapas", "ck_companies_slug_format"),
        ("ab", "ck_companies_slug_length"),
    ],
)
def test_invalid_slug_fails(db_session: Session, slug: str, constraint: str) -> None:
    assert_violates(db_session, constraint, Company(name="Empresa", slug=slug))


def test_max_shift_hours_out_of_range_fails(db_session: Session) -> None:
    assert_violates(
        db_session,
        "ck_companies_max_shift_hours_range",
        Company(name="Empresa", slug="empresa-x", max_shift_hours=25),
    )


def test_slug_is_immutable(db_session: Session) -> None:
    company = make_company(db_session, slug="detapas")
    company.slug = "otro-slug"

    with pytest.raises(ImmutableDataError):
        db_session.flush()


def test_company_with_dependent_data_cannot_be_deleted(db_session: Session) -> None:
    company = make_company(db_session)
    make_employee(db_session, company)

    with pytest.raises(IntegrityError) as exc_info:
        with db_session.begin_nested():
            db_session.delete(company)
            db_session.flush()

    assert exc_info.value.orig.diag.constraint_name == "fk_employees_company_id_companies"  # type: ignore[union-attr]
