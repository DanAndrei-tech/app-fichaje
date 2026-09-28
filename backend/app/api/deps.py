"""Dependencias comunes de los endpoints.

Uso en un endpoint:

    @router.get("/...")
    def endpoint(db: DbSession) -> ...:
        ...
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db

# scope="function": el código posterior al `yield` de get_db (commit/rollback
# y cierre) se ejecuta al terminar el endpoint y ANTES de enviar la respuesta.
# Con el scope por defecto se ejecutaría después, y un commit fallido no
# llegaría al cliente (recibiría un 200 aunque no se hubiera guardado nada).
DbSession = Annotated[Session, Depends(get_db, scope="function")]
