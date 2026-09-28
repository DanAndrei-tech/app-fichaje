"""Modelo de auditoría: quién cambió qué, cuándo y por qué. Inmutable.

old_value / new_value (JSONB) contienen SOLO campos permitidos de la
entidad. Nunca: PIN, pin_lookup, contraseñas ni su hash, tokens de terminal
ni su hash, JWT ni refresh tokens. Acciones como PIN_REGENERATED se
registran sin valores.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.immutability import immutable_model
from app.db.mixins import UUIDPrimaryKeyMixin
from app.db.types import str_enum


class AuditActorType(StrEnum):
    USER = "USER"  # un usuario de administración (actor_user_id obligatorio)
    SYSTEM = "SYSTEM"  # un proceso automático (sin actor_user_id)


class AuditAction(StrEnum):
    """Acciones previstas. La columna no las restringe con un CHECK para
    poder añadir acciones nuevas sin migración."""

    EMPLOYEE_CREATED = "EMPLOYEE_CREATED"
    EMPLOYEE_UPDATED = "EMPLOYEE_UPDATED"
    EMPLOYEE_DEACTIVATED = "EMPLOYEE_DEACTIVATED"
    EMPLOYEE_REACTIVATED = "EMPLOYEE_REACTIVATED"
    PIN_REGENERATED = "PIN_REGENERATED"
    TERMINAL_CREATED = "TERMINAL_CREATED"
    TERMINAL_REVOKED = "TERMINAL_REVOKED"
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    SESSION_CORRECTED = "SESSION_CORRECTED"
    SESSION_VOIDED = "SESSION_VOIDED"


@immutable_model
class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint("(actor_type = 'USER') = (actor_user_id IS NOT NULL)", name="actor_user_matches_type"),
        CheckConstraint("entity_type ~ '^[a-z][a-z_]*$'", name="entity_type_format"),
        CheckConstraint("action ~ '^[A-Z][A-Z_]*$'", name="action_format"),
        # Listado de auditoría de una empresa.
        Index("ix_audit_logs_company_id_created_at", "company_id", "created_at"),
        # Historial de una entidad concreta.
        Index("ix_audit_logs_entity_type_entity_id_created_at", "entity_type", "entity_id", "created_at"),
    )

    # NULL solo para acciones de plataforma (sin empresa).
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    actor_type: Mapped[AuditActorType] = mapped_column(str_enum(AuditActorType, name="actor_type"))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    entity_type: Mapped[str] = mapped_column(String(50))  # p. ej. "work_session", "employee"
    entity_id: Mapped[uuid.UUID]  # sin FK: apunta a tablas distintas según entity_type
    action: Mapped[str] = mapped_column(String(50))  # ver AuditAction
    old_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    new_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[uuid.UUID | None]  # agrupa las filas de una misma operación
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} {self.entity_type}:{self.entity_id}>"
