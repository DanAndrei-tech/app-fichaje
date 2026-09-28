"""Modelos de fichaje: jornadas, pausas y eventos originales.

- ClockEvent: lo que ocurrió en el terminal. Inmutable.
- WorkSession / WorkBreak: la interpretación de esos eventos (jornadas y
  pausas). Es lo que se corrige desde administración, con auditoría.

Multiempresa: cada tabla lleva company_id y las FK hacia empleados,
terminales y jornadas son compuestas (company_id, x_id), de modo que
PostgreSQL rechaza cualquier mezcla de empresas.
"""

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.immutability import immutable_columns, immutable_model
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import str_enum
from app.modules.employees.models import Employee
from app.modules.terminals.models import Terminal


def _company_fk() -> ForeignKey:
    return ForeignKey("companies.id", ondelete="RESTRICT", onupdate="RESTRICT")


def _tenant_fk(column: str, target_table: str) -> ForeignKeyConstraint:
    """FK compuesta (company_id, column) -> target_table(company_id, id)."""
    return ForeignKeyConstraint(
        ["company_id", column],
        [f"{target_table}.company_id", f"{target_table}.id"],
        ondelete="RESTRICT",
        onupdate="RESTRICT",
    )


class WorkSessionStatus(StrEnum):
    OPEN = "OPEN"  # en curso; como máximo una por empleado
    CLOSED = "CLOSED"  # terminada y válida
    NEEDS_REVIEW = "NEEDS_REVIEW"  # anómala; la corrige un ADMIN/MANAGER
    VOIDED = "VOIDED"  # anulada (sustituye al borrado)


class ClockEventType(StrEnum):
    CLOCK_IN = "CLOCK_IN"
    BREAK_START = "BREAK_START"
    BREAK_END = "BREAK_END"
    CLOCK_OUT = "CLOCK_OUT"


@immutable_columns("company_id", "employee_id")
class WorkSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Jornada de un empleado.

    work_date es el día laboral: la fecha local (zona horaria de la empresa)
    del CLOCK_IN. Un turno 22:00-06:00 pertenece al día de entrada. Lo
    calculará el servicio de fichaje; aquí solo se almacena.
    """

    __tablename__ = "work_sessions"
    __table_args__ = (
        _tenant_fk("employee_id", "employees"),
        # Destino de las FK compuestas (company_id, work_session_id).
        UniqueConstraint("company_id", "id"),
        # Destino de la FK de clock_events (company_id, employee_id,
        # work_session_id): el evento y su jornada son del mismo empleado.
        UniqueConstraint("company_id", "employee_id", "id"),
        CheckConstraint("ended_at IS NULL OR ended_at > started_at", name="ended_after_started"),
        CheckConstraint("status <> 'OPEN' OR ended_at IS NULL", name="open_has_no_end"),
        CheckConstraint("status <> 'CLOSED' OR ended_at IS NOT NULL", name="closed_has_end"),
        # Como máximo una jornada OPEN por empleado (y consulta del estado actual).
        Index(
            "uq_work_sessions_employee_id_open",
            "employee_id",
            unique=True,
            postgresql_where=text("status = 'OPEN'"),
        ),
        # Horas e historial de un empleado.
        Index("ix_work_sessions_company_id_employee_id_work_date", "company_id", "employee_id", "work_date"),
        # Informes diarios/semanales de toda la empresa.
        Index("ix_work_sessions_company_id_work_date", "company_id", "work_date"),
        # Bandeja de revisión (por empresa y, opcionalmente, por empleado).
        Index(
            "ix_work_sessions_company_id_employee_id_needs_review",
            "company_id",
            "employee_id",
            postgresql_where=text("status = 'NEEDS_REVIEW'"),
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(_company_fk())
    employee_id: Mapped[uuid.UUID]
    work_date: Mapped[date]
    started_at: Mapped[datetime]
    ended_at: Mapped[datetime | None]
    status: Mapped[WorkSessionStatus] = mapped_column(
        str_enum(WorkSessionStatus, name="status"),
        server_default=WorkSessionStatus.OPEN.value,
    )

    employee: Mapped[Employee] = relationship(back_populates="work_sessions")
    breaks: Mapped[list["WorkBreak"]] = relationship(
        back_populates="work_session",
        passive_deletes="all",
        order_by="WorkBreak.started_at",
    )

    def __repr__(self) -> str:
        return f"<WorkSession {self.work_date} {self.status}>"


@immutable_columns("company_id", "work_session_id")
class WorkBreak(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Pausa dentro de una jornada.

    Que la pausa quede dentro de la jornada y que no se solape con otras lo
    validará el servicio de fichaje (no cabe en un CHECK).
    """

    __tablename__ = "work_breaks"
    __table_args__ = (
        _tenant_fk("work_session_id", "work_sessions"),
        CheckConstraint("ended_at IS NULL OR ended_at > started_at", name="ended_after_started"),
        # Como máximo una pausa abierta por jornada.
        Index(
            "uq_work_breaks_work_session_id_open",
            "work_session_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
        # Pausas de una jornada, ordenadas.
        Index("ix_work_breaks_work_session_id_started_at", "work_session_id", "started_at"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(_company_fk())
    work_session_id: Mapped[uuid.UUID]
    started_at: Mapped[datetime]
    ended_at: Mapped[datetime | None]

    work_session: Mapped[WorkSession] = relationship(back_populates="breaks")

    def __repr__(self) -> str:
        return f"<WorkBreak {self.started_at}-{self.ended_at}>"


@immutable_model
class ClockEvent(UUIDPrimaryKeyMixin, Base):
    """Evento original de fichaje, tal como llegó del terminal. Inmutable.

    occurred_at es la hora oficial: la del servidor al recibir el fichaje.
    client_reported_at es la hora que dice el dispositivo (solo informativa).
    No tiene created_at: coincidiría con occurred_at (no hay fichaje offline).
    """

    __tablename__ = "clock_events"
    __table_args__ = (
        _tenant_fk("employee_id", "employees"),
        _tenant_fk("terminal_id", "terminals"),
        # La jornada del evento es de la misma empresa Y del mismo empleado.
        # Nombre explícito: el de la convención superaría los 63 caracteres
        # que admite PostgreSQL.
        ForeignKeyConstraint(
            ["company_id", "employee_id", "work_session_id"],
            ["work_sessions.company_id", "work_sessions.employee_id", "work_sessions.id"],
            name="fk_clock_events_company_id_employee_id_work_session_id",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        # Idempotencia: un reintento de la misma petición no duplica eventos.
        # event_type forma parte de la clave porque "finalizar pausa y salir"
        # genera BREAK_END + CLOCK_OUT con una sola petición.
        UniqueConstraint("terminal_id", "idempotency_key", "event_type"),
        # Historial de eventos de un empleado.
        Index("ix_clock_events_company_id_employee_id_occurred_at", "company_id", "employee_id", "occurred_at"),
        # Actividad de un terminal.
        Index("ix_clock_events_company_id_terminal_id_occurred_at", "company_id", "terminal_id", "occurred_at"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(_company_fk())
    employee_id: Mapped[uuid.UUID]
    terminal_id: Mapped[uuid.UUID]
    work_session_id: Mapped[uuid.UUID]
    event_type: Mapped[ClockEventType] = mapped_column(str_enum(ClockEventType, name="event_type"))
    occurred_at: Mapped[datetime] = mapped_column(server_default=func.now())
    client_reported_at: Mapped[datetime | None]
    idempotency_key: Mapped[uuid.UUID]

    # Solo lectura: los eventos se crean asignando los ids explícitamente.
    employee: Mapped[Employee] = relationship(viewonly=True)
    terminal: Mapped[Terminal] = relationship(viewonly=True)
    work_session: Mapped[WorkSession] = relationship(viewonly=True)

    def __repr__(self) -> str:
        return f"<ClockEvent {self.event_type} {self.occurred_at}>"
