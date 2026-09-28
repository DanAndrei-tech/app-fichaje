"""Protección de datos inmutables a nivel de aplicación (ORM).

- immutable_model: filas que nunca se modifican ni se borran
  (clock_events, audit_logs). Rechaza el UPDATE/DELETE de objetos y también
  los `update()`/`delete()` masivos del ORM.
- immutable_columns: columnas que no pueden cambiar una vez creadas
  (p. ej. companies.slug, company_id de cualquier tabla).

Límites conocidos: no protege frente a SQL escrito a mano (text()) ni frente
a accesos directos a PostgreSQL, e immutable_columns solo vigila cambios en
objetos (no `update()` masivos). Esa protección (triggers o permisos) queda
para la fase de hardening.
"""

from typing import Any

from sqlalchemy import event, inspect
from sqlalchemy.orm import Mapper, ORMExecuteState, Session


class ImmutableDataError(Exception):
    """Se intentó modificar o borrar un dato inmutable."""


_IMMUTABLE_MODELS: set[type[Any]] = set()


def _reject_row_change(_mapper: Mapper[Any], _connection: Any, target: Any) -> None:
    raise ImmutableDataError(f"{type(target).__name__} es inmutable: no se puede modificar ni borrar.")


def immutable_model[T](cls: type[T]) -> type[T]:
    """Decorador de modelo: sus filas no pueden modificarse ni borrarse desde el ORM."""
    event.listen(cls, "before_update", _reject_row_change)
    event.listen(cls, "before_delete", _reject_row_change)
    _IMMUTABLE_MODELS.add(cls)
    return cls


def immutable_columns[T](*column_names: str) -> Any:
    """Decorador de modelo: esas columnas no pueden cambiar tras el INSERT."""

    def decorator(cls: type[T]) -> type[T]:
        def reject_column_change(_mapper: Mapper[Any], _connection: Any, target: Any) -> None:
            state = inspect(target)
            for name in column_names:
                if state.attrs[name].history.has_changes():
                    raise ImmutableDataError(f"{cls.__name__}.{name} es inmutable.")

        event.listen(cls, "before_update", reject_column_change)
        return cls

    return decorator


@event.listens_for(Session, "do_orm_execute")
def _reject_bulk_changes(state: ORMExecuteState) -> None:
    if not (state.is_update or state.is_delete):
        return
    for mapper in state.all_mappers:
        if mapper.class_ in _IMMUTABLE_MODELS:
            raise ImmutableDataError(
                f"{mapper.class_.__name__} es inmutable: no se puede modificar ni borrar."
            )
