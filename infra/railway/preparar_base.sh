#!/bin/sh
# MATU · Preparar la base gestionada de staging en Railway (MATU-25)
#
# Hace lo mismo que infra/postgres/init/10_matu.sh, pero se puede correr más de una vez:
#   - crea los cuatro roles de backend/db/00_roles.sql si no existen (ninguno SUPERUSER ni BYPASSRLS)
#   - fija las contraseñas de matu_owner, matu_app, matu_scheduler y matu_publisher desde el entorno
#     (las dos últimas desde MATU-74: los cron de las tareas se conectan con su propio rol)
#   - crea la base matu con matu_owner como dueño, si no existe
#   - habilita btree_gist y deja el esquema public a nombre de matu_owner
#
# No crea tablas: eso lo hace Alembic en el preDeployCommand de railway.json.
#
# Variables (nunca en el repositorio ni en el chat):
#   ADMIN_DATABASE_URL   URL del superusuario de la base de Railway. Desde un computador, la pública
#                        (DATABASE_PUBLIC_URL del servicio Postgres). Solo se usa aquí.
#   MATU_OWNER_PASSWORD  contraseña de matu_owner (la de MIGRATIONS_DATABASE_URL)
#   MATU_APP_PASSWORD    contraseña de matu_app (la de DATABASE_URL)
#   MATU_SCHEDULER_PASSWORD  contraseña de matu_scheduler (la de SCHEDULER_DATABASE_URL de los cron)
#   MATU_PUBLISHER_PASSWORD  contraseña de matu_publisher (la de PUBLISHER_DATABASE_URL del cron de avisos)
#   ROLES_SQL            ruta de 00_roles.sql. Por omisión, la del repositorio
#
# Uso, desde la raíz del repositorio:
#   ADMIN_DATABASE_URL=... MATU_OWNER_PASSWORD=... MATU_APP_PASSWORD=... MATU_SCHEDULER_PASSWORD=... \
#     MATU_PUBLISHER_PASSWORD=... sh infra/railway/preparar_base.sh
set -eu

: "${ADMIN_DATABASE_URL:?Falta ADMIN_DATABASE_URL (DATABASE_PUBLIC_URL del servicio Postgres de Railway)}"
: "${MATU_OWNER_PASSWORD:?Falta MATU_OWNER_PASSWORD}"
: "${MATU_APP_PASSWORD:?Falta MATU_APP_PASSWORD}"
: "${MATU_SCHEDULER_PASSWORD:?Falta MATU_SCHEDULER_PASSWORD}"
: "${MATU_PUBLISHER_PASSWORD:?Falta MATU_PUBLISHER_PASSWORD}"
AQUI=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROLES_SQL="${ROLES_SQL:-$AQUI/../../backend/db/00_roles.sql}"

# -X: sin el .psqlrc de quien lo corre. Córrelo en tu computador: la URL queda en la lista de procesos
PSQL="psql -v ON_ERROR_STOP=1 -q -X -d $ADMIN_DATABASE_URL"

# Cuántos de los cuatro roles ya existen: 0, se crean con 00_roles.sql; 4, se dejan; otro, se detiene
EXISTENTES=$($PSQL -At -c "SELECT count(*) FROM pg_roles
  WHERE rolname IN ('matu_owner', 'matu_app', 'matu_publisher', 'matu_scheduler')")
case "$EXISTENTES" in
  0) $PSQL -f "$ROLES_SQL"; echo "MATU: roles creados" ;;
  4) echo "MATU: los roles ya existían" ;;
  *) echo "MATU: hay $EXISTENTES de los 4 roles. Revisa a mano antes de seguir" >&2; exit 1 ;;
esac

# Ningún rol de MATU puede saltarse RLS (política 2), ni crear roles o bases, ni replicar. Si alguien lo cambió a mano, se detiene
PELIGROSOS=$($PSQL -At -c "SELECT count(*) FROM pg_roles
  WHERE rolname LIKE 'matu\_%' AND (rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb OR rolreplication)")
if [ "$PELIGROSOS" != "0" ]; then
  echo "MATU: un rol de MATU es SUPERUSER, BYPASSRLS, CREATEROLE, CREATEDB o REPLICATION. Corrígelo antes de seguir" >&2
  exit 1
fi

# Los roles de las tareas no heredan nada de otro rol (condición C7 de MATU-74)
MIEMBROS=$($PSQL -At -c "SELECT count(*) FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.member
  WHERE r.rolname IN ('matu_scheduler', 'matu_publisher')")
if [ "$MIEMBROS" != "0" ]; then
  echo "MATU: matu_scheduler o matu_publisher es miembro de otro rol. Corrígelo antes de seguir" >&2
  exit 1
fi

$PSQL -v owner_pw="$MATU_OWNER_PASSWORD" -v app_pw="$MATU_APP_PASSWORD" \
  -v scheduler_pw="$MATU_SCHEDULER_PASSWORD" -v publisher_pw="$MATU_PUBLISHER_PASSWORD" <<'SQL'
ALTER ROLE matu_owner     PASSWORD :'owner_pw';
ALTER ROLE matu_app       PASSWORD :'app_pw';
ALTER ROLE matu_scheduler PASSWORD :'scheduler_pw';
ALTER ROLE matu_publisher PASSWORD :'publisher_pw';
SELECT 'CREATE DATABASE matu OWNER matu_owner'
 WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'matu')\gexec
\connect matu
CREATE EXTENSION IF NOT EXISTS btree_gist;
ALTER SCHEMA public OWNER TO matu_owner;
SQL

echo "MATU: base matu lista, con btree_gist. Falta alembic upgrade head (lo corre el despliegue)"
