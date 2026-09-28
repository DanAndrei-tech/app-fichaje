"""Registro de modelos para Alembic.

Alembic solo ve las tablas de los modelos que se han importado. Cada vez que
un módulo defina modelos, hay que importarlos aquí, por ejemplo:

    from app.modules.companies import models as companies_models  # noqa: F401

Todavía no hay modelos: se crearán en la fase siguiente.
"""

from app.db.base import Base

__all__ = ["Base"]
