"""Base declarativa de la que heredarán todos los modelos SQLAlchemy.

Decisiones que aplican a todos los modelos:

- Convención de nombres: constraints e índices reciben nombres deterministas
  (p. ej. "uq_employees_company_id_pin_lookup"). Así Alembic puede crearlos,
  compararlos y borrarlos por nombre en las migraciones, en vez de depender
  de nombres generados por PostgreSQL.

- UUID: un atributo anotado como Mapped[uuid.UUID] se guarda como el tipo
  nativo UUID de PostgreSQL y se lee como uuid.UUID de Python.

- Fechas y horas: un atributo anotado como Mapped[datetime] se guarda como
  TIMESTAMP WITH TIME ZONE (timestamptz). La aplicación trabaja siempre con
  instantes en UTC (datetime con tzinfo=UTC); nunca con fechas "naive".
  La zona horaria de cada empresa se guardará como nombre IANA
  (p. ej. "Europe/Madrid") y solo se usará para mostrar y agrupar
  (día, semana), no para almacenar instantes.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, MetaData, Uuid
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    type_annotation_map = {
        uuid.UUID: Uuid(as_uuid=True),
        datetime: DateTime(timezone=True),
    }
