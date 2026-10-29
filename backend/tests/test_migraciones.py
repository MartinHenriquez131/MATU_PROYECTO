"""
MATU · Reversibilidad de la migración 0002 (ADR-027) contra PostgreSQL real.

Crea una base desechable, la lleva a 0001 con filas del modelo anterior (autorización con
margen y captura diferida), sube a head, verifica cómo se convirtieron, baja a 0001 y compara
el catálogo con el de antes: tablas, columnas, tipos, nulos, valores por omisión, CHECK,
claves, índices, políticas, RLS, triggers, funciones y permisos. La base se borra al final.

PostgreSQL no reordena columnas: la comparación es por nombre, no por posición.

Necesita MIGRATIONS_DATABASE_URL (Alembic como matu_owner) y MATU_TEST_DSN (superusuario, solo
para crear y borrar la base desechable). Sin MIGRATIONS_DATABASE_URL la prueba se salta.
"""

import os
import subprocess
import sys
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv
from psycopg.conninfo import make_conninfo
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND.parent / ".env")
DSN = os.environ.get("MATU_TEST_DSN", "host=localhost port=5432 user=postgres dbname=matu")
URL_MIGRACIONES = os.environ.get("MIGRATIONS_DATABASE_URL")
BASE = "matu_prueba_migraciones"

pytestmark = pytest.mark.skipif(not URL_MIGRACIONES, reason="MIGRATIONS_DATABASE_URL no está definida")

CATALOGO = {
    "columnas": """
        SELECT table_name, column_name, data_type, is_nullable, column_default
        FROM information_schema.columns WHERE table_schema = 'public' ORDER BY 1, 2""",
    "restricciones": """
        SELECT conrelid::regclass::text, conname, pg_get_constraintdef(oid)
        FROM pg_constraint WHERE connamespace = 'public'::regnamespace ORDER BY 1, 2""",
    "indices": "SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' ORDER BY 1, 2",
    "politicas": """
        SELECT tablename, policyname, permissive, roles::text, cmd, qual, with_check
        FROM pg_policies WHERE schemaname = 'public' ORDER BY 1, 2""",
    "rls": """
        SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class
        WHERE relnamespace = 'public'::regnamespace AND relkind = 'r' ORDER BY 1""",
    "triggers": """
        SELECT tgrelid::regclass::text, tgname, pg_get_triggerdef(oid)
        FROM pg_trigger WHERE NOT tgisinternal ORDER BY 1, 2""",
    "funciones": """
        SELECT p.oid::regprocedure::text, p.prosrc FROM pg_proc p
        WHERE p.pronamespace = 'public'::regnamespace
          AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = p.oid AND d.deptype = 'e')
        ORDER BY 1""",
    "permisos": """
        SELECT table_name, grantee, privilege_type FROM information_schema.role_table_grants
        WHERE table_schema = 'public' ORDER BY 1, 2, 3""",
    "permisos_columna": """
        SELECT table_name, column_name, grantee, privilege_type FROM information_schema.column_privileges
        WHERE table_schema = 'public' ORDER BY 1, 2, 3, 4""",
}

# Filas del modelo de 0001, sintéticas. Se insertan como superusuario (sin RLS).
G, U, P = ("00000000-0000-0000-0000-0000000000" + s for s in ("0a", "a1", "1a"))
CAT, PROD, COM, OF = ("00000000-0000-0000-0000-000000000" + s for s in ("c01", "f01", "4c1", "f11"))
PED_AUT, PED_CAP, PED_BOR = ("00000000-0000-0000-0000-0000000006" + s for s in ("a1", "a2", "a3"))
CAR_COMPLETO, CAR_REVERTIDO = ("00000000-0000-0000-0000-0000000007" + s for s in ("a1", "a2"))
PAR_AUT, PAR_REV = ("00000000-0000-0000-0000-0000000008" + s for s in ("a1", "a2"))

FILAS_0001 = f"""
INSERT INTO usuario (id, email, nombre, password_hash) VALUES ('{U}', 'a@correo.ejemplo', 'Persona A', 'h');
INSERT INTO grupo_familiar (id, nombre, creado_por) VALUES ('{G}', 'Familia A', '{U}');
INSERT INTO persona_cuidada (id, grupo_id, nombre, nombre_pila, nivel_apoyo)
    VALUES ('{P}', '{G}', 'Persona Cuidada', 'Persona', 'apoyo_total');
INSERT INTO categoria_cuidado (id, nombre) VALUES ('{CAT}', 'Higiene');
INSERT INTO producto (id, categoria_id, nombre, presentacion, unidad, unidades_por_envase)
    VALUES ('{PROD}', '{CAT}', 'Producto de prueba', 'x30', 'unidad', 30);
INSERT INTO comercio (id, razon_social, nombre_fantasia, rut, direccion, comuna)
    VALUES ('{COM}', 'Comercio Uno SpA', 'Comercio Uno', '76.000.000-1', 'Calle 1', 'Comuna');
INSERT INTO oferta (id, producto_id, comercio_id, precio_referencia) VALUES ('{OF}', '{PROD}', '{COM}', 12990);
INSERT INTO pedido (id, grupo_id, persona_cuidada_id, comercio_id, estado, total_estimado, total_autorizado,
                    total_real, destinatario_nombre_pila, creado_por) VALUES
 ('{PED_AUT}', '{G}', '{P}', '{COM}', 'autorizado',        25980, 29877, NULL,  'Persona', '{U}'),
 ('{PED_CAP}', '{G}', '{P}', '{COM}', 'captura_pendiente', 12990, 14938, 11990, 'Persona', '{U}'),
 ('{PED_BOR}', '{G}', '{P}', '{COM}', 'borrador',          12990, NULL,  NULL,  'Persona', '{U}');
INSERT INTO pedido_linea (pedido_id, oferta_id, producto_id, cantidad, precio_snapshot, precio_real, estado_linea)
VALUES ('{PED_AUT}', '{OF}', '{PROD}', 2, 12990, NULL, 'requiere_decision'),
       ('{PED_CAP}', '{OF}', '{PROD}', 1, 12990, 11990, 'sustituida');
INSERT INTO regla_sustitucion (pedido_id, producto_id, accion, producto_sustituto_id, precio_maximo) VALUES
 ('{PED_AUT}', '{PROD}', 'no_sustituir',        NULL,     NULL),
 ('{PED_CAP}', '{PROD}', 'producto_especifico', '{PROD}', 15000),
 ('{PED_BOR}', '{PROD}', 'consultar',           NULL,     NULL);
INSERT INTO cargo (id, pedido_id, monto_objetivo, monto_autorizado, monto_capturado, estado, recaudacion_expira_en)
VALUES ('{CAR_COMPLETO}',  '{PED_AUT}', 25980, 29877, 0, 'completo',  now()),
       ('{CAR_REVERTIDO}', '{PED_CAP}', 12990, 14938, 0, 'revertido', now());
INSERT INTO participacion (id, cargo_id, usuario_id, porcentaje_bp, monto_comprometido, monto_autorizado, estado)
VALUES ('{PAR_AUT}', '{CAR_COMPLETO}',  '{U}', 10000, 29877, 29877, 'autorizada'),
       ('{PAR_REV}', '{CAR_REVERTIDO}', '{U}', 10000, 14938, 14938, 'revertida');
INSERT INTO transaccion_pasarela (participacion_id, proveedor, tipo, buy_order, monto, idempotency_key) VALUES
 ('{PAR_AUT}', 'webpay_plus', 'autorizacion', 'MATU-P-0001', 29877, 'kp1'),
 ('{PAR_REV}', 'webpay_plus', 'reversa',      'MATU-P-0002', 14938, 'kp2');
"""


def _dsn(dbname: str) -> str:
    return make_conninfo(DSN, dbname=dbname)


@pytest.fixture
def base_desechable():
    with psycopg.connect(_dsn("postgres"), autocommit=True) as c:
        c.execute(f"DROP DATABASE IF EXISTS {BASE} WITH (FORCE)")
        c.execute(f"CREATE DATABASE {BASE} OWNER matu_owner")
    # Lo mismo que hace infra/postgres/init/10_matu.sh con la base matu
    with psycopg.connect(_dsn(BASE), autocommit=True) as c:
        c.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
        c.execute("ALTER SCHEMA public OWNER TO matu_owner")
    yield
    with psycopg.connect(_dsn("postgres"), autocommit=True) as c:
        c.execute(f"DROP DATABASE IF EXISTS {BASE} WITH (FORCE)")


def alembic(*args: str) -> None:
    assert URL_MIGRACIONES is not None
    url = make_url(URL_MIGRACIONES).set(database=BASE).render_as_string(hide_password=False)
    # Proceso aparte: el fileConfig de alembic.ini no debe reconfigurar los logs de esta sesión de pytest
    r = subprocess.run(
        [sys.executable, "-c", "from alembic.config import main; main()", *args],
        cwd=BACKEND, env={**os.environ, "MIGRATIONS_DATABASE_URL": url},
        capture_output=True, text=True, check=False,
    )
    assert r.returncode == 0, f"alembic {' '.join(args)} falló:\n{r.stderr[-4000:]}"


def catalogo() -> dict[str, list[tuple]]:
    with psycopg.connect(_dsn(BASE)) as c:
        return {nombre: c.execute(sql).fetchall() for nombre, sql in CATALOGO.items()}


def consultar(sql: str) -> list[tuple]:
    with psycopg.connect(_dsn(BASE)) as c:
        return c.execute(sql).fetchall()


@pytest.mark.rf("ADR-027")
def test_0002_sube_convierte_las_filas_y_baja_al_esquema_de_0001(base_desechable):
    alembic("upgrade", "0001")
    esquema_0001 = catalogo()
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute(FILAS_0001)

    # ---- sube: las filas del modelo anterior quedan en el ciclo del ADR-027
    alembic("upgrade", "head")
    assert catalogo() != esquema_0001
    pedidos = dict((r[0], r[1:]) for r in consultar(
        "SELECT id::text, estado, subtotal_productos, costo_envio, total, pagado_en IS NOT NULL FROM pedido"))
    assert pedidos[PED_AUT] == ("pagado", 29877, 0, 29877, True)
    assert pedidos[PED_CAP] == ("entregado", 11990, 0, 11990, True)
    assert pedidos[PED_BOR] == ("borrador", 12990, 0, 12990, False)
    assert sorted(consultar("SELECT estado_linea, precio_unitario FROM pedido_linea")) == [
        ("eliminada", 12990), ("faltante", 12990)]
    assert sorted(consultar("SELECT estado, monto_cobrado, monto_devuelto FROM cargo")) == [
        ("anulado", 14938, 14938), ("pagado", 29877, 0)]
    assert sorted(consultar("SELECT estado, monto_cobrado, monto_devuelto FROM participacion")) == [
        ("anulada", 14938, 14938), ("pagada", 29877, 0)]
    assert sorted(consultar("SELECT tipo FROM transaccion_pasarela")) == [("anulacion",), ("venta",)]
    # RF-21: no sustituir pasa a quitar; el resto, al mismo producto en otro comercio
    assert sorted(consultar("SELECT accion FROM regla_sustitucion")) == [
        ("otro_comercio",), ("otro_comercio",), ("quitar",)]
    # Lo pagado no se reabre (pedido_pagado_fijo)
    with pytest.raises(psycopg.errors.CheckViolation), psycopg.connect(_dsn(BASE)) as c:
        c.execute(f"UPDATE pedido SET estado = 'borrador', pagado_en = NULL WHERE id = '{PED_AUT}'")

    # ---- baja: el esquema vuelve a ser exactamente el de 0001, con las filas convertidas de vuelta
    alembic("downgrade", "0001")
    despues = catalogo()
    for parte, filas in esquema_0001.items():
        assert despues[parte] == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues[parte])}"
    assert sorted(consultar("SELECT estado, total_estimado, total_autorizado FROM pedido")) == [
        ("autorizado", 29877, 29877), ("borrador", 12990, None), ("entregado", 11990, 11990)]
    assert sorted(consultar("SELECT estado, monto_autorizado, monto_capturado FROM cargo")) == [
        ("capturado", 29877, 29877), ("revertido", 14938, 0)]
    assert sorted(consultar("SELECT tipo FROM transaccion_pasarela")) == [("autorizacion",), ("reversa",)]
    assert sorted(consultar("SELECT accion, producto_sustituto_id, precio_maximo FROM regla_sustitucion")) == [
        ("equivalente", None, None), ("equivalente", None, None), ("no_sustituir", None, None)]

    # ---- y vuelve a subir
    alembic("upgrade", "head")


# ---- 0003 (MATU-11): una clave de datos destruida no resucita

CLAVE_VIGENTE, CLAVE_DESTRUIDA = ("00000000-0000-0000-0000-0000000009" + s for s in ("a1", "a2"))
P2 = "00000000-0000-0000-0000-0000000000" + "1b"

FILAS_CLAVES = f"""
INSERT INTO usuario (id, email, nombre, password_hash) VALUES ('{U}', 'a@correo.ejemplo', 'Persona A', 'h');
INSERT INTO grupo_familiar (id, nombre, creado_por) VALUES ('{G}', 'Familia A', '{U}');
INSERT INTO persona_cuidada (id, grupo_id, nombre, nombre_pila, nivel_apoyo) VALUES
 ('{P}', '{G}', 'Persona Cuidada', 'Persona', 'apoyo_total'),
 ('{P2}', '{G}', 'Otra Persona', 'Otra', 'apoyo_parcial');
INSERT INTO clave_datos (id, grupo_id, persona_cuidada_id, dek_cifrada_con_kek, kek_version, destruida_en) VALUES
 ('{CLAVE_VIGENTE}', '{G}', '{P}', '\x01', 1, NULL),
 ('{CLAVE_DESTRUIDA}', '{G}', '{P2}', NULL, 1, now());
"""


def _permisos_clave_datos() -> set[str]:
    return {r[0] for r in consultar(
        "SELECT privilege_type FROM information_schema.role_table_grants"
        " WHERE table_name = 'clave_datos' AND grantee = 'matu_app'")}


def test_0003_fija_la_clave_destruida_y_baja_al_esquema_de_0002(base_desechable):
    alembic("upgrade", "0002")
    esquema_0002 = catalogo()
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute(FILAS_CLAVES)
    assert "DELETE" in _permisos_clave_datos()

    # ---- sube: matu_app pierde DELETE y la clave destruida queda fija; la vigente no cambia
    alembic("upgrade", "0003")
    assert _permisos_clave_datos() == {"SELECT", "INSERT", "UPDATE"}
    with pytest.raises(psycopg.errors.CheckViolation), psycopg.connect(_dsn(BASE)) as c:
        c.execute(f"UPDATE clave_datos SET dek_cifrada_con_kek = '\x02', destruida_en = NULL"
                  f" WHERE id = '{CLAVE_DESTRUIDA}'")
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute(f"UPDATE clave_datos SET kek_version = 2 WHERE id = '{CLAVE_VIGENTE}'")
    assert sorted(consultar("SELECT kek_version, destruida_en IS NULL FROM clave_datos")) == [(1, False), (2, True)]

    # ---- baja: el esquema vuelve a ser exactamente el de 0002, con las filas intactas
    alembic("downgrade", "0002")
    despues = catalogo()
    for parte, filas in esquema_0002.items():
        assert despues[parte] == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues[parte])}"
    assert consultar("SELECT count(*) FROM clave_datos") == [(2,)]

    # ---- y vuelve a subir
    alembic("upgrade", "head")


# ---- 0004 (MATU-18): el acceso de relevo guarda el nombre de pila de quien comparte

PLAN = "00000000-0000-0000-0000-0000000000" + "b1"
ACCESO = "00000000-0000-0000-0000-0000000000" + "c1"

FILAS_ACCESO = f"""
INSERT INTO usuario (id, email, nombre, password_hash) VALUES ('{U}', 'a@correo.ejemplo', 'Persona A', 'h');
INSERT INTO grupo_familiar (id, nombre, creado_por) VALUES ('{G}', 'Familia A', '{U}');
INSERT INTO persona_cuidada (id, grupo_id, nombre, nombre_pila, nivel_apoyo) VALUES
 ('{P}', '{G}', 'Persona Cuidada', 'Persona', 'apoyo_total');
INSERT INTO plan_cuidado (id, grupo_id, persona_cuidada_id) VALUES ('{PLAN}', '{G}', '{P}');
"""


def _insertar_acceso(nombre_comparte: str | None) -> None:
    columna, valor = ("", "") if nombre_comparte is None else (", nombre_pila_comparte", f", '{nombre_comparte}'")
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute(
            "INSERT INTO acceso_relevo (id, grupo_id, plan_id, otorgado_por, otorgado_a_nombre, otorgado_a_telefono,"
            f" nombre_pila_persona, secciones_permitidas, motivo, token_hash, pin_hash, expira_en,"
            f" relevo_informado_en{columna})"
            f" VALUES ('{ACCESO}', '{G}', '{PLAN}', '{U}', 'Relevo', '+56955550137', 'Persona', ARRAY['rutina'],"
            f" 'otro', sha256('t'), 'p', now() + interval '1 day', now(){valor})")


@pytest.mark.rf("RF-05")
def test_0004_agrega_el_nombre_de_quien_comparte_y_baja_al_esquema_de_0003(base_desechable):
    alembic("upgrade", "0003")
    esquema_0003 = catalogo()
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute(FILAS_ACCESO)

    # ---- sube: la columna es obligatoria y no admite un nombre vacío
    alembic("upgrade", "0004")
    with pytest.raises(psycopg.errors.NotNullViolation):
        _insertar_acceso(None)
    with pytest.raises(psycopg.errors.CheckViolation):
        _insertar_acceso("  ")
    _insertar_acceso("Persona")
    assert consultar("SELECT nombre_pila_comparte FROM acceso_relevo") == [("Persona",)]

    # ---- baja: sin filas de acceso, el esquema vuelve a ser exactamente el de 0003
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute("DELETE FROM acceso_relevo")
    alembic("downgrade", "0003")
    despues = catalogo()
    for parte, filas in esquema_0003.items():
        assert despues[parte] == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues[parte])}"

    # ---- y vuelve a subir
    alembic("upgrade", "head")


# ---- 0005 (MATU-14): quién lee la auditoría (decisión 36)


@pytest.mark.rf("RF-08")
def test_0005_reemplaza_la_lectura_de_auditoria_y_baja_al_esquema_de_0004(base_desechable):
    alembic("upgrade", "0004")
    esquema_0004 = catalogo()

    alembic("upgrade", "0005")
    politicas = dict(consultar(
        "SELECT policyname, cmd FROM pg_policies WHERE tablename = 'auditoria' ORDER BY 1"))
    assert politicas == {"auditoria_familia": "SELECT", "auditoria_insertar": "INSERT", "auditoria_relevo": "INSERT"}
    [(qual,)] = consultar("SELECT qual FROM pg_policies WHERE policyname = 'auditoria_familia'")
    assert "app_usuario()" in qual and "'admin'" in qual

    alembic("downgrade", "0004")
    despues = catalogo()
    for parte, filas in esquema_0004.items():
        assert despues[parte] == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues[parte])}"
    alembic("upgrade", "head")


# ---- 0006: el consentimiento es inalterable; solo se registra la revocación


@pytest.mark.rf("RF-01")
def test_0006_consentimiento_inalterable_y_baja_al_esquema_de_0005(base_desechable):
    alembic("upgrade", "0005")
    esquema_0005 = catalogo()

    alembic("upgrade", "0006")
    politicas = dict(consultar(
        "SELECT policyname, cmd FROM pg_policies WHERE tablename = 'consentimiento' ORDER BY 1"))
    assert politicas == {
        "consentimiento_familia_crear": "INSERT", "consentimiento_familia_leer": "SELECT",
        "consentimiento_familia_revocar": "UPDATE", "consentimiento_operacion": "SELECT"}
    permisos = {p for (p,) in consultar(
        "SELECT privilege_type FROM information_schema.role_table_grants"
        " WHERE table_name = 'consentimiento' AND grantee = 'matu_app'")}
    assert not {"UPDATE", "DELETE"} & permisos
    columnas = {c for (c,) in consultar(
        "SELECT column_name FROM information_schema.column_privileges WHERE table_name = 'consentimiento'"
        " AND grantee = 'matu_app' AND privilege_type = 'UPDATE'")}
    assert columnas == {"revocado_en"}
    disparadores = {t for (t,) in consultar(
        "SELECT tgname FROM pg_trigger WHERE tgrelid = 'consentimiento'::regclass AND NOT tgisinternal")}
    assert {"consentimiento_solo_revocacion", "consentimiento_sin_borrado"} <= disparadores

    alembic("downgrade", "0005")
    despues = catalogo()
    for parte, filas in esquema_0005.items():
        assert despues[parte] == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues[parte])}"
    alembic("upgrade", "head")


# ---- 0007 (MATU-19): revocado_en en indice_token, políticas del relevo y autorización vigente


@pytest.mark.rf("RF-06")
def test_0007_agrega_lo_del_relevo_y_baja_al_esquema_de_0006(base_desechable):
    alembic("upgrade", "0006")
    esquema_0006 = catalogo()

    alembic("upgrade", "0007")
    assert consultar(
        "SELECT data_type, is_nullable FROM information_schema.columns"
        " WHERE table_name = 'indice_token' AND column_name = 'revocado_en'"
    ) == [("timestamp with time zone", "YES")]
    politicas = dict(consultar("SELECT policyname, cmd FROM pg_policies WHERE tablename = 'acceso_relevo'"))
    assert politicas == {"acceso_familia": "ALL", "acceso_relevo_leer": "SELECT", "acceso_relevo_contar": "UPDATE"}
    [(definer, config, acl)] = consultar(
        "SELECT prosecdef, proconfig, proacl::text FROM pg_proc WHERE proname = 'relevo_autorizacion_vigente'")
    assert definer and config == ["search_path=pg_catalog, public, pg_temp"]
    assert "matu_app=X" in acl and "=X/" not in acl.replace("matu_app=X/", "").replace("matu_owner=X/", "")

    alembic("downgrade", "0006")
    despues = catalogo()
    for parte, filas in esquema_0006.items():
        assert despues[parte] == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues[parte])}"
    alembic("upgrade", "head")
