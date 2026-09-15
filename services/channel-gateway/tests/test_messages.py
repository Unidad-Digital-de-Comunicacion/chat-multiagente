from app.core_client import CanalNoEncontrado
from app.meta_client import EnvioFallido
from app.schemas import CanalConfig


def _body(canal_uuid="11111111-1111-1111-1111-111111111111"):
    return {"canal_uuid": canal_uuid, "destinatario_id": "PSID123", "texto": "Hola!"}


def _headers(token):
    return {"Authorization": f"Service-Token {token}"}


def test_envio_exitoso(client, canal_messenger, core_service_token, monkeypatch):
    async def fake_obtener_canal(canal_uuid):
        return canal_messenger
    monkeypatch.setattr("app.messages.obtener_canal", fake_obtener_canal)

    async def fake_enviar(canal, destinatario_id, texto):
        assert canal.tipo == "MESSENGER"
        assert destinatario_id == "PSID123"
        assert texto == "Hola!"
        return {"recipient_id": "PSID123", "message_id": "mid.1"}
    monkeypatch.setattr("app.messages.enviar_texto_por_canal", fake_enviar)

    response = client.post("/messages/send", json=_body(), headers=_headers(core_service_token))
    assert response.status_code == 200, response.text
    assert response.json()["graph_api_response"]["message_id"] == "mid.1"


def test_envio_exitoso_por_whatsapp(client, canal_whatsapp, core_service_token, monkeypatch):
    async def fake_obtener_canal(canal_uuid):
        return canal_whatsapp
    monkeypatch.setattr("app.messages.obtener_canal", fake_obtener_canal)

    async def fake_enviar(canal, destinatario_id, texto):
        assert canal.tipo == "WHATSAPP"
        assert canal.telefono_id == "1234567890"
        return {"messages": [{"id": "wamid.1"}]}
    monkeypatch.setattr("app.messages.enviar_texto_por_canal", fake_enviar)

    response = client.post("/messages/send", json=_body(), headers=_headers(core_service_token))
    assert response.status_code == 200, response.text
    assert response.json()["graph_api_response"]["messages"][0]["id"] == "wamid.1"


def test_sin_token_de_servicio_es_rechazado(client, canal_messenger, core_service_token, monkeypatch):
    async def fake_obtener_canal(canal_uuid):
        return canal_messenger
    monkeypatch.setattr("app.messages.obtener_canal", fake_obtener_canal)

    response = client.post("/messages/send", json=_body())
    assert response.status_code == 401


def test_token_de_servicio_incorrecto_es_rechazado(client, canal_messenger, core_service_token, monkeypatch):
    async def fake_obtener_canal(canal_uuid):
        return canal_messenger
    monkeypatch.setattr("app.messages.obtener_canal", fake_obtener_canal)

    response = client.post("/messages/send", json=_body(), headers=_headers("no-es-el-token-correcto"))
    assert response.status_code == 401


def test_sin_core_service_token_configurado_se_niega_todo(client, monkeypatch):
    from app.config import get_settings
    get_settings().core_service_token = ""

    response = client.post("/messages/send", json=_body(), headers=_headers("lo-que-sea"))
    assert response.status_code == 503


def test_canal_inexistente(client, core_service_token, monkeypatch):
    async def fake_obtener_canal(canal_uuid):
        raise CanalNoEncontrado(canal_uuid)
    monkeypatch.setattr("app.messages.obtener_canal", fake_obtener_canal)

    response = client.post("/messages/send", json=_body(), headers=_headers(core_service_token))
    assert response.status_code == 404


def test_canal_desactivado(client, core_service_token, monkeypatch):
    canal_inactivo = CanalConfig(
        organization_id=1, tipo="MESSENGER", api_key="x", webhook_secret="y", activo=False,
    )

    async def fake_obtener_canal(canal_uuid):
        return canal_inactivo
    monkeypatch.setattr("app.messages.obtener_canal", fake_obtener_canal)

    response = client.post("/messages/send", json=_body(), headers=_headers(core_service_token))
    assert response.status_code == 400


def test_canal_sin_soporte_de_envio(client, core_service_token, monkeypatch):
    canal_webchat = CanalConfig(
        organization_id=1, tipo="WEBCHAT", api_key="x", webhook_secret="", activo=True,
    )

    async def fake_obtener_canal(canal_uuid):
        return canal_webchat
    monkeypatch.setattr("app.messages.obtener_canal", fake_obtener_canal)

    response = client.post("/messages/send", json=_body(), headers=_headers(core_service_token))
    assert response.status_code == 400


def test_la_graph_api_rechaza_el_envio(client, canal_messenger, core_service_token, monkeypatch):
    async def fake_obtener_canal(canal_uuid):
        return canal_messenger
    monkeypatch.setattr("app.messages.obtener_canal", fake_obtener_canal)

    async def fake_enviar(*args, **kwargs):
        raise EnvioFallido("Invalid OAuth access token")
    monkeypatch.setattr("app.messages.enviar_texto_por_canal", fake_enviar)

    response = client.post("/messages/send", json=_body(), headers=_headers(core_service_token))
    assert response.status_code == 502
    assert "Invalid OAuth access token" in response.text
