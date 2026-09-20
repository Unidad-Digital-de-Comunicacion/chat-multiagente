"""Siembra la fila única de `MetaAppConfig` (pk=1) con lo que hoy vive en
`META_APP_ID`/`META_APP_SECRET` del entorno — a propósito lee `os.environ`
directo, no `django.conf.settings` (evita depender del estado de settings
en el momento de correr la migración, mismo criterio que cualquier otra
`RunPython` de este proyecto). Sin esto, pasar a que Core sea la fuente de
verdad real (en vez de la variable de entorno) perdería en silencio las
credenciales ya cargadas y confirmadas funcionando en producción
(2026-09-20)."""
import os

from django.db import migrations


def sembrar(apps, schema_editor):
    MetaAppConfig = apps.get_model("platform_admin", "MetaAppConfig")
    MetaAppConfig.objects.get_or_create(
        pk=1,
        defaults={
            "app_id": os.environ.get("META_APP_ID", ""),
            "app_secret": os.environ.get("META_APP_SECRET", ""),
        },
    )


def revertir(apps, schema_editor):
    MetaAppConfig = apps.get_model("platform_admin", "MetaAppConfig")
    MetaAppConfig.objects.filter(pk=1).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("platform_admin", "0002_metaappconfig"),
    ]

    operations = [
        migrations.RunPython(sembrar, revertir),
    ]
