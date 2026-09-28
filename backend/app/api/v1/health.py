"""Comprobación de salud: indica que la API está levantada.

En la fase de base de datos se podrá ampliar para comprobar también PostgreSQL.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
