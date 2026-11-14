"""La familia después de pagar: cancelar con devolución (R15, D-63-11) y el retracto (R3, D-63-9 y D-63-10), sin
pantalla todavía (MATU-92). Decisiones 422 a 424.

Viven en backoffice porque orquestan el despacho (fulfillment) y la devolución (payments). Un rol que no alcanza, o un
pedido de otro grupo: 404. Cache-Control: no-store (prefijo /v1/pedidos en app.main).

- cancelar-con-devolucion: solo el admin, mientras ningún comercio empezó a preparar. La transacción del sistema
  bloquea el pedido como comercio_preparar, cancela las partes y devuelve todo, envío incluido, a la misma tarjeta.
- retractos: el admin, o quien pagó si sigue en el grupo, dentro de los 10 días hábiles desde la entrega.
"""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import obtener_fabrica_sesiones
from app.core.errores import ErrorMATU
from app.modules.backoffice.api.esquemas import (
    EstadoPedidoVista,
    RetractosDelPedido,
    RetractoVista,
    SolicitudRetracto,
)
from app.modules.backoffice.application.despacho import NoCancelable, cancelar_pagado
from app.modules.backoffice.infrastructure.sistema import AbrirDespachoSQL
from app.modules.care_circle.api.dependencias import SesionDeGrupo
from app.modules.care_circle.api.router_autorizaciones import RelojDep
from app.modules.payments.application import retractos as casos
from app.modules.payments.application.ports import PasarelaWebpay, Unidad
from app.modules.payments.domain.retracto import RetractoInvalido, plazo_retracto
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
    404: {"description": "El rol no alcanza, o el pedido no es del grupo o no se entregó", **_PROBLEMA},
}


def _uuid(valor: str) -> uuid.UUID:
    try:
        return uuid.UUID(valor)
    except ValueError:
        raise ErrorMATU(404) from None


@router.post(
    "/pedidos/{pedido_id}/cancelar-con-devolucion",
    response_model=EstadoPedidoVista,
    responses={
        **_RESPUESTAS,
        409: {"description": "ya-se-prepara: un comercio empezó a preparar, o el pedido no está pagado", **_PROBLEMA},
        503: {"description": "Sin PASARELA_PAGO no se puede devolver: no se cancela", **_PROBLEMA},
    },
    description=(
        "R15 (D-63-11): el admin cancela un pedido pagado mientras ningún comercio empezó a preparar. Se devuelve todo,"
        " envío incluido, a la misma tarjeta, y las partes quedan canceladas. Pantalla en MATU-92."
    ),
)
def cancelar_con_devolucion(
    pedido_id: _ID, contexto: SesionDeGrupo, fabrica: Fabrica, reloj: RelojDep, pasarela: PasarelaDep
) -> EstadoPedidoVista:
    if contexto.rol != "admin":
        raise ErrorMATU(404)
    identificador = _uuid(pedido_id)
    if RepositorioRetractosSQL(contexto.sesion, contexto.grupo_id).pedido(identificador) is None:
        raise ErrorMATU(404)
    if pasarela is None:
        raise ErrorMATU(503, tipo="pasarela-no-disponible", detalle="No se puede cancelar en este momento")
    with AbrirDespachoSQL(fabrica, reloj)(contexto.grupo_id) as (u, _):
        try:
            cancelar_pagado(u, pasarela, identificador, contexto.usuario_id, reloj.ahora())
        except NoCancelable:
            raise ErrorMATU(
                409, tipo="ya-se-prepara", detalle="El comercio ya empezó a preparar el pedido: no se puede cancelar"
            ) from None
    return EstadoPedidoVista(pedido_id=identificador, estado="cancelado_con_devolucion")


def _vista(r: casos.Retracto, monto: int) -> RetractoVista:
    return RetractoVista(
        id=r.id, pedido_id=r.pedido_id, estado=r.estado,  # type: ignore[arg-type]
        solicitado_en=r.solicitado_en, plazo_hasta=r.plazo_hasta, incluye_envio=r.incluye_envio, monto=monto,
    )


def _unidad(contexto: SesionDeGrupo, reloj: RelojDep) -> Unidad:
    return Unidad(RepositorioPagosSQL(contexto.sesion, contexto.grupo_id), RegistroAuditoriaSql(contexto.sesion, reloj))


@router.get(
    "/pedidos/{pedido_id}/retractos",
    response_model=RetractosDelPedido,
    responses=_RESPUESTAS,
    description="Hasta cuándo se puede pedir el retracto (fecha exacta, D-63-9) y los retractos pedidos. MATU-92.",
)
def ver_retractos(pedido_id: _ID, contexto: SesionDeGrupo, reloj: RelojDep) -> RetractosDelPedido:
    if contexto.rol == "observador":
        raise ErrorMATU(404)
    identificador = _uuid(pedido_id)
    retractos = RepositorioRetractosSQL(contexto.sesion, contexto.grupo_id)
    pedido = retractos.pedido(identificador)
    if pedido is None or pedido.entregado_en is None:
        raise ErrorMATU(404)
    unidad = _unidad(contexto, reloj)
    lista = [r for r in (retractos.retracto(x) for x in _ids_de(contexto, identificador)) if r is not None]
    return RetractosDelPedido(
        plazo_hasta=plazo_retracto(pedido.entregado_en),
        retractos=[_vista(r, casos.monto_de(unidad, retractos, r)) for r in lista],
    )


def _ids_de(contexto: SesionDeGrupo, pedido_id: uuid.UUID) -> list[uuid.UUID]:
    filas = contexto.sesion.execute(
        text("SELECT id FROM retracto WHERE pedido_id = :p ORDER BY solicitado_en, id"), {"p": pedido_id}
    )
    return [f.id for f in filas]


@router.post(
    "/pedidos/{pedido_id}/retractos",
    response_model=RetractoVista,
    status_code=status.HTTP_201_CREATED,
    responses={
        **_RESPUESTAS,
        409: {"description": "fuera-de-plazo: pasaron los 10 días hábiles (extensión plazo_hasta)", **_PROBLEMA},
        422: {"description": "producto-no-retractable: un producto no se entregó, ya se pidió o la cantidad no calza",
              **_PROBLEMA},
    },
    description=(
        "R3: «Arrepentirme de la compra». El admin, o quien pagó si sigue en el grupo, elige los productos y cuántos."
        " Se devuelven a precio pagado, y el envío según las condiciones aceptadas (D-63-10), cuando MATU recibe el"
        " producto con el sello intacto. Pantalla en MATU-92."
    ),
)
def pedir_retracto(
    pedido_id: _ID, solicitud: SolicitudRetracto, contexto: SesionDeGrupo, reloj: RelojDep
) -> RetractoVista:
    identificador = _uuid(pedido_id)
    unidad = _unidad(contexto, reloj)
    if contexto.rol != "admin":
        cargo = unidad.repositorio.cargo_de(identificador)
        participacion = None if cargo is None else unidad.repositorio.participacion_de(cargo.id, contexto.usuario_id)
        if participacion is None or participacion.monto_cobrado <= 0:
            raise ErrorMATU(404)
    pedidas: dict[uuid.UUID, int] = {}
    for linea in solicitud.lineas:
        pedidas[linea.linea_id] = pedidas.get(linea.linea_id, 0) + linea.cantidad
    retractos = RepositorioRetractosSQL(contexto.sesion, contexto.grupo_id)
    try:
        r = casos.solicitar(
            unidad, retractos, contexto.grupo_id, identificador, contexto.usuario_id, pedidas, reloj.ahora()
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
    return _vista(r, casos.monto_de(unidad, retractos, r))
