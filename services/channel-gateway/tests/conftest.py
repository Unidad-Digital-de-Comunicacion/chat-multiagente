import dataclasses

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.http_client import get_http_client
from app.main import app
from app.schemas import CanalConfig


class FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.content = b"1" if json_data is not None else b""

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)


class FakeAsyncClient:
    """Cliente HTTP falso inyectado vía `app.dependency_overrides[get_http_
    client]` (fixture `fake_http_client` más abajo) — el seam real para los
    tests end-to-end con `TestClient`, en vez de parchear un import.

    `obtener_canal`/`obtener_canal_por_organizacion`/`obtener_meta_app`
    sólo hacen GET (contra Core, a tres URLs distintas — se enrutan por
    `/organizacion/` y `/meta-app/` en el path) y comparten el mismo
    cliente que `enviar_mensaje_entrante` (POST a Core) y `meta_client`
    (POST a la Graph API de Meta) en el flujo real de `webhooks.py` — se
    enruta por URL en vez de asumir un solo GET/POST posible."""

    def __init__(self):
        self.calls = []
        self.core_get_response = FakeResponse(200, {})
        self.core_get_exc = None
        # Canal "hermano" (`obtener_canal_por_organizacion`) — 404 por
        # defecto (`CanalNoEncontrado`), la organización no siempre tiene
        # configurado el tipo que se busca.
        self.sibling_get_response = FakeResponse(404)
        self.sibling_get_exc = None
        # `obtener_meta_app` — "app-secret" por defecto para que los tests
        # existentes (que firman con ese mismo valor, ver `_firmar` en
        # `test_webhooks.py`) sigan validando sin tener que configurar esto
        # a mano en cada uno.
        self.meta_app_response = FakeResponse(200, {"app_id": "app-id", "app_secret": "app-secret"})
        self.meta_app_exc = None
        self.core_post_response = FakeResponse(200, {"acciones": []})
        self.meta_response = FakeResponse(200, {"message_id": "mid.1"})
        self.meta_exc = None

    async def get(self, url, headers=None):
        self.calls.append(("GET", url, headers, None))
        if "/meta-app/" in url:
            if self.meta_app_exc:
                raise self.meta_app_exc
            return self.meta_app_response
        if "/organizacion/" in url:
            if self.sibling_get_exc:
                raise self.sibling_get_exc
            return self.sibling_get_response
        if self.core_get_exc:
            raise self.core_get_exc
        return self.core_get_response

    async def post(self, url, headers=None, json=None, params=None):
        self.calls.append(("POST", url, headers, json))
        if "graph.facebook.com" in url:
            if self.meta_exc:
                raise self.meta_exc
            return self.meta_response
        return self.core_post_response


def canal_a_json(canal: CanalConfig) -> dict:
    return dataclasses.asdict(canal)


@pytest.fixture
def fake_http_client():
    fake = FakeAsyncClient()
    app.dependency_overrides[get_http_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_http_client, None)


@pytest.fixture
def client(fake_http_client):
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
