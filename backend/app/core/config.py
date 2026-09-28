"""Configuración de la aplicación, leída de variables de entorno.

Los valores NO se escriben en el código: llegan desde el entorno
(docker-compose.yml -> .env). Aquí solo se declaran y se validan.

Por ahora solo se declara lo que se usa. Los secretos (JWT_SECRET,
PIN_HMAC_SECRET) se añadirán, como obligatorios, en las fases que los usen.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    app_name: str = "App Fichaje API"
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "info"
    api_v1_prefix: str = "/api/v1"

    # Obligatoria: sin ella la aplicación no arranca.
    # Formato: postgresql+psycopg://usuario:contraseña@host:puerto/base_de_datos
    database_url: str


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
