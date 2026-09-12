#!/usr/bin/env bash
# Se ejecuta una sola vez, la primera vez que se crea el volumen de datos de
# `db` (convención de docker-entrypoint-initdb.d de la imagen postgres).
# Crea un esquema por microservicio y el usuario de solo lectura de Analytics.
#
# Nota: POSTGRES_READONLY_PASSWORD se interpola directamente en el SQL (no
# hay forma simple de parametrizar CREATE ROLE), así que no debe contener
# comillas simples.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE SCHEMA IF NOT EXISTS core;
    CREATE SCHEMA IF NOT EXISTS channel_gateway;
    CREATE SCHEMA IF NOT EXISTS conversation_engine;
    CREATE SCHEMA IF NOT EXISTS operators_desk;
    CREATE SCHEMA IF NOT EXISTS analytics;
    CREATE SCHEMA IF NOT EXISTS webchat;
EOSQL

if [ -n "${POSTGRES_READONLY_USER:-}" ] && [ -n "${POSTGRES_READONLY_PASSWORD:-}" ]; then
    ya_existe=$(psql -tA --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
        -c "SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = '${POSTGRES_READONLY_USER}'")

    if [ "$ya_existe" != "1" ]; then
        psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
            -c "CREATE ROLE \"${POSTGRES_READONLY_USER}\" WITH LOGIN PASSWORD '${POSTGRES_READONLY_PASSWORD}'"
    fi

    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
        GRANT USAGE ON SCHEMA core, conversation_engine TO "${POSTGRES_READONLY_USER}";
        ALTER DEFAULT PRIVILEGES IN SCHEMA core GRANT SELECT ON TABLES TO "${POSTGRES_READONLY_USER}";
        ALTER DEFAULT PRIVILEGES IN SCHEMA conversation_engine GRANT SELECT ON TABLES TO "${POSTGRES_READONLY_USER}";
        GRANT SELECT ON ALL TABLES IN SCHEMA core TO "${POSTGRES_READONLY_USER}";
        GRANT SELECT ON ALL TABLES IN SCHEMA conversation_engine TO "${POSTGRES_READONLY_USER}";
EOSQL
else
    echo "init-schemas.sh: POSTGRES_READONLY_USER/PASSWORD no definidos, se omite el usuario de solo lectura." >&2
fi
