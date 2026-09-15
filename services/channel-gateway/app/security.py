"""Verificación de webhooks de Meta — dos secretos distintos, no
intercambiables:

- `hub.verify_token` (handshake `GET`, una vez al suscribir el webhook): se
  compara contra `Canal.webhook_secret` de Core, uno por canal.
- `X-Hub-Signature-256` (firma de CADA `POST` entrante): HMAC-SHA256 del
  body crudo con `META_APP_SECRET`, uno solo para toda la plataforma (una
  única app de Meta) — por eso viene de `config.Settings`, no de Core."""
import hashlib
import hmac


def verificar_verify_token(hub_verify_token: str, webhook_secret: str) -> bool:
    return bool(webhook_secret) and hmac.compare_digest(hub_verify_token, webhook_secret)


def verificar_firma(raw_body: bytes, signature_header: str | None, app_secret: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    if not app_secret:
        return False
    firma_recibida = signature_header[len("sha256="):]
    firma_esperada = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(firma_recibida, firma_esperada)
