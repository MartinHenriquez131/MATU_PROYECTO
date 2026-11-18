"""La familia después de pagar: «Tus pedidos» (MATU-92), cancelar con devolución (R15, D-63-11) y el retracto (R3,
D-63-9 y D-63-10). Decisiones 422 a 424 y 436 en adelante.

    GET  /v1/personas-cuidadas/{persona_id}/pedidos       los cuatro roles (el observador, su vista). 200
    GET  /v1/pedidos/{pedido_id}/seguimiento              admin, cuidador, pagador y el observador que pagó. 200
    POST /v1/pedidos/{pedido_id}/cancelar-con-devolucion  admin. Idempotency-Key. 200
    GET  /v1/pedidos/{pedido_id}/retractos                admin, cuidador, pagador y el observador que pagó. 200
    POST /v1/pedidos/{pedido_id}/retractos                admin o quien pagó, en cualquier rol. Idempotency-Key. 201

Viven en backoffice porque orquestan el despacho (fulfillment) y la devolución (payments). Un rol que no alcanza, un
pedido o una persona de otro grupo, una persona eliminada, un pedido vencido (2 años desde el cierre) o un id que no
es UUID: 404, nunca 403. No piden la autorización despacho (C1). Cache-Control: no-store (prefijos /v1/pedidos y
/v1/personas-cuidadas/ en app.main). Nada del pedido, los montos ni la Idempotency-Key van a los logs (C23).

- cancelar-con-devolucion: solo el admin, mientras ningún comercio empezó a preparar. La transacción del sistema
  bloquea el pedido como comercio_preparar, cancela las partes y devuelve todo, envío incluido, a la misma tarjeta.
  Orden: 401, 404, 428, 422 (cabecera), idempotencia, 503, 409 estado-pedido (ya cancelado, C11) o ya-se-prepara.
- retractos: el admin, o quien pagó si sigue en el grupo, dentro de los 10 días hábiles desde la entrega. Orden: 401,
  404 (C6 revisado en MATU-116: quien no es admin y no pagó este pedido, también el observador; lo dice la base), 428,
  422, idempotencia, 404 (sin entregar), 409 fuera-de-plazo, 422 producto-no-retractable y 201.
- MATU-116 (J1, C5; decisión 475): el observador que pagó un pedido lo ve en la lista con la fila «pagaste», tiene su
  detalle (puede_cancelar siempre false, con su motivo) y puede arrepentirse. De los pedidos que no pagó, la fila
  «se_informa» y 404 en el resto.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Request, Response, status
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import obtener_fabrica_sesiones
from app.core.errores import ErrorMATU
from app.modules.backoffice.api import vistas_familia as vistas
from app.modules.backoffice.api.esquemas import (
    EstadoPedidoVista,
    ListaPedidosPagados,
    ListaPedidosPagadosObservador,
    RetractosDelPedido,
    RetractoVistaFamilia,
    SeguimientoPedido,
    SeguimientoPedidoPagaste,
    SolicitudRetracto,
)
from app.modules.backoffice.application import pedidos_familia as tus_pedidos
from app.modules.backoffice.application.despacho import NoCancelable, cancelar_pagado
from app.modules.backoffice.infrastructure.lectura_pedidos import LecturaPedidosSQL
from app.modules.backoffice.infrastructure.sistema import AbrirDespachoSQL
from app.modules.care_circle.api.dependencias import SesionDeGrupo
from app.modules.care_circle.api.router_autorizaciones import RelojDep
from app.modules.fulfillment.domain.despacho import CANCELADOS
from app.modules.ordering.api.router import Clave, Idempotencia, Llave, reservar_clave_con_vencimiento
from app.modules.ordering.application.pedidos import Actor
from app.modules.payments.application import retractos as casos
from app.modules.payments.application.ports import PasarelaWebpay, Unidad
from app.modules.payments.domain.retracto import RetractoInvalido
from app.modules.payments.infrastructure.pasarela import obtener_pasarela
from app.modules.payments.infrastructure.repositorio_pagos import RepositorioPagosSQL
from app.modules.payments.infrastructure.repositorio_retractos import RepositorioRetractosSQL
from app.shared.auditoria_sql import RegistroAuditoriaSql

router = APIRouter(tags=["pedidos"])

_PROBLEMA: dict[str, Any] = {"content": {"application/problem+json": {}}}
_ID = Annotated[str, Path(json_schema_extra={"format": "uuid"})]
Fabrica = Annotated[sessionmaker[Session], Depends(obtener_fabrica_sesiones)]
PasarelaDep = Annotated[PasarelaWebpay | None, Depends(obtener_pasarela)]
_RESPUESTAS: dict[int | str, dict[str, Any]] = {
    401: {"description": "no-autenticado o token-invalido", **_PROBLEMA},
    404: {
        "description": "El rol no alcanza, o el pedido no es del grupo, es de una persona eliminada, venció o no se"
        " entregó",
        **_PROBLEMA,
    },
}
_IDEMPOTENCIA: dict[int | str, dict[str, Any]] = {
    428: {"description": "/errores/falta-idempotencia", **_PROBLEMA},
    422: {"description": "Idempotency-Key o cuerpo inválidos, o /errores/idempotencia-reutilizada", **_PROBLEMA},
}
_EN_CURSO = "/errores/idempotencia-en-curso: una petición con la misma clave todavía no termina"
Vista = ListaPedidosPagados | ListaPedidosPagadosObservador
# Namespace fijo de los retractos de una Idempotency-Key: la repetición encuentra el mismo retracto (C8)
_NAMESPACE_RETRACTO = uuid.UUID("5f0e2c43-9a1d-4b8e-8c39-2d7b6a1e9f04")
_EPOCA = datetime(1970, 1, 1, tzinfo=UTC)


def _uuid(valor: str) -> uuid.UUID:
    try:
        return uuid.UUID(valor)
    except ValueError:
        raise ErrorMATU(404) from None


def _lectura(contexto: SesionDeGrupo) -> LecturaPedidosSQL:
    return LecturaPedidosSQL(contexto.sesion, contexto.grupo_id)


def _unidad(contexto: SesionDeGrupo, reloj: RelojDep) -> Unidad:
    return Unidad(RepositorioPagosSQL(contexto.sesion, contexto.grupo_id), RegistroAuditoriaSql(contexto.sesion, reloj))


def _actor(request: Request, contexto: SesionDeGrupo) -> Actor:
    return Actor(
        usuario_id=contexto.usuario_id,
        grupo_id=contexto.grupo_id,
        rol=contexto.rol,
        request_id=getattr(request.state, "request_id", None),
    )


# --- Tus pedidos ---------------------------------------------------------------------------------------------------


@router.get(
    "/personas-cuidadas/{persona_id}/pedidos",
    response_model=Vista,
    responses={**_RESPUESTAS, 422: {"description": "cursor inválido o limite fuera de 1 a 100", **_PROBLEMA}},
    summary="«Tus pedidos»: los pedidos pagados de la persona, de los últimos 2 años",
    description=(
        "MATU-92 (D-92-1 y D-92-2). Los cuatro roles, sin la autorización despacho ni puede_ver_plan (C1 y C2)."
        " admin, cuidador y pagador: ListaPedidosPagados, con el total, lo devuelto, el estado para la familia y lo"
        " que se puede hacer (puede_cancelar y puede_arrepentirse con su motivo, C7). observador:"
        " ListaPedidosPagadosObservador, la fecha del pago, el estado para la familia, entregado_en y los productos,"
        " sin ningún monto (C3; MATU-113, decisión 472), con vista = se_informa; y en los pedidos que pagó, la fila de"
        " quien paga con puede_cancelar en false, con vista = pagaste (MATU-116, C5). Del más reciente al más antiguo;"
        " sin los que cumplieron 2 años desde la entrega o la cancelación. Paginada con cursor opaco. No se audita."
        " Capa 3"
    ),
)
def listar_pedidos(
    response: Response,
    contexto: SesionDeGrupo,
    persona_id: _ID,
    reloj: RelojDep,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limite: Annotated[int, Query(ge=1, le=tus_pedidos.LIMITE_MAXIMO)] = tus_pedidos.LIMITE_POR_OMISION,
) -> Vista:
    persona = _uuid(persona_id)
    despues_de = None if cursor is None else vistas.decodificar_cursor(cursor)
    try:
        pagina = tus_pedidos.listar(
            _lectura(contexto), contexto.rol, contexto.usuario_id, persona, reloj.ahora(), despues_de, limite
        )
    except tus_pedidos.PedidoNoEncontrado:
        raise ErrorMATU(404) from None
    response.headers["Cache-Control"] = "no-store"
    siguiente = None if pagina.siguiente is None else vistas.codificar_cursor(pagina.siguiente)
    if not pagina.ve_el_pago:
        return ListaPedidosPagadosObservador(
            items=[vistas.fila_pagaste(p) if p.pagaste else vistas.fila_observador(p) for p in pagina.pedidos],
            siguiente_cursor=siguiente,
        )
    return ListaPedidosPagados(items=[vistas.fila(p) for p in pagina.pedidos], siguiente_cursor=siguiente)


@router.get(
    "/pedidos/{pedido_id}/seguimiento",
    response_model=SeguimientoPedido | SeguimientoPedidoPagaste,
    responses=_RESPUESTAS,
    summary="Cómo va un pedido pagado, por comercio",
    description=(
        "MATU-92 (ruta 2). admin, cuidador y pagador: SeguimientoPedido. El observador que pagó el pedido:"
        " SeguimientoPedidoPagaste, con puede_cancelar en false (MATU-116, C5); de uno que no pagó, no tiene"
        " detalle (404,"
        " D-92-1 a). Cada parte con el"
        " nombre de fantasía del comercio, su estado y cancelada_por; cada línea con unidades_faltantes. Nunca el"
        " código de retiro, la referencia de la parte ni la cuenta del encargado (C15). El comprobante es GET …/pago"
        " (C14). No se audita. Capa 3"
    ),
)
def ver_seguimiento(
    response: Response, pedido_id: _ID, contexto: SesionDeGrupo, reloj: RelojDep
) -> SeguimientoPedido | SeguimientoPedidoPagaste:
    try:
        pedido = tus_pedidos.seguimiento(
            _lectura(contexto), contexto.rol, contexto.usuario_id, _uuid(pedido_id), reloj.ahora()
        )
    except tus_pedidos.PedidoNoEncontrado:
        raise ErrorMATU(404) from None
    response.headers["Cache-Control"] = "no-store"
    return vistas.seguimiento(pedido)


# --- Cancelar con devolución (R15) ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class PedidoDeLaFamilia:
    actor: Actor
    pedido_id: uuid.UUID


def _pedido_para_cancelar(request: Request, contexto: SesionDeGrupo, pedido_id: _ID) -> PedidoDeLaFamilia:
    """404 antes de la cabecera y el cuerpo: solo el admin, y un pedido del grupo."""
    if contexto.rol != "admin":
        raise ErrorMATU(404)
    identificador = _uuid(pedido_id)
    if RepositorioRetractosSQL(contexto.sesion, contexto.grupo_id).pedido(identificador) is None:
        raise ErrorMATU(404)
    return PedidoDeLaFamilia(_actor(request, contexto), identificador)


def _pedido_para_retracto(request: Request, contexto: SesionDeGrupo, pedido_id: _ID) -> PedidoDeLaFamilia:
    """C6, revisado en MATU-116 (C5): quien no es admin tiene que haber pagado el pedido, en cualquier rol, también el
    observador. Si no, 404 antes de la cabecera y el cuerpo. La base lo vuelve a exigir (retracto_familia_crear)."""
    if contexto.rol not in tus_pedidos.ROLES_QUE_LEEN:
        raise ErrorMATU(404)
    identificador = _uuid(pedido_id)
    if contexto.rol != "admin":
        repositorio = RepositorioPagosSQL(contexto.sesion, contexto.grupo_id)
        cargo = repositorio.cargo_de(identificador)
        participacion = None if cargo is None else repositorio.participacion_de(cargo.id, contexto.usuario_id)
        if participacion is None or participacion.monto_cobrado <= 0:
            raise ErrorMATU(404)
    elif RepositorioRetractosSQL(contexto.sesion, contexto.grupo_id).pedido(identificador) is None:
        raise ErrorMATU(404)
    return PedidoDeLaFamilia(_actor(request, contexto), identificador)


@router.post(
    "/pedidos/{pedido_id}/cancelar-con-devolucion",
    response_model=EstadoPedidoVista,
    responses={
        **_RESPUESTAS,
        **_IDEMPOTENCIA,
        409: {
            "description": "/errores/estado-pedido (con estado): el pedido ya se canceló o no está pagado (C11);"
            " /errores/ya-se-prepara: un comercio empezó a preparar; o " + _EN_CURSO,
            **_PROBLEMA,
        },
        503: {"description": "Sin PASARELA_PAGO no se puede devolver: no se cancela", **_PROBLEMA},
    },
    description=(
        "R15 (D-63-11): el admin cancela un pedido pagado mientras ningún comercio empezó a preparar. Se devuelve todo,"
        " envío incluido, a la misma tarjeta, y las partes quedan canceladas. MATU-92: Idempotency-Key obligatoria"
        " (la repetición responde 200 con el estado actual, C8), y un pedido ya cancelado responde 409 estado-pedido"
        " (C11). Registra pedido.cancelar y pago.devolver. Capa 3"
    ),
)
def cancelar_con_devolucion(
    response: Response,
    pedido: Annotated[PedidoDeLaFamilia, Depends(_pedido_para_cancelar)],
    clave: Clave,
    contexto: SesionDeGrupo,
    idem: Idempotencia,
    llave: Llave,
    fabrica: Fabrica,
    reloj: RelojDep,
    pasarela: PasarelaDep,
) -> EstadoPedidoVista:
    endpoint = f"POST /v1/pedidos/{pedido.pedido_id}/cancelar-con-devolucion"
    repeticion, _ = reservar_clave_con_vencimiento(idem, endpoint, clave, pedido.actor, {}, reloj, llave)
    if repeticion is not None:
        actual = RepositorioRetractosSQL(contexto.sesion, contexto.grupo_id).pedido(pedido.pedido_id)
        if actual is None:
            raise ErrorMATU(404)
        response.status_code = repeticion.estado_http
        return EstadoPedidoVista(pedido_id=pedido.pedido_id, estado=actual.estado)
    if pasarela is None:
        raise ErrorMATU(503, tipo="pasarela-no-disponible", detalle="No se puede cancelar en este momento")
    with AbrirDespachoSQL(fabrica, reloj)(contexto.grupo_id) as (u, _):
        try:
            cancelar_pagado(u, pasarela, pedido.pedido_id, contexto.usuario_id, reloj.ahora())
        except NoCancelable as error:
            if not error.pagado or error.estado in CANCELADOS:
                raise ErrorMATU(
                    409,
                    tipo="estado-pedido",
                    detalle="El estado del pedido no permite esta acción",
                    extension={"estado": error.estado},
                ) from None
            raise ErrorMATU(
                409, tipo="ya-se-prepara", detalle="El comercio ya empezó a preparar el pedido: no se puede cancelar"
            ) from None
    idem.completar(endpoint, clave, status.HTTP_200_OK, pedido.pedido_id)
    return EstadoPedidoVista(pedido_id=pedido.pedido_id, estado="cancelado_con_devolucion")


# --- El retracto (R3) ----------------------------------------------------------------------------------------------


@router.get(
    "/pedidos/{pedido_id}/retractos",
    response_model=RetractosDelPedido,
    responses=_RESPUESTAS,
    description=(
        "Hasta cuándo se puede pedir el retracto (fecha exacta, D-63-9) y los retractos pedidos. MATU-92 (rutas 3 y"
        " 4): por línea, lo entregado, lo ya pedido, lo disponible, el precio pagado y si se pierde al abrir; si"
        " devolver todo incluye el envío; plazo_correo_hasta (C22); puede_arrepentirse con su motivo (C7); y en cada"
        " retracto sus líneas, es_tuyo (C18), origen (C21) y resuelto_en. admin, cuidador y pagador, y el observador"
        " que pagó el pedido (MATU-116, C5); pedido entregado. No se audita. Capa 3"
    ),
)
def ver_retractos(pedido_id: _ID, contexto: SesionDeGrupo, reloj: RelojDep) -> RetractosDelPedido:
    identificador = _uuid(pedido_id)
    try:
        detalle = tus_pedidos.para_devolver(
            _lectura(contexto), contexto.rol, contexto.usuario_id, identificador, reloj.ahora()
        )
    except tus_pedidos.PedidoNoEncontrado:
        raise ErrorMATU(404) from None
    retractos = RepositorioRetractosSQL(contexto.sesion, contexto.grupo_id)
    unidad = _unidad(contexto, reloj)
    acciones = detalle.pedido.acciones
    assert acciones is not None and acciones.plazo_hasta is not None and acciones.plazo_correo_hasta is not None
    c = detalle.pedido.cabecera
    return RetractosDelPedido(
        plazo_hasta=acciones.plazo_hasta.astimezone(UTC),
        plazo_correo_hasta=acciones.plazo_correo_hasta.astimezone(UTC),
        puede_arrepentirse=acciones.puede_arrepentirse,
        arrepentirse_motivo=None if acciones.motivo_arrepentirse is None else acciones.motivo_arrepentirse.value,
        condiciones_version=c.condiciones_version,
        costo_envio=c.costo_envio,
        incluye_envio_si_todo=detalle.incluye_envio_si_todo,
        lineas=[vistas.linea_para_retracto(x.linea, x.ya_pedidas, x.disponibles) for x in detalle.lineas],
        retractos=[
            vistas.retracto_familia(unidad, retractos, r, contexto.usuario_id) for r in retractos.de_pedido(c.id)
        ],
    )


def _retracto_de_la_clave(contexto: SesionDeGrupo, endpoint: str, clave: str, vence: datetime) -> uuid.UUID:
    """El id del retracto de esta reserva de la clave: el mismo en la repetición, otro si la clave venció y se
    reservó de nuevo. La clave no se guarda ni se puede recuperar del id."""
    instante = (vence.astimezone(UTC) - _EPOCA) // timedelta(microseconds=1)
    semilla = f"{contexto.grupo_id}|{contexto.usuario_id}|{endpoint}|{clave}|{instante}"
    return uuid.uuid5(_NAMESPACE_RETRACTO, semilla)


@router.post(
    "/pedidos/{pedido_id}/retractos",
    response_model=RetractoVistaFamilia,
    status_code=status.HTTP_201_CREATED,
    responses={
        **_RESPUESTAS,
        **_IDEMPOTENCIA,
        409: {
            "description": "/errores/fuera-de-plazo: pasaron los 10 días hábiles (extensión plazo_hasta); o "
            + _EN_CURSO,
            **_PROBLEMA,
        },
        422: {
            "description": "/errores/producto-no-retractable: un producto no se entregó, ya se pidió o la cantidad no"
            " calza; Idempotency-Key o cuerpo inválidos; o /errores/idempotencia-reutilizada",
            **_PROBLEMA,
        },
    },
    description=(
        "R3: «Arrepentirme de la compra». El admin, o quien pagó si sigue en el grupo en cualquier rol (MATU-116, C5),"
        " elige los productos y cuántos."
        " Se devuelven a precio pagado, y el envío según las condiciones aceptadas (D-63-10), cuando MATU recibe el"
        " producto con el sello intacto. MATU-92: quien no pagó y no es admin recibe 404 (C6);"
        " Idempotency-Key obligatoria (la"
        " repetición responde 201 con el mismo retracto, C8); el pedido se bloquea antes de leer lo ya pedido, y dos"
        " solicitudes a la vez no piden más de lo entregado. Registra pedido.retracto_solicitar. Capa 3"
    ),
)
def pedir_retracto(
    response: Response,
    pedido: Annotated[PedidoDeLaFamilia, Depends(_pedido_para_retracto)],
    clave: Clave,
    solicitud: SolicitudRetracto,
    contexto: SesionDeGrupo,
    idem: Idempotencia,
    llave: Llave,
    reloj: RelojDep,
) -> RetractoVistaFamilia:
    endpoint = f"POST /v1/pedidos/{pedido.pedido_id}/retractos"
    repeticion, vence = reservar_clave_con_vencimiento(
        idem, endpoint, clave, pedido.actor, solicitud.model_dump(mode="json"), reloj, llave
    )
    retracto_id = _retracto_de_la_clave(contexto, endpoint, clave, vence)
    unidad = _unidad(contexto, reloj)
    retractos = RepositorioRetractosSQL(contexto.sesion, contexto.grupo_id)
    if repeticion is not None:
        repetido = retractos.retracto(retracto_id)
        if repetido is None:
            raise ErrorMATU(404)
        response.status_code = repeticion.estado_http
        return vistas.retracto_familia(unidad, retractos, repetido, contexto.usuario_id)
    pedidas: dict[uuid.UUID, int] = {}
    for linea in solicitud.lineas:
        pedidas[linea.linea_id] = pedidas.get(linea.linea_id, 0) + linea.cantidad
    try:
        r = casos.solicitar(
            unidad,
            retractos,
            contexto.grupo_id,
            pedido.pedido_id,
            contexto.usuario_id,
            pedidas,
            reloj.ahora(),
            retracto_id=retracto_id,
        )
    except casos.SinPedidoEntregado:
        raise ErrorMATU(404) from None
    except casos.FueraDePlazo as error:
        raise ErrorMATU(
            409, tipo="fuera-de-plazo", detalle="Pasó el plazo para arrepentirse de la compra",
            extension={"plazo_hasta": error.plazo.isoformat()},
        ) from None
    except RetractoInvalido:
        raise ErrorMATU(
            422, tipo="producto-no-retractable", detalle="Elige productos entregados, hasta la cantidad que llegó"
        ) from None
    idem.completar(endpoint, clave, status.HTTP_201_CREATED, pedido.pedido_id)
    return vistas.retracto_familia(unidad, retractos, r, contexto.usuario_id)
