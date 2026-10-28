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
                           pin_hash, expira_en) VALUES
 ('{ACC_VIGENTE}',  '{G_A}', '{PLAN_A}', '{U_ADMIN_A}', 'Relevo',   '+56911111111', 'María', 'Ana',
  ARRAY['rutina','manejo_situaciones'], 'fin de semana', sha256('t1'), 'p', now() + interval '1 day'),
 ('{ACC_VENCIDO}',  '{G_A}', '{PLAN_A}', '{U_ADMIN_A}', 'Vencido',  '+56922222222', 'María', 'Ana',
  ARRAY['rutina'], 'turno', sha256('t2'), 'p', now() + interval '1 day'),
 ('{ACC_REVOCADO}', '{G_A}', '{PLAN_A}', '{U_ADMIN_A}', 'Revocado', '+56933333333', 'María', 'Ana',
  ARRAY['rutina'], 'turno', sha256('t3'), 'p', now() + interval '1 day');
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
INSERT INTO oferta (id, producto_id, comercio_id, precio_referencia) VALUES
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
                   expira_en)
               VALUES (%s, %s, %s, 'Relevo', '+56955550137', 'María', 'Luis', ARRAY['rutina'], 'otro',
                   sha256('t9'), 'p', now() + interval '1 day')""", (G_A, PLAN_A, U_ADMIN_B))


def test_relevo_ve_exactamente_sus_secciones(cx):
    como(cx, rol="relevo", acceso_relevo_id=ACC_VIGENTE)
    tipos = {r[0] for r in cx.execute("SELECT tipo FROM plan_seccion").fetchall()}
    assert tipos == {"rutina", "manejo_situaciones"}
    assert contar(cx, "acceso_relevo") == 1          # no ve los otros accesos
    assert contar(cx, "clave_datos") == 1            # puede descifrar solo a esa persona


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
    # Tampoco se crea otra clave para la misma persona
    with pytest.raises(errors.UniqueViolation), cx.transaction():
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
        INSERT INTO oferta (id, producto_id, comercio_id, precio_referencia) VALUES
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
