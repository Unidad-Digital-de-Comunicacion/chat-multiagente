"""Utilidades para exponer la clave pública de firma de JWT como JWKS
(RFC 7517), para que los servicios FastAPI la consuman sin compartir ningún
secreto (ver JWT_PUBLIC_KEY_URL en docker-compose.yml)."""
import base64

from cryptography.hazmat.primitives import serialization

KID = "core-1"


def _b64url_uint(number):
    byte_length = max((number.bit_length() + 7) // 8, 1)
    data = number.to_bytes(byte_length, "big")
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def public_key_to_jwk(public_key_pem: str) -> dict:
    public_key = serialization.load_pem_public_key(public_key_pem.encode())
    numbers = public_key.public_numbers()
    return {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": KID,
        "n": _b64url_uint(numbers.n),
        "e": _b64url_uint(numbers.e),
    }
