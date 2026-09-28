"""Registro de modelos para Alembic.

Alembic solo ve las tablas de los modelos que se han importado. Cada vez que
un módulo defina modelos nuevos, hay que importarlos aquí.
"""

from app.db.base import Base
from app.modules.audit.models import AuditLog
from app.modules.clock.models import ClockEvent, WorkBreak, WorkSession
from app.modules.companies.models import Company
from app.modules.employees.models import Employee
from app.modules.terminals.models import Terminal
from app.modules.users.models import User

__all__ = [
    "AuditLog",
    "Base",
    "ClockEvent",
    "Company",
    "Employee",
    "Terminal",
    "User",
    "WorkBreak",
    "WorkSession",
]
