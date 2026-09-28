"""Punto de entrada de la API.

Crea la aplicación FastAPI y monta las rutas versionadas bajo /api/v1.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

import app.db.models  # noqa: F401  (registra todos los modelos SQLAlchemy)
from app.api.v1.router import api_router
from app.core.config import settings
from app.db.session import engine


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield
    # Al apagar la aplicación, cierra las conexiones del pool.
    engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router, prefix=settings.api_v1_prefix)
