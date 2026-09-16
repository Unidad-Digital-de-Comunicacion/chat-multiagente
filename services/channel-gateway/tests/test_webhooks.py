import hashlib
import hmac
import json

import httpx

from app.schemas import CanalConfig
from tests.conftest import FakeResponse, canal_a_json


def _firmar(body: bytes, secreto: str) -> str:
    return "sha256=" + hmac.new(secreto.encode(), body, hashlib.sha256).hexdigest()


def test_handshake_correcto_devuelve_el_challenge(client, fake_http_client, canal_messenger):
    fake_http_client.core_get_response = FakeResponse(200, canal_a_json(canal_messenger))

    response = client.get(
        "/webhooks/messenger/11111111-1111-1111-1111-111111111111",
        params={"hub.mode": "subscribe", "hub.verify_token": "el-verify-token-del-canal", "hub.challenge": "1234"},
    )
    assert response.status_code == 200
    assert response.text == "1234"


def test_handshake_de_whatsapp_tambien_funciona(client, fake_http_client, canal_whatsapp):
    fake_http_client.core_get_response = FakeResponse(200, canal_a_json(canal_whatsapp))

    response = client.get(
        "/webhooks/whatsapp/11111111-1111-1111-1111-111111111111",
        params={"hub.mode": "subscribe", "hub.verify_token": "el-verify-token-del-canal", "hub.challenge": "5678"},
    )
    assert response.status_code == 200
    assert response.text == "5678"


def test_handshake_con_verify_token_incorrecto(client, fake_http_client, canal_messenger):
    fake_http_client.core_get_response = FakeResponse(200, canal_a_json(canal_messenger))

    response = client.get(
        "/webhooks/messenger/11111111-1111-1111-1111-111111111111",
        params={"hub.mode": "subscribe", "hub.verify_token": "no-es-el-correcto", "hub.challenge": "1234"},
    )
    assert response.status_code == 403


def test_handshake_canal_inexistente(client, fake_http_client):
    fake_http_client.core_get_response = FakeResponse(404)

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


def test_core_caido_devuelve_503(client, fake_http_client):
    fake_http_client.core_get_exc = httpx.ConnectError("timeout")

    response = client.get(
        "/webhooks/messenger/11111111-1111-1111-1111-111111111111",
        params={"hub.mode": "subscribe", "hub.verify_token": "x", "hub.challenge": "1234"},
    )
    assert response.status_code == 503


def test_evento_con_firma_valida_ejecuta_las_acciones_que_devuelve_core(client, fake_http_client, canal_messenger):
    from app.config import get_settings
    get_settings().meta_app_secret = "app-secret"

    fake_http_client.core_get_response = FakeResponse(200, canal_a_json(canal_messenger))
    fake_http_client.core_post_response = FakeResponse(200, {"acciones": [{"tipo": "enviar_texto", "texto": "¡Bienvenido!"}]})
    fake_http_client.meta_response = FakeResponse(200, {"message_id": "mid.respuesta"})

    body = {"object": "page", "entry": [{"messaging": [{"sender": {"id": "PSID"}, "message": {"text": "hola"}}]}]}
    raw = json.dumps(body).encode()
    firma = _firmar(raw, "app-secret")

    response = client.post(
        "/webhooks/messenger/11111111-1111-1111-1111-111111111111",
        content=raw,
        headers={"X-Hub-Signature-256": firma, "Content-Type": "application/json"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok"}

    llamada_core = next(c for c in fake_http_client.calls if c[0] == "POST" and "mensaje-entrante" in c[1])
    assert llamada_core[3] == {"organization_id": 1, "channel": "MESSENGER", "contact_externo_id": "PSID", "texto": "hola"}

    llamada_meta = next(c for c in fake_http_client.calls if c[0] == "POST" and "graph.facebook.com" in c[1])
    assert llamada_meta[3]["message"]["text"] == "¡Bienvenido!"


def test_accion_mostrar_menu_se_manda_con_enviar_menu_por_canal(client, fake_http_client, canal_whatsapp):
    from app.config import get_settings
    get_settings().meta_app_secret = "app-secret"

    fake_http_client.core_get_response = FakeResponse(200, canal_a_json(canal_whatsapp))
    fake_http_client.core_post_response = FakeResponse(200, {"acciones": [{
        "tipo": "mostrar_menu", "texto": "1. Ventas\n2. Soporte",
        "encabezado": "¿En qué te ayudo?", "opciones": [{"id": "1", "titulo": "Ventas"}, {"id": "2", "titulo": "Soporte"}],
    }]})
    fake_http_client.meta_response = FakeResponse(200, {"messages": [{"id": "wamid.1"}]})

    body = {"object": "whatsapp_business_account", "entry": [{"changes": [{"field": "messages", "value": {
        "messages": [{"from": "5493511234567", "type": "text", "text": {"body": "hola"}}],
    }}]}]}
    raw = json.dumps(body).encode()
    firma = _firmar(raw, "app-secret")

    response = client.post(
        "/webhooks/whatsapp/11111111-1111-1111-1111-111111111111",
        content=raw,
        headers={"X-Hub-Signature-256": firma, "Content-Type": "application/json"},
    )
    assert response.status_code == 200, response.text

    llamada_meta = next(c for c in fake_http_client.calls if c[0] == "POST" and "graph.facebook.com" in c[1])
    assert "/1234567890/messages" in llamada_meta[1]
    interactive = llamada_meta[3]["interactive"]
    assert interactive["type"] == "button"  # 2 opciones -> botones (1 a 3)
    assert interactive["body"]["text"] == "1. Ventas\n2. Soporte"
    assert [b["reply"]["title"] for b in interactive["action"]["buttons"]] == ["Ventas", "Soporte"]


def test_evento_de_whatsapp_normaliza_y_ejecuta_las_acciones(client, fake_http_client, canal_whatsapp):
    from app.config import get_settings
    get_settings().meta_app_secret = "app-secret"

    fake_http_client.core_get_response = FakeResponse(200, canal_a_json(canal_whatsapp))
    fake_http_client.core_post_response = FakeResponse(200, {"acciones": [{"tipo": "enviar_texto", "texto": "¡Bienvenido!"}]})
    fake_http_client.meta_response = FakeResponse(200, {"messages": [{"id": "wamid.1"}]})

    body = {
        "object": "whatsapp_business_account",
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

    llamada_core = next(c for c in fake_http_client.calls if c[0] == "POST" and "mensaje-entrante" in c[1])
    assert llamada_core[3]["channel"] == "WHATSAPP"
    assert llamada_core[3]["contact_externo_id"] == "5493511234567"
    assert llamada_core[3]["texto"] == "hola"

    llamada_meta = next(c for c in fake_http_client.calls if c[0] == "POST" and "graph.facebook.com" in c[1])
    assert llamada_meta[3]["text"]["body"] == "¡Bienvenido!"


def test_sin_acciones_de_core_no_manda_nada(client, fake_http_client, canal_messenger):
    from app.config import get_settings
    get_settings().meta_app_secret = "app-secret"

    fake_http_client.core_get_response = FakeResponse(200, canal_a_json(canal_messenger))
    fake_http_client.core_post_response = FakeResponse(200, {"acciones": []})

    body = {"object": "page", "entry": [{"messaging": [{"sender": {"id": "PSID"}, "message": {"text": "sigo la charla"}}]}]}
    raw = json.dumps(body).encode()
    firma = _firmar(raw, "app-secret")

    response = client.post(
        "/webhooks/messenger/11111111-1111-1111-1111-111111111111",
        content=raw,
        headers={"X-Hub-Signature-256": firma, "Content-Type": "application/json"},
    )
    assert response.status_code == 200, response.text
    assert not any(c[0] == "POST" and "graph.facebook.com" in c[1] for c in fake_http_client.calls)


def test_si_falla_el_envio_de_una_accion_igual_se_confirma_el_webhook(client, fake_http_client, canal_messenger):
    # Meta reintenta si no contestamos 200 rápido — una api_key vencida no
    # debería hacer que Meta reintente el mismo webhook una y otra vez.
    from app.config import get_settings
    get_settings().meta_app_secret = "app-secret"

    fake_http_client.core_get_response = FakeResponse(200, canal_a_json(canal_messenger))
    fake_http_client.core_post_response = FakeResponse(200, {"acciones": [{"tipo": "enviar_texto", "texto": "¡Bienvenido!"}]})
    fake_http_client.meta_response = FakeResponse(400, {"error": {"message": "Invalid OAuth access token"}})

    body = {"object": "page", "entry": [{"messaging": [{"sender": {"id": "PSID"}, "message": {"text": "hola"}}]}]}
    raw = json.dumps(body).encode()
    firma = _firmar(raw, "app-secret")

    response = client.post(
        "/webhooks/messenger/11111111-1111-1111-1111-111111111111",
        content=raw,
        headers={"X-Hub-Signature-256": firma, "Content-Type": "application/json"},
    )
    assert response.status_code == 200, response.text


def test_evento_con_firma_invalida_se_rechaza(client, fake_http_client):
    from app.config import get_settings
    get_settings().meta_app_secret = "app-secret"

    raw = b'{"entry": []}'
    response = client.post(
        "/webhooks/messenger/11111111-1111-1111-1111-111111111111",
        content=raw,
        headers={"X-Hub-Signature-256": "sha256=firma-inventada", "Content-Type": "application/json"},
    )
    assert response.status_code == 403
    # La firma se verifica ANTES de pedirle nada a Core.
    assert fake_http_client.calls == []


def test_objeto_desconocido_no_procesa_nada(client, fake_http_client, canal_messenger):
    from app.config import get_settings
    get_settings().meta_app_secret = "app-secret"

    fake_http_client.core_get_response = FakeResponse(200, canal_a_json(canal_messenger))

    body = {"object": "user"}  # algo que Meta manda pero no es mensajería
    raw = json.dumps(body).encode()
    firma = _firmar(raw, "app-secret")

    response = client.post(
        "/webhooks/messenger/11111111-1111-1111-1111-111111111111",
        content=raw,
        headers={"X-Hub-Signature-256": firma, "Content-Type": "application/json"},
    )
    assert response.status_code == 200, response.text
    assert not any(c[0] == "POST" for c in fake_http_client.calls)


def test_objeto_del_payload_manda_al_canal_hermano_de_la_misma_organizacion(client, fake_http_client):
    # Meta sólo deja una Callback URL por app: si el Admin usó la URL de
    # Messenger para las tres suscripciones, un evento de Instagram real
    # llega a esa MISMA URL. Tiene que resolverse con el canal INSTAGRAM de
    # la organización, no con el canal MESSENGER de la URL.
    from app.config import get_settings
    get_settings().meta_app_secret = "app-secret"

    canal_url = CanalConfig(organization_id=7, tipo="MESSENGER", api_key="msj-token", webhook_secret="x", activo=True)
    canal_hermano = CanalConfig(organization_id=7, tipo="INSTAGRAM", api_key="ig-token", webhook_secret="y", activo=True)
    fake_http_client.core_get_response = FakeResponse(200, canal_a_json(canal_url))
    fake_http_client.sibling_get_response = FakeResponse(200, canal_a_json(canal_hermano))
    fake_http_client.core_post_response = FakeResponse(200, {"acciones": []})

    body = {"object": "instagram", "entry": [{"messaging": [{"sender": {"id": "IGSID"}, "message": {"text": "hola"}}]}]}
    raw = json.dumps(body).encode()
    firma = _firmar(raw, "app-secret")

    response = client.post(
        "/webhooks/messenger/11111111-1111-1111-1111-111111111111",  # URL de Messenger
        content=raw,
        headers={"X-Hub-Signature-256": firma, "Content-Type": "application/json"},
    )
    assert response.status_code == 200, response.text

    llamada_hermano = next(c for c in fake_http_client.calls if c[0] == "GET" and "/organizacion/" in c[1])
    assert "/organizacion/7/INSTAGRAM/" in llamada_hermano[1]
    llamada_core = next(c for c in fake_http_client.calls if c[0] == "POST" and "mensaje-entrante" in c[1])
    assert llamada_core[3]["channel"] == "INSTAGRAM"  # el canal hermano, no el de la URL


def test_sin_canal_hermano_configurado_no_rompe(client, fake_http_client, canal_messenger):
    from app.config import get_settings
    get_settings().meta_app_secret = "app-secret"

    fake_http_client.core_get_response = FakeResponse(200, canal_a_json(canal_messenger))
    # `sibling_get_response` queda en el default (404 -> CanalNoEncontrado).

    body = {"object": "instagram", "entry": []}
    raw = json.dumps(body).encode()
    firma = _firmar(raw, "app-secret")

    response = client.post(
        "/webhooks/messenger/11111111-1111-1111-1111-111111111111",
        content=raw,
        headers={"X-Hub-Signature-256": firma, "Content-Type": "application/json"},
    )
    assert response.status_code == 200, response.text
    assert not any(c[0] == "POST" for c in fake_http_client.calls)
