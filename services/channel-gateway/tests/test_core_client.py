import asyncio

import httpx
import pytest

from app.config import get_settings
from app.core_client import CanalNoEncontrado, CoreNoDisponible, enviar_mensaje_entrante, obtener_canal


class _FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)


class _FakeAsyncClient:
    def __init__(self, response=None, exc=None, **kwargs):
        self._response = response
        self._exc = exc
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, headers=None):
        self.calls.append(("GET", url, headers, None))
        if self._exc:
            raise self._exc
        return self._response

    async def post(self, url, headers=None, json=None):
        self.calls.append(("POST", url, headers, json))
        if self._exc:
            raise self._exc
        return self._response


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _settings():
    settings = get_settings()
    settings.core_base_url = "http://core-test"
    settings.core_service_token = "el-token-de-gateway"
    yield settings


def test_devuelve_la_config_del_canal(monkeypatch):
    data = {
        "organization_id": 7, "tipo": "MESSENGER", "api_key": "pat",
        "webhook_secret": "secreto", "activo": True,
    }
    fake_client = _FakeAsyncClient(response=_FakeResponse(200, data))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: fake_client)

    canal = _run(obtener_canal("un-uuid"))

    assert canal.organization_id == 7
    assert canal.api_key == "pat"
    metodo, url, headers, _ = fake_client.calls[0]
    assert metodo == "GET"
    assert url == "http://core-test/api/core/internal/canales/un-uuid/"
    assert headers["Authorization"] == "Service-Token el-token-de-gateway"


def test_canal_inexistente_da_404(monkeypatch):
    fake_client = _FakeAsyncClient(response=_FakeResponse(404))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: fake_client)

    with pytest.raises(CanalNoEncontrado):
        _run(obtener_canal("un-uuid"))


def test_core_inalcanzable(monkeypatch):
    fake_client = _FakeAsyncClient(exc=httpx.ConnectError("no responde"))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: fake_client)

    with pytest.raises(CoreNoDisponible):
        _run(obtener_canal("un-uuid"))


def test_mensaje_entrante_devuelve_las_acciones(monkeypatch):
    fake_client = _FakeAsyncClient(response=_FakeResponse(200, {"acciones": [{"tipo": "enviar_texto", "texto": "hola"}]}))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: fake_client)

    acciones = _run(enviar_mensaje_entrante(
        organization_id=7, channel="WHATSAPP", contact_externo_id="549351", texto="hola",
    ))

    assert acciones == [{"tipo": "enviar_texto", "texto": "hola"}]
    metodo, url, headers, body = fake_client.calls[0]
    assert metodo == "POST"
    assert url == "http://core-test/api/core/bot/mensaje-entrante/"
    assert headers["Authorization"] == "Service-Token el-token-de-gateway"
    assert body == {"organization_id": 7, "channel": "WHATSAPP", "contact_externo_id": "549351", "texto": "hola"}


def test_mensaje_entrante_si_core_falla_devuelve_lista_vacia(monkeypatch):
    fake_client = _FakeAsyncClient(response=_FakeResponse(500, {}))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: fake_client)

    acciones = _run(enviar_mensaje_entrante(
        organization_id=7, channel="WHATSAPP", contact_externo_id="549351", texto="hola",
    ))
    assert acciones == []


def test_mensaje_entrante_si_core_no_responde_devuelve_lista_vacia(monkeypatch):
    fake_client = _FakeAsyncClient(exc=httpx.ConnectError("no responde"))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: fake_client)

    acciones = _run(enviar_mensaje_entrante(
        organization_id=7, channel="WHATSAPP", contact_externo_id="549351", texto="hola",
    ))
    assert acciones == []
