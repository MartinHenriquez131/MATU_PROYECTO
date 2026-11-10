#!/bin/sh
# MATU · Arranque de la base
#
# Crea los cuatro roles, les asigna contraseña, crea la base matu con matu_owner
# como dueño y habilita btree_gist. Se ejecuta una sola vez, con el superusuario.
#
# En Docker lo corre la imagen de PostgreSQL la primera vez que se crea el volumen.
# En el pipeline se corre a mano contra el servicio de PostgreSQL.
#
# Variables: MATU_OWNER_PASSWORD y MATU_APP_PASSWORD (obligatorias), MATU_SCHEDULER_PASSWORD y
# MATU_PUBLISHER_PASSWORD (opcionales, MATU-74: las conexiones de las tareas; sin ellas esos roles quedan sin
# contraseña y las tareas que los usan fallan con FaltaConexion), ROLES_SQL (ruta de 00_roles.sql). La conexión usa las variables estándar de psql
# (PGHOST, PGUSER, PGPASSWORD).
set -eu

: "${MATU_OWNER_PASSWORD:?Falta MATU_OWNER_PASSWORD}"
: "${MATU_APP_PASSWORD:?Falta MATU_APP_PASSWORD}"
ROLES_SQL="${ROLES_SQL:-/matu-db/00_roles.sql}"
SUPER="${POSTGRES_USER:-${PGUSER:-postgres}}"

PSQL="psql -v ON_ERROR_STOP=1 -q --username $SUPER"

$PSQL --dbname postgres -f "$ROLES_SQL"
$PSQL --dbname postgres \
  -v owner_pw="$MATU_OWNER_PASSWORD" -v app_pw="$MATU_APP_PASSWORD" <<'SQL'
ALTER ROLE matu_owner PASSWORD :'owner_pw';
ALTER ROLE matu_app   PASSWORD :'app_pw';
CREATE DATABASE matu OWNER matu_owner;
SQL
if [ -n "${MATU_SCHEDULER_PASSWORD:-}" ]; then
  $PSQL --dbname postgres -v pw="$MATU_SCHEDULER_PASSWORD" <<'SQL'
ALTER ROLE matu_scheduler PASSWORD :'pw';
SQL
fi
if [ -n "${MATU_PUBLISHER_PASSWORD:-}" ]; then
  $PSQL --dbname postgres -v pw="$MATU_PUBLISHER_PASSWORD" <<'SQL'
ALTER ROLE matu_publisher PASSWORD :'pw';
SQL
fi
$PSQL --dbname matu <<'SQL'
CREATE EXTENSION IF NOT EXISTS btree_gist;
ALTER SCHEMA public OWNER TO matu_owner;
SQL

echo "MATU: roles y base creados"
