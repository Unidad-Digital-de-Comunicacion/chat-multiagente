import hashlib
import hmac

from app.security import verificar_firma, verificar_verify_token


def test_verify_token_correcto():
    assert verificar_verify_token("el-secreto", "el-secreto") is True


def test_verify_token_incorrecto():
    assert verificar_verify_token("otra-cosa", "el-secreto") is False


def test_verify_token_vacio_en_core_nunca_pasa():
    # Un canal sin webhook_secret cargado (no debería pasar en la práctica,
    # Core lo genera siempre al crear el canal) no debe poder "verificarse"
    # con un verify_token vacío.
    assert verificar_verify_token("", "") is False


def _firmar(body: bytes, secreto: str) -> str:
    return "sha256=" + hmac.new(secreto.encode(), body, hashlib.sha256).hexdigest()


def test_firma_correcta():
    body = b'{"object": "page"}'
    assert verificar_firma(body, _firmar(body, "app-secret"), "app-secret") is True


def test_firma_incorrecta():
    body = b'{"object": "page"}'
    assert verificar_firma(body, _firmar(body, "otro-secret"), "app-secret") is False


def test_body_modificado_invalida_la_firma():
    body_original = b'{"object": "page"}'
    firma = _firmar(body_original, "app-secret")
    body_modificado = b'{"object": "page-modificado"}'
    assert verificar_firma(body_modificado, firma, "app-secret") is False


def test_sin_header_de_firma():
    assert verificar_firma(b"da lo mismo", None, "app-secret") is False


def test_header_con_formato_invalido():
    assert verificar_firma(b"da lo mismo", "no-empieza-con-sha256=", "app-secret") is False


def test_sin_app_secret_configurado_nunca_pasa():
    body = b'{"object": "page"}'
    assert verificar_firma(body, _firmar(body, ""), "") is False
