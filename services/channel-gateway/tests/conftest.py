import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.schemas import CanalConfig


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def canal_messenger():
    return CanalConfig(
        organization_id=1, tipo="MESSENGER", api_key="page-access-token",
        webhook_secret="el-verify-token-del-canal", activo=True,
    )


@pytest.fixture
def canal_whatsapp():
    return CanalConfig(
        organization_id=1, tipo="WHATSAPP", api_key="cloud-api-token", telefono_id="1234567890",
        webhook_secret="el-verify-token-del-canal", activo=True,
    )


@pytest.fixture
def core_service_token():
    """Deja `CORE_SERVICE_TOKEN` en un valor conocido para las pruebas de
    `internal_auth` — se guarda directo en el singleton de `Settings`, mismo
    patrón que `test_core_client.py::_settings`."""
    settings = get_settings()
    anterior = settings.core_service_token
    settings.core_service_token = "el-token-interno-de-prueba"
    yield settings.core_service_token
    settings.core_service_token = anterior
