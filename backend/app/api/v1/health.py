"""Comprobación de salud de la API y de PostgreSQL.

- 200 {"status": "ok", "database": "ok"}: todo funciona.
- 503 {"status": "degraded", "database": "unavailable"}: la API responde,
  pero no puede usar PostgreSQL. El detalle del error solo va al log.
"""

import logging

from fastapi import APIRouter, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import DbSession

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "PostgreSQL no disponible"}},
)
def health(db: DbSession, response: Response) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Health: no se puede conectar con PostgreSQL")
        db.rollback()
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "degraded", "database": "unavailable"}
    return {"status": "ok", "database": "ok"}
