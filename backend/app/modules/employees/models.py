"""Modelo de empleado (persona que ficha con PIN)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    LargeBinary,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.immutability import immutable_columns
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.companies.models import Company

if TYPE_CHECKING:
    from app.modules.clock.models import WorkSession


@immutable_columns("company_id")
class Employee(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Empleado.

    PIN: nunca se guarda en claro. pin_lookup = HMAC-SHA256(clave de la
    versión pin_key_version, f"{company_id}:{pin}") — 32 bytes. Sirve para
    buscar al empleado por PIN y para garantizar que el PIN es único dentro
    de la empresa. Regenerar el PIN = sustituir pin_lookup, pin_key_version
    y pin_generated_at (el PIN anterior deja de funcionar).
    """

    __tablename__ = "employees"
    __table_args__ = (
        # Destino de las FK compuestas (company_id, employee_id) de otras tablas.
        UniqueConstraint("company_id", "id"),
        # Un PIN no puede repetirse dentro de la empresa (sí entre empresas).
        UniqueConstraint("company_id", "pin_lookup"),
        # DNI opcional, único dentro de la empresa cuando existe.
        Index(
            "uq_employees_company_id_dni",
            "company_id",
            "dni",
            unique=True,
            postgresql_where=text("dni IS NOT NULL"),
        ),
        CheckConstraint("btrim(first_name) <> ''", name="first_name_not_blank"),
        CheckConstraint("btrim(last_name) <> ''", name="last_name_not_blank"),
        # Normalizado: mayúsculas y dígitos, sin espacios ni guiones.
        CheckConstraint("dni ~ '^[A-Z0-9]+$'", name="dni_format"),
        CheckConstraint("octet_length(pin_lookup) = 32", name="pin_lookup_length"),
        CheckConstraint("pin_key_version >= 1", name="pin_key_version_positive"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(150))
    dni: Mapped[str | None] = mapped_column(String(20))
    pin_lookup: Mapped[bytes] = mapped_column(LargeBinary)
    pin_key_version: Mapped[int] = mapped_column(SmallInteger)
    pin_generated_at: Mapped[datetime] = mapped_column(server_default=func.now())
    active: Mapped[bool] = mapped_column(server_default=true())

    company: Mapped[Company] = relationship()
    # passive_deletes="all": el ORM no toca las sesiones al borrar un
    # empleado; es PostgreSQL (ON DELETE RESTRICT) quien lo impide.
    work_sessions: Mapped[list["WorkSession"]] = relationship(
        back_populates="employee", passive_deletes="all"
    )

    def __repr__(self) -> str:
        return f"<Employee {self.first_name} {self.last_name}>"
