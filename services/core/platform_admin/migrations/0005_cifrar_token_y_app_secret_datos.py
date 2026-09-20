"""Paso 2/3: cifra en el lugar `ServiceToken.token` y `MetaAppConfig.
app_secret` con la clave real (`settings.FIELD_ENCRYPTION_KEY`) — ANTES
de que la 0006 cambie la clase de estos dos campos a la que descifra
sola (si corriera después, leer estos valores ya intentaría descifrar
algo que en este punto todavía es texto plano). Se cifra "a mano" con
`cryptography.fernet` directo (no importando `common.encrypted_fields`)
para que esta migración quede autocontenida, mismo criterio que
`channels/migrations/0008_cifrar_api_key_datos.py`."""
from cryptography.fernet import Fernet

from django.conf import settings
from django.db import migrations


def _fernet():
    key = settings.FIELD_ENCRYPTION_KEY
    if not key:
        return None
    return Fernet(key.encode())


def cifrar(apps, schema_editor):
    fernet = _fernet()
    if not fernet:
        return

    ServiceToken = apps.get_model("platform_admin", "ServiceToken")
    for st in ServiceToken.objects.exclude(token=""):
        ServiceToken.objects.filter(pk=st.pk).update(token=fernet.encrypt(st.token.encode()).decode())

    MetaAppConfig = apps.get_model("platform_admin", "MetaAppConfig")
    for config in MetaAppConfig.objects.exclude(app_secret=""):
        MetaAppConfig.objects.filter(pk=config.pk).update(app_secret=fernet.encrypt(config.app_secret.encode()).decode())


def descifrar(apps, schema_editor):
    fernet = _fernet()
    if not fernet:
        return

    ServiceToken = apps.get_model("platform_admin", "ServiceToken")
    for st in ServiceToken.objects.exclude(token=""):
        ServiceToken.objects.filter(pk=st.pk).update(token=fernet.decrypt(st.token.encode()).decode())

    MetaAppConfig = apps.get_model("platform_admin", "MetaAppConfig")
    for config in MetaAppConfig.objects.exclude(app_secret=""):
        MetaAppConfig.objects.filter(pk=config.pk).update(app_secret=fernet.decrypt(config.app_secret.encode()).decode())


class Migration(migrations.Migration):

    dependencies = [
        ("platform_admin", "0004_ensanchar_token_y_app_secret"),
    ]

    operations = [
        migrations.RunPython(cifrar, descifrar),
    ]
