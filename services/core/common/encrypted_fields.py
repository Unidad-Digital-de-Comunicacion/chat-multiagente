"""Campo de Django que cifra al guardar y descifra al leer, transparente
para el resto del código — para credenciales que Core necesita poder
REUSAR en texto plano de verdad (mandarlas a Meta, firmar HMAC), a
diferencia de un secreto que sólo se compara y nunca se reenvía a nadie
(`platform_admin.models.ServiceToken.token_hash`, que va con hash en vez
de esto — un hash no sirve acá porque no se puede "desdeshashear").

Usa Fernet (AES-128-CBC + HMAC, ya autenticado — detecta manipulación, no
sólo cifra) de `cryptography`, que ya es dependencia directa del proyecto
(RS256 de los JWT la necesita) — no hace falta agregar ninguna librería
nueva. La clave (`settings.FIELD_ENCRYPTION_KEY`) nunca vive en la base.

Real en producción (2026-09-20): antes de esto, `Canal.api_key` y
`MetaAppConfig.app_secret` (tokens de página/app de Meta) se guardaban en
texto plano en la base — alguien con acceso de sólo lectura a Postgres
podía mandar mensajes por WhatsApp/Messenger/Instagram en nombre de
cualquier organización sin pasar por Core."""
from cryptography.fernet import Fernet, InvalidToken

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


def _fernet() -> Fernet:
    key = settings.FIELD_ENCRYPTION_KEY
    if not key:
        raise ImproperlyConfigured(
            "Falta FIELD_ENCRYPTION_KEY — hace falta para leer/escribir campos cifrados "
            "(Canal.api_key, MetaAppConfig.app_secret).",
        )
    return Fernet(key.encode())


class EncryptedTextField(models.TextField):
    """`TextField`, no `CharField` — el texto cifrado siempre es más largo
    que el original (base64 + IV + HMAC de Fernet), así que un
    `max_length` pensado para el valor plano quedaría corto."""

    def from_db_value(self, value, expression, connection):
        if not value:
            return value
        try:
            return _fernet().decrypt(value.encode()).decode()
        except InvalidToken as exc:
            # Dato que no es un token Fernet válido con la clave actual —
            # nunca debería pasar después de la migración de datos que
            # cifra lo existente ANTES de cambiar el tipo de campo. Fallar
            # visible en vez de devolver basura silenciosa (ej. binario
            # ilegible pasado como si fuera la api_key real).
            raise ValueError(
                "No se pudo descifrar el valor — ¿FIELD_ENCRYPTION_KEY correcta, o el dato "
                "todavía no pasó por la migración de datos?",
            ) from exc

    def get_prep_value(self, value):
        if not value:
            return value
        return _fernet().encrypt(value.encode()).decode()
