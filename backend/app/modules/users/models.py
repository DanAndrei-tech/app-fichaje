"""Modelo de usuario de administración."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, String, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.immutability import immutable_columns
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import str_enum
from app.modules.companies.models import Company


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    # Administrador de la plataforma, sin empresa. Aún sin uso funcional.
    PLATFORM_ADMIN = "PLATFORM_ADMIN"


@immutable_columns("company_id")
class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Cuenta de administración (email + contraseña). Los empleados NO usan esta tabla."""

    __tablename__ = "users"
    __table_args__ = (
        # El email se guarda normalizado: la aplicación lo pasa a minúsculas.
        CheckConstraint("email = lower(email)", name="email_lowercase"),
        CheckConstraint("btrim(email) <> ''", name="email_not_blank"),
        CheckConstraint("btrim(full_name) <> ''", name="full_name_not_blank"),
        # PLATFORM_ADMIN <=> sin empresa; ADMIN y MANAGER <=> con empresa.
        CheckConstraint("(role = 'PLATFORM_ADMIN') = (company_id IS NULL)", name="company_matches_role"),
    )

    company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    # Único en toda la plataforma: el login no pide empresa.
    email: Mapped[str] = mapped_column(String(254), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    # Hash Argon2id en formato PHC. Nunca la contraseña.
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(str_enum(UserRole, name="role"))
    active: Mapped[bool] = mapped_column(server_default=true())
    last_login_at: Mapped[datetime | None]

    company: Mapped[Company | None] = relationship()

    def __repr__(self) -> str:
        return f"<User {self.email} {self.role}>"
