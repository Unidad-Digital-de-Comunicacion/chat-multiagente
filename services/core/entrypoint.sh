#!/usr/bin/env bash
set -euo pipefail

: "${GUNICORN_WORKERS:=3}"
export GUNICORN_WORKERS
if [ "${GUNICORN_RELOAD:-false}" = "true" ]; then
    export GUNICORN_EXTRA_ARGS="--reload"
else
    export GUNICORN_EXTRA_ARGS=""
fi

echo "entrypoint: esperando a que Postgres acepte conexiones..."
python - <<'PYEOF'
import os
import sys
import time

import psycopg2

deadline = time.time() + 60
while time.time() < deadline:
    try:
        psycopg2.connect(
            host=os.environ["DB_HOST"],
            port=os.environ.get("DB_PORT", "5432"),
            dbname=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
        ).close()
        sys.exit(0)
    except psycopg2.OperationalError:
        time.sleep(1)
sys.exit("entrypoint: Postgres no respondió a tiempo")
PYEOF

echo "entrypoint: generando par de claves JWT (si no existen)..."
python manage.py generate_jwt_keys

echo "entrypoint: aplicando migraciones..."
python manage.py migrate --noinput

echo "entrypoint: recolectando estáticos..."
python manage.py collectstatic --noinput

echo "entrypoint: arrancando nginx + gunicorn (supervisord)..."
exec supervisord -c /etc/supervisor/conf.d/supervisord.conf
