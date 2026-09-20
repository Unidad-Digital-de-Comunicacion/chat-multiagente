import asyncio

import pytest

from app.meta_client import EnvioFallido, enviar_menu_por_canal, enviar_texto_por_canal, enviar_texto_whatsapp
from app.schemas import CanalConfig


class _FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.content = b"1" if json_data is not None else b""

    def json(self):
        return self._json_data


class _FakeAsyncClient:
    """El seam real para los tests de `meta_client`: se pasa directo como
    argumento a cada función en vez de parchear `httpx.AsyncClient` (el
    import global) — production code recibe el `httpx.AsyncClient`
    compartido de la app de la misma forma (ver `http_client.py`)."""

    def __init__(self, response, capture):
        self._response = response
        self._capture = capture

    async def post(self, url, headers=None, json=None, params=None):
        self._capture["url"] = url
        self._capture["headers"] = headers
        self._capture["json"] = json
        self._capture["params"] = params
        return self._response


def _run(coro):
    return asyncio.run(coro)


def test_whatsapp_manda_bearer_y_url_con_telefono_id():
    capture = {}
    fake_client = _FakeAsyncClient(_FakeResponse(200, {"messages": [{"id": "wamid.1"}]}), capture)

    resultado = _run(enviar_texto_whatsapp(
        fake_client, api_key="cloud-api-token", telefono_id="111", destinatario_id="5493511234567", texto="Hola",
    ))

    assert resultado == {"messages": [{"id": "wamid.1"}]}
    assert capture["url"].endswith("/111/messages")
    assert capture["headers"]["Authorization"] == "Bearer cloud-api-token"
    assert capture["json"]["to"] == "5493511234567"
    assert capture["json"]["text"]["body"] == "Hola"
    assert capture["json"]["messaging_product"] == "whatsapp"


def test_whatsapp_sin_telefono_id_no_intenta_nada():
    fake_client = _FakeAsyncClient(_FakeResponse(200), {})
    with pytest.raises(EnvioFallido, match="phone_number_id"):
        _run(enviar_texto_whatsapp(fake_client, api_key="token", telefono_id="", destinatario_id="x", texto="y"))


def test_whatsapp_sin_api_key_no_intenta_nada():
    fake_client = _FakeAsyncClient(_FakeResponse(200), {})
    with pytest.raises(EnvioFallido, match="token"):
        _run(enviar_texto_whatsapp(fake_client, api_key="", telefono_id="111", destinatario_id="x", texto="y"))


def test_whatsapp_error_de_la_cloud_api():
    capture = {}
    fake_client = _FakeAsyncClient(_FakeResponse(400, {"error": {"message": "Invalid parameter"}}), capture)

    with pytest.raises(EnvioFallido, match="Invalid parameter"):
        _run(enviar_texto_whatsapp(fake_client, api_key="token", telefono_id="111", destinatario_id="x", texto="y"))


def test_dispatcher_manda_whatsapp_a_la_cloud_api():
    capture = {}
    fake_client = _FakeAsyncClient(_FakeResponse(200, {"messages": [{"id": "wamid.1"}]}), capture)

    canal = CanalConfig(
        organization_id=1, tipo="WHATSAPP", api_key="token", telefono_id="111",
        webhook_secret="x", activo=True,
    )
    _run(enviar_texto_por_canal(fake_client, canal, "5493511234567", "Hola"))
    assert "/111/messages" in capture["url"]


def test_dispatcher_manda_messenger_a_la_send_api():
    capture = {}
    fake_client = _FakeAsyncClient(_FakeResponse(200, {"recipient_id": "PSID", "message_id": "mid.1"}), capture)

    canal = CanalConfig(organization_id=1, tipo="MESSENGER", api_key="token", webhook_secret="x", activo=True)
    _run(enviar_texto_por_canal(fake_client, canal, "PSID", "Hola"))
    assert capture["url"].endswith("/me/messages")
    assert capture["params"]["access_token"] == "token"


def _canal_whatsapp():
    return CanalConfig(
        organization_id=1, tipo="WHATSAPP", api_key="token", telefono_id="111",
        webhook_secret="x", activo=True,
    )


def test_menu_con_1_a_3_opciones_manda_botones():
    capture = {}
    fake_client = _FakeAsyncClient(_FakeResponse(200, {"messages": [{"id": "wamid.1"}]}), capture)

    opciones = [{"id": "1", "titulo": "Ventas"}, {"id": "2", "titulo": "Soporte"}]
    _run(enviar_menu_por_canal(
        fake_client, _canal_whatsapp(), "5493511234567", "1. Ventas\n2. Soporte", "¿En qué te ayudo?", opciones,
    ))

    interactive = capture["json"]["interactive"]
    assert interactive["type"] == "button"
    # El cuerpo lleva el texto CON el listado numerado (no sólo el saludo)
    # — las opciones tienen que verse como texto además del selector táctil.
    assert interactive["body"]["text"] == "1. Ventas\n2. Soporte"
    botones = interactive["action"]["buttons"]
    assert len(botones) == 2
    assert botones[0]["reply"] == {"id": "1", "title": "Ventas"}


def test_menu_con_4_a_10_opciones_manda_lista():
    capture = {}
    fake_client = _FakeAsyncClient(_FakeResponse(200, {"messages": [{"id": "wamid.1"}]}), capture)

    opciones = [{"id": str(i), "titulo": f"Opción {i}"} for i in range(1, 6)]
    _run(enviar_menu_por_canal(
        fake_client, _canal_whatsapp(), "5493511234567", "texto plano con el listado", "Elegí una:", opciones,
    ))

    interactive = capture["json"]["interactive"]
    assert interactive["type"] == "list"
    assert interactive["body"]["text"] == "texto plano con el listado"
    filas = interactive["action"]["sections"][0]["rows"]
    assert len(filas) == 5
    assert filas[0] == {"id": "1", "title": "Opción 1"}


def test_menu_recorta_titulos_largos_al_limite_de_whatsapp():
    capture = {}
    fake_client = _FakeAsyncClient(_FakeResponse(200, {"messages": []}), capture)

    titulo_largo = "Un título de opción larguísimo que supera el límite de WhatsApp"
    opciones = [{"id": "1", "titulo": titulo_largo}, {"id": "2", "titulo": "Corto"}, {"id": "3", "titulo": "Otro"}]
    _run(enviar_menu_por_canal(fake_client, _canal_whatsapp(), "x", "texto", "Elegí:", opciones))

    titulo_enviado = capture["json"]["interactive"]["action"]["buttons"][0]["reply"]["title"]
    assert len(titulo_enviado) == 20


def test_menu_con_mas_de_10_opciones_cae_a_texto_plano():
    capture = {}
    fake_client = _FakeAsyncClient(_FakeResponse(200, {"messages": []}), capture)

    opciones = [{"id": str(i), "titulo": f"Opción {i}"} for i in range(1, 12)]
    _run(enviar_menu_por_canal(fake_client, _canal_whatsapp(), "x", "1. Opción 1\n...", "Elegí:", opciones))

    assert capture["json"]["type"] == "text"
    assert capture["json"]["text"]["body"] == "1. Opción 1\n..."


def test_menu_para_messenger_siempre_manda_texto_plano_numerado():
    # Se probaron quick_replies, Button Template y Generic Template para
    # Messenger y ninguno funcionó bien en la práctica (ver docstring del
    # módulo) — quedó revertido a texto plano numerado sin importar la
    # cantidad de opciones, el contacto responde escribiendo el número.
    capture = {}
    fake_client = _FakeAsyncClient(_FakeResponse(200, {"message_id": "mid.1"}), capture)

    canal = CanalConfig(organization_id=1, tipo="MESSENGER", api_key="token", webhook_secret="x", activo=True)
    opciones = [{"id": "1", "titulo": "Ventas"}, {"id": "2", "titulo": "Soporte"}]
    _run(enviar_menu_por_canal(fake_client, canal, "PSID", "1. Ventas\n2. Soporte", "¿En qué te ayudo?", opciones))

    assert capture["url"].endswith("/me/messages")
    assert "attachment" not in capture["json"]["message"]
    assert "quick_replies" not in capture["json"]["message"]
    assert capture["json"]["message"]["text"] == "1. Ventas\n2. Soporte"


def test_menu_para_messenger_con_muchas_opciones_tambien_manda_texto_plano():
    capture = {}
    fake_client = _FakeAsyncClient(_FakeResponse(200, {"message_id": "mid.1"}), capture)

    canal = CanalConfig(organization_id=1, tipo="MESSENGER", api_key="token", webhook_secret="x", activo=True)
    opciones = [{"id": str(i), "titulo": f"Opción {i}"} for i in range(1, 12)]
    _run(enviar_menu_por_canal(fake_client, canal, "PSID", "1. Opción 1\n...", "Elegí:", opciones))

    assert "attachment" not in capture["json"]["message"]
    assert "quick_replies" not in capture["json"]["message"]
    assert capture["json"]["message"]["text"] == "1. Opción 1\n..."


def test_menu_para_instagram_siempre_manda_texto_plano_numerado():
    # Misma configuración que Messenger (pedido explícito, 2026-09-20): con
    # Instagram dado de alta bajo la misma app de Meta, `quick_replies` no
    # le llegaba al contacto en producción — se unificó a texto plano.
    capture = {}
    fake_client = _FakeAsyncClient(_FakeResponse(200, {"message_id": "mid.1"}), capture)

    canal = CanalConfig(organization_id=1, tipo="INSTAGRAM", api_key="token", webhook_secret="x", activo=True)
    opciones = [{"id": "1", "titulo": "Ventas"}, {"id": "2", "titulo": "Soporte"}]
    _run(enviar_menu_por_canal(fake_client, canal, "PSID", "1. Ventas\n2. Soporte", "¿En qué te ayudo?", opciones))

    assert capture["url"].endswith("/me/messages")
    assert "attachment" not in capture["json"]["message"]
    assert "quick_replies" not in capture["json"]["message"]
    assert capture["json"]["message"]["text"] == "1. Ventas\n2. Soporte"


def test_menu_para_instagram_con_muchas_opciones_tambien_manda_texto_plano():
    capture = {}
    fake_client = _FakeAsyncClient(_FakeResponse(200, {"message_id": "mid.1"}), capture)

    canal = CanalConfig(organization_id=1, tipo="INSTAGRAM", api_key="token", webhook_secret="x", activo=True)
    opciones = [{"id": str(i), "titulo": f"Opción {i}"} for i in range(1, 15)]
    _run(enviar_menu_por_canal(fake_client, canal, "PSID", "1. Opción 1\n...", "Elegí:", opciones))

    assert "quick_replies" not in capture["json"]["message"]
    assert capture["json"]["message"]["text"] == "1. Opción 1\n..."
