"""Modelo de empresa (tenant)."""

from sqlalchemy import CheckConstraint, SmallInteger, String, text, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.immutability import immutable_columns
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


@immutable_columns("slug")
class Company(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Empresa. Su slug identifica el terminal: /clock/{slug}. Inmutable en el MVP."""

    __tablename__ = "companies"
    __table_args__ = (
        CheckConstraint("btrim(name) <> ''", name="name_not_blank"),
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="slug_format"),
        CheckConstraint("char_length(slug) BETWEEN 3 AND 50", name="slug_length"),
        CheckConstraint("btrim(timezone) <> ''", name="timezone_not_blank"),
        CheckConstraint("max_shift_hours BETWEEN 1 AND 24", name="max_shift_hours_range"),
    )

    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(50), unique=True)
    # Nombre IANA (p. ej. "Europe/Madrid"). Se valida con zoneinfo en la
    # aplicación: PostgreSQL no puede comprobarlo en un CHECK.
    timezone: Mapped[str] = mapped_column(String(64), server_default="Europe/Madrid")
    # Horas a partir de las cuales una jornada pasa a NEEDS_REVIEW
    # (la lógica que lo aplica llegará con el servicio de fichaje).
    max_shift_hours: Mapped[int] = mapped_column(SmallInteger, server_default=text("16"))
    active: Mapped[bool] = mapped_column(server_default=true())

    def __repr__(self) -> str:
        return f"<Company {self.slug}>"
