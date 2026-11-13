"""Las rutas de operación del despacho (MATU-63; D-63-5, D-63-6, D-63-10; decisiones 417 a 421). La pantalla es de
MATU-81: mientras tanto, en la demo se opera por estas rutas.

Solo una cuenta con usuario.es_operacion; otra: 404. Cada acción corre con app.rol = 'operacion' y el grupo del pedido,
sin cuenta (trigger pedido_escritura_del_pago), y se audita con la cuenta de quien opera y la persona del pedido.

- POST …/partes/{id}/codigo genera o regenera el código de una parte lista y lo devuelve **una sola vez**: la base
  guarda solo su HMAC. Regenerar borra el uso, los intentos y el bloqueo anteriores (D-63-4).
- «En camino», «entregado» (fija entregado_en, el inicio del retracto, y registra lo que MATU debe a cada comercio,
  RF-31) y «no entregado» (D-63-6).
- Resolver un retracto: devolver a la misma tarjeta o rechazar (D-63-10).
"""

import secrets
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Request, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import obtener_fabrica_sesiones, sesion_tenant
from app.core.errores import ErrorMATU
from app.modules.backoffice.api.dependencias import Operador, SecretoCodigo
from app.modules.backoffice.api.esquemas import (
    CodigoGenerado,
    EstadoPedidoVista,
    ListaPedidosOperacion,
    ListaRetractos,
    ParteOperacion,
    PedidoOperacion,
    RetractoVista,
    SolicitudResolverRetracto,
)
from app.modules.backoffice.application.despacho import UnidadDespacho
from app.modules.backoffice.infrastructure.sistema import AbrirDespachoSQL
from app.modules.care_circle.api.router_autorizaciones import RelojDep
from app.modules.fulfillment.domain.despacho import (
    CIFRAS_CODIGO,
    EN_CAMINO_DESDE,
    ENTREGADO_DESDE,
    NO_ENTREGADO_DESDE,
    VIDA_CODIGO,
    EstadoParte,
    estado_codigo,
    huella_codigo,
    monto_consumo,
)
from app.modules.payments.application import retractos as casos_retracto
from app.modules.payments.application.ports import PasarelaWebpay
from app.modules.payments.application.retractos import Retracto
from app.modules.payments.domain.cargo import DevolucionInvalida
from app.modules.payments.infrastructure.pasarela import obtener_pasarela
from app.modules.payments.infrastructure.repositorio_retractos import RepositorioRetractosSQL
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria

router = APIRouter(prefix="/operacion", tags=["operacion"])

_PROBLEMA: dict[str, Any] = {"content": {"application/problem+json": {}}}
_ID = Annotated[str, Path(json_schema_extra={"format": "uuid"})]
Fabrica = Annotated[sessionmaker[Session], Depends(obtener_fabrica_sesiones)]
PasarelaDep = Annotated[PasarelaWebpay | None, Depends(obtener_pasarela)]
_RESPUESTAS: dict[int | str, dict[str, Any]] = {
    401: {"description": "no-autenticado o token-invalido", **_PROBLEMA},
    404: {"description": "No es una cuenta de operación, o el pedido, la parte o el retracto no existen", **_PROBLEMA},
    409: {"description": "estado-pedido o estado-parte: el estado no permite la acción", **_PROBLEMA},
}

_PEDIDOS = text(
    "SELECT p.id, p.estado, p.referencia, p.entregado_en, pc.id AS parte_id, co.nombre_fantasia, pc.referencia AS"
    " referencia_parte, pc.estado AS estado_parte, pc.codigo_generado_en, pc.codigo_hash IS NOT NULL AS con_hash,"
    " pc.codigo_expira_en, pc.codigo_usado_en, pc.codigo_bloqueado_en"
    " FROM pedido p JOIN pedido_comercio pc ON pc.pedido_id = p.id JOIN comercio co ON co.id = pc.comercio_id"
    " WHERE p.pagado_en IS NOT NULL AND p.estado NOT IN ('cancelado', 'cancelado_con_devolucion', 'cerrado')"
    " ORDER BY p.pagado_en, p.id, pc.creado_en, pc.id"
)
_GRUPO_DE_PEDIDO = text("SELECT grupo_id FROM pedido WHERE id = :id")
_GRUPO_DE_PARTE = text("SELECT pedido_id, grupo_id FROM pedido_comercio WHERE id = :id")
_GRUPO_DE_RETRACTO = text("SELECT grupo_id FROM retracto WHERE id = :id")


def _uuid(valor: str) -> uuid.UUID:
    try:
        return uuid.UUID(valor)
    except ValueError:
        raise ErrorMATU(404) from None


def _consultar_grupo(fabrica: sessionmaker[Session], consulta: Any, identificador: uuid.UUID) -> Any:
    with sesion_tenant(fabrica, rol="operacion") as sesion:
        fila = sesion.execute(consulta, {"id": identificador}).first()
    if fila is None:
        raise ErrorMATU(404)
    return fila


def _auditar(u: UnidadDespacho, operador: uuid.UUID, accion: AccionAuditoria, entidad: EntidadAuditoria,
             entidad_id: uuid.UUID, grupo_id: uuid.UUID, persona_id: uuid.UUID, request: Request) -> None:
    u.pagos.registro.registrar(
        EntradaAuditoria(
            grupo_id=grupo_id,
            actor_tipo=ActorTipo.OPERACION,
            actor_ref=operador,
            accion=accion,
            entidad=entidad,
            entidad_id=entidad_id,
            persona_cuidada_id=persona_id,
            request_id=getattr(request.state, "request_id", None),
        )
    )


@router.get("/pedidos", response_model=ListaPedidosOperacion, responses=_RESPUESTAS,
            description="Los pedidos pagados en curso con sus partes y el estado del código de cada una.")
def listar_pedidos(_operador: Operador, fabrica: Fabrica, reloj: RelojDep) -> ListaPedidosOperacion:
    ahora = reloj.ahora()
    pedidos: dict[uuid.UUID, PedidoOperacion] = {}
    with sesion_tenant(fabrica, rol="operacion") as sesion:
        for f in sesion.execute(_PEDIDOS):
            pedido = pedidos.setdefault(
                f.id,
                PedidoOperacion(id=f.id, estado=f.estado, referencia=f.referencia, entregado_en=f.entregado_en,
                                partes=[]),
            )
            pedido.partes.append(
                ParteOperacion(
                    id=f.parte_id,
                    comercio=f.nombre_fantasia,
                    referencia=f.referencia_parte,
                    estado=f.estado_parte,
                    estado_codigo=estado_codigo(
                        generado_en=f.codigo_generado_en, con_hash=f.con_hash, expira_en=f.codigo_expira_en,
                        usado_en=f.codigo_usado_en, bloqueado_en=f.codigo_bloqueado_en, ahora=ahora,
                    ).value,
                )
            )
    return ListaPedidosOperacion(pedidos=list(pedidos.values()))


@router.post(
    "/partes/{parte_id}/codigo",
    response_model=CodigoGenerado,
    status_code=status.HTTP_201_CREATED,
    responses={**_RESPUESTAS, 503: {"description": "Falta CODIGO_RETIRO_SECRETO", **_PROBLEMA}},
    description=(
        "Genera (o regenera) el código de retiro de una parte lista y lo devuelve una sola vez (D-63-5). Vale 90"
        " minutos y sirve una vez. Quien retira por MATU lo muestra en el comercio; la familia no lo ve."
    ),
)
def generar_codigo(
    parte_id: _ID, request: Request, operador: Operador, fabrica: Fabrica, reloj: RelojDep, secreto: SecretoCodigo,
    respuesta: Response,
) -> CodigoGenerado:
    identificador = _uuid(parte_id)
    fila = _consultar_grupo(fabrica, _GRUPO_DE_PARTE, identificador)
    ahora = reloj.ahora()
    codigo = f"{secrets.randbelow(10**CIFRAS_CODIGO):0{CIFRAS_CODIGO}d}"
    with AbrirDespachoSQL(fabrica, reloj, rol="operacion")(fila.grupo_id) as (u, _):
        pedido = u.despacho.pedido(fila.pedido_id)
        assert pedido is not None
        guardado = u.despacho.guardar_codigo(
            identificador, huella_codigo(secreto, identificador, codigo), ahora, ahora + VIDA_CODIGO
        )
        if not guardado:
            raise ErrorMATU(409, tipo="estado-parte", detalle="La parte no está lista para retirar")
        _auditar(u, operador, AccionAuditoria.DESPACHO_CODIGO_GENERAR, EntidadAuditoria.PEDIDO_COMERCIO,
                 identificador, fila.grupo_id, pedido.persona_id, request)
    respuesta.headers["Cache-Control"] = "no-store"
    return CodigoGenerado(parte_id=identificador, codigo=codigo, expira_en=ahora + VIDA_CODIGO)


def _mover(
    fabrica: sessionmaker[Session], reloj: RelojDep, request: Request, operador: uuid.UUID, pedido_id: str,
    pasos_desde: dict[str, list[str]], accion: AccionAuditoria,
) -> EstadoPedidoVista:
    identificador = _uuid(pedido_id)
    grupo_id = _consultar_grupo(fabrica, _GRUPO_DE_PEDIDO, identificador).grupo_id
    ahora = reloj.ahora()
    with AbrirDespachoSQL(fabrica, reloj, rol="operacion")(grupo_id) as (u, _):
        pedido = u.despacho.pedido(identificador, bloquear=True)
        if pedido is None:
            raise ErrorMATU(404)
        camino = pasos_desde.get(pedido.estado)
        if camino is None:
            raise ErrorMATU(409, tipo="estado-pedido", detalle="El estado del pedido no permite la acción",
                            extension={"estado": pedido.estado})
        desde = pedido.estado
        for hacia in camino:
            u.despacho.cambiar_estado(identificador, desde, hacia, "operacion", operador, None, ahora)
            desde = hacia
        if desde == "entregado":
            lineas = u.despacho.lineas(identificador)
            for parte in u.despacho.partes(identificador):
                if parte.estado is EstadoParte.RETIRADA:
                    monto = monto_consumo([x for x in lineas if x.parte_id == parte.id])
                    u.despacho.registrar_consumo(parte, identificador, monto, ahora)
            u.despacho.emitir("PedidoEntregado", identificador, grupo_id, ahora)
        _auditar(u, operador, accion, EntidadAuditoria.PEDIDO, identificador, grupo_id, pedido.persona_id, request)
    return EstadoPedidoVista(pedido_id=identificador, estado=desde)


_EN_CAMINO = {
    **{desde: ["en_ruta"] for desde in EN_CAMINO_DESDE},
    "no_entregado": ["reprogramado", "en_ruta"],
}


@router.post("/pedidos/{pedido_id}/en-camino", response_model=EstadoPedidoVista, responses=_RESPUESTAS,
             description="Retirado (o reprogramado tras no entregarse) → en_ruta (D-63-6).")
def en_camino(pedido_id: _ID, request: Request, operador: Operador, fabrica: Fabrica,
              reloj: RelojDep) -> EstadoPedidoVista:
    return _mover(fabrica, reloj, request, operador, pedido_id, _EN_CAMINO, AccionAuditoria.DESPACHO_EN_CAMINO)


@router.post(
    "/pedidos/{pedido_id}/entregado",
    response_model=EstadoPedidoVista,
    responses=_RESPUESTAS,
    description=(
        "en_ruta → entregado. Fija entregado_en, desde donde corren los 10 días hábiles del retracto, y registra lo que"
        " MATU debe a cada comercio por lo retirado (consumo_comercio, RF-31), con la boleta pendiente."
    ),
)
def entregado(pedido_id: _ID, request: Request, operador: Operador, fabrica: Fabrica,
              reloj: RelojDep) -> EstadoPedidoVista:
    pasos = {desde: ["entregado"] for desde in ENTREGADO_DESDE}
    return _mover(fabrica, reloj, request, operador, pedido_id, pasos, AccionAuditoria.DESPACHO_ENTREGAR)


@router.post("/pedidos/{pedido_id}/no-entregado", response_model=EstadoPedidoVista, responses=_RESPUESTAS,
             description="en_ruta → no_entregado: nadie recibió el pedido (D-63-6).")
def no_entregado(pedido_id: _ID, request: Request, operador: Operador, fabrica: Fabrica,
                 reloj: RelojDep) -> EstadoPedidoVista:
    pasos = {desde: ["no_entregado"] for desde in NO_ENTREGADO_DESDE}
    return _mover(fabrica, reloj, request, operador, pedido_id, pasos, AccionAuditoria.DESPACHO_NO_ENTREGADO)


def _retracto_vista(r: Retracto, monto: int) -> RetractoVista:
    return RetractoVista(
        id=r.id, pedido_id=r.pedido_id, estado=r.estado,  # type: ignore[arg-type]
        solicitado_en=r.solicitado_en, plazo_hasta=r.plazo_hasta, incluye_envio=r.incluye_envio, monto=monto,
    )


@router.get("/retractos", response_model=ListaRetractos, responses=_RESPUESTAS,
            description="Los retractos por resolver, con lo que se devolvería.")
def listar_retractos(_operador: Operador, fabrica: Fabrica, reloj: RelojDep) -> ListaRetractos:
    with sesion_tenant(fabrica, rol="operacion") as sesion:
        pendientes = RepositorioRetractosSQL(sesion).pendientes()
    vistas = []
    for r in pendientes:
        with AbrirDespachoSQL(fabrica, reloj, rol="operacion")(r.grupo_id) as (u, retractos):
            vistas.append(_retracto_vista(r, casos_retracto.monto_de(u.pagos, retractos, r)))
    return ListaRetractos(retractos=vistas)


@router.post(
    "/retractos/{retracto_id}/resolver",
    response_model=RetractoVista,
    responses={**_RESPUESTAS, 503: {"description": "Sin PASARELA_PAGO no se puede devolver", **_PROBLEMA}},
    description=(
        "Operación recibió el producto. «devolver»: anula a la misma tarjeta los productos y, si corresponde, el envío"
        " (motivo retracto). «rechazar»: el sello no venía intacto. Antes de 45 días desde la solicitud (D-63-10)."
    ),
)
def resolver_retracto(
    retracto_id: _ID, solicitud: SolicitudResolverRetracto, operador: Operador, fabrica: Fabrica, reloj: RelojDep,
    pasarela: PasarelaDep,
) -> RetractoVista:
    identificador = _uuid(retracto_id)
    grupo_id = _consultar_grupo(fabrica, _GRUPO_DE_RETRACTO, identificador).grupo_id
    devolver = solicitud.decision == "devolver"
    if devolver and pasarela is None:
        raise ErrorMATU(503, tipo="pasarela-no-disponible", detalle="No se puede devolver en este momento")
    with AbrirDespachoSQL(fabrica, reloj, rol="operacion")(grupo_id) as (u, retractos):
        try:
            resuelto = casos_retracto.resolver(
                u.pagos, retractos, pasarela, identificador, devolver, operador, reloj.ahora()  # type: ignore[arg-type]
            )
        except casos_retracto.SinPedidoEntregado:
            raise ErrorMATU(404) from None
        except (casos_retracto.RetractoNoResoluble, DevolucionInvalida):
            raise ErrorMATU(409, tipo="retracto-no-resoluble", detalle="El retracto ya se resolvió o venció") from None
        return _retracto_vista(resuelto, casos_retracto.monto_de(u.pagos, retractos, resuelto))
