"""Tipos de columna reutilizables."""

from enum import StrEnum

from sqlalchemy import Enum


def str_enum[E: StrEnum](enum_class: type[E], name: str) -> Enum:
    """Enumerado guardado como VARCHAR + CHECK (no como ENUM nativo de PostgreSQL).

    Los ENUM nativos son difíciles de migrar (no se pueden quitar valores);
    un CHECK se cambia en una migración normal. `name` da nombre al CHECK:
    ck_<tabla>_<name>.
    """
    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        length=max(len(member.value) for member in enum_class),
    )
