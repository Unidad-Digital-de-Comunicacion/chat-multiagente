# Paso 1/3 de cifrar `ServiceToken.token`/`MetaAppConfig.app_secret` en
# reposo: sólo ENSANCHA las dos columnas a `text` (siguen siendo campos
# planos, sin cifrar todavía) — el texto cifrado con Fernet siempre es más
# largo que el original (base64 + IV + HMAC), y el `varchar(255)`/
# `varchar(128)` actuales se quedan cortos para escribirlo. Tiene que ir
# ANTES que la 0005 (datos): confirmado en vivo (`DataError: value too
# long for type character varying`) al intentar cifrar sin ensanchar
# primero. La 0006 (esquema) recién ahí cambia la CLASE de los dos campos
# a la que descifra sola.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('platform_admin', '0003_seed_meta_app_config_desde_env'),
    ]

    operations = [
        migrations.AlterField(
            model_name='servicetoken',
            name='token',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='metaappconfig',
            name='app_secret',
            field=models.TextField(blank=True),
        ),
    ]
