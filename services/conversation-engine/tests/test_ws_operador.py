import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import WebSocketDisconnect


def _evento(**overrides):
    body = {"tipo": "mensaje_nuevo", "organization_id": 7, "conversacion_id": 501}
    body.update(overrides)
    return body


def _headers(token):
    return {"Authorization": f"Service-Token {token}"}


class TestConexionYAutenticacion:
    def test_token_invalido_cierra_la_conexion(self, client):
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws/operador/esto-no-es-un-jwt"):
                pass

    def test_token_firmado_con_otra_clave_es_rechazado(self, client, hacer_token):
        otra_clave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = pyjwt.encode(
            {"user_id": 1, "org_id": 7, "grupos": [], "email": "x@test.com"}, otra_clave, algorithm="RS256",
        )
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(f"/ws/operador/{token}"):
                pass

    def test_token_vencido_es_rechazado(self, client, hacer_token):
        token = hacer_token(exp_en_segundos=-10)
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(f"/ws/operador/{token}"):
                pass

    def test_token_valido_conecta(self, client, hacer_token):
        token = hacer_token(org_id=7)
        with client.websocket_connect(f"/ws/operador/{token}"):
            pass  # no levanta -> conectó


class TestEntregaDeEventos:
    def test_recibe_un_evento_de_su_propia_organizacion(self, client, hacer_token, core_service_token):
        token = hacer_token(org_id=7)
        with client.websocket_connect(f"/ws/operador/{token}") as websocket:
            respuesta = client.post("/internal/eventos/", json=_evento(organization_id=7), headers=_headers(core_service_token))
            assert respuesta.status_code == 200
            assert respuesta.json() == {"entregados": 1}
            mensaje = websocket.receive_json()
            assert mensaje == {
                "tipo": "mensaje_nuevo", "organization_id": 7, "conversacion_id": 501,
                "team_id": None, "operador_id": None,
            }

    def test_no_recibe_eventos_de_otra_organizacion(self, client, hacer_token, core_service_token):
        token = hacer_token(org_id=7)
        with client.websocket_connect(f"/ws/operador/{token}") as websocket:
            client.post("/internal/eventos/", json=_evento(organization_id=99, conversacion_id=1), headers=_headers(core_service_token))
            # Uno propio después, para confirmar que la conexión seguía viva
            # y sólo se saltó el de la otra organización (no una cuestión de
            # timing del test).
            client.post("/internal/eventos/", json=_evento(organization_id=7, conversacion_id=2), headers=_headers(core_service_token))
            mensaje = websocket.receive_json()
            assert mensaje["conversacion_id"] == 2

    def test_dos_operadores_de_la_misma_organizacion_reciben_el_mismo_evento(self, client, hacer_token, core_service_token):
        token_a = hacer_token(org_id=7, user_id=1)
        token_b = hacer_token(org_id=7, user_id=2)
        with client.websocket_connect(f"/ws/operador/{token_a}") as ws_a:
            with client.websocket_connect(f"/ws/operador/{token_b}") as ws_b:
                respuesta = client.post("/internal/eventos/", json=_evento(organization_id=7), headers=_headers(core_service_token))
                assert respuesta.json() == {"entregados": 2}
                assert ws_a.receive_json()["conversacion_id"] == 501
                assert ws_b.receive_json()["conversacion_id"] == 501

    def test_sin_nadie_conectado_entregados_es_cero(self, client, core_service_token):
        respuesta = client.post("/internal/eventos/", json=_evento(), headers=_headers(core_service_token))
        assert respuesta.status_code == 200
        assert respuesta.json() == {"entregados": 0}
