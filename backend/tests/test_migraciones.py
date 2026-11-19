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
import secrets
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from dotenv import load_dotenv
from psycopg import sql
from psycopg.conninfo import make_conninfo
from sqlalchemy.engine import make_url

from tests.proteccion_base import nombre_de_la_base

BACKEND = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND.parent / ".env")
# MATU-94: sin valor por omisión (antes, dbname=matu). La base desechable BASE se crea desde la de origen, que
# tests/conftest.py exige que sea de pruebas
DSN = os.environ.get("MATU_TEST_DSN", "")
URL_MIGRACIONES = os.environ.get("MIGRATIONS_DATABASE_URL")
# La base desechable. MATU_BASE_MIGRACIONES (MATU-62) fuerza un nombre. Por omisión lleva el nombre de la de origen
# y termina en _test. Antes era una sola, matu_prueba_migraciones, para todas las copias del repositorio en el mismo
# servidor, y dos corridas a la vez (wt94 y wt62, el 11-11) se la borraban una a la otra. MATU-94 le puso el nombre de
# la base de origen, que todavía choca si dos corridas usan la misma (el QA y el desarrollo sobre matu_wt55). MATU-79:
# además el pid y un sufijo aleatorio, uno por corrida, dentro de los 63 caracteres de un nombre de PostgreSQL
SUFIJO_CORRIDA = f"{os.getpid()}_{secrets.token_hex(3)}"
BASE = os.environ.get("MATU_BASE_MIGRACIONES") or (
    f"{(nombre_de_la_base(DSN) or 'matu')[:32]}_mig_{SUFIJO_CORRIDA}_test".lower()
)

pytestmark = pytest.mark.skipif(
    not URL_MIGRACIONES or not DSN, reason="MIGRATIONS_DATABASE_URL o MATU_TEST_DSN no está definida"
)

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


def _borrar_base(nombre: str) -> None:
    with psycopg.connect(_dsn("postgres"), autocommit=True) as c:
        c.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(nombre)))


def _existe_base(nombre: str) -> bool:
    with psycopg.connect(_dsn("postgres")) as c:
        return c.execute("SELECT 1 FROM pg_database WHERE datname = %s", (nombre,)).fetchone() is not None


@contextmanager
def _base_temporal(nombre: str) -> Iterator[None]:
    """Crea la base desechable y la borra al salir, también si la prueba falla o si falla su preparación (MATU-79).
    Antes de crearla borra una que haya quedado con el mismo nombre, que solo puede ser de esta misma corrida."""
    _borrar_base(nombre)
    try:
        with psycopg.connect(_dsn("postgres"), autocommit=True) as c:
            c.execute(sql.SQL("CREATE DATABASE {} OWNER matu_owner").format(sql.Identifier(nombre)))
        # Lo mismo que hace infra/postgres/init/10_matu.sh con la base matu
        with psycopg.connect(_dsn(nombre), autocommit=True) as c:
            c.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
            c.execute("ALTER SCHEMA public OWNER TO matu_owner")
        yield
    finally:
        _borrar_base(nombre)


@pytest.fixture
def base_desechable():
    with _base_temporal(BASE):
        yield


def test_la_base_desechable_es_unica_por_corrida_y_se_borra_aunque_la_prueba_falle():
    """MATU-79: el nombre lleva el pid y un sufijo aleatorio, y la base se borra aunque la prueba lance un error."""
    if not os.environ.get("MATU_BASE_MIGRACIONES"):
        assert BASE != "matu_prueba_migraciones"
        assert BASE.endswith(f"_mig_{SUFIJO_CORRIDA}_test") and str(os.getpid()) in BASE
        assert len(BASE) <= 63
    # Una base propia de esta prueba, para no tocar BASE
    nombre = f"{BASE[:40]}_{secrets.token_hex(4)}_test"
    with pytest.raises(RuntimeError, match="la prueba falló"), _base_temporal(nombre):
        assert _existe_base(nombre)
        raise RuntimeError("la prueba falló")
    assert not _existe_base(nombre)


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


# ---- 0008 (MATU-38): motivo 'dispositivo', operación acotada, conservación y auditoria.detalle


@pytest.mark.rf("RF-37")
def test_0008_acota_operacion_y_baja_al_esquema_de_0007(base_desechable):
    alembic("upgrade", "0007")
    esquema_0007 = catalogo()

    alembic("upgrade", "0008")
    politicas = dict(consultar(
        "SELECT policyname, cmd FROM pg_policies WHERE tablename IN ('sesion_refresh', 'dispositivo')"))
    assert "sesion_operacion" not in politicas and "dispositivo_operacion" not in politicas
    assert politicas["sesion_conservacion_borrar"] == "DELETE"
    assert politicas["dispositivo_conservacion_borrar"] == "DELETE"
    # Las políticas de conservación son solo de matu_owner, el dueño de la función
    roles = dict(consultar(
        "SELECT policyname, roles::text FROM pg_policies WHERE policyname LIKE '%conservacion%'"))
    assert set(roles.values()) == {"{matu_owner}"}
    [(definer, config, acl)] = consultar(
        "SELECT prosecdef, proconfig, proacl::text FROM pg_proc WHERE proname = 'iam_conservar'")
    assert definer and config == ["search_path=pg_catalog, public, pg_temp"]
    assert "matu_app=X" in acl and "=X/" not in acl.replace("matu_app=X/", "").replace("matu_owner=X/", "")
    [(definicion,)] = consultar(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'sesion_refresh_motivo_revocacion_check'")
    assert "'dispositivo'" in definicion
    assert consultar(
        "SELECT data_type FROM information_schema.columns WHERE table_name = 'auditoria' AND column_name = 'detalle'"
    ) == [("jsonb",)]

    alembic("downgrade", "0007")
    despues = catalogo()
    for parte, filas in esquema_0007.items():
        assert despues[parte] == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues[parte])}"
    alembic("upgrade", "head")


# ---- 0009 (MATU-36): versión y autor del perfil, CHECK de nombre, escritura por rol y conservación


@pytest.mark.rf("RF-10")
def test_0009_perfil_de_consumo_y_baja_al_esquema_de_0008(base_desechable):
    alembic("upgrade", "0008")
    esquema_0008 = catalogo()

    alembic("upgrade", "0009")
    politicas = dict(consultar("SELECT policyname, cmd FROM pg_policies WHERE tablename = 'perfil_consumo'"))
    assert "perfil_familia" not in politicas
    assert politicas["perfil_leer"] == "SELECT"
    assert (politicas["perfil_crear"], politicas["perfil_editar"], politicas["perfil_borrar"]) == (
        "INSERT", "UPDATE", "DELETE")
    roles = dict(consultar(
        "SELECT policyname, roles::text FROM pg_policies WHERE policyname LIKE 'perfil_conservacion%'"))
    assert set(roles.values()) == {"{matu_owner}"}
    [(definer, config, acl)] = consultar(
        "SELECT prosecdef, proconfig, proacl::text FROM pg_proc WHERE proname = 'consumo_conservar'")
    assert definer and config == ["search_path=pg_catalog, public, pg_temp"]
    assert "matu_app=X" in acl and "=X/" not in acl.replace("matu_app=X/", "").replace("matu_owner=X/", "")
    columnas = dict(consultar(
        "SELECT column_name, column_default FROM information_schema.columns WHERE table_name = 'perfil_consumo'"
        " AND column_name IN ('version', 'actualizado_por')"))
    assert columnas == {"version": "1", "actualizado_por": None}
    restricciones = dict(consultar(
        "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = 'perfil_consumo'::regclass"))
    assert "<>" in restricciones["perfil_consumo_producto"]
    assert "60" in restricciones["perfil_consumo_nombre_libre"]

    alembic("downgrade", "0008")
    despues = catalogo()
    for parte, filas in esquema_0008.items():
        assert despues[parte] == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues[parte])}"
    alembic("upgrade", "head")


# ---- 0010 (MATU-45): la familia que ve el plan lee las aperturas del relevo


@pytest.mark.rf("RF-08")
def test_0010_agrega_la_lectura_de_aperturas_y_baja_al_esquema_de_0009(base_desechable):
    alembic("upgrade", "0009")
    esquema_0009 = catalogo()

    alembic("upgrade", "0010")
    politicas = dict(consultar("SELECT policyname, cmd FROM pg_policies WHERE tablename = 'auditoria'"))
    assert politicas["auditoria_aperturas_relevo"] == "SELECT"
    [(qual,)] = consultar("SELECT qual FROM pg_policies WHERE policyname = 'auditoria_aperturas_relevo'")
    assert "app_puede_ver_plan()" in qual and "'relevo'" in qual and "relevo.canje" not in qual
    for accion in ("relevo.presentar", "relevo.abrir", "relevo.pin_incorrecto", "relevo.bloqueo"):
        assert accion in qual

    alembic("downgrade", "0009")
    despues = catalogo()
    for parte, filas in esquema_0009.items():
        assert despues[parte] == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues[parte])}"
    alembic("upgrade", "head")


# ---- 0011 (MATU-37): alertas y reposiciones con políticas por operación, transiciones y conservación


@pytest.mark.rf("RF-12")
def test_0011_alertas_y_reposiciones_y_baja_al_esquema_de_0010(base_desechable):
    alembic("upgrade", "0010")
    esquema_0010 = catalogo()

    alembic("upgrade", "0011")
    politicas = dict(consultar(
        "SELECT policyname, cmd FROM pg_policies WHERE tablename IN ('alerta_quiebre', 'reposicion')"))
    assert "alerta_hereda" not in politicas and "reposicion_hereda" not in politicas
    assert politicas["alerta_leer"] == "SELECT" and politicas["reposicion_leer"] == "SELECT"
    assert {politicas[p] for p in ("alerta_materializar", "alerta_cerrar_sin_aviso", "reposicion_declarar",
                                   "reposicion_pedido")} == {"INSERT"}
    assert {politicas[p] for p in ("alerta_notificar", "alerta_cerrar")} == {"UPDATE"}
    # Sin DELETE para matu_app: solo la conservación, de matu_owner
    borrar = consultar("SELECT policyname, roles::text FROM pg_policies WHERE cmd = 'DELETE'"
                       " AND tablename IN ('alerta_quiebre', 'reposicion')")
    assert borrar == [("alerta_conservacion_borrar", "{matu_owner}")]
    [(definer, acl)] = consultar("SELECT prosecdef, proacl::text FROM pg_proc WHERE proname = 'quiebre_conservar'")
    assert definer and "matu_app=X" in acl
    assert consultar("SELECT tgname FROM pg_trigger WHERE tgname = 'alerta_transicion'") == [("alerta_transicion",)]

    alembic("downgrade", "0010")
    despues = catalogo()
    for parte, filas in esquema_0010.items():
        assert despues[parte] == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues[parte])}"
    alembic("upgrade", "head")


# ---- 0012 (MATU-57): celular verificado, su canal y el trigger que lo limpia al cambiar el número


@pytest.mark.rf("RF-37")
def test_0012_celular_verificado_y_baja_al_esquema_de_0011(base_desechable):
    alembic("upgrade", "0011")
    esquema_0011 = catalogo()

    alembic("upgrade", "0012")
    columnas = dict(consultar(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'usuario'"
        " AND column_name IN ('celular_verificado_en', 'celular_canal')"))
    assert columnas == {"celular_verificado_en": "timestamp with time zone", "celular_canal": "text"}
    with psycopg.connect(_dsn(BASE), autocommit=True) as c:
        c.execute(
            "INSERT INTO usuario (id, email, nombre, password_hash, telefono, celular_verificado_en)"
            " VALUES (%s, 'a@correo.ejemplo', 'Persona A', 'h', '+56900000001', now())", (U,))
        c.execute("UPDATE usuario SET nombre = 'Persona B' WHERE id = %s", (U,))
        assert c.execute("SELECT celular_verificado_en IS NOT NULL FROM usuario").fetchone() == (True,)
        c.execute("UPDATE usuario SET telefono = '+56900000002' WHERE id = %s", (U,))
        assert c.execute("SELECT celular_verificado_en IS NULL, celular_canal FROM usuario").fetchone() == (True, "sms")
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute("UPDATE usuario SET celular_canal = 'paloma'")
        c.execute("DELETE FROM usuario")

    alembic("downgrade", "0011")
    despues = catalogo()
    for parte, filas in esquema_0011.items():
        assert despues[parte] == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues[parte])}"
    alembic("upgrade", "head")


# ---- 0013 (MATU-50): secciones complementarias, creado_en, lo que ve el relevo y el detalle de la auditoría

_FILAS_0013 = r"""
INSERT INTO usuario (id, email, nombre, password_hash) VALUES ('{u}', 'b@correo.ejemplo', 'Persona B', 'h');
INSERT INTO grupo_familiar (id, nombre, creado_por) VALUES ('{g}', 'Familia B', '{u}');
INSERT INTO persona_cuidada (id, grupo_id, nombre, nombre_pila, nivel_apoyo)
    VALUES ('{p}', '{g}', 'Persona Cuidada', 'Persona', 'apoyo_total');
INSERT INTO plan_cuidado (id, grupo_id, persona_cuidada_id) VALUES ('{plan}', '{g}', '{p}');
INSERT INTO plan_seccion (plan_id, tipo, contenido_cifrado, nonce, tag_auth, kek_version)
    VALUES ('{plan}', 'remedios', '\xcc', '\x0000000000000000000013a1', '\x00000000000000000000000000000000', 1);
"""


@pytest.mark.rf("RF-03")
def test_0013_secciones_complementarias_y_baja_al_esquema_de_0012(base_desechable):
    alembic("upgrade", "0012")
    esquema_0012 = catalogo()

    alembic("upgrade", "0013")
    restricciones = dict(consultar(
        "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint"
        " WHERE conname IN ('plan_seccion_tipo_check', 'acceso_relevo_secciones_permitidas_check',"
        " 'auditoria_detalle_acotado')"))
    for nombre in ("plan_seccion_tipo_check", "acceso_relevo_secciones_permitidas_check"):
        for tipo in ("quien_es", "comunicacion", "remedios", "horarios", "actividades"):
            assert f"'{tipo}'" in restricciones[nombre], (nombre, tipo)
    assert "secciones" in restricciones["auditoria_detalle_acotado"]
    assert "NOT VALID" not in restricciones["auditoria_detalle_acotado"]
    assert consultar(
        "SELECT is_nullable, column_default FROM information_schema.columns"
        " WHERE table_name = 'plan_seccion' AND column_name = 'creado_en'"
    ) == [("NO", "now()")]
    [(qual,)] = consultar("SELECT qual FROM pg_policies WHERE policyname = 'seccion_relevo'")
    assert "creado_en" in qual
    assert consultar("SELECT tgname FROM pg_trigger WHERE tgname = 'plan_seccion_creado_fijo'") == [
        ("plan_seccion_creado_fijo",)]
    # Decisión 102: lectura y escritura separadas; escribir exige app_escribe_plan()
    politicas = dict(consultar(
        "SELECT policyname, cmd FROM pg_policies WHERE tablename = 'plan_seccion' AND policyname <> 'seccion_relevo'"))
    assert politicas == {"seccion_leer": "SELECT", "seccion_crear": "INSERT", "seccion_editar": "UPDATE",
                         "seccion_borrar": "DELETE"}
    for nombre, columna in (("seccion_crear", "with_check"), ("seccion_editar", "qual"), ("seccion_borrar", "qual")):
        [(expresion,)] = consultar(f"SELECT {columna} FROM pg_policies WHERE policyname = '{nombre}'")
        assert "app_escribe_plan()" in expresion, nombre
    # Decisión 103: plan_cuidado sin DELETE para matu_app, ni política ni permiso
    politicas = dict(consultar(
        "SELECT policyname, cmd FROM pg_policies WHERE tablename = 'plan_cuidado' AND policyname <> 'plan_relevo'"))
    assert politicas == {"plan_leer": "SELECT", "plan_crear": "INSERT", "plan_editar": "UPDATE"}
    assert consultar(
        "SELECT privilege_type FROM information_schema.role_table_grants"
        " WHERE table_name = 'plan_cuidado' AND grantee = 'matu_app' AND privilege_type = 'DELETE'") == []

    alembic("downgrade", "0012")
    despues = catalogo()
    for parte, filas in esquema_0012.items():
        assert despues[parte] == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues[parte])}"
    alembic("upgrade", "head")


@pytest.mark.rf("RF-03")
def test_0013_no_baja_si_quedan_secciones_nuevas_y_conserva_la_auditoria(base_desechable):
    """El downgrade no borra datos sin aviso: con una sección remedios se detiene. La auditoría no se
    toca: con detalles de secciones, el CHECK de la 0008 vuelve como NOT VALID."""
    alembic("upgrade", "0013")
    ids = {"u": "00000000-0000-0000-0000-0000000013a1", "g": "00000000-0000-0000-0000-0000000013a2",
           "p": "00000000-0000-0000-0000-0000000013a3", "plan": "00000000-0000-0000-0000-0000000013a4"}
    with psycopg.connect(_dsn(BASE), autocommit=True) as c:
        c.execute(_FILAS_0013.format(**ids))
        c.execute(
            "INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, detalle)"
            " VALUES (%s, 'usuario', %s, 'plan.quitar_seccion', 'plan_seccion', '{\"seccion\": \"remedios\"}')",
            (ids["g"], ids["u"]),
        )
    with pytest.raises(AssertionError, match="no borra datos"):
        alembic("downgrade", "0012")
    assert consultar("SELECT count(*) FROM plan_seccion WHERE tipo = 'remedios'") == [(1,)]

    with psycopg.connect(_dsn(BASE), autocommit=True) as c:
        c.execute("DELETE FROM plan_seccion WHERE tipo = 'remedios'")
    alembic("downgrade", "0012")
    [(definicion,)] = consultar(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'auditoria_detalle_acotado'")
    assert definicion.endswith("NOT VALID") and "secciones" not in definicion
    assert consultar("SELECT detalle FROM auditoria") == [({"seccion": "remedios"},)]
    alembic("upgrade", "head")


# ---- 0014 (MATU-41): avisos, dispositivo para el sistema, publicador del outbox y conservación de los fallidos


@pytest.mark.rf("RF-39")
def test_0014_avisos_y_outbox_y_baja_al_esquema_de_0013(base_desechable):
    alembic("upgrade", "0013")
    esquema_0013 = catalogo()

    alembic("upgrade", "0014")
    politicas = dict(consultar("SELECT policyname, cmd FROM pg_policies WHERE tablename = 'dispositivo'"))
    assert politicas["dispositivo_sistema_leer"] == "SELECT"
    assert politicas["dispositivo_sistema_expirar"] == "UPDATE"
    funciones = dict(consultar(
        "SELECT proname, prosecdef FROM pg_proc WHERE proname IN"
        " ('outbox_tomar', 'outbox_publicado', 'outbox_reintentar', 'outbox_posponer')"))
    assert funciones == dict.fromkeys(("outbox_tomar", "outbox_publicado", "outbox_reintentar", "outbox_posponer"),
                                      True)
    for (acl,) in consultar("SELECT proacl::text FROM pg_proc WHERE proname LIKE 'outbox_%'"):
        entradas = acl.strip("{}").split(",")
        # EXECUTE para matu_app y nunca para PUBLIC (la entrada sin rol: "=X/matu_owner")
        assert "matu_app=X/matu_owner" in entradas and not any(e.startswith("=") for e in entradas)
    [(cuerpo,)] = consultar("SELECT prosrc FROM pg_proc WHERE proname = 'quiebre_conservar'")
    assert "fallido_en" in cuerpo and "evento_consumido" in cuerpo
    assert consultar("SELECT conname FROM pg_constraint WHERE conname = 'notificacion_error'") == [
        ("notificacion_error",)]

    alembic("downgrade", "0013")
    despues = catalogo()
    for parte, filas in esquema_0013.items():
        assert despues[parte] == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues[parte])}"
    alembic("upgrade", "head")


# ---- 0015 (MATU-60): unidades por envase en el perfil de consumo, sin cambiar RLS


@pytest.mark.rf("RF-15")
def test_0015_unidades_por_envase_y_baja_al_esquema_de_0014(base_desechable):
    alembic("upgrade", "0014")
    esquema_0014 = catalogo()
    politicas_0014 = [f for f in esquema_0014["politicas"] if f[0] == "perfil_consumo"]

    alembic("upgrade", "0015")
    assert consultar(
        "SELECT data_type, is_nullable, column_default FROM information_schema.columns"
        " WHERE table_name = 'perfil_consumo' AND column_name = 'unidades_por_envase'") == [("integer", "YES", None)]
    [(definicion,)] = consultar(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'perfil_consumo_envase'")
    assert "IS NULL" in definicion and ">= 1" in definicion and "<= 10000" in definicion
    # RLS no cambia: las mismas políticas, el mismo FORCE y los mismos permisos de tabla
    despues = catalogo()
    assert [f for f in despues["politicas"] if f[0] == "perfil_consumo"] == politicas_0014
    assert despues["rls"] == esquema_0014["rls"] and despues["permisos"] == esquema_0014["permisos"]
    # El CHECK rechaza 0 y 10.001 y admite NULL, 1 y 10.000
    ids = {"u": "00000000-0000-0000-0000-0000000015a1", "g": "00000000-0000-0000-0000-0000000015a2",
           "p": "00000000-0000-0000-0000-0000000015a3", "pc": "00000000-0000-0000-0000-0000000015a4"}
    with psycopg.connect(_dsn(BASE), autocommit=True) as c:
        c.execute(f"""
            INSERT INTO usuario (id, email, nombre, password_hash) VALUES ('{ids['u']}', 'a15@example.com', 'A', 'h');
            INSERT INTO grupo_familiar (id, nombre, creado_por) VALUES ('{ids['g']}', 'Familia 15', '{ids['u']}');
            INSERT INTO persona_cuidada (id, grupo_id, nombre, nombre_pila, nivel_apoyo)
                VALUES ('{ids['p']}', '{ids['g']}', 'Persona Quince', 'Persona', 'apoyo_total');
            INSERT INTO perfil_consumo (id, grupo_id, persona_cuidada_id, nombre_libre, tasa_unidades, stock_unidades,
                                        stock_medido_en, fecha_quiebre_estimada)
                VALUES ('{ids['pc']}', '{ids['g']}', '{ids['p']}', 'Toallitas', 4, 24, current_date, current_date + 6);
        """)
        for valor in ("NULL", "1", "10000"):
            c.execute(f"UPDATE perfil_consumo SET unidades_por_envase = {valor} WHERE id = '{ids['pc']}'")
        for valor in ("0", "10001"):
            with pytest.raises(psycopg.errors.CheckViolation):
                c.execute(f"UPDATE perfil_consumo SET unidades_por_envase = {valor} WHERE id = '{ids['pc']}'")

    alembic("downgrade", "0014")
    despues = catalogo()
    for parte, filas in esquema_0014.items():
        assert despues[parte] == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues[parte])}"
    # El perfil sigue, sin la columna
    assert consultar(f"SELECT nombre_libre FROM perfil_consumo WHERE id = '{ids['pc']}'") == [("Toallitas",)]
    alembic("upgrade", "head")


# ---- 0016 (MATU-44): el motivo de la revocación, la barrera por rol y la destrucción a los 90 días


@pytest.mark.rf("RF-02")
def test_0016_retiro_con_motivo_y_baja_al_esquema_de_0015(base_desechable):
    alembic("upgrade", "0015")
    esquema_0015 = catalogo()
    ids = {"u": "00000000-0000-0000-0000-0000000016a1", "g": "00000000-0000-0000-0000-0000000016a2",
           "p": "00000000-0000-0000-0000-0000000016a3", "c1": "00000000-0000-0000-0000-0000000016a4",
           "c2": "00000000-0000-0000-0000-0000000016a5"}
    with psycopg.connect(_dsn(BASE), autocommit=True) as c:
        c.execute(f"""
            INSERT INTO usuario (id, email, nombre, password_hash) VALUES ('{ids['u']}', 'a16@example.com', 'A', 'h');
            INSERT INTO grupo_familiar (id, nombre, creado_por) VALUES ('{ids['g']}', 'Familia 16', '{ids['u']}');
            INSERT INTO persona_cuidada (id, grupo_id, nombre, nombre_pila, nivel_apoyo)
                VALUES ('{ids['p']}', '{ids['g']}', 'Persona Dieciséis', 'Persona', 'apoyo_total');
            INSERT INTO consentimiento (id, grupo_id, persona_cuidada_id, usuario_id, calidad_otorgante, finalidad,
                                        version_politica, evidencia, revocado_en)
                VALUES ('{ids['c1']}', '{ids['g']}', '{ids['p']}', '{ids['u']}', 'titular', 'plan_cuidado',
                        '0.9', '{{}}', now() - interval '1 day'),
                       ('{ids['c2']}', '{ids['g']}', '{ids['p']}', '{ids['u']}', 'titular', 'plan_cuidado',
                        '0.9', '{{}}', NULL);
        """)

    alembic("upgrade", "0016")
    # La revocación anterior quedó como retiro, y la vigente sin motivo
    assert dict(consultar("SELECT id::text, revocacion_motivo FROM consentimiento ORDER BY 1")) == {
        ids["c1"]: "retiro", ids["c2"]: None}
    restricciones = {n for (n,) in consultar(
        "SELECT conname FROM pg_constraint WHERE conrelid = 'consentimiento'::regclass")}
    assert {"consentimiento_revocacion_motivo", "consentimiento_revocacion_completa"} <= restricciones
    columnas = {c for (c,) in consultar(
        "SELECT column_name FROM information_schema.column_privileges WHERE table_name = 'consentimiento'"
        " AND grantee = 'matu_app' AND privilege_type = 'UPDATE'")}
    assert columnas == {"revocado_en", "revocacion_motivo"}
    [(condicion,)] = consultar(
        "SELECT qual FROM pg_policies WHERE policyname = 'consentimiento_familia_revocar'")
    assert "app_retira_autorizacion" in condicion
    assert consultar("SELECT relforcerowsecurity FROM pg_class WHERE relname = 'consentimiento'") == [(True,)]
    funciones = {f for (f,) in consultar("SELECT proname FROM pg_proc WHERE proname = 'plan_destruir_claves'")}
    assert funciones == {"plan_destruir_claves"}
    # P8: una sola clave no destruida por persona, y la nueva solo tras una autorización nueva
    [(indice,)] = consultar("SELECT indexdef FROM pg_indexes WHERE indexname = 'clave_datos_vigente_uq'")
    assert "UNIQUE" in indice and "destruida_en IS NULL" in indice
    assert consultar("SELECT conname FROM pg_constraint WHERE conname = 'clave_datos_persona_cuidada_id_key'") == []
    assert consultar("SELECT tgname FROM pg_trigger WHERE tgname = 'clave_datos_nueva_tras_autorizacion'") != []

    alembic("downgrade", "0015")
    despues = catalogo()
    for parte, filas in esquema_0015.items():
        assert despues[parte] == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues[parte])}"
    alembic("upgrade", "head")


# ---- 0017 (MATU-51): la conservación de las compras declaradas a los 90 días


@pytest.mark.rf("RF-11")
def test_0017_conservar_compras_y_baja_al_esquema_de_0016(base_desechable):
    alembic("upgrade", "0016")
    esquema_0016 = catalogo()

    alembic("upgrade", "0017")
    [(definer, acl, resultado)] = consultar(
        "SELECT prosecdef, proacl::text, pg_get_function_result(oid) FROM pg_proc WHERE proname = 'quiebre_conservar'")
    entradas = acl.strip("{}").split(",")
    assert definer and "matu_app=X/matu_owner" in entradas and not any(e.startswith("=") for e in entradas)
    assert "reposiciones integer" in resultado
    [(cuerpo,)] = consultar("SELECT prosrc FROM pg_proc WHERE proname = 'quiebre_conservar'")
    assert "origen = 'declarada'" in cuerpo and "registrada_en <= limite_alertas" in cuerpo
    assert "fallido_en" in cuerpo and "evento_consumido" in cuerpo  # lo de la 0014 sigue
    politicas = dict(consultar("SELECT policyname, cmd || ' ' || roles::text FROM pg_policies"
                               " WHERE tablename = 'reposicion'"))
    assert politicas["reposicion_conservacion"] == "SELECT {matu_owner}"
    assert politicas["reposicion_conservacion_borrar"] == "DELETE {matu_owner}"
    # Lo de la familia y del sistema no cambia (decisión C: reposicion_pedido igual)
    assert {politicas[p] for p in ("reposicion_declarar", "reposicion_pedido")} == {"INSERT {public}"}

    alembic("downgrade", "0016")
    despues = catalogo()
    for parte, filas in esquema_0016.items():
        assert despues[parte] == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues[parte])}"
    alembic("upgrade", "head")


# ---- 0018 (MATU-72): el borrado de la persona, con su marca, su motivo y la barrera por rol


@pytest.mark.rf("RF-01")
def test_0018_borrar_persona_y_baja_al_esquema_de_0017(base_desechable):
    alembic("upgrade", "0017")
    esquema_0017 = catalogo()

    alembic("upgrade", "0018")
    [(motivo,)] = consultar("SELECT pg_get_constraintdef(oid) FROM pg_constraint"
                            " WHERE conname = 'consentimiento_revocacion_motivo'")
    assert "'borrado'" in motivo and "'retiro'" in motivo and "'renovacion'" in motivo
    columnas = dict(consultar("SELECT column_name, is_nullable FROM information_schema.columns"
                              " WHERE table_name = 'persona_cuidada'"))
    assert columnas["datos_borrados_en"] == "YES" and columnas["nivel_apoyo"] == "YES"
    restricciones = {r[0] for r in consultar("SELECT conname FROM pg_constraint"
                                            " WHERE conrelid = 'persona_cuidada'::regclass")}
    assert {"persona_cuidada_nivel_apoyo_presente", "persona_cuidada_borrada"} <= restricciones
    disparadores = consultar("SELECT tgname FROM pg_trigger WHERE tgname = 'persona_borrada_fija'")
    assert disparadores == [("persona_borrada_fija",)]
    politicas = dict(consultar("SELECT policyname, cmd FROM pg_policies WHERE tablename = 'persona_cuidada'"))
    assert politicas == {"persona_familia_leer": "SELECT", "persona_familia_crear": "INSERT",
                         "persona_familia_editar": "UPDATE", "persona_familia_borrar": "DELETE",
                         "persona_operacion": "SELECT"}
    escritura = consultar("SELECT qual, with_check FROM pg_policies WHERE policyname = 'persona_familia_editar'")
    assert all("app_retira_autorizacion" in (parte or "") for parte in escritura[0])

    # Con una persona borrada, el downgrade se detiene en vez de perder la marca
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute(f"INSERT INTO usuario (id, email, nombre, password_hash) VALUES ('{U}', 'a@correo.ejemplo',"
                  " 'Persona A', 'h')")
        c.execute(f"INSERT INTO grupo_familiar (id, nombre, creado_por) VALUES ('{G}', 'Familia A', '{U}')")
        c.execute(f"INSERT INTO persona_cuidada (id, grupo_id, nombre, nombre_pila, nivel_apoyo, eliminado_en,"
                  f" datos_borrados_en) VALUES ('{P}', '{G}', 'borrada', 'borrada', NULL, now(), now())")
    with pytest.raises(AssertionError, match="persona"):
        alembic("downgrade", "0017")
    assert consultar("SELECT count(*) FROM persona_cuidada WHERE datos_borrados_en IS NOT NULL") == [(1,)]
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute(f"DELETE FROM persona_cuidada WHERE id = '{P}'")

    alembic("downgrade", "0017")
    despues = catalogo()
    for parte, filas in esquema_0017.items():
        assert despues[parte] == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues[parte])}"
    alembic("upgrade", "head")


# ---- 0019 (MATU-59): el precio exacto con IVA, el stock por oferta y el retracto por producto


@pytest.mark.rf("RF-20")
def test_0019_precio_stock_y_retracto_y_baja_al_esquema_de_0018(base_desechable):
    alembic("upgrade", "0018")
    esquema_0018 = catalogo()
    ids = {"cat": "00000000-0000-0000-0000-0000000019c1", "prod": "00000000-0000-0000-0000-0000000019f1",
           "com": "00000000-0000-0000-0000-0000000019a1", "of": "00000000-0000-0000-0000-0000000019b1"}
    with psycopg.connect(_dsn(BASE), autocommit=True) as c:
        c.execute(f"""
            INSERT INTO categoria_cuidado (id, nombre) VALUES ('{ids['cat']}', 'Categoría 19');
            INSERT INTO producto (id, categoria_id, nombre, presentacion, unidad, unidades_por_envase)
                VALUES ('{ids['prod']}', '{ids['cat']}', 'Producto 19', 'Caja de 30 unidades', 'unidad', 30);
            INSERT INTO comercio (id, razon_social, nombre_fantasia, rut, direccion, comuna)
                VALUES ('{ids['com']}', 'Comercio 19 (ficticio)', 'Comercio 19', '77.777.719-0', 'Calle 19', 'Ñuñoa');
            INSERT INTO oferta (id, producto_id, comercio_id, precio_referencia)
                VALUES ('{ids['of']}', '{ids['prod']}', '{ids['com']}', 12990);
        """)

    alembic("upgrade", "0019")
    columnas = {(t, c): (tipo, nulo, defecto) for t, c, tipo, nulo, defecto in consultar(
        "SELECT table_name, column_name, data_type, is_nullable, column_default FROM information_schema.columns"
        " WHERE table_name IN ('oferta', 'producto')")}
    assert ("oferta", "precio_referencia") not in columnas
    assert columnas[("oferta", "precio")] == ("bigint", "NO", None)
    assert columnas[("oferta", "stock")] == ("integer", "NO", "0")
    assert columnas[("producto", "retracto_pierde_al_abrir")] == ("boolean", "NO", "false")
    restricciones = dict(consultar("SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint"
                                   " WHERE conrelid = 'oferta'::regclass AND contype = 'c'"))
    assert restricciones == {"oferta_precio_check": "CHECK ((precio > 0))",
                             "oferta_stock_check": "CHECK ((stock >= 0))"}
    [(comentario,)] = consultar("SELECT col_description('oferta'::regclass, attnum) FROM pg_attribute"
                                " WHERE attrelid = 'oferta'::regclass AND attname = 'precio'")
    assert comentario.startswith("Precio exacto en pesos enteros, con IVA") and "ADR-011" not in comentario
    # La fila de antes conserva su precio, sin stock, y el producto sin pérdida del retracto
    assert consultar(f"SELECT precio, stock FROM oferta WHERE id = '{ids['of']}'") == [(12990, 0)]
    assert consultar(f"SELECT retracto_pierde_al_abrir FROM producto WHERE id = '{ids['prod']}'") == [(False,)]
    despues = catalogo()
    # RLS y permisos de tabla no cambian (los de columna son los de la tabla, también para las columnas nuevas)
    for parte in ("politicas", "rls", "permisos", "triggers", "funciones"):
        assert despues[parte] == esquema_0018[parte], parte
    with psycopg.connect(_dsn(BASE), autocommit=True) as c:
        for cambio in ("precio = 0", "stock = -1"):
            with pytest.raises(psycopg.errors.CheckViolation):
                c.execute(f"UPDATE oferta SET {cambio} WHERE id = '{ids['of']}'")
        c.execute(f"UPDATE oferta SET stock = 5, precio = 13990 WHERE id = '{ids['of']}'")

    alembic("downgrade", "0018")
    despues = catalogo()
    for parte, filas in esquema_0018.items():
        assert despues[parte] == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues[parte])}"
    # El precio vuelve a precio_referencia con su valor; el stock se pierde
    assert consultar(f"SELECT precio_referencia FROM oferta WHERE id = '{ids['of']}'") == [(13990,)]
    alembic("upgrade", "head")


# ---- 0020 (MATU-47 y MATU-66): permisos de matu_app acotados y RLS por operación y por rol


def _privilegios(tabla: str) -> set[str]:
    return {p for (p,) in consultar("SELECT privilege_type FROM information_schema.role_table_grants"
                                    f" WHERE table_name = '{tabla}' AND grantee = 'matu_app'")}


def _columnas_con(tabla: str, privilegio: str) -> set[str]:
    return {c for (c,) in consultar("SELECT column_name FROM information_schema.column_privileges"
                                    f" WHERE table_name = '{tabla}' AND grantee = 'matu_app'"
                                    f" AND privilege_type = '{privilegio}'")}


@pytest.mark.rf("RF-05")
def test_0020_acota_permisos_y_politicas_y_baja_al_esquema_de_0019(base_desechable):
    alembic("upgrade", "0019")
    esquema_0019 = catalogo()
    del_dueno = [p for p in esquema_0019["politicas"] if p[3] == "{matu_owner}"]

    alembic("upgrade", "0020")
    # MATU-47: indice_token con SELECT e INSERT, UPDATE solo de revocado_en y sin DELETE
    assert _privilegios("indice_token") == {"SELECT", "INSERT"}
    assert _columnas_con("indice_token", "UPDATE") == {"revocado_en"}
    disparadores = {t for (t,) in consultar("SELECT tgname FROM pg_trigger WHERE tgname LIKE '%vida_fija'")}
    assert disparadores == {"indice_token_vida_fija", "acceso_relevo_vida_fija"}
    # MATU-66: ninguna política FOR ALL en acceso_relevo, clave_datos ni usuario_operacion
    politicas = {(t, n): c for t, n, c in consultar(
        "SELECT tablename, policyname, cmd FROM pg_policies"
        " WHERE tablename IN ('acceso_relevo', 'clave_datos', 'usuario') AND 'matu_owner' <> ALL (roles)")}
    assert politicas == {
        ("acceso_relevo", "acceso_familia_leer"): "SELECT", ("acceso_relevo", "acceso_familia_crear"): "INSERT",
        ("acceso_relevo", "acceso_familia_cortar"): "UPDATE", ("acceso_relevo", "acceso_relevo_leer"): "SELECT",
        ("acceso_relevo", "acceso_relevo_contar"): "UPDATE",
        ("clave_datos", "clave_familia_leer"): "SELECT", ("clave_datos", "clave_familia_crear"): "INSERT",
        ("clave_datos", "clave_familia_destruir"): "UPDATE", ("clave_datos", "clave_relevo"): "SELECT",
        ("usuario", "usuario_propio_leer"): "SELECT", ("usuario", "usuario_propio_crear"): "INSERT",
        ("usuario", "usuario_propio_editar"): "UPDATE", ("usuario", "usuario_comiembro"): "SELECT",
        ("usuario", "usuario_operacion_leer"): "SELECT",
    }
    # Sin DELETE en acceso_relevo ni en usuario, y la cuenta solo cambia lo que la app cambia
    assert _privilegios("acceso_relevo") == {"SELECT", "INSERT"}
    assert _privilegios("usuario") == {"INSERT"}
    assert _columnas_con("usuario", "UPDATE") == {
        "password_hash", "telefono", "celular_verificado_en", "celular_canal", "actualizado_en"}
    assert _columnas_con("acceso_relevo", "UPDATE") == {
        "revocado_en", "nombre_pila_persona", "pin_intentos_fallidos", "usos", "ultimo_uso_en"}
    [(crear,)] = consultar("SELECT with_check FROM pg_policies WHERE policyname = 'consentimiento_familia_crear'")
    assert "app_retira_autorizacion" in crear
    # password_hash y mfa_secreto_cifrado: sin SELECT para matu_app; el login usa iam_credencial
    legibles = _columnas_con("usuario", "SELECT")
    assert "password_hash" not in legibles and "mfa_secreto_cifrado" not in legibles
    assert {"email", "telefono", "estado"} <= legibles
    [(definer, config, acl)] = consultar(
        "SELECT prosecdef, proconfig, proacl::text FROM pg_proc WHERE proname = 'iam_credencial'")
    assert definer and config == ["search_path=pg_catalog, public, pg_temp"]
    assert "matu_app=X" in acl and "=X/" not in acl.replace("matu_app=X/", "").replace("matu_owner=X/", "")
    # Condición 4: las políticas TO matu_owner no cambian
    despues = catalogo()
    assert [p for p in despues["politicas"] if p[3] == "{matu_owner}"] == del_dueno

    alembic("downgrade", "0019")
    despues = catalogo()
    for parte, filas in esquema_0019.items():
        assert despues[parte] == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues[parte])}"
    assert consultar("SELECT count(*) FROM pg_proc WHERE proname IN ('iam_credencial', 'token_vida_fija')") == [(0,)]
    alembic("upgrade", "head")


# ---- 0021 (MATU-75): la aceptación de la política al crear la cuenta


@pytest.mark.rf("RF-37")
def test_0021_aceptacion_politica_y_baja_al_esquema_de_0020(base_desechable):
    alembic("upgrade", "0020")
    esquema_0020 = catalogo()
    del_dueno = [p for p in esquema_0020["politicas"] if p[3] == "{matu_owner}"]
    # Una cuenta anterior a MATU-75 queda sin registro: la migración no rellena nada (D2)
    with psycopg.connect(_dsn(BASE), autocommit=True) as c:
        c.execute("INSERT INTO usuario (id, email, nombre, password_hash) VALUES (%s, 'a@correo.ejemplo', 'A', 'h')",
                  (U,))

    alembic("upgrade", "0021")
    assert consultar("SELECT count(*) FROM aceptacion_politica") == [(0,)]
    assert consultar("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'aceptacion_politica'"
                     ) == [(True, True)]
    politicas = {(n, c, r) for n, c, r in consultar(
        "SELECT policyname, cmd, roles::text FROM pg_policies WHERE tablename = 'aceptacion_politica'")}
    assert politicas == {("aceptacion_propia_leer", "SELECT", "{public}"),
                         ("aceptacion_propia_crear", "INSERT", "{public}"),
                         ("aceptacion_operacion_leer", "SELECT", "{public}")}
    assert _privilegios("aceptacion_politica") == {"SELECT", "INSERT"}
    # Sin ON DELETE CASCADE: la aceptación no cae con la cuenta (CL-49)
    [(definicion,)] = consultar("SELECT pg_get_constraintdef(oid) FROM pg_constraint"
                                " WHERE conrelid = 'aceptacion_politica'::regclass AND contype = 'f'")
    assert "CASCADE" not in definicion
    assert consultar("SELECT tgname FROM pg_trigger WHERE tgrelid = 'aceptacion_politica'::regclass"
                     " AND NOT tgisinternal") == [("aceptacion_politica_inalterable",)]
    # Lo que dejó la 0020 no cambia
    despues = catalogo()
    assert [p for p in despues["politicas"] if p[3] == "{matu_owner}"] == del_dueno
    assert [p for p in despues["politicas"] if p[0] != "aceptacion_politica"] == esquema_0020["politicas"]

    alembic("downgrade", "0020")
    despues = catalogo()
    for parte, filas in esquema_0020.items():
        assert despues[parte] == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues[parte])}"
    alembic("upgrade", "head")


# ---- 0022 (MATU-74, H2 y C4): las funciones de las tareas con sus roles y operación sin los avisos

FUNCIONES_0022 = {
    "plan_destruir_claves": "matu_scheduler", "consumo_conservar": "matu_scheduler",
    "iam_conservar": "matu_scheduler", "quiebre_conservar": "matu_scheduler",
    "outbox_tomar": "matu_publisher", "outbox_publicado": "matu_publisher",
    "outbox_reintentar": "matu_publisher", "outbox_posponer": "matu_publisher",
}


def _acl_funciones() -> dict[str, set[str]]:
    nombres = ", ".join(f"'{f}'" for f in FUNCIONES_0022)
    filas = consultar(f"SELECT proname, proacl::text FROM pg_proc WHERE proname IN ({nombres})")
    return {nombre: set(acl.strip("{}").split(",")) for nombre, acl in filas}


def _tablas_de(rol: str) -> set[tuple[str, str]]:
    return {(t, p) for t, p in consultar("SELECT table_name, privilege_type FROM information_schema.role_table_grants"
                                         f" WHERE table_schema = 'public' AND grantee = '{rol}'")}


@pytest.mark.rf("RF-02")
@pytest.mark.rf("RF-39")
def test_0022_roles_de_las_tareas_y_baja_al_esquema_de_0021(base_desechable):
    alembic("upgrade", "0021")
    esquema_0021, acl_0021 = catalogo(), _acl_funciones()
    assert _tablas_de("matu_publisher") == {("evento_outbox", "SELECT"), ("evento_outbox", "UPDATE"),
                                            ("evento_consumido", "SELECT"), ("evento_consumido", "INSERT")}

    alembic("upgrade", "0022")
    politicas = {n: (c, r) for n, c, r in consultar(
        "SELECT policyname, cmd, roles::text FROM pg_policies WHERE tablename = 'notificacion'")}
    assert "notificacion_operacion" not in politicas
    assert politicas["notificacion_conservacion"] == ("SELECT", "{matu_owner}")
    assert politicas["notificacion_conservacion_borrar"] == ("DELETE", "{matu_owner}")
    for nombre, entradas in _acl_funciones().items():
        rol = FUNCIONES_0022[nombre]
        assert f"{rol}=X/matu_owner" in entradas, nombre
        assert not any(e.startswith(("matu_app=", "=")) for e in entradas), (nombre, entradas)
        assert len(entradas) == 2, (nombre, entradas)  # el dueño y el rol de la tarea
    assert _tablas_de("matu_publisher") == set()
    # Lo demás no cambia: ni el resto de las políticas ni los permisos de matu_app sobre tablas
    despues = catalogo()
    assert [p for p in despues["politicas"] if p[0] != "notificacion"] == [
        p for p in esquema_0021["politicas"] if p[0] != "notificacion"]
    assert despues["permisos"] == [g for g in esquema_0021["permisos"] if g[1] != "matu_publisher"]

    alembic("downgrade", "0021")
    despues = catalogo()
    for parte, filas in esquema_0021.items():
        assert despues[parte] == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues[parte])}"
    assert _acl_funciones() == acl_0021
    alembic("upgrade", "head")


# ---- 0024 (MATU-62): el pago con Webpay Plus

TABLAS_DEL_PAGO = ("cargo", "participacion", "transaccion_pasarela")
FUNCIONES_0024 = {"pagos_por_conciliar": "matu_scheduler", "pago_resolver_venta": "matu_app"}

# Filas de la 0023: un pedido pagado con su cobro (con la respuesta de Transbank guardada y unos últimos 4 que no son
# cifras, que la 0024 vacía) y un pedido sin pagar. Como superusuario
G24, U24, P24, P24B = ("00000000-0000-0000-0000-0000000024" + s for s in ("0a", "a1", "1a", "1b"))
PED24, PED24B, CAR24, PAR24 = ("00000000-0000-0000-0000-0000000024" + s for s in ("d1", "d2", "c1", "e1"))
FILAS_0023 = f"""
INSERT INTO usuario (id, email, nombre, password_hash) VALUES ('{U24}', 'a24@correo.ejemplo', 'Persona A', 'h');
INSERT INTO grupo_familiar (id, nombre, creado_por) VALUES ('{G24}', 'Familia A', '{U24}');
INSERT INTO persona_cuidada (id, grupo_id, nombre, nombre_pila, nivel_apoyo) VALUES
 ('{P24}', '{G24}', 'Persona Cuidada', 'Persona', 'apoyo_total'), ('{P24B}', '{G24}', 'Otra', 'Otra', 'apoyo_total');
INSERT INTO pedido (id, grupo_id, persona_cuidada_id, estado, subtotal_productos, costo_envio, total,
                    total_confirmado_en, total_vence_en, creado_por) VALUES
 ('{PED24}', '{G24}', '{P24}', 'total_confirmado', 12990, 2990, 15980, now(), now() + interval '15 minutes', '{U24}'),
 ('{PED24B}', '{G24}', '{P24B}', 'borrador', 0, 0, 0, NULL, NULL, '{U24}');
UPDATE pedido SET estado = 'pagado', pagado_en = now(), condiciones_version = '0.1', condiciones_aceptadas_en = now(),
                  condiciones_huella = repeat('a', 64) WHERE id = '{PED24}';
INSERT INTO cargo (id, pedido_id, estado, monto_cobrado) VALUES ('{CAR24}', '{PED24}', 'pagado', 15980);
INSERT INTO participacion (id, cargo_id, usuario_id, porcentaje_bp, estado, monto_cobrado)
    VALUES ('{PAR24}', '{CAR24}', '{U24}', 10000, 'pagada', 15980);
INSERT INTO transaccion_pasarela (participacion_id, proveedor, tipo, buy_order, monto, estado, idempotency_key,
                                  ultimos4, payload_respuesta)
    VALUES ('{PAR24}', 'webpay_plus', 'venta', 'MATU-24-0001', 15980, 'aprobada', 'k24', 'xx12', '{{"vci": "TSY"}}');
"""


def _acl_0024() -> dict[str, set[str]]:
    nombres = ", ".join(f"'{f}'" for f in FUNCIONES_0024)
    filas = consultar(f"SELECT proname, proacl::text FROM pg_proc WHERE proname IN ({nombres})")
    return {nombre: set(acl.strip("{}").split(",")) for nombre, acl in filas}


@pytest.mark.rf("RF-25")
def test_0024_pago_y_baja_al_esquema_de_0023(base_desechable):
    alembic("upgrade", "0023")
    esquema_0023 = catalogo()
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute(FILAS_0023)

    alembic("upgrade", "0024")
    # Las políticas del pago son por operación y por rol: ninguna FOR ALL
    politicas = consultar(
        "SELECT tablename, policyname, cmd, roles::text FROM pg_policies WHERE tablename IN"
        " ('cargo', 'participacion', 'transaccion_pasarela')")
    assert politicas and not [p for p in politicas if p[2] == "ALL"]
    assert ("cargo", "cargo_conservacion_borrar", "DELETE", "{matu_owner}") in politicas
    # Nadie de la API borra el pago
    assert not [g for g in _tablas_de("matu_app") if g[0] in TABLAS_DEL_PAGO and g[1] == "DELETE"]
    # Las funciones nuevas, solo para su rol
    for nombre, entradas in _acl_0024().items():
        assert f"{FUNCIONES_0024[nombre]}=X/matu_owner" in entradas, nombre
        assert len(entradas) == 2 and not any(e.startswith("=") for e in entradas), (nombre, entradas)
    # Las filas: la venta con su cargo y su total, y sin la respuesta de Transbank ni unos últimos 4 que no son cifras
    assert consultar("SELECT cargo_id::text, total_confirmado_en IS NOT NULL, payload_respuesta, ultimos4"
                     " FROM transaccion_pasarela") == [(CAR24, True, None, None)]
    # pedido_pago_con_condiciones queda validada (ninguna fila la viola); la de las condiciones completas, no: el
    # pedido pagado de la 0023 no tiene quién aceptó
    restricciones = dict(consultar(
        "SELECT conname, convalidated FROM pg_constraint WHERE conname IN"
        " ('pedido_pago_con_condiciones', 'pedido_condiciones_completas')"))
    assert restricciones == {"pedido_pago_con_condiciones": True, "pedido_condiciones_completas": False}
    with pytest.raises(psycopg.errors.CheckViolation), psycopg.connect(_dsn(BASE)) as c:
        c.execute("UPDATE transaccion_pasarela SET payload_respuesta = '{}'")
    # Lo pagado y lo aceptado no se reabren
    with pytest.raises(psycopg.errors.CheckViolation), psycopg.connect(_dsn(BASE)) as c:
        c.execute(f"UPDATE pedido SET condiciones_version = '0.2' WHERE id = '{PED24}'")
    # La conservación: el borrador sin cobro se borra a los 30 días; el pagado no
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute("SET session_replication_role = replica")
        # Solo el borrador: el pedido pagado de la 0023 no tiene quién aceptó, y pedido_condiciones_completas
        # (NOT VALID)
        # rechaza cualquier escritura nueva de esa fila. Lo pagado no se conserva por fecha
        c.execute(f"UPDATE pedido SET actualizado_en = now() - interval '40 days' WHERE id = '{PED24B}'")
        c.execute("SET session_replication_role = origin")
        c.execute("SET ROLE matu_scheduler")
        c.execute("SELECT set_config('app.rol', 'operacion', false)")
        c.execute("SELECT * FROM pedido_conservar(now() - interval '30 days', now())")
    assert consultar("SELECT id::text FROM pedido") == [(PED24,)]

    alembic("downgrade", "0023")
    despues = catalogo()
    for parte, filas in esquema_0023.items():
        assert despues[parte] == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues[parte])}"
    assert consultar("SELECT count(*) FROM transaccion_pasarela") == [(1,)]
    alembic("upgrade", "head")


# MATU-55 (0025): filas de la auditoría de 0024, como superusuario. Una de la cuenta (con la ip vacía, como siempre) y
# una del grupo
U25, G25 = "00000000-0000-0000-0000-0000000055a1", "00000000-0000-0000-0000-0000000055a0"
FILAS_0024_AUDITORIA = f"""
INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, ip) VALUES
 (NULL,     'usuario', '{U25}', 'sesion.iniciar', 'dispositivo', NULL),
 ('{G25}',  'usuario', '{U25}', 'plan.leer',      'plan_cuidado', NULL);
"""


def _alembic_falla(*args: str) -> str:
    """Corre alembic esperando que falle, y devuelve su stderr."""
    assert URL_MIGRACIONES is not None
    url = make_url(URL_MIGRACIONES).set(database=BASE).render_as_string(hide_password=False)
    r = subprocess.run(
        [sys.executable, "-c", "from alembic.config import main; main()", *args],
        cwd=BACKEND, env={**os.environ, "MIGRATIONS_DATABASE_URL": url},
        capture_output=True, text=True, check=False,
    )
    assert r.returncode != 0, f"alembic {' '.join(args)} debía fallar"
    return r.stderr


@pytest.mark.rf("RF-37")
def test_0025_auditoria_de_la_cuenta_y_baja_al_esquema_de_0024(base_desechable):
    from app.shared.auditoria import ACCIONES_DE_CUENTA

    alembic("upgrade", "0024")
    esquema_0024 = catalogo()
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute(FILAS_0024_AUDITORIA)

    alembic("upgrade", "0025")
    # La política, el índice y el CHECK validado; la columna ip ya no está, y las filas siguen
    assert consultar("SELECT cmd FROM pg_policies WHERE policyname = 'auditoria_cuenta_propia'") == [("SELECT",)]
    assert consultar("SELECT indexdef LIKE '%WHERE (grupo_id IS NULL)' FROM pg_indexes"
                     " WHERE indexname = 'auditoria_cuenta_ix'") == [(True,)]
    [(definicion, validada)] = consultar(
        "SELECT pg_get_constraintdef(oid), convalidated FROM pg_constraint WHERE conname = 'auditoria_cuenta_acotada'")
    assert validada is True
    # La lista del CHECK es la de ACCIONES_DE_CUENTA (decisión 258), sin la copia de la cuenta que suma la 0028
    assert set(definicion.split("ARRAY[", 1)[1].split("]", 1)[0].replace("::text", "").replace("'", "")
               .replace(" ", "").split(",")) == {a.value for a in ACCIONES_DE_CUENTA} - {"cuenta.datos_descargar"}
    assert consultar("SELECT count(*) FROM information_schema.columns WHERE table_name = 'auditoria'"
                     " AND column_name = 'ip'") == [(0,)]
    assert consultar("SELECT count(*) FROM auditoria") == [(2,)]
    with pytest.raises(psycopg.errors.CheckViolation), psycopg.connect(_dsn(BASE)) as c:
        c.execute(f"INSERT INTO auditoria (actor_tipo, actor_ref, accion, entidad) VALUES ('usuario', '{U25}',"
                  " 'plan.leer', 'plan_cuidado')")

    alembic("downgrade", "0024")
    despues = catalogo()
    for parte, filas in esquema_0024.items():
        assert despues[parte] == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues[parte])}"
    assert consultar("SELECT count(*) FROM auditoria") == [(2,)]

    # Una fila sin grupo que no es de la cuenta hace fallar la subida con el nombre del CHECK, en vez de quedar oculta
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute(f"INSERT INTO auditoria (actor_tipo, actor_ref, accion, entidad) VALUES ('usuario', '{U25}',"
                  " 'plan.leer', 'plan_cuidado')")
    assert "auditoria_cuenta_acotada" in _alembic_falla("upgrade", "0025")
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute("SET session_replication_role = replica")
        c.execute("DELETE FROM auditoria WHERE grupo_id IS NULL AND accion = 'plan.leer'")
    alembic("upgrade", "head")


# MATU-42 (0026): invitaciones, membresías y el grupo que nunca queda sin admin. Filas como superusuario
G26, U26A, U26B, U26C = ("00000000-0000-0000-0000-0000000026" + s for s in ("0a", "a1", "a2", "a3"))
FILAS_0025_GRUPO = f"""
INSERT INTO usuario (id, email, nombre, password_hash) VALUES
 ('{U26A}', 'a26@correo.ejemplo', 'Persona A', 'h'), ('{U26B}', 'b26@correo.ejemplo', 'Persona B', 'h'),
 ('{U26C}', 'c26@correo.ejemplo', 'Persona C', 'h');
INSERT INTO grupo_familiar (id, nombre, creado_por) VALUES ('{G26}', 'Familia A', '{U26A}');
INSERT INTO membresia (grupo_id, usuario_id, rol) VALUES ('{G26}', '{U26A}', 'admin'), ('{G26}', '{U26B}', 'cuidador');
"""
FUNCIONES_0026 = {
    "invitacion_presentar": "matu_app",
    "invitacion_verificar": "matu_app",
    "invitacion_aceptar": "matu_app",
    "membresia_retirar": "matu_app",
    "invitacion_conservar": "matu_scheduler",
}


def _invitacion_0026(invitacion_id: str, token: str, cerrada_hace: str | None) -> str:
    """Una invitación de la 0026 con su indice_token; cerrada_hace la deja anulada hace ese intervalo."""
    revocada = "NULL" if cerrada_hace is None else f"now() - interval '{cerrada_hace}'"
    creada = "now()" if cerrada_hace is None else f"now() - interval '{cerrada_hace}' - interval '1 day'"
    return (
        "INSERT INTO invitacion (id, grupo_id, rol, token_hash, codigo_hash, invitado_por, nombre_pila_invita,"
        f" creada_en, expira_en, revocada_en) VALUES ('{invitacion_id}', '{G26}', 'cuidador', sha256('{token}'),"
        f" sha256('c'), '{U26A}', 'Persona', {creada}, {creada} + interval '7 days', {revocada});"
        "INSERT INTO indice_token (token_hash, tipo, grupo_id, referencia_id, expira_en)"
        f" VALUES (sha256('{token}'), 'invitacion', '{G26}', '{invitacion_id}', {creada} + interval '7 days');"
    )


@pytest.mark.rf("RF-38")
def test_0026_invitaciones_y_miembros_y_baja_al_esquema_de_0025(base_desechable):
    alembic("upgrade", "0025")
    esquema_0025 = catalogo()
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute(FILAS_0025_GRUPO)
        # Una invitación del modelo anterior hace fallar la subida con un mensaje claro (ninguna ruta las creó)
        c.execute(f"INSERT INTO invitacion (grupo_id, destino_email, rol, token_hash, invitado_por, expira_en) VALUES"
                  f" ('{G26}', 'x@correo.ejemplo', 'cuidador', sha256('v'), '{U26A}', now() + interval '1 day')")
    assert "la 0026 exige la tabla invitacion vacía" in _alembic_falla("upgrade", "0026")
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute("DELETE FROM invitacion")

    alembic("upgrade", "0026")
    # Ninguna política FOR ALL en membresia, invitacion ni direccion; en el grupo, solo la de operación
    politicas = consultar("SELECT tablename, policyname, cmd FROM pg_policies WHERE tablename IN"
                          " ('membresia', 'invitacion', 'direccion', 'grupo_familiar')")
    assert {(t, p) for t, p, cmd in politicas if cmd == "ALL"} == {("grupo_familiar", "grupo_operacion")}
    # Sin DELETE para la API, y UPDATE solo de las columnas que cambia
    assert not {g for g in _tablas_de("matu_app") if g[0] in ("membresia", "invitacion", "grupo_familiar")
                and g[1] in ("UPDATE", "DELETE")}
    assert _columnas_con("membresia", "UPDATE") == {"rol", "puede_ver_plan", "version"}
    assert _columnas_con("invitacion", "UPDATE") == {"revocada_en"}
    assert _columnas_con("grupo_familiar", "UPDATE") == {"nombre", "actualizado_en"}
    # Las funciones, solo para su rol
    nombres = ", ".join(f"'{f}'" for f in FUNCIONES_0026)
    acl = {n: set(a.strip("{}").split(",")) for n, a in consultar(
        f"SELECT proname, proacl::text FROM pg_proc WHERE proname IN ({nombres})")}
    for nombre, rol in FUNCIONES_0026.items():
        assert f"{rol}=X/matu_owner" in acl[nombre], nombre
        assert len(acl[nombre]) == 2 and not any(e.startswith("=") for e in acl[nombre]), (nombre, acl[nombre])
    # La invitación ya no guarda contacto
    columnas = {c for (c,) in consultar("SELECT column_name FROM information_schema.columns"
                                        " WHERE table_name = 'invitacion'")}
    assert not {"destino_email", "destino_telefono"} & columnas
    assert {"nombre_pila_invita", "codigo_hash", "codigo_intentos_fallidos", "bloqueada_en"} <= columnas
    # El grupo nunca queda sin admin, también para el superusuario
    with pytest.raises(psycopg.errors.CheckViolation), psycopg.connect(_dsn(BASE)) as c:
        c.execute(f"UPDATE membresia SET rol = 'cuidador' WHERE usuario_id = '{U26A}'")
    # La conservación: la anulada hace 31 días se va con su indice_token; la pendiente se queda
    vieja, nueva = "00000000-0000-0000-0000-0000000026e1", "00000000-0000-0000-0000-0000000026e2"
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute(_invitacion_0026(vieja, "t1", "31 days") + _invitacion_0026(nueva, "t2", None))
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute("SET ROLE matu_scheduler")
        c.execute("SELECT set_config('app.rol', 'operacion', false)")
        assert c.execute("SELECT invitacion_conservar(now() - interval '30 days', now())").fetchone() == (1,)
    assert consultar("SELECT id::text FROM invitacion") == [(nueva,)]
    assert consultar("SELECT referencia_id::text FROM indice_token WHERE tipo = 'invitacion'") == [(nueva,)]
    # Volver a invitar a quien salió: una fila nueva. Con ella, la bajada falla con un mensaje claro
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute(f"UPDATE membresia SET estado = 'retirada' WHERE usuario_id = '{U26B}'")
        c.execute(f"INSERT INTO membresia (grupo_id, usuario_id, rol) VALUES ('{G26}', '{U26B}', 'observador')")
    assert "una cuenta tiene dos membresías en el mismo grupo" in _alembic_falla("downgrade", "0025")
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute(f"DELETE FROM membresia WHERE usuario_id = '{U26B}' AND estado = 'retirada'")
        c.execute("DELETE FROM indice_token WHERE tipo = 'invitacion'")
        c.execute("DELETE FROM invitacion")

    alembic("downgrade", "0025")
    despues = catalogo()
    for parte, filas in esquema_0025.items():
        assert despues[parte] == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues[parte])}"
    assert consultar("SELECT count(*) FROM membresia") == [(2,)]
    alembic("upgrade", "head")


@pytest.mark.rf("RF-38")
def test_0026_baja_con_auditoria_de_roles_y_la_conserva(base_desechable):
    """Con filas de auditoría con rol (o invitaciones sin contacto), la bajada no borra nada: los CHECK de la 0025
    vuelven NOT VALID. Validar un CHECK ve todas las filas, sin RLS."""
    alembic("upgrade", "0026")
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute(FILAS_0025_GRUPO)
        c.execute(f"INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, detalle) VALUES"
                  f" ('{G26}', 'usuario', '{U26A}', 'invitacion.crear', 'invitacion', '{{\"rol\": \"cuidador\"}}')")
        c.execute(_invitacion_0026("00000000-0000-0000-0000-0000000026e3", "t3", None))
    alembic("downgrade", "0025")
    assert dict(consultar("SELECT conname, convalidated FROM pg_constraint WHERE conname IN"
                          " ('auditoria_detalle_acotado', 'invitacion_destino')")) == {
        "auditoria_detalle_acotado": False, "invitacion_destino": False}
    assert consultar("SELECT count(*) FROM auditoria WHERE detalle ? 'rol'") == [(1,)]
    assert consultar("SELECT count(*) FROM invitacion") == [(1,)]


# MATU-46 (0027): el teléfono del relevo se borra a los 30 días, y al tiro al borrar a la persona. Como superusuario
ACC27_VIEJO, ACC27_VIGENTE = ("00000000-0000-0000-0000-0000000027" + s for s in ("c1", "c2"))


def _acceso_0027(acceso_id: str, token: str, termino_hace: str | None) -> str:
    """Un acceso de relevo; termino_hace lo deja vencido hace ese intervalo."""
    creado = "now()" if termino_hace is None else f"now() - interval '{termino_hace}' - interval '1 day'"
    return (
        "INSERT INTO acceso_relevo (id, grupo_id, plan_id, otorgado_por, otorgado_a_nombre, otorgado_a_telefono,"
        " nombre_pila_persona, nombre_pila_comparte, secciones_permitidas, motivo, token_hash, pin_hash, creado_en,"
        f" expira_en, relevo_informado_en) VALUES ('{acceso_id}', '{G}', '{PLAN}', '{U}', 'Relevo', '+56955550127',"
        f" 'Persona', 'Ana', ARRAY['rutina'], 'otro', sha256('{token}'), 'p', {creado}, {creado} + interval '1 day',"
        " now());"
    )


@pytest.mark.rf("RF-05")
def test_0027_telefono_del_relevo_y_baja_al_esquema_de_0026(base_desechable):
    alembic("upgrade", "0026")
    esquema_0026 = catalogo()
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute(FILAS_ACCESO + _acceso_0027(ACC27_VIEJO, "t1", "31 days") + _acceso_0027(ACC27_VIGENTE, "t2", None))

    alembic("upgrade", "0027")
    columnas = dict(consultar("SELECT column_name, is_nullable FROM information_schema.columns"
                              " WHERE table_name = 'acceso_relevo'"))
    assert columnas["otorgado_a_telefono"] == "YES" and columnas["telefono_borrado_en"] == "YES"
    assert consultar("SELECT convalidated FROM pg_constraint WHERE conname = 'acceso_relevo_telefono_borrado'"
                     ) == [(True,)]
    assert consultar("SELECT tgname FROM pg_trigger WHERE tgname = 'acceso_relevo_telefono'") == [
        ("acceso_relevo_telefono",)]
    # Las políticas de la tarea, solo para matu_owner; las de la familia y del relevo no cambian
    politicas = {(n, r, c) for n, r, c in consultar(
        "SELECT policyname, roles::text, cmd FROM pg_policies WHERE tablename = 'acceso_relevo'"
        " AND policyname LIKE 'acceso_conservacion%'")}
    assert politicas == {("acceso_conservacion_leer", "{matu_owner}", "SELECT"),
                         ("acceso_conservacion", "{matu_owner}", "UPDATE")}
    # matu_app recibe solo el UPDATE de las dos columnas del teléfono (D-46-3 a)
    assert _columnas_con("acceso_relevo", "UPDATE") == {
        "revocado_en", "nombre_pila_persona", "pin_intentos_fallidos", "usos", "ultimo_uso_en",
        "otorgado_a_telefono", "telefono_borrado_en"}
    assert _privilegios("acceso_relevo") == {"SELECT", "INSERT"}
    # La función, SECURITY DEFINER con search_path fijo, solo para matu_scheduler (C9)
    [(definer, config, acl)] = consultar(
        "SELECT prosecdef, proconfig, proacl::text FROM pg_proc WHERE proname = 'relevo_conservar'")
    assert definer and config == ["search_path=pg_catalog, public, pg_temp"]
    assert set(acl.strip("{}").split(",")) == {"matu_owner=X/matu_owner", "matu_scheduler=X/matu_owner"}
    # La tarea vacía el teléfono del acceso vencido hace 31 días, y solo ese
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute("SET ROLE matu_scheduler")
        c.execute("SELECT set_config('app.rol', 'operacion', false)")
        assert c.execute("SELECT relevo_conservar(now() - interval '30 days', now())").fetchone() == (1,)
        assert c.execute("SELECT relevo_conservar(now() - interval '30 days', now())").fetchone() == (0,)
    assert dict(consultar("SELECT id::text, otorgado_a_telefono FROM acceso_relevo")) == {
        ACC27_VIEJO: None, ACC27_VIGENTE: "+56955550127"}
    # El trigger, también para el superusuario: el teléfono no vuelve
    with pytest.raises(psycopg.errors.CheckViolation), psycopg.connect(_dsn(BASE)) as c:
        c.execute(f"UPDATE acceso_relevo SET otorgado_a_telefono = '+56955550127', telefono_borrado_en = NULL"
                  f" WHERE id = '{ACC27_VIEJO}'")

    # Con un teléfono borrado, la bajada se detiene en vez de inventar uno
    assert "MATU nunca inventa un teléfono" in _alembic_falla("downgrade", "0026")
    assert consultar("SELECT count(*) FROM acceso_relevo WHERE otorgado_a_telefono IS NULL") == [(1,)]
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute(f"DELETE FROM acceso_relevo WHERE id = '{ACC27_VIEJO}'")

    alembic("downgrade", "0026")
    despues = catalogo()
    for parte, filas in esquema_0026.items():
        assert despues[parte] == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues[parte])}"
    assert consultar("SELECT id::text, otorgado_a_telefono FROM acceso_relevo") == [(ACC27_VIGENTE, "+56955550127")]
    alembic("upgrade", "head")


# MATU-54 (0028): la persona de cada fila de auditoría. Otro grupo con su persona, para la clave foránea compuesta
G28, U28, P28 = ("00000000-0000-0000-0000-0000000028" + s for s in ("0a", "a1", "b1"))
FILAS_OTRO_GRUPO_0028 = f"""
INSERT INTO usuario (id, email, nombre, password_hash) VALUES ('{U28}', 'b28@correo.ejemplo', 'Persona B', 'h');
INSERT INTO grupo_familiar (id, nombre, creado_por) VALUES ('{G28}', 'Familia B', '{U28}');
INSERT INTO persona_cuidada (id, grupo_id, nombre, nombre_pila, nivel_apoyo) VALUES
 ('{P28}', '{G28}', 'Persona Cuidada B', 'Persona', 'apoyo_total');
"""


# MATU-63: las acciones de persona que suma la 0029
NUEVAS_0029 = {"pago.devolver", "pedido.retracto_solicitar", "codigo_retiro.generar", "despacho.en_camino",
               "despacho.entregar", "despacho.no_entregado", "retracto.resolver"}


def _lista_del_check(nombre: str) -> set[str]:
    [(definicion,)] = consultar(f"SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = '{nombre}'")
    return set(definicion.split("ARRAY[", 1)[1].split("]", 1)[0].replace("::text", "").replace("'", "")
               .replace(" ", "").split(","))


@pytest.mark.rf("RF-08")
@pytest.mark.rf("Ley-21.719")
def test_0028_auditoria_con_persona_y_baja_al_esquema_de_0027(base_desechable):
    from app.shared.auditoria import ACCIONES_DE_CUENTA, ACCIONES_DE_PERSONA

    alembic("upgrade", "0027")
    esquema_0027 = catalogo()
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute(FILAS_ACCESO + FILAS_OTRO_GRUPO_0028)
        # Una fila anterior, sin persona: se queda tal cual
        c.execute(f"INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, entidad_id)"
                  f" VALUES ('{G}', 'usuario', '{U}', 'plan.leer', 'plan_cuidado', '{PLAN}')")

    alembic("upgrade", "0028")
    columnas = dict(consultar("SELECT column_name, is_nullable FROM information_schema.columns"
                              " WHERE table_name = 'auditoria' AND column_name = 'persona_cuidada_id'"))
    assert columnas == {"persona_cuidada_id": "YES"}
    # Sin relleno: la fila anterior sigue sin persona
    assert consultar("SELECT count(*) FROM auditoria WHERE persona_cuidada_id IS NULL") == [(1,)]
    validadas = dict(consultar(
        "SELECT conname, convalidated FROM pg_constraint WHERE conname IN ('auditoria_persona_fk',"
        " 'auditoria_persona_con_grupo', 'auditoria_persona_obligatoria', 'auditoria_cuenta_acotada',"
        " 'persona_cuidada_id_grupo_uq')"))
    # La de las acciones de persona queda NOT VALID a propósito: las filas anteriores no tienen persona
    assert validadas == {"auditoria_persona_fk": True, "auditoria_persona_con_grupo": True,
                         "auditoria_persona_obligatoria": False, "auditoria_cuenta_acotada": True,
                         "persona_cuidada_id_grupo_uq": True}
    # Las listas de los dos CHECK son las del código
    # Sin las acciones que suma la 0029 (MATU-63)
    assert _lista_del_check("auditoria_persona_obligatoria") == (
        {a.value for a in ACCIONES_DE_PERSONA} - NUEVAS_0029 - NUEVAS_0030 - NUEVAS_0031)
    assert _lista_del_check("auditoria_cuenta_acotada") == {a.value for a in ACCIONES_DE_CUENTA}
    assert consultar("SELECT indexdef LIKE '%WHERE (persona_cuidada_id IS NOT NULL)' FROM pg_indexes"
                     " WHERE indexname = 'auditoria_persona_ix'") == [(True,)]
    # plan_destruir_claves conserva su dueño y su permiso (solo matu_scheduler, 0022) y escribe la persona
    [(acl, definicion)] = consultar("SELECT proacl::text, pg_get_functiondef(oid) FROM pg_proc"
                                    " WHERE proname = 'plan_destruir_claves'")
    assert set(acl.strip("{}").split(",")) == {"matu_owner=X/matu_owner", "matu_scheduler=X/matu_owner"}
    assert "d.persona_cuidada_id FROM destruidas" in definicion

    with psycopg.connect(_dsn(BASE)) as c:
        # Una acción de persona nueva sin persona: la base la rechaza
        with pytest.raises(psycopg.errors.CheckViolation), c.transaction():
            c.execute(f"INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad)"
                      f" VALUES ('{G}', 'usuario', '{U}', 'plan.leer', 'plan_cuidado')")
        # La persona de otro grupo: la clave foránea compuesta la rechaza
        with pytest.raises(psycopg.errors.ForeignKeyViolation), c.transaction():
            c.execute(f"INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, persona_cuidada_id)"
                      f" VALUES ('{G}', 'usuario', '{U}', 'plan.leer', 'plan_cuidado', '{P28}')")
        # Persona sin grupo: el CHECK lo rechaza (con MATCH SIMPLE escaparía a la FK)
        with pytest.raises(psycopg.errors.CheckViolation), c.transaction():
            c.execute(f"INSERT INTO auditoria (actor_tipo, actor_ref, accion, entidad, persona_cuidada_id)"
                      f" VALUES ('usuario', '{U}', 'cuenta.datos_descargar', 'usuario', '{P}')")
        # La copia de la cuenta va sin grupo
        c.execute(f"INSERT INTO auditoria (actor_tipo, actor_ref, accion, entidad, entidad_id)"
                  f" VALUES ('usuario', '{U}', 'cuenta.datos_descargar', 'usuario', '{U}')")

    # Sin filas con persona, la bajada pasa, y el CHECK de la cuenta vuelve NOT VALID porque hay una copia de la cuenta
    alembic("downgrade", "0027")
    despues = catalogo()
    for parte, filas in esquema_0027.items():
        if parte == "restricciones":
            filas = [f for f in filas if "auditoria_cuenta_acotada" not in str(f)]
            despues_parte = [f for f in despues[parte] if "auditoria_cuenta_acotada" not in str(f)]
            assert despues_parte == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues_parte)}"
        else:
            assert despues[parte] == filas, f"downgrade no restaura {parte}: {set(filas) ^ set(despues[parte])}"
    assert consultar("SELECT convalidated FROM pg_constraint WHERE conname = 'auditoria_cuenta_acotada'") == [(False,)]
    assert consultar("SELECT count(*) FROM auditoria") == [(2,)]

    # Con una fila con persona, la bajada se detiene: nunca borra un registro de auditoría
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute("SET session_replication_role = replica")
        c.execute("DELETE FROM auditoria WHERE accion = 'cuenta.datos_descargar'")
    alembic("upgrade", "0028")
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute(f"INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, persona_cuidada_id)"
                  f" VALUES ('{G}', 'usuario', '{U}', 'persona.datos_descargar', 'persona_cuidada', '{P}')")
    assert "la bajada de la 0028 no borra registros" in _alembic_falla("downgrade", "0027")
    assert consultar("SELECT count(*) FROM auditoria WHERE persona_cuidada_id IS NOT NULL") == [(1,)]
    alembic("upgrade", "head")


# MATU-63 (0029): una parte con la referencia de antes (16 a 64 caracteres) y una evidencia con ubicación
PED29, PARTE29, CAT29, PROD29, COM29, OF29 = (
    "00000000-0000-0000-0000-0000000029" + s for s in ("d1", "e1", "c1", "f1", "a1", "b1")
)
FILAS_0028_DESPACHO = f"""
INSERT INTO categoria_cuidado (id, nombre) VALUES ('{CAT29}', 'Higiene 29');
INSERT INTO producto (id, categoria_id, nombre, presentacion, unidad, unidades_por_envase)
    VALUES ('{PROD29}', '{CAT29}', 'Pañal 29', 'x30', 'unidad', 30);
INSERT INTO comercio (id, razon_social, nombre_fantasia, rut, direccion, comuna)
    VALUES ('{COM29}', 'Comercio 29', 'Comercio 29', '76.000.029-0', 'Calle de Prueba 29', 'Ñuñoa');
INSERT INTO oferta (id, producto_id, comercio_id, precio, stock) VALUES ('{OF29}', '{PROD29}', '{COM29}', 12990, 5);
INSERT INTO pedido (id, grupo_id, persona_cuidada_id, estado, subtotal_productos, costo_envio, total, creado_por)
    VALUES ('{PED29}', '{G}', '{P}', 'borrador', 0, 0, 0, '{U}');
INSERT INTO pedido_comercio (id, grupo_id, pedido_id, comercio_id, referencia)
    VALUES ('{PARTE29}', '{G}', '{PED29}', '{COM29}', 'referencia-opaca-de-la-0028');
INSERT INTO evidencia (pedido_id, tipo, objeto_clave, sha256, lat, lng, registrada_por_tipo, registrada_por)
    VALUES ('{PED29}', 'entrega', 'x', sha256('x'), -33.4, -70.6, 'operacion', '{U}');
"""
FUNCIONES_0029 = {
    "comercio_partes": "matu_app", "comercio_lineas": "matu_app", "comercio_preparar": "matu_app",
    "comercio_marcar_linea": "matu_app", "comercio_listo": "matu_app", "comercio_validar_codigo": "matu_app",
    "comercio_existencias": "matu_app", "oferta_disponible": "matu_app", "despacho_resolver_parte": "matu_app",
    "despacho_pendiente": "matu_scheduler",
}


# MATU-81: las acciones de persona que suma la 0030
NUEVAS_0030 = {"operacion.pedido_ver", "incidencia.crear", "incidencia.resolver"}
# MATU-114 (J2): lo que suma la 0031
NUEVAS_0031 = {"operacion.retracto_correo_fallido"}


@pytest.mark.rf("RF-26")
@pytest.mark.rf("Ley-21.719")
def test_0029_vista_del_comercio_y_baja_al_esquema_de_0028(base_desechable):
    from app.shared.auditoria import ACCIONES_DE_CUENTA, ACCIONES_DE_PERSONA, ACCIONES_DEL_COMERCIO

    alembic("upgrade", "0028")
    esquema_0028 = catalogo()
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute(FILAS_ACCESO + FILAS_0028_DESPACHO)

    alembic("upgrade", "0029")
    # D-63-1: el comercio ya no tiene políticas sobre el pedido, sus partes ni sus líneas (solo las de las funciones,
    # TO matu_owner)
    politicas = consultar(
        "SELECT policyname, roles::text FROM pg_policies WHERE tablename IN ('pedido', 'pedido_comercio',"
        " 'pedido_linea') AND coalesce(qual, '') || coalesce(with_check, '') LIKE '%= app_comercio()%'")
    assert politicas and {roles for _, roles in politicas} == {"{matu_owner}"}
    # Las funciones nuevas, solo para su rol
    filas = consultar("SELECT proname, proacl::text, prosecdef FROM pg_proc WHERE proname = ANY(%s)"
                      % ("ARRAY[" + ", ".join(f"'{f}'" for f in FUNCIONES_0029) + "]"))
    assert {f[0] for f in filas} == set(FUNCIONES_0029)
    for nombre, acl, definer in filas:
        entradas = set(acl.strip("{}").split(","))
        assert definer and entradas == {"matu_owner=X/matu_owner", f"{FUNCIONES_0029[nombre]}=X/matu_owner"}, nombre
    # O6: la referencia de antes se rehízo con el alfabeto que se dicta
    [(referencia,)] = consultar(f"SELECT referencia FROM pedido_comercio WHERE id = '{PARTE29}'")
    assert len(referencia) == 6 and not set(referencia) & set("0O1IL")
    # D-63-15: la ubicación de la evidencia se vació
    assert consultar("SELECT lat, lng FROM evidencia") == [(None, None)]
    # Las listas de los CHECK de la auditoría son las del código, sin lo que suma la 0030 (MATU-81)
    assert _lista_del_check("auditoria_persona_obligatoria") == ({a.value for a in ACCIONES_DE_PERSONA}
                                                                   - NUEVAS_0030 - NUEVAS_0031)
    assert _lista_del_check("auditoria_cuenta_acotada") == {a.value for a in ACCIONES_DE_CUENTA | ACCIONES_DEL_COMERCIO}
    assert consultar("SELECT bool_and(relrowsecurity AND relforcerowsecurity) FROM pg_class"
                     " WHERE relname IN ('retracto', 'retracto_linea')") == [(True,)]
    with psycopg.connect(_dsn(BASE)) as c:
        # Una referencia que no se dicta, rechazada
        with pytest.raises(psycopg.errors.CheckViolation), c.transaction():
            c.execute(f"UPDATE pedido_comercio SET referencia = 'K4M7X0' WHERE id = '{PARTE29}'")
        # Una cuenta de comercio no entra a un grupo (D-63-14)
        c.execute(f"INSERT INTO membresia (grupo_id, usuario_id, rol) VALUES ('{G}', '{U}', 'admin')")
        with pytest.raises(psycopg.errors.CheckViolation), c.transaction():
            c.execute(f"INSERT INTO usuario_comercio (usuario_id, comercio_id) VALUES ('{U}', '{COM29}')")

    alembic("downgrade", "0028")
    despues = catalogo()
    for parte, filas_0028 in esquema_0028.items():
        assert despues[parte] == filas_0028, f"downgrade no restaura {parte}: {set(filas_0028) ^ set(despues[parte])}"
    # La referencia vuelve a caber en el CHECK de la 0023 (16 a 64)
    [(referencia,)] = consultar(f"SELECT referencia FROM pedido_comercio WHERE id = '{PARTE29}'")
    assert 16 <= len(referencia) <= 64
    alembic("upgrade", "head")


# ---- 0030 (MATU-81): las incidencias, el segundo factor y la consola de operación

FUNCIONES_0030 = {"iam_mfa_secreto": "matu_app",  # pragma: allowlist secret
                  "operacion_buscar_cuenta": "matu_scheduler", "operacion_alta": "matu_scheduler"}
INC30 = "00000000-0000-0000-0000-0000000030a1"


@pytest.mark.rf("RF-40")
@pytest.mark.rf("Ley-21.719")
def test_0030_backoffice_de_operacion_y_baja_al_esquema_de_0029(base_desechable):
    from app.shared.auditoria import (
        ACCIONES_DE_CUENTA,
        ACCIONES_DE_OPERACION,
        ACCIONES_DE_PERSONA,
        ACCIONES_DEL_COMERCIO,
    )

    alembic("upgrade", "0028")
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute(FILAS_ACCESO + FILAS_0028_DESPACHO)
    alembic("upgrade", "0029")
    esquema_0029 = catalogo()
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute(f"INSERT INTO incidencia (id, pedido_id, tipo, descripcion, creada_por)"
                  f" VALUES ('{INC30}', '{PED29}', 'desviacion_monto', 'Nota anterior', '{U}')")

    # Decisión 471: la nota en claro no se cifra desde la base; con incidencias, la subida se detiene sin tocarlas
    assert "la 0030 no las cifra ni las borra" in _alembic_falla("upgrade", "0030")
    assert consultar(f"SELECT tipo, descripcion FROM incidencia WHERE id = '{INC30}'") == [
        ("desviacion_monto", "Nota anterior")]
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute(f"DELETE FROM incidencia WHERE id = '{INC30}'")

    alembic("upgrade", "0030")
    politicas = {(n, c) for n, c in consultar("SELECT policyname, cmd FROM pg_policies WHERE tablename = 'incidencia'")}
    assert politicas == {("incidencia_operacion_leer", "SELECT"), ("incidencia_operacion_crear", "INSERT"),
                         ("incidencia_operacion_editar", "UPDATE"), ("incidencia_familia", "SELECT")}
    assert _privilegios("incidencia") == {"SELECT", "INSERT"}
    assert _columnas_con("incidencia", "UPDATE") == {"estado", "asignada_a", "resolucion", "resolucion_clave_id",
                                                     "resuelta_en"}
    # La nota y la resolución, cifradas: bytea, con la clave de cada una
    tipos = dict(consultar("SELECT column_name, data_type FROM information_schema.columns"
                           " WHERE table_name = 'incidencia' AND column_name IN ('descripcion', 'resolucion',"
                           " 'clave_notas_id', 'resolucion_clave_id')"))
    assert tipos == {"descripcion": "bytea", "resolucion": "bytea", "clave_notas_id": "uuid",
                     "resolucion_clave_id": "uuid"}
    # clave_notas: FORCE ROW LEVEL SECURITY, sus políticas y solo SELECT e INSERT para matu_app
    assert consultar("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'clave_notas'") == [
        (True, True)]
    politicas = {(n, c, r) for n, c, r in consultar(
        "SELECT policyname, cmd, roles::text FROM pg_policies WHERE tablename = 'clave_notas'")}
    assert politicas == {
        ("clave_notas_operacion_leer", "SELECT", "{public}"), ("clave_notas_operacion_crear", "INSERT", "{public}"),
        ("clave_notas_familia_leer", "SELECT", "{public}"),
        ("clave_notas_destruccion_leer", "SELECT", "{matu_owner}"),
        ("clave_notas_destruccion", "UPDATE", "{matu_owner}"),
    }
    assert _privilegios("clave_notas") == {"SELECT", "INSERT"}
    [(acl, definer)] = consultar("SELECT proacl::text, prosecdef FROM pg_proc WHERE proname = 'clave_notas_destruir'")
    assert definer and acl == "{matu_owner=X/matu_owner}"
    # Decisión de Jorge del 17-11: la clave de las notas se destruye solo con el borrado de la persona, nunca con la de
    # la ficha (clave_datos_destruye_notas ya no existe)
    disparadores = {n for (n,) in consultar("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal AND tgname IN"
                                            " ('clave_datos_destruye_notas', 'persona_borrada_destruye_notas',"
                                            " 'clave_notas_solo_destruir')")}
    assert disparadores == {"persona_borrada_destruye_notas", "clave_notas_solo_destruir"}
    [(fk,)] = consultar("SELECT pg_get_constraintdef(oid) FROM pg_constraint"
                        " WHERE conname = 'incidencia_pedido_id_fkey'")
    assert "ON DELETE CASCADE" in fk
    # D-81-2 y D-81-6
    quitadas = consultar("SELECT policyname FROM pg_policies WHERE policyname IN ('aceptacion_operacion_leer',"
                         " 'persona_operacion', 'entrega_operacion')")
    assert quitadas == []
    assert consultar("SELECT cmd FROM pg_policies WHERE policyname = 'entrega_operacion_leer'") == [("SELECT",)]
    assert consultar("SELECT count(*) FROM pg_policies WHERE policyname = 'direccion_operacion_leer'") == [(1,)]
    assert consultar("SELECT policyname, roles::text FROM pg_policies WHERE tablename = 'consentimiento'"
                     " AND qual LIKE '%operacion%'") == [("consentimiento_conservacion", "{matu_owner}")]
    # Las funciones nuevas, solo para su rol, con dueño matu_owner
    filas = consultar("SELECT proname, proacl::text, prosecdef FROM pg_proc WHERE proname = ANY(ARRAY["
                      + ", ".join(f"'{x}'" for x in FUNCIONES_0030) + "])")
    assert {x[0] for x in filas} == set(FUNCIONES_0030)
    for nombre, acl, definer in filas:
        assert definer and set(acl.strip("{}").split(",")) == {
            "matu_owner=X/matu_owner", f"{FUNCIONES_0030[nombre]}=X/matu_owner"}, nombre
    # matu_app sigue sin leer el secreto
    assert "mfa_secreto_cifrado" not in _columnas_con("usuario", "SELECT")
    # Las listas de los CHECK de la auditoría son las del código
    assert _lista_del_check("auditoria_persona_obligatoria") == {a.value for a in ACCIONES_DE_PERSONA} - NUEVAS_0031
    assert _lista_del_check("auditoria_cuenta_acotada") == {
        a.value for a in ACCIONES_DE_CUENTA | ACCIONES_DEL_COMERCIO | ACCIONES_DE_OPERACION}
    with psycopg.connect(_dsn(BASE)) as c:
        # C12: sobre un pedido sin pagar, no
        with pytest.raises(psycopg.errors.CheckViolation), c.transaction():
            c.execute(f"INSERT INTO incidencia (pedido_id, tipo, descripcion, creada_por)"
                      f" VALUES ('{PED29}', 'otro', 'x', '{U}')")
        # C24: el motivo de rechazo, solo en un rechazado y de la lista
        with pytest.raises(psycopg.errors.CheckViolation), c.transaction():
            c.execute("SET session_replication_role = replica")
            c.execute("INSERT INTO retracto (grupo_id, pedido_id, solicitado_por, solicitado_en, plazo_hasta,"
                      f" incluye_envio, motivo_rechazo) VALUES ('{G}', '{PED29}', '{U}', now(),"
                      " now() + interval '1 day', false, 'sello_abierto')")

    # Con una clave de notas o una incidencia (cifrada), la bajada se detiene sin tocarlas: lo cifrado no vuelve a texto
    with psycopg.connect(_dsn(BASE)) as c:
        [(persona, grupo)] = c.execute(
            f"SELECT persona_cuidada_id, grupo_id FROM pedido WHERE id = '{PED29}'").fetchall()
        c.execute("INSERT INTO clave_notas (grupo_id, persona_cuidada_id, dek_cifrada_con_kek, kek_version)"
                  " VALUES (%s, %s, %s, 1)", (grupo, persona, b"\x05" * 40))
    assert "no las descifra ni las borra" in _alembic_falla("downgrade", "0029")
    assert consultar("SELECT count(*) FROM clave_notas") == [(1,)]
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute("DELETE FROM clave_notas")

    alembic("downgrade", "0029")
    despues = catalogo()
    for parte, filas_0029 in esquema_0029.items():
        assert despues[parte] == filas_0029, f"downgrade no restaura {parte}: {set(filas_0029) ^ set(despues[parte])}"
    assert consultar("SELECT count(*) FROM pg_class WHERE relname = 'clave_notas'") == [(0,)]
    alembic("upgrade", "head")


# ---- 0031 (MATU-114): operación deja de leer cuentas y membresías

FUNCIONES_0031 = {"operacion_cuenta_activa": "matu_app", "cuenta_es_operacion": "matu_app",
                  "operacion_solicitante_retracto": "matu_app"}
# Las políticas que no son TO matu_owner y miran app.rol = 'operacion', después de la 0031 (docstring de la migración)
POLITICAS_OPERACION_0031 = {
    "alerta_quiebre": {"alerta_leer"}, "asignacion": {"asignacion_operacion"}, "auditoria": {"auditoria_insertar"},
    "cargo": {"cargo_operacion_editar", "cargo_operacion_leer"}, "categoria_cuidado": {"categoria_operacion"},
    "clave_notas": {"clave_notas_operacion_crear", "clave_notas_operacion_leer"},
    "comercio": {"comercio_operacion"}, "consumo_comercio": {"consumo_comercio_operacion"},
    "convenio": {"convenio_operacion"}, "direccion": {"direccion_operacion_leer"},
    "grupo_familiar": {"grupo_operacion"},
    "incidencia": {"incidencia_operacion_crear", "incidencia_operacion_editar", "incidencia_operacion_leer"},
    "invitacion": {"invitacion_no_operacion"}, "liquidacion": {"liquidacion_operacion"},
    "membresia": {"membresia_no_operacion"}, "oferta": {"oferta_operacion"},
    "oferta_asignacion": {"oferta_asig_operacion"},
    "participacion": {"participacion_operacion_editar", "participacion_operacion_leer"},
    "pedido": {"pedido_operacion_leer", "pedido_operacion_pago"},
    "pedido_comercio": {"pedido_comercio_operacion_editar", "pedido_comercio_operacion_leer"},
    "pedido_entrega": {"entrega_operacion_leer"}, "pedido_linea": {"linea_pago_devolver"},
    "pedido_transicion": {"transicion_sistema_crear"}, "perfil_consumo": {"perfil_leer"},
    "producto": {"producto_operacion"}, "repartidor": {"repartidor_operacion"}, "reposicion": {"reposicion_leer"},
    "retracto": {"retracto_operacion_crear", "retracto_operacion_editar", "retracto_operacion_leer"},
    "retracto_linea": {"retracto_linea_operacion_crear", "retracto_linea_operacion_leer"},
    "transaccion_pasarela": {"transaccion_operacion_crear", "transaccion_operacion_editar",
                             "transaccion_operacion_leer"},
    "usuario": {"usuario_no_operacion"}, "usuario_comercio": {"usuario_comercio_operacion"},
}


@pytest.mark.rf("RF-40")
@pytest.mark.rf("Ley-21.719")
def test_0031_operacion_sin_cuentas_y_baja_al_esquema_de_0030(base_desechable):
    from app.shared.auditoria import ACCIONES_DE_PERSONA

    alembic("upgrade", "0030")
    esquema_0030 = catalogo()
    alembic("upgrade", "0031")

    # C1, C7 y O1: salen las tres; las restrictivas (TO matu_app) dejan solo la propia cuenta con operación
    quitadas = consultar("SELECT policyname FROM pg_policies WHERE policyname IN ('usuario_operacion_leer',"
                         " 'membresia_operacion', 'invitacion_operacion')")
    assert quitadas == []
    restrictivas = {(t, n, p, r) for t, n, p, r in consultar(
        "SELECT tablename, policyname, permissive, roles::text FROM pg_policies"
        " WHERE policyname LIKE '%_no_operacion'")}
    assert restrictivas == {("usuario", "usuario_no_operacion", "RESTRICTIVE", "{matu_app}"),
                            ("membresia", "membresia_no_operacion", "RESTRICTIVE", "{matu_app}"),
                            ("invitacion", "invitacion_no_operacion", "RESTRICTIVE", "{matu_app}")}
    # (f): la conservación de invitaciones sigue viendo lo que borra, solo como matu_owner
    assert consultar("SELECT roles::text, cmd FROM pg_policies WHERE policyname = 'invitacion_conservacion_leer'"
                     ) == [("{matu_owner}", "SELECT")]
    # C18: la lista de las políticas de operación que quedan, la del docstring
    filas = consultar("SELECT tablename, policyname FROM pg_policies WHERE roles::text <> '{matu_owner}'"
                      " AND coalesce(qual, '') || coalesce(with_check, '') LIKE '%''operacion''%'")
    quedan: dict[str, set[str]] = {}
    for tabla, politica in filas:
        quedan.setdefault(tabla, set()).add(politica)
    assert quedan == POLITICAS_OPERACION_0031
    # C2, C8 y O6: definer, dueño matu_owner, search_path fijo y EXECUTE solo de matu_app
    filas = consultar("SELECT proname, proacl::text, prosecdef, proconfig::text, pg_get_userbyid(proowner)"
                      " FROM pg_proc WHERE proname = ANY(ARRAY[" + ", ".join(f"'{x}'" for x in FUNCIONES_0031) + "])")
    assert {x[0] for x in filas} == set(FUNCIONES_0031)
    for nombre, acl, definer, config, dueno in filas:
        assert definer and dueno == "matu_owner" and "search_path=pg_catalog, public, pg_temp" in config, nombre
        assert set(acl.strip("{}").split(",")) == {"matu_owner=X/matu_owner", f"{FUNCIONES_0031[nombre]}=X/matu_owner"}
    # C3, C5 y O6: las funciones de la 0030 ya no leen usuario con los permisos de quien llama
    fuentes = dict(consultar("SELECT proname, prosrc FROM pg_proc WHERE proname IN ('incidencia_reglas',"
                             " 'sesion_refresh_mfa', 'operacion_buscar_cuenta')"))
    assert "operacion_cuenta_activa(NEW.creada_por)" in fuentes["incidencia_reglas"]
    assert "FROM usuario" not in fuentes["incidencia_reglas"]
    assert "cuenta_es_operacion(NEW.usuario_id)" in fuentes["sesion_refresh_mfa"]
    assert "set_config('app.funcion', 'cuentas', true)" in fuentes["operacion_buscar_cuenta"]
    # C12 y C13: matu_app no lee codigo_hash, sí codigo_vigente (generada)
    assert "codigo_hash" not in _columnas_con("pedido_comercio", "SELECT")
    assert "codigo_vigente" in _columnas_con("pedido_comercio", "SELECT")
    assert "SELECT" not in _privilegios("pedido_comercio")
    assert consultar("SELECT is_generated, generation_expression FROM information_schema.columns"
                     " WHERE table_name = 'pedido_comercio' AND column_name = 'codigo_vigente'") == [
        ("ALWAYS", "(codigo_hash IS NOT NULL)")]
    # C16
    [(qual,)] = consultar("SELECT qual FROM pg_policies WHERE policyname = 'clave_notas_familia_leer'")
    assert "app_escribe_plan()" in qual and "membresia" not in qual
    # J2: la acción nueva lleva persona
    assert _lista_del_check("auditoria_persona_obligatoria") == {a.value for a in ACCIONES_DE_PERSONA}

    # La bajada no borra nada: una fila de la acción nueva se queda, y el CHECK de la 0030 vuelve NOT VALID
    with psycopg.connect(_dsn(BASE)) as c:
        c.execute(f"INSERT INTO usuario (id, email, nombre, password_hash) VALUES ('{U}', 'a@correo.ejemplo', 'A',"
                  " 'h');"
                  f" INSERT INTO grupo_familiar (id, nombre, creado_por) VALUES ('{G}', 'Familia A', '{U}');"
                  f" INSERT INTO persona_cuidada (id, grupo_id, nombre, nombre_pila, nivel_apoyo)"
                  f" VALUES ('{P}', '{G}', 'Persona Cuidada', 'Persona', 'apoyo_total');"
                  f" INSERT INTO auditoria (grupo_id, actor_tipo, accion, entidad, entidad_id, persona_cuidada_id)"
                  f" VALUES ('{G}', 'operacion', 'operacion.retracto_correo_fallido', 'pedido', gen_random_uuid(),"
                  f" '{P}')")
    alembic("downgrade", "0030")
    assert consultar("SELECT count(*) FROM auditoria WHERE accion = 'operacion.retracto_correo_fallido'") == [(1,)]
    despues = catalogo()
    for parte, filas_0030 in esquema_0030.items():
        assert despues[parte] == filas_0030, f"downgrade no restaura {parte}: {set(filas_0030) ^ set(despues[parte])}"
    alembic("upgrade", "head")


# ---- 0033 (MATU-122): operación lee solo lo que usa

_SALEN_0033 = {"direccion": {"direccion_operacion_leer"}, "grupo_familiar": {"grupo_operacion"},
               "pedido_entrega": {"entrega_operacion_leer"}, "usuario_comercio": {"usuario_comercio_operacion"}}
_ENTRAN_0033 = {"direccion": {"direccion_no_operacion"}, "grupo_familiar": {"grupo_no_operacion"},
                "usuario_comercio": {"usuario_comercio_operacion_crear", "usuario_comercio_operacion_editar",
                                     "usuario_comercio_operacion_leer"}}
# Las políticas que no son TO matu_owner y miran app.rol = 'operacion', después de la 0033 (docstring de la migración)
_TRAS_0033 = {
    tabla: (POLITICAS_OPERACION_0031.get(tabla, set()) - _SALEN_0033.get(tabla, set())) | _ENTRAN_0033.get(tabla, set())
    for tabla in POLITICAS_OPERACION_0031.keys() | _ENTRAN_0033.keys()
}
POLITICAS_OPERACION_0033 = {tabla: politicas for tabla, politicas in _TRAS_0033.items() if politicas}
# Las nuevas que miran un marcador: solo las funciones de matu_owner
POLITICAS_MATU_OWNER_0033 = {
    ("pedido_entrega", "entrega_conservacion_leer", "SELECT"),
    ("pedido_entrega", "entrega_conservacion_borrar", "DELETE"),
    ("participacion", "participacion_conservacion_leer", "SELECT"),
    ("participacion", "participacion_solicitante_leer", "SELECT"),
    ("invitacion", "invitacion_conservacion_leer", "SELECT"),
    ("invitacion", "invitacion_conservacion_borrar", "DELETE"),
}


@pytest.mark.rf("RNF-07")
@pytest.mark.rf("Ley-21.719")
def test_0033_operacion_lee_lo_que_usa_y_baja_al_esquema_de_0032(base_desechable):
    alembic("upgrade", "0032")
    esquema_0032 = catalogo()
    alembic("upgrade", "0033")

    # C1, C2 y C3: salen las cuatro
    quitadas = consultar("SELECT policyname FROM pg_policies WHERE policyname IN ('usuario_comercio_operacion',"
                         " 'direccion_operacion_leer', 'entrega_operacion_leer', 'grupo_operacion')")
    assert quitadas == []
    # C8: la lista de las políticas de operación que quedan, la del docstring
    filas = consultar("SELECT tablename, policyname FROM pg_policies WHERE roles::text <> '{matu_owner}'"
                      " AND coalesce(qual, '') || coalesce(with_check, '') LIKE '%''operacion''%'")
    quedan: dict[str, set[str]] = {}
    for tabla, politica in filas:
        quedan.setdefault(tabla, set()).add(politica)
    assert quedan == POLITICAS_OPERACION_0033
    # Las de un marcador, solo TO matu_owner
    nuevas = {(t, n, c) for t, n, c, r in consultar(
        "SELECT tablename, policyname, cmd, roles::text FROM pg_policies WHERE roles::text = '{matu_owner}'"
        " AND policyname IN (" + ", ".join(f"'{n}'" for _, n, _ in POLITICAS_MATU_OWNER_0033) + ")")}
    assert nuevas == POLITICAS_MATU_OWNER_0033
    # C1: las cuentas de los comercios ficticios, TO matu_app y sin DELETE
    comercio = consultar("SELECT policyname, roles::text, cmd FROM pg_policies WHERE tablename = 'usuario_comercio'"
                         " AND policyname LIKE 'usuario_comercio_operacion%'")
    assert set(comercio) == {("usuario_comercio_operacion_leer", "{matu_app}", "SELECT"),
                             ("usuario_comercio_operacion_crear", "{matu_app}", "INSERT"),
                             ("usuario_comercio_operacion_editar", "{matu_app}", "UPDATE")}
    for cmd, qual, check in consultar("SELECT cmd, qual, with_check FROM pg_policies"
                                      " WHERE policyname LIKE 'usuario_comercio_operacion%'"):
        assert all("c.ficticio" in x for x in {"SELECT": (qual,), "INSERT": (check,), "UPDATE": (qual, check)}[cmd])
    # (e) y (f): las restrictivas, TO matu_app
    restrictivas = set(consultar("SELECT tablename, policyname, roles::text FROM pg_policies"
                                 " WHERE permissive = 'RESTRICTIVE' AND policyname IN ('direccion_no_operacion',"
                                 " 'grupo_no_operacion')"))
    assert restrictivas == {("direccion", "direccion_no_operacion", "{matu_app}"),
                            ("grupo_familiar", "grupo_no_operacion", "{matu_app}")}
    # C4: la devolución, TO matu_app, sin cuenta y con el grupo del contexto
    for _, roles, qual in consultar("SELECT policyname, roles::text, qual FROM pg_policies"
                                    " WHERE policyname IN ('participacion_operacion_leer',"
                                    " 'participacion_operacion_editar')"):
        assert roles == "{matu_app}" and "app_usuario() IS NULL" in qual and "app_grupo()" in qual
    fuentes = dict(consultar("SELECT proname, prosrc FROM pg_proc WHERE proname IN ('operacion_solicitante_retracto',"
                             " 'invitacion_conservar')"))
    assert "set_config('app.funcion', 'solicitante_retracto', true)" in fuentes["operacion_solicitante_retracto"]
    assert "set_config('app.funcion', 'invitacion_conservar', true)" in fuentes["invitacion_conservar"]
    # Observación 3 del QA: las dos cambian app.funcion, y son VOLATILE
    volatilidad = ("SELECT proname, provolatile FROM pg_proc WHERE proname IN ('operacion_solicitante_retracto',"
                   " 'invitacion_conservar')")
    assert dict(consultar(volatilidad)) == {"operacion_solicitante_retracto": "v", "invitacion_conservar": "v"}
    # C5
    [(qual,)] = consultar("SELECT qual FROM pg_policies WHERE policyname = 'incidencia_familia'")
    assert "app_escribe_plan()" in qual
    # C7: el trigger, y su función sin EXECUTE para PUBLIC
    assert consultar("SELECT tgname FROM pg_trigger WHERE tgrelid = 'comercio'::regclass"
                     " AND tgname = 'comercio_ficticio_fijo'") == [("comercio_ficticio_fijo",)]
    acl = {nombre: a for nombre, a in consultar(
        "SELECT proname, proacl::text FROM pg_proc WHERE proname IN ('comercio_ficticio_fijo',"
        " 'operacion_solicitante_retracto', 'invitacion_conservar')")}
    assert acl["comercio_ficticio_fijo"] == "{matu_owner=X/matu_owner}"
    assert set(acl["operacion_solicitante_retracto"].strip("{}").split(",")) == {"matu_owner=X/matu_owner",
                                                                                  "matu_app=X/matu_owner"}
    assert set(acl["invitacion_conservar"].strip("{}").split(",")) == {"matu_owner=X/matu_owner",
                                                                        "matu_scheduler=X/matu_owner"}

    # C9: la bajada deja el catálogo como en la 0032
    alembic("downgrade", "0032")
    despues = catalogo()
    for parte, filas_0032 in esquema_0032.items():
        assert despues[parte] == filas_0032, f"downgrade no restaura {parte}: {set(filas_0032) ^ set(despues[parte])}"
    # catalogo() no mira la volatilidad: la de la 0032
    assert dict(consultar(volatilidad)) == {"operacion_solicitante_retracto": "s", "invitacion_conservar": "v"}
    alembic("upgrade", "head")


# ---- 0034 (MATU-79, parte 3): el contacto de las cuentas y del relevo, y el registro de avisos

CONTACTO_0034 = {"email", "telefono", "celular_verificado_en", "celular_canal"}
FUNCIONES_0034 = {"cuenta_contacto_propia": "s", "aviso_correo": "v", "acceso_relevo_telefono": "s"}
# catalogo() mira information_schema.column_privileges; esto mira además los ACL tal cual, de tabla y de columna
_ACL_0034 = """
    SELECT c.relname, NULL::text, c.relacl::text FROM pg_class c
     WHERE c.relname IN ('usuario', 'acceso_relevo', 'notificacion') AND c.relnamespace = 'public'::regnamespace
    UNION ALL
    SELECT c.relname, a.attname::text, a.attacl::text FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid
     WHERE c.relname IN ('usuario', 'acceso_relevo', 'notificacion') AND c.relnamespace = 'public'::regnamespace
       AND a.attnum > 0 AND NOT a.attisdropped AND a.attacl IS NOT NULL
    ORDER BY 1, 2 NULLS FIRST"""


@pytest.mark.rf("RNF-07")
@pytest.mark.rf("Ley-21.719")
def test_0034_politicas_de_contacto_y_baja_al_esquema_de_0033(base_desechable):
    alembic("upgrade", "0033")
    esquema_0033 = catalogo()
    acl_0033 = consultar(_ACL_0034)
    columnas_acceso = {c for (c,) in consultar("SELECT column_name FROM information_schema.columns"
                                               " WHERE table_name = 'acceso_relevo'")}
    alembic("upgrade", "0034")

    # A1: matu_app no lee el contacto de ninguna cuenta; el resto de lo que leía sigue
    legibles = _columnas_con("usuario", "SELECT")
    assert not CONTACTO_0034 & legibles
    assert {"id", "nombre", "estado", "eliminado_en", "es_operacion", "creado_en"} <= legibles
    # La cuenta sigue cambiando su celular y su contraseña (UPDATE por columna, como desde la 0020)
    assert _columnas_con("usuario", "UPDATE") == {
        "password_hash", "telefono", "celular_verificado_en", "celular_canal", "actualizado_en"}
    # A4: acceso_relevo sin SELECT de tabla, con todas las columnas menos el teléfono
    assert _privilegios("acceso_relevo") == {"INSERT"}
    assert _columnas_con("acceso_relevo", "SELECT") == columnas_acceso - {"otorgado_a_telefono"}
    # A7 y D3: notificacion sin DELETE, UPDATE solo de estado, error y enviada_en, y ninguna política ALL
    assert _privilegios("notificacion") == {"SELECT", "INSERT"}
    assert _columnas_con("notificacion", "UPDATE") == {"estado", "error", "enviada_en"}
    politicas = {(n, c, r) for n, c, r in consultar(
        "SELECT policyname, cmd, roles::text FROM pg_policies WHERE tablename = 'notificacion'")}
    assert not [p for p in politicas if p[1] == "ALL"]
    assert {p for p in politicas if p[0].startswith("notificacion_sistema")} == {
        ("notificacion_sistema_leer", "SELECT", "{matu_app}"), ("notificacion_sistema_crear", "INSERT", "{matu_app}"),
        ("notificacion_sistema_editar", "UPDATE", "{matu_app}")}
    for qual, check in consultar("SELECT coalesce(qual, ''), coalesce(with_check, '') FROM pg_policies"
                                 " WHERE policyname LIKE 'notificacion_sistema_%'"):
        for expresion in filter(None, (qual, check)):
            assert "'sistema'" in expresion and "app_usuario() IS NULL" in expresion and "app_grupo()" in expresion
    # A3: la política del marcador, solo TO matu_owner
    assert consultar("SELECT roles::text, cmd, qual FROM pg_policies WHERE policyname = 'usuario_aviso_correo'") == [
        ("{matu_owner}", "SELECT", "(current_setting('app.funcion'::text, true) = 'aviso_correo'::text)")]
    # A2, A3 y A5: definer de matu_owner, search_path fijo, EXECUTE solo para matu_app, VOLATILE la que fija app.funcion
    funciones = {n: (d, v, c, a, o) for n, d, v, c, a, o in consultar(
        "SELECT proname, prosecdef, provolatile, proconfig, proacl::text, pg_get_userbyid(proowner) FROM pg_proc"
        " WHERE proname IN ('cuenta_contacto_propia', 'aviso_correo', 'acceso_relevo_telefono')")}
    assert set(funciones) == set(FUNCIONES_0034)
    for nombre, (definer, volatilidad, config, acl, dueno) in funciones.items():
        assert definer and dueno == "matu_owner", nombre
        assert volatilidad == FUNCIONES_0034[nombre], nombre
        assert config == ["search_path=pg_catalog, public, pg_temp"], nombre
        assert set(acl.strip("{}").split(",")) == {"matu_owner=X/matu_owner", "matu_app=X/matu_owner"}, nombre
    assert "set_config('app.funcion', 'aviso_correo', true)" in consultar(
        "SELECT prosrc FROM pg_proc WHERE proname = 'aviso_correo'")[0][0]

    # La bajada deja el catálogo, y los ACL de tabla y de columna, como en la 0033
    alembic("downgrade", "0033")
    despues = catalogo()
    for parte, filas_0033 in esquema_0033.items():
        assert despues[parte] == filas_0033, f"downgrade no restaura {parte}: {set(filas_0033) ^ set(despues[parte])}"
    assert consultar(_ACL_0034) == acl_0033
    assert consultar("SELECT cmd, roles::text FROM pg_policies WHERE policyname = 'notificacion_sistema'") == [
        ("ALL", "{public}")]
    assert consultar("SELECT count(*) FROM pg_proc WHERE proname IN ('cuenta_contacto_propia', 'aviso_correo',"
                     " 'acceso_relevo_telefono')") == [(0,)]
    alembic("upgrade", "head")


# ---- 0036 (MATU-128): quien pagó un pedido ve lo que pasó con él

# La anterior de la 0036: hoy la 0034; con la 0035 de MATU-124 en la rama, la 0035. Se lee de la migración
ANTES_0036 = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini"))).get_revision("0036").down_revision
# C3 y C10: las dos nuevas, con el marcador, solo TO matu_owner
POLITICAS_MATU_OWNER_0036 = {
    ("incidencia", "incidencia_lo_que_paso", "SELECT"),
    ("clave_notas", "clave_notas_lo_que_paso", "SELECT"),
}
# C2: las columnas de la función, en orden. Nunca creada_por, asignada_a ni version
COLUMNAS_0036 = [
    "id", "tipo", "estado", "creada_en", "resuelta_en", "descripcion", "clave_notas_id", "resolucion",
    "resolucion_clave_id", "nota_dek_cifrada", "nota_kek_version", "resolucion_dek_cifrada", "resolucion_kek_version",
]


@pytest.mark.rf("RNF-07")
@pytest.mark.rf("Ley-21.719")
def test_0036_lo_que_paso_de_quien_pago_y_baja_al_esquema_anterior(base_desechable):
    assert isinstance(ANTES_0036, str)
    alembic("upgrade", ANTES_0036)
    esquema_antes = catalogo()
    politicas_antes = {n: (q, r) for n, q, r in consultar(
        "SELECT policyname, qual, roles::text FROM pg_policies"
        " WHERE policyname IN ('incidencia_familia', 'clave_notas_familia_leer')")}
    alembic("upgrade", "0036")

    # C3: las dos políticas, SELECT y TO matu_owner, con el marcador y el rol de una sesión de familia
    nuevas = consultar("SELECT tablename, policyname, cmd, roles::text, qual FROM pg_policies"
                       " WHERE policyname LIKE '%lo_que_paso'")
    assert {(t, n, c) for t, n, c, _, _ in nuevas} == POLITICAS_MATU_OWNER_0036
    for _, nombre, _, roles, qual in nuevas:
        assert roles == "{matu_owner}", nombre
        assert "current_setting('app.funcion'::text, true) = 'lo_que_paso'::text" in qual, nombre
        assert "app_rol() = 'ninguno'::text" in qual and "app_grupo()" in qual, nombre
    [(qual_incidencia,)] = consultar("SELECT qual FROM pg_policies WHERE policyname = 'incidencia_lo_que_paso'")
    assert "app_pago_el_pedido(pedido_id)" in qual_incidencia
    # C4: las de la familia no cambian
    assert {n: (q, r) for n, q, r in consultar(
        "SELECT policyname, qual, roles::text FROM pg_policies"
        " WHERE policyname IN ('incidencia_familia', 'clave_notas_familia_leer')")} == politicas_antes
    # C1: definer de matu_owner, VOLATILE, search_path fijo y EXECUTE solo para matu_app
    [(definer, volatilidad, config, acl, dueno, nombres, fuente)] = consultar(
        "SELECT prosecdef, provolatile, proconfig, proacl::text, pg_get_userbyid(proowner), proargnames, prosrc"
        " FROM pg_proc WHERE proname = 'pedido_lo_que_paso'")
    assert definer and volatilidad == "v" and dueno == "matu_owner"
    assert config == ["search_path=pg_catalog, public, pg_temp"]
    assert set(acl.strip("{}").split(",")) == {"matu_owner=X/matu_owner", "matu_app=X/matu_owner"}
    # C2: el parámetro y las columnas fijas
    assert nombres == ["p_pedido", *COLUMNAS_0036]
    assert not {"creada_por", "asignada_a", "version"} & set(nombres)
    # El marcador se fija después de app_pago_el_pedido y antes de leer, y se devuelve al salir
    assert fuente.index("app_pago_el_pedido") < fuente.index("'lo_que_paso'") < fuente.index("FROM public.incidencia")
    assert "set_config('app.funcion', COALESCE(v_antes, ''), true)" in fuente

    # C10: la bajada quita la función y las políticas y deja el catálogo como antes, sin borrar filas
    alembic("downgrade", ANTES_0036)
    despues = catalogo()
    for parte, filas_antes in esquema_antes.items():
        assert despues[parte] == filas_antes, f"downgrade no restaura {parte}: {set(filas_antes) ^ set(despues[parte])}"
    assert consultar("SELECT count(*) FROM pg_proc WHERE proname = 'pedido_lo_que_paso'") == [(0,)]
    alembic("upgrade", "head")
