from app.config import get_settings


def _evento(**overrides):
    body = {"tipo": "mensaje_nuevo", "organization_id": 7, "conversacion_id": 501}
    body.update(overrides)
    return body


class TestInternalAuth:
    def test_sin_header_es_401(self, client, core_service_token):
        respuesta = client.post("/internal/eventos/", json=_evento())
        assert respuesta.status_code == 401

    def test_con_token_incorrecto_es_401(self, client, core_service_token):
        respuesta = client.post(
            "/internal/eventos/", json=_evento(), headers={"Authorization": "Service-Token no-es-el-correcto"},
        )
        assert respuesta.status_code == 401

    def test_con_esquema_incorrecto_es_401(self, client, core_service_token):
        respuesta = client.post(
            "/internal/eventos/", json=_evento(), headers={"Authorization": f"Bearer {core_service_token}"},
        )
        assert respuesta.status_code == 401

    def test_sin_token_configurado_del_lado_del_servicio_es_503(self, client):
        settings = get_settings()
        anterior = settings.core_service_token
        settings.core_service_token = ""
        try:
            respuesta = client.post(
                "/internal/eventos/", json=_evento(), headers={"Authorization": "Service-Token cualquiera"},
            )
            assert respuesta.status_code == 503
        finally:
            settings.core_service_token = anterior

    def test_con_token_correcto_pasa(self, client, core_service_token):
        respuesta = client.post(
            "/internal/eventos/", json=_evento(), headers={"Authorization": f"Service-Token {core_service_token}"},
        )
        assert respuesta.status_code == 200


class TestConexionesActivas:
    def test_requiere_bearer(self, client):
        respuesta = client.get("/organizations/7/conexiones-activas")
        assert respuesta.status_code == 401

    def test_no_deja_ver_las_conexiones_de_otra_organizacion(self, client, hacer_token):
        token = hacer_token(org_id=7)
        respuesta = client.get("/organizations/99/conexiones-activas", headers={"Authorization": f"Bearer {token}"})
        assert respuesta.status_code == 403

    def test_sin_nadie_conectado_da_cero(self, client, hacer_token):
        token = hacer_token(org_id=7)
        respuesta = client.get("/organizations/7/conexiones-activas", headers={"Authorization": f"Bearer {token}"})
        assert respuesta.status_code == 200
        assert respuesta.json() == {"conectados": 0}

    def test_cuenta_las_conexiones_activas_de_esa_organizacion(self, client, hacer_token):
        token_ws = hacer_token(org_id=7, user_id=1)
        token_http = hacer_token(org_id=7, user_id=2)
        with client.websocket_connect(f"/ws/operador/{token_ws}"):
            respuesta = client.get("/organizations/7/conexiones-activas", headers={"Authorization": f"Bearer {token_http}"})
            assert respuesta.json() == {"conectados": 1}
