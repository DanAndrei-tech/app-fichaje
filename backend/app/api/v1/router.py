"""Router principal de la API v1.

Agrupa los routers de cada módulo. En cada fase se irá añadiendo aquí
el router del módulo correspondiente (companies, employees, clock...).
"""

from fastapi import APIRouter

from app.api.v1 import health

api_router = APIRouter()

api_router.include_router(health.router)
