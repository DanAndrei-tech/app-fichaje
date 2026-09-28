"""Modelo de terminal de fichaje (móvil, tablet, PC o pantalla táctil)."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, LargeBinary, String, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.immutability import immutable_columns
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.companies.models import Company


@immutable_columns("company_id")
class Terminal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Dispositivo autorizado para fichar en una empresa.

    El token del terminal NUNCA se guarda: solo su SHA-256 (token_hash, 32
    bytes). Estados: activo; desactivado (active=false, reversible);
    revocado (revoked_at con valor, definitivo, implica active=false).
    """

    __tablename__ = "terminals"
    __table_args__ = (
        # Destino de las FK compuestas (company_id, terminal_id).
        UniqueConstraint("company_id", "id"),
        UniqueConstraint("company_id", "name"),
        CheckConstraint("btrim(name) <> ''", name="name_not_blank"),
        CheckConstraint("octet_length(token_hash) = 32", name="token_hash_length"),
        CheckConstraint("revoked_at IS NULL OR NOT active", name="revoked_is_inactive"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    name: Mapped[str] = mapped_column(String(100))
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    active: Mapped[bool] = mapped_column(server_default=true())
    revoked_at: Mapped[datetime | None]
    last_used_at: Mapped[datetime | None]

    company: Mapped[Company] = relationship()

    def __repr__(self) -> str:
        return f"<Terminal {self.name}>"
