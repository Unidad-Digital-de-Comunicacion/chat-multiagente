import asyncio

import httpx
import pytest

from app.meta_client import EnvioFallido, enviar_texto_por_canal, enviar_texto_whatsapp
from app.schemas import CanalConfig


class _FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.content = b"1" if json_data is not None else b""

    def json(self):
        return self._json_data


class _FakeAsyncClient:
    def __init__(self, response, capture, **kwargs):
        self._response = response
        self._capture = capture

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, headers=None, json=None, params=None):
        self._capture["url"] = url
        self._capture["headers"] = headers
        self._capture["json"] = json
        self._capture["params"] = params
        return self._response


def _run(coro):
    return asyncio.run(coro)


def test_whatsapp_manda_bearer_y_url_con_telefono_id(monkeypatch):
    capture = {}
    fake_response = _FakeResponse(200, {"messages": [{"id": "wamid.1"}]})
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(fake_response, capture))

    resultado = _run(enviar_texto_whatsapp(
        api_key="cloud-api-token", telefono_id="111", destinatario_id="5493511234567", texto="Hola",
    ))

    assert resultado == {"messages": [{"id": "wamid.1"}]}
    assert capture["url"].endswith("/111/messages")
    assert capture["headers"]["Authorization"] == "Bearer cloud-api-token"
    assert capture["json"]["to"] == "5493511234567"
    assert capture["json"]["text"]["body"] == "Hola"
    assert capture["json"]["messaging_product"] == "whatsapp"


def test_whatsapp_sin_telefono_id_no_intenta_nada():
    with pytest.raises(EnvioFallido, match="phone_number_id"):
        _run(enviar_texto_whatsapp(api_key="token", telefono_id="", destinatario_id="x", texto="y"))


def test_whatsapp_sin_api_key_no_intenta_nada():
    with pytest.raises(EnvioFallido, match="token"):
        _run(enviar_texto_whatsapp(api_key="", telefono_id="111", destinatario_id="x", texto="y"))


def test_whatsapp_error_de_la_cloud_api(monkeypatch):
    capture = {}
    fake_response = _FakeResponse(400, {"error": {"message": "Invalid parameter"}})
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(fake_response, capture))

    with pytest.raises(EnvioFallido, match="Invalid parameter"):
        _run(enviar_texto_whatsapp(api_key="token", telefono_id="111", destinatario_id="x", texto="y"))


def test_dispatcher_manda_whatsapp_a_la_cloud_api(monkeypatch):
    capture = {}
    fake_response = _FakeResponse(200, {"messages": [{"id": "wamid.1"}]})
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(fake_response, capture))

    canal = CanalConfig(
        organization_id=1, tipo="WHATSAPP", api_key="token", telefono_id="111",
        webhook_secret="x", activo=True,
    )
    _run(enviar_texto_por_canal(canal, "5493511234567", "Hola"))
    assert "/111/messages" in capture["url"]


def test_dispatcher_manda_messenger_a_la_send_api(monkeypatch):
    capture = {}
    fake_response = _FakeResponse(200, {"recipient_id": "PSID", "message_id": "mid.1"})
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(fake_response, capture))

    canal = CanalConfig(organization_id=1, tipo="MESSENGER", api_key="token", webhook_secret="x", activo=True)
    _run(enviar_texto_por_canal(canal, "PSID", "Hola"))
    assert capture["url"].endswith("/me/messages")
    assert capture["params"]["access_token"] == "token"
