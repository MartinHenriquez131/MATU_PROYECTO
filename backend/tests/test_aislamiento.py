"""
MATU · Pruebas de aislamiento del modelo de datos contra PostgreSQL real.

Arquitectura, secciones 7.7 y 12.5. Requiere una base recién migrada:
roles y base con infra/postgres/init/10_matu.sh y esquema con `alembic upgrade head`.

    pytest -q tests/

La conexión se toma de MATU_TEST_DSN (archivo .env o variable del pipeline). Es de
superusuario solo para sembrar datos. Cada verificación corre con SET ROLE matu_app
(o el rol que corresponda), que NO evade RLS.
"""
import os
import uuid
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv
from psycopg import errors

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
DSN = os.environ.get("MATU_TEST_DSN", "host=localhost port=5432 user=postgres dbname=matu")

# Identificadores fijos para leer las pruebas con facilidad
U_ADMIN_A, U_OBS_A, U_PAG_A, U_PAG2_A = (uuid.UUID(f"00000000-0000-0000-0000-0000000000a{i}") for i in (1, 2, 3, 4))
U_ADMIN_B = uuid.UUID("00000000-0000-0000-0000-0000000000b1")
U_ENC = uuid.UUID("00000000-0000-0000-0000-0000000000c1")
U_REP = uuid.UUID("00000000-0000-0000-0000-0000000000d1")
U_NUEVO = uuid.UUID("00000000-0000-0000-0000-0000000000e1")
G_A = uuid.UUID("00000000-0000-0000-0000-00000000000a")
G_B = uuid.UUID("00000000-0000-0000-0000-00000000000b")
P_A = uuid.UUID("00000000-0000-0000-0000-0000000001a0")
P_B = uuid.UUID("00000000-0000-0000-0000-0000000001b0")
PLAN_A = uuid.UUID("00000000-0000-0000-0000-0000000002a0")
PLAN_B = uuid.UUID("00000000-0000-0000-0000-0000000002b0")
ACC_VIGENTE = uuid.UUID("00000000-0000-0000-0000-0000000003a1")
ACC_VENCIDO = uuid.UUID("00000000-0000-0000-0000-0000000003a2")
ACC_REVOCADO = uuid.UUID("00000000-0000-0000-0000-0000000003a3")
COMERCIO = uuid.UUID("00000000-0000-0000-0000-0000000004c1")
REPARTIDOR = uuid.UUID("00000000-0000-0000-0000-0000000005d1")
PED_A_ENVIADO = uuid.UUID("00000000-0000-0000-0000-0000000006a1")
PED_A_BORRADOR = uuid.UUID("00000000-0000-0000-0000-0000000006a2")
PED_B_ENVIADO = uuid.UUID("00000000-0000-0000-0000-0000000006b1")

INFRA_SIN_RLS = {"evento_outbox", "evento_consumido", "indice_token", "indice_credencial"}
REFERENCIA_PUBLICA = {"categoria_cuidado", "producto", "oferta", "comercio"}

SEMILLA = f"""
TRUNCATE usuario, grupo_familiar, comercio, categoria_cuidado, evento_outbox, evento_consumido,
         indice_token, auditoria RESTART IDENTITY CASCADE;
INSERT INTO usuario (id, email, nombre, password_hash) VALUES
 ('{U_ADMIN_A}', 'admin.a@x.cl', 'Admin A', 'h'), ('{U_OBS_A}', 'obs.a@x.cl', 'Obs A', 'h'),
 ('{U_PAG_A}', 'pag.a@x.cl', 'Pag A', 'h'),       ('{U_PAG2_A}', 'pag2.a@x.cl', 'Pag2 A', 'h'),
 ('{U_ADMIN_B}', 'admin.b@x.cl', 'Admin B', 'h'), ('{U_ENC}', 'enc@comercio.cl', 'Encargado', 'h'),
 ('{U_REP}', 'rep@x.cl', 'Repartidor', 'h'),      ('{U_NUEVO}', 'nuevo@x.cl', 'Nuevo', 'h');
INSERT INTO grupo_familiar (id, nombre, creado_por) VALUES
 ('{G_A}', 'Familia A', '{U_ADMIN_A}'), ('{G_B}', 'Familia B', '{U_ADMIN_B}');
INSERT INTO membresia (grupo_id, usuario_id, rol, puede_ver_plan) VALUES
 ('{G_A}', '{U_ADMIN_A}', 'admin', false), ('{G_A}', '{U_OBS_A}', 'observador', false),
 ('{G_A}', '{U_PAG_A}', 'pagador', false),  ('{G_A}', '{U_PAG2_A}', 'pagador', true),
 ('{G_B}', '{U_ADMIN_B}', 'admin', false);
INSERT INTO direccion (id, grupo_id, calle, numero, comuna) VALUES
 ('00000000-0000-0000-0000-00000000d1a0', '{G_A}', 'Los Aromos', '123', 'La Reina');
INSERT INTO persona_cuidada (id, grupo_id, nombre, nombre_pila, nivel_apoyo, direccion_entrega_id) VALUES
 ('{P_A}', '{G_A}', 'María Soto', 'María', 'apoyo_total', '00000000-0000-0000-0000-00000000d1a0'),
 ('{P_B}', '{G_B}', 'Luis Pérez', 'Luis', 'apoyo_parcial', NULL);
INSERT INTO clave_datos (grupo_id, persona_cuidada_id, dek_cifrada_con_kek, kek_version) VALUES
 ('{G_A}', '{P_A}', '\\x01', 1), ('{G_B}', '{P_B}', '\\x02', 1);
INSERT INTO plan_cuidado (id, grupo_id, persona_cuidada_id) VALUES
 ('{PLAN_A}', '{G_A}', '{P_A}'), ('{PLAN_B}', '{G_B}', '{P_B}');
INSERT INTO plan_seccion (plan_id, tipo, contenido_cifrado, nonce, tag_auth, kek_version) VALUES
 ('{PLAN_A}', 'rutina',             '\\xaa', '\\x000000000000000000000001', '\\x00000000000000000000000000000000', 1),
 ('{PLAN_A}', 'manejo_situaciones', '\\xaa', '\\x000000000000000000000002', '\\x00000000000000000000000000000000', 1),
 ('{PLAN_A}', 'red_apoyo',          '\\xaa', '\\x000000000000000000000003', '\\x00000000000000000000000000000000', 1),
 ('{PLAN_B}', 'rutina',             '\\xbb', '\\x000000000000000000000004', '\\x00000000000000000000000000000000', 1);
INSERT INTO acceso_relevo (id, grupo_id, plan_id, otorgado_por, otorgado_a_nombre, otorgado_a_telefono,
                           nombre_pila_persona, nombre_pila_comparte, secciones_permitidas, motivo, token_hash,
                           pin_hash, expira_en, relevo_informado_en) VALUES
 ('{ACC_VIGENTE}',  '{G_A}', '{PLAN_A}', '{U_ADMIN_A}', 'Relevo',   '+56911111111', 'María', 'Ana',
  ARRAY['rutina','manejo_situaciones'], 'fin de semana', sha256('t1'), 'p', now() + interval '1 day', now()),
 ('{ACC_VENCIDO}',  '{G_A}', '{PLAN_A}', '{U_ADMIN_A}', 'Vencido',  '+56922222222', 'María', 'Ana',
  ARRAY['rutina'], 'turno', sha256('t2'), 'p', now() + interval '1 day', now()),
 ('{ACC_REVOCADO}', '{G_A}', '{PLAN_A}', '{U_ADMIN_A}', 'Revocado', '+56933333333', 'María', 'Ana',
  ARRAY['rutina'], 'turno', sha256('t3'), 'p', now() + interval '1 day', now());
UPDATE acceso_relevo SET creado_en = now() - interval '3 days', expira_en = now() - interval '1 day'
 WHERE id = '{ACC_VENCIDO}';
UPDATE acceso_relevo SET revocado_en = now() WHERE id = '{ACC_REVOCADO}';

INSERT INTO categoria_cuidado (id, nombre) VALUES ('00000000-0000-0000-0000-000000000c01', 'Incontinencia');
INSERT INTO producto (id, categoria_id, nombre, presentacion, unidad, unidades_por_envase) VALUES
 ('00000000-0000-0000-0000-000000000f01', '00000000-0000-0000-0000-000000000c01',
  'Pañal adulto M', 'x30', 'unidad', 30);
INSERT INTO comercio (id, razon_social, nombre_fantasia, rut, direccion, comuna) VALUES
 ('{COMERCIO}', 'Farmacia Uno SpA', 'Farmacia Uno', '76.000.000-1', 'Av. Larraín 1', 'La Reina');
INSERT INTO usuario_comercio (usuario_id, comercio_id) VALUES ('{U_ENC}', '{COMERCIO}');
INSERT INTO oferta (id, producto_id, comercio_id, precio) VALUES
 ('00000000-0000-0000-0000-000000000f11', '00000000-0000-0000-0000-000000000f01', '{COMERCIO}', 12990);
INSERT INTO perfil_consumo (grupo_id, persona_cuidada_id, producto_id, tasa_unidades, stock_unidades,
                            stock_medido_en, fecha_quiebre_estimada) VALUES
 ('{G_A}', '{P_A}', '00000000-0000-0000-0000-000000000f01', 4, 24, current_date, current_date + 6),
 ('{G_B}', '{P_B}', '00000000-0000-0000-0000-000000000f01', 3, 30, current_date, current_date + 10);

-- Los pedidos nacen en borrador con sus líneas. Las líneas de un pedido pagado ya no cambian
-- (ADR-027), así que el pago y el envío al comercio van después.
INSERT INTO pedido (id, grupo_id, persona_cuidada_id, comercio_id, estado, subtotal_productos, costo_envio, total,
                    destinatario_nombre_pila, creado_por) VALUES
 ('{PED_A_ENVIADO}',  '{G_A}', '{P_A}', '{COMERCIO}', 'borrador', 25980, 2990, 28970, 'María', '{U_ADMIN_A}'),
 ('{PED_A_BORRADOR}', '{G_A}', '{P_A}', '{COMERCIO}', 'borrador', 12990, 2990, 15980, 'María', '{U_ADMIN_A}'),
 ('{PED_B_ENVIADO}',  '{G_B}', '{P_B}', '{COMERCIO}', 'borrador', 12990, 2990, 15980, 'Luis',  '{U_ADMIN_B}');
INSERT INTO pedido_entrega (pedido_id, calle, numero, comuna, telefono_contacto) VALUES
 ('{PED_A_ENVIADO}', 'Los Aromos', '123', 'La Reina', '+56911111111');
INSERT INTO pedido_linea (pedido_id, oferta_id, producto_id, cantidad, precio_unitario) VALUES
 ('{PED_A_ENVIADO}',  '00000000-0000-0000-0000-000000000f11', '00000000-0000-0000-0000-000000000f01', 2, 12990),
 ('{PED_A_BORRADOR}', '00000000-0000-0000-0000-000000000f11', '00000000-0000-0000-0000-000000000f01', 1, 12990);
UPDATE pedido SET estado = 'enviado_a_comercio', total_confirmado_en = now() - interval '5 minutes',
                  total_vence_en = now() + interval '10 minutes', pagado_en = now()
 WHERE id IN ('{PED_A_ENVIADO}', '{PED_B_ENVIADO}');
INSERT INTO cargo (id, pedido_id, estado, monto_cobrado) VALUES
 ('00000000-0000-0000-0000-0000000007a1', '{PED_A_ENVIADO}', 'pagado', 28970);
INSERT INTO participacion (id, cargo_id, usuario_id, porcentaje_bp, estado, monto_cobrado) VALUES
 ('00000000-0000-0000-0000-0000000008a1', '00000000-0000-0000-0000-0000000007a1', '{U_ADMIN_A}', 10000,
  'pagada', 28970);
INSERT INTO transaccion_pasarela (participacion_id, proveedor, tipo, buy_order, monto, estado, idempotency_key) VALUES
 ('00000000-0000-0000-0000-0000000008a1', 'webpay_plus', 'venta', 'MATU-0001', 28970, 'aprobada', 'k1');
INSERT INTO repartidor (id, usuario_id, vehiculo, comuna_base) VALUES ('{REPARTIDOR}', '{U_REP}', 'auto', 'La Reina');
INSERT INTO asignacion (grupo_id, pedido_id, repartidor_id) VALUES ('{G_A}', '{PED_A_ENVIADO}', '{REPARTIDOR}');
INSERT INTO idempotencia (grupo_id, endpoint, clave, usuario_id, hash_peticion, respuesta) VALUES
 ('{G_A}', 'POST /v1/pedidos', 'k-a', '{U_ADMIN_A}', '\\x00', '{{"id": "x"}}'),
 ('{G_B}', 'POST /v1/pedidos', 'k-b', '{U_ADMIN_B}', '\\x00', '{{"id": "y"}}');
"""

CONTEXTO = ("usuario_id", "grupo_id", "comercio_id", "repartidor_id", "rol", "acceso_relevo_id")


@pytest.fixture(scope="session", autouse=True)
def semilla():
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute(SEMILLA)


@pytest.fixture
def cx():
    """Conexión en transacción que se revierte al final de cada prueba."""
    with psycopg.connect(DSN) as c:
        yield c
        c.rollback()


def como(cx, db_rol="matu_app", **ctx):
    """Cambia al rol de base de datos indicado y fija el contexto de sesión (local a la transacción)."""
    cx.execute(f"SET LOCAL ROLE {db_rol}")
    for k in CONTEXTO:
        v = ctx.get(k)
        cx.execute("SELECT set_config(%s, %s, true)", (f"app.{k}", "" if v is None else str(v)))
    return cx


def contar(cx, tabla, where="true"):
    return cx.execute(f"SELECT count(*) FROM {tabla} WHERE {where}").fetchone()[0]


def tablas_publicas(cx):
    return [r[0] for r in cx.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1").fetchall()]


# ------------------------------------------------------------------ estructura

def test_force_activo_tabla_por_tabla(cx):
    """El escenario 'RLS finge proteger' no puede ocurrir en ninguna tabla de negocio."""
    filas = cx.execute("""
        SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'""").fetchall()
    for nombre, rls, force in filas:
        if nombre in INFRA_SIN_RLS:
            assert not rls, f"{nombre} es infraestructura declarada y no debe tener RLS"
        else:
            assert rls and force, f"{nombre} no tiene RLS forzado"


def test_rol_de_aplicacion_no_es_propietario(cx):
    duenos = {r[0] for r in cx.execute(
        "SELECT DISTINCT tableowner FROM pg_tables WHERE schemaname = 'public'").fetchall()}
    assert duenos == {"matu_owner"}
    bypass = cx.execute("SELECT rolbypassrls OR rolsuper FROM pg_roles WHERE rolname = 'matu_app'").fetchone()[0]
    assert not bypass


# ------------------------------------------------------------------ contexto

def test_sin_contexto_cero_filas(cx):
    """Una consulta sin app.grupo_id no devuelve todo: devuelve nada."""
    como(cx)
    for t in tablas_publicas(cx):
        if t in INFRA_SIN_RLS | REFERENCIA_PUBLICA:
            continue
        assert contar(cx, t) == 0, f"{t} devuelve filas sin contexto"


def test_worker_sin_contexto_cero_filas(cx):
    """El rol sistema sin grupo no alcanza nada (hueco del diseño anterior)."""
    como(cx, rol="sistema")
    for t in ("perfil_consumo", "alerta_quiebre", "pedido", "plan_reposicion", "notificacion"):
        assert contar(cx, t) == 0, t


def test_worker_con_contexto_ve_solo_su_grupo(cx):
    como(cx, grupo_id=G_A, rol="sistema")
    assert contar(cx, "perfil_consumo") == 1
    assert contar(cx, "perfil_consumo", f"grupo_id = '{G_B}'") == 0


# ------------------------------------------------------------------ familia

def test_grupo_a_no_ve_grupo_b(cx):
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    assert contar(cx, "persona_cuidada") == 1
    assert contar(cx, "pedido", f"id = '{PED_B_ENVIADO}'") == 0
    assert contar(cx, "plan_cuidado", f"id = '{PLAN_B}'") == 0
    assert contar(cx, "usuario", f"id = '{U_ADMIN_B}'") == 0


def test_idempotencia_de_otro_grupo_cero_filas(cx):
    """Regresión del defecto 4 de la sección 12.8."""
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    assert contar(cx, "idempotencia") == 1
    assert contar(cx, "idempotencia", "clave = 'k-b'") == 0


@pytest.mark.parametrize("usuario, ve_plan", [
    (U_ADMIN_A, True),   # admin
    (U_OBS_A, False),    # observador: nunca
    (U_PAG_A, False),    # pagador sin permiso explícito
    (U_PAG2_A, True),    # pagador con permiso explícito
])
def test_rol_de_membresia_decide_el_plan(cx, usuario, ve_plan):
    como(cx, usuario_id=usuario, grupo_id=G_A)
    esperado = 3 if ve_plan else 0
    assert contar(cx, "plan_seccion") == esperado
    assert contar(cx, "clave_datos") == (1 if ve_plan else 0)
    # el perfil de consumo sí lo ve todo miembro (sección 11.2)
    assert contar(cx, "perfil_consumo") == 1


def test_alta_de_grupo_desde_cero(cx):
    """Un usuario nuevo crea su grupo y queda como admin, sin contexto de grupo previo."""
    como(cx, usuario_id=U_NUEVO)
    g = cx.execute("INSERT INTO grupo_familiar (nombre, creado_por) VALUES ('Nueva', %s) RETURNING id",
                   (U_NUEVO,)).fetchone()[0]
    cx.execute("INSERT INTO membresia (grupo_id, usuario_id, rol) VALUES (%s, %s, 'admin')", (g, U_NUEVO))
    assert contar(cx, "grupo_familiar") == 1


def test_no_puede_autoproclamarse_admin_de_grupo_ajeno(cx):
    como(cx, usuario_id=U_NUEVO)
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("INSERT INTO membresia (grupo_id, usuario_id, rol) VALUES (%s, %s, 'admin')", (G_A, U_NUEVO))


# ------------------------------------------------------------------ operación

def test_operacion_no_alcanza_plan_ni_consumo(cx):
    """La celda 'operación · plan de cuidado · nunca' de la sección 11.2 es cierta."""
    como(cx, usuario_id=U_ADMIN_B, rol="operacion")
    for t in ("plan_cuidado", "plan_seccion", "clave_datos", "acceso_relevo",
              "perfil_consumo", "reposicion", "alerta_quiebre"):
        assert contar(cx, t) == 0, f"operación alcanza {t}"
    assert contar(cx, "pedido") == 3
    assert contar(cx, "persona_cuidada") == 2


# ------------------------------------------------------------------ relevo

@pytest.mark.rf("RF-05")
def test_familia_no_ve_ni_crea_accesos_de_relevo_de_otro_grupo(cx):
    """MATU-18: la familia B no ve los accesos de A ni puede crear uno sobre el plan de A."""
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    assert contar(cx, "acceso_relevo") == 3
    assert {r[0] for r in cx.execute("SELECT nombre_pila_comparte FROM acceso_relevo").fetchall()} == {"Ana"}
    como(cx, usuario_id=U_ADMIN_B, grupo_id=G_B)
    assert contar(cx, "acceso_relevo") == 0
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute(
            """INSERT INTO acceso_relevo (grupo_id, plan_id, otorgado_por, otorgado_a_nombre, otorgado_a_telefono,
                   nombre_pila_persona, nombre_pila_comparte, secciones_permitidas, motivo, token_hash, pin_hash,
                   expira_en, relevo_informado_en)
               VALUES (%s, %s, %s, 'Relevo', '+56955550137', 'María', 'Luis', ARRAY['rutina'], 'otro',
                   sha256('t9'), 'p', now() + interval '1 day', now())""", (G_A, PLAN_A, U_ADMIN_B))


def test_relevo_ve_exactamente_sus_secciones(cx):
    como(cx, rol="relevo", acceso_relevo_id=ACC_VIGENTE)
    tipos = {r[0] for r in cx.execute("SELECT tipo FROM plan_seccion").fetchall()}
    assert tipos == {"rutina", "manejo_situaciones"}
    assert contar(cx, "acceso_relevo") == 1          # no ve los otros accesos
    assert contar(cx, "clave_datos") == 1            # puede descifrar solo a esa persona


# ---- MATU-50 (migración 0013): secciones complementarias y lo que ve el relevo

ACC_SECCIONES = uuid.UUID("00000000-0000-0000-0000-0000000003a4")
_TAG = bytes(16)


def _seccion(cx, plan, tipo, nonce, creado_en):
    cx.execute(
        "INSERT INTO plan_seccion (plan_id, tipo, contenido_cifrado, nonce, tag_auth, kek_version, creado_en)"
        f" VALUES (%s, %s, %s, %s, %s, 1, {creado_en})", (plan, tipo, b"\xcc", bytes.fromhex(nonce), _TAG))


def _acceso_con_secciones(cx, permitidas):
    cx.execute(
        """INSERT INTO acceso_relevo (id, grupo_id, plan_id, otorgado_por, otorgado_a_nombre, otorgado_a_telefono,
               nombre_pila_persona, nombre_pila_comparte, secciones_permitidas, motivo, token_hash, pin_hash,
               creado_en, expira_en, relevo_informado_en)
           VALUES (%s, %s, %s, %s, 'Relevo', '+56944444444', 'María', 'Ana', %s, 'otro', sha256('t4'), 'p',
               now() - interval '1 hour', now() + interval '1 day', now())""",
        (ACC_SECCIONES, G_A, PLAN_A, U_ADMIN_A, permitidas))


@pytest.mark.rf("RF-03")
def test_relevo_no_ve_secciones_agregadas_despues_de_su_acceso(cx):
    """seccion_relevo: una sección complementaria compartida solo se ve si nació antes que el acceso (o en el
    mismo instante). Los tres campos base se ven siempre. Una no compartida no se ve nunca."""
    _acceso_con_secciones(cx, ["rutina", "red_apoyo", "comunicacion", "remedios", "quien_es"])
    _seccion(cx, PLAN_A, "comunicacion", "0000000000000000000050a1", "now() - interval '2 hours'")
    _seccion(cx, PLAN_A, "quien_es", "0000000000000000000050a2", "now() - interval '1 hour'")  # mismo instante
    _seccion(cx, PLAN_A, "remedios", "0000000000000000000050a3", "now()")                       # después
    _seccion(cx, PLAN_A, "preferencias", "0000000000000000000050a4", "now() - interval '3 hours'")  # no compartida
    como(cx, rol="relevo", acceso_relevo_id=ACC_SECCIONES)
    tipos = {r[0] for r in cx.execute("SELECT tipo FROM plan_seccion").fetchall()}
    assert tipos == {"rutina", "red_apoyo", "comunicacion", "quien_es"}


@pytest.mark.rf("RF-03")
def test_creado_en_de_una_seccion_no_cambia_al_editarla(cx):
    """El trigger plan_seccion_creado_fijo impide adelantar creado_en para que un relevo vea una sección
    agregada después de su acceso, o atrasarlo para ocultársela."""
    _seccion(cx, PLAN_A, "remedios", "0000000000000000000050b1", "now() - interval '2 hours'")
    antes = cx.execute("SELECT creado_en FROM plan_seccion WHERE plan_id = %s AND tipo = 'remedios'",
                       (PLAN_A,)).fetchone()[0]
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    cx.execute("UPDATE plan_seccion SET creado_en = now() - interval '10 days', version = version + 1"
               " WHERE plan_id = %s AND tipo = 'remedios'", (PLAN_A,))
    assert cx.execute("SELECT creado_en, version FROM plan_seccion WHERE plan_id = %s AND tipo = 'remedios'",
                      (PLAN_A,)).fetchone() == (antes, 2)


@pytest.mark.rf("RF-03")
def test_familia_no_ve_ni_crea_secciones_complementarias_de_otro_grupo(cx):
    _seccion(cx, PLAN_A, "remedios", "0000000000000000000050c1", "now()")
    como(cx, usuario_id=U_ADMIN_B, grupo_id=G_B)
    assert contar(cx, "plan_seccion", f"plan_id = '{PLAN_A}'") == 0
    assert cx.execute("DELETE FROM plan_seccion WHERE plan_id = %s RETURNING id", (PLAN_A,)).fetchall() == []
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute(
            "INSERT INTO plan_seccion (plan_id, tipo, contenido_cifrado, nonce, tag_auth, kek_version)"
            " VALUES (%s, 'quien_es', %s, %s, %s, 1)",
            (PLAN_A, b"\xcc", bytes.fromhex("0000000000000000000050c2"), _TAG))


class _Deshacer(Exception):
    """Sale de sesion_tenant con rollback: la prueba no deja cambios en la semilla."""


@pytest.fixture
def sesiones_app():
    """Sesiones como matu_app (DATABASE_URL), la misma conexión que usa la API."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.config import obtener_configuracion

    url = obtener_configuracion().database_url
    if not url:
        pytest.skip("DATABASE_URL no está definida")
    engine = create_engine(url, pool_size=1, max_overflow=0)
    try:
        yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    finally:
        engine.dispose()


@pytest.mark.rf("RF-03")
def test_pagador_con_plan_lee_secciones_pero_no_las_escribe_ni_borra(sesiones_app):
    """Decisión 102 (migración 0013): el pagador con puede_ver_plan lee plan_seccion, pero con SQL directo,
    como matu_app y con su contexto fijado por sesion_tenant, no inserta, no edita ni borra. El admin sí."""
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from app.core.db import sesion_tenant

    filtro = {"plan": PLAN_A}
    with sesion_tenant(sesiones_app, usuario_id=U_PAG2_A, grupo_id=G_A) as s:
        assert {r[0] for r in s.execute(text("SELECT tipo FROM plan_seccion WHERE plan_id = :plan"), filtro)} == {
            "rutina", "manejo_situaciones", "red_apoyo"}
        editadas = s.execute(text("UPDATE plan_seccion SET version = version + 1 WHERE plan_id = :plan"), filtro)
        borradas = s.execute(text("DELETE FROM plan_seccion WHERE plan_id = :plan"), filtro)
        assert (editadas.rowcount, borradas.rowcount) == (0, 0)  # type: ignore[attr-defined]
    with pytest.raises(DBAPIError) as error, sesion_tenant(sesiones_app, usuario_id=U_PAG2_A, grupo_id=G_A) as s:
        s.execute(
            text("INSERT INTO plan_seccion (plan_id, tipo, contenido_cifrado, nonce, tag_auth, kek_version)"
                 " VALUES (:plan, 'quien_es', :c, :n, :t, 1)"),
            {**filtro, "c": b"\xcc", "n": bytes.fromhex("0000000000000000000050d1"), "t": _TAG},
        )
    assert isinstance(error.value.orig, errors.InsufficientPrivilege)

    # Nada cambió, y el admin del mismo grupo sí edita (se deshace al final)
    with pytest.raises(_Deshacer), sesion_tenant(sesiones_app, usuario_id=U_ADMIN_A, grupo_id=G_A) as s:
        versiones = s.execute(text("SELECT version FROM plan_seccion WHERE plan_id = :plan"), filtro).scalars().all()
        assert versiones == [1, 1, 1]
        editadas = s.execute(text("UPDATE plan_seccion SET version = version + 1 WHERE plan_id = :plan"), filtro)
        assert editadas.rowcount == 3  # type: ignore[attr-defined]
        raise _Deshacer


def _secciones_del_plan_a() -> int:
    with psycopg.connect(DSN) as c:
        fila = c.execute("SELECT count(*) FROM plan_seccion WHERE plan_id = %s", (PLAN_A,)).fetchone()
    assert fila is not None
    return int(fila[0])


@pytest.mark.rf("RF-03")
def test_el_plan_lo_lee_quien_lo_ve_lo_editan_admin_y_cuidador_y_nadie_lo_borra(sesiones_app):
    """Decisión 103 (migración 0013): el pagador con puede_ver_plan lee plan_cuidado, pero su UPDATE no toca
    filas y su DELETE no borra el plan ni, en cascada, sus secciones. El admin lo edita, y tampoco lo borra:
    matu_app no tiene DELETE sobre plan_cuidado."""
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from app.core.db import sesion_tenant

    filtro = {"plan": PLAN_A}
    secciones = _secciones_del_plan_a()
    assert secciones > 0
    with pytest.raises(_Deshacer), sesion_tenant(sesiones_app, usuario_id=U_PAG2_A, grupo_id=G_A) as s:
        assert s.execute(text("SELECT id FROM plan_cuidado WHERE id = :plan"), filtro).scalar_one() == PLAN_A
        editado = s.execute(text("UPDATE plan_cuidado SET modo = 'completo' WHERE id = :plan"), filtro)
        assert editado.rowcount == 0  # type: ignore[attr-defined]
        raise _Deshacer
    for usuario in (U_PAG2_A, U_ADMIN_A):
        with pytest.raises(DBAPIError) as error, sesion_tenant(sesiones_app, usuario_id=usuario, grupo_id=G_A) as s:
            s.execute(text("DELETE FROM plan_cuidado WHERE id = :plan"), filtro)
        assert isinstance(error.value.orig, errors.InsufficientPrivilege)
    assert _secciones_del_plan_a() == secciones

    # El admin sí edita (se deshace al final)
    with pytest.raises(_Deshacer), sesion_tenant(sesiones_app, usuario_id=U_ADMIN_A, grupo_id=G_A) as s:
        editado = s.execute(text("UPDATE plan_cuidado SET completitud_pct = 67 WHERE id = :plan"), filtro)
        assert editado.rowcount == 1  # type: ignore[attr-defined]
        raise _Deshacer


@pytest.mark.rf("RF-03")
@pytest.mark.parametrize(
    ("detalle", "acepta"),
    [
        ('{"seccion": "remedios"}', True),
        ('{"secciones": ["comunicacion", "remedios"]}', True),
        ('{"secciones": []}', True),
        ('{"seccion": "Toma una pastilla"}', False),
        ('{"seccion": "rutina"}', False),
        ('{"secciones": ["texto libre"]}', False),
        ('{"secciones": [{"texto": "x"}]}', False),
        ('{"secciones": "remedios"}', False),
        ('{"texto": "Toma una pastilla"}', False),
    ],
)
def test_detalle_de_auditoria_solo_admite_tipos_de_seccion(cx, detalle, acepta):
    insertar = ("INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, detalle)"
                " VALUES (%s, 'usuario', %s, 'plan.editar', 'plan_seccion', CAST(%s AS jsonb))")
    if acepta:
        cx.execute(insertar, (G_A, U_ADMIN_A, detalle))
    else:
        with pytest.raises(errors.CheckViolation):
            cx.execute(insertar, (G_A, U_ADMIN_A, detalle))


def test_relevo_no_hereda_nada_de_la_familia(cx):
    """El relevo no fija app.grupo_id: no ve pedidos, pagos, direcciones ni personas."""
    como(cx, rol="relevo", acceso_relevo_id=ACC_VIGENTE)
    for t in ("pedido", "pedido_entrega", "cargo", "direccion", "persona_cuidada",
              "perfil_consumo", "membresia", "usuario"):
        assert contar(cx, t) == 0, f"el relevo alcanza {t}"


@pytest.mark.parametrize("acceso", [ACC_VENCIDO, ACC_REVOCADO, None])
def test_relevo_vencido_revocado_o_sin_acceso_cero_filas(cx, acceso):
    como(cx, rol="relevo", acceso_relevo_id=acceso)
    for t in ("plan_seccion", "plan_cuidado", "acceso_relevo", "clave_datos"):
        assert contar(cx, t) == 0, t


def test_relevo_registra_su_apertura_en_auditoria(cx):
    como(cx, rol="relevo", acceso_relevo_id=ACC_VIGENTE)
    cx.execute("""INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, entidad_id)
                  VALUES (%s, 'relevo', %s, 'relevo.abrir', 'plan_cuidado', %s)""", (G_A, ACC_VIGENTE, PLAN_A))
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("""INSERT INTO auditoria (grupo_id, actor_tipo, accion, entidad)
                      VALUES (%s, 'relevo', 'relevo.abrir', 'plan_cuidado')""", (G_B,))


# ---- MATU-19 (migración 0007): lo que el relevo puede cambiar de su acceso y la autorización vigente


@pytest.mark.rf("RF-06")
def test_relevo_cuenta_intentos_pero_no_borra_ni_cambia_su_acceso(cx):
    como(cx, rol="relevo", acceso_relevo_id=ACC_VIGENTE)
    # Sube el contador, los usos y el último uso: lo único que el canje y la ficha escriben
    cx.execute("UPDATE acceso_relevo SET pin_intentos_fallidos = pin_intentos_fallidos + 1")
    cx.execute("UPDATE acceso_relevo SET usos = usos + 1, ultimo_uso_en = now()")
    assert cx.execute("SELECT pin_intentos_fallidos, usos FROM acceso_relevo").fetchone() == (1, 1)
    # No borra su acceso: sin política de DELETE, cero filas afectadas
    assert cx.execute("DELETE FROM acceso_relevo").rowcount == 0
    assert contar(cx, "acceso_relevo") == 1
    # No amplía los campos, no se alarga el vencimiento, no se des-revoca ni cambia el PIN
    for cambio in ("secciones_permitidas = ARRAY['rutina','manejo_situaciones','red_apoyo']",
                   "expira_en = expira_en + interval '1 day'", "pin_hash = 'otro'", "otorgado_a_nombre = 'X'"):
        cx.execute("SAVEPOINT s")
        with pytest.raises(errors.InsufficientPrivilege):
            cx.execute(f"UPDATE acceso_relevo SET {cambio}")
        cx.execute("ROLLBACK TO SAVEPOINT s")
    # Tampoco inserta un acceso
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute(
            """INSERT INTO acceso_relevo (grupo_id, plan_id, otorgado_por, otorgado_a_nombre, otorgado_a_telefono,
                   nombre_pila_persona, nombre_pila_comparte, secciones_permitidas, motivo, token_hash, pin_hash,
                   expira_en, relevo_informado_en)
               VALUES (%s, %s, %s, 'Relevo', '+56955550137', 'María', 'Ana', ARRAY['rutina'], 'otro',
                   sha256('t8'), 'p', now() + interval '1 day', now())""", (G_A, PLAN_A, U_ADMIN_A))


@pytest.mark.rf("RF-06")
def test_relevo_no_toca_el_acceso_de_otro(cx):
    como(cx, rol="relevo", acceso_relevo_id=ACC_VIGENTE)
    assert cx.execute("UPDATE acceso_relevo SET usos = usos + 1 WHERE id = %s", (ACC_VENCIDO,)).rowcount == 0
    como(cx, rol="relevo", acceso_relevo_id=ACC_REVOCADO)
    assert cx.execute("UPDATE acceso_relevo SET pin_intentos_fallidos = 1").rowcount == 0


@pytest.mark.rf("RF-05")
def test_familia_sigue_actualizando_sus_accesos(cx):
    """El trigger de 0007 solo limita al relevo: la familia sigue revocando (MATU-20) y cambiando su acceso."""
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    assert cx.execute("UPDATE acceso_relevo SET revocado_en = now() WHERE id = %s", (ACC_VIGENTE,)).rowcount == 1


def _consentimiento_relevo(cx, calidad="titular", revision="NULL", revocado="NULL"):
    """Un consentimiento para plan_cuidado de P_A, como superusuario y dentro de la transacción de la prueba."""
    cx.execute(f"""INSERT INTO consentimiento (grupo_id, persona_cuidada_id, usuario_id, calidad_otorgante, finalidad,
                       version_politica, evidencia, revision_vence_en, revocado_en, revocacion_motivo)
                   VALUES (%s, %s, %s, %s, 'plan_cuidado', '0.0', '{{}}', {revision}, {revocado},
                           CASE WHEN {revocado} IS NULL THEN NULL ELSE 'retiro' END)""",
               (G_A, P_A, U_ADMIN_A, calidad))


def _vigente(cx, ahora="now()"):
    return cx.execute(f"SELECT relevo_autorizacion_vigente({ahora})").fetchone()[0]


@pytest.mark.rf("RF-06")
@pytest.mark.parametrize(("calidad", "revision", "revocado", "esperado"), [
    ("titular", "NULL", "NULL", True),
    ("cuidador_de_hecho", "now() + interval '1 day'", "NULL", True),
    ("cuidador_de_hecho", "now() - interval '1 day'", "NULL", False),   # revisión anual vencida
    ("titular", "NULL", "now()", False),                                 # consentimiento revocado
    (None, None, None, False),                                           # sin consentimiento
])
def test_autorizacion_vigente_del_relevo_devuelve_solo_un_booleano(cx, calidad, revision, revocado, esperado):
    if calidad is not None:
        _consentimiento_relevo(cx, calidad, revision, revocado)
    como(cx, rol="relevo", acceso_relevo_id=ACC_VIGENTE)
    assert _vigente(cx) is esperado
    # El relevo no lee consentimiento, ni siquiera con la función disponible
    assert contar(cx, "consentimiento") == 0


@pytest.mark.rf("RF-06")
def test_autorizacion_vigente_usa_el_instante_del_reloj(cx):
    _consentimiento_relevo(cx, "cuidador_de_hecho", "now() + interval '1 day'")
    como(cx, rol="relevo", acceso_relevo_id=ACC_VIGENTE)
    assert _vigente(cx, "now() + interval '2 days'") is False
    assert _vigente(cx, "now()") is True


@pytest.mark.rf("RF-06")
def test_autorizacion_vigente_solo_en_contexto_de_relevo(cx):
    _consentimiento_relevo(cx)
    # Sin contexto, con la familia o con otro acceso (vencido): falso, nunca un dato
    for ctx in ({}, {"usuario_id": U_ADMIN_A, "grupo_id": G_A}, {"rol": "relevo", "acceso_relevo_id": ACC_VENCIDO}):
        como(cx, **ctx)
        assert _vigente(cx) is False, ctx
    # matu_owner es el único con la política de lectura de 0007; matu_publisher no ejecuta la función
    cx.execute("RESET ROLE")
    cx.execute("SAVEPOINT s")
    cx.execute("SET LOCAL ROLE matu_publisher")
    with pytest.raises(errors.InsufficientPrivilege):
        _vigente(cx)
    cx.execute("ROLLBACK TO SAVEPOINT s")


# ------------------------------------------------------------------ comercio y repartidor

def test_comercio_ve_pedidos_enviados_sin_direccion_ni_pago(cx):
    como(cx, usuario_id=U_ENC, comercio_id=COMERCIO)
    assert contar(cx, "pedido") == 2                          # A y B enviados, no el borrador
    assert contar(cx, "pedido", f"id = '{PED_A_BORRADOR}'") == 0
    assert contar(cx, "pedido_linea") == 1                    # solo la del pedido enviado
    for t in ("pedido_entrega", "cargo", "participacion", "transaccion_pasarela",
              "persona_cuidada", "direccion", "plan_cuidado", "perfil_consumo"):
        assert contar(cx, t) == 0, f"el comercio alcanza {t}"


def test_repartidor_sin_precios_unitarios(cx):
    como(cx, usuario_id=U_REP, repartidor_id=REPARTIDOR)
    assert contar(cx, "pedido") == 1
    assert contar(cx, "pedido_entrega") == 1
    for t in ("pedido_linea", "cargo", "plan_seccion", "perfil_consumo", "persona_cuidada"):
        assert contar(cx, t) == 0, f"el repartidor alcanza {t}"


# ------------------------------------------------------------------ integridad

def test_auditoria_es_solo_insercion(cx):
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    cx.execute("INSERT INTO auditoria (grupo_id, actor_tipo, accion, entidad) VALUES (%s, 'usuario', 'x', 'y')", (G_A,))
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("UPDATE auditoria SET accion = 'z'")


def test_transaccion_de_pasarela_no_se_borra(cx):
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("DELETE FROM transaccion_pasarela")


def test_outbox_solo_admite_identificadores(cx):
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    cx.execute("""INSERT INTO evento_outbox (grupo_id, tipo, agregado_tipo, agregado_id, payload)
                  VALUES (%s, 'PedidoEnviado', 'pedido', %s, jsonb_build_object('pedido_id', %s::text))""",
               (G_A, PED_A_ENVIADO, PED_A_ENVIADO))
    with pytest.raises(errors.CheckViolation):
        cx.execute("""INSERT INTO evento_outbox (grupo_id, tipo, agregado_tipo, agregado_id, payload)
                      VALUES (%s, 'X', 'pedido', %s, '{"nombre": "María"}')""", (G_A, PED_A_ENVIADO))


def test_la_api_no_lee_el_outbox(cx):
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("SELECT * FROM evento_outbox")


def test_publicador_no_alcanza_tablas_de_negocio(cx):
    cx.execute("SET LOCAL ROLE matu_publisher")
    assert cx.execute("SELECT count(*) FROM evento_outbox").fetchone()[0] >= 0
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("SELECT count(*) FROM pedido")


def test_scheduler_solo_enumera_identificadores(cx):
    cx.execute("SET LOCAL ROLE matu_scheduler")
    assert cx.execute("SELECT count(id) FROM grupo_familiar").fetchone()[0] == 2
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("SELECT nombre FROM grupo_familiar")


def test_borrado_criptografico_es_explicito(cx):
    """Regresión del defecto 5: sin clave no hay estado ambiguo."""
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("UPDATE clave_datos SET dek_cifrada_con_kek = NULL")
    cx.execute("UPDATE clave_datos SET dek_cifrada_con_kek = NULL, destruida_en = now()")


# MATU-11, migración 0003: una clave destruida no resucita, ni borrándola ni actualizándola

def test_la_api_no_borra_la_clave_de_datos(cx):
    """Sin la fila, la persona quedaría en "no existe" y la escritura siguiente crearía otra DEK."""
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    assert contar(cx, "clave_datos") == 1
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("DELETE FROM clave_datos WHERE persona_cuidada_id = %s", (P_A,))


@pytest.mark.parametrize("db_rol", ["matu_app", None])   # None: superusuario, el trigger también lo alcanza
@pytest.mark.parametrize("cambio", [
    "dek_cifrada_con_kek = '\\x03', destruida_en = NULL",          # devolverle una DEK
    "dek_cifrada_con_kek = '\\x03'",                               # DEK con marca de destrucción (también el CHECK)
    "destruida_en = NULL",                                         # quitar la marca (también el CHECK)
    "destruida_en = destruida_en + interval '1 day'",              # mover la marca
    "kek_version = 2",
    "rotada_en = now()",
])
def test_clave_destruida_no_vuelve_a_tener_dek(cx, db_rol, cambio):
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    cx.execute("UPDATE clave_datos SET dek_cifrada_con_kek = NULL, destruida_en = now() WHERE persona_cuidada_id = %s",
               (P_A,))
    if db_rol is None:
        cx.execute("RESET ROLE")
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute(f"UPDATE clave_datos SET {cambio} WHERE persona_cuidada_id = %s", (P_A,))
    # Tampoco se crea otra clave para la misma persona sin una autorización nueva (trigger de 0016, P8)
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("""INSERT INTO clave_datos (grupo_id, persona_cuidada_id, dek_cifrada_con_kek, kek_version)
                      VALUES (%s, %s, '\\x04', 1)""", (G_A, P_A))
    assert cx.execute("SELECT dek_cifrada_con_kek IS NULL FROM clave_datos WHERE persona_cuidada_id = %s",
                      (P_A,)).fetchone() == (True,)


def test_clave_vigente_se_sigue_actualizando(cx):
    """El trigger solo fija la fila destruida: la vigente se puede volver a envolver (rotación futura)."""
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    cx.execute("UPDATE clave_datos SET dek_cifrada_con_kek = '\\x05', kek_version = 2, rotada_en = now()"
               " WHERE persona_cuidada_id = %s", (P_A,))
    assert cx.execute("SELECT kek_version FROM clave_datos WHERE persona_cuidada_id = %s", (P_A,)).fetchone() == (2,)


def test_nonce_no_se_repite(cx):
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.UniqueViolation):
        cx.execute("""INSERT INTO plan_seccion (plan_id, tipo, contenido_cifrado, nonce, tag_auth, kek_version)
                      VALUES (%s, 'horarios', '\\xaa', '\\x000000000000000000000001',
                              '\\x00000000000000000000000000000000', 1)""", (PLAN_A,))


# ------------------------------------------------------------------ precios exactos y un solo cobro (ADR-027)

CARGO_A = "00000000-0000-0000-0000-0000000007a1"
PRODUCTO = "00000000-0000-0000-0000-000000000f01"
OFERTA = "00000000-0000-0000-0000-000000000f11"


@pytest.mark.rf("ADR-027")
@pytest.mark.parametrize("tabla", ["cargo", "participacion"])
def test_devuelto_no_supera_lo_cobrado(cx, tabla):
    """Reemplaza a la prueba del tope de captura: ya no hay autorizado ni capturado, solo cobrado y devuelto."""
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    parcial = "devuelto_parcial" if tabla == "cargo" else "devuelta_parcial"
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute(f"UPDATE {tabla} SET estado = %s, monto_devuelto = monto_cobrado + 1", (parcial,))
    cx.execute(f"UPDATE {tabla} SET estado = %s, monto_devuelto = 12990", (parcial,))
    assert cx.execute(f"SELECT monto_cobrado - monto_devuelto FROM {tabla}").fetchone()[0] == 28970 - 12990


@pytest.mark.rf("ADR-027")
def test_total_es_productos_mas_un_envio(cx):
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("UPDATE pedido SET total = total + 1 WHERE id = %s", (PED_A_BORRADOR,))
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("UPDATE pedido SET costo_envio = -1, total = subtotal_productos - 1 WHERE id = %s",
                   (PED_A_BORRADOR,))
    cx.execute("UPDATE pedido SET costo_envio = 0, total = subtotal_productos WHERE id = %s", (PED_A_BORRADOR,))


@pytest.mark.rf("ADR-027")
@pytest.mark.parametrize(("tabla", "columna", "valor"), [
    ("pedido", "estado", "pendiente_recaudacion"),
    ("pedido", "estado", "autorizado"),
    ("pedido", "estado", "requiere_decision"),
    ("pedido", "estado", "captura_pendiente"),
    ("pedido", "estado", "incobrable"),
    ("pedido_linea", "estado_linea", "sustituida"),
    ("cargo", "estado", "capturado"),
    ("participacion", "estado", "autorizada"),
    ("transaccion_pasarela", "tipo", "captura"),
    ("transaccion_pasarela", "tipo", "autorizacion"),
])
def test_estados_de_la_captura_diferida_ya_no_existen(cx, tabla, columna, valor):
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.CheckViolation):
        cx.execute(f"UPDATE {tabla} SET {columna} = %s", (valor,))


@pytest.mark.rf("ADR-027")
def test_estado_del_cargo_coincide_con_sus_montos(cx):
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    for estado, cobrado, devuelto in (("pagado", 0, 0), ("pendiente", 28970, 0), ("rechazado", 28970, 0),
                                      ("anulado", 28970, 100), ("devuelto_parcial", 28970, 0),
                                      ("devuelto_parcial", 28970, 28970), ("pagado", 28970, 100)):
        with pytest.raises(errors.CheckViolation), cx.transaction():
            cx.execute("UPDATE cargo SET estado = %s, monto_cobrado = %s, monto_devuelto = %s",
                       (estado, cobrado, devuelto))
    # Cancelación sin costo antes de preparar: se anula el total
    cx.execute("UPDATE cargo SET estado = 'anulado', monto_devuelto = monto_cobrado")
    cx.execute("UPDATE participacion SET estado = 'anulada', monto_devuelto = monto_cobrado")


@pytest.mark.rf("ADR-027")
def test_pedido_pagado_exige_total_confirmado_y_marca_de_pago(cx):
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    # Sin pagar no se envía al comercio
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("UPDATE pedido SET estado = 'enviado_a_comercio' WHERE id = %s", (PED_A_BORRADOR,))
    # Un total confirmado tiene vencimiento, posterior a la confirmación
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("UPDATE pedido SET estado = 'total_confirmado', total_confirmado_en = now() WHERE id = %s",
                   (PED_A_BORRADOR,))
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("""UPDATE pedido SET estado = 'total_confirmado', total_confirmado_en = now(),
                      total_vence_en = now() - interval '1 minute' WHERE id = %s""", (PED_A_BORRADOR,))
    # Un borrador no lleva marca de pago
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("""UPDATE pedido SET total_confirmado_en = now(), total_vence_en = now() + interval '15 minutes',
                      pagado_en = now() WHERE id = %s""", (PED_A_BORRADOR,))
    cx.execute("""UPDATE pedido SET estado = 'total_confirmado', total_confirmado_en = now(),
                  total_vence_en = now() + interval '15 minutes' WHERE id = %s""", (PED_A_BORRADOR,))
    cx.execute("UPDATE pedido SET estado = 'vencido' WHERE id = %s", (PED_A_BORRADOR,))
    # Si vence, se vuelve a confirmar, y recién entonces se paga
    cx.execute("""UPDATE pedido SET estado = 'total_confirmado', total_confirmado_en = now() + interval '1 minute',
                  total_vence_en = now() + interval '16 minutes' WHERE id = %s""", (PED_A_BORRADOR,))
    cx.execute("UPDATE pedido SET estado = 'pagado', pagado_en = now() + interval '2 minutes' WHERE id = %s",
               (PED_A_BORRADOR,))


@pytest.mark.rf("ADR-027")
def test_el_precio_pagado_queda_fijo(cx):
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    for sql in (
        f"UPDATE pedido_linea SET precio_unitario = 9990 WHERE pedido_id = '{PED_A_ENVIADO}'",
        f"UPDATE pedido_linea SET cantidad = 3 WHERE pedido_id = '{PED_A_ENVIADO}'",
        f"DELETE FROM pedido_linea WHERE pedido_id = '{PED_A_ENVIADO}'",
        f"""INSERT INTO pedido_linea (pedido_id, oferta_id, producto_id, cantidad, precio_unitario)
            VALUES ('{PED_A_ENVIADO}', '{OFERTA}', '{PRODUCTO}', 1, 12990)""",
    ):
        with pytest.raises(errors.CheckViolation), cx.transaction():
            cx.execute(sql)
    # El estado de la línea sí avanza, y antes de pagar el precio todavía puede cambiar
    cx.execute("UPDATE pedido_linea SET estado_linea = 'preparada' WHERE pedido_id = %s", (PED_A_ENVIADO,))
    cx.execute("UPDATE pedido_linea SET precio_unitario = 11990 WHERE pedido_id = %s", (PED_A_BORRADOR,))


@pytest.mark.rf("ADR-027")
def test_la_devolucion_de_una_linea_no_supera_lo_pagado(cx):
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("""UPDATE pedido_linea SET estado_linea = 'devuelta', devuelta_en = now(),
                      monto_devuelto = 2 * 12990 + 1 WHERE pedido_id = %s""", (PED_A_ENVIADO,))
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("UPDATE pedido_linea SET estado_linea = 'devuelta' WHERE pedido_id = %s", (PED_A_ENVIADO,))
    cx.execute("""UPDATE pedido_linea SET estado_linea = 'devuelta', devuelta_en = now(),
                  monto_devuelto = 2 * 12990 WHERE pedido_id = %s""", (PED_A_ENVIADO,))


@pytest.mark.rf("ADR-027")
def test_reasignacion_solo_al_mismo_producto_nunca_otra_marca(cx):
    otro_comercio, otra_marca = "00000000-0000-0000-0000-0000000004c2", "00000000-0000-0000-0000-000000000f02"
    misma, distinta = "00000000-0000-0000-0000-000000000f12", "00000000-0000-0000-0000-000000000f13"
    cx.execute(f"""
        INSERT INTO comercio (id, razon_social, nombre_fantasia, rut, direccion, comuna) VALUES
         ('{otro_comercio}', 'Farmacia Dos SpA', 'Farmacia Dos', '76.000.000-2', 'Av. Ossa 2', 'La Reina');
        INSERT INTO producto (id, categoria_id, nombre, presentacion, unidad, unidades_por_envase) VALUES
         ('{otra_marca}', '00000000-0000-0000-0000-000000000c01', 'Pañal adulto M otra marca', 'x30', 'unidad', 30);
        INSERT INTO oferta (id, producto_id, comercio_id, precio) VALUES
         ('{misma}', '{PRODUCTO}', '{otro_comercio}', 13990), ('{distinta}', '{otra_marca}', '{otro_comercio}', 9990);
    """)
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    reasignar = """UPDATE pedido_linea SET oferta_reasignada_id = %s, precio_reasignado = %s,
                   reasignada_en = now() WHERE pedido_id = %s"""
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute(reasignar, (distinta, 9990, PED_A_ENVIADO))
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute(reasignar, (OFERTA, 12990, PED_A_ENVIADO))         # la misma oferta no es reasignar
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("UPDATE pedido_linea SET oferta_reasignada_id = %s WHERE pedido_id = %s", (misma, PED_A_ENVIADO))
    # Mismo producto en otro comercio, más caro: MATU asume la diferencia y la familia paga lo mismo
    cx.execute(reasignar, (misma, 13990, PED_A_ENVIADO))
    assert cx.execute("SELECT precio_unitario FROM pedido_linea WHERE pedido_id = %s",
                      (PED_A_ENVIADO,)).fetchone()[0] == 12990


@pytest.mark.rf("ADR-027")
@pytest.mark.parametrize("estado", ["total_confirmado", "vencido", "pagado", "cancelado"])
def test_comercio_no_ve_pedidos_sin_pagar_o_sin_enviar(cx, estado):
    pagado = estado == "pagado"
    cx.execute("""INSERT INTO pedido (grupo_id, persona_cuidada_id, comercio_id, estado, subtotal_productos, total,
                                      total_confirmado_en, total_vence_en, pagado_en, destinatario_nombre_pila,
                                      creado_por)
                  VALUES (%s, %s, %s, %s, 12990, 12990, now(), now() + interval '15 minutes',
                          CASE WHEN %s THEN now() END, 'María', %s)""",
               (G_A, P_A, COMERCIO, estado, pagado, U_ADMIN_A))
    como(cx, usuario_id=U_ENC, comercio_id=COMERCIO)
    assert contar(cx, "pedido") == 2                          # solo los dos pagados y enviados de la semilla


@pytest.mark.rf("ADR-027")
@pytest.mark.parametrize("quien", ["familia", "comercio"])
@pytest.mark.parametrize("cambio", [
    # Hallazgo P2-1 del QA: reabrir el pedido pagado para cambiar el precio
    "estado = 'borrador', pagado_en = NULL",
    "estado = 'total_confirmado', pagado_en = NULL",
    "estado = 'vencido'",
    "pagado_en = pagado_en + interval '1 minute'",
    "subtotal_productos = subtotal_productos - 1000, total = total - 1000",
    "costo_envio = 0, total = subtotal_productos",
    "total_confirmado_en = total_confirmado_en - interval '1 minute'",
    "total_vence_en = total_vence_en + interval '1 hour'",
])
def test_el_pedido_pagado_no_se_reabre(cx, quien, cambio):
    """Sin el trigger pedido_pagado_fijo, la familia o el comercio podrían cambiar lo ya cobrado."""
    ctx = {"usuario_id": U_ADMIN_A, "grupo_id": G_A} if quien == "familia" else \
          {"usuario_id": U_ENC, "comercio_id": COMERCIO}
    como(cx, **ctx)
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute(f"UPDATE pedido SET {cambio} WHERE id = %s", (PED_A_ENVIADO,))
    # El pedido pagado sí avanza en su ciclo, y lo cobrado sigue igual
    cx.execute("UPDATE pedido SET estado = 'preparando' WHERE id = %s", (PED_A_ENVIADO,))
    assert cx.execute("SELECT subtotal_productos, costo_envio, total FROM pedido WHERE id = %s",
                      (PED_A_ENVIADO,)).fetchone() == (25980, 2990, 28970)


# ------------------------------------------------------------------ si un producto falta (RF-21)

REGLA = "INSERT INTO regla_sustitucion (pedido_id, producto_id, accion) VALUES (%s, %s, %s)"


@pytest.mark.rf("RF-21")
@pytest.mark.parametrize("accion", ["equivalente", "producto_especifico", "no_sustituir", "consultar"])
def test_ya_no_se_sustituye_por_otro_producto(cx, accion):
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.CheckViolation):
        cx.execute(REGLA, (PED_A_BORRADOR, PRODUCTO, accion))


@pytest.mark.rf("RF-21")
def test_regla_sin_producto_sustituto_ni_precio_maximo(cx):
    columnas = {r[0] for r in cx.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'regla_sustitucion'").fetchall()}
    assert columnas == {"id", "pedido_id", "producto_id", "accion"}


@pytest.mark.rf("RF-21")
@pytest.mark.parametrize("accion", ["otro_comercio", "quitar"])
def test_si_falta_otro_comercio_o_quitar(cx, accion):
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    cx.execute(REGLA, (PED_A_BORRADOR, PRODUCTO, accion))
    assert contar(cx, "regla_sustitucion", f"accion = '{accion}'") == 1
    # Una sola decisión por producto del pedido
    with pytest.raises(errors.UniqueViolation):
        cx.execute(REGLA, (PED_A_BORRADOR, PRODUCTO, "otro_comercio"))


@pytest.mark.rf("RF-21")
def test_regla_de_otro_grupo_no_se_ve_ni_se_crea(cx):
    como(cx, usuario_id=U_ADMIN_B, grupo_id=G_B)
    cx.execute(REGLA, (PED_B_ENVIADO, PRODUCTO, "quitar"))
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    assert contar(cx, "regla_sustitucion") == 0
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute(REGLA, (PED_B_ENVIADO, PRODUCTO, "otro_comercio"))


# ------------------------------------------------------------------ lectura de la auditoría (decisión 36)

U_CUID_A = uuid.UUID("00000000-0000-0000-0000-0000000000a9")


def _sembrar_auditoria(cx):
    """Como superusuario, dentro de la transacción que se revierte: un cuidador y una fila por actor."""
    cx.execute("INSERT INTO usuario (id, email, nombre, password_hash) VALUES (%s, 'cuid.a@x.cl', 'Cuid A', 'h')",
               (U_CUID_A,))
    cx.execute("INSERT INTO membresia (grupo_id, usuario_id, rol, puede_ver_plan) VALUES (%s, %s, 'cuidador', false)",
               (G_A, U_CUID_A))
    for grupo, actor in ((G_A, U_ADMIN_A), (G_A, U_CUID_A), (G_A, U_OBS_A), (G_B, U_ADMIN_B)):
        cx.execute("INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad)"
                   " VALUES (%s, 'usuario', %s, 'plan.leer', 'plan_cuidado')", (grupo, actor))


def _actores_visibles(cx):
    return {r[0] for r in cx.execute("SELECT actor_ref FROM auditoria").fetchall()}


@pytest.mark.rf("RF-08")
@pytest.mark.parametrize("usuario, grupo, esperado", [
    (U_ADMIN_A, G_A, {U_ADMIN_A, U_CUID_A, U_OBS_A}),   # el admin ve todo su grupo
    (U_CUID_A, G_A, {U_CUID_A}),                         # el cuidador, solo lo suyo
    (U_OBS_A, G_A, {U_OBS_A}),                           # el observador, solo lo suyo
    (U_ADMIN_A, G_B, set()),                             # otro grupo: nada
])
def test_lectura_de_auditoria_por_rol(cx, usuario, grupo, esperado):
    _sembrar_auditoria(cx)
    como(cx, usuario_id=usuario, grupo_id=grupo)
    assert _actores_visibles(cx) == esperado


@pytest.mark.rf("RF-08")
def test_operacion_no_lee_la_auditoria(cx):
    _sembrar_auditoria(cx)
    como(cx, rol="operacion")
    assert _actores_visibles(cx) == set()


# ---- consentimiento inalterable (0006): solo se registra la revocación

def _consentimiento(cx):
    """Un consentimiento de G_A, insertado por el superusuario dentro de la transacción de la prueba."""
    return cx.execute(
        "INSERT INTO consentimiento (grupo_id, persona_cuidada_id, usuario_id, calidad_otorgante, finalidad,"
        " version_politica, evidencia) VALUES (%s, %s, %s, 'titular', 'plan_cuidado', 'v1',"
        " '{\"esquema\": 1}'::jsonb) RETURNING id",
        (G_A, P_A, U_ADMIN_A),
    ).fetchone()[0]


@pytest.mark.rf("RF-01")
def test_consentimiento_no_se_modifica(cx):
    cid = _consentimiento(cx)
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("UPDATE consentimiento SET calidad_otorgante = 'cuidador_de_hecho' WHERE id = %s", (cid,))


@pytest.mark.rf("RF-01")
def test_consentimiento_no_se_borra(cx):
    cid = _consentimiento(cx)
    with pytest.raises(errors.InsufficientPrivilege), cx.transaction():  # tampoco el superusuario
        cx.execute("DELETE FROM consentimiento WHERE id = %s", (cid,))
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("DELETE FROM consentimiento WHERE id = %s", (cid,))


@pytest.mark.rf("RF-01")
def test_revocar_registra_fecha_una_vez(cx):
    cid = _consentimiento(cx)
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    cur = cx.execute("UPDATE consentimiento SET revocado_en = now(), revocacion_motivo = 'retiro' WHERE id = %s",
                     (cid,))
    assert cur.rowcount == 1
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("UPDATE consentimiento SET revocado_en = now() + interval '1 day' WHERE id = %s", (cid,))


# ---- sesión y dispositivos (0008, MATU-38): operación no lee push_token ni token_hash

DISP_A = uuid.UUID("00000000-0000-0000-0000-0000000009a1")
DISP_B = uuid.UUID("00000000-0000-0000-0000-0000000009b1")


def _sembrar_sesiones(cx):
    """Un dispositivo con push_token y una sesión por usuario (A y B), como superusuario en la transacción."""
    for usuario, dispositivo, semilla in ((U_ADMIN_A, DISP_A, "a"), (U_ADMIN_B, DISP_B, "b")):
        cx.execute(
            "INSERT INTO dispositivo (id, usuario_id, plataforma, nombre, push_token, ultimo_uso_en)"
            " VALUES (%s, %s, 'web', 'Chrome en Android', %s, now())",
            (dispositivo, usuario, f"https://fcm.googleapis.com/fcm/send/{semilla}"),
        )
        cx.execute(
            "INSERT INTO sesion_refresh (usuario_id, dispositivo_id, familia_id, token_hash, expira_en)"
            " VALUES (%s, %s, gen_random_uuid(), sha256(%s::bytea), now() + interval '30 days')",
            (usuario, dispositivo, f"refresh-{semilla}".encode()),
        )


@pytest.mark.rf("RF-37")
def test_operacion_no_lee_push_token_ni_token_hash(cx):
    _sembrar_sesiones(cx)
    como(cx, rol="operacion")
    assert cx.execute("SELECT push_token FROM dispositivo").fetchall() == []
    assert cx.execute("SELECT token_hash FROM sesion_refresh").fetchall() == []
    # Tampoco los cambia ni los borra por fuera de la conservación
    assert cx.execute("UPDATE dispositivo SET push_token = NULL RETURNING id").fetchall() == []
    assert cx.execute("DELETE FROM sesion_refresh RETURNING id").fetchall() == []


@pytest.mark.rf("RF-37")
def test_conservacion_de_operacion_solo_devuelve_contadores(cx):
    _sembrar_sesiones(cx)
    como(cx, rol="operacion")
    fila = cx.execute(
        "SELECT * FROM iam_conservar(now() - interval '30 days', now() - interval '90 days', now())").fetchone()
    assert fila == (0, 0)
    columnas = [c.name for c in cx.execute(
        "SELECT * FROM iam_conservar(now() - interval '30 days', now() - interval '90 days', now())").description]
    assert columnas == ["sesiones_borradas", "dispositivos_borrados"]


@pytest.mark.rf("RF-37")
def test_conservacion_sin_rol_de_operacion_falla(cx):
    como(cx, usuario_id=U_ADMIN_A)
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("SELECT * FROM iam_conservar(now(), now(), now())")


@pytest.mark.rf("RF-37")
def test_usuario_no_ve_ni_toca_el_dispositivo_ni_la_sesion_de_otro(cx):
    _sembrar_sesiones(cx)
    como(cx, usuario_id=U_ADMIN_A)
    assert [r[0] for r in cx.execute("SELECT id FROM dispositivo").fetchall()] == [DISP_A]
    assert contar(cx, "sesion_refresh") == 1
    assert cx.execute(
        "UPDATE dispositivo SET revocado_en = now() WHERE id = %s RETURNING id", (DISP_B,)).fetchall() == []
    assert cx.execute("DELETE FROM dispositivo WHERE id = %s RETURNING id", (DISP_B,)).fetchall() == []
    assert cx.execute(
        "UPDATE sesion_refresh SET revocado_en = now() WHERE usuario_id = %s RETURNING id", (U_ADMIN_B,)
    ).fetchall() == []


@pytest.mark.rf("RF-37")
def test_usuario_no_cuelga_una_sesion_de_un_dispositivo_ajeno(cx):
    _sembrar_sesiones(cx)
    como(cx, usuario_id=U_ADMIN_A)
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute(
            "INSERT INTO sesion_refresh (usuario_id, dispositivo_id, familia_id, token_hash, expira_en)"
            " VALUES (%s, %s, gen_random_uuid(), sha256('x'::bytea), now() + interval '1 day')",
            (U_ADMIN_A, DISP_B),
        )


@pytest.mark.rf("RF-37")
def test_usuario_no_crea_un_dispositivo_a_nombre_de_otro(cx):
    como(cx, usuario_id=U_ADMIN_A)
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("INSERT INTO dispositivo (usuario_id, plataforma) VALUES (%s, 'web')", (U_ADMIN_B,))


@pytest.mark.rf("RF-37")
def test_conservacion_con_ahora_futuro_falla(cx):
    _sembrar_sesiones(cx)
    como(cx, rol="operacion")
    with pytest.raises(errors.InvalidParameterValue):
        cx.execute("SELECT * FROM iam_conservar(now() + interval '400 days', now() + interval '400 days',"
                   " now() + interval '430 days')")


@pytest.mark.rf("RF-37")
def test_auditoria_no_admite_la_huella_del_email(cx):
    """Decisión 64: auditoria.detalle solo admite sesiones_revocadas."""
    with pytest.raises(errors.CheckViolation):
        cx.execute(
            "INSERT INTO auditoria (actor_tipo, accion, entidad, detalle) VALUES ('sistema',"
            " 'sesion.inicio_fallido', 'usuario', %s::jsonb)",
            ('{"huella_email": "' + "ab" * 32 + '"}',),
        )


# ------------------------------------------------------------------ consumo (MATU-36, migración 0009)

U_CUID_CONSUMO_A = uuid.UUID("00000000-0000-0000-0000-0000000000a5")


def _con_cuidador_a(cx):
    """Una cuidadora en el grupo A, sembrada como superusuario dentro de la transacción de la prueba."""
    cx.execute("INSERT INTO usuario (id, email, nombre, password_hash) VALUES (%s, 'cuid.a@x.cl', 'Cuid A', 'h')",
               (U_CUID_CONSUMO_A,))
    cx.execute("INSERT INTO membresia (grupo_id, usuario_id, rol) VALUES (%s, %s, 'cuidador')", (G_A, U_CUID_CONSUMO_A))


def _insertar_perfil_libre(cx, grupo=G_A, persona=P_A, nombre="Toallitas húmedas"):
    cx.execute(
        "INSERT INTO perfil_consumo (grupo_id, persona_cuidada_id, nombre_libre, tasa_unidades, stock_unidades,"
        " stock_medido_en, fecha_quiebre_estimada) VALUES (%s, %s, %s, 10, 160, current_date, current_date + 16)",
        (grupo, persona, nombre),
    )


@pytest.mark.rf("RF-10")
@pytest.mark.parametrize("usuario, escribe", [
    (U_ADMIN_A, True),
    (U_CUID_CONSUMO_A, True),
    (U_PAG_A, False),
    (U_PAG2_A, False),   # el permiso de ver el plan no da escritura en el consumo
    (U_OBS_A, False),
])
def test_consumo_lo_leen_todos_y_lo_escriben_admin_y_cuidador(cx, usuario, escribe):
    _con_cuidador_a(cx)
    como(cx, usuario_id=usuario, grupo_id=G_A)
    assert contar(cx, "perfil_consumo") == 1
    cx.execute("SAVEPOINT antes_de_insertar")
    if escribe:
        _insertar_perfil_libre(cx)
    else:
        with pytest.raises(errors.InsufficientPrivilege):
            _insertar_perfil_libre(cx)
        # El contexto (SET LOCAL) se fijó antes del savepoint y sigue vigente
        cx.execute("ROLLBACK TO SAVEPOINT antes_de_insertar")
    esperado = 1 if escribe else 0
    assert len(cx.execute("UPDATE perfil_consumo SET dias_aviso = 3 WHERE producto_id IS NOT NULL RETURNING id")
               .fetchall()) == esperado
    assert len(cx.execute("DELETE FROM perfil_consumo WHERE producto_id IS NOT NULL RETURNING id")
               .fetchall()) == esperado


@pytest.mark.rf("RF-10")
def test_consumo_no_se_escribe_en_otro_grupo(cx):
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.InsufficientPrivilege):
        _insertar_perfil_libre(cx, grupo=G_B, persona=P_B)


@pytest.mark.rf("RF-10")
def test_admin_de_otro_grupo_no_escribe_con_el_grupo_ajeno_en_contexto(cx):
    """app.grupo_id ajeno sin membresía: la API nunca lo fija, pero la base tampoco lo deja escribir."""
    como(cx, usuario_id=U_ADMIN_B, grupo_id=G_A)
    assert cx.execute("UPDATE perfil_consumo SET dias_aviso = 3 RETURNING id").fetchall() == []
    assert cx.execute("DELETE FROM perfil_consumo RETURNING id").fetchall() == []


@pytest.mark.rf("RF-10")
def test_operacion_no_ve_el_consumo_ni_con_un_grupo_en_contexto(cx):
    como(cx, usuario_id=U_ADMIN_B, grupo_id=G_A, rol="operacion")
    assert contar(cx, "perfil_consumo") == 0
    assert cx.execute("DELETE FROM perfil_consumo RETURNING id").fetchall() == []
    como(cx, rol="operacion")
    assert contar(cx, "perfil_consumo") == 0


@pytest.mark.rf("RF-10")
@pytest.mark.parametrize("producto, nombre", [
    ("00000000-0000-0000-0000-000000000f01", "Pañal adulto M"),   # los dos
    (None, None),                                                 # ninguno
    (None, "x" * 61),                                             # nombre largo
    (None, ""),                                                   # nombre vacío
])
def test_perfil_exige_producto_o_nombre_de_hasta_60(cx, producto, nombre):
    with pytest.raises(errors.CheckViolation):
        cx.execute(
            "INSERT INTO perfil_consumo (grupo_id, persona_cuidada_id, producto_id, nombre_libre, tasa_unidades,"
            " stock_unidades, stock_medido_en, fecha_quiebre_estimada)"
            " VALUES (%s, %s, %s, %s, 1, 1, current_date, current_date)",
            (G_B, P_B, producto, nombre),
        )


@pytest.mark.rf("RF-10")
def test_conservacion_del_consumo_solo_con_operacion_y_tras_90_dias(cx):
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("SELECT consumo_conservar(now() - interval '90 days', now())")
    cx.rollback()
    como(cx, rol="operacion")
    with pytest.raises(errors.InvalidParameterValue):
        cx.execute("SELECT consumo_conservar(now() - interval '89 days', now())")
    cx.rollback()
    como(cx, rol="operacion")
    # Sin consentimientos de consumo en la semilla: no borra nada y devuelve solo un contador
    assert cx.execute("SELECT consumo_conservar(now() - interval '90 days', now())").fetchone() == (0,)


@pytest.mark.rf("RF-10")
def test_conservacion_del_consumo_borra_tras_90_dias_de_revocada(cx):
    for revocado, queda in (("now() - interval '91 days'", 0), ("now() - interval '89 days'", 1)):
        cx.execute(
            "INSERT INTO consentimiento (grupo_id, persona_cuidada_id, usuario_id, calidad_otorgante, finalidad,"
            " version_politica, evidencia, otorgado_en, revocado_en, revocacion_motivo)"
            f" VALUES (%s, %s, %s, 'titular', 'consumo', '0.10', '{{}}', now() - interval '200 days', {revocado},"
            " 'retiro')",
            (G_A, P_A, U_ADMIN_A),
        )
        como(cx, rol="operacion")
        cx.execute("SELECT consumo_conservar(now() - interval '90 days', now())")
        cx.execute("RESET ROLE")  # superusuario: cuenta sin RLS
        assert contar(cx, "perfil_consumo", f"grupo_id = '{G_A}'") == queda
        cx.rollback()


# ---- MATU-45 (migración 0010): quién ve las aperturas del relevo en auditoria

U_CUID_APERTURAS_A = uuid.UUID("00000000-0000-0000-0000-0000000000a7")
ACCIONES_APERTURA = ("relevo.presentar", "relevo.abrir", "relevo.pin_incorrecto", "relevo.bloqueo")


def _sembrar_aperturas(cx):
    """Como superusuario, en la transacción que se revierte: un cuidador de G_A, las cuatro acciones del
    relevo y un relevo.canje en G_A, y una apertura en G_B (con actor_ref inventado: no hay acceso en B)."""
    cx.execute("INSERT INTO usuario (id, email, nombre, password_hash) VALUES (%s, 'cuid.ap@x.cl', 'Cuid', 'h')",
               (U_CUID_APERTURAS_A,))
    cx.execute("INSERT INTO membresia (grupo_id, usuario_id, rol, puede_ver_plan) VALUES (%s, %s, 'cuidador', false)",
               (G_A, U_CUID_APERTURAS_A))
    for accion in (*ACCIONES_APERTURA, "relevo.canje"):
        cx.execute("INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, entidad_id)"
                   " VALUES (%s, 'relevo', %s, %s, 'acceso_relevo', %s)", (G_A, ACC_VIGENTE, accion, ACC_VIGENTE))
    cx.execute("INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad)"
               " VALUES (%s, 'relevo', %s, 'relevo.abrir', 'plan_cuidado')", (G_B, uuid.uuid4()))


def _acciones_del_relevo(cx):
    return sorted(r[0] for r in cx.execute("SELECT accion FROM auditoria WHERE actor_tipo = 'relevo'").fetchall())


@pytest.mark.rf("RF-08")
@pytest.mark.parametrize("usuario, grupo, esperado", [
    (U_ADMIN_A, G_A, sorted((*ACCIONES_APERTURA, "relevo.canje"))),  # el admin ya leía todo su grupo (0005)
    (U_CUID_APERTURAS_A, G_A, sorted(ACCIONES_APERTURA)),           # cuidador: solo las cuatro, sin el canje
    (U_PAG2_A, G_A, sorted(ACCIONES_APERTURA)),                     # pagador con puede_ver_plan
    (U_PAG_A, G_A, []),                                             # pagador sin puede_ver_plan
    (U_OBS_A, G_A, []),                                             # observador
    (U_ADMIN_B, G_B, ["relevo.abrir"]),                             # B ve solo lo suyo
    (U_ADMIN_A, G_B, []),                                           # A con el grupo de B: no es miembro
])
def test_aperturas_del_relevo_por_rol(cx, usuario, grupo, esperado):
    _sembrar_aperturas(cx)
    como(cx, usuario_id=usuario, grupo_id=grupo)
    assert _acciones_del_relevo(cx) == esperado


@pytest.mark.rf("RF-08")
def test_aperturas_del_relevo_no_las_ve_ni_operacion_ni_el_relevo(cx):
    _sembrar_aperturas(cx)
    como(cx, rol="operacion")
    assert _acciones_del_relevo(cx) == []
    como(cx, rol="relevo", acceso_relevo_id=ACC_VIGENTE)
    assert _acciones_del_relevo(cx) == []


@pytest.mark.rf("RF-08")
def test_cuidador_sigue_sin_ver_las_lecturas_de_otros_miembros(cx):
    """0010 abre solo las filas del relevo: plan.leer del admin sigue fuera del alcance del cuidador."""
    _sembrar_aperturas(cx)
    cx.execute("INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad)"
               " VALUES (%s, 'usuario', %s, 'plan.leer', 'plan_cuidado')", (G_A, U_ADMIN_A))
    como(cx, usuario_id=U_CUID_APERTURAS_A, grupo_id=G_A)
    assert contar(cx, "auditoria", "actor_tipo = 'usuario'") == 0


# ------------------------------------------------------------------ alertas y reposiciones (MATU-37, migración 0011)

def _perfil_de(cx, grupo):
    """El perfil de la semilla del grupo, leído como superusuario."""
    cx.execute("RESET ROLE")
    return cx.execute("SELECT id FROM perfil_consumo WHERE grupo_id = %s AND producto_id IS NOT NULL",
                      (grupo,)).fetchone()[0]


def _alerta_pendiente(cx, perfil, dias=6):
    cx.execute("RESET ROLE")
    return cx.execute("INSERT INTO alerta_quiebre (perfil_id, fecha_prevista) VALUES (%s, current_date + %s)"
                      " RETURNING id", (perfil, dias)).fetchone()[0]


@pytest.mark.rf("RF-12")
def test_alertas_y_reposiciones_de_otro_grupo_no_se_ven(cx):
    perfil_a = _perfil_de(cx, G_A)
    _alerta_pendiente(cx, perfil_a)
    cx.execute("INSERT INTO reposicion (perfil_id, cantidad_unidades, origen, ocurrida_en) VALUES"
               " (%s, 10, 'declarada', current_date)", (perfil_a,))
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    assert (contar(cx, "alerta_quiebre"), contar(cx, "reposicion")) == (1, 1)
    como(cx, usuario_id=U_ADMIN_B, grupo_id=G_B)
    assert (contar(cx, "alerta_quiebre"), contar(cx, "reposicion")) == (0, 0)
    assert cx.execute("UPDATE alerta_quiebre SET estado = 'descartada', cerrada_en = now() RETURNING id"
                      ).fetchall() == []
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("INSERT INTO reposicion (perfil_id, cantidad_unidades, origen, ocurrida_en, registrada_por)"
                   " VALUES (%s, 5, 'declarada', current_date, %s)", (perfil_a, U_ADMIN_B))


@pytest.mark.rf("RF-12")
def test_operacion_no_ve_alertas_ni_reposiciones_ni_con_grupo(cx):
    _alerta_pendiente(cx, _perfil_de(cx, G_A))
    como(cx, usuario_id=U_ADMIN_B, grupo_id=G_A, rol="operacion")
    assert (contar(cx, "alerta_quiebre"), contar(cx, "reposicion")) == (0, 0)
    assert cx.execute("UPDATE alerta_quiebre SET estado = 'descartada', cerrada_en = now() RETURNING id"
                      ).fetchall() == []


@pytest.mark.rf("RF-12")
@pytest.mark.parametrize("usuario, escribe", [
    (U_ADMIN_A, True),
    (U_CUID_CONSUMO_A, True),
    (U_PAG_A, False),
    (U_PAG2_A, False),
    (U_OBS_A, False),
])
def test_alertas_las_cierran_solo_admin_y_cuidador(cx, usuario, escribe):
    _con_cuidador_a(cx)
    perfil = _perfil_de(cx, G_A)
    _alerta_pendiente(cx, perfil)
    como(cx, usuario_id=usuario, grupo_id=G_A)
    assert contar(cx, "alerta_quiebre") == 1   # leen los cuatro roles
    cerradas = cx.execute("UPDATE alerta_quiebre SET estado = 'descartada', cerrada_en = now() RETURNING id"
                          ).fetchall()
    assert len(cerradas) == (1 if escribe else 0)
    # Nadie de la familia borra una alerta
    assert cx.execute("DELETE FROM alerta_quiebre RETURNING id").fetchall() == []
    cx.execute("SAVEPOINT antes")
    # Nadie de la familia crea una alerta abierta: dispararía un aviso
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("INSERT INTO alerta_quiebre (perfil_id, fecha_prevista) VALUES (%s, current_date + 1)", (perfil,))
    cx.execute("ROLLBACK TO SAVEPOINT antes")
    insertar_cerrada = ("INSERT INTO alerta_quiebre (perfil_id, fecha_prevista, estado, cerrada_en)"
                        " VALUES (%s, current_date + 2, 'descartada', now())")
    if escribe:
        cx.execute(insertar_cerrada, (perfil,))
    else:
        with pytest.raises(errors.InsufficientPrivilege):
            cx.execute(insertar_cerrada, (perfil,))


@pytest.mark.rf("RF-12")
def test_el_sistema_materializa_y_avisa_solo_en_su_grupo(cx):
    perfil = _perfil_de(cx, G_A)
    perfil_b = _perfil_de(cx, G_B)
    como(cx, grupo_id=G_A, rol="sistema")
    alerta = cx.execute("INSERT INTO alerta_quiebre (id, perfil_id, fecha_prevista)"
                        " VALUES (gen_random_uuid(), %s, current_date + 6) RETURNING id", (perfil,)).fetchone()[0]
    assert cx.execute("UPDATE alerta_quiebre SET estado = 'notificada', notificada_en = now() WHERE id = %s"
                      " RETURNING id", (alerta,)).fetchall() == [(alerta,)]
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("INSERT INTO alerta_quiebre (perfil_id, fecha_prevista) VALUES (%s, current_date)", (perfil_b,))


@pytest.mark.rf("RF-12")
@pytest.mark.parametrize("cambio", [
    "estado = 'descartada', cerrada_en = now(), fecha_prevista = fecha_prevista + 1",
    "estado = 'notificada', notificada_en = now()",
    "creada_en = creada_en",          # sin transición: no se admite ningún otro cambio
])
def test_la_familia_solo_cierra_sin_cambiar_la_fecha(cx, cambio):
    _alerta_pendiente(cx, _perfil_de(cx, G_A))
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.CheckViolation):
        cx.execute("UPDATE alerta_quiebre SET " + cambio)


@pytest.mark.rf("RF-12")
def test_una_alerta_cerrada_no_se_reabre_ni_se_cierra_sin_fecha(cx):
    alerta = _alerta_pendiente(cx, _perfil_de(cx, G_A))
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    cx.execute("SAVEPOINT antes")
    with pytest.raises(errors.CheckViolation):
        cx.execute("UPDATE alerta_quiebre SET estado = 'descartada' WHERE id = %s", (alerta,))  # sin cerrada_en
    cx.execute("ROLLBACK TO SAVEPOINT antes")
    cx.execute("UPDATE alerta_quiebre SET estado = 'resuelta', cerrada_en = now() WHERE id = %s", (alerta,))
    with pytest.raises(errors.CheckViolation):
        cx.execute("UPDATE alerta_quiebre SET estado = 'descartada' WHERE id = %s", (alerta,))


@pytest.mark.rf("RF-12")
@pytest.mark.parametrize("usuario, escribe", [
    (U_ADMIN_A, True),
    (U_CUID_CONSUMO_A, True),
    (U_PAG_A, False),
    (U_OBS_A, False),
])
def test_reposiciones_las_declaran_solo_admin_y_cuidador_a_su_nombre(cx, usuario, escribe):
    _con_cuidador_a(cx)
    perfil = _perfil_de(cx, G_A)
    como(cx, usuario_id=usuario, grupo_id=G_A)
    declarar = ("INSERT INTO reposicion (perfil_id, cantidad_unidades, origen, ocurrida_en, registrada_por)"
                " VALUES (%s, 10, 'declarada', current_date, %s)")
    if not escribe:
        with pytest.raises(errors.InsufficientPrivilege):
            cx.execute(declarar, (perfil, usuario))
        return
    cx.execute(declarar, (perfil, usuario))
    assert cx.execute("UPDATE reposicion SET cantidad_unidades = 99 RETURNING id").fetchall() == []
    assert cx.execute("DELETE FROM reposicion RETURNING id").fetchall() == []
    pedido = ("INSERT INTO reposicion (perfil_id, cantidad_unidades, origen, pedido_ref, ocurrida_en, registrada_por)"
              " VALUES (%s, 10, 'pedido_matu', gen_random_uuid(), current_date, %s)")
    for sql, params in ((declarar, (perfil, U_OBS_A)), (pedido, (perfil, usuario))):
        cx.execute("SAVEPOINT antes")
        with pytest.raises(errors.InsufficientPrivilege):
            cx.execute(sql, params)
        cx.execute("ROLLBACK TO SAVEPOINT antes")


@pytest.mark.rf("RF-12")
def test_el_sistema_registra_solo_reposiciones_de_pedido(cx):
    perfil = _perfil_de(cx, G_A)
    como(cx, grupo_id=G_A, rol="sistema")
    cx.execute("INSERT INTO reposicion (perfil_id, cantidad_unidades, origen, pedido_ref, ocurrida_en)"
               " VALUES (%s, 10, 'pedido_matu', gen_random_uuid(), current_date)", (perfil,))
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("INSERT INTO reposicion (perfil_id, cantidad_unidades, origen, ocurrida_en)"
                   " VALUES (%s, 10, 'declarada', current_date)", (perfil,))


@pytest.mark.rf("RF-12")
def test_conservacion_de_alertas_solo_con_operacion_y_con_sus_plazos(cx):
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("SELECT * FROM quiebre_conservar(now() - interval '90 days', now() - interval '30 days', now())")
    cx.rollback()
    for limites in ("now() - interval '89 days', now() - interval '30 days'",
                    "now() - interval '90 days', now() - interval '29 days'"):
        como(cx, rol="operacion")
        with pytest.raises(errors.InvalidParameterValue):
            cx.execute(f"SELECT * FROM quiebre_conservar({limites}, now())")
        cx.rollback()


@pytest.mark.rf("RF-12")
def test_conservacion_de_alertas_borra_lo_vencido_y_deja_lo_reciente(cx):
    perfil = _perfil_de(cx, G_A)
    cx.execute(
        "INSERT INTO alerta_quiebre (perfil_id, fecha_prevista, estado, creada_en, cerrada_en) VALUES"
        " (%(p)s, current_date - 200, 'descartada', now() - interval '200 days', now() - interval '91 days'),"
        " (%(p)s, current_date - 100, 'resuelta', now() - interval '100 days', now() - interval '89 days'),"
        " (%(p)s, current_date - 300, 'pendiente', now() - interval '300 days', NULL)",
        {"p": perfil},
    )
    cx.execute("DELETE FROM evento_outbox")
    cx.execute(
        "INSERT INTO evento_outbox (grupo_id, tipo, agregado_tipo, agregado_id, publicado_en) VALUES"
        " (%(g)s, 'QuiebreProximo', 'alerta_quiebre', gen_random_uuid(), now() - interval '31 days'),"
        " (%(g)s, 'QuiebreProximo', 'alerta_quiebre', gen_random_uuid(), now() - interval '29 days'),"
        " (%(g)s, 'QuiebreProximo', 'alerta_quiebre', gen_random_uuid(), NULL)",
        {"g": G_A},
    )
    cx.execute("DELETE FROM notificacion")
    cx.execute(
        "INSERT INTO notificacion (usuario_id, grupo_id, evento_id, canal, plantilla, creada_en) VALUES"
        " (%(u)s, %(g)s, 1, 'push', 'quiebre_proximo', now() - interval '91 days'),"
        " (%(u)s, %(g)s, 2, 'push', 'quiebre_proximo', now() - interval '10 days')",
        {"u": U_ADMIN_A, "g": G_A},
    )
    como(cx, rol="operacion")
    fila = cx.execute("SELECT * FROM quiebre_conservar(now() - interval '90 days', now() - interval '30 days',"
                      " now())").fetchone()
    assert fila == (1, 1, 1, 0)  # MATU-51: el cuarto contador, las compras declaradas
    cx.execute("RESET ROLE")
    assert contar(cx, "alerta_quiebre", f"perfil_id = '{perfil}'") == 2
    assert contar(cx, "evento_outbox") == 2
    assert contar(cx, "notificacion") == 1


# ---- MATU-41 (migración 0014): avisos, dispositivo para el sistema, publicador del outbox y conservación

DISP_OBS_A = uuid.UUID("00000000-0000-0000-0000-0000000009a2")


def _dispositivo_obs_a(cx):
    """Un dispositivo con push_token del observador del grupo A, como superusuario en la transacción."""
    cx.execute("RESET ROLE")
    cx.execute(
        "INSERT INTO dispositivo (id, usuario_id, plataforma, push_token) VALUES (%s, %s, 'web', %s)",
        (DISP_OBS_A, U_OBS_A, "https://fcm.googleapis.com/fcm/send/obs-a"),
    )


@pytest.mark.rf("RF-39")
def test_el_sistema_ve_solo_los_dispositivos_de_miembros_activos_de_su_grupo(cx):
    _sembrar_sesiones(cx)
    _dispositivo_obs_a(cx)
    como(cx, grupo_id=G_A, rol="sistema")
    assert {r[0] for r in cx.execute("SELECT id FROM dispositivo").fetchall()} == {DISP_A, DISP_OBS_A}
    # Sin grupo, el sistema no ve ninguno; con el otro grupo, solo los de ese grupo
    como(cx, rol="sistema")
    assert contar(cx, "dispositivo") == 0
    como(cx, grupo_id=G_B, rol="sistema")
    assert [r[0] for r in cx.execute("SELECT id FROM dispositivo").fetchall()] == [DISP_B]
    # La familia con el grupo en contexto, sin el rol sistema, sigue viendo solo los suyos
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    assert [r[0] for r in cx.execute("SELECT id FROM dispositivo").fetchall()] == [DISP_A]


@pytest.mark.rf("RF-39")
def test_el_sistema_no_ve_el_dispositivo_de_un_miembro_retirado(cx):
    _dispositivo_obs_a(cx)
    cx.execute("UPDATE membresia SET estado = 'retirada' WHERE usuario_id = %s AND grupo_id = %s", (U_OBS_A, G_A))
    como(cx, grupo_id=G_A, rol="sistema")
    assert contar(cx, "dispositivo", f"id = '{DISP_OBS_A}'") == 0
    assert cx.execute("UPDATE dispositivo SET push_token = NULL WHERE id = %s RETURNING id", (DISP_OBS_A,)
                      ).fetchall() == []


@pytest.mark.rf("RF-39")
def test_el_sistema_solo_borra_el_push_token(cx):
    _sembrar_sesiones(cx)
    como(cx, grupo_id=G_A, rol="sistema")
    assert cx.execute("UPDATE dispositivo SET push_token = NULL WHERE id = %s RETURNING id", (DISP_A,)
                      ).fetchall() == [(DISP_A,)]
    for cambio in ("push_token = 'https://otro.example/x'", "revocado_en = now()", "nombre = 'otro'"):
        cx.execute("SAVEPOINT antes")
        with pytest.raises((errors.CheckViolation, errors.InsufficientPrivilege)):
            cx.execute(f"UPDATE dispositivo SET {cambio} WHERE id = %s", (DISP_A,))
        cx.execute("ROLLBACK TO SAVEPOINT antes")
    # El dispositivo del otro grupo no se alcanza
    assert cx.execute("UPDATE dispositivo SET push_token = NULL WHERE id = %s RETURNING id", (DISP_B,)
                      ).fetchall() == []
    # Ni lo borra
    assert cx.execute("DELETE FROM dispositivo RETURNING id").fetchall() == []


@pytest.mark.rf("RF-39")
def test_notificaciones_y_preferencias_de_otro_grupo_no_las_ve_el_sistema(cx):
    cx.execute(
        "INSERT INTO notificacion (usuario_id, grupo_id, evento_id, canal, plantilla) VALUES"
        " (%s, %s, 1, 'correo', 'quiebre_proximo'), (%s, %s, 2, 'correo', 'quiebre_proximo')",
        (U_ADMIN_A, G_A, U_ADMIN_B, G_B),
    )
    cx.execute(
        "INSERT INTO preferencia_notificacion (usuario_id, tipo_evento, canal, activo) VALUES"
        " (%s, 'quiebre_proximo', 'correo', false), (%s, 'quiebre_proximo', 'correo', true)",
        (U_ADMIN_A, U_ADMIN_B),
    )
    como(cx, grupo_id=G_A, rol="sistema")
    assert contar(cx, "notificacion") == 1 and contar(cx, "preferencia_notificacion") == 1
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("INSERT INTO notificacion (usuario_id, grupo_id, evento_id, canal, plantilla)"
                   " VALUES (%s, %s, 3, 'push', 'quiebre_proximo')", (U_ADMIN_B, G_B))


@pytest.mark.rf("RF-39")
def test_la_preferencia_propia_no_lee_ni_escribe_la_ajena(cx):
    cx.execute(
        "INSERT INTO preferencia_notificacion (usuario_id, tipo_evento, canal, activo)"
        " VALUES (%s, 'quiebre_proximo', 'correo', false)", (U_ADMIN_B,),
    )
    como(cx, usuario_id=U_ADMIN_A)
    assert contar(cx, "preferencia_notificacion") == 0
    assert cx.execute("UPDATE preferencia_notificacion SET activo = true RETURNING usuario_id").fetchall() == []
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("INSERT INTO preferencia_notificacion (usuario_id, tipo_evento, canal, activo)"
                   " VALUES (%s, 'quiebre_proximo', 'push', true)", (U_ADMIN_B,))


@pytest.mark.rf("RF-39")
def test_notificacion_error_es_de_lista_cerrada(cx):
    with pytest.raises(errors.CheckViolation):
        cx.execute("INSERT INTO notificacion (usuario_id, grupo_id, evento_id, canal, plantilla, estado, error)"
                   " VALUES (%s, %s, 1, 'push', 'quiebre_proximo', 'fallida', '410 Gone: endpoint')", (U_ADMIN_A, G_A))


@pytest.mark.rf("RF-39")
@pytest.mark.parametrize("llamada", [
    "SELECT * FROM outbox_tomar(10, now())",
    "SELECT outbox_publicado(1, now())",
    "SELECT outbox_reintentar(1, now() + interval '1 minute', now())",
    "SELECT outbox_posponer(1, now() + interval '1 hour', now())",
])
@pytest.mark.parametrize("contexto", [
    {"usuario_id": U_ADMIN_A, "grupo_id": G_A},
    {"grupo_id": G_A, "rol": "sistema"},
    {},
])
def test_el_outbox_solo_lo_publica_operacion(cx, llamada, contexto):
    como(cx, **contexto)
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute(llamada)
    cx.rollback()
    # Ni con operación lee la tabla directamente
    como(cx, rol="operacion")
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("SELECT id FROM evento_outbox")


def _evento(cx, grupo=G_A, **columnas):
    cx.execute("RESET ROLE")
    nombres = ", ".join(["grupo_id", "tipo", "agregado_tipo", "agregado_id", *columnas])
    marcas = ", ".join(["%s"] * (4 + len(columnas)))
    return cx.execute(
        f"INSERT INTO evento_outbox ({nombres}) VALUES ({marcas}) RETURNING id",
        (grupo, "QuiebreProximo", "alerta_quiebre", uuid.uuid4(), *columnas.values()),
    ).fetchone()[0]


@pytest.mark.rf("RF-39")
def test_operacion_toma_arrienda_reintenta_y_falla_al_octavo(cx):
    cx.execute("DELETE FROM evento_outbox")
    a = _evento(cx)
    b = _evento(cx, grupo=G_B)
    _evento(cx, disponible_en="2100-01-01T00:00:00Z")  # todavía no disponible
    como(cx, rol="operacion")
    assert [r[0] for r in cx.execute("SELECT id FROM outbox_tomar(10, now(), %s)", (G_A,)).fetchall()] == [a]
    # Arrendado: otro publicador no lo vuelve a tomar
    assert [r[0] for r in cx.execute("SELECT id FROM outbox_tomar(10, now())").fetchall()] == [b]
    assert cx.execute("SELECT * FROM outbox_tomar(10, now())").fetchall() == []
    for intento in range(1, 8):
        quedo_fallido = cx.execute("SELECT outbox_reintentar(%s, now() + interval '1 second', now())", (a,)).fetchone()
        assert quedo_fallido == (False,), intento
    assert cx.execute("SELECT outbox_reintentar(%s, now() + interval '1 second', now())", (a,)).fetchone() == (True,)
    assert cx.execute("SELECT outbox_publicado(%s, now())", (b,)).fetchone() == (True,)
    cx.execute("RESET ROLE")
    assert cx.execute("SELECT intentos, fallido_en IS NOT NULL FROM evento_outbox WHERE id = %s", (a,)
                      ).fetchone() == (8, True)
    assert cx.execute("SELECT publicado_en IS NOT NULL FROM evento_outbox WHERE id = %s", (b,)).fetchone() == (True,)


@pytest.mark.rf("RF-39")
def test_posponer_no_suma_un_intento_y_tiene_limite(cx):
    cx.execute("DELETE FROM evento_outbox")
    a = _evento(cx)
    como(cx, rol="operacion")
    assert cx.execute("SELECT outbox_posponer(%s, now() + interval '5 hours', now())", (a,)).fetchone() == (True,)
    assert cx.execute("SELECT * FROM outbox_tomar(10, now())").fetchall() == []
    cx.execute("SAVEPOINT antes")
    with pytest.raises(errors.InvalidParameterValue):
        cx.execute("SELECT outbox_posponer(%s, now() + interval '2 days', now())", (a,))
    cx.execute("ROLLBACK TO SAVEPOINT antes")
    cx.execute("RESET ROLE")
    assert cx.execute("SELECT intentos FROM evento_outbox WHERE id = %s", (a,)).fetchone() == (0,)


@pytest.mark.rf("RF-39")
def test_conservacion_borra_los_fallidos_a_los_30_dias_con_su_evento_consumido(cx):
    cx.execute("DELETE FROM evento_outbox")
    cx.execute("DELETE FROM evento_consumido")
    viejo = _evento(cx, fallido_en="2026-01-01T00:00:00Z")
    reciente = _evento(cx, fallido_en="2026-01-01T00:00:00Z")
    publicado = _evento(cx, publicado_en="2026-01-01T00:00:00Z")
    pendiente = _evento(cx)
    cx.execute("UPDATE evento_outbox SET fallido_en = now() - interval '31 days' WHERE id = %s", (viejo,))
    cx.execute("UPDATE evento_outbox SET fallido_en = now() - interval '29 days' WHERE id = %s", (reciente,))
    cx.execute("UPDATE evento_outbox SET publicado_en = now() - interval '31 days' WHERE id = %s", (publicado,))
    for evento in (viejo, reciente, publicado, pendiente):
        cx.execute("INSERT INTO evento_consumido (evento_id, consumidor) VALUES (%s, 'notifications.quiebre_proximo')",
                   (evento,))
    como(cx, rol="operacion")
    fila = cx.execute("SELECT * FROM quiebre_conservar(now() - interval '90 days', now() - interval '30 days',"
                      " now())").fetchone()
    assert fila[1] == 2  # el fallido viejo y el publicado viejo
    cx.execute("RESET ROLE")
    assert {r[0] for r in cx.execute("SELECT id FROM evento_outbox").fetchall()} == {reciente, pendiente}
    assert {r[0] for r in cx.execute("SELECT evento_id FROM evento_consumido").fetchall()} == {reciente, pendiente}


# ---- MATU-60 (migración 0015): unidades por envase en el perfil y la lista de insumos
# La columna no cambia RLS: las políticas de la 0009 deciden filas. La lista lee lo mismo que «Se acaban
# pronto» (perfil_consumo con su alerta), así que no hay tabla ni política nueva.


@pytest.mark.rf("RF-15")
def test_envase_de_otro_grupo_no_se_lee_ni_se_cambia(cx):
    como(cx, usuario_id=U_ADMIN_B, grupo_id=G_B)
    assert cx.execute("SELECT unidades_por_envase FROM perfil_consumo WHERE grupo_id = %s", (G_A,)).fetchall() == []
    assert cx.execute("UPDATE perfil_consumo SET unidades_por_envase = 20 WHERE grupo_id = %s RETURNING id",
                      (G_A,)).fetchall() == []
    # Con el grupo ajeno en contexto y sin membresía, tampoco
    como(cx, usuario_id=U_ADMIN_B, grupo_id=G_A)
    assert cx.execute("UPDATE perfil_consumo SET unidades_por_envase = 20 RETURNING id").fetchall() == []
    # La lista une el perfil con su alerta: desde el grupo B no aparece nada del A
    como(cx, usuario_id=U_ADMIN_B, grupo_id=G_B)
    assert cx.execute(
        "SELECT p.id FROM perfil_consumo p LEFT JOIN alerta_quiebre a ON a.perfil_id = p.id"
        " WHERE p.persona_cuidada_id = %s", (P_A,)).fetchall() == []
    cx.execute("RESET ROLE")
    assert cx.execute("SELECT unidades_por_envase FROM perfil_consumo WHERE grupo_id = %s",
                      (G_A,)).fetchall() == [(None,)]


@pytest.mark.rf("RF-15")
@pytest.mark.parametrize("usuario, cambia", [
    (U_ADMIN_A, True),
    (U_CUID_CONSUMO_A, True),
    (U_PAG_A, False),
    (U_PAG2_A, False),
    (U_OBS_A, False),
])
def test_el_envase_lo_leen_todos_y_lo_cambian_admin_y_cuidador(cx, usuario, cambia):
    _con_cuidador_a(cx)
    como(cx, usuario_id=usuario, grupo_id=G_A)
    assert cx.execute("SELECT unidades_por_envase FROM perfil_consumo").fetchall() == [(None,)]
    filas = cx.execute("UPDATE perfil_consumo SET unidades_por_envase = 20 RETURNING id").fetchall()
    assert len(filas) == (1 if cambia else 0)


@pytest.mark.rf("RF-14")
@pytest.mark.parametrize("valor, acepta", [(None, True), (1, True), (10_000, True), (0, False), (10_001, False),
                                           (-5, False)])
def test_envase_admite_null_o_de_1_a_10000(cx, valor, acepta):
    if acepta:
        cx.execute("UPDATE perfil_consumo SET unidades_por_envase = %s WHERE grupo_id = %s", (valor, G_A))
        assert cx.execute("SELECT unidades_por_envase FROM perfil_consumo WHERE grupo_id = %s",
                          (G_A,)).fetchall() == [(valor,)]
    else:
        with pytest.raises(errors.CheckViolation):
            cx.execute("UPDATE perfil_consumo SET unidades_por_envase = %s WHERE grupo_id = %s", (valor, G_A))


# ---- MATU-44 (migración 0016): retirar con motivo, solo admin y cuidador, y la destrucción a los 90 días

U_CUID_RETIRO_A = uuid.UUID("00000000-0000-0000-0000-0000000000a8")
_RETIRAR_SQL = "UPDATE consentimiento SET revocado_en = now(), revocacion_motivo = 'retiro' WHERE id = %s"


def _cuidador_retiro(cx):
    """Un cuidador de G_A, como superusuario en la transacción que se revierte."""
    cx.execute("INSERT INTO usuario (id, email, nombre, password_hash) VALUES (%s, 'cuid.ret@x.cl', 'Cuid', 'h')",
               (U_CUID_RETIRO_A,))
    cx.execute("INSERT INTO membresia (grupo_id, usuario_id, rol, puede_ver_plan) VALUES (%s, %s, 'cuidador', false)",
               (G_A, U_CUID_RETIRO_A))


@pytest.mark.rf("RF-02")
@pytest.mark.parametrize("usuario", [U_ADMIN_A, U_CUID_RETIRO_A])
def test_retiran_admin_y_cuidador(cx, usuario):
    _cuidador_retiro(cx)
    cid = _consentimiento(cx)
    como(cx, usuario_id=usuario, grupo_id=G_A)
    assert cx.execute(_RETIRAR_SQL, (cid,)).rowcount == 1


@pytest.mark.rf("RF-02")
@pytest.mark.parametrize("usuario", [U_OBS_A, U_PAG_A, U_PAG2_A])
def test_barrera_por_rol_pagador_y_observador_no_retiran(cx, usuario):
    """Antes de la 0016 cualquier miembro fijaba revocado_en por SQL directo. Ahora RLS no les muestra la fila."""
    cid = _consentimiento(cx)
    como(cx, usuario_id=usuario, grupo_id=G_A)
    assert cx.execute(_RETIRAR_SQL, (cid,)).rowcount == 0
    cx.execute("RESET ROLE")
    assert cx.execute("SELECT revocado_en FROM consentimiento WHERE id = %s", (cid,)).fetchone() == (None,)


@pytest.mark.rf("RF-02")
def test_otro_grupo_no_retira(cx):
    cid = _consentimiento(cx)
    como(cx, usuario_id=U_ADMIN_B, grupo_id=G_B)
    assert cx.execute(_RETIRAR_SQL, (cid,)).rowcount == 0


@pytest.mark.rf("RF-02")
def test_la_revocacion_exige_su_motivo_una_vez(cx):
    cid = _consentimiento(cx)
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.InsufficientPrivilege), cx.transaction():  # sin motivo, el trigger la rechaza
        cx.execute("UPDATE consentimiento SET revocado_en = now() WHERE id = %s", (cid,))
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("UPDATE consentimiento SET revocado_en = now(), revocacion_motivo = 'otro' WHERE id = %s", (cid,))
    assert cx.execute(_RETIRAR_SQL, (cid,)).rowcount == 1
    with pytest.raises(errors.InsufficientPrivilege):  # el motivo tampoco cambia después
        cx.execute("UPDATE consentimiento SET revocacion_motivo = 'renovacion' WHERE id = %s", (cid,))


@pytest.mark.rf("RF-02")
def test_el_motivo_no_va_sin_revocado_en(cx):
    with pytest.raises(errors.CheckViolation):
        cx.execute(
            "INSERT INTO consentimiento (grupo_id, persona_cuidada_id, usuario_id, calidad_otorgante, finalidad,"
            " version_politica, evidencia, revocacion_motivo) VALUES (%s, %s, %s, 'titular', 'consumo', 'v1',"
            " '{}', 'retiro')", (G_A, P_A, U_ADMIN_A))


def _retiro_de_plan(cx, hace: str):
    """El consentimiento de plan_cuidado de P_A, retirado hace ``hace`` (superusuario, en la transacción)."""
    cx.execute(
        "INSERT INTO consentimiento (grupo_id, persona_cuidada_id, usuario_id, calidad_otorgante, finalidad,"
        " version_politica, evidencia, otorgado_en, revocado_en, revocacion_motivo)"
        f" VALUES (%s, %s, %s, 'titular', 'plan_cuidado', '0.10', '{{}}', now() - interval '200 days',"
        f" now() - interval '{hace}', 'retiro')", (G_A, P_A, U_ADMIN_A))


def _clave_destruida(cx, persona):
    cx.execute("RESET ROLE")
    fila = cx.execute("SELECT dek_cifrada_con_kek IS NULL, destruida_en IS NOT NULL FROM clave_datos"
                      " WHERE persona_cuidada_id = %s", (persona,)).fetchone()
    return fila


@pytest.mark.rf("RF-02")
def test_destruir_claves_exige_operacion_y_los_90_dias(cx):
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("SELECT plan_destruir_claves(now() - interval '90 days', now())")
    cx.rollback()
    como(cx, rol="operacion")
    with pytest.raises(errors.InvalidParameterValue):
        cx.execute("SELECT plan_destruir_claves(now() - interval '89 days', now())")
    cx.rollback()
    como(cx, rol="operacion")
    with pytest.raises(errors.InvalidParameterValue):
        cx.execute("SELECT plan_destruir_claves(now(), now() + interval '91 days')")
    cx.rollback()
    como(cx, rol="operacion")
    # Sin retiros en la semilla: no destruye nada y devuelve solo un contador
    assert cx.execute("SELECT plan_destruir_claves(now() - interval '90 days', now())").fetchone() == (0,)


@pytest.mark.rf("RF-02")
@pytest.mark.parametrize(("hace", "destruye"), [("91 days", True), ("89 days", False)])
def test_destruir_claves_solo_tras_90_dias_y_solo_esa_persona(cx, hace, destruye):
    _retiro_de_plan(cx, hace)
    como(cx, rol="operacion")
    assert cx.execute("SELECT plan_destruir_claves(now() - interval '90 days', now())").fetchone() == (int(destruye),)
    assert _clave_destruida(cx, P_A) == (destruye, destruye)
    # CL-6: con la clave se van las filas cifradas con ella (secciones y campos base) y el plan queda en 0
    secciones_a = contar(cx, "plan_seccion", f"plan_id = '{PLAN_A}'")
    assert secciones_a == (0 if destruye else 3)
    if destruye:
        assert cx.execute("SELECT completitud_pct FROM plan_cuidado WHERE id = %s", (PLAN_A,)).fetchone() == (0,)
    # La otra familia no se toca
    assert _clave_destruida(cx, P_B) == (False, False)
    assert contar(cx, "plan_seccion", f"plan_id = '{PLAN_B}'") == 1
    filas = cx.execute("SELECT actor_tipo, actor_ref, entidad, detalle FROM auditoria WHERE accion = 'clave.destruir'"
                       " AND grupo_id = %s", (G_A,)).fetchall()
    assert filas == ([("sistema", None, "clave_datos", None)] if destruye else [])


@pytest.mark.rf("RF-02")
def test_destruir_claves_es_idempotente(cx):
    _retiro_de_plan(cx, "100 days")
    como(cx, rol="operacion")
    assert cx.execute("SELECT plan_destruir_claves(now() - interval '90 days', now())").fetchone() == (1,)
    assert cx.execute("SELECT plan_destruir_claves(now() - interval '90 days', now())").fetchone() == (0,)
    cx.execute("RESET ROLE")
    assert cx.execute("SELECT count(*) FROM auditoria WHERE accion = 'clave.destruir'").fetchone() == (1,)


@pytest.mark.rf("RF-02")
def test_destruir_claves_no_toca_a_quien_volvio_a_autorizar(cx):
    _retiro_de_plan(cx, "100 days")
    _consentimiento(cx)  # una autorización nueva de plan_cuidado, no revocada
    como(cx, rol="operacion")
    assert cx.execute("SELECT plan_destruir_claves(now() - interval '90 days', now())").fetchone() == (0,)


@pytest.mark.rf("RF-02")
def test_operacion_sigue_sin_leer_clave_datos(cx):
    """Las políticas de la 0016 son solo para matu_owner: matu_app con app.rol = 'operacion' no ve claves."""
    como(cx, rol="operacion")
    assert contar(cx, "clave_datos") == 0
    assert cx.execute("UPDATE clave_datos SET dek_cifrada_con_kek = NULL, destruida_en = now()").rowcount == 0


@pytest.mark.rf("RF-02")
def test_clave_nueva_solo_tras_una_autorizacion_nueva_y_la_destruida_sigue_destruida(cx):
    """MATU-44, P8: después de destruida la clave, una autorización nueva para plan_cuidado deja crear otra para
    contenido nuevo. La destruida no cambia y hay una sola no destruida por persona (clave_datos_vigente_uq)."""
    _retiro_de_plan(cx, "100 days")
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    cx.execute("UPDATE clave_datos SET dek_cifrada_con_kek = NULL, destruida_en = now() - interval '1 day'"
               " WHERE persona_cuidada_id = %s", (P_A,))
    nueva = """INSERT INTO clave_datos (grupo_id, persona_cuidada_id, dek_cifrada_con_kek, kek_version)
               VALUES (%s, %s, '\\x06', 1)"""
    with pytest.raises(errors.CheckViolation), cx.transaction():  # sin autorización nueva
        cx.execute(nueva, (G_A, P_A))
    cx.execute("RESET ROLE")
    _consentimiento(cx)  # otorgada ahora, después de la destrucción
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    cx.execute(nueva, (G_A, P_A))
    with pytest.raises(errors.UniqueViolation), cx.transaction():  # una sola vigente
        cx.execute(nueva, (G_A, P_A))
    assert cx.execute("SELECT count(*) FILTER (WHERE destruida_en IS NOT NULL AND dek_cifrada_con_kek IS NULL),"
                      " count(*) FILTER (WHERE destruida_en IS NULL) FROM clave_datos WHERE persona_cuidada_id = %s",
                      (P_A,)).fetchone() == (1, 1)


# ---- MATU-51 (migración 0017): «Compré» declara reposiciones y la conservación las borra a los 90 días
# Las políticas de INSERT de la 0011 no cambian: reposicion_declarar (admin y cuidador, a su nombre, perfil del
# grupo) y reposicion_pedido (solo sistema). La 0017 suma dos políticas solo para matu_owner con operación.


@pytest.mark.rf("RF-11")
def test_reposicion_no_se_declara_sobre_un_perfil_de_otro_grupo(cx):
    """Condición 5 del analista: el admin de B no puede anotar una compra sobre un perfil de A, ni ver las de A."""
    perfil_a = _perfil_de(cx, G_A)
    cx.execute("INSERT INTO reposicion (perfil_id, cantidad_unidades, origen, ocurrida_en, registrada_por)"
               " VALUES (%s, 5, 'declarada', current_date, %s)", (perfil_a, U_ADMIN_A))
    como(cx, usuario_id=U_ADMIN_B, grupo_id=G_B)
    assert contar(cx, "reposicion", f"perfil_id = '{perfil_a}'") == 0
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("INSERT INTO reposicion (perfil_id, cantidad_unidades, origen, ocurrida_en, registrada_por)"
                   " VALUES (%s, 5, 'declarada', current_date, %s)", (perfil_a, U_ADMIN_B))


@pytest.mark.rf("RF-11")
def test_reposicion_acepta_lo_que_sale_de_envases_hasta_el_tope_del_stock(cx):
    """Decisión 146: cantidad_unidades solo exige > 0; 99 envases de 1.000 caben sin cambiar la columna."""
    perfil = _perfil_de(cx, G_A)
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    cx.execute("INSERT INTO reposicion (perfil_id, cantidad_unidades, origen, ocurrida_en, registrada_por)"
               " VALUES (%s, 99000, 'declarada', current_date, %s)", (perfil, U_ADMIN_A))
    with pytest.raises(errors.CheckViolation):
        cx.execute("INSERT INTO reposicion (perfil_id, cantidad_unidades, origen, ocurrida_en, registrada_por)"
                   " VALUES (%s, 0, 'declarada', current_date, %s)", (perfil, U_ADMIN_A))


@pytest.mark.rf("RF-11")
def test_conservacion_borra_las_compras_declaradas_a_los_90_dias(cx):
    """Decisión 145: declaradas con registrada_en de 90 días o más se borran; las recientes y las de pedido no."""
    perfil = _perfil_de(cx, G_A)
    cx.execute(
        "INSERT INTO reposicion (perfil_id, cantidad_unidades, origen, pedido_ref, ocurrida_en, registrada_en) VALUES"
        " (%(p)s, 5, 'declarada', NULL, current_date - 91, now() - interval '91 days'),"
        " (%(p)s, 6, 'declarada', NULL, current_date - 89, now() - interval '89 days'),"
        " (%(p)s, 7, 'pedido_matu', gen_random_uuid(), current_date - 200, now() - interval '200 days')",
        {"p": perfil},
    )
    como(cx, rol="operacion")
    fila = cx.execute("SELECT reposiciones FROM quiebre_conservar(now() - interval '90 days',"
                      " now() - interval '30 days', now())").fetchone()
    assert fila == (1,)
    cx.execute("RESET ROLE")
    restantes = {r[0] for r in cx.execute("SELECT cantidad_unidades FROM reposicion WHERE perfil_id = %s",
                                          (perfil,)).fetchall()}
    assert {6, 7} <= restantes and 5 not in restantes


@pytest.mark.rf("RF-11")
def test_operacion_no_lee_ni_borra_reposiciones_como_matu_app(cx):
    """Las políticas de la 0017 son solo para matu_owner: matu_app con app.rol = 'operacion' no ve ni borra."""
    perfil = _perfil_de(cx, G_A)
    cx.execute("INSERT INTO reposicion (perfil_id, cantidad_unidades, origen, ocurrida_en, registrada_en)"
               " VALUES (%s, 5, 'declarada', current_date - 200, now() - interval '200 days')", (perfil,))
    como(cx, rol="operacion")
    assert contar(cx, "reposicion") == 0
    assert cx.execute("DELETE FROM reposicion").rowcount == 0
    cx.execute("RESET ROLE")
    assert contar(cx, "reposicion", f"perfil_id = '{perfil}'") == 1


# ---- MATU-72 (migración 0018): borrar a la persona, solo admin y cuidador, y la marca durable

_BORRAR_PERSONA_SQL = (
    "UPDATE persona_cuidada SET eliminado_en = now(), datos_borrados_en = now(), nombre = 'borrada',"
    " nombre_pila = 'borrada', nivel_apoyo = NULL, direccion_entrega_id = NULL WHERE id = %s"
)


@pytest.mark.rf("RF-01")
@pytest.mark.parametrize("usuario", [U_ADMIN_A, U_CUID_RETIRO_A])
def test_borran_a_la_persona_admin_y_cuidador(cx, usuario):
    _cuidador_retiro(cx)
    como(cx, usuario_id=usuario, grupo_id=G_A)
    assert cx.execute(_BORRAR_PERSONA_SQL, (P_A,)).rowcount == 1


@pytest.mark.rf("RF-01")
@pytest.mark.parametrize("usuario", [U_OBS_A, U_PAG_A, U_PAG2_A])
def test_barrera_por_rol_pagador_y_observador_no_tocan_a_la_persona(cx, usuario):
    """C2: antes de la 0018 cualquier miembro modificaba la persona por SQL directo. Ahora la ven y no la tocan."""
    como(cx, usuario_id=usuario, grupo_id=G_A)
    assert contar(cx, "persona_cuidada", f"id = '{P_A}'") == 1
    assert cx.execute(_BORRAR_PERSONA_SQL, (P_A,)).rowcount == 0
    assert cx.execute("UPDATE persona_cuidada SET nombre = 'x' WHERE id = %s", (P_A,)).rowcount == 0
    assert cx.execute("DELETE FROM persona_cuidada WHERE id = %s", (P_A,)).rowcount == 0
    # Tampoco la bloquean: FOR UPDATE exige la política de UPDATE y la fila no aparece
    assert cx.execute("SELECT id FROM persona_cuidada WHERE id = %s FOR UPDATE", (P_A,)).fetchall() == []
    with pytest.raises(errors.InsufficientPrivilege), cx.transaction():
        cx.execute("INSERT INTO persona_cuidada (grupo_id, nombre, nombre_pila, nivel_apoyo) VALUES"
                   " (%s, 'Nueva Persona', 'Nueva', 'apoyo_total')", (G_A,))
    cx.execute("RESET ROLE")
    assert cx.execute("SELECT nombre, eliminado_en FROM persona_cuidada WHERE id = %s", (P_A,)).fetchone() == (
        "María Soto", None)


@pytest.mark.rf("RF-01")
def test_otro_grupo_no_borra_ni_ve_a_la_persona(cx):
    como(cx, usuario_id=U_ADMIN_B, grupo_id=G_B)
    assert contar(cx, "persona_cuidada", f"id = '{P_A}'") == 0
    assert cx.execute(_BORRAR_PERSONA_SQL, (P_A,)).rowcount == 0
    # Con el grupo ajeno en contexto, sin membresía allí, tampoco
    como(cx, usuario_id=U_ADMIN_B, grupo_id=G_A)
    assert cx.execute(_BORRAR_PERSONA_SQL, (P_A,)).rowcount == 0
    cx.execute("RESET ROLE")
    assert cx.execute("SELECT datos_borrados_en FROM persona_cuidada WHERE id = %s", (P_A,)).fetchone() == (None,)


@pytest.mark.rf("RF-01")
def test_borrar_a_una_persona_no_toca_a_la_otra(cx):
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    assert cx.execute(_BORRAR_PERSONA_SQL, (P_A,)).rowcount == 1
    cx.execute("RESET ROLE")
    assert cx.execute("SELECT nombre, datos_borrados_en FROM persona_cuidada WHERE id = %s", (P_B,)).fetchone() == (
        "Luis Pérez", None)


@pytest.mark.rf("RF-01")
def test_una_persona_borrada_no_se_vuelve_a_modificar(cx):
    """Trigger persona_borrada_fija: nadie la revive, ni el admin ni el superusuario."""
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    assert cx.execute(_BORRAR_PERSONA_SQL, (P_A,)).rowcount == 1
    with pytest.raises(errors.InsufficientPrivilege), cx.transaction():
        cx.execute("UPDATE persona_cuidada SET eliminado_en = NULL, datos_borrados_en = NULL, nivel_apoyo ="
                   " 'apoyo_total', nombre = 'María Soto' WHERE id = %s", (P_A,))
    cx.execute("RESET ROLE")
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("UPDATE persona_cuidada SET nombre = 'María Soto' WHERE id = %s", (P_A,))


@pytest.mark.rf("RF-01")
@pytest.mark.parametrize("cambio", [
    "nivel_apoyo = NULL",  # sin eliminado_en
    "datos_borrados_en = now()",  # sin eliminado_en ni nivel_apoyo en NULL
    "datos_borrados_en = now(), eliminado_en = now(), nivel_apoyo = NULL",  # con la dirección todavía
])
def test_la_marca_del_borrado_exige_la_fila_sin_datos(cx, cambio):
    with pytest.raises(errors.CheckViolation):
        cx.execute(f"UPDATE persona_cuidada SET {cambio} WHERE id = %s", (P_A,))


@pytest.mark.rf("RF-01")
def test_el_motivo_borrado_existe_y_se_fija_una_vez(cx):
    cid = _consentimiento(cx)
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    assert cx.execute("UPDATE consentimiento SET revocado_en = now(), revocacion_motivo = 'borrado' WHERE id = %s",
                      (cid,)).rowcount == 1
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("UPDATE consentimiento SET revocacion_motivo = 'retiro' WHERE id = %s", (cid,))


@pytest.mark.rf("RF-01")
@pytest.mark.parametrize("usuario", [U_OBS_A, U_PAG_A])
def test_pagador_y_observador_no_revocan_con_motivo_borrado(cx, usuario):
    cid = _consentimiento(cx)
    como(cx, usuario_id=usuario, grupo_id=G_A)
    assert cx.execute("UPDATE consentimiento SET revocado_en = now(), revocacion_motivo = 'borrado' WHERE id = %s",
                      (cid,)).rowcount == 0


# ------------------------------------------------------------------ catálogo (MATU-59, decisión 169)


@pytest.mark.rf("RF-20")
@pytest.mark.parametrize("usuario, grupo", [(U_ADMIN_A, G_A), (U_OBS_A, G_A), (U_ADMIN_B, G_B), (U_NUEVO, None)])
def test_la_familia_lee_el_catalogo_pero_no_cambia_precio_stock_ni_retracto(cx, usuario, grupo):
    como(cx, usuario_id=usuario, grupo_id=grupo)
    assert contar(cx, "oferta", f"id = '{OFERTA}'") == 1
    assert contar(cx, "producto", f"id = '{PRODUCTO}'") == 1
    # La familia no es operación ni el comercio de la oferta: el UPDATE no alcanza ninguna fila
    assert cx.execute("UPDATE oferta SET precio = 1, stock = 999 WHERE id = %s", (OFERTA,)).rowcount == 0
    assert cx.execute("UPDATE producto SET retracto_pierde_al_abrir = NOT retracto_pierde_al_abrir"
                      " WHERE id = %s", (PRODUCTO,)).rowcount == 0
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("INSERT INTO oferta (producto_id, comercio_id, precio, stock) VALUES (%s, %s, 990, 1)",
                   (PRODUCTO, uuid.uuid4()))


@pytest.mark.rf("RF-20")
def test_el_comercio_cambia_el_stock_solo_de_sus_ofertas(cx):
    otro = "00000000-0000-0000-0000-0000000004c9"
    oferta_ajena = "00000000-0000-0000-0000-000000000f19"
    cx.execute(f"""
        INSERT INTO comercio (id, razon_social, nombre_fantasia, rut, direccion, comuna) VALUES
         ('{otro}', 'Comercio Nueve (ficticio)', 'Comercio Nueve', '76.000.000-9', 'Calle de Prueba 9', 'La Reina');
        INSERT INTO oferta (id, producto_id, comercio_id, precio, stock) VALUES ('{oferta_ajena}', '{PRODUCTO}',
         '{otro}', 11990, 3);
    """)
    como(cx, usuario_id=U_ENC, comercio_id=COMERCIO)
    assert cx.execute("UPDATE oferta SET stock = 7 WHERE id = %s", (OFERTA,)).rowcount == 1
    assert cx.execute("UPDATE oferta SET stock = 0 WHERE id = %s", (oferta_ajena,)).rowcount == 0


@pytest.mark.rf("RF-20")
@pytest.mark.parametrize("cambio", ["precio = 0", "precio = -1", "stock = -1"])
def test_precio_positivo_y_stock_no_negativo(cx, cambio):
    como(cx, rol="operacion")
    with pytest.raises(errors.CheckViolation):
        cx.execute(f"UPDATE oferta SET {cambio} WHERE id = %s", (OFERTA,))


@pytest.mark.rf("RF-20")
def test_operacion_mantiene_el_catalogo_y_el_retracto_parte_en_false(cx):
    como(cx, rol="operacion")
    assert cx.execute("UPDATE oferta SET stock = 0 WHERE id = %s", (OFERTA,)).rowcount == 1
    assert cx.execute("SELECT retracto_pierde_al_abrir FROM producto WHERE id = %s", (PRODUCTO,)).fetchone() == (False,)
    assert cx.execute("UPDATE producto SET retracto_pierde_al_abrir = true WHERE id = %s", (PRODUCTO,)).rowcount == 1


@pytest.mark.rf("RF-20")
def test_la_familia_no_ve_un_comercio_que_no_esta_activo(cx):
    cx.execute("UPDATE comercio SET estado = 'suspendido' WHERE id = %s", (COMERCIO,))
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    assert contar(cx, "comercio", f"id = '{COMERCIO}'") == 0
