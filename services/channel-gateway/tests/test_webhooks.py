import hashlib
import hmac
import json

from app.core_client import CanalNoEncontrado, CoreNoDisponible
from app.meta_client import EnvioFallido
from app.schemas import CanalConfig


def _firmar(body: bytes, secreto: str) -> str:
    return "sha256=" + hmac.new(secreto.encode(), body, hashlib.sha256).hexdigest()


def test_handshake_correcto_devuelve_el_challenge(client, canal_messenger, monkeypatch):
    async def fake_obtener_canal(canal_uuid):
        return canal_messenger
    monkeypatch.setattr("app.webhooks.obtener_canal", fake_obtener_canal)

    response = client.get(
        "/webhooks/messenger/11111111-1111-1111-1111-111111111111",
        params={"hub.mode": "subscribe", "hub.verify_token": "el-verify-token-del-canal", "hub.challenge": "1234"},
    )
    assert response.status_code == 200
    assert response.text == "1234"


def test_handshake_de_whatsapp_tambien_funciona(client, canal_whatsapp, monkeypatch):
    async def fake_obtener_canal(canal_uuid):
        return canal_whatsapp
    monkeypatch.setattr("app.webhooks.obtener_canal", fake_obtener_canal)

    response = client.get(
        "/webhooks/whatsapp/11111111-1111-1111-1111-111111111111",
        params={"hub.mode": "subscribe", "hub.verify_token": "el-verify-token-del-canal", "hub.challenge": "5678"},
    )
    assert response.status_code == 200
    assert response.text == "5678"


def test_handshake_con_verify_token_incorrecto(client, canal_messenger, monkeypatch):
    async def fake_obtener_canal(canal_uuid):
        return canal_messenger
    monkeypatch.setattr("app.webhooks.obtener_canal", fake_obtener_canal)

    response = client.get(
        "/webhooks/messenger/11111111-1111-1111-1111-111111111111",
        params={"hub.mode": "subscribe", "hub.verify_token": "no-es-el-correcto", "hub.challenge": "1234"},
    )
    assert response.status_code == 403


def test_handshake_canal_inexistente(client, monkeypatch):
    async def fake_obtener_canal(canal_uuid):
        raise CanalNoEncontrado(canal_uuid)
    monkeypatch.setattr("app.webhooks.obtener_canal", fake_obtener_canal)

    response = client.get(
        "/webhooks/messenger/00000000-0000-0000-0000-000000000000",
        params={"hub.mode": "subscribe", "hub.verify_token": "x", "hub.challenge": "1234"},
    )
    assert response.status_code == 404


def test_tipo_de_canal_no_soportado_todavia(client):
    response = client.get(
        "/webhooks/telegram/11111111-1111-1111-1111-111111111111",
        params={"hub.mode": "subscribe", "hub.verify_token": "x", "hub.challenge": "1234"},
    )
    assert response.status_code == 404


def test_core_caido_devuelve_503(client, monkeypatch):
    async def fake_obtener_canal(canal_uuid):
        raise CoreNoDisponible("timeout")
    monkeypatch.setattr("app.webhooks.obtener_canal", fake_obtener_canal)

    response = client.get(
        "/webhooks/messenger/11111111-1111-1111-1111-111111111111",
        params={"hub.mode": "subscribe", "hub.verify_token": "x", "hub.challenge": "1234"},
    )
    assert response.status_code == 503


def test_evento_con_firma_valida_ejecuta_las_acciones_que_devuelve_core(client, canal_messenger, monkeypatch):
    async def fake_obtener_canal(canal_uuid):
        return canal_messenger
    monkeypatch.setattr("app.webhooks.obtener_canal", fake_obtener_canal)
    from app.config import get_settings
    get_settings().meta_app_secret = "app-secret"

    llamadas_core = []

    async def fake_mensaje_entrante(*, organization_id, channel, contact_externo_id, texto):
        llamadas_core.append((organization_id, channel, contact_externo_id, texto))
        return [{"tipo": "enviar_texto", "texto": "¡Bienvenido!"}]
    monkeypatch.setattr("app.webhooks.enviar_mensaje_entrante", fake_mensaje_entrante)

    llamadas_envio = []

    async def fake_enviar_texto_por_canal(canal, destinatario_id, texto):
        llamadas_envio.append((canal.tipo, destinatario_id, texto))
        return {"message_id": "mid.respuesta"}
    monkeypatch.setattr("app.webhooks.enviar_texto_por_canal", fake_enviar_texto_por_canal)

    body = {"entry": [{"messaging": [{"sender": {"id": "PSID"}, "message": {"text": "hola"}}]}]}
    raw = json.dumps(body).encode()
    firma = _firmar(raw, "app-secret")

    response = client.post(
        "/webhooks/messenger/11111111-1111-1111-1111-111111111111",
        content=raw,
        headers={"X-Hub-Signature-256": firma, "Content-Type": "application/json"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok"}

    assert llamadas_core == [(1, "MESSENGER", "PSID", "hola")]
    assert llamadas_envio == [("MESSENGER", "PSID", "¡Bienvenido!")]


def test_evento_de_whatsapp_normaliza_y_ejecuta_las_acciones(client, canal_whatsapp, monkeypatch):
    async def fake_obtener_canal(canal_uuid):
        return canal_whatsapp
    monkeypatch.setattr("app.webhooks.obtener_canal", fake_obtener_canal)
    from app.config import get_settings
    get_settings().meta_app_secret = "app-secret"

    async def fake_mensaje_entrante(*, organization_id, channel, contact_externo_id, texto):
        assert channel == "WHATSAPP"
        assert contact_externo_id == "5493511234567"
        assert texto == "hola"
        return [{"tipo": "enviar_texto", "texto": "¡Bienvenido!"}]
    monkeypatch.setattr("app.webhooks.enviar_mensaje_entrante", fake_mensaje_entrante)

    llamadas_envio = []

    async def fake_enviar_texto_por_canal(canal, destinatario_id, texto):
        llamadas_envio.append((canal.tipo, destinatario_id, texto))
    monkeypatch.setattr("app.webhooks.enviar_texto_por_canal", fake_enviar_texto_por_canal)

    body = {
        "entry": [{"changes": [{"field": "messages", "value": {
            "messages": [{"from": "5493511234567", "type": "text", "text": {"body": "hola"}, "timestamp": "1700000000"}],
        }}]}],
    }
    raw = json.dumps(body).encode()
    firma = _firmar(raw, "app-secret")

    response = client.post(
        "/webhooks/whatsapp/11111111-1111-1111-1111-111111111111",
        content=raw,
        headers={"X-Hub-Signature-256": firma, "Content-Type": "application/json"},
    )
    assert response.status_code == 200, response.text
    assert llamadas_envio == [("WHATSAPP", "5493511234567", "¡Bienvenido!")]


def test_sin_acciones_de_core_no_manda_nada(client, canal_messenger, monkeypatch):
    async def fake_obtener_canal(canal_uuid):
        return canal_messenger
    monkeypatch.setattr("app.webhooks.obtener_canal", fake_obtener_canal)
    from app.config import get_settings
    get_settings().meta_app_secret = "app-secret"

    async def fake_mensaje_entrante(**kwargs):
        return []
    monkeypatch.setattr("app.webhooks.enviar_mensaje_entrante", fake_mensaje_entrante)

    llamadas_envio = []
    monkeypatch.setattr(
        "app.webhooks.enviar_texto_por_canal",
        lambda *a, **kw: llamadas_envio.append((a, kw)),
    )

    body = {"entry": [{"messaging": [{"sender": {"id": "PSID"}, "message": {"text": "sigo la charla"}}]}]}
    raw = json.dumps(body).encode()
    firma = _firmar(raw, "app-secret")

    response = client.post(
        "/webhooks/messenger/11111111-1111-1111-1111-111111111111",
        content=raw,
        headers={"X-Hub-Signature-256": firma, "Content-Type": "application/json"},
    )
    assert response.status_code == 200, response.text
    assert llamadas_envio == []


def test_si_falla_el_envio_de_una_accion_igual_se_confirma_el_webhook(client, canal_messenger, monkeypatch):
    # Meta reintenta si no contestamos 200 rápido — una api_key vencida no
    # debería hacer que Meta reintente el mismo webhook una y otra vez.
    async def fake_obtener_canal(canal_uuid):
        return canal_messenger
    monkeypatch.setattr("app.webhooks.obtener_canal", fake_obtener_canal)
    from app.config import get_settings
    get_settings().meta_app_secret = "app-secret"

    async def fake_mensaje_entrante(**kwargs):
        return [{"tipo": "enviar_texto", "texto": "¡Bienvenido!"}]
    monkeypatch.setattr("app.webhooks.enviar_mensaje_entrante", fake_mensaje_entrante)

    async def fake_enviar_texto_por_canal(*args, **kwargs):
        raise EnvioFallido("Invalid OAuth access token")
    monkeypatch.setattr("app.webhooks.enviar_texto_por_canal", fake_enviar_texto_por_canal)

    body = {"entry": [{"messaging": [{"sender": {"id": "PSID"}, "message": {"text": "hola"}}]}]}
    raw = json.dumps(body).encode()
    firma = _firmar(raw, "app-secret")

    response = client.post(
        "/webhooks/messenger/11111111-1111-1111-1111-111111111111",
        content=raw,
        headers={"X-Hub-Signature-256": firma, "Content-Type": "application/json"},
    )
    assert response.status_code == 200, response.text


def test_evento_con_firma_invalida_se_rechaza(client, canal_messenger, monkeypatch):
    from app.config import get_settings
    get_settings().meta_app_secret = "app-secret"

    async def fake_obtener_canal(canal_uuid):
        return canal_messenger
    monkeypatch.setattr("app.webhooks.obtener_canal", fake_obtener_canal)

    raw = b'{"entry": []}'
    response = client.post(
        "/webhooks/messenger/11111111-1111-1111-1111-111111111111",
        content=raw,
        headers={"X-Hub-Signature-256": "sha256=firma-inventada", "Content-Type": "application/json"},
    )
    assert response.status_code == 403


def test_evento_de_canal_con_tipo_distinto_al_de_la_url(client, monkeypatch):
    from app.config import get_settings
    get_settings().meta_app_secret = "app-secret"

    canal_instagram = CanalConfig(
        organization_id=1, tipo="INSTAGRAM", api_key="x", webhook_secret="y", activo=True,
    )

    async def fake_obtener_canal(canal_uuid):
        return canal_instagram
    monkeypatch.setattr("app.webhooks.obtener_canal", fake_obtener_canal)

    raw = b'{"entry": []}'
    firma = _firmar(raw, "app-secret")
    # Este uuid es de un canal INSTAGRAM (según el mock) pero se llama por
    # la URL de messenger — no debería coincidir.
    response = client.post(
        "/webhooks/messenger/11111111-1111-1111-1111-111111111111",
        content=raw,
        headers={"X-Hub-Signature-256": firma, "Content-Type": "application/json"},
    )
    assert response.status_code == 404
