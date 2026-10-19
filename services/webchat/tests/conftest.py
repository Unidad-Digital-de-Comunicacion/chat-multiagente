import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def core_service_token():
    """Deja `CORE_SERVICE_TOKEN` en un valor conocido para los tests de
    `/messages/send` (gateado con Service-Token) — mismo patrón que
    channel-gateway (`tests/conftest.py::core_service_token`)."""
    anterior = settings.CORE_SERVICE_TOKEN
    settings.CORE_SERVICE_TOKEN = "el-token-interno-de-prueba"
    yield settings.CORE_SERVICE_TOKEN
    settings.CORE_SERVICE_TOKEN = anterior
