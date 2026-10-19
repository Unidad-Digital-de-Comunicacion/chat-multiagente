import asyncio

import httpx
import pytest

from app.config import settings
from app.core_client import CoreClient
import app.core_client as core_client_module


class FakeResponse:
    def __init__(self, status_code, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.text = text

    def json(self):
        return self._json_data


class FakeAsyncClient:
    """Reemplaza `httpx.AsyncClient` dentro de `app.core_client` — no hay un
    cliente HTTP inyectable (a diferencia de channel-gateway), cada método
    de `CoreClient` abre el suyo con `async with httpx.AsyncClient(...)`, así
    que el seam disponible es parchear el propio `httpx.AsyncClient` que usa
    ese módulo."""

    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, params=None, headers=None):
        self.calls.append(("GET", url, params, headers))
        if self._exc:
            raise self._exc
        return self._response

    async def post(self, url, json=None, headers=None):
        self.calls.append(("POST", url, json, headers))
        if self._exc:
            raise self._exc
        return self._response


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def core_client_con(monkeypatch):
    """Devuelve una fábrica que arma un `CoreClient` nuevo con
    CORE_URL/CORE_SERVICE_TOKEN conocidos y su `httpx.AsyncClient`
    parcheado por el fake dado."""
    monkeypatch.setattr(settings, "CORE_URL", "http://core-test:80")
    monkeypatch.setattr(settings, "CORE_SERVICE_TOKEN", "el-token-webchat")

    def _factory(fake):
        monkeypatch.setattr(core_client_module.httpx, "AsyncClient", lambda timeout=None: fake)
        return CoreClient()

    return _factory


def test_enviar_mensaje_entrante_arma_la_url_y_el_payload_correctos(core_client_con):
    fake = FakeAsyncClient(response=FakeResponse(200, {"acciones": [{"tipo": "enviar_texto", "texto": "hola"}]}))
    client = core_client_con(fake)

    acciones = _run(client.enviar_mensaje_entrante(organization_id=7, visitor_id="v-1", texto="hola"))

    assert acciones == [{"tipo": "enviar_texto", "texto": "hola"}]
    metodo, url, body, headers = fake.calls[0]
    assert metodo == "POST"
    assert url == "http://core-test:80/api/core/bot/mensaje-entrante/"
    assert body == {
        "organization_id": 7,
        "channel": "WEBCHAT",
        "contact_externo_id": "v-1",
        "texto": "hola",
    }
    assert headers["Authorization"] == "Service-Token el-token-webchat"


def test_enviar_mensaje_entrante_si_core_devuelve_error_da_lista_vacia(core_client_con):
    fake = FakeAsyncClient(response=FakeResponse(500, text="boom"))
    client = core_client_con(fake)

    acciones = _run(client.enviar_mensaje_entrante(organization_id=7, visitor_id="v-1", texto="hola"))

    assert acciones == []


def test_enviar_mensaje_entrante_si_core_no_responde_da_lista_vacia(core_client_con):
    fake = FakeAsyncClient(exc=httpx.ConnectError("no responde"))
    client = core_client_con(fake)

    acciones = _run(client.enviar_mensaje_entrante(organization_id=7, visitor_id="v-1", texto="hola"))

    assert acciones == []


def test_obtener_historial_sesion_arma_los_params_correctos(core_client_con):
    fake = FakeAsyncClient(response=FakeResponse(200, {"mensajes": [{"texto": "hola"}]}))
    client = core_client_con(fake)

    mensajes = _run(client.obtener_historial_sesion(organization_id=7, visitor_id="v-1"))

    assert mensajes == [{"texto": "hola"}]
    metodo, url, params, headers = fake.calls[0]
    assert metodo == "GET"
    assert url == "http://core-test:80/api/core/internal/mensajes/"
    assert params == {"organization_id": 7, "canal": "WEBCHAT", "contact_externo_id": "v-1"}
    assert headers["Authorization"] == "Service-Token el-token-webchat"


def test_obtener_historial_sesion_si_core_no_lo_tiene_implementado_da_lista_vacia(core_client_con):
    fake = FakeAsyncClient(response=FakeResponse(404))
    client = core_client_con(fake)

    mensajes = _run(client.obtener_historial_sesion(organization_id=7, visitor_id="v-1"))

    assert mensajes == []


def test_obtener_historial_sesion_si_core_no_responde_da_lista_vacia(core_client_con):
    fake = FakeAsyncClient(exc=httpx.ConnectError("no responde"))
    client = core_client_con(fake)

    mensajes = _run(client.obtener_historial_sesion(organization_id=7, visitor_id="v-1"))

    assert mensajes == []
