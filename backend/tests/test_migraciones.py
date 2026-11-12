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
# La base desechable. MATU_BASE_MIGRACIONES la cambia para que dos worktrees no se pisen en el mismo servidor
BASE = os.environ.get("MATU_BASE_MIGRACIONES", "matu_prueba_migraciones")

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
        # Solo el borrador: el pedido pagado de la 0023 no tiene quién aceptó, y pedido_condiciones_completas (NOT VALID)
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
