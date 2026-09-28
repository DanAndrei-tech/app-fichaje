"""Columnas comunes a varios modelos.

- UUIDPrimaryKeyMixin: clave primaria UUIDv4 generada en la aplicación al
  insertar (así el id existe antes de llegar a PostgreSQL).
- TimestampMixin: created_at y updated_at como TIMESTAMPTZ. Los pone
  PostgreSQL (now(), en UTC); updated_at se renueva en cada UPDATE del ORM.

sort_order coloca id como primera columna y los timestamps al final.
"""

import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, sort_order=-1)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), sort_order=1)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), sort_order=1
    )
