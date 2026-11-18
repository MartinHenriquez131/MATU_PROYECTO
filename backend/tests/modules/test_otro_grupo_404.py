"""MATU-79: toda ruta con un recurso de un grupo responde 404 desde otro grupo, nunca 403 ni 200.

Arquitectura, sección 7.7, y CLAUDE.md, agente 2, punto 4: un recurso de otro grupo responde 404, nunca 403. Las
pruebas de cada módulo lo prueban ruta por ruta, y esta lo hace para todas a la vez:

1. Recorre las rutas de la API montada como en producción, con la capa 3 encendida (``iter_route_contexts``, que
   también ve los routers incluidos). Toda ruta con un parámetro en la ruta tiene que estar en ``RECURSO_DE_GRUPO``
   o en ``EXCEPCIONES``, con su motivo. **Una ruta nueva sin clasificar hace fallar la prueba**: quien la agrega
   decide si es de un grupo (y entonces se prueba aquí) o por qué no.
2. Siembra una familia A con cada recurso de verdad (grupo, persona, membresía, invitación, acceso de relevo,
   perfil de consumo, alerta y pedido), y pide cada ruta de ``RECURSO_DE_GRUPO`` con los ids de A desde el admin de
   otra familia B, de dos formas: con ``X-Grupo-Id`` del grupo B (su grupo, del que sí es miembro) y con el de A (del
   que no lo es). Las dos responden 404 RFC 7807, sin el nombre de A ni de su persona en el cuerpo.
3. El control, para que la prueba no pase en vacío con un id mal sembrado:
   - cada valor sembrado existe en la base, consultado como superusuario, es de A y está vigente (``EXISTE``),
     también los que solo aparecen en escrituras (``alerta_id``, ``invitacion_id``, ``membresia_id`` y
     ``acceso_id``);
   - el admin de A pide las rutas de lectura con los mismos ids y recibe 200.
4. Las peticiones de B no cambian nada de A: la huella de las filas de A (``huella_de_a``) es la misma antes y
   después de todas ellas.

El cuerpo de cada petición es válido para la ruta (``CUERPOS``) y lleva las cabeceras de versión e idempotencia, así
el 404 no puede ser la sombra de un 422 o un 428.
"""

import json
import re
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.routing import iter_route_contexts

from app.core.config import obtener_configuracion
from app.main import incluir_capa_3
from app.modules.care_circle.api.router_autorizaciones import finalidades_activas
from app.modules.care_circle.domain.personas import FINALIDAD_DESPACHO
from app.modules.care_circle.domain.retiro import finalidades_retirables
from app.modules.care_circle.infrastructure.efectos_retiro import registrar_efecto
from app.modules.care_plan.api.dependencias import obtener_custodia
from app.modules.catalog.infrastructure.catalogo_simulado import CatalogoComercioSimulado
from app.modules.ordering.api.router import obtener_catalogo_comercio_pedido, obtener_costo_envio
from app.modules.ordering.infrastructure.efecto_retiro import EfectoRetiroPedidos
from app.modules.payments.infrastructure.pasarela import obtener_pasarela
from app.modules.payments.infrastructure.pasarela_falsa import PasarelaFalsa
from tests.base_datos import DSN, requiere_base
from tests.dobles.custodia_en_memoria import CustodiaEnMemoria
from tests.fabricas import Fabrica, FamiliaCreada, UsuarioCreado
from tests.modules.catalog.conftest import CatalogoSintetico, catalogo_sintetico  # noqa: F401
from tests.modules.conftest import EntornoIam
from tests.modules.ordering.conftest import COSTO_ENVIO, EntornoPedido, Existencias
from tests.modules.payments.conftest import cuerpo_pagar

pytestmark = [requiere_base, pytest.mark.rf("MATU-79")]

PROBLEMA = "application/problem+json"

# Las rutas con un recurso de un grupo familiar: se piden desde otro grupo y responden 404. La clave es
# (método, plantilla de la ruta)
RECURSO_DE_GRUPO: frozenset[tuple[str, str]] = frozenset({
    # care_circle: el grupo, sus personas, invitaciones y miembros
    ("POST", "/v1/grupos/{grupo_id}/personas-cuidadas"),
    ("GET", "/v1/grupos/{grupo_id}/personas-cuidadas"),
    ("POST", "/v1/grupos/{grupo_id}/invitaciones"),
    ("GET", "/v1/grupos/{grupo_id}/invitaciones"),
    ("DELETE", "/v1/grupos/{grupo_id}/invitaciones/{invitacion_id}"),
    ("GET", "/v1/grupos/{grupo_id}/miembros"),
    ("PATCH", "/v1/grupos/{grupo_id}/miembros/{membresia_id}"),
    ("DELETE", "/v1/grupos/{grupo_id}/miembros/{membresia_id}"),
    ("POST", "/v1/grupos/{grupo_id}/salida"),
    ("POST", "/v1/personas-cuidadas/{persona_id}/consentimientos"),
    ("GET", "/v1/personas-cuidadas/{persona_id}/consentimientos"),
    ("POST", "/v1/personas-cuidadas/{persona_id}/consentimientos/{finalidad}/retiro"),
    ("POST", "/v1/personas-cuidadas/{persona_id}/borrado"),
    ("PUT", "/v1/personas-cuidadas/{persona_id}/direccion"),
    ("DELETE", "/v1/personas-cuidadas/{persona_id}/direccion"),
    # care_plan: la ficha, sus secciones, el relevo, las aperturas y la copia de los datos
    ("GET", "/v1/personas-cuidadas/{persona_id}/plan/ficha"),
    ("PUT", "/v1/personas-cuidadas/{persona_id}/plan/ficha/{campo}"),
    ("PUT", "/v1/personas-cuidadas/{persona_id}/plan/secciones/{seccion}"),
    ("DELETE", "/v1/personas-cuidadas/{persona_id}/plan/secciones/{seccion}"),
    ("POST", "/v1/personas-cuidadas/{persona_id}/plan/accesos-relevo"),
    ("GET", "/v1/personas-cuidadas/{persona_id}/plan/accesos-relevo"),
    ("DELETE", "/v1/accesos-relevo/{acceso_id}"),
    ("GET", "/v1/personas-cuidadas/{persona_id}/plan/aperturas"),
    ("GET", "/v1/personas-cuidadas/{persona_id}/datos"),
    # consumption: los insumos, las alertas, la lista y la reposición
    ("GET", "/v1/personas-cuidadas/{persona_id}/consumo/por-acabarse"),
    ("GET", "/v1/personas-cuidadas/{persona_id}/consumo/alertas"),
    ("POST", "/v1/personas-cuidadas/{persona_id}/consumo/alertas/{alerta_id}/descartar"),
    ("POST", "/v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}/resolver"),
    ("GET", "/v1/personas-cuidadas/{persona_id}/consumo/lista"),
    ("GET", "/v1/personas-cuidadas/{persona_id}/consumo"),
    ("POST", "/v1/personas-cuidadas/{persona_id}/consumo"),
    ("GET", "/v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}"),
    ("PATCH", "/v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}"),
    ("DELETE", "/v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}"),
    ("POST", "/v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}/desactivar"),
    ("POST", "/v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}/activar"),
    ("POST", "/v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}/reponer"),
    ("POST", "/v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}/recontar"),
    # ordering, payments y backoffice (familia): el pedido de la persona, antes y después de pagar
    ("POST", "/v1/personas-cuidadas/{persona_id}/pedidos"),
    ("GET", "/v1/personas-cuidadas/{persona_id}/pedido-en-curso"),
    ("GET", "/v1/pedidos/{pedido_id}"),
    ("PUT", "/v1/pedidos/{pedido_id}/lineas"),
    ("PUT", "/v1/pedidos/{pedido_id}/reglas-faltante"),
    ("POST", "/v1/pedidos/{pedido_id}/confirmar"),
    ("PUT", "/v1/pedidos/{pedido_id}/contacto"),
    ("POST", "/v1/pedidos/{pedido_id}/cambiar"),
    ("POST", "/v1/pedidos/{pedido_id}/cancelar"),
    ("POST", "/v1/pedidos/{pedido_id}/pagar"),
    ("GET", "/v1/pedidos/{pedido_id}/pago"),
    ("GET", "/v1/personas-cuidadas/{persona_id}/pedido-pagado"),
    ("GET", "/v1/personas-cuidadas/{persona_id}/pedidos"),
    ("GET", "/v1/pedidos/{pedido_id}/seguimiento"),
    ("POST", "/v1/pedidos/{pedido_id}/cancelar-con-devolucion"),
    ("GET", "/v1/pedidos/{pedido_id}/retractos"),
    ("POST", "/v1/pedidos/{pedido_id}/retractos"),
})

# Por qué la vista del comercio y la consola de operación no son de un grupo, y dónde se prueba su aislamiento
COMERCIO = (
    "vista del comercio (MATU-63): el alcance es la cuenta del comercio (app.comercio_id), nunca un grupo; el comercio"
    " no manda X-Grupo-Id. Otro comercio y la familia reciben 404 en tests/modules/backoffice/test_despacho_api.py"
    " (test_la_parte_de_otro_comercio_es_404, test_la_linea_y_la_oferta_de_otro_comercio_son_404_y_no_cambian y"
    " test_las_rutas_con_parametro_de_comercio_y_operacion_son_404_para_la_familia)"
)
OPERACION = (
    "consola de operación (MATU-63, D-63-5): la cuenta con usuario.es_operacion ve los pedidos de todos los grupos por"
    " diseño y no manda X-Grupo-Id. La familia recibe 404 en tests/modules/backoffice/test_despacho_api.py"
    " (test_las_rutas_con_parametro_de_comercio_y_operacion_son_404_para_la_familia)"
)

# Las rutas con parámetro que no son de un grupo familiar, con el motivo y dónde se prueba su aislamiento
EXCEPCIONES: dict[tuple[str, str], str] = {
    ("DELETE", "/v1/dispositivos/{dispositivo_id}"): (
        "recurso de la cuenta, no de un grupo: no lleva X-Grupo-Id. El dispositivo de otra cuenta responde 404 en"
        " tests/modules/iam/test_refresh_api.py (test_dispositivo_ajeno_inexistente_o_sin_uuid_responde_404)"
    ),
    ("GET", "/v1/comercio/partes/{parte_id}"): COMERCIO,
    ("POST", "/v1/comercio/partes/{parte_id}/preparar"): COMERCIO,
    ("PUT", "/v1/comercio/partes/{parte_id}/lineas/{linea_id}"): COMERCIO,
    ("POST", "/v1/comercio/partes/{parte_id}/listo"): COMERCIO,
    ("POST", "/v1/comercio/partes/{parte_id}/validar-codigo"): COMERCIO,
    ("PATCH", "/v1/comercio/productos/{oferta_id}"): COMERCIO,
    ("POST", "/v1/operacion/partes/{parte_id}/codigo"): OPERACION,
    ("POST", "/v1/operacion/pedidos/{pedido_id}/en-camino"): OPERACION,
    ("POST", "/v1/operacion/pedidos/{pedido_id}/entregado"): OPERACION,
    ("POST", "/v1/operacion/pedidos/{pedido_id}/no-entregado"): OPERACION,
    ("POST", "/v1/operacion/pedidos/{pedido_id}/cancelar-con-devolucion"): OPERACION,
    ("POST", "/v1/operacion/pedidos/{pedido_id}/retractos"): OPERACION,
    ("POST", "/v1/operacion/retractos/{retracto_id}/resolver"): OPERACION,
}

# Las rutas que solo existen para un pedido pagado: se piden con el pedido pagado de A, no con el carrito
DEL_PEDIDO_PAGADO: frozenset[str] = frozenset({
    "/v1/pedidos/{pedido_id}/pago",
    "/v1/pedidos/{pedido_id}/seguimiento",
    "/v1/pedidos/{pedido_id}/cancelar-con-devolucion",
    "/v1/pedidos/{pedido_id}/retractos",
})

PARAMETRO = re.compile(r"\{([a-z_]+)\}")
METODOS_DE_LECTURA = frozenset({"GET"})


def rutas_con_parametro(app: FastAPI) -> set[tuple[str, str]]:
    """(método, plantilla) de cada ruta de la app con al menos un parámetro en la ruta, incluidos los routers
    incluidos. HEAD y OPTIONS no cuentan: los agrega Starlette."""
    rutas: set[tuple[str, str]] = set()
    for contexto in iter_route_contexts(app.routes):
        ruta = contexto.path
        if not ruta or not PARAMETRO.search(ruta):
            continue
        for metodo in contexto.methods or ():
            if metodo not in {"HEAD", "OPTIONS"}:
                rutas.add((metodo, ruta))
    return rutas


# --- La app como en producción, con la capa 3 ----------------------------------------------------------------------


@pytest.fixture
def existencias() -> Existencias:
    return Existencias()


@pytest.fixture
def pasarela_falsa() -> PasarelaFalsa:
    return PasarelaFalsa()


@pytest.fixture
def rutas_de_prueba(
    existencias: Existencias, custodia: CustodiaEnMemoria, pasarela_falsa: PasarelaFalsa
) -> Callable[[FastAPI], None]:
    """La capa 3 montada como lo hace crear_app con CAPA3_HABILITADA (si el .env no la encendió ya), con el catálogo
    simulado, el costo del envío y la custodia en memoria. Ningún doble cambia el orden de evaluación de una ruta."""

    def montar(app: FastAPI) -> None:
        if not obtener_configuracion().capa3_habilitada:
            incluir_capa_3(app)
        registrar_efecto(FINALIDAD_DESPACHO, EfectoRetiroPedidos)
        app.dependency_overrides[finalidades_activas] = lambda: finalidades_retirables(True)
        app.dependency_overrides[obtener_costo_envio] = lambda: COSTO_ENVIO
        app.dependency_overrides[obtener_catalogo_comercio_pedido] = lambda: CatalogoComercioSimulado(
            existencias.por_comercio
        )
        app.dependency_overrides[obtener_custodia] = lambda: custodia
        app.dependency_overrides[obtener_pasarela] = lambda: pasarela_falsa

    return montar


@dataclass
class FamiliaSembrada:
    """La familia A con un recurso de verdad para cada parámetro, y el valor de cada parámetro."""

    familia: FamiliaCreada
    valores: dict[str, str] = field(default_factory=dict)


@dataclass
class Entorno:
    pedido: EntornoPedido
    a: FamiliaSembrada
    b: FamiliaCreada

    @property
    def iam(self) -> EntornoIam:
        return self.pedido.iam

    def pedir(self, metodo: str, plantilla: str, usuario: UsuarioCreado, grupo: uuid.UUID) -> Any:
        ruta = plantilla.removeprefix("/v1")
        for nombre in PARAMETRO.findall(plantilla):
            valor = self.a.valores["pedido_pagado_id" if plantilla in DEL_PEDIDO_PAGADO else nombre]
            ruta = ruta.replace("{" + nombre + "}", valor if nombre == "pedido_id" else self.a.valores[nombre])
        cabeceras = {
            "Authorization": f"Bearer {self.pedido.token(usuario)}",
            "X-Grupo-Id": str(grupo),
            "If-Match": '"v1"',
            "Idempotency-Key": self.pedido.clave(),
        }
        cuerpo = CUERPOS.get((metodo, plantilla))
        return self.iam.cliente.request(
            metodo, "/v1" + ruta, headers=cabeceras, json=cuerpo(self) if callable(cuerpo) else cuerpo
        )


def _superusuario(sql: str, *parametros: Any) -> Any:
    with psycopg.connect(DSN, autocommit=True) as cx:
        return cx.execute(sql, parametros).fetchone()


# Cada valor sembrado, como superusuario: existe, es del grupo A y está vigente. Uno que no existe (o de otro grupo, o
# ya cerrado) también respondería 404 y la prueba pasaría en vacío
EXISTE: dict[str, str] = {
    "grupo_id": "SELECT 1 FROM grupo_familiar WHERE id = %(valor)s AND id = %(grupo)s",
    "persona_id": "SELECT 1 FROM persona_cuidada WHERE id = %(valor)s AND grupo_id = %(grupo)s",
    "pedido_id": "SELECT 1 FROM pedido WHERE id = %(valor)s AND grupo_id = %(grupo)s AND pagado_en IS NULL",
    "pedido_pagado_id": "SELECT 1 FROM pedido WHERE id = %(valor)s AND grupo_id = %(grupo)s"
                        " AND pagado_en IS NOT NULL",
    "perfil_id": "SELECT 1 FROM perfil_consumo WHERE id = %(valor)s AND grupo_id = %(grupo)s",
    "alerta_id": "SELECT 1 FROM alerta_quiebre a JOIN perfil_consumo p ON p.id = a.perfil_id"
                 " WHERE a.id = %(valor)s AND p.grupo_id = %(grupo)s AND a.estado = 'pendiente'",
    "membresia_id": "SELECT 1 FROM membresia WHERE id = %(valor)s AND grupo_id = %(grupo)s AND estado = 'activa'",
    "invitacion_id": "SELECT 1 FROM invitacion WHERE id = %(valor)s AND grupo_id = %(grupo)s"
                     " AND aceptada_en IS NULL AND revocada_en IS NULL",
    "acceso_id": "SELECT 1 FROM acceso_relevo WHERE id = %(valor)s AND grupo_id = %(grupo)s AND revocado_en IS NULL",
    # Los que no son ids: la ficha de A existe para el campo y la sección, y su autorización de esa finalidad sigue
    # vigente
    "campo": "SELECT 1 FROM plan_cuidado WHERE grupo_id = %(grupo)s AND %(valor)s = 'rutina'",
    "seccion": "SELECT 1 FROM plan_cuidado WHERE grupo_id = %(grupo)s AND %(valor)s = 'alimentacion'",
    "finalidad": "SELECT 1 FROM consentimiento WHERE grupo_id = %(grupo)s AND finalidad = %(valor)s"
                 " AND revocado_en IS NULL",
}


def _existe(sql: str, valor: str, grupo: str) -> bool:
    with psycopg.connect(DSN, autocommit=True) as cx:
        return cx.execute(sql, {"valor": valor, "grupo": grupo}).fetchone() is not None


# Las llaves foráneas de una columna hacia el id de otra tabla: (tabla hija, columna, tabla madre)
_LLAVES = """
SELECT h.relname, a.attname, m.relname
  FROM pg_constraint k
  JOIN pg_class h ON h.oid = k.conrelid
  JOIN pg_class m ON m.oid = k.confrelid
  JOIN pg_attribute a ON a.attrelid = k.conrelid AND a.attnum = k.conkey[1]
  JOIN pg_attribute r ON r.attrelid = k.confrelid AND r.attnum = k.confkey[1]
 WHERE k.contype = 'f' AND cardinality(k.conkey) = 1 AND r.attname = 'id'
   AND h.relnamespace = 'public'::regnamespace AND m.relnamespace = 'public'::regnamespace
 ORDER BY 1, 2, 3
"""
_CON_GRUPO = """
SELECT c.table_name FROM information_schema.columns c
  JOIN information_schema.tables t ON t.table_schema = c.table_schema AND t.table_name = c.table_name
 WHERE c.table_schema = 'public' AND c.column_name = 'grupo_id' AND t.table_type = 'BASE TABLE'
 ORDER BY 1
"""
_MD5 = "SELECT md5(coalesce(string_agg(x::text, '|' ORDER BY x::text), '')) FROM {tabla} x WHERE {filtro}"


def _alcance_del_grupo(cx: psycopg.Connection[Any]) -> dict[str, str]:
    """Cada tabla con filas de un grupo y el filtro que las elige (con %(g)s): el grupo por su id, las tablas con
    grupo_id, y las que cuelgan de ellas por llaves foráneas, en cadena (hijas, nietas…). El filtro de una tabla sin
    grupo_id es el OR de todas sus llaves hacia tablas alcanzadas: una fila de A cuenta por cualquiera de ellas."""
    con_grupo = {fila[0] for fila in cx.execute(_CON_GRUPO).fetchall()}
    base = {"grupo_familiar": "id = %(g)s", **{t: "grupo_id = %(g)s" for t in con_grupo}}
    llaves: dict[str, list[tuple[str, str]]] = {}
    for hija, columna, madre in cx.execute(_LLAVES).fetchall():
        if hija not in base and hija != madre:
            llaves.setdefault(hija, []).append((columna, madre))
    alcanzadas = set(base)
    while nuevas := {h for h, ls in llaves.items() if h not in alcanzadas and any(m in alcanzadas for _, m in ls)}:
        alcanzadas |= nuevas

    def filtro(tabla: str, camino: frozenset[str]) -> str:
        if tabla in base:
            return base[tabla]
        partes = [f"{columna} IN (SELECT id FROM {madre} WHERE {filtro(madre, camino | {tabla})})"
                  for columna, madre in llaves[tabla] if madre in alcanzadas and madre not in camino]
        return "(" + " OR ".join(partes) + ")" if partes else "false"

    return {tabla: filtro(tabla, frozenset()) for tabla in sorted(alcanzadas)}


def huella_de_a(grupo: uuid.UUID) -> dict[str, str]:
    """La huella (md5 de las filas, en orden) de cada tabla de ``_alcance_del_grupo``, como superusuario y sin RLS."""
    with psycopg.connect(DSN, autocommit=True) as cx:
        huellas: dict[str, str] = {}
        for clave, filtro in _alcance_del_grupo(cx).items():
            fila = cx.execute(_MD5.format(tabla=clave, filtro=filtro), {"g": grupo}).fetchone()
            assert fila is not None
            huellas[clave] = fila[0]
    return huellas


def _sembrar_a(e: EntornoPedido, pasarela: PasarelaFalsa) -> FamiliaSembrada:
    """La familia A con ficha, autorizaciones de pedidos y de consumo, dirección, un pedido pagado y otro sin pagar, un
    perfil con su alerta, una invitación y un acceso de relevo, todo creado por la API o por la fábrica."""
    familia = e.lista_para_pedir(e.fabrica.familia(con_ficha=True))
    e.hay("panal", "uno")
    # El pagado: se confirma, se paga en la pasarela falsa y Webpay vuelve a MATU
    primero = e.crear(familia, [{"oferta_id": e.oferta("panal", "uno"), "cantidad": 1}])
    assert primero.status_code == 201, primero.text
    confirmado = e.confirmar(familia, primero.json()["id"])
    assert confirmado.status_code == 200, confirmado.text
    pago = e.pedir("POST", f"/v1/pedidos/{primero.json()['id']}/pagar", familia.admin, familia, cuerpo_pagar(),
                   **{"Idempotency-Key": e.clave(), "If-Match": confirmado.json()["etag"]})
    assert pago.status_code == 201, pago.text
    pasarela.pagar(pago.json()["token"])
    vuelta = e.iam.cliente.post("/v1/pagos/retorno", json={"token_ws": pago.json()["token"]})
    assert vuelta.status_code == 200 and vuelta.json()["resultado"] == "aprobado", vuelta.text
    # Entregado, para que existan sus retractos. El despacho completo (comercio, código y operación) lo prueba
    # tests/modules/backoffice/: aquí se marca como superusuario sin triggers, como la semilla de test_aislamiento
    with psycopg.connect(DSN) as cx:
        cx.execute("SET LOCAL session_replication_role = replica")
        cx.execute("UPDATE pedido SET estado = 'entregado', entregado_en = %s WHERE id = %s",
                   (e.iam.reloj.ahora(), primero.json()["id"]))
    # El carrito, sin pagar: hay uno solo por persona, y el pagado ya no cuenta
    creado = e.crear(familia, [{"oferta_id": e.oferta("panal", "uno"), "cantidad": 1}])
    assert creado.status_code == 201, creado.text
    pedido_id = creado.json()["id"]

    # Con la autorización de consumo: sin ella, las lecturas del consumo de A responden 403 y el control no sirve
    e.fabrica.autorizacion_consumo(familia.persona, otorgante=familia.admin)
    perfil_id = e.fabrica.perfil_consumo(familia.persona)
    [alerta_id] = _superusuario(
        "INSERT INTO alerta_quiebre (perfil_id, fecha_prevista) VALUES (%s, current_date + 3) RETURNING id", perfil_id
    )

    invitacion = e.pedir("POST", f"/v1/grupos/{familia.grupo.id}/invitaciones", familia.admin, familia,
                         {"rol": "cuidador"})
    assert invitacion.status_code == 201, invitacion.text

    acceso = e.pedir(
        "POST", f"/v1/personas-cuidadas/{familia.persona.id}/plan/accesos-relevo", familia.admin, familia,
        {"nombre_relevo": "Rosa", "telefono_relevo": "+56 9 5555 0137", "motivo": "turno_de_noche",
         "relevo_informado": True},
    )
    assert acceso.status_code == 201, acceso.text

    return FamiliaSembrada(familia=familia, valores={
        "grupo_id": str(familia.grupo.id),
        "persona_id": str(familia.persona.id),
        "pedido_id": str(pedido_id),
        "pedido_pagado_id": str(primero.json()["id"]),
        "perfil_id": str(perfil_id),
        "alerta_id": str(alerta_id),
        "membresia_id": str(familia.miembros["observador"].membresia.id),
        "invitacion_id": str(invitacion.json()["id"]),
        "acceso_id": str(acceso.json()["id"]),
        "campo": "rutina",
        "seccion": "alimentacion",
        "finalidad": "plan_cuidado",
    })


# Cuerpos válidos para cada escritura: el 404 no puede ser la sombra de un 422. Los que dependen de A son funciones
CUERPOS: dict[tuple[str, str], Any] = {
    ("POST", "/v1/grupos/{grupo_id}/personas-cuidadas"): {
        "nombre": "Persona Sintética", "nombre_pila": "Persona", "nivel_apoyo": "apoyo_parcial",
        "calidad_otorgante": "titular",
    },
    ("POST", "/v1/grupos/{grupo_id}/invitaciones"): {"rol": "cuidador"},
    ("PATCH", "/v1/grupos/{grupo_id}/miembros/{membresia_id}"): {"rol": "cuidador"},
    ("POST", "/v1/personas-cuidadas/{persona_id}/consentimientos"): {
        "finalidad": "consumo", "calidad_otorgante": "titular",
    },
    ("PUT", "/v1/personas-cuidadas/{persona_id}/direccion"): {
        "calle": "Calle de Prueba", "numero": "123", "comuna": "Comuna Sintética",
    },
    ("PUT", "/v1/personas-cuidadas/{persona_id}/plan/ficha/{campo}"): {"texto": "Texto sintético"},
    ("PUT", "/v1/personas-cuidadas/{persona_id}/plan/secciones/{seccion}"): {"texto": "Texto sintético"},
    ("POST", "/v1/personas-cuidadas/{persona_id}/plan/accesos-relevo"): {
        "nombre_relevo": "Rosa", "telefono_relevo": "+56 9 5555 0137", "motivo": "turno_de_noche",
        "relevo_informado": True,
    },
    ("POST", "/v1/personas-cuidadas/{persona_id}/consumo"): {
        "nombre_libre": "Insumo sintético", "unidad": "unidad", "tasa_unidades": 1, "tasa_dias": 1,
        "stock_unidades": 10,
    },
    ("PATCH", "/v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}"): {"stock_unidades": 5},
    ("POST", "/v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}/reponer"): {"cantidad": 5},
    ("POST", "/v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}/recontar"): {"stock_unidades": 5},
    ("POST", "/v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}/resolver"): {"cantidad": 5},
    ("POST", "/v1/personas-cuidadas/{persona_id}/pedidos"): lambda e: {
        "lineas": [{"oferta_id": e.pedido.oferta("panal", "uno"), "cantidad": 1}]},
    ("PUT", "/v1/pedidos/{pedido_id}/lineas"): lambda e: {
        "lineas": [{"oferta_id": e.pedido.oferta("panal", "uno"), "cantidad": 2}]},
    ("PUT", "/v1/pedidos/{pedido_id}/reglas-faltante"): {"reglas": []},
    ("POST", "/v1/pedidos/{pedido_id}/confirmar"): {"telefono_contacto": "+56 9 5555 0177"},
    ("PUT", "/v1/pedidos/{pedido_id}/contacto"): {"telefono_contacto": "+56 9 5555 0177"},
    ("POST", "/v1/pedidos/{pedido_id}/pagar"): {
        "acepta_condiciones": True, "condiciones": {"version": "0.3", "huella": "a" * 64}},
    ("POST", "/v1/pedidos/{pedido_id}/retractos"): lambda e: {
        "lineas": [{"linea_id": str(uuid.uuid4()), "cantidad": 1}]},
}


@pytest.fixture
def entorno(
    entorno_iam: EntornoIam,
    catalogo_sintetico: CatalogoSintetico,  # noqa: F811
    existencias: Existencias,
    pasarela_falsa: PasarelaFalsa,
) -> Iterator[Entorno]:
    fabrica = Fabrica(pepper=entorno_iam.pepper)
    pedido = EntornoPedido(iam=entorno_iam, fabrica=fabrica, catalogo=catalogo_sintetico, existencias=existencias)
    try:
        yield Entorno(pedido=pedido, a=_sembrar_a(pedido, pasarela_falsa), b=fabrica.familia())
    finally:
        fabrica.limpiar()


# --- Las pruebas ---------------------------------------------------------------------------------------------------


def test_toda_ruta_con_parametro_esta_clasificada(entorno: Entorno) -> None:
    """Una ruta nueva con parámetro tiene que entrar en RECURSO_DE_GRUPO o en EXCEPCIONES, con su motivo."""
    app = entorno.iam.cliente.app
    assert isinstance(app, FastAPI)
    rutas = rutas_con_parametro(app)

    sin_clasificar = sorted(rutas - RECURSO_DE_GRUPO - set(EXCEPCIONES))
    assert not sin_clasificar, f"Rutas con parámetro sin clasificar en {__name__}: {sin_clasificar}"
    # Lo clasificado existe: una ruta quitada o renombrada sale de las listas
    assert not sorted((RECURSO_DE_GRUPO | set(EXCEPCIONES)) - rutas)
    assert not RECURSO_DE_GRUPO & set(EXCEPCIONES)
    assert all(motivo.strip() for motivo in EXCEPCIONES.values())
    # Cada parámetro de un recurso de grupo tiene su valor sembrado en A
    parametros = {nombre for _, ruta in RECURSO_DE_GRUPO for nombre in PARAMETRO.findall(ruta)}
    assert parametros <= set(entorno.a.valores)


@pytest.mark.parametrize("grupo_de_la_cabecera", ["propio", "ajeno"])
def test_desde_otro_grupo_toda_ruta_de_un_recurso_de_grupo_responde_404(
    entorno: Entorno, grupo_de_la_cabecera: str
) -> None:
    """El admin de B pide cada recurso de A con su propio X-Grupo-Id y con el de A: siempre 404, nunca 403 ni 2xx.
    Las lecturas van primero y las escrituras después, en orden fijo, para que una escritura que se colara no cambie
    lo que ven las siguientes."""
    b = entorno.b
    grupo = b.grupo.id if grupo_de_la_cabecera == "propio" else entorno.a.familia.grupo.id
    nombres_de_a = (entorno.a.familia.grupo.nombre, entorno.a.familia.persona.nombre)
    antes = huella_de_a(entorno.a.familia.grupo.id)
    vacia = huella_de_a(uuid.uuid4())
    assert antes["persona_cuidada"] != vacia["persona_cuidada"] and antes["pedido"] != vacia["pedido"]  # mira filas
    distintas: dict[str, str] = {}
    for metodo, plantilla in sorted(RECURSO_DE_GRUPO, key=lambda r: (r[0] not in METODOS_DE_LECTURA, r)):
        respuesta = entorno.pedir(metodo, plantilla, b.admin, grupo)
        clave = f"{metodo} {plantilla}"
        if respuesta.status_code != 404:
            distintas[clave] = f"{respuesta.status_code} {respuesta.text[:200]}"
            continue
        if not respuesta.headers["content-type"].startswith(PROBLEMA):
            distintas[clave] = f"404 sin problem+json: {respuesta.headers['content-type']}"
            continue
        if any(nombre in respuesta.text for nombre in nombres_de_a):
            distintas[clave] = "404 con un nombre de A en el cuerpo"
    assert not distintas, json.dumps(distintas, ensure_ascii=False, indent=2)
    # Ninguna petición de B cambió una fila de A
    despues = huella_de_a(entorno.a.familia.grupo.id)
    cambiadas = sorted(t for t in antes.keys() | despues.keys() if antes.get(t) != despues.get(t))
    assert not cambiadas, f"las peticiones de B cambiaron filas de A en: {cambiadas}"


def test_control_cada_valor_sembrado_existe_es_de_a_y_esta_vigente(entorno: Entorno) -> None:
    """Sin este control, un id que no existe respondería 404 y la prueba de arriba pasaría en vacío. Cubre también los
    que solo aparecen en escrituras, como acceso_id en DELETE /v1/accesos-relevo/{acceso_id}."""
    parametros = {nombre for _, ruta in RECURSO_DE_GRUPO for nombre in PARAMETRO.findall(ruta)}
    assert parametros | {"pedido_pagado_id"} == set(EXISTE)
    grupo = str(entorno.a.familia.grupo.id)
    no_existen = sorted(n for n, sql in EXISTE.items() if not _existe(sql, entorno.a.valores[n], grupo))
    assert not no_existen, f"valores sembrados que no existen en A o no están vigentes: {no_existen}"


def test_control_el_admin_de_a_si_alcanza_sus_lecturas(entorno: Entorno) -> None:
    """Sin este control, un id mal sembrado también respondería 404 y la prueba de arriba pasaría en vacío. Cada
    lectura responde 200, su código exitoso en el contrato: un 500 o un 403 tampoco sirven de control."""
    a = entorno.a.familia
    no_alcanza: dict[str, str] = {}
    for metodo, plantilla in sorted(r for r in RECURSO_DE_GRUPO if r[0] in METODOS_DE_LECTURA):
        respuesta = entorno.pedir(metodo, plantilla, a.admin, a.grupo.id)
        if respuesta.status_code != 200:
            no_alcanza[plantilla] = f"{respuesta.status_code} {respuesta.text[:200]}"
    assert not no_alcanza, json.dumps(no_alcanza, ensure_ascii=False, indent=2)
