"""Conexión a PostgreSQL: engine, fábrica de sesiones y sesión por petición.

- engine: gestiona el pool de conexiones. Se crea una vez por proceso y no
  abre ninguna conexión hasta que se necesita.
- SessionLocal: fabrica sesiones (Session). Cada petición HTTP usa la suya.
- get_db: dependencia de FastAPI que abre la sesión, hace commit si el
  endpoint termina bien, rollback si lanza una excepción, y la cierra siempre.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    # Comprueba la conexión antes de usarla y descarta las rotas
    # (p. ej. tras reiniciar PostgreSQL).
    pool_pre_ping=True,
    # Si PostgreSQL no responde, falla en segundos en vez de quedarse colgado.
    connect_args={"connect_timeout": 5},
)

# expire_on_commit=False: tras el commit, los objetos siguen siendo legibles
# (útil para construir la respuesta sin volver a consultar la base de datos).
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Una sesión por petición: commit al terminar bien, rollback si falla, cierre siempre.

    Se usa a través de `DbSession` (app/api/deps.py), que la registra con
    scope="function" para que el commit ocurra ANTES de enviar la respuesta.
    """
    with SessionLocal() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
