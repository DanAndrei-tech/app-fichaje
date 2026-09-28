from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import app


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_reports_unavailable_database_without_details() -> None:
    # Puerto 1 de localhost: la conexión se rechaza de inmediato.
    unreachable_engine = create_engine(
        "postgresql+psycopg://nobody:not-a-real-secret@127.0.0.1:1/nowhere",
        connect_args={"connect_timeout": 2},
    )

    def override_get_db() -> Iterator[Session]:
        with Session(unreachable_engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            response = test_client.get("/api/v1/health")
    finally:
        app.dependency_overrides.pop(get_db, None)
        unreachable_engine.dispose()

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "unavailable"}
    for internal_detail in ("not-a-real-secret", "127.0.0.1", "psycopg", "Error"):
        assert internal_detail not in response.text
