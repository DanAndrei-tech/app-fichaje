"""Punto de entrada de la API.

Crea la aplicación FastAPI y monta las rutas versionadas bajo /api/v1.
"""

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)

app.include_router(api_router, prefix=settings.api_v1_prefix)
