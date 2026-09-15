import secrets
import uuid

from django.db import migrations, models


def generar_valores_faltantes(apps, schema_editor):
    # Se agrega `uuid` como nullable/no-único primero (más abajo) para poder
    # poblar un valor DISTINTO por fila acá: Postgres no permite crear el
    # índice único del paso siguiente si todas las filas existentes
    # comparten el mismo default. `webhook_secret` no tiene esa restricción
    # pero se aprovecha el mismo RunPython para generarlo de una.
    Canal = apps.get_model("channels", "Canal")
    for canal in Canal.objects.all():
        actualizar = []
        if canal.uuid is None:
            canal.uuid = uuid.uuid4()
            actualizar.append("uuid")
        if not canal.webhook_secret:
            canal.webhook_secret = secrets.token_urlsafe(24)
            actualizar.append("webhook_secret")
        if actualizar:
            canal.save(update_fields=actualizar)


class Migration(migrations.Migration):

    dependencies = [
        ('channels', '0002_canal_ultimo_chequeo_at_canal_ultimo_chequeo_detalle_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='canal',
            name='uuid',
            # Nulo y sin `unique` en este paso: dos NULL no chocan contra un
            # índice único en Postgres, así que agregar la columna así no
            # rompe con las filas ya existentes — el paso 3 (`AlterField`)
            # recién ahí exige NOT NULL + único, una vez que el paso 2 ya
            # le puso un valor distinto a cada fila.
            field=models.UUIDField(null=True, editable=False),
        ),
        migrations.AddField(
            model_name='canal',
            name='webhook_secret',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.RunPython(generar_valores_faltantes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='canal',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
