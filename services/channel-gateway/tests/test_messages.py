from tests.conftest import FakeResponse, canal_a_json


def _body(canal_uuid="11111111-1111-1111-1111-111111111111"):
    return {"canal_uuid": canal_uuid, "destinatario_id": "PSID123", "texto": "Hola!"}


def _headers(token):
    return {"Authorization": f"Service-Token {token}"}


def test_envio_exitoso(client, fake_http_client, canal_messenger, core_service_token):
    fake_http_client.core_get_response = FakeResponse(200, canal_a_json(canal_messenger))
    fake_http_client.meta_response = FakeResponse(200, {"recipient_id": "PSID123", "message_id": "mid.1"})

    response = client.post("/messages/send", json=_body(), headers=_headers(core_service_token))
    assert response.status_code == 200, response.text
    assert response.json()["graph_api_response"]["message_id"] == "mid.1"

    metodo_post, url_post, _, body_post = fake_http_client.calls[-1]
    assert metodo_post == "POST"
    assert "graph.facebook.com" in url_post
    assert body_post["message"]["text"] == "Hola!"


def test_envio_exitoso_por_whatsapp(client, fake_http_client, canal_whatsapp, core_service_token):
    fake_http_client.core_get_response = FakeResponse(200, canal_a_json(canal_whatsapp))
    fake_http_client.meta_response = FakeResponse(200, {"messages": [{"id": "wamid.1"}]})

    response = client.post("/messages/send", json=_body(), headers=_headers(core_service_token))
    assert response.status_code == 200, response.text
    assert response.json()["graph_api_response"]["messages"][0]["id"] == "wamid.1"

    _, url_post, _, _ = fake_http_client.calls[-1]
    assert "/1234567890/messages" in url_post


def test_sin_token_de_servicio_es_rechazado(client, fake_http_client, canal_messenger, core_service_token):
    fake_http_client.core_get_response = FakeResponse(200, canal_a_json(canal_messenger))

    response = client.post("/messages/send", json=_body())
    assert response.status_code == 401


def test_token_de_servicio_incorrecto_es_rechazado(client, fake_http_client, canal_messenger, core_service_token):
    fake_http_client.core_get_response = FakeResponse(200, canal_a_json(canal_messenger))

    response = client.post("/messages/send", json=_body(), headers=_headers("no-es-el-token-correcto"))
    assert response.status_code == 401


def test_sin_core_service_token_configurado_se_niega_todo(client):
    from app.config import get_settings
    get_settings().core_service_token = ""

    response = client.post("/messages/send", json=_body(), headers=_headers("lo-que-sea"))
    assert response.status_code == 503


def test_canal_inexistente(client, fake_http_client, core_service_token):
    fake_http_client.core_get_response = FakeResponse(404)

    response = client.post("/messages/send", json=_body(), headers=_headers(core_service_token))
    assert response.status_code == 404


def test_canal_desactivado(client, fake_http_client, core_service_token):
    canal_inactivo = {
        "organization_id": 1, "tipo": "MESSENGER", "api_key": "x", "webhook_secret": "y",
        "activo": False, "telefono_id": "",
    }
    fake_http_client.core_get_response = FakeResponse(200, canal_inactivo)

    response = client.post("/messages/send", json=_body(), headers=_headers(core_service_token))
    assert response.status_code == 400


def test_canal_sin_soporte_de_envio(client, fake_http_client, core_service_token):
    canal_webchat = {
        "organization_id": 1, "tipo": "WEBCHAT", "api_key": "x", "webhook_secret": "",
        "activo": True, "telefono_id": "",
    }
    fake_http_client.core_get_response = FakeResponse(200, canal_webchat)

    response = client.post("/messages/send", json=_body(), headers=_headers(core_service_token))
    assert response.status_code == 400


def test_la_graph_api_rechaza_el_envio(client, fake_http_client, canal_messenger, core_service_token):
    fake_http_client.core_get_response = FakeResponse(200, canal_a_json(canal_messenger))
    fake_http_client.meta_response = FakeResponse(400, {"error": {"message": "Invalid OAuth access token"}})

    response = client.post("/messages/send", json=_body(), headers=_headers(core_service_token))
    assert response.status_code == 502
    assert "Invalid OAuth access token" in response.text
