"""Cifra en el lugar el `api_key` de cada `Canal` existente ANTES de que la
próxima migración (`0009`) cambie el tipo de campo a `EncryptedTextField`
— el orden importa: si esto corriera DESPUÉS del cambio de tipo, leer
`canal.api_key` acá ya intentaría descifrar un valor que todavía está en
texto plano y reventaría con `InvalidToken`. Se cifra "a mano" con
`cryptography.fernet` directo (no importando `common.encrypted_fields`)
para que esta migración quede autocontenida y no dependa de que ese
módulo exista/no cambie en el futuro."""
from cryptography.fernet import Fernet

from django.conf import settings
from django.db import migrations


def cifrar(apps, schema_editor):
    Canal = apps.get_model("channels", "Canal")
    key = settings.FIELD_ENCRYPTION_KEY
    if not key:
        # Sin clave configurada no hay nada seguro que hacer acá — mejor
        # dejar los datos como estaban (la migración de esquema de abajo
        # fallaría igual de todos modos al intentar leer algo después) que
        # inventar una clave nueva a mitad de una migración.
        return
    fernet = Fernet(key.encode())
    for canal in Canal.objects.exclude(api_key=""):
        Canal.objects.filter(pk=canal.pk).update(api_key=fernet.encrypt(canal.api_key.encode()).decode())


def descifrar(apps, schema_editor):
    Canal = apps.get_model("channels", "Canal")
    key = settings.FIELD_ENCRYPTION_KEY
    if not key:
        return
    fernet = Fernet(key.encode())
    for canal in Canal.objects.exclude(api_key=""):
        Canal.objects.filter(pk=canal.pk).update(api_key=fernet.decrypt(canal.api_key.encode()).decode())


class Migration(migrations.Migration):

    dependencies = [
        ("channels", "0007_canal_waba_id"),
    ]

    operations = [
        migrations.RunPython(cifrar, descifrar),
    ]
