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
from datetime import timedelta
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv
from psycopg import errors

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
# MATU-94: sin valor por omisión (antes, dbname=matu, la base de uso). Sin MATU_TEST_DSN, el archivo se salta como
# las demás pruebas de integración, y tests/conftest.py exige que apunte a una base de pruebas
DSN = os.environ.get("MATU_TEST_DSN", "")
pytestmark = pytest.mark.skipif(not DSN, reason="MATU_TEST_DSN no está definida")

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
# MATU-61 (D7): un segundo comercio, su encargado y un pedido de A con dos partes, solo en sus pruebas
COMERCIO_2 = uuid.UUID("00000000-0000-0000-0000-0000000004c3")
U_ENC_2 = uuid.UUID("00000000-0000-0000-0000-0000000000c3")
P_A2 = uuid.UUID("00000000-0000-0000-0000-0000000001a2")
PED_A_DOS = uuid.UUID("00000000-0000-0000-0000-0000000006a3")
PRODUCTO_2 = uuid.UUID("00000000-0000-0000-0000-000000000f03")
OFERTA_2 = uuid.UUID("00000000-0000-0000-0000-000000000f14")
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

INSERT INTO categoria_cuidado (id, nombre) VALUES
 ('00000000-0000-0000-0000-000000000c01', 'Higiene y cuidado personal');
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

-- Los pedidos nacen con sus líneas antes del pago. Las líneas de un pedido pagado ya no cambian
-- (ADR-027), así que el pago y el envío al comercio van después. Desde la 0023 (MATU-61, C4) hay un solo pedido
-- sin pagar por persona: el de A que se envía nace como cancelado, y sin destinatario_nombre_pila (C16). Cada
-- comercio tiene su parte (D7), visible para él recién con enviado_en.
INSERT INTO pedido (id, grupo_id, persona_cuidada_id, comercio_id, estado, subtotal_productos, costo_envio, total,
                    creado_por) VALUES
 ('{PED_A_ENVIADO}',  '{G_A}', '{P_A}', '{COMERCIO}', 'cancelado', 25980, 2990, 28970, '{U_ADMIN_A}'),
 ('{PED_A_BORRADOR}', '{G_A}', '{P_A}', '{COMERCIO}', 'borrador', 12990, 2990, 15980, '{U_ADMIN_A}'),
 ('{PED_B_ENVIADO}',  '{G_B}', '{P_B}', '{COMERCIO}', 'borrador', 12990, 2990, 15980, '{U_ADMIN_B}');
INSERT INTO pedido_entrega (pedido_id, calle, numero, comuna, telefono_contacto) VALUES
 ('{PED_A_ENVIADO}', 'Los Aromos', '123', 'La Reina', '+56911111111');
INSERT INTO pedido_comercio (id, grupo_id, pedido_id, comercio_id, referencia, enviado_en) VALUES
 ('00000000-0000-0000-0000-0000000009a1', '{G_A}', '{PED_A_ENVIADO}', '{COMERCIO}', 'AAAA22', now()),
 ('00000000-0000-0000-0000-0000000009b1', '{G_B}', '{PED_B_ENVIADO}', '{COMERCIO}', 'BBBB22', now());
INSERT INTO pedido_linea (pedido_id, oferta_id, producto_id, cantidad, precio_unitario, pedido_comercio_id) VALUES
 ('{PED_A_ENVIADO}',  '00000000-0000-0000-0000-000000000f11', '00000000-0000-0000-0000-000000000f01', 2, 12990,
  '00000000-0000-0000-0000-0000000009a1'),
 ('{PED_A_BORRADOR}', '00000000-0000-0000-0000-000000000f11', '00000000-0000-0000-0000-000000000f01', 1, 12990, NULL);
INSERT INTO pedido_transicion (pedido_id, desde, hacia, actor_tipo, actor_ref) VALUES
 ('{PED_A_BORRADOR}', NULL, 'borrador', 'usuario', '{U_ADMIN_A}');
-- MATU-62 (0024): marcar un pedido pagado lo hace solo el sistema, con su venta aprobada (trigger
-- pedido_escritura_del_pago). La semilla escribe el pago con el rol de réplica, sin triggers; los CHECK se cumplen
SET session_replication_role = replica;
UPDATE pedido SET estado = 'enviado_a_comercio', total_confirmado_en = now() - interval '5 minutes',
                  total_vence_en = now() + interval '10 minutes', pagado_en = now(),
                  condiciones_version = '0.1', condiciones_aceptadas_en = now(), condiciones_huella = repeat('a', 64),
                  condiciones_aceptadas_por = creado_por
 WHERE id IN ('{PED_A_ENVIADO}', '{PED_B_ENVIADO}');
INSERT INTO cargo (id, pedido_id, estado, monto_cobrado) VALUES
 ('00000000-0000-0000-0000-0000000007a1', '{PED_A_ENVIADO}', 'pagado', 28970);
INSERT INTO participacion (id, cargo_id, usuario_id, porcentaje_bp, estado, monto_cobrado) VALUES
 ('00000000-0000-0000-0000-0000000008a1', '00000000-0000-0000-0000-0000000007a1', '{U_ADMIN_A}', 10000,
  'pagada', 28970);
INSERT INTO transaccion_pasarela (participacion_id, cargo_id, proveedor, tipo, buy_order, monto, estado,
                                  idempotency_key, total_confirmado_en) VALUES
 ('00000000-0000-0000-0000-0000000008a1', '00000000-0000-0000-0000-0000000007a1', 'webpay_plus', 'venta',
  'MATU-0001', 28970, 'aprobada', 'k1', now() - interval '5 minutes');
SET session_replication_role = origin;
INSERT INTO repartidor (id, usuario_id, vehiculo, comuna_base) VALUES ('{REPARTIDOR}', '{U_REP}', 'auto', 'La Reina');
INSERT INTO asignacion (grupo_id, pedido_id, repartidor_id) VALUES ('{G_A}', '{PED_A_ENVIADO}', '{REPARTIDOR}');
INSERT INTO idempotencia (grupo_id, endpoint, clave, usuario_id, hash_peticion, estado_http, pedido_id) VALUES
 ('{G_A}', 'POST /v1/pedidos', 'k-a', '{U_ADMIN_A}', '\\x00', 201, '{PED_A_BORRADOR}'),
 ('{G_B}', 'POST /v1/pedidos', 'k-b', '{U_ADMIN_B}', '\\x00', 201, '{PED_B_ENVIADO}');
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
    insertar = ("INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, detalle, persona_cuidada_id)"
                " VALUES (%s, 'usuario', %s, 'plan.editar', 'plan_seccion', CAST(%s AS jsonb), %s)")
    if acepta:
        cx.execute(insertar, (G_A, U_ADMIN_A, detalle, P_A))
    else:
        with pytest.raises(errors.CheckViolation):
            cx.execute(insertar, (G_A, U_ADMIN_A, detalle, P_A))


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
    cx.execute("""INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, entidad_id,
                  persona_cuidada_id) VALUES (%s, 'relevo', %s, 'relevo.abrir', 'plan_cuidado', %s, %s)""",
               (G_A, ACC_VIGENTE, PLAN_A, P_A))
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("""INSERT INTO auditoria (grupo_id, actor_tipo, accion, entidad, persona_cuidada_id)
                      VALUES (%s, 'relevo', 'relevo.abrir', 'plan_cuidado', %s)""", (G_B, P_B))


# ---- MATU-19 (migración 0007): lo que el relevo puede cambiar de su acceso y la autorización vigente


@pytest.mark.rf("RF-06")
def test_relevo_cuenta_intentos_pero_no_borra_ni_cambia_su_acceso(cx):
    como(cx, rol="relevo", acceso_relevo_id=ACC_VIGENTE)
    # Sube el contador, los usos y el último uso: lo único que el canje y la ficha escriben
    cx.execute("UPDATE acceso_relevo SET pin_intentos_fallidos = pin_intentos_fallidos + 1")
    cx.execute("UPDATE acceso_relevo SET usos = usos + 1, ultimo_uso_en = now()")
    assert cx.execute("SELECT pin_intentos_fallidos, usos FROM acceso_relevo").fetchone() == (1, 1)
    # No borra su acceso: matu_app no tiene DELETE sobre acceso_relevo (migración 0020)
    with pytest.raises(errors.InsufficientPrivilege), cx.transaction():
        cx.execute("DELETE FROM acceso_relevo")
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
    """MATU-63 (D-63-1): el comercio no lee ninguna fila del pedido; ve sus partes solo por comercio_partes."""
    como(cx, usuario_id=U_ENC, comercio_id=COMERCIO)
    assert contar(cx, "pedido") == 0 and contar(cx, "pedido_linea") == 0 and contar(cx, "pedido_comercio") == 0
    assert {r[0] for r in cx.execute("SELECT referencia FROM comercio_partes('-infinity')").fetchall()} == {
        "AAAA22", "BBBB22"}
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
    # Desde la 0022 (MATU-74) el publicador llega al outbox solo por las funciones outbox_*
    como(cx, "matu_publisher", rol="operacion")
    assert cx.execute("SELECT count(*) FROM outbox_tomar(1, now() - interval '1 day')").fetchone()[0] >= 0
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


def test_clave_vigente_se_sigue_reenvolviendo_como_dueno(cx):
    """El trigger solo fija la fila destruida: la vigente se puede volver a envolver (rotación futura). Desde la
    0020 (MATU-66) matu_app no la reenvuelve (test_admin_crea_y_destruye_la_clave_pero_no_la_reenvuelve): la
    rotación irá por una función SECURITY DEFINER. Aquí escribe el superusuario: el trigger no se lo impide."""
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    cx.execute("RESET ROLE")
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
    """Reemplaza a la prueba del tope de captura: ya no hay autorizado ni capturado, solo cobrado y devuelto. Desde la
    0024 (MATU-62) el cargo lo actualizan el sistema y operación, no la familia."""
    como(cx, rol="operacion")
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
    # MATU-62: las tablas del pago las actualiza operación (la familia no alcanza la fila y el UPDATE no fallaría)
    if tabla in ("cargo", "participacion", "transaccion_pasarela"):
        como(cx, rol="operacion")
    else:
        como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.CheckViolation):
        cx.execute(f"UPDATE {tabla} SET {columna} = %s", (valor,))


@pytest.mark.rf("ADR-027")
def test_estado_del_cargo_coincide_con_sus_montos(cx):
    como(cx, rol="operacion")  # MATU-62: el cargo lo actualizan el sistema y operación
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
    # MATU-61 (D6): no hay pago sin las condiciones aceptadas
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("UPDATE pedido SET estado = 'pagado', pagado_en = now() + interval '2 minutes' WHERE id = %s",
                   (PED_A_BORRADOR,))
    # MATU-62 (D-62-4): la familia acepta las condiciones, pero el pago lo marca solo el sistema, con su venta aprobada
    cx.execute("""UPDATE pedido SET condiciones_version = '0.2',
                  condiciones_aceptadas_en = now() + interval '2 minutes',
                  condiciones_huella = repeat('b', 64), condiciones_aceptadas_por = %s WHERE id = %s""",
               (U_ADMIN_A, PED_A_BORRADOR))
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("UPDATE pedido SET estado = 'pagado', pagado_en = now() + interval '2 minutes' WHERE id = %s",
                   (PED_A_BORRADOR,))


@pytest.mark.rf("ADR-027")
def test_el_precio_pagado_queda_fijo(cx):
    # MATU-63 (0029): la familia ya no alcanza las líneas de un pedido pagado (linea_editar); el trigger
    # pedido_linea_pagada_fija detiene también al sistema y a operación, que sí las alcanzan
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    assert cx.execute("UPDATE pedido_linea SET estado_linea = 'preparada' WHERE pedido_id = %s RETURNING id",
                      (PED_A_ENVIADO,)).fetchall() == []
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute(f"""INSERT INTO pedido_linea (pedido_id, oferta_id, producto_id, cantidad, precio_unitario)
                       VALUES ('{PED_A_ENVIADO}', '{OFERTA}', '{PRODUCTO}', 1, 12990)""")
    # Antes de pagar el precio todavía puede cambiar
    cx.execute("UPDATE pedido_linea SET precio_unitario = 11990 WHERE pedido_id = %s", (PED_A_BORRADOR,))
    cx.execute("RESET ROLE")
    como(cx, rol="operacion")
    for sql in (
        f"UPDATE pedido_linea SET precio_unitario = 9990 WHERE pedido_id = '{PED_A_ENVIADO}'",
        f"UPDATE pedido_linea SET cantidad = 3 WHERE pedido_id = '{PED_A_ENVIADO}'",
    ):
        with pytest.raises(errors.CheckViolation), cx.transaction():
            cx.execute(sql)
    # El estado de la línea sí avanza
    cx.execute("UPDATE pedido_linea SET estado_linea = 'preparada' WHERE pedido_id = %s", (PED_A_ENVIADO,))


@pytest.mark.rf("ADR-027")
def test_la_devolucion_de_una_linea_no_supera_lo_pagado(cx):
    como(cx, rol="operacion")  # MATU-63: la devolución la marcan el sistema y operación
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("""UPDATE pedido_linea SET estado_linea = 'devuelta', devuelta_en = now(),
                      monto_devuelto = 2 * 12990 + 1 WHERE pedido_id = %s""", (PED_A_ENVIADO,))
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("UPDATE pedido_linea SET estado_linea = 'devuelta' WHERE pedido_id = %s", (PED_A_ENVIADO,))
    # D-63-8: lo devuelto lleva su fecha, y una devolución parcial no deja la línea devuelta
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("UPDATE pedido_linea SET monto_devuelto = 12990 WHERE pedido_id = %s", (PED_A_ENVIADO,))
    cx.execute("""UPDATE pedido_linea SET estado_linea = 'faltante', unidades_faltantes = 1, devuelta_en = now(),
                  monto_devuelto = 12990 WHERE pedido_id = %s""", (PED_A_ENVIADO,))
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
    como(cx, rol="operacion")  # MATU-63: después del pago, la línea la escriben el sistema y operación
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
    # Desde la 0023: sin destinatario_nombre_pila (C16), con las condiciones si está pagado (D6), y de otra persona
    # de A, porque P_A ya tiene su pedido sin pagar (C4)
    _persona_a2(cx)
    pedido = cx.execute("""INSERT INTO pedido (grupo_id, persona_cuidada_id, comercio_id, estado, subtotal_productos,
                                      total, total_confirmado_en, total_vence_en, pagado_en, condiciones_version,
                                      condiciones_aceptadas_en, condiciones_huella, condiciones_aceptadas_por,
                                      creado_por)
                  VALUES (%s, %s, %s, %s, 12990, 12990, now(), now() + interval '15 minutes',
                          CASE WHEN %s THEN now() END, CASE WHEN %s THEN '0.1' END, CASE WHEN %s THEN now() END,
                          CASE WHEN %s THEN repeat('c', 64) END, CASE WHEN %s THEN %s::uuid END, %s) RETURNING id""",
               (G_A, P_A2, COMERCIO, estado, pagado, pagado, pagado, pagado, pagado, U_ADMIN_A,
                U_ADMIN_A)).fetchone()[0]
    # Aunque tenga su parte enviada: sin pagar o sin enviar, el comercio no lo ve
    cx.execute("INSERT INTO pedido_comercio (grupo_id, pedido_id, comercio_id, referencia, enviado_en)"
               " VALUES (%s, %s, %s, 'PRUEBA', now())", (G_A, pedido, COMERCIO))
    como(cx, usuario_id=U_ENC, comercio_id=COMERCIO)
    # MATU-63: ninguna fila del pedido, y por la función solo las partes pagadas: desde la 0029, la parte llega al
    # comercio con el pago (enviado_en), así que la del pedido pagado sí aparece
    assert contar(cx, "pedido") == 0
    assert {r[0] for r in cx.execute("SELECT referencia FROM comercio_partes('-infinity')").fetchall()} == {
        "AAAA22", "BBBB22", *(["PRUEBA"] if pagado else [])}


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
    if quien == "familia":
        with pytest.raises(errors.CheckViolation), cx.transaction():
            cx.execute(f"UPDATE pedido SET {cambio} WHERE id = %s", (PED_A_ENVIADO,))
        # MATU-63 (0029): tampoco lo mueve en su ciclo
        with pytest.raises(errors.CheckViolation), cx.transaction():
            cx.execute("UPDATE pedido SET estado = 'preparando' WHERE id = %s", (PED_A_ENVIADO,))
    else:
        # MATU-63 (D-63-2): el comercio no alcanza la fila
        assert cx.execute(f"UPDATE pedido SET {cambio} WHERE id = %s RETURNING id", (PED_A_ENVIADO,)).fetchall() == []
    # El pedido pagado sí avanza en su ciclo, por el sistema, y lo cobrado sigue igual
    cx.execute("RESET ROLE")
    como(cx, grupo_id=G_A, rol="sistema")
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
    # Desde la 0023 (C12) la regla de un pedido pagado queda fija: B arma un pedido sin pagar
    cx.execute("UPDATE pedido SET estado = 'cancelado' WHERE id = %s", (PED_A_BORRADOR,))
    sin_pagar = cx.execute("INSERT INTO pedido (grupo_id, persona_cuidada_id, creado_por) VALUES (%s, %s, %s)"
                           " RETURNING id", (G_B, P_B, U_ADMIN_B)).fetchone()[0]
    como(cx, usuario_id=U_ADMIN_B, grupo_id=G_B)
    cx.execute(REGLA, (sin_pagar, PRODUCTO, "quitar"))
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    assert contar(cx, "regla_sustitucion") == 0
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute(REGLA, (sin_pagar, PRODUCTO, "otro_comercio"))


# ------------------------------------------------------------------ lectura de la auditoría (decisión 36)

U_CUID_A = uuid.UUID("00000000-0000-0000-0000-0000000000a9")


def _sembrar_auditoria(cx):
    """Como superusuario, dentro de la transacción que se revierte: un cuidador y una fila por actor."""
    cx.execute("INSERT INTO usuario (id, email, nombre, password_hash) VALUES (%s, 'cuid.a@x.cl', 'Cuid A', 'h')",
               (U_CUID_A,))
    cx.execute("INSERT INTO membresia (grupo_id, usuario_id, rol, puede_ver_plan) VALUES (%s, %s, 'cuidador', false)",
               (G_A, U_CUID_A))
    for grupo, actor in ((G_A, U_ADMIN_A), (G_A, U_CUID_A), (G_A, U_OBS_A), (G_B, U_ADMIN_B)):
        cx.execute("INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, persona_cuidada_id)"
                   " VALUES (%s, 'usuario', %s, 'plan.leer', 'plan_cuidado', %s)",
                   (grupo, actor, P_A if grupo == G_A else P_B))


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
    como(cx, "matu_scheduler", rol="operacion")
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
    como(cx, "matu_scheduler", rol="operacion")
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
    como(cx, "matu_scheduler", rol="operacion")
    with pytest.raises(errors.InvalidParameterValue):
        cx.execute("SELECT consumo_conservar(now() - interval '89 days', now())")
    cx.rollback()
    como(cx, "matu_scheduler", rol="operacion")
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
        como(cx, "matu_scheduler", rol="operacion")
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
        cx.execute("INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, entidad_id,"
                   " persona_cuidada_id) VALUES (%s, 'relevo', %s, %s, 'acceso_relevo', %s, %s)",
                   (G_A, ACC_VIGENTE, accion, ACC_VIGENTE, P_A))
    cx.execute("INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, persona_cuidada_id)"
               " VALUES (%s, 'relevo', %s, 'relevo.abrir', 'plan_cuidado', %s)", (G_B, uuid.uuid4(), P_B))


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
    cx.execute("INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, persona_cuidada_id)"
               " VALUES (%s, 'usuario', %s, 'plan.leer', 'plan_cuidado', %s)", (G_A, U_ADMIN_A, P_A))
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
        como(cx, "matu_scheduler", rol="operacion")
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
    como(cx, "matu_scheduler", rol="operacion")
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
    # Ni con operación lee la tabla directamente: tampoco el publicador desde la 0022 (un solo camino, las funciones)
    for db_rol in ("matu_app", "matu_publisher"):
        como(cx, db_rol, rol="operacion")
        with pytest.raises(errors.InsufficientPrivilege):
            cx.execute("SELECT id FROM evento_outbox")
        cx.rollback()


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
    como(cx, "matu_publisher", rol="operacion")
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
    como(cx, "matu_publisher", rol="operacion")
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
    como(cx, "matu_scheduler", rol="operacion")
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
    como(cx, "matu_scheduler", rol="operacion")
    with pytest.raises(errors.InvalidParameterValue):
        cx.execute("SELECT plan_destruir_claves(now() - interval '89 days', now())")
    cx.rollback()
    como(cx, "matu_scheduler", rol="operacion")
    with pytest.raises(errors.InvalidParameterValue):
        cx.execute("SELECT plan_destruir_claves(now(), now() + interval '91 days')")
    cx.rollback()
    como(cx, "matu_scheduler", rol="operacion")
    # Sin retiros en la semilla: no destruye nada y devuelve solo un contador
    assert cx.execute("SELECT plan_destruir_claves(now() - interval '90 days', now())").fetchone() == (0,)


@pytest.mark.rf("RF-02")
@pytest.mark.parametrize(("hace", "destruye"), [("91 days", True), ("89 days", False)])
def test_destruir_claves_solo_tras_90_dias_y_solo_esa_persona(cx, hace, destruye):
    _retiro_de_plan(cx, hace)
    como(cx, "matu_scheduler", rol="operacion")
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
    como(cx, "matu_scheduler", rol="operacion")
    assert cx.execute("SELECT plan_destruir_claves(now() - interval '90 days', now())").fetchone() == (1,)
    assert cx.execute("SELECT plan_destruir_claves(now() - interval '90 days', now())").fetchone() == (0,)
    cx.execute("RESET ROLE")
    assert cx.execute("SELECT count(*) FROM auditoria WHERE accion = 'clave.destruir'").fetchone() == (1,)


@pytest.mark.rf("RF-02")
def test_destruir_claves_no_toca_a_quien_volvio_a_autorizar(cx):
    _retiro_de_plan(cx, "100 days")
    _consentimiento(cx)  # una autorización nueva de plan_cuidado, no revocada
    como(cx, "matu_scheduler", rol="operacion")
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
    como(cx, "matu_scheduler", rol="operacion")
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


# ------------------------------------------------------------------ MATU-47 (migración 0020): indice_token

TOKEN_RELEVO = b"\x47" * 32


def _token_de_relevo(cx, revocado="now()"):
    """Una fila de indice_token del acceso revocado de A, como superusuario dentro de la transacción."""
    cx.execute("INSERT INTO indice_token (token_hash, tipo, grupo_id, referencia_id, expira_en, revocado_en)"
               f" VALUES (%s, 'relevo', %s, %s, now() + interval '1 day', {revocado})",
               (TOKEN_RELEVO, G_A, ACC_REVOCADO))


@pytest.mark.rf("RF-05")
def test_la_api_no_reabre_una_revocacion_de_indice_token(cx):
    _token_de_relevo(cx)
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.CheckViolation):
        cx.execute("UPDATE indice_token SET revocado_en = NULL WHERE token_hash = %s", (TOKEN_RELEVO,))


@pytest.mark.rf("RF-05")
@pytest.mark.parametrize("db_rol", ["matu_app", None])   # None: superusuario, el trigger también lo alcanza
def test_nadie_alarga_el_vencimiento_de_indice_token(cx, db_rol):
    _token_de_relevo(cx, revocado="NULL")
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    # matu_app ni siquiera escribe expira_en; al superusuario lo detiene el trigger
    error = errors.CheckViolation if db_rol is None else errors.InsufficientPrivilege
    if db_rol is None:
        cx.execute("RESET ROLE")
    with pytest.raises(error):
        cx.execute("UPDATE indice_token SET expira_en = expira_en + interval '1 day' WHERE token_hash = %s",
                   (TOKEN_RELEVO,))


@pytest.mark.rf("RF-05")
def test_la_api_no_borra_un_token(cx):
    _token_de_relevo(cx)
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("DELETE FROM indice_token WHERE token_hash = %s", (TOKEN_RELEVO,))


@pytest.mark.rf("RF-05")
def test_la_api_sigue_cortando_un_token_y_queda_cortado(cx):
    """MATU-20: el corte fija revocado_en una vez. Después, ni el superusuario lo mueve."""
    _token_de_relevo(cx, revocado="NULL")
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    assert cx.execute("UPDATE indice_token SET revocado_en = now() WHERE token_hash = %s AND revocado_en IS NULL",
                      (TOKEN_RELEVO,)).rowcount == 1
    cx.execute("RESET ROLE")
    # Acortar el vencimiento no lo pide nadie hoy, pero el trigger no lo impide
    cx.execute("UPDATE indice_token SET expira_en = expira_en - interval '1 hour' WHERE token_hash = %s",
               (TOKEN_RELEVO,))
    with pytest.raises(errors.CheckViolation):
        cx.execute("UPDATE indice_token SET revocado_en = revocado_en - interval '1 hour' WHERE token_hash = %s",
                   (TOKEN_RELEVO,))


# ------------------------------------------------------------------ MATU-66 (migración 0020): acceso_relevo


@pytest.mark.rf("RF-05")
def test_un_acceso_cortado_no_se_reabre_y_ninguno_se_alarga(cx):
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("UPDATE acceso_relevo SET revocado_en = NULL WHERE id = %s", (ACC_REVOCADO,))
    for cambio in ("expira_en = expira_en + interval '1 day'", "pin_hash = 'otro'",
                   "secciones_permitidas = ARRAY['rutina']"):
        with pytest.raises(errors.InsufficientPrivilege), cx.transaction():
            cx.execute(f"UPDATE acceso_relevo SET {cambio} WHERE id = %s", (ACC_VIGENTE,))
    # MATU-46 (0027, D-46-3 a): matu_app puede vaciar el teléfono, pero el trigger no deja cambiarlo por otro
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("UPDATE acceso_relevo SET otorgado_a_telefono = '+56900000047' WHERE id = %s", (ACC_VIGENTE,))


def _insertar_acceso_sql():
    from sqlalchemy import text

    return text(
        "INSERT INTO acceso_relevo (grupo_id, plan_id, otorgado_por, otorgado_a_nombre, otorgado_a_telefono,"
        " nombre_pila_persona, nombre_pila_comparte, secciones_permitidas, motivo, token_hash, pin_hash,"
        " expira_en, relevo_informado_en)"
        " VALUES (:grupo, :plan, :usuario, 'Relevo', '+56955550147', 'María', 'Pag', ARRAY['rutina'], 'otro',"
        " sha256('t66'), 'p', now() + interval '1 day', now())"
    )


@pytest.mark.rf("RF-05")
def test_el_pagador_con_permiso_lee_los_accesos_pero_no_los_crea_ni_los_corta(sesiones_app):
    """Con sesion_tenant, como matu_app: el pagador con puede_ver_plan ve los tres accesos de A, su UPDATE no
    alcanza ninguna fila y su INSERT lo rechaza RLS. Con acceso_familia (FOR ALL, antes de la 0020) los cortaba."""
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from app.core.db import sesion_tenant

    filtro = {"id": ACC_VIGENTE}
    with pytest.raises(_Deshacer), sesion_tenant(sesiones_app, usuario_id=U_PAG2_A, grupo_id=G_A) as s:
        assert s.execute(text("SELECT count(*) FROM acceso_relevo")).scalar_one() == 3
        cortado = s.execute(text("UPDATE acceso_relevo SET revocado_en = now() WHERE id = :id"), filtro)
        anonimizado = s.execute(text("UPDATE acceso_relevo SET nombre_pila_persona = 'x' WHERE id = :id"), filtro)
        assert (cortado.rowcount, anonimizado.rowcount) == (0, 0)  # type: ignore[attr-defined]
        raise _Deshacer
    with pytest.raises(DBAPIError) as error, sesion_tenant(sesiones_app, usuario_id=U_PAG2_A, grupo_id=G_A) as s:
        s.execute(_insertar_acceso_sql(), {"grupo": G_A, "plan": PLAN_A, "usuario": U_PAG2_A})
    assert isinstance(error.value.orig, errors.InsufficientPrivilege)


@pytest.mark.rf("RF-05")
@pytest.mark.parametrize("usuario", [U_OBS_A, U_PAG_A])
def test_observador_y_pagador_sin_permiso_no_ven_ni_cortan_accesos(sesiones_app, usuario):
    from sqlalchemy import text

    from app.core.db import sesion_tenant

    with pytest.raises(_Deshacer), sesion_tenant(sesiones_app, usuario_id=usuario, grupo_id=G_A) as s:
        assert s.execute(text("SELECT count(*) FROM acceso_relevo")).scalar_one() == 0
        cortado = s.execute(text("UPDATE acceso_relevo SET revocado_en = now() WHERE id = :id"), {"id": ACC_VIGENTE})
        assert cortado.rowcount == 0  # type: ignore[attr-defined]
        raise _Deshacer


@pytest.mark.rf("RF-05")
def test_admin_y_cuidador_crean_cortan_y_anonimizan_los_accesos(sesiones_app):
    """Condición 2: el corte (MATU-20), el retiro (MATU-44) y el borrado (MATU-72) siguen escribiendo."""
    from sqlalchemy import text

    from app.core.db import sesion_tenant

    with pytest.raises(_Deshacer), sesion_tenant(sesiones_app, usuario_id=U_ADMIN_A, grupo_id=G_A) as s:
        s.execute(_insertar_acceso_sql(), {"grupo": G_A, "plan": PLAN_A, "usuario": U_ADMIN_A})
        cortado = s.execute(
            text("UPDATE acceso_relevo SET revocado_en = now() WHERE id = :id AND revocado_en IS NULL"),
            {"id": ACC_VIGENTE})
        anonimizados = s.execute(
            text("UPDATE acceso_relevo SET nombre_pila_persona = 'borrada' WHERE plan_id = :p"), {"p": PLAN_A})
        assert (cortado.rowcount, anonimizados.rowcount) == (1, 4)  # type: ignore[attr-defined]
        raise _Deshacer


@pytest.mark.rf("RF-05")
@pytest.mark.parametrize("usuario", [U_ADMIN_A, U_PAG2_A])
def test_nadie_borra_un_acceso_de_relevo(sesiones_app, usuario):
    """matu_app no tiene DELETE sobre acceso_relevo (migración 0020): ni el admin borra un acceso, se corta."""
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from app.core.db import sesion_tenant

    with pytest.raises(DBAPIError) as error, sesion_tenant(sesiones_app, usuario_id=usuario, grupo_id=G_A) as s:
        s.execute(text("DELETE FROM acceso_relevo WHERE id = :id"), {"id": ACC_VIGENTE})
    assert isinstance(error.value.orig, errors.InsufficientPrivilege)


# ------------------------------------------------------------------ MATU-66 (migración 0020): clave_datos

P_SIN_CLAVE = uuid.UUID("00000000-0000-0000-0000-0000000066a0")


@pytest.mark.rf("RF-03")
def test_el_pagador_con_permiso_lee_la_clave_pero_no_la_crea_ni_la_destruye(cx):
    cx.execute("INSERT INTO persona_cuidada (id, grupo_id, nombre, nombre_pila, nivel_apoyo)"
               " VALUES (%s, %s, 'Persona 66', 'Persona', 'apoyo_parcial')", (P_SIN_CLAVE, G_A))
    como(cx, usuario_id=U_PAG2_A, grupo_id=G_A)
    assert contar(cx, "clave_datos") == 1
    assert cx.execute("UPDATE clave_datos SET dek_cifrada_con_kek = NULL, destruida_en = now()").rowcount == 0
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("INSERT INTO clave_datos (grupo_id, persona_cuidada_id, dek_cifrada_con_kek, kek_version)"
                   " VALUES (%s, %s, '\\x66', 1)", (G_A, P_SIN_CLAVE))


@pytest.mark.rf("RF-03")
def test_admin_crea_y_destruye_la_clave_pero_no_la_reenvuelve(cx):
    """Las escrituras del cifrado son crear y destruir (MATU-66). La rotación, cuando exista, irá por una
    función SECURITY DEFINER."""
    cx.execute("INSERT INTO persona_cuidada (id, grupo_id, nombre, nombre_pila, nivel_apoyo)"
               " VALUES (%s, %s, 'Persona 66', 'Persona', 'apoyo_parcial')", (P_SIN_CLAVE, G_A))
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    cx.execute("INSERT INTO clave_datos (grupo_id, persona_cuidada_id, dek_cifrada_con_kek, kek_version)"
               " VALUES (%s, %s, '\\x66', 1)", (G_A, P_SIN_CLAVE))
    with pytest.raises(errors.InsufficientPrivilege), cx.transaction():
        cx.execute("UPDATE clave_datos SET dek_cifrada_con_kek = '\\x05', kek_version = 2, rotada_en = now()"
                   " WHERE persona_cuidada_id = %s", (P_A,))
    assert cx.execute("UPDATE clave_datos SET dek_cifrada_con_kek = NULL, destruida_en = now()"
                      " WHERE persona_cuidada_id = %s", (P_A,)).rowcount == 1


# ------------------------------------------------------------------ MATU-66 (migración 0020): consentimiento

_INSERTAR_CONSENTIMIENTO = (
    "INSERT INTO consentimiento (grupo_id, persona_cuidada_id, usuario_id, calidad_otorgante, finalidad,"
    " version_politica, evidencia) VALUES (%s, %s, %s, 'titular', 'plan_cuidado', 'v1', '{\"esquema\": 1}'::jsonb)"
)


@pytest.mark.rf("RF-01")
@pytest.mark.parametrize("usuario", [U_OBS_A, U_PAG_A, U_PAG2_A])
def test_pagador_y_observador_no_dan_una_autorizacion(cx, usuario):
    como(cx, usuario_id=usuario, grupo_id=G_A)
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute(_INSERTAR_CONSENTIMIENTO, (G_A, P_A, usuario))


@pytest.mark.rf("RF-01")
def test_el_admin_da_la_autorizacion_y_todo_el_grupo_la_lee(cx):
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    cx.execute(_INSERTAR_CONSENTIMIENTO, (G_A, P_A, U_ADMIN_A))
    for usuario in (U_ADMIN_A, U_OBS_A, U_PAG_A, U_PAG2_A):
        como(cx, usuario_id=usuario, grupo_id=G_A)
        assert contar(cx, "consentimiento") == 1, usuario


# ------------------------------------------------------------------ MATU-66 (migración 0020): usuario


@pytest.mark.rf("RF-37")
def test_operacion_lee_email_y_celular_pero_no_cambia_ni_crea_cuentas(sesiones_app):
    """Condición 5: soporte lee el email y el celular. No inserta, no edita ni borra una cuenta."""
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from app.core.db import sesion_tenant

    with pytest.raises(_Deshacer), sesion_tenant(sesiones_app, rol="operacion") as s:
        filas = s.execute(text("SELECT email, telefono FROM usuario WHERE id = :id"), {"id": U_OBS_A}).all()
        assert [f[0] for f in filas] == ["obs.a@x.cl"]
        # Ni siquiera una columna que la app sí cambia: operación no alcanza la fila ajena
        editadas = s.execute(text("UPDATE usuario SET telefono = '+56900000066' WHERE id = :id"), {"id": U_OBS_A})
        assert editadas.rowcount == 0  # type: ignore[attr-defined]
        raise _Deshacer
    for sentencia in ("UPDATE usuario SET estado = 'bloqueado' WHERE id = :id", "DELETE FROM usuario WHERE id = :id"):
        with pytest.raises(DBAPIError) as error, sesion_tenant(sesiones_app, rol="operacion") as s:
            s.execute(text(sentencia), {"id": U_OBS_A})
        assert isinstance(error.value.orig, errors.InsufficientPrivilege), sentencia
    with pytest.raises(DBAPIError) as error, sesion_tenant(sesiones_app, rol="operacion") as s:
        s.execute(text("INSERT INTO usuario (id, email, nombre, password_hash) VALUES (:id, 'op66@x.cl', 'Op', 'h')"),
                  {"id": uuid.uuid4()})
    assert isinstance(error.value.orig, errors.InsufficientPrivilege)


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize("contexto", [
    {"rol": "operacion"},                                  # soporte
    {"usuario_id": U_ADMIN_A, "grupo_id": G_A},            # un comiembro
    {"usuario_id": U_OBS_A},                               # la propia cuenta, tampoco con SQL directo
], ids=["operacion", "comiembro", "propia"])
def test_nadie_lee_password_hash_con_sql_directo(sesiones_app, contexto):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from app.core.db import sesion_tenant

    for consulta in ("SELECT password_hash FROM usuario WHERE id = :id",
                     "SELECT * FROM usuario WHERE id = :id",
                     "SELECT id FROM usuario WHERE id = :id AND password_hash IS NOT NULL",
                     "UPDATE usuario SET nombre = nombre WHERE id = :id RETURNING password_hash"):
        with pytest.raises(DBAPIError) as error, sesion_tenant(sesiones_app, **contexto) as s:
            s.execute(text(consulta), {"id": U_OBS_A})
        assert isinstance(error.value.orig, errors.InsufficientPrivilege), consulta


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize("contexto, devuelve", [
    ({"usuario_id": U_OBS_A}, True),                       # el login de la propia cuenta
    ({"usuario_id": U_ADMIN_A, "grupo_id": G_A}, False),   # otra cuenta, aunque sea comiembro
    ({"usuario_id": U_OBS_A, "rol": "operacion"}, False),  # operación, ni con el id fijado
    ({"rol": "operacion"}, False),
    ({}, False),
], ids=["propia", "comiembro", "operacion-con-id", "operacion", "sin-contexto"])
def test_iam_credencial_solo_devuelve_la_cuenta_del_contexto(sesiones_app, contexto, devuelve):
    from sqlalchemy import text

    from app.core.db import sesion_tenant

    with sesion_tenant(sesiones_app, **contexto) as s:
        filas = [tuple(f) for f in s.execute(text("SELECT password_hash, estado FROM iam_credencial(:id)"),
                                             {"id": U_OBS_A})]
    assert filas == ([("h", "activo")] if devuelve else [])


# ------------------------------------------------------------------ MATU-75: aceptación de la política

HUELLA_A, HUELLA_B = "a" * 64, "b" * 64


def _sembrar_aceptaciones(cx):
    """Una aceptación de U_OBS_A y otra de U_ADMIN_B, como superusuario, dentro de la transacción de la prueba."""
    cx.execute("INSERT INTO aceptacion_politica (usuario_id, version, huella)"
               " VALUES (%s, '0.11', %s), (%s, '0.11', %s)", (U_OBS_A, HUELLA_A, U_ADMIN_B, HUELLA_B))


def _falla_por_permiso(cx, sql, *parametros):
    with pytest.raises(errors.InsufficientPrivilege), cx.transaction():
        cx.execute(sql, parametros)


@pytest.mark.rf("RF-37")
def test_la_titular_lee_y_agrega_solo_sus_aceptaciones(cx):
    _sembrar_aceptaciones(cx)
    como(cx, usuario_id=U_OBS_A)
    assert cx.execute("SELECT usuario_id, huella FROM aceptacion_politica").fetchall() == [(U_OBS_A, HUELLA_A)]
    cx.execute("INSERT INTO aceptacion_politica (usuario_id, version, huella) VALUES (%s, '0.11', %s)",
               (U_OBS_A, HUELLA_B))
    assert contar(cx, "aceptacion_politica") == 2
    # No agrega una a nombre de otra cuenta (WITH CHECK de aceptacion_propia_crear)
    _falla_por_permiso(cx, "INSERT INTO aceptacion_politica (usuario_id, version, huella) VALUES (%s, '0.11', %s)",
                       U_ADMIN_B, HUELLA_A)
    # Ni cambia ni borra las suyas: matu_app no tiene UPDATE ni DELETE
    _falla_por_permiso(cx, "UPDATE aceptacion_politica SET version = '0.10' WHERE usuario_id = %s", U_OBS_A)
    _falla_por_permiso(cx, "DELETE FROM aceptacion_politica WHERE usuario_id = %s", U_OBS_A)


@pytest.mark.rf("RF-37")
def test_un_comiembro_no_ve_la_aceptacion_de_otra_cuenta(cx):
    _sembrar_aceptaciones(cx)
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    assert contar(cx, "aceptacion_politica") == 0


@pytest.mark.rf("RF-37")
def test_operacion_lee_las_aceptaciones_y_no_las_cambia(cx):
    _sembrar_aceptaciones(cx)
    como(cx, rol="operacion")
    assert sorted(r[0] for r in cx.execute("SELECT huella FROM aceptacion_politica").fetchall()) == [
        HUELLA_A, HUELLA_B]
    _falla_por_permiso(cx, "INSERT INTO aceptacion_politica (usuario_id, version, huella) VALUES (%s, '0.11', %s)",
                       U_OBS_A, HUELLA_A)
    _falla_por_permiso(cx, "UPDATE aceptacion_politica SET version = '0.10'")
    _falla_por_permiso(cx, "DELETE FROM aceptacion_politica")


@pytest.mark.rf("RF-37")
def test_una_aceptacion_no_se_cambia_ni_como_superusuario(cx):
    """El trigger aceptacion_politica_inalterable alcanza también a quien se salta RLS."""
    _sembrar_aceptaciones(cx)
    _falla_por_permiso(cx, "UPDATE aceptacion_politica SET version = '0.10' WHERE usuario_id = %s", U_OBS_A)


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize("version, huella", [("0.11", "A" * 64), ("0.11", "a" * 63), ("v0.11", "a" * 64)])
def test_la_version_y_la_huella_tienen_su_forma(cx, version, huella):
    with pytest.raises(errors.CheckViolation):
        cx.execute("INSERT INTO aceptacion_politica (usuario_id, version, huella) VALUES (%s, %s, %s)",
                   (U_OBS_A, version, huella))


# ------------------------------------------------------------------ MATU-66 (migración 0020): la propia cuenta


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize("sentencia", [
    "UPDATE usuario SET es_operacion = true WHERE id = :id",
    "UPDATE usuario SET estado = 'activo' WHERE id = :id",
    "UPDATE usuario SET email = 'otro@x.cl' WHERE id = :id",
    "UPDATE usuario SET eliminado_en = NULL WHERE id = :id",
    "DELETE FROM usuario WHERE id = :id",
], ids=["hacerse-operacion", "cambiar-estado", "cambiar-email", "eliminado-en", "borrarse"])
def test_una_cuenta_no_se_hace_operacion_ni_cambia_su_estado_ni_se_borra(sesiones_app, sentencia):
    """Con su propio contexto, como matu_app: antes de la 0020 usuario_propio (FOR ALL) y el UPDATE y el DELETE de
    toda la tabla lo dejaban."""
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from app.core.db import sesion_tenant

    with pytest.raises(DBAPIError) as error, sesion_tenant(sesiones_app, usuario_id=U_OBS_A) as s:
        s.execute(text(sentencia), {"id": U_OBS_A})
    assert isinstance(error.value.orig, errors.InsufficientPrivilege)


@pytest.mark.rf("RF-37")
def test_el_registro_no_crea_una_cuenta_de_operacion(sesiones_app):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from app.core.db import sesion_tenant

    nuevo = uuid.uuid4()
    with pytest.raises(DBAPIError) as error, sesion_tenant(sesiones_app, usuario_id=nuevo) as s:
        s.execute(text("INSERT INTO usuario (id, email, nombre, password_hash, es_operacion)"
                       " VALUES (:id, 'op.66@x.cl', 'Op', 'h', true)"), {"id": nuevo})
    assert isinstance(error.value.orig, errors.InsufficientPrivilege)


@pytest.mark.rf("RF-37")
def test_la_cuenta_cambia_lo_que_la_app_cambia_y_solo_la_propia(sesiones_app):
    """Registro (MATU-04), contraseña nueva y celular verificado (MATU-57), y el celular de la semilla (MATU-64)."""
    from sqlalchemy import text

    from app.core.db import sesion_tenant

    nuevo = uuid.uuid4()
    with pytest.raises(_Deshacer), sesion_tenant(sesiones_app, usuario_id=nuevo) as s:
        s.execute(text("INSERT INTO usuario (id, email, nombre, password_hash, telefono)"
                       " VALUES (:id, 'nueva.66@x.cl', 'Nueva', 'h', '+56900000066')"), {"id": nuevo})
        raise _Deshacer
    with pytest.raises(_Deshacer), sesion_tenant(sesiones_app, usuario_id=U_OBS_A) as s:
        for sentencia in (
            "UPDATE usuario SET password_hash = 'h2', actualizado_en = now() WHERE id = app_usuario()",
            "UPDATE usuario SET telefono = '+56900000067' WHERE id = app_usuario()",
            "UPDATE usuario SET celular_verificado_en = now(), celular_canal = 'sms' WHERE id = app_usuario()",
        ):
            assert s.execute(text(sentencia)).rowcount == 1, sentencia  # type: ignore[attr-defined]
        # La fila de otra cuenta, aunque sea del mismo grupo, no la alcanza
        ajena = s.execute(text("UPDATE usuario SET telefono = '+56900000068' WHERE id = :id"), {"id": U_ADMIN_A})
        assert ajena.rowcount == 0  # type: ignore[attr-defined]
        raise _Deshacer


# ---- MATU-74 (migración 0022, hallazgos H2 y C4 de Martín): las tareas con sus roles, operación sin avisos

FUNCIONES_SCHEDULER = {
    "plan_destruir_claves": "SELECT plan_destruir_claves(now() - interval '90 days', now())",
    "consumo_conservar": "SELECT consumo_conservar(now() - interval '90 days', now())",
    "iam_conservar": "SELECT * FROM iam_conservar(now() - interval '30 days', now() - interval '90 days', now())",
    "quiebre_conservar": "SELECT * FROM quiebre_conservar(now() - interval '90 days', now() - interval '30 days',"
                         " now())",
    # MATU-61 (D5): lo no pagado a los 30 días
    "pedido_conservar": "SELECT * FROM pedido_conservar(now() - interval '30 days', now())",
    # MATU-62 (D-62-5): la conciliación, solo ids
    "pagos_por_conciliar": "SELECT * FROM pagos_por_conciliar(now(), 10)",
    # MATU-42 (D-42-6): las invitaciones cerradas a los 30 días
    "invitacion_conservar": "SELECT invitacion_conservar(now() - interval '30 days', now())",
    # MATU-46 (decisión 25): el teléfono del relevo a los 30 días
    "relevo_conservar": "SELECT relevo_conservar(now() - interval '30 days', now())",
    # MATU-63 (D-63-8): lo que el despacho tiene que llevar, solo ids
    "despacho_pendiente": "SELECT * FROM despacho_pendiente(10)",
    # MATU-63 (D-63-5 y D-63-13): el código desde la consola de operación y el vaciado de los vencidos
    "codigo_retiro_guardar": "SELECT codigo_retiro_guardar(gen_random_uuid(), repeat('a', 64), now(),"
                             " now() + interval '90 minutes')",
    "codigo_retiro_vencer": "SELECT codigo_retiro_vencer(now())",
}
FUNCIONES_PUBLISHER = {
    "outbox_tomar": "SELECT * FROM outbox_tomar(1, now() - interval '1 day')",
    "outbox_publicado": "SELECT outbox_publicado(0, now())",
    "outbox_reintentar": "SELECT outbox_reintentar(0, now() + interval '1 minute', now())",
    "outbox_posponer": "SELECT outbox_posponer(0, now() + interval '1 hour', now())",
}
FUNCION_Y_ROL = [(f, s, "matu_scheduler") for f, s in FUNCIONES_SCHEDULER.items()] + [
    (f, s, "matu_publisher") for f, s in FUNCIONES_PUBLISHER.items()]
ROLES_TAREAS = ("matu_scheduler", "matu_publisher")


def _notificacion(cx, usuario, grupo, evento, dias):
    cx.execute("INSERT INTO notificacion (usuario_id, grupo_id, evento_id, canal, plantilla, creada_en)"
               " VALUES (%s, %s, %s, 'correo', 'quiebre_proximo', now() - make_interval(days => %s))",
               (usuario, grupo, evento, dias))


@pytest.mark.rf("RF-39")
def test_operacion_no_lee_los_avisos_de_ningun_grupo(cx):
    """C4: sin notificacion_operacion, matu_app con app.rol = 'operacion' no ve ninguna notificación."""
    cx.execute("DELETE FROM notificacion")
    _notificacion(cx, U_ADMIN_A, G_A, 1, 1)
    _notificacion(cx, U_ADMIN_B, G_B, 2, 1)
    # Con una cuenta sin avisos propios y un grupo en el contexto, tampoco (la propia sigue viendo los suyos)
    for contexto in ({"rol": "operacion"}, {"rol": "operacion", "usuario_id": U_ENC, "grupo_id": G_A}):
        como(cx, **contexto)
        assert contar(cx, "notificacion") == 0, contexto
        cx.execute("RESET ROLE")


@pytest.mark.rf("RF-39")
def test_cada_usuario_ve_solo_sus_avisos(cx):
    cx.execute("DELETE FROM notificacion")
    _notificacion(cx, U_ADMIN_A, G_A, 1, 1)
    _notificacion(cx, U_OBS_A, G_A, 1, 1)
    _notificacion(cx, U_ADMIN_B, G_B, 2, 1)
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    assert [r[0] for r in cx.execute("SELECT usuario_id FROM notificacion").fetchall()] == [U_ADMIN_A]


@pytest.mark.rf("RF-39")
def test_la_conservacion_sigue_borrando_los_avisos_a_los_90_dias(cx):
    """La trampa de C4: quiebre_conservar ve las filas como matu_owner por notificacion_conservacion."""
    cx.execute("DELETE FROM notificacion")
    _notificacion(cx, U_ADMIN_A, G_A, 1, 91)
    _notificacion(cx, U_ADMIN_A, G_A, 2, 89)
    como(cx, "matu_scheduler", rol="operacion")
    [notificaciones] = cx.execute("SELECT notificaciones FROM quiebre_conservar(now() - interval '90 days',"
                                  " now() - interval '30 days', now())").fetchone()
    assert notificaciones == 1
    cx.execute("RESET ROLE")
    assert [r[0] for r in cx.execute("SELECT evento_id FROM notificacion").fetchall()] == [2]


@pytest.mark.rf("RF-02")
@pytest.mark.parametrize(("funcion", "sentencia", "rol"), FUNCION_Y_ROL, ids=[f for f, _, _ in FUNCION_Y_ROL])
def test_solo_el_rol_de_la_tarea_ejecuta_su_funcion(cx, funcion, sentencia, rol):
    """H2: matu_app, ni con operación, ejecuta las funciones de las tareas. El rol de la tarea sí, y el otro no."""
    otro = next(r for r in ROLES_TAREAS if r != rol)
    for db_rol in ("matu_app", otro):
        como(cx, db_rol, rol="operacion")
        with pytest.raises(errors.InsufficientPrivilege):
            cx.execute(sentencia)
        cx.rollback()
    como(cx, rol, rol="operacion")
    cx.execute(sentencia)
    # Y sin app.rol = 'operacion', ni el rol de la tarea pasa el chequeo de la función
    cx.rollback()
    como(cx, rol)
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute(sentencia)


@pytest.mark.rf("RF-02")
@pytest.mark.parametrize("rol", ROLES_TAREAS)
def test_los_roles_de_las_tareas_ejecutan_solo_sus_funciones_definer(cx, rol):
    esperadas = set(FUNCIONES_SCHEDULER if rol == "matu_scheduler" else FUNCIONES_PUBLISHER)
    ejecuta = {f for (f,) in cx.execute(
        "SELECT proname FROM pg_proc WHERE pronamespace = 'public'::regnamespace AND prosecdef"
        " AND has_function_privilege(%s, oid, 'EXECUTE')", (rol,)).fetchall()}
    assert ejecuta == esperadas


@pytest.mark.rf("RF-02")
@pytest.mark.parametrize("rol", ROLES_TAREAS)
def test_los_roles_de_las_tareas_no_tocan_credenciales_ni_la_ficha(cx, rol):
    """C8: ni password_hash ni mfa_secreto_cifrado, ni las tablas de la ficha, el relevo, los tokens o las sesiones."""
    for columna in ("password_hash", "mfa_secreto_cifrado"):
        for privilegio in ("SELECT", "INSERT", "UPDATE", "REFERENCES"):
            assert cx.execute("SELECT has_column_privilege(%s, 'usuario', %s, %s)",
                              (rol, columna, privilegio)).fetchone() == (False,), (columna, privilegio)
    for tabla in ("clave_datos", "plan_cuidado", "plan_seccion", "acceso_relevo", "indice_token", "sesion_refresh",
                  "usuario", "evento_outbox", "evento_consumido"):
        for privilegio in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
            assert cx.execute("SELECT has_table_privilege(%s, %s, %s)",
                              (rol, tabla, privilegio)).fetchone() == (False,), (tabla, privilegio)
    # Lo único que tienen sobre tablas: el scheduler, leer id y estado de grupo_familiar
    tablas = cx.execute("SELECT table_name, privilege_type FROM information_schema.role_table_grants"
                        " WHERE grantee = %s AND table_schema = 'public'", (rol,)).fetchall()
    columnas = set(cx.execute("SELECT table_name, column_name, privilege_type FROM information_schema.column_privileges"
                              " WHERE grantee = %s AND table_schema = 'public'", (rol,)).fetchall())
    assert tablas == []
    assert columnas == ({("grupo_familiar", "id", "SELECT"), ("grupo_familiar", "estado", "SELECT")}
                        if rol == "matu_scheduler" else set())


@pytest.mark.rf("RF-02")
@pytest.mark.parametrize("rol", ROLES_TAREAS)
def test_los_roles_de_las_tareas_no_tienen_atributos_ni_membresias(cx, rol):
    """C7: sin SUPERUSER, BYPASSRLS, CREATEROLE, CREATEDB ni REPLICATION, y sin ser miembros de matu_owner ni de
    matu_app."""
    assert cx.execute("SELECT rolcanlogin, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb, rolreplication"
                      " FROM pg_roles WHERE rolname = %s", (rol,)).fetchone() == (True, False, False, False, False,
                                                                                   False)
    for otro in ("matu_owner", "matu_app", *(r for r in ROLES_TAREAS if r != rol)):
        assert cx.execute("SELECT pg_has_role(%s, %s, 'USAGE')", (rol, otro)).fetchone() == (False,), otro
    assert cx.execute("SELECT count(*) FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.member"
                      " WHERE r.rolname = %s", (rol,)).fetchone() == (0,)


@pytest.mark.rf("RF-02")
def test_los_privilegios_por_omision_no_dan_nada_a_los_roles_de_las_tareas(cx):
    """C12: ALTER DEFAULT PRIVILEGES solo nombra a matu_app."""
    beneficiarios = {r for (r,) in cx.execute(
        "SELECT DISTINCT a.grantee::regrole::text FROM pg_default_acl d, aclexplode(d.defaclacl) a").fetchall()}
    assert beneficiarios & set(ROLES_TAREAS) == set()


# ---- MATU-61 (migración 0023): el pedido sin pagar por operación y por rol, y un registro por comercio (D7)

def _persona_a2(cx):
    cx.execute("INSERT INTO persona_cuidada (id, grupo_id, nombre, nombre_pila, nivel_apoyo)"
               " VALUES (%s, %s, 'Rosa Díaz', 'Rosa', 'apoyo_parcial') ON CONFLICT (id) DO NOTHING", (P_A2, G_A))


def _pedido_de_dos_comercios(cx, enviado: bool = True):
    """Como superusuario: un pedido pagado de A preparado por dos comercios, con su parte cada uno (D7)."""
    _persona_a2(cx)
    cx.execute("INSERT INTO usuario (id, email, nombre, password_hash) VALUES (%s, 'enc2@comercio.cl', 'Enc 2', 'h')",
               (U_ENC_2,))
    cx.execute("INSERT INTO comercio (id, razon_social, nombre_fantasia, rut, direccion, comuna)"
               " VALUES (%s, 'Bodega Tres SpA', 'Bodega Tres', '76.000.000-3', 'Av. Ossa 3', 'La Reina')",
               (COMERCIO_2,))
    cx.execute("INSERT INTO usuario_comercio (usuario_id, comercio_id) VALUES (%s, %s)", (U_ENC_2, COMERCIO_2))
    cx.execute("INSERT INTO producto (id, categoria_id, nombre, presentacion, unidad, unidades_por_envase)"
               " VALUES (%s, '00000000-0000-0000-0000-000000000c01', 'Toallitas húmedas', 'x80', 'unidad', 80)",
               (PRODUCTO_2,))
    cx.execute("INSERT INTO oferta (id, producto_id, comercio_id, precio) VALUES (%s, %s, %s, 4490)",
               (OFERTA_2, PRODUCTO_2, COMERCIO_2))
    cx.execute("INSERT INTO pedido (id, grupo_id, persona_cuidada_id, estado, subtotal_productos, costo_envio, total,"
               " creado_por) VALUES (%s, %s, %s, 'borrador', 17480, 2990, 20470, %s)",
               (PED_A_DOS, G_A, P_A2, U_ADMIN_A))
    enviado_en = "now()" if enviado else "NULL"
    for parte, comercio, referencia in ((uuid.UUID(int=0xA31), COMERCIO, "DDDU22"),
                                         (uuid.UUID(int=0xA32), COMERCIO_2, "DDDD22")):
        cx.execute("INSERT INTO pedido_comercio (id, grupo_id, pedido_id, comercio_id, referencia, enviado_en)"
                   f" VALUES (%s, %s, %s, %s, %s, {enviado_en})", (parte, G_A, PED_A_DOS, comercio, referencia))
    cx.execute("INSERT INTO pedido_linea (pedido_id, oferta_id, producto_id, cantidad, precio_unitario,"
               " pedido_comercio_id) VALUES (%s, %s, %s, 1, 12990, %s), (%s, %s, %s, 1, 4490, %s)",
               (PED_A_DOS, OFERTA, PRODUCTO, uuid.UUID(int=0xA31), PED_A_DOS, OFERTA_2, PRODUCTO_2,
                uuid.UUID(int=0xA32)))
    cx.execute("INSERT INTO regla_sustitucion (pedido_id, producto_id, accion) VALUES (%s, %s, 'quitar')",
               (PED_A_DOS, PRODUCTO))
    # MATU-62: solo el sistema marca el pago (trigger pedido_escritura_del_pago); aquí, sin triggers
    cx.execute("SET LOCAL session_replication_role = replica")
    cx.execute("""UPDATE pedido SET estado = 'enviado_a_comercio', total_confirmado_en = now() - interval '5 minutes',
                  total_vence_en = now() + interval '10 minutes', pagado_en = now(), condiciones_version = '0.1',
                  condiciones_aceptadas_en = now(), condiciones_huella = repeat('d', 64),
                  condiciones_aceptadas_por = creado_por WHERE id = %s""",
               (PED_A_DOS,))
    cx.execute("SET LOCAL session_replication_role = origin")


A_PAGADOR = {"usuario_id": U_PAG_A, "grupo_id": G_A}
A_OBSERVADOR = {"usuario_id": U_OBS_A, "grupo_id": G_A}
A_ADMIN = {"usuario_id": U_ADMIN_A, "grupo_id": G_A}
INSERTAR_PEDIDO = ("INSERT INTO pedido (grupo_id, persona_cuidada_id, estado, creado_por)"
                   " VALUES (%s, %s, 'cancelado', %s)"
                   " RETURNING id")


@pytest.mark.rf("RF-21")
@pytest.mark.parametrize("ctx", [A_PAGADOR, A_OBSERVADOR], ids=["pagador", "observador"])
def test_pagador_y_observador_leen_el_pedido_y_no_lo_escriben(cx, ctx):
    """C3 y C13: lee todo el grupo; escriben solo admin y cuidador (antes de la 0023, pedido_familia era FOR ALL)."""
    cx.execute(REGLA, (PED_A_BORRADOR, PRODUCTO, "otro_comercio"))
    como(cx, **ctx)
    assert contar(cx, "pedido", f"id = '{PED_A_BORRADOR}'") == 1
    assert contar(cx, "regla_sustitucion", f"pedido_id = '{PED_A_BORRADOR}'") == 1
    # MATU-62 (D-62-16): el pagador alcanza la fila del pedido sin pagar para aceptar las condiciones, y el trigger
    # pedido_escritura_del_pago rechaza todo lo demás
    if ctx == A_PAGADOR:
        with pytest.raises(errors.CheckViolation), cx.transaction():
            cx.execute(f"UPDATE pedido SET version = version + 1 WHERE id = '{PED_A_BORRADOR}'")
    else:
        assert cx.execute(f"UPDATE pedido SET version = version + 1 WHERE id = '{PED_A_BORRADOR}'").rowcount == 0
    for sentencia in (
        f"UPDATE pedido_linea SET cantidad = 5 WHERE pedido_id = '{PED_A_BORRADOR}'",
        f"UPDATE regla_sustitucion SET accion = 'quitar' WHERE pedido_id = '{PED_A_BORRADOR}'",
        f"DELETE FROM pedido_linea WHERE pedido_id = '{PED_A_BORRADOR}'",
        f"DELETE FROM regla_sustitucion WHERE pedido_id = '{PED_A_BORRADOR}'",
    ):
        assert cx.execute(sentencia).rowcount == 0, sentencia
    for sentencia, parametros in (
        (INSERTAR_PEDIDO, (G_A, P_A, ctx["usuario_id"])),
        ("INSERT INTO pedido_transicion (pedido_id, hacia, actor_tipo) VALUES (%s, 'cancelado', 'usuario')",
         (PED_A_BORRADOR,)),
    ):
        cx.execute("SAVEPOINT s")
        with pytest.raises(errors.InsufficientPrivilege):
            cx.execute(sentencia, parametros)
        cx.execute("ROLLBACK TO SAVEPOINT s")


@pytest.mark.rf("RF-21")
def test_admin_escribe_su_pedido_y_nadie_lo_borra_desde_la_api(cx):
    cx.execute(REGLA, (PED_A_BORRADOR, PRODUCTO, "otro_comercio"))
    como(cx, **A_ADMIN)
    assert cx.execute(f"UPDATE pedido SET version = version + 1 WHERE id = '{PED_A_BORRADOR}'").rowcount == 1
    assert cx.execute(f"UPDATE regla_sustitucion SET accion = 'quitar' WHERE pedido_id = '{PED_A_BORRADOR}'"
                      ).rowcount == 1
    # Sin política de DELETE para la familia: lo no pagado lo borra pedido_conservar (D5)
    assert cx.execute(f"DELETE FROM pedido WHERE id = '{PED_A_BORRADOR}'").rowcount == 0
    # Otro grupo, 0 filas
    assert cx.execute(f"UPDATE pedido SET version = version + 1 WHERE id = '{PED_B_ENVIADO}'").rowcount == 0


@pytest.mark.rf("RF-21")
def test_el_observador_no_ve_la_entrega_y_el_pagador_si(cx):
    """C3: el observador ve el carrito sin la dirección ni el teléfono."""
    como(cx, **A_OBSERVADOR)
    assert contar(cx, "pedido_entrega") == 0
    cx.execute("RESET ROLE")
    como(cx, **A_PAGADOR)
    assert contar(cx, "pedido_entrega") == 1


@pytest.mark.rf("RF-21")
def test_cada_comercio_ve_solo_su_parte_y_sus_lineas(cx):
    """D7 y R8: el segundo comercio ve su parte con su línea, nunca la del otro ni su referencia. Desde la 0029, solo
    por las funciones del comercio (D-63-1)."""
    _pedido_de_dos_comercios(cx)
    como(cx, usuario_id=U_ENC_2, comercio_id=COMERCIO_2)
    assert contar(cx, "pedido") == 0 and contar(cx, "pedido_linea") == 0 and contar(cx, "pedido_comercio") == 0
    assert [r[0] for r in cx.execute("SELECT referencia FROM comercio_partes('-infinity')").fetchall()] == ["DDDD22"]
    assert [r[0] for r in cx.execute("SELECT producto_nombre FROM comercio_lineas(%s)",
                                     (uuid.UUID(int=0xA32),)).fetchall()] == ["Toallitas húmedas"]
    # La parte del otro comercio: cero líneas
    assert cx.execute("SELECT * FROM comercio_lineas(%s)", (uuid.UUID(int=0xA31),)).fetchall() == []
    cx.execute("RESET ROLE")
    como(cx, usuario_id=U_ENC, comercio_id=COMERCIO)
    assert len(cx.execute("SELECT * FROM comercio_lineas(%s)", (uuid.UUID(int=0xA31),)).fetchall()) == 1
    # R8 y D7: tampoco la elección de la familia si falta un producto (regla_sustitucion, cierre del analista)
    for t in ("pedido_entrega", "pedido_transicion", "idempotencia", "persona_cuidada", "direccion",
              "regla_sustitucion"):
        assert contar(cx, t) == 0, t


@pytest.mark.rf("RF-21")
def test_la_parte_no_enviada_no_la_ve_el_comercio(cx):
    _pedido_de_dos_comercios(cx, enviado=False)
    como(cx, usuario_id=U_ENC_2, comercio_id=COMERCIO_2)
    assert contar(cx, "pedido") == 0 and contar(cx, "pedido_linea") == 0 and contar(cx, "pedido_comercio") == 0
    assert cx.execute("SELECT * FROM comercio_partes('-infinity')").fetchall() == []


@pytest.mark.rf("RF-21")
def test_pedido_comercio_tiene_rls_forzado_y_el_grupo_de_su_pedido(cx):
    assert cx.execute("SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname = 'pedido_comercio'"
                      ).fetchone() == (True,)
    como(cx, **A_ADMIN)
    # Con el grupo de otro (RLS) o con el pedido de otro grupo (pedido_comercio_mismo_grupo): no entra
    for grupo in (G_B, G_A):
        cx.execute("SAVEPOINT s")
        with pytest.raises((errors.InsufficientPrivilege, errors.CheckViolation)):
            cx.execute("INSERT INTO pedido_comercio (grupo_id, pedido_id, comercio_id, referencia)"
                       " VALUES (%s, %s, %s, 'TTRGRP')", (grupo, PED_B_ENVIADO, COMERCIO))
        cx.execute("ROLLBACK TO SAVEPOINT s")
    como(cx, usuario_id=U_ADMIN_B, grupo_id=G_B)
    assert contar(cx, "pedido_comercio", f"pedido_id = '{PED_A_ENVIADO}'") == 0


@pytest.mark.rf("RF-21")
def test_la_clave_de_idempotencia_la_escribe_solo_su_cuenta(cx):
    como(cx, **A_ADMIN)
    cx.execute("SAVEPOINT s")
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("INSERT INTO idempotencia (grupo_id, endpoint, clave, usuario_id, hash_peticion)"
                   " VALUES (%s, 'e', 'k-ajena', %s, '\\x00')", (G_A, U_OBS_A))
    cx.execute("ROLLBACK TO SAVEPOINT s")
    cx.execute("RESET ROLE")
    como(cx, **A_OBSERVADOR)
    # La del admin la ve (para responder 422 idempotencia-reutilizada), pero no la cambia ni la borra
    assert contar(cx, "idempotencia") == 1
    assert cx.execute("UPDATE idempotencia SET estado_http = 500").rowcount == 0
    assert cx.execute("DELETE FROM idempotencia").rowcount == 0


@pytest.mark.rf("RF-21")
def test_la_regla_queda_fija_con_el_pedido_pagado(cx):
    """C12: ni el superusuario cambia, agrega ni borra la regla de un pedido pagado."""
    _pedido_de_dos_comercios(cx)
    for sentencia in (
        f"UPDATE regla_sustitucion SET accion = 'otro_comercio' WHERE pedido_id = '{PED_A_DOS}'",
        f"DELETE FROM regla_sustitucion WHERE pedido_id = '{PED_A_DOS}'",
        f"INSERT INTO regla_sustitucion (pedido_id, producto_id, accion)"
        f" VALUES ('{PED_A_DOS}', '{PRODUCTO_2}', 'quitar')",
    ):
        with pytest.raises(errors.CheckViolation), cx.transaction():
            cx.execute(sentencia)


@pytest.mark.rf("RF-21")
def test_no_hay_pago_sin_condiciones_aceptadas_ni_motivo_libre(cx):
    """D6 y C19."""
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute(f"UPDATE pedido SET condiciones_aceptadas_en = NULL, condiciones_version = NULL,"
                   f" condiciones_huella = NULL WHERE id = '{PED_A_ENVIADO}'")
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("INSERT INTO pedido_transicion (pedido_id, hacia, actor_tipo, motivo)"
                   " VALUES (%s, 'cancelado', 'usuario', 'se le acabaron los remedios')", (PED_A_BORRADOR,))
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("UPDATE direccion SET lat = -33.45, lng = -70.66")


@pytest.mark.rf("RF-21")
def test_un_solo_pedido_sin_pagar_por_persona(cx):
    """C4: pedido_sin_pagar_uq."""
    with pytest.raises(errors.UniqueViolation):
        cx.execute("INSERT INTO pedido (grupo_id, persona_cuidada_id, estado, creado_por)"
                   " VALUES (%s, %s, 'borrador', %s)", (G_A, P_A, U_ADMIN_A))


@pytest.mark.rf("RF-21")
def test_pedido_conservar_borra_lo_no_pagado_con_su_linea_de_tiempo(cx):
    """D5 y C10: con su línea de tiempo (la cascada que el trigger de solo inserción deja pasar), y nunca lo pagado."""
    cx.execute("SET LOCAL session_replication_role = replica")
    cx.execute(f"UPDATE pedido SET actualizado_en = now() - interval '40 days' WHERE id IN"
               f" ('{PED_A_BORRADOR}', '{PED_A_ENVIADO}')")
    cx.execute("SET LOCAL session_replication_role = origin")
    como(cx, "matu_scheduler", rol="operacion")
    assert cx.execute("SELECT * FROM pedido_conservar(now() - interval '30 days', now())").fetchone()[0] == 1
    cx.execute("RESET ROLE")
    assert contar(cx, "pedido", f"id = '{PED_A_BORRADOR}'") == 0
    assert contar(cx, "pedido_transicion", f"pedido_id = '{PED_A_BORRADOR}'") == 0
    assert contar(cx, "pedido", f"id = '{PED_A_ENVIADO}'") == 1
    # Fuera de la cascada, la línea de tiempo sigue siendo de solo inserción
    cx.execute("INSERT INTO pedido_transicion (pedido_id, hacia, actor_tipo) VALUES (%s, 'pagado', 'sistema')",
               (PED_A_ENVIADO,))
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("DELETE FROM pedido_transicion")


@pytest.mark.rf("RF-21")
def test_la_api_no_ejecuta_pedido_conservar(cx):
    como(cx, rol="operacion")
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("SELECT * FROM pedido_conservar(now() - interval '30 days', now())")


@pytest.mark.rf("RF-21")
def test_borrar_un_perfil_deja_la_reposicion_programada_sin_perfil(cx):
    """D3: plan_reposicion_linea.perfil_consumo_id ON DELETE SET NULL; antes de la 0023, borrar el perfil fallaba."""
    perfil = cx.execute("SELECT id FROM perfil_consumo WHERE grupo_id = %s", (G_A,)).fetchone()[0]
    plan = cx.execute("INSERT INTO plan_reposicion (grupo_id, persona_cuidada_id, comercio_id, frecuencia_dias,"
                      " proxima_fecha, creado_por) VALUES (%s, %s, %s, 30, current_date + 30, %s) RETURNING id",
                      (G_A, P_A, COMERCIO, U_ADMIN_A)).fetchone()[0]
    cx.execute("INSERT INTO plan_reposicion_linea (plan_reposicion_id, producto_id, perfil_consumo_id,"
               " cantidad_envases) VALUES (%s, '00000000-0000-0000-0000-000000000f01', %s, 1)", (plan, perfil))
    cx.execute("DELETE FROM perfil_consumo WHERE id = %s", (perfil,))
    assert cx.execute("SELECT perfil_consumo_id FROM plan_reposicion_linea WHERE plan_reposicion_id = %s",
                      (plan,)).fetchone() == (None,)


# ---- MATU-62 (migración 0024): el pago por operación y por rol, la venta atada al total y la conservación con dinero

TABLAS_DEL_PAGO = ("cargo", "participacion", "transaccion_pasarela")


def _cuidador_a(cx):
    """Un cuidador en A, como superusuario y solo en esta prueba (la semilla no trae cuidador)."""
    cx.execute("INSERT INTO membresia (grupo_id, usuario_id, rol) VALUES (%s, %s, 'cuidador')"
               " ON CONFLICT DO NOTHING", (G_A, U_NUEVO))


def _pedido_por_pagar(cx, total_confirmado_en="now() - interval '1 minute'"):
    """Como superusuario: un pedido de A con el total confirmado y vigente, de otra persona de A (C4)."""
    _persona_a2(cx)
    return cx.execute(
        "INSERT INTO pedido (grupo_id, persona_cuidada_id, estado, subtotal_productos, costo_envio, total,"
        f" total_confirmado_en, total_vence_en, creado_por) VALUES (%s, %s, 'total_confirmado', 12990, 2990, 15980,"
        f" {total_confirmado_en}, {total_confirmado_en} + interval '15 minutes', %s) RETURNING id, total_confirmado_en",
        (G_A, P_A2, U_ADMIN_A)).fetchone()


def _venta(cx, pedido, confirmado_en, *, estado="iniciada", monto=15980, token=None, usuario=U_ADMIN_A):
    """Como superusuario: el cargo, la participación y una venta del pedido."""
    cargo = cx.execute("INSERT INTO cargo (pedido_id) VALUES (%s) ON CONFLICT (pedido_id) DO UPDATE"
                       " SET pedido_id = EXCLUDED.pedido_id RETURNING id", (pedido,)).fetchone()[0]
    participacion = cx.execute(
        "INSERT INTO participacion (cargo_id, usuario_id, porcentaje_bp) VALUES (%s, %s, 10000)"
        " ON CONFLICT (cargo_id, usuario_id) DO UPDATE SET porcentaje_bp = 10000 RETURNING id",
        (cargo, usuario)).fetchone()[0]
    venta = cx.execute(
        "INSERT INTO transaccion_pasarela (participacion_id, cargo_id, proveedor, tipo, buy_order, session_id, token,"
        " monto, estado, idempotency_key, total_confirmado_en) VALUES (%s, %s, 'webpay_plus', 'venta', %s, 's', %s,"
        " %s, %s, %s, %s) RETURNING id",
        (participacion, cargo, uuid.uuid4().hex[:26], token or uuid.uuid4().hex, monto, estado, uuid.uuid4().hex,
         confirmado_en)).fetchone()[0]
    return cargo, participacion, venta


@pytest.mark.rf("RF-25")
def test_las_politicas_del_pago_son_por_operacion_sin_for_all(cx):
    filas = cx.execute("SELECT tablename, policyname, cmd FROM pg_policies WHERE tablename = ANY(%s)",
                       (list(TABLAS_DEL_PAGO),)).fetchall()
    assert filas, "sin políticas del pago"
    assert [f for f in filas if f[2] == "ALL"] == []
    privilegios = {(t, p) for t, p in cx.execute(
        "SELECT table_name, privilege_type FROM information_schema.role_table_grants"
        " WHERE grantee = 'matu_app' AND table_name = ANY(%s)", (list(TABLAS_DEL_PAGO),))}
    assert not {p for t, p in privilegios if p == "DELETE"}


@pytest.mark.rf("RF-25")
def test_el_observador_no_lee_el_pago_y_admin_cuidador_y_pagador_si(cx):
    _cuidador_a(cx)
    for usuario, ve in ((U_OBS_A, False), (U_ADMIN_A, True), (U_NUEVO, True), (U_PAG_A, True)):
        como(cx, usuario_id=usuario, grupo_id=G_A)
        for tabla in TABLAS_DEL_PAGO:
            assert (contar(cx, tabla) > 0) is ve, (usuario, tabla)
        cx.execute("RESET ROLE")


@pytest.mark.rf("RF-25")
@pytest.mark.parametrize("usuario", [U_OBS_A, U_NUEVO], ids=["observador", "cuidador"])
def test_el_observador_y_el_cuidador_no_pagan(cx, usuario):
    """D-62-8: no crean el cargo; sin cargo no hay participación ni venta."""
    _cuidador_a(cx)
    pedido, _ = _pedido_por_pagar(cx)
    como(cx, usuario_id=usuario, grupo_id=G_A)
    with pytest.raises(errors.InsufficientPrivilege), cx.transaction():
        cx.execute("INSERT INTO cargo (pedido_id) VALUES (%s)", (pedido,))
    if usuario == U_OBS_A:
        # El observador tampoco acepta las condiciones: no alcanza la fila
        assert cx.execute("UPDATE pedido SET condiciones_version = '0.2', condiciones_aceptadas_en = now(),"
                          " condiciones_huella = repeat('a', 64), condiciones_aceptadas_por = %s WHERE id = %s",
                          (usuario, pedido)).rowcount == 0


@pytest.mark.rf("RF-25")
@pytest.mark.parametrize("usuario", [U_ADMIN_A, U_PAG_A], ids=["admin", "pagador"])
def test_admin_y_pagador_abren_la_venta_atada_al_total(cx, usuario):
    pedido, confirmado_en = _pedido_por_pagar(cx)
    como(cx, usuario_id=usuario, grupo_id=G_A)
    cargo = cx.execute("INSERT INTO cargo (pedido_id) VALUES (%s) RETURNING id", (pedido,)).fetchone()[0]
    participacion = cx.execute("INSERT INTO participacion (cargo_id, usuario_id, porcentaje_bp) VALUES (%s, %s, 10000)"
                               " RETURNING id", (cargo, usuario)).fetchone()[0]
    venta = ("INSERT INTO transaccion_pasarela (participacion_id, cargo_id, proveedor, tipo, buy_order, session_id,"
             " token, monto, estado, idempotency_key, total_confirmado_en)"
             " VALUES (%s, %s, 'webpay_plus', 'venta', %s, 's', %s, %s, 'iniciada', %s, %s)")
    # D-62-4: atada al total y al total_confirmado_en del pedido
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute(venta, (participacion, cargo, "o" * 26, "t-otro-monto", 15981, "k-otro-monto", confirmado_en))
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute(venta, (participacion, cargo, "p" * 26, "t-otro-total", 15980, "k-otro-total",
                           confirmado_en + timedelta(seconds=1)))
    cx.execute(venta, (participacion, cargo, "q" * 26, "t-bien", 15980, "k-bien", confirmado_en))
    # Quien paga no cierra la venta ni la marca aprobada: eso es del sistema
    assert cx.execute("UPDATE transaccion_pasarela SET estado = 'aprobada' WHERE token = 't-bien'").rowcount == 0


@pytest.mark.rf("RF-25")
def test_el_pagador_solo_escribe_las_condiciones_a_su_nombre(cx):
    """D-62-16: el pagador no arma el pedido; acepta las condiciones con su cuenta y nada más."""
    pedido, _ = _pedido_por_pagar(cx)
    como(cx, usuario_id=U_PAG_A, grupo_id=G_A)
    for cambio in ("costo_envio = 0, total = subtotal_productos", "estado = 'cancelado'", "version = version + 1"):
        with pytest.raises(errors.CheckViolation), cx.transaction():
            cx.execute(f"UPDATE pedido SET {cambio} WHERE id = %s", (pedido,))
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("UPDATE pedido SET condiciones_version = '0.2', condiciones_aceptadas_en = now(),"
                   " condiciones_huella = repeat('a', 64), condiciones_aceptadas_por = %s WHERE id = %s",
                   (U_ADMIN_A, pedido))
    assert cx.execute("UPDATE pedido SET condiciones_version = '0.2', condiciones_aceptadas_en = now(),"
                      " condiciones_huella = repeat('a', 64), condiciones_aceptadas_por = %s WHERE id = %s",
                      (U_PAG_A, pedido)).rowcount == 1
    # Ni la referencia ni el pago
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("UPDATE pedido SET referencia = '1234' WHERE id = %s", (pedido,))


@pytest.mark.rf("RF-25")
def test_otro_grupo_no_ve_ni_toca_el_pago(cx):
    pedido, confirmado_en = _pedido_por_pagar(cx)
    cargo, _, venta = _venta(cx, pedido, confirmado_en)
    for ctx in ({"usuario_id": U_ADMIN_B, "grupo_id": G_B}, {"grupo_id": G_B, "rol": "sistema"}):
        como(cx, **ctx)
        for tabla in TABLAS_DEL_PAGO:
            assert contar(cx, tabla, f"id IN ('{cargo}', '{venta}')") == 0, (ctx, tabla)
        assert cx.execute("UPDATE transaccion_pasarela SET estado = 'rechazada' WHERE id = %s", (venta,)).rowcount == 0
        cx.execute("RESET ROLE")


@pytest.mark.rf("RF-25")
@pytest.mark.parametrize("ctx", [
    {"usuario_id": U_ADMIN_A, "grupo_id": G_A}, {"grupo_id": G_A, "rol": "sistema"}, {"rol": "operacion"},
], ids=["admin", "sistema", "operacion"])
def test_nadie_borra_cargos_participaciones_ni_transacciones(cx, ctx):
    como(cx, **ctx)
    for tabla in TABLAS_DEL_PAGO:
        with pytest.raises(errors.InsufficientPrivilege), cx.transaction():
            cx.execute(f"DELETE FROM {tabla}")


@pytest.mark.rf("RF-25")
def test_el_sistema_marca_pagado_solo_con_la_venta_aprobada_del_mismo_total(cx):
    """D-62-4: total_confirmado → pagado con una venta aprobada y no anulada del mismo total y total_confirmado_en."""
    pedido, confirmado_en = _pedido_por_pagar(cx)
    _, _, venta = _venta(cx, pedido, confirmado_en)
    cx.execute("UPDATE pedido SET condiciones_version = '0.2', condiciones_aceptadas_en = now(),"
               " condiciones_huella = repeat('a', 64), condiciones_aceptadas_por = %s WHERE id = %s",
               (U_ADMIN_A, pedido))
    como(cx, grupo_id=G_A, rol="sistema")
    pagar = "UPDATE pedido SET estado = 'pagado', pagado_en = now(), referencia = '4821' WHERE id = %s"
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute(pagar, (pedido,))  # la venta sigue iniciada
    cx.execute("UPDATE transaccion_pasarela SET estado = 'aprobada', cerrada_en = now() WHERE id = %s", (venta,))
    # El sistema solo marca el pago: no cambia el total ni la entrega
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("UPDATE pedido SET estado = 'pagado', pagado_en = now(), costo_envio = 0, total = 12990"
                   " WHERE id = %s", (pedido,))
    assert cx.execute(pagar, (pedido,)).rowcount == 1
    cx.execute("INSERT INTO pedido_transicion (pedido_id, desde, hacia, actor_tipo, motivo)"
               " VALUES (%s, 'total_confirmado', 'pagado', 'sistema', 'pago_aprobado')", (pedido,))
    # Con el pago, las condiciones quedan fijas, también para el admin
    cx.execute("RESET ROLE")
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("UPDATE pedido SET condiciones_version = '0.3' WHERE id = %s", (pedido,))


@pytest.mark.rf("RF-25")
def test_una_sola_venta_aprobada_por_cargo_token_unico_y_sin_respuesta_de_transbank(cx):
    pedido, confirmado_en = _pedido_por_pagar(cx)
    _, _, primera = _venta(cx, pedido, confirmado_en, token="token-sintetico-1")
    _, _, segunda = _venta(cx, pedido, confirmado_en, token="token-sintetico-2")
    with pytest.raises(errors.UniqueViolation), cx.transaction():
        _venta(cx, pedido, confirmado_en, token="token-sintetico-1")
    cx.execute("UPDATE transaccion_pasarela SET estado = 'aprobada' WHERE id = %s", (primera,))
    with pytest.raises(errors.UniqueViolation), cx.transaction():
        cx.execute("UPDATE transaccion_pasarela SET estado = 'aprobada' WHERE id = %s", (segunda,))
    # Regla 3: aprobada y anulada completa en el mismo momento, sí
    cx.execute("UPDATE transaccion_pasarela SET estado = 'aprobada', anulacion_total = true WHERE id = %s", (segunda,))
    for cambio in ("payload_respuesta = '{\"vci\": \"TSY\"}'", "ultimos4 = 'abcd'", "monto = 1",
                   "estado = 'iniciada'"):
        with pytest.raises(errors.CheckViolation), cx.transaction():
            cx.execute(f"UPDATE transaccion_pasarela SET {cambio} WHERE id = %s", (primera,))


@pytest.mark.rf("RF-25")
def test_lo_anulado_no_supera_lo_cobrado_y_una_linea_se_devuelve_una_vez(cx):
    pedido, confirmado_en = _pedido_por_pagar(cx)
    cargo, participacion, venta = _venta(cx, pedido, confirmado_en, estado="aprobada")
    anular = ("INSERT INTO transaccion_pasarela (participacion_id, cargo_id, proveedor, tipo, buy_order, monto, estado,"
              " idempotency_key, venta_id, motivo_anulacion) VALUES (%s, %s, 'webpay_plus', 'anulacion', %s, %s,"
              " 'iniciada', %s, %s, 'pago_tardio')")
    como(cx, grupo_id=G_A, rol="sistema")
    cx.execute(anular, (participacion, cargo, "a" * 26, 10000, "k-anular-1", venta))
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute(anular, (participacion, cargo, "b" * 26, 5981, "k-anular-2", venta))
    cx.execute(anular, (participacion, cargo, "c" * 26, 5980, "k-anular-3", venta))


@pytest.mark.rf("RF-25")
def test_la_vuelta_resuelve_su_venta_solo_como_sistema_y_sin_grupo(cx):
    pedido, confirmado_en = _pedido_por_pagar(cx)
    _, _, venta = _venta(cx, pedido, confirmado_en, token="token-de-la-vuelta")
    como(cx, rol="sistema")
    assert cx.execute("SELECT * FROM pago_resolver_venta('token-de-la-vuelta', NULL, NULL)").fetchall() == [
        (venta, G_A)]
    assert cx.execute("SELECT * FROM pago_resolver_venta('otro', NULL, NULL)").fetchall() == []
    # Sin rol sistema, o con un grupo o una cuenta, no
    cx.execute("RESET ROLE")
    for ctx in ({"grupo_id": G_B, "rol": "sistema"}, {"usuario_id": U_ADMIN_A, "grupo_id": G_A}, {"rol": "operacion"}):
        como(cx, **ctx)
        with pytest.raises(errors.InsufficientPrivilege), cx.transaction():
            cx.execute("SELECT * FROM pago_resolver_venta('token-de-la-vuelta', NULL, NULL)")
        cx.execute("RESET ROLE")


@pytest.mark.rf("RF-25")
def test_la_conciliacion_es_solo_de_matu_scheduler_y_entrega_solo_ids(cx):
    pedido, confirmado_en = _pedido_por_pagar(cx)
    _, _, venta = _venta(cx, pedido, confirmado_en, estado="autorizando")
    como(cx, rol="operacion")
    with pytest.raises(errors.InsufficientPrivilege), cx.transaction():
        cx.execute("SELECT * FROM pagos_por_conciliar(now(), 10)")
    cx.execute("RESET ROLE")
    como(cx, "matu_scheduler", rol="operacion")
    filas = cx.execute("SELECT * FROM pagos_por_conciliar(now(), 500)").fetchall()
    assert (venta, G_A) in filas and all(len(f) == 2 for f in filas)


@pytest.mark.rf("RF-25")
def test_pedido_conservar_separa_por_dinero(cx):
    """D-62-13 (c): sin dinero se borra todo con el pedido; con dinero (aunque anulado) se conservan el pedido sin
    entrega, el cargo y las transacciones, y se borran las líneas, las reglas y la línea de tiempo."""
    sin_dinero, confirmado_en = _pedido_por_pagar(cx, "now() - interval '40 days'")
    cargo_sin, _, venta_sin = _venta(cx, sin_dinero, confirmado_en, estado="rechazada")
    cx.execute("UPDATE cargo SET estado = 'rechazado' WHERE id = %s", (cargo_sin,))
    cx.execute("UPDATE pedido SET estado = 'cancelado' WHERE id = %s", (sin_dinero,))
    # Otra persona de A, con un pago tardío anulado completo (regla 3) y el pedido cancelado
    persona_3 = cx.execute("INSERT INTO persona_cuidada (grupo_id, nombre, nombre_pila, nivel_apoyo)"
                           " VALUES (%s, 'Ana Rojas', 'Ana', 'apoyo_parcial') RETURNING id", (G_A,)).fetchone()[0]
    con_dinero, confirmado_3 = cx.execute(
        "INSERT INTO pedido (grupo_id, persona_cuidada_id, estado, subtotal_productos, costo_envio, total,"
        " total_confirmado_en, total_vence_en, creado_por) VALUES (%s, %s, 'total_confirmado', 12990, 2990, 15980,"
        " now() - interval '40 days', now() - interval '40 days' + interval '15 minutes', %s)"
        " RETURNING id, total_confirmado_en", (G_A, persona_3, U_ADMIN_A)).fetchone()
    cx.execute("INSERT INTO pedido_linea (pedido_id, oferta_id, producto_id, cantidad, precio_unitario)"
               " VALUES (%s, %s, %s, 1, 12990)", (con_dinero, OFERTA, PRODUCTO))
    cx.execute("INSERT INTO pedido_transicion (pedido_id, hacia, actor_tipo) VALUES (%s, 'borrador', 'sistema')",
               (con_dinero,))
    cargo_con, participacion, venta_con = _venta(cx, con_dinero, confirmado_3)
    cx.execute("UPDATE transaccion_pasarela SET estado = 'aprobada', anulacion_total = true WHERE id = %s",
               (venta_con,))
    cx.execute("INSERT INTO transaccion_pasarela (participacion_id, cargo_id, proveedor, tipo, buy_order, monto,"
               " estado, idempotency_key, venta_id, motivo_anulacion) VALUES (%s, %s, 'webpay_plus', 'anulacion', %s,"
               " 15980,"
               " 'aprobada', %s, %s, 'pago_tardio')", (participacion, cargo_con, "z" * 26, "k-z", venta_con))
    cx.execute("UPDATE pedido SET estado = 'cancelado' WHERE id = %s", (con_dinero,))
    cx.execute("SET LOCAL session_replication_role = replica")
    cx.execute("UPDATE pedido SET actualizado_en = now() - interval '40 days' WHERE id IN (%s, %s)",
               (sin_dinero, con_dinero))
    cx.execute("SET LOCAL session_replication_role = origin")

    como(cx, "matu_scheduler", rol="operacion")
    cx.execute("SELECT * FROM pedido_conservar(now() - interval '30 days', now())")
    cx.execute("RESET ROLE")

    assert contar(cx, "pedido", f"id = '{sin_dinero}'") == 0
    assert contar(cx, "cargo", f"id = '{cargo_sin}'") == 0
    assert contar(cx, "transaccion_pasarela", f"id = '{venta_sin}'") == 0
    assert contar(cx, "pedido", f"id = '{con_dinero}'") == 1
    assert contar(cx, "cargo", f"id = '{cargo_con}'") == 1
    assert contar(cx, "transaccion_pasarela", f"cargo_id = '{cargo_con}'") == 2
    assert contar(cx, "pedido_linea", f"pedido_id = '{con_dinero}'") == 0
    assert contar(cx, "pedido_transicion", f"pedido_id = '{con_dinero}'") == 0
    assert contar(cx, "pedido", f"id = '{PED_A_ENVIADO}'") == 1  # lo pagado no se toca
    # Fuera de pedido_conservar, el registro contable sigue sin borrarse
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("DELETE FROM transaccion_pasarela WHERE cargo_id = %s", (cargo_con,))


def _pedido_viejo(cx):
    """Como superusuario: un pedido de otra persona de A con el total confirmado hace 40 días, con una línea."""
    persona = cx.execute("INSERT INTO persona_cuidada (grupo_id, nombre, nombre_pila, nivel_apoyo)"
                         " VALUES (%s, 'Eva Soto', 'Eva', 'apoyo_parcial') RETURNING id", (G_A,)).fetchone()[0]
    pedido, confirmado_en = cx.execute(
        "INSERT INTO pedido (grupo_id, persona_cuidada_id, estado, subtotal_productos, costo_envio, total,"
        " total_confirmado_en, total_vence_en, creado_por) VALUES (%s, %s, 'total_confirmado', 12990, 2990, 15980,"
        " now() - interval '40 days', now() - interval '40 days' + interval '15 minutes', %s)"
        " RETURNING id, total_confirmado_en", (G_A, persona, U_ADMIN_A)).fetchone()
    cx.execute("INSERT INTO pedido_linea (pedido_id, oferta_id, producto_id, cantidad, precio_unitario)"
               " VALUES (%s, %s, %s, 1, 12990)", (pedido, OFERTA, PRODUCTO))
    return pedido, confirmado_en


def _conservar_a_40_dias(cx, *pedidos):
    cx.execute("SET LOCAL session_replication_role = replica")
    cx.execute("UPDATE pedido SET actualizado_en = now() - interval '40 days' WHERE id = ANY(%s)", (list(pedidos),))
    cx.execute("SET LOCAL session_replication_role = origin")
    como(cx, "matu_scheduler", rol="operacion")
    cx.execute("SELECT * FROM pedido_conservar(now() - interval '30 days', now())")
    cx.execute("RESET ROLE")


@pytest.mark.rf("RF-25")
def test_pedido_conservar_cancela_el_pedido_abierto_con_dinero_que_queda_sin_lineas(cx):
    """Observación 5 del cierre del analista: un pago tardío anulado de un pedido que siguió abierto (total confirmado)
    deja, a los 30 días, el pedido sin líneas: pasa a cancelado y no queda como el pedido sin pagar de la persona."""
    pedido, confirmado_en = _pedido_viejo(cx)
    cargo, participacion, venta = _venta(cx, pedido, confirmado_en)
    cx.execute("UPDATE transaccion_pasarela SET estado = 'aprobada', anulacion_total = true WHERE id = %s", (venta,))
    cx.execute("INSERT INTO transaccion_pasarela (participacion_id, cargo_id, proveedor, tipo, buy_order, monto,"
               " estado, idempotency_key, venta_id, motivo_anulacion) VALUES (%s, %s, 'webpay_plus', 'anulacion', %s,"
               " 15980, 'aprobada', %s, %s, 'pago_tardio')", (participacion, cargo, "y" * 26, "k-y", venta))

    _conservar_a_40_dias(cx, pedido)

    assert cx.execute("SELECT estado, pagado_en FROM pedido WHERE id = %s", (pedido,)).fetchone() == ("cancelado", None)
    assert contar(cx, "pedido_linea", f"pedido_id = '{pedido}'") == 0
    assert contar(cx, "transaccion_pasarela", f"cargo_id = '{cargo}'") == 2
    # Fuera de pedido_conservar, operación no cancela un pedido así
    pedido_2, _ = _pedido_viejo(cx)
    como(cx, rol="operacion")
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("UPDATE pedido SET estado = 'cancelado' WHERE id = %s", (pedido_2,))


@pytest.mark.rf("RF-25")
def test_una_venta_autorizando_cuenta_como_dinero_y_no_se_borra(cx):
    """Observación 6: el commit de una venta autorizando pudo cobrar; su pedido y su venta se conservan."""
    pedido, confirmado_en = _pedido_viejo(cx)
    cargo, _, venta = _venta(cx, pedido, confirmado_en, estado="autorizando")
    cx.execute("UPDATE pedido SET estado = 'cancelado' WHERE id = %s", (pedido,))

    _conservar_a_40_dias(cx, pedido)

    assert contar(cx, "pedido", f"id = '{pedido}'") == 1
    assert contar(cx, "transaccion_pasarela", f"id = '{venta}'") == 1
    assert contar(cx, "cargo", f"id = '{cargo}'") == 1


# ---- MATU-55 (migración 0025): cada persona lee solo la auditoría de su propia cuenta

DISP_CUENTA_A = uuid.UUID("00000000-0000-0000-0000-0000000055a1")
DISP_CUENTA_B = uuid.UUID("00000000-0000-0000-0000-0000000055b1")


def _sembrar_cuenta(cx):
    """Como superusuario, dentro de la transacción que se revierte: filas de la cuenta de A y de B, el código pedido y
    el fallido de A (actor sistema), un inicio fallido sin actor, y una fila del grupo de A."""
    for usuario, dispositivo in ((U_ADMIN_A, DISP_CUENTA_A), (U_ADMIN_B, DISP_CUENTA_B)):
        cx.execute("INSERT INTO dispositivo (id, usuario_id, plataforma, nombre) VALUES (%s, %s, 'web',"
                   " 'Chrome en Android')", (dispositivo, usuario))
        for accion in ("sesion.iniciar", "dispositivo.push_registrar", "cuenta.celular_solicitar"):
            cx.execute("INSERT INTO auditoria (actor_tipo, actor_ref, accion, entidad, entidad_id)"
                       " VALUES ('usuario', %s, %s, 'dispositivo', %s)", (usuario, accion, dispositivo))
        cx.execute("INSERT INTO auditoria (actor_tipo, actor_ref, accion, entidad, entidad_id)"
                   " VALUES ('usuario', %s, 'avisos.preferencia', 'usuario', %s)", (usuario, usuario))
    for accion in ("cuenta.recuperar_solicitar", "cuenta.recuperar_verificar_fallido"):
        cx.execute("INSERT INTO auditoria (actor_tipo, accion, entidad, entidad_id) VALUES ('sistema', %s, 'usuario',"
                   " %s)", (accion, U_ADMIN_A))
    cx.execute("INSERT INTO auditoria (actor_tipo, accion, entidad) VALUES ('sistema', 'sesion.inicio_fallido',"
               " 'usuario')")
    cx.execute("INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, persona_cuidada_id)"
               " VALUES (%s, 'usuario', %s, 'plan.leer', 'plan_cuidado', %s)", (G_A, U_ADMIN_A, P_A))


def _cuenta_visible(cx):
    return sorted(cx.execute(
        "SELECT accion, coalesce(actor_ref, entidad_id) FROM auditoria WHERE grupo_id IS NULL").fetchall())


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize("grupo", [None, G_A, G_B])
def test_cada_persona_lee_solo_la_auditoria_de_su_cuenta(cx, grupo):
    """A ve sus filas de la cuenta, con o sin un grupo en el contexto, y nunca las de B; ve el código de recuperación
    pedido (actor sistema) y no el código fallido; nadie ve el inicio fallido (decisión 257)."""
    _sembrar_cuenta(cx)
    como(cx, usuario_id=U_ADMIN_A, grupo_id=grupo)
    assert _cuenta_visible(cx) == sorted([
        ("avisos.preferencia", U_ADMIN_A),
        ("cuenta.celular_solicitar", U_ADMIN_A),
        ("cuenta.recuperar_solicitar", U_ADMIN_A),
        ("dispositivo.push_registrar", U_ADMIN_A),
        ("sesion.iniciar", U_ADMIN_A),
    ])
    como(cx, usuario_id=U_ADMIN_B, grupo_id=grupo)
    assert {r[1] for r in _cuenta_visible(cx)} == {U_ADMIN_B}


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize("contexto", [
    {"usuario_id": U_NUEVO},                              # otra persona, sin filas propias
    {"rol": "relevo", "acceso_relevo_id": ACC_VIGENTE},  # el relevo
    {"rol": "sistema"},                                  # el sistema, sin cuenta
    {"rol": "operacion"},                                # operación
    {},                                                  # sin contexto
])
def test_nadie_mas_lee_la_auditoria_de_una_cuenta(cx, contexto):
    _sembrar_cuenta(cx)
    como(cx, **contexto)
    assert _cuenta_visible(cx) == []


@pytest.mark.rf("RF-37")
def test_la_auditoria_de_la_cuenta_no_abre_la_del_grupo(cx):
    """Las lecturas del grupo y las aperturas del relevo siguen como en la 0005 y la 0010: la fila del grupo de A la ve
    su admin con el grupo en el contexto, y no sin él."""
    _sembrar_cuenta(cx)
    como(cx, usuario_id=U_ADMIN_A)
    assert contar(cx, "auditoria", "grupo_id IS NOT NULL") == 0
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    assert contar(cx, "auditoria", "grupo_id IS NOT NULL") == 1
    como(cx, usuario_id=U_ADMIN_B, grupo_id=G_A)
    assert contar(cx, "auditoria", "grupo_id IS NOT NULL") == 0


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize(("accion", "acepta"), [
    ("sesion.iniciar", True),
    ("avisos.preferencia", True),
    ("plan.leer", False),
    ("consumo.editar", False),
    ("pago.aprobar", False),
])
def test_una_fila_sin_grupo_es_siempre_de_la_cuenta(cx, accion, acepta):
    """CHECK auditoria_cuenta_acotada (decisión 258), también para el superusuario."""
    insertar = "INSERT INTO auditoria (actor_tipo, actor_ref, accion, entidad) VALUES ('usuario', %s, %s, 'usuario')"
    if acepta:
        cx.execute(insertar, (U_ADMIN_A, accion))
    else:
        with pytest.raises(errors.CheckViolation):
            cx.execute(insertar, (U_ADMIN_A, accion))


@pytest.mark.rf("RF-37")
def test_la_auditoria_ya_no_tiene_ip(cx):
    """Decisión 266 (D7)."""
    assert contar(cx, "information_schema.columns", "table_name = 'auditoria' AND column_name = 'ip'") == 0


# ------------------------------------------------------------------ MATU-42: invitaciones y miembros (0026)

INV_42 = uuid.UUID("00000000-0000-0000-0000-0000000042e1")
TOKEN_42 = b"t" * 32
CODIGO_42 = b"c" * 32


def _invitacion(cx, grupo=G_A, invitado_por=U_ADMIN_A, invitacion_id=INV_42, token=TOKEN_42, rol="cuidador"):
    """Una invitación con su indice_token, como superusuario. token_hash y codigo_hash son 32 bytes fijos."""
    cx.execute(
        "INSERT INTO invitacion (id, grupo_id, rol, token_hash, codigo_hash, invitado_por, nombre_pila_invita,"
        " creada_en, expira_en) VALUES (%s, %s, %s, %s, %s, %s, 'Admin', now(), now() + interval '1 day')",
        (invitacion_id, grupo, rol, token, CODIGO_42, invitado_por))
    cx.execute(
        "INSERT INTO indice_token (token_hash, tipo, grupo_id, referencia_id, expira_en)"
        " VALUES (%s, 'invitacion', %s, %s, now() + interval '1 day')", (token, grupo, invitacion_id))


def _membresia_id(cx, usuario, grupo=G_A):
    return cx.execute("SELECT id FROM membresia WHERE usuario_id = %s AND grupo_id = %s AND estado <> 'retirada'",
                      (usuario, grupo)).fetchone()[0]


@pytest.mark.rf("RF-38")
@pytest.mark.parametrize("usuario", [U_OBS_A, U_PAG_A])
def test_quien_no_administra_no_cambia_membresias_ni_se_sube_a_admin(cx, usuario):
    propia, otra = _membresia_id(cx, usuario), _membresia_id(cx, U_PAG2_A)
    como(cx, usuario_id=usuario, grupo_id=G_A)
    assert cx.execute("UPDATE membresia SET rol = 'admin' WHERE id = %s RETURNING id", (propia,)).fetchall() == []
    assert cx.execute("UPDATE membresia SET puede_ver_plan = false WHERE id = %s RETURNING id", (otra,)
                      ).fetchall() == []
    # membresia_retirar sobre otra persona sin ser admin: no hace nada
    assert cx.execute("SELECT membresia_retirar(%s, now())", (otra,)).fetchone() == (None,)


@pytest.mark.rf("RF-38")
def test_membresia_retirar_solo_la_propia_o_siendo_admin_del_grupo(cx):
    otra, de_a = _membresia_id(cx, U_PAG2_A), _membresia_id(cx, U_OBS_A)
    como(cx, usuario_id=U_ADMIN_B, grupo_id=G_B)
    assert cx.execute("SELECT membresia_retirar(%s, now())", (de_a,)).fetchone() == (None,)
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    assert cx.execute("SELECT membresia_retirar(%s, now())", (otra,)).fetchone() == ("pagador",)
    como(cx, usuario_id=U_OBS_A, grupo_id=G_A)
    assert cx.execute("SELECT membresia_retirar(%s, now())", (de_a,)).fetchone() == ("observador",)


@pytest.mark.rf("RF-38")
def test_nadie_borra_membresias(cx):
    otra = _membresia_id(cx, U_PAG2_A)
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("DELETE FROM membresia WHERE id = %s", (otra,))


@pytest.mark.rf("RF-38")
def test_el_admin_no_retira_con_un_update_de_estado(cx):
    otra = _membresia_id(cx, U_PAG2_A)
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("UPDATE membresia SET estado = 'retirada' WHERE id = %s", (otra,))


@pytest.mark.rf("RF-38")
def test_el_admin_cambia_roles_y_el_ultimo_admin_no_se_degrada(cx):
    pagador, propia = _membresia_id(cx, U_PAG_A), _membresia_id(cx, U_ADMIN_A)
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    assert cx.execute("UPDATE membresia SET rol = 'cuidador', version = version + 1 WHERE id = %s RETURNING rol",
                      (pagador,)).fetchall() == [("cuidador",)]
    with pytest.raises(errors.CheckViolation) as error:
        cx.execute("UPDATE membresia SET rol = 'cuidador' WHERE id = %s", (propia,))
    assert error.value.diag.constraint_name == "membresia_ultimo_admin"


@pytest.mark.rf("RF-38")
def test_el_ultimo_admin_tampoco_se_retira_como_superusuario(cx):
    propia = _membresia_id(cx, U_ADMIN_A)
    with pytest.raises(errors.CheckViolation):
        cx.execute("UPDATE membresia SET estado = 'retirada' WHERE id = %s", (propia,))


@pytest.mark.rf("RF-38")
def test_quien_salio_no_ve_a_sus_excompaneros(cx):
    cx.execute("UPDATE membresia SET estado = 'retirada' WHERE usuario_id = %s AND grupo_id = %s", (U_OBS_A, G_A))
    # sesion_de_grupo ya no le fija el grupo (no es miembro activo): solo ve su propia membresía y su propia cuenta
    como(cx, usuario_id=U_OBS_A)
    assert [r[0] for r in cx.execute("SELECT usuario_id FROM membresia").fetchall()] == [U_OBS_A]
    assert [r[0] for r in cx.execute("SELECT id FROM usuario").fetchall()] == [U_OBS_A]
    assert contar(cx, "grupo_familiar") == 0
    # Quien sigue no ve su nombre ni su membresía retirada
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    assert contar(cx, "usuario", f"id = '{U_OBS_A}'") == 0
    assert contar(cx, "membresia", f"usuario_id = '{U_OBS_A}'") == 0


@pytest.mark.rf("RF-38")
def test_solo_admin_lee_y_anula_invitaciones_y_b_no_ve_las_de_a(cx):
    _invitacion(cx)
    como(cx, usuario_id=U_PAG2_A, grupo_id=G_A)
    assert contar(cx, "invitacion") == 0
    assert cx.execute("UPDATE invitacion SET revocada_en = now() WHERE id = %s RETURNING id", (INV_42,)
                      ).fetchall() == []
    como(cx, usuario_id=U_ADMIN_B, grupo_id=G_B)
    assert contar(cx, "invitacion") == 0
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    assert contar(cx, "invitacion") == 1
    assert cx.execute("UPDATE invitacion SET revocada_en = now() WHERE id = %s RETURNING id", (INV_42,)
                      ).fetchall() == [(INV_42,)]


@pytest.mark.rf("RF-38")
def test_quien_no_administra_no_crea_invitaciones(cx):
    como(cx, usuario_id=U_PAG2_A, grupo_id=G_A)
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute(
            "INSERT INTO invitacion (grupo_id, rol, token_hash, codigo_hash, invitado_por, nombre_pila_invita,"
            " expira_en) VALUES (%s, 'admin', %s, %s, %s, 'Pag2', now() + interval '1 day')",
            (G_A, b"u" * 32, CODIGO_42, U_PAG2_A))


@pytest.mark.rf("RF-38")
def test_lo_que_define_una_invitacion_no_lo_cambia_la_app(cx):
    _invitacion(cx)
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("UPDATE invitacion SET rol = 'admin' WHERE id = %s", (INV_42,))


@pytest.mark.rf("RF-38")
def test_una_anulada_no_se_reabre(cx):
    _invitacion(cx)
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    cx.execute("UPDATE invitacion SET revocada_en = now() WHERE id = %s", (INV_42,))
    with pytest.raises(errors.CheckViolation):
        cx.execute("UPDATE invitacion SET revocada_en = now() + interval '1 hour' WHERE id = %s", (INV_42,))


@pytest.mark.rf("RF-38")
def test_matu_app_no_borra_invitaciones(cx):
    _invitacion(cx)
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("DELETE FROM invitacion WHERE id = %s", (INV_42,))


@pytest.mark.rf("RF-38")
def test_las_funciones_de_la_invitacion_no_admiten_grupo_en_el_contexto(cx):
    _invitacion(cx)
    como(cx, usuario_id=U_NUEVO, grupo_id=G_A)
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("SELECT * FROM invitacion_presentar(%s, now())", (TOKEN_42,))


@pytest.mark.rf("RF-38")
def test_la_aceptacion_exige_una_cuenta(cx):
    _invitacion(cx)
    como(cx)
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("SELECT * FROM invitacion_aceptar(%s, %s, now(), NULL)", (TOKEN_42, CODIGO_42))


@pytest.mark.rf("RF-38")
def test_matu_app_no_corre_la_conservacion_de_invitaciones(cx):
    como(cx, rol="operacion")
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("SELECT invitacion_conservar(now() - interval '30 days', now())")


@pytest.mark.rf("RF-38")
def test_el_codigo_cuenta_intentos_y_bloquea(cx):
    _invitacion(cx)
    como(cx)
    presentacion = cx.execute("SELECT resultado, nombre_pila_invita, rol FROM invitacion_presentar(%s, now())",
                              (TOKEN_42,)).fetchone()
    assert presentacion == ("ok", "Admin", "cuidador")
    # Sin contexto no ve la invitación ni el grupo por su cuenta: solo lo que devuelve la función
    assert contar(cx, "invitacion") == 0 and contar(cx, "grupo_familiar") == 0
    resultados = [cx.execute("SELECT resultado, intentos_restantes FROM invitacion_verificar(%s, %s, now(), NULL)",
                             (TOKEN_42, b"x" * 32)).fetchone() for _ in range(5)]
    assert resultados == [("codigo_incorrecto", 4), ("codigo_incorrecto", 3), ("codigo_incorrecto", 2),
                          ("codigo_incorrecto", 1), ("bloqueada", None)]
    assert cx.execute("SELECT resultado FROM invitacion_verificar(%s, %s, now(), NULL)", (TOKEN_42, CODIGO_42)
                      ).fetchone() == ("bloqueada",)
    # El marcador de las políticas TO matu_owner no queda puesto
    assert cx.execute("SELECT coalesce(current_setting('app.funcion', true), '')").fetchone() == ("",)


@pytest.mark.rf("RF-38")
def test_aceptar_une_una_sola_vez(cx):
    _invitacion(cx)
    como(cx, usuario_id=U_NUEVO)
    fila = cx.execute("SELECT resultado, grupo_id, rol FROM invitacion_aceptar(%s, %s, now(), NULL)",
                      (TOKEN_42, CODIGO_42)).fetchone()
    assert fila == ("ok", G_A, "cuidador")
    assert cx.execute("SELECT resultado, grupo_id FROM invitacion_aceptar(%s, %s, now(), NULL)",
                      (TOKEN_42, CODIGO_42)).fetchone() == ("ya_eres_parte", G_A)
    como(cx, usuario_id=U_ADMIN_B)
    assert cx.execute("SELECT resultado FROM invitacion_aceptar(%s, %s, now(), NULL)", (TOKEN_42, CODIGO_42)
                      ).fetchone() == ("usada",)
    cx.execute("RESET ROLE")
    assert cx.execute("SELECT rol, estado, puede_ver_plan, invitado_por FROM membresia WHERE usuario_id = %s",
                      (U_NUEVO,)).fetchall() == [("cuidador", "activa", False, U_ADMIN_A)]
    assert cx.execute("SELECT accion, detalle FROM auditoria WHERE entidad_id = %s", (INV_42,)).fetchall() == [
        ("invitacion.aceptar", {"rol": "cuidador"})]


@pytest.mark.rf("RF-38")
def test_volver_a_invitar_a_quien_salio_crea_otra_membresia(cx):
    cx.execute("UPDATE membresia SET estado = 'retirada' WHERE usuario_id = %s AND grupo_id = %s", (U_OBS_A, G_A))
    cx.execute("INSERT INTO membresia (grupo_id, usuario_id, rol) VALUES (%s, %s, 'cuidador')", (G_A, U_OBS_A))
    assert contar(cx, "membresia", f"usuario_id = '{U_OBS_A}' AND grupo_id = '{G_A}'") == 2
    with pytest.raises(errors.UniqueViolation):
        cx.execute("INSERT INTO membresia (grupo_id, usuario_id, rol) VALUES (%s, %s, 'cuidador')", (G_A, U_OBS_A))


@pytest.mark.rf("RF-38")
@pytest.mark.parametrize("usuario", [U_OBS_A, U_PAG2_A])
def test_solo_admin_y_cuidador_escriben_la_direccion(cx, usuario):
    como(cx, usuario_id=usuario, grupo_id=G_A)
    assert contar(cx, "direccion") == 1
    assert cx.execute("UPDATE direccion SET calle = 'Otra' RETURNING id").fetchall() == []
    assert cx.execute("DELETE FROM direccion RETURNING id").fetchall() == []


@pytest.mark.rf("RF-38")
def test_quien_no_escribe_la_direccion_no_la_crea(cx):
    como(cx, usuario_id=U_OBS_A, grupo_id=G_A)
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("INSERT INTO direccion (grupo_id, calle, numero, comuna) VALUES (%s, 'X', '1', 'Y')", (G_A,))


@pytest.mark.rf("RF-38")
def test_el_admin_escribe_la_direccion_y_b_no_ve_la_de_a(cx):
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    assert len(cx.execute("UPDATE direccion SET referencia = 'Portón verde' RETURNING id").fetchall()) == 1
    como(cx, usuario_id=U_ADMIN_B, grupo_id=G_B)
    assert contar(cx, "direccion") == 0


@pytest.mark.rf("RF-38")
@pytest.mark.parametrize("usuario", [U_OBS_A, U_PAG_A])
def test_solo_admin_cambia_el_nombre_del_grupo(cx, usuario):
    como(cx, usuario_id=usuario, grupo_id=G_A)
    assert cx.execute("UPDATE grupo_familiar SET nombre = 'Otro' RETURNING id").fetchall() == []
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    assert cx.execute("UPDATE grupo_familiar SET nombre = 'Familia A' RETURNING id").fetchall() == [(G_A,)]


@pytest.mark.rf("RF-38")
def test_nadie_borra_el_grupo(cx):
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("DELETE FROM grupo_familiar WHERE id = %s", (G_A,))


@pytest.mark.rf("RF-38")
@pytest.mark.parametrize(("detalle", "acepta"), [
    ('{"rol": "pagador"}', True),
    ('{"rol": "jefe"}', False),
    ('{"rol": 1}', False),
    ('{"rol": "admin", "email": "x@y.cl"}', False),
])
def test_la_auditoria_solo_admite_un_rol_de_la_lista(cx, detalle, acepta):
    insertar = ("INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, detalle)"
                " VALUES (%s, 'usuario', %s, 'membresia.cambiar_rol', 'membresia', %s::jsonb)")
    if acepta:
        cx.execute(insertar, (G_A, U_ADMIN_A, detalle))
    else:
        with pytest.raises(errors.CheckViolation):
            cx.execute(insertar, (G_A, U_ADMIN_A, detalle))


# --- MATU-42: dos a la vez, con datos confirmados en un grupo propio que se borra al final

G_42 = uuid.UUID("00000000-0000-0000-0000-00000000042c")
U_42 = tuple(uuid.UUID(f"00000000-0000-0000-0000-00000000042{i}") for i in "abcd")
TOKEN_G_42 = b"z" * 32


@pytest.fixture
def grupo_42():
    with psycopg.connect(DSN, autocommit=True) as c:
        for i, usuario in enumerate(U_42):
            c.execute("INSERT INTO usuario (id, email, nombre, password_hash) VALUES (%s, %s, 'Sintética', 'h')",
                      (usuario, f"u42.{i}@x.cl"))
        c.execute("INSERT INTO grupo_familiar (id, nombre, creado_por) VALUES (%s, 'Familia 42', %s)", (G_42, U_42[0]))
        c.execute("INSERT INTO membresia (grupo_id, usuario_id, rol) VALUES (%s, %s, 'admin'), (%s, %s, 'admin')",
                  (G_42, U_42[0], G_42, U_42[1]))
        _invitacion(c, grupo=G_42, invitado_por=U_42[0], invitacion_id=uuid.UUID(int=42), token=TOKEN_G_42)
    try:
        yield
    finally:
        with psycopg.connect(DSN, autocommit=True) as c:
            c.execute("SET session_replication_role = replica")
            c.execute("DELETE FROM indice_token WHERE grupo_id = %s", (G_42,))
            c.execute("DELETE FROM invitacion WHERE grupo_id = %s", (G_42,))
            c.execute("DELETE FROM membresia WHERE grupo_id = %s", (G_42,))
            c.execute("DELETE FROM auditoria WHERE grupo_id = %s", (G_42,))
            c.execute("DELETE FROM grupo_familiar WHERE id = %s", (G_42,))
            c.execute("DELETE FROM usuario WHERE id = ANY(%s)", (list(U_42),))


def _en_paralelo(primera, segunda):
    """primera en una conexión que confirma solo después de que segunda empezó y quedó esperando su bloqueo."""
    import threading
    import time

    resultados: dict[str, object] = {}
    with psycopg.connect(DSN) as uno, psycopg.connect(DSN) as dos:
        resultados["primera"] = primera(uno)

        def correr():
            try:
                resultados["segunda"] = segunda(dos)
                dos.commit()
            except psycopg.Error as error:
                resultados["segunda"] = error
                dos.rollback()

        hilo = threading.Thread(target=correr)
        hilo.start()
        time.sleep(0.5)
        assert "segunda" not in resultados, "la segunda no esperó el bloqueo"
        uno.commit()
        hilo.join(timeout=10)
    return resultados


@pytest.mark.rf("RF-38")
def test_dos_degradaciones_a_la_vez_dejan_un_admin(grupo_42):
    def degradar(usuario):
        def paso(c):
            como(c, usuario_id=usuario, grupo_id=G_42)
            return c.execute("UPDATE membresia SET rol = 'cuidador' WHERE usuario_id = %s AND grupo_id = %s"
                             " RETURNING rol", (usuario, G_42)).fetchall()
        return paso

    resultados = _en_paralelo(degradar(U_42[0]), degradar(U_42[1]))
    assert resultados["primera"] == [("cuidador",)]
    assert isinstance(resultados["segunda"], errors.CheckViolation)
    with psycopg.connect(DSN) as c:
        assert c.execute("SELECT count(*) FROM membresia WHERE grupo_id = %s AND rol = 'admin'", (G_42,)
                         ).fetchone() == (1,)


@pytest.mark.rf("RF-38")
def test_dos_aceptaciones_a_la_vez_unen_a_una_sola_persona(grupo_42):
    def aceptar(usuario):
        def paso(c):
            como(c, usuario_id=usuario)
            return c.execute("SELECT resultado FROM invitacion_aceptar(%s, %s, now(), NULL)", (TOKEN_G_42, CODIGO_42)
                             ).fetchone()
        return paso

    resultados = _en_paralelo(aceptar(U_42[2]), aceptar(U_42[3]))
    assert resultados == {"primera": ("ok",), "segunda": ("usada",)}
    with psycopg.connect(DSN) as c:
        assert c.execute("SELECT usuario_id FROM membresia WHERE grupo_id = %s AND rol = 'cuidador'", (G_42,)
                         ).fetchall() == [(U_42[2],)]


# --- MATU-42, cierre del analista: O1 (el instante, decisión 340) y O2 (el marcador app.funcion, decisión 341)

@pytest.mark.rf("RF-38")
@pytest.mark.parametrize("corrido", ["now() - interval '1 day'", "now() - interval '6 minutes'",
                                     "now() + interval '6 minutes'"])
def test_las_funciones_de_la_0026_exigen_el_instante_actual(cx, corrido):
    """O1: con un ahora del pasado se podría aceptar una invitación vencida o fechar retirado_en hacia atrás."""
    _invitacion(cx)
    otra = _membresia_id(cx, U_PAG2_A)
    llamadas = [
        (dict(), f"SELECT * FROM invitacion_presentar(%s, {corrido})", (TOKEN_42,)),
        (dict(), f"SELECT * FROM invitacion_verificar(%s, %s, {corrido}, NULL)", (TOKEN_42, CODIGO_42)),
        (dict(usuario_id=U_NUEVO), f"SELECT * FROM invitacion_aceptar(%s, %s, {corrido}, NULL)", (TOKEN_42, CODIGO_42)),
        (dict(usuario_id=U_ADMIN_A, grupo_id=G_A), f"SELECT membresia_retirar(%s, {corrido})", (otra,)),
    ]
    for contexto, sql, parametros in llamadas:
        cx.execute("SAVEPOINT antes")
        como(cx, **contexto)
        with pytest.raises(errors.InvalidParameterValue):
            cx.execute(sql, parametros)
        cx.execute("ROLLBACK TO SAVEPOINT antes")


@pytest.mark.rf("RF-38")
def test_una_invitacion_vencida_no_se_acepta_con_un_instante_del_pasado(cx):
    """O1: la invitación venció hace una hora; un ahora de hace dos días la haría pasar por vigente."""
    _invitacion(cx)
    cx.execute("SET LOCAL session_replication_role = replica")
    cx.execute("UPDATE invitacion SET creada_en = now() - interval '3 days', expira_en = now() - interval '1 hour'"
               " WHERE id = %s", (INV_42,))
    cx.execute("SET LOCAL session_replication_role = origin")
    cx.execute("SAVEPOINT antes")
    como(cx, usuario_id=U_NUEVO)
    with pytest.raises(errors.InvalidParameterValue):
        cx.execute("SELECT * FROM invitacion_aceptar(%s, %s, now() - interval '2 days', NULL)", (TOKEN_42, CODIGO_42))
    cx.execute("ROLLBACK TO SAVEPOINT antes")
    como(cx, usuario_id=U_NUEVO)
    assert cx.execute("SELECT resultado FROM invitacion_aceptar(%s, %s, now(), NULL)", (TOKEN_42, CODIGO_42)
                      ).fetchone() == ("vencida",)


MARCAS_0026 = ("invitacion", "membresia_retirar")
# MATU-63 (0029): las marcas de las funciones del comercio, del apartado, del despacho y de las cuentas
MARCAS_0029 = ("comercio", "disponible", "despacho", "cuentas", "codigo_retiro")


def _lo_que_ve(cx, usuario_id=None, grupo_id=None):
    como(cx, usuario_id=usuario_id, grupo_id=grupo_id)
    return {tabla: contar(cx, tabla) for tabla in
            ("invitacion", "membresia", "grupo_familiar", "persona_cuidada", "auditoria", "usuario")}


@pytest.mark.rf("RF-38")
@pytest.mark.parametrize("marca", MARCAS_0026 + MARCAS_0029)
@pytest.mark.parametrize("contexto", [{}, {"usuario_id": U_NUEVO}, {"usuario_id": U_OBS_A, "grupo_id": G_A}])
def test_matu_app_no_gana_nada_fijando_el_marcador(cx, marca, contexto):
    """O2: las políticas del marcador son TO matu_owner. matu_app que fija app.funcion no ve ni escribe más."""
    _invitacion(cx)
    sin_marca = _lo_que_ve(cx, **contexto)
    cx.execute("SELECT set_config('app.funcion', %s, true)", (marca,))
    assert {tabla: contar(cx, tabla) for tabla in sin_marca} == sin_marca
    assert cx.execute("UPDATE invitacion SET revocada_en = now() WHERE id = %s RETURNING id", (INV_42,)
                      ).fetchall() == []
    assert cx.execute("UPDATE membresia SET rol = 'admin' WHERE grupo_id = %s RETURNING id", (G_A,)).fetchall() == []
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("INSERT INTO membresia (grupo_id, usuario_id, rol) VALUES (%s, %s, 'admin')", (G_A, U_NUEVO))


@pytest.mark.rf("RF-38")
@pytest.mark.parametrize("marca", MARCAS_0026 + MARCAS_0029)
def test_el_marcador_puesto_por_matu_app_no_abre_las_otras_funciones_definer(cx, marca):
    """O2: con el marcador puesto, las funciones SECURITY DEFINER que matu_app ejecuta devuelven lo mismo, y las de la
    0026 lo pisan con el suyo y lo limpian al salir."""
    _invitacion(cx)
    otra = _membresia_id(cx, U_PAG2_A)
    consultas = [
        ({"rol": "relevo", "acceso_relevo_id": ACC_VIGENTE}, "SELECT relevo_autorizacion_vigente(now())", ()),
        ({"usuario_id": U_OBS_A}, "SELECT * FROM iam_credencial(%s)", (U_OBS_A,)),
        ({"rol": "sistema"}, "SELECT * FROM pago_resolver_venta(NULL, 'MATU-0001', 'x')", ()),
        ({}, "SELECT resultado, nombre_pila_invita FROM invitacion_presentar(%s, now())", (TOKEN_42,)),
        # Un observador no retira a otra persona aunque traiga la marca de membresia_retirar
        ({"usuario_id": U_OBS_A, "grupo_id": G_A}, "SELECT membresia_retirar(%s, now())", (otra,)),
    ]
    for contexto, sql, parametros in consultas:
        como(cx, **contexto)
        esperado = cx.execute(sql, parametros).fetchall()
        cx.execute("SELECT set_config('app.funcion', %s, true)", (marca,))
        assert cx.execute(sql, parametros).fetchall() == esperado, sql
    assert cx.execute("SELECT membresia_retirar(%s, now())", (otra,)).fetchone() == (None,)
    assert cx.execute("SELECT coalesce(current_setting('app.funcion', true), '')").fetchone() == ("",)


@pytest.mark.rf("RF-38")
def test_las_politicas_del_marcador_son_solo_de_matu_owner_y_las_definer_de_matu_app_estan_revisadas(cx):
    """O2, por catálogo: toda política que mira app.funcion es TO matu_owner, y una función SECURITY DEFINER nueva que
    matu_app pueda ejecutar hace fallar esta prueba hasta revisar que no lea esas tablas con el marcador puesto."""
    politicas = cx.execute("SELECT policyname, roles::text FROM pg_policies"
                           " WHERE coalesce(qual, '') || coalesce(with_check, '') LIKE '%app.funcion%'").fetchall()
    assert politicas and {roles for _, roles in politicas} == {"{matu_owner}"}
    ejecuta = {f for (f,) in cx.execute(
        "SELECT proname FROM pg_proc WHERE pronamespace = 'public'::regnamespace AND prosecdef"
        " AND has_function_privilege('matu_app', oid, 'EXECUTE')").fetchall()}
    assert ejecuta == {"relevo_autorizacion_vigente", "iam_credencial", "pago_resolver_venta", "membresia_retirar",
                       "invitacion_presentar", "invitacion_verificar", "invitacion_aceptar",
                       # MATU-63 (0029): cada una pisa el marcador con el suyo y lo limpia al salir
                       "comercio_partes", "comercio_lineas", "comercio_preparar", "comercio_marcar_linea",
                       "comercio_listo", "comercio_validar_codigo", "comercio_existencias", "oferta_disponible",
                       "despacho_resolver_parte"}


# ------------------------------------------------------------------ MATU-46 (migración 0027): el teléfono del relevo

ACC_B_46 = uuid.UUID("00000000-0000-0000-0000-0000000046b1")
TELEFONOS_SEMILLA = {ACC_VIGENTE: "+56911111111", ACC_VENCIDO: "+56922222222", ACC_REVOCADO: "+56933333333"}


def _acceso_b_vencido_hace_40_dias(cx):
    cx.execute("INSERT INTO acceso_relevo (id, grupo_id, plan_id, otorgado_por, otorgado_a_nombre, otorgado_a_telefono,"
               " nombre_pila_persona, nombre_pila_comparte, secciones_permitidas, motivo, token_hash, pin_hash,"
               " creado_en, expira_en, relevo_informado_en) VALUES (%s, %s, %s, %s, 'Relevo B', '+56944444444',"
               " 'Luis', 'Admin', ARRAY['rutina'], 'otro', sha256('t46'), 'p', now() - interval '41 days',"
               " now() - interval '40 days', now())", (ACC_B_46, G_B, PLAN_B, U_ADMIN_B))


@pytest.mark.rf("RF-05")
def test_relevo_conservar_vacia_solo_lo_terminado_hace_30_dias_y_solo_el_telefono(cx):
    """C11: de los cuatro accesos (tres de A, uno de B), solo el de B terminó hace 30 días. Se vacía su teléfono, y su
    nombre y su motivo se quedan."""
    _acceso_b_vencido_hace_40_dias(cx)
    como(cx, "matu_scheduler", rol="operacion")
    assert cx.execute("SELECT relevo_conservar(now() - interval '30 days', now())").fetchone() == (1,)
    # El scheduler no lee la tabla: solo ejecuta la función
    with pytest.raises(errors.InsufficientPrivilege), cx.transaction():
        cx.execute("SELECT count(*) FROM acceso_relevo")
    cx.execute("RESET ROLE")
    telefonos = dict(cx.execute("SELECT id, otorgado_a_telefono FROM acceso_relevo").fetchall())
    assert telefonos == {**TELEFONOS_SEMILLA, ACC_B_46: None}
    assert cx.execute("SELECT otorgado_a_nombre, motivo, telefono_borrado_en IS NOT NULL FROM acceso_relevo"
                      " WHERE id = %s", (ACC_B_46,)).fetchone() == ("Relevo B", "otro", True)


@pytest.mark.rf("RF-05")
def test_relevo_conservar_no_abre_lecturas_a_matu_app(cx):
    """C10: las políticas de la tarea son TO matu_owner. matu_app con operación sigue sin ver ningún acceso, y con el
    contexto de B no ve los de A."""
    _acceso_b_vencido_hace_40_dias(cx)
    como(cx, rol="operacion")
    assert contar(cx, "acceso_relevo") == 0
    como(cx, usuario_id=U_ADMIN_B, grupo_id=G_B)
    assert {r[0] for r in cx.execute("SELECT id FROM acceso_relevo").fetchall()} == {ACC_B_46}


@pytest.mark.rf("RF-05")
@pytest.mark.parametrize(("limite", "ahora"), [
    ("now() - interval '30 days'", "now() + interval '1 hour'"),   # ahora en el futuro
    ("now() - interval '29 days'", "now()"),                       # límite reciente
    ("NULL", "now()"),
    ("now() - interval '30 days'", "NULL"),
])
def test_relevo_conservar_rechaza_un_ahora_futuro_o_un_limite_reciente(cx, limite, ahora):
    como(cx, "matu_scheduler", rol="operacion")
    with pytest.raises(errors.InvalidParameterValue):
        cx.execute(f"SELECT relevo_conservar(({limite})::timestamptz, ({ahora})::timestamptz)")


@pytest.mark.rf("RF-05")
def test_nadie_devuelve_ni_cambia_un_telefono_borrado_tampoco_el_superusuario(cx):
    """El trigger acceso_relevo_telefono vale para todos los roles: un teléfono solo se vacía, una vez."""
    cx.execute("UPDATE acceso_relevo SET otorgado_a_telefono = NULL, telefono_borrado_en = now() WHERE id = %s",
               (ACC_VENCIDO,))
    for cambio in ("otorgado_a_telefono = '+56922222222', telefono_borrado_en = NULL",
                   "telefono_borrado_en = now() + interval '1 day'"):
        with pytest.raises(errors.CheckViolation), cx.transaction():
            cx.execute(f"UPDATE acceso_relevo SET {cambio} WHERE id = %s", (ACC_VENCIDO,))
    # Ni vaciarlo sin dejar el instante, ni fijar el instante con el teléfono puesto (CHECK de la 0027)
    for cambio in ("otorgado_a_telefono = NULL", "telefono_borrado_en = now()"):
        with pytest.raises(errors.CheckViolation), cx.transaction():
            cx.execute(f"UPDATE acceso_relevo SET {cambio} WHERE id = %s", (ACC_VIGENTE,))


@pytest.mark.rf("RF-05")
def test_matu_app_vacia_el_telefono_solo_como_admin_o_cuidador(sesiones_app):
    """D-46-3 a): el borrado de la persona lo vacía como matu_app. El pagador con permiso, el observador y otro grupo
    no alcanzan ninguna fila."""
    from sqlalchemy import text

    from app.core.db import sesion_tenant

    vaciar = text("UPDATE acceso_relevo SET otorgado_a_telefono = NULL, telefono_borrado_en = now() WHERE id = :id")
    for usuario, grupo in ((U_PAG2_A, G_A), (U_OBS_A, G_A), (U_ADMIN_B, G_B)):
        with pytest.raises(_Deshacer), sesion_tenant(sesiones_app, usuario_id=usuario, grupo_id=grupo) as s:
            assert s.execute(vaciar, {"id": ACC_VIGENTE}).rowcount == 0, usuario  # type: ignore[attr-defined]
            raise _Deshacer
    with pytest.raises(_Deshacer), sesion_tenant(sesiones_app, usuario_id=U_ADMIN_A, grupo_id=G_A) as s:
        assert s.execute(vaciar, {"id": ACC_VIGENTE}).rowcount == 1  # type: ignore[attr-defined]
        raise _Deshacer


# ---- MATU-54 (migración 0028): la persona de cada fila de auditoría y la copia de los datos


def _sembrar_copias(cx):
    """Como superusuario, en la transacción que se revierte: una copia pedida por cada admin, de su persona."""
    for grupo, actor, persona in ((G_A, U_ADMIN_A, P_A), (G_B, U_ADMIN_B, P_B)):
        cx.execute("INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, entidad_id,"
                   " persona_cuidada_id) VALUES (%s, 'usuario', %s, 'persona.datos_descargar', 'persona_cuidada', %s,"
                   " %s)", (grupo, actor, persona, persona))


@pytest.mark.rf("RF-08")
@pytest.mark.rf("Ley-21.719")
@pytest.mark.parametrize("usuario, grupo", [
    (U_ADMIN_A, G_A),   # A, con su grupo, filtrando por la persona de B
    (U_ADMIN_A, G_B),   # A con el grupo de B: no es miembro
    (U_PAG_A, G_A),     # pagador de A
    (U_OBS_A, G_A),     # observador de A
])
def test_nadie_lee_la_auditoria_de_la_persona_de_otro(cx, usuario, grupo):
    """D-54-6 a: la columna nueva no abre lecturas. A no lee lo de la persona de B, ni el pagador ni el observador
    leen la copia que pidió el admin."""
    _sembrar_copias(cx)
    como(cx, usuario_id=usuario, grupo_id=grupo)
    assert contar(cx, "auditoria", f"persona_cuidada_id = '{P_B}'") == 0
    if usuario != U_ADMIN_A:
        assert contar(cx, "auditoria", f"persona_cuidada_id = '{P_A}'") == 0


@pytest.mark.rf("RF-08")
@pytest.mark.rf("Ley-21.719")
def test_el_admin_lee_la_copia_de_su_persona(cx):
    _sembrar_copias(cx)
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    assert contar(cx, "auditoria", f"persona_cuidada_id = '{P_A}'") == 1


@pytest.mark.rf("RF-08")
@pytest.mark.rf("Ley-21.719")
def test_una_fila_con_la_persona_de_otro_grupo_falla(cx):
    """auditoria_persona_fk: la integridad referencial no pasa por RLS, y vale para matu_app y para el relevo."""
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.ForeignKeyViolation):
        cx.execute("INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, persona_cuidada_id)"
                   " VALUES (%s, 'usuario', %s, 'plan.leer', 'plan_cuidado', %s)", (G_A, U_ADMIN_A, P_B))


@pytest.mark.rf("RF-08")
@pytest.mark.rf("Ley-21.719")
def test_el_relevo_no_registra_con_la_persona_de_otro_grupo(cx):
    como(cx, rol="relevo", acceso_relevo_id=ACC_VIGENTE)
    with pytest.raises(errors.ForeignKeyViolation):
        cx.execute("INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, persona_cuidada_id)"
                   " VALUES (%s, 'relevo', %s, 'relevo.abrir', 'plan_cuidado', %s)", (G_A, ACC_VIGENTE, P_B))


@pytest.mark.rf("RF-08")
@pytest.mark.rf("Ley-21.719")
def test_una_accion_de_persona_sin_persona_falla(cx):
    """auditoria_persona_obligatoria (NOT VALID): toda fila nueva de una acción de persona lleva su persona."""
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.CheckViolation):
        cx.execute("INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad)"
                   " VALUES (%s, 'usuario', %s, 'persona.datos_descargar', 'persona_cuidada')", (G_A, U_ADMIN_A))


@pytest.mark.rf("RF-37")
@pytest.mark.rf("Ley-21.719")
def test_la_copia_de_la_cuenta_la_lee_solo_su_duena(cx):
    for usuario in (U_ADMIN_A, U_ADMIN_B):
        cx.execute("INSERT INTO auditoria (actor_tipo, actor_ref, accion, entidad, entidad_id)"
                   " VALUES ('usuario', %s, 'cuenta.datos_descargar', 'usuario', %s)", (usuario, usuario))
    como(cx, usuario_id=U_ADMIN_A)
    assert {r[0] for r in cx.execute(
        "SELECT actor_ref FROM auditoria WHERE accion = 'cuenta.datos_descargar'").fetchall()} == {U_ADMIN_A}


# ---- MATU-63 (migración 0029): la vista del comercio por funciones, el despacho y el retracto

TABLAS_SIN_COMERCIO = ("pedido", "pedido_comercio", "pedido_linea", "pedido_transicion", "regla_sustitucion",
                       "pedido_entrega", "cargo", "participacion", "transaccion_pasarela", "evidencia",
                       "retracto", "retracto_linea", "persona_cuidada", "direccion", "idempotencia",
                       # H9 del cierre del analista: tampoco lo que MATU le debe, hasta que exista la liquidación
                       "consumo_comercio")
PARTE_A = uuid.UUID("00000000-0000-0000-0000-0000000009a1")


@pytest.mark.rf("RF-26")
@pytest.mark.rf("Ley-21.719")
def test_el_comercio_lee_cero_filas_de_las_tablas_del_pedido(cx):
    """D-63-1: ni el pedido, ni su parte, ni sus líneas, transiciones, reglas, entrega, pago, evidencia o retracto."""
    _pedido_de_dos_comercios(cx)
    for usuario, comercio in ((U_ENC, COMERCIO), (U_ENC_2, COMERCIO_2)):
        cx.execute("RESET ROLE")
        como(cx, usuario_id=usuario, comercio_id=comercio)
        for t in TABLAS_SIN_COMERCIO:
            assert contar(cx, t) == 0, f"el comercio alcanza {t}"


@pytest.mark.rf("RF-26")
def test_la_proyeccion_del_comercio_no_trae_nada_de_la_familia(cx):
    """D-63-1 y R7: las columnas de las funciones, sin pedido_id, grupo, persona, montos, referencia de la familia ni
    hash."""
    como(cx, usuario_id=U_ENC, comercio_id=COMERCIO)
    prohibidas = {"pedido_id", "grupo_id", "persona_cuidada_id", "creado_por", "total", "costo_envio",
                  "precio_unitario", "monto_devuelto", "codigo_hash", "condiciones_version"}
    for funcion in ("comercio_partes('-infinity')", f"comercio_lineas('{PARTE_A}')", "comercio_existencias(now())"):
        columnas = {d.name for d in cx.execute(f"SELECT * FROM {funcion}").description}
        assert not columnas & prohibidas, funcion


@pytest.mark.rf("RF-26")
def test_el_comercio_no_cambia_grupo_estado_lineas_ni_dinero(cx):
    """D-63-2: el comercio escribe solo por sus funciones. Directo no alcanza ninguna fila del pedido ni del pago."""
    como(cx, usuario_id=U_ENC, comercio_id=COMERCIO)
    for sql in (
        f"UPDATE pedido SET estado = 'entregado' WHERE id = '{PED_A_ENVIADO}' RETURNING id",
        f"UPDATE pedido_comercio SET grupo_id = '{G_B}', estado = 'retirada' WHERE id = '{PARTE_A}' RETURNING id",
        f"UPDATE pedido_linea SET monto_devuelto = 1, estado_linea = 'devuelta' WHERE pedido_id = '{PED_A_ENVIADO}'"
        " RETURNING id",
        f"UPDATE cargo SET monto_devuelto = 1 WHERE id = '{CARGO_A}' RETURNING id",
        "UPDATE transaccion_pasarela SET estado = 'error' RETURNING id",
    ):
        assert cx.execute(sql).fetchall() == [], sql
    for sql in (
        f"INSERT INTO consumo_comercio (comercio_id, pedido_id, monto_autorizado) VALUES ('{COMERCIO}',"
        f" '{PED_A_ENVIADO}', 1)",
        f"INSERT INTO evidencia (pedido_id, tipo, objeto_clave, sha256, registrada_por_tipo, registrada_por)"
        f" VALUES ('{PED_A_ENVIADO}', 'boleta', 'x', sha256('x'), 'comercio', '{U_ENC}')",
        # P3: su auditoría, solo como comercio, sin grupo ni persona
        f"INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad) VALUES"
        f" ('{G_A}', 'comercio', '{U_ENC}', 'pedido.crear', 'pedido')",
        f"INSERT INTO auditoria (actor_tipo, actor_ref, accion, entidad) VALUES"
        f" ('usuario', '{U_ENC}', 'sesion.iniciar', 'usuario')",
    ):
        cx.execute("SAVEPOINT s")
        with pytest.raises((errors.InsufficientPrivilege, errors.CheckViolation)):
            cx.execute(sql)
        cx.execute("ROLLBACK TO SAVEPOINT s")
    cx.execute(f"INSERT INTO auditoria (actor_tipo, actor_ref, accion, entidad, entidad_id) VALUES"
               f" ('comercio', '{U_ENC}', 'comercio.preparar', 'pedido_comercio', '{PARTE_A}')")
    # De su oferta, solo el stock y si la ofrece (trigger oferta_comercio_acotada), nunca el precio
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("UPDATE oferta SET precio = 1 WHERE comercio_id = %s", (COMERCIO,))
    assert cx.execute("UPDATE oferta SET stock = 3, disponible = false WHERE comercio_id = %s RETURNING id",
                      (COMERCIO,)).fetchall() != []


@pytest.mark.rf("RF-26")
def test_cada_comercio_mueve_solo_sus_partes_tambien_en_el_mismo_pedido(cx):
    """D7 y R8 con escritura: el comercio que reemplaza o comparte el pedido no toca la parte del otro."""
    _pedido_de_dos_comercios(cx)
    parte_uno, parte_dos = uuid.UUID(int=0xA31), uuid.UUID(int=0xA32)
    [(linea_uno,)] = cx.execute("SELECT id FROM pedido_linea WHERE pedido_comercio_id = %s", (parte_uno,)).fetchall()
    como(cx, usuario_id=U_ENC_2, comercio_id=COMERCIO_2)
    assert cx.execute("SELECT comercio_preparar(%s, NULL, now())", (parte_uno,)).fetchone() == ("no_encontrada",)
    assert cx.execute("SELECT comercio_listo(%s, NULL, now())", (parte_uno,)).fetchone() == ("no_encontrada",)
    assert cx.execute("SELECT * FROM comercio_validar_codigo(%s, repeat('a', 64), now())",
                      (parte_uno,)).fetchone()[0] == "no_encontrada"
    assert cx.execute("SELECT comercio_preparar(%s, NULL, now())", (parte_dos,)).fetchone() == ("ok",)
    # Su propia parte, con la línea del otro: no la encuentra
    assert cx.execute("SELECT comercio_marcar_linea(%s, %s, 'faltante', 1, NULL)",
                      (parte_dos, linea_uno)).fetchone() == ("no_encontrada",)
    cx.execute("RESET ROLE")
    assert cx.execute("SELECT estado FROM pedido_comercio WHERE id = %s", (parte_uno,)).fetchone() == ("enviada",)
    assert cx.execute("SELECT unidades_faltantes FROM pedido_linea WHERE id = %s", (linea_uno,)).fetchone() == (0,)


@pytest.mark.rf("RF-26")
@pytest.mark.parametrize("contexto", [
    {"usuario_id": U_ADMIN_A, "comercio_id": COMERCIO},
    {"usuario_id": U_ENC, "comercio_id": COMERCIO, "grupo_id": G_A},
    {"usuario_id": U_ENC, "comercio_id": COMERCIO, "rol": "sistema"},
    {"comercio_id": COMERCIO},
], ids=["otra-cuenta", "con-grupo", "con-rol", "sin-cuenta"])
def test_las_funciones_del_comercio_exigen_su_cuenta_activa(cx, contexto):
    como(cx, **contexto)
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("SELECT * FROM comercio_partes('-infinity')")


@pytest.mark.rf("RF-26")
def test_una_cuenta_de_comercio_inactiva_no_entra(cx):
    cx.execute("UPDATE usuario_comercio SET activo = false WHERE usuario_id = %s", (U_ENC,))
    como(cx, usuario_id=U_ENC, comercio_id=COMERCIO)
    with pytest.raises(errors.InsufficientPrivilege):
        cx.execute("SELECT * FROM comercio_partes('-infinity')")


@pytest.mark.rf("Ley-21.719")
def test_una_cuenta_de_comercio_no_es_miembro_de_un_grupo_y_al_reves(cx):
    """D-63-14, en la base: también como superusuario."""
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("INSERT INTO membresia (grupo_id, usuario_id, rol) VALUES (%s, %s, 'observador')", (G_A, U_ENC))
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("INSERT INTO usuario_comercio (usuario_id, comercio_id) VALUES (%s, %s)", (U_ADMIN_A, COMERCIO))


@pytest.mark.rf("Ley-21.719")
def test_la_evidencia_no_guarda_ubicacion(cx):
    """D-63-15."""
    with pytest.raises(errors.CheckViolation):
        cx.execute("INSERT INTO evidencia (pedido_id, tipo, objeto_clave, sha256, lat, lng, registrada_por_tipo,"
                   " registrada_por) VALUES (%s, 'entrega', 'x', sha256('x'), -33.4, -70.6, 'operacion', %s)",
                   (PED_A_ENVIADO, U_ADMIN_A))


@pytest.mark.rf("RF-26")
def test_despues_del_pago_el_sistema_mueve_el_pedido_solo_por_el_despacho(cx):
    """pedido_escritura_del_pago (0029): ni saltarse estados, ni tocar otra columna, ni fijar entregado_en a mano."""
    como(cx, grupo_id=G_A, rol="sistema")
    for cambio in ("estado = 'entregado'", "estado = 'cerrado'", "referencia = '9999'",
                   "entregado_en = now()", "condiciones_version = '0.9'"):
        cx.execute("SAVEPOINT s")
        with pytest.raises(errors.CheckViolation):
            cx.execute(f"UPDATE pedido SET {cambio} WHERE id = %s", (PED_A_ENVIADO,))
        cx.execute("ROLLBACK TO SAVEPOINT s")
    cx.execute("UPDATE pedido SET estado = 'preparando' WHERE id = %s", (PED_A_ENVIADO,))
    # Operación tampoco salta; avanza por las transiciones
    cx.execute("RESET ROLE")
    como(cx, rol="operacion")
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("UPDATE pedido SET estado = 'en_ruta' WHERE id = %s", (PED_A_ENVIADO,))


def _entregado(cx):
    """Como superusuario, sin triggers: el pedido pagado de A, entregado."""
    cx.execute("SET LOCAL session_replication_role = replica")
    cx.execute("UPDATE pedido SET estado = 'entregado', entregado_en = now() WHERE id = %s", (PED_A_ENVIADO,))
    cx.execute("SET LOCAL session_replication_role = origin")


@pytest.mark.rf("R3")
def test_el_retracto_lo_pide_el_admin_o_quien_pago_y_lo_ve_solo_su_grupo(cx):
    """D-63-10, en la base: retracto_familia_crear y RLS forzado en retracto y retracto_linea."""
    _entregado(cx)
    assert cx.execute("SELECT bool_and(relrowsecurity AND relforcerowsecurity) FROM pg_class"
                      " WHERE relname IN ('retracto', 'retracto_linea')").fetchone() == (True,)
    insertar = ("INSERT INTO retracto (id, grupo_id, pedido_id, solicitado_por, solicitado_en, plazo_hasta,"
                " incluye_envio) VALUES (%s, %s, %s, %s, now(), now() + interval '10 days', true)")
    # El pagador que no pagó este pedido y el observador: no
    for usuario in (U_PAG_A, U_OBS_A):
        cx.execute("RESET ROLE")
        como(cx, usuario_id=usuario, grupo_id=G_A)
        cx.execute("SAVEPOINT s")
        with pytest.raises(errors.InsufficientPrivilege):
            cx.execute(insertar, (uuid.uuid4(), G_A, PED_A_ENVIADO, usuario))
        cx.execute("ROLLBACK TO SAVEPOINT s")
    cx.execute("RESET ROLE")
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    retracto = uuid.uuid4()
    cx.execute(insertar, (retracto, G_A, PED_A_ENVIADO, U_ADMIN_A))
    [(linea,)] = cx.execute("SELECT id FROM pedido_linea WHERE pedido_id = %s", (PED_A_ENVIADO,)).fetchall()
    # Hasta lo entregado (2 pañales), también entre varios retractos (H3)
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("INSERT INTO retracto_linea (retracto_id, grupo_id, pedido_linea_id, cantidad)"
                   " VALUES (%s, %s, %s, 3)", (retracto, G_A, linea))
    cx.execute("INSERT INTO retracto_linea (retracto_id, grupo_id, pedido_linea_id, cantidad) VALUES (%s, %s, %s, 1)",
               (retracto, G_A, linea))
    otro = uuid.uuid4()
    cx.execute(insertar, (otro, G_A, PED_A_ENVIADO, U_ADMIN_A))
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute("INSERT INTO retracto_linea (retracto_id, grupo_id, pedido_linea_id, cantidad)"
                   " VALUES (%s, %s, %s, 2)", (otro, G_A, linea))
    cx.execute("INSERT INTO retracto_linea (retracto_id, grupo_id, pedido_linea_id, cantidad) VALUES (%s, %s, %s, 1)",
               (otro, G_A, linea))
    # H2: la familia no registra un retracto «por correo»
    with pytest.raises(errors.InsufficientPrivilege), cx.transaction():
        cx.execute("INSERT INTO retracto (grupo_id, pedido_id, solicitado_por, solicitado_en, plazo_hasta,"
                   " incluye_envio, origen) VALUES (%s, %s, %s, now(), now() + interval '10 days', true, 'correo')",
                   (G_A, PED_A_ENVIADO, U_ADMIN_A))
    # La familia no lo resuelve
    assert cx.execute("UPDATE retracto SET estado = 'devuelto', resuelto_en = now() WHERE id = %s RETURNING id",
                      (retracto,)).fetchall() == []
    for usuario, grupo, comercio in ((U_ADMIN_B, G_B, None), (U_ENC, None, COMERCIO)):
        cx.execute("RESET ROLE")
        como(cx, usuario_id=usuario, grupo_id=grupo, comercio_id=comercio)
        assert contar(cx, "retracto") == 0 and contar(cx, "retracto_linea") == 0


@pytest.mark.rf("RF-25")
def test_una_linea_se_anula_una_vez_por_motivo(cx):
    """transaccion_linea_devuelta_uq (0029): un faltante y un retracto de la misma línea, nunca dos del mismo motivo."""
    [(linea,)] = cx.execute("SELECT id FROM pedido_linea WHERE pedido_id = %s", (PED_A_ENVIADO,)).fetchall()
    [(venta,)] = cx.execute("SELECT id FROM transaccion_pasarela WHERE tipo = 'venta' AND cargo_id = %s",
                            (CARGO_A,)).fetchall()
    insertar = ("INSERT INTO transaccion_pasarela (participacion_id, cargo_id, proveedor, tipo, buy_order, monto,"
                " estado, idempotency_key, venta_id, motivo_anulacion, pedido_linea_id) VALUES"
                " ('00000000-0000-0000-0000-0000000008a1', %s, 'webpay_plus', 'anulacion', %s, 100, 'iniciada', %s,"
                " %s, %s, %s)")
    cx.execute(insertar, (CARGO_A, "MATU-A1", "a1", venta, "producto_no_entregado", linea))
    with pytest.raises(errors.UniqueViolation), cx.transaction():
        cx.execute(insertar, (CARGO_A, "MATU-A9", "a9", venta, "producto_no_entregado", linea))
    # H3: una anulación por línea en cada retracto, y dos retractos de la misma línea, dos anulaciones
    _entregado(cx)
    retractos = []
    for _ in range(2):
        r = uuid.uuid4()
        cx.execute("INSERT INTO retracto (id, grupo_id, pedido_id, solicitado_por, solicitado_en, plazo_hasta,"
                   " incluye_envio) VALUES (%s, %s, %s, %s, now(), now() + interval '10 days', false)",
                   (r, G_A, PED_A_ENVIADO, U_ADMIN_A))
        retractos.append(r)
    con_retracto = insertar.replace("pedido_linea_id)", "pedido_linea_id, retracto_id)").replace("%s)", "%s, %s)")
    cx.execute(con_retracto, (CARGO_A, "MATU-A2", "a2", venta, "retracto", linea, retractos[0]))
    cx.execute(con_retracto, (CARGO_A, "MATU-A3", "a3", venta, "retracto", linea, retractos[1]))
    with pytest.raises(errors.UniqueViolation):
        cx.execute(con_retracto, (CARGO_A, "MATU-A4", "a4", venta, "retracto", linea, retractos[0]))


@pytest.mark.rf("Ley-21.719")
def test_d63_13_las_partes_lineas_y_retractos_siguen_al_pedido_y_las_anulaciones_al_pago(cx):
    """D-63-13: al borrar un pedido (cuando venza su plazo de 2 años), sus partes, líneas y retractos se van con él; la
    anulación de un retracto se queda con el pago (6 años), sin el retracto."""
    reglas = dict(cx.execute("""
        SELECT conrelid::regclass::text || '.' || a.attname, c.confdeltype
          FROM pg_constraint c JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
         WHERE c.contype = 'f' AND conrelid::regclass::text IN
               ('pedido_comercio', 'pedido_linea', 'retracto', 'retracto_linea', 'transaccion_pasarela')""").fetchall())
    assert reglas["pedido_comercio.pedido_id"] == "c" and reglas["pedido_linea.pedido_id"] == "c"
    assert reglas["retracto.pedido_id"] == "c" and reglas["retracto_linea.retracto_id"] == "c"
    assert reglas["retracto_linea.pedido_linea_id"] == "c"
    assert reglas["transaccion_pasarela.retracto_id"] == "n"


@pytest.mark.rf("RF-26")
def test_el_codigo_desde_la_consola_es_solo_para_matu_scheduler_y_parte_lista(cx):
    """D-63-5: codigo_retiro_guardar no la ejecuta matu_app, ni con operación; con una parte que no está lista no
    escribe nada."""
    como(cx, rol="operacion")
    with pytest.raises(errors.InsufficientPrivilege), cx.transaction():
        cx.execute("SELECT codigo_retiro_guardar(%s, repeat('a', 64), now(), now() + interval '90 minutes')",
                   (PARTE_A,))
    cx.execute("RESET ROLE")
    como(cx, "matu_scheduler", rol="operacion")
    assert cx.execute("SELECT codigo_retiro_guardar(%s, repeat('a', 64), now(), now() + interval '90 minutes')",
                      (PARTE_A,)).fetchone() == ("estado",)
    # Un plazo distinto de 90 minutos no entra
    with pytest.raises(errors.InvalidParameterValue), cx.transaction():
        cx.execute("SELECT codigo_retiro_guardar(%s, repeat('a', 64), now(), now() + interval '1 day')", (PARTE_A,))



@pytest.mark.rf("R3")
def test_el_plazo_del_retracto_depende_de_su_origen(cx):
    """H2: en la app, como mucho 16 días corridos desde la entrega (10 hábiles); por correo, 90 días (CL-54). Operación
    registra solo los de correo."""
    _entregado(cx)
    insertar = ("INSERT INTO retracto (grupo_id, pedido_id, solicitado_por, solicitado_en, plazo_hasta, incluye_envio,"
                " origen) VALUES (%s, %s, %s, now(), now() + %s::interval, false, %s)")
    como(cx, rol="operacion")
    with pytest.raises(errors.InsufficientPrivilege), cx.transaction():
        cx.execute(insertar, (G_A, PED_A_ENVIADO, U_ADMIN_A, "10 days", "app"))
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute(insertar, (G_A, PED_A_ENVIADO, U_ADMIN_A, "120 days", "correo"))
    cx.execute(insertar, (G_A, PED_A_ENVIADO, U_ADMIN_A, "80 days", "correo"))
    cx.execute("RESET ROLE")
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.CheckViolation), cx.transaction():
        cx.execute(insertar, (G_A, PED_A_ENVIADO, U_ADMIN_A, "30 days", "app"))


@pytest.mark.rf("R3")
def test_la_familia_no_suma_lineas_a_un_retracto_por_correo(cx):
    """P3 del cierre: aunque el retracto de correo vaya a su nombre, la familia no le agrega productos; solo
    operación."""
    _entregado(cx)
    retracto = uuid.uuid4()
    como(cx, rol="operacion")
    cx.execute("INSERT INTO retracto (id, grupo_id, pedido_id, solicitado_por, solicitado_en, plazo_hasta,"
               " incluye_envio, origen) VALUES (%s, %s, %s, %s, now(), now() + interval '80 days', false, 'correo')",
               (retracto, G_A, PED_A_ENVIADO, U_ADMIN_A))
    [(linea,)] = cx.execute("SELECT id FROM pedido_linea WHERE pedido_id = %s", (PED_A_ENVIADO,)).fetchall()
    cx.execute("RESET ROLE")
    como(cx, usuario_id=U_ADMIN_A, grupo_id=G_A)
    with pytest.raises(errors.InsufficientPrivilege), cx.transaction():
        cx.execute("INSERT INTO retracto_linea (retracto_id, grupo_id, pedido_linea_id, cantidad)"
                   " VALUES (%s, %s, %s, 1)", (retracto, G_A, linea))
    cx.execute("RESET ROLE")
    como(cx, rol="operacion")
    cx.execute("INSERT INTO retracto_linea (retracto_id, grupo_id, pedido_linea_id, cantidad) VALUES (%s, %s, %s, 1)",
               (retracto, G_A, linea))
