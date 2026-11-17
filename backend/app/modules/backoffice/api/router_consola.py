"""La consola de operación (MATU-81): el detalle del pedido, la búsqueda, la conciliación, las incidencias y el
catálogo de los comercios ficticios. Rutas 1, 2, 3, 4, 6 y 7 de la revisión previa; decisiones 449 en adelante.

Solo una cuenta de operación con el segundo factor (operador(): 404 si no es de operación, 401 mfa-requerido sin la
marca). Toda transacción corre con app.rol = 'operacion'. Lo ajeno o lo que no existe: 404.

- Abrir el detalle o el cobro de un pedido se audita como operacion.pedido_ver, con su grupo y su persona y sin
  contenido (D-81-5, C9). Las listas no se auditan.
- La búsqueda lleva la referencia en el cuerpo (C7). Ninguna ruta lleva una referencia ni un buy_order en la URL.
- Las incidencias: crear (incidencia.crear) y resolver (incidencia.resolver) se auditan sin el texto (C14). El PATCH
  exige If-Match con la versión (428 sin él, 412 si cambió).
- El catálogo: solo las ofertas de los comercios ficticios (D-81-7; trigger oferta_operacion_ficticia, C1). El PATCH
  exige If-Match (C4) y se audita como catalogo.oferta_cambiar, sin grupo y sin los valores. Un precio nuevo vale solo
  para las confirmaciones nuevas: pedido_linea guarda el precio confirmado (C3).
- Cache-Control: no-store en todas las respuestas (C8).
"""

import uuid
from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response, status
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import obtener_fabrica_sesiones, sesion_tenant
from app.core.errores import ErrorMATU
from app.modules.backoffice.api.dependencias import Operador
from app.modules.backoffice.api.esquemas import ListaPedidosOperacion
from app.modules.backoffice.api.esquemas_consola import (
    AccionDisponible,
    AnulacionPendiente,
    AnulacionVista,
    CatalogoConsola,
    CobroPedido,
    CobrosPendientes,
    ComercioOperacion,
    EventoLineaTiempo,
    IncidenciaVista,
    LineaDetalle,
    ListaIncidencias,
    OfertaConsola,
    ParteDetalle,
    PedidoDetalle,
    SolicitudBuscarPedido,
    SolicitudEditarIncidencia,
    SolicitudIncidencia,
    SolicitudOferta,
    VentaPendiente,
    VentaVista,
)
from app.modules.backoffice.api.router_operacion import pedidos_de_filas
from app.modules.backoffice.application import consola
from app.modules.backoffice.infrastructure import consola_sql as sql
from app.modules.care_circle.api.router_autorizaciones import RelojDep
from app.modules.fulfillment.domain.despacho import EstadoParte, LineaDespacho, estado_codigo
from app.modules.payments.domain.retracto import plazo_por_correo
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.auditoria_sql import RegistroAuditoriaSql

router = APIRouter(prefix="/operacion", tags=["operacion"])

_PROBLEMA: dict[str, Any] = {"content": {"application/problem+json": {}}}
_ID = Annotated[str, Path(json_schema_extra={"format": "uuid"})]
Fabrica = Annotated[sessionmaker[Session], Depends(obtener_fabrica_sesiones)]
IfMatch = Annotated[str | None, Header(alias="If-Match")]
_BASE: dict[int | str, dict[str, Any]] = {
    401: {"description": "no-autenticado, token-invalido o mfa-requerido (sin el segundo factor)", **_PROBLEMA},
    404: {"description": "No es una cuenta de operación, o lo pedido no existe", **_PROBLEMA},
}
_CON_VERSION: dict[int | str, dict[str, Any]] = {
    412: {"description": "version-desactualizada: el If-Match no es la versión actual", **_PROBLEMA},
    428: {"description": "falta-version: el PATCH exige If-Match", **_PROBLEMA},
}
# C17: una venta sin respuesta por más de 15 minutos
SIN_RESPUESTA = timedelta(minutes=15)
_ESTADO_ANULACION = {"aprobada": "hecha", "rechazada": "rechazada"}


def _uuid(valor: str) -> uuid.UUID:
    try:
        return uuid.UUID(valor)
    except ValueError:
        raise ErrorMATU(404) from None


def _no_store(respuesta: Response) -> None:
    respuesta.headers["Cache-Control"] = "no-store"


def _auditar(sesion: Session, reloj: RelojDep, request: Request, operador: uuid.UUID, accion: AccionAuditoria,
             entidad: EntidadAuditoria, entidad_id: uuid.UUID, grupo_id: uuid.UUID | None,
             persona_id: uuid.UUID | None) -> None:
    RegistroAuditoriaSql(sesion, reloj).registrar(
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


def _grupo_del_pedido(fabrica: sessionmaker[Session], pedido_id: uuid.UUID) -> Any:
    with sesion_tenant(fabrica, rol="operacion") as sesion:
        fila = sql.pedido(sesion, pedido_id)
    if fila is None:
        raise ErrorMATU(404)
    return fila


# --- Ruta 2: buscar -------------------------------------------------------------------------------------------------


@router.post(
    "/pedidos/buscar",
    response_model=ListaPedidosOperacion,
    responses=_BASE,
    description=(
        "C7: busca un pedido pagado por su referencia o por la de una de sus partes, sin distinguir mayúsculas. La"
        " referencia va solo en el cuerpo: nunca en la URL, los logs, los errores ni la auditoría. Sin resultado,"
        " una lista vacía. No se audita (abrir el pedido sí)."
    ),
)
def buscar_pedido(solicitud: SolicitudBuscarPedido, _operador: Operador, fabrica: Fabrica, reloj: RelojDep,
                  respuesta: Response) -> ListaPedidosOperacion:
    with sesion_tenant(fabrica, rol="operacion") as sesion:
        vista = pedidos_de_filas(sesion, sql.buscar(sesion, solicitud.referencia), reloj.ahora(), hay_mas=False)
    _no_store(respuesta)
    return vista


# --- Ruta 1: el detalle ---------------------------------------------------------------------------------------------


def _lineas_despacho(filas: list[Any]) -> list[LineaDespacho]:
    return [
        LineaDespacho(id=f.id, parte_id=f.parte_id, cantidad=int(f.cantidad),
                      unidades_faltantes=int(f.unidades_faltantes),
                      precio_unitario=int(f.precio_unitario), monto_devuelto=int(f.monto_devuelto))
        for f in filas
    ]


def _actor(actor_tipo: str) -> str:
    return "familia" if actor_tipo == "usuario" else actor_tipo


def _linea_de_tiempo(sesion: Session, pedido: Any, partes: list[Any], transacciones: list[Any]) -> list[
        EventoLineaTiempo]:
    eventos: list[EventoLineaTiempo] = []
    for t in sql.transiciones(sesion, pedido.id):
        eventos.append(EventoLineaTiempo(
            en=t.ocurrido_en, tipo="estado", actor_tipo=_actor(t.actor_tipo),  # type: ignore[arg-type]
            comercio=t.nombre_fantasia if t.actor_tipo == "comercio" else None,
            desde=t.desde, hacia=t.hacia, motivo=t.motivo, monto=None,
        ))
    for p in partes:
        for campo, hacia, actor in (("enviado_en", "enviada", "sistema"), ("preparando_en", "preparando", "comercio"),
                                    ("lista_en", "lista", "comercio"), ("retirada_en", "retirada", "comercio"),
                                    ("cancelada_en", "cancelada", "sistema")):
            instante = getattr(p, campo)
            if instante is not None:
                eventos.append(EventoLineaTiempo(
                    en=instante, tipo="parte", actor_tipo=actor,  # type: ignore[arg-type]
                    comercio=p.nombre_fantasia, desde=None, hacia=hacia,
                    motivo=p.motivo_cancelacion if hacia == "cancelada" else None, monto=None,
                ))
    for t in transacciones:
        if t.tipo == "venta" and t.estado == "aprobada":
            eventos.append(EventoLineaTiempo(
                en=t.cerrada_en or t.retorno_recibido_en or t.actualizado_en, tipo="cobro", actor_tipo="sistema",
                comercio=None, desde=None, hacia="aprobada", motivo=None, monto=int(t.monto),
            ))
        elif t.tipo == "anulacion":
            eventos.append(EventoLineaTiempo(
                en=t.creado_en, tipo="anulacion", actor_tipo="sistema", comercio=None, desde=None,
                hacia=_ESTADO_ANULACION.get(t.estado, "en_curso"), motivo=t.motivo_anulacion, monto=int(t.monto),
            ))
    for r in sql.retractos_del_pedido(sesion, pedido.id):
        eventos.append(EventoLineaTiempo(en=r.solicitado_en, tipo="retracto", actor_tipo="familia", comercio=None,
                                         desde=None, hacia="solicitado", motivo=None, monto=None))
        if r.resuelto_en is not None:
            eventos.append(EventoLineaTiempo(en=r.resuelto_en, tipo="retracto", actor_tipo="operacion",
                                             comercio=None, desde="solicitado", hacia=r.estado,
                                             motivo=r.motivo_rechazo, monto=None))
    for i in sql.incidencias_del_pedido(sesion, pedido.id):
        eventos.append(EventoLineaTiempo(en=i.creada_en, tipo="incidencia", actor_tipo="operacion", comercio=None,
                                         desde=None, hacia="abierta", motivo=i.tipo, monto=None))
        if i.resuelta_en is not None:
            eventos.append(EventoLineaTiempo(en=i.resuelta_en, tipo="incidencia", actor_tipo="operacion",
                                             comercio=None, desde=None, hacia="resuelta", motivo=i.tipo, monto=None))
    eventos.sort(key=lambda e: e.en)
    return eventos


@router.get(
    "/pedidos/{pedido_id}",
    response_model=PedidoDetalle,
    responses=_BASE,
    description=(
        "Ruta 1: el pedido pagado con sus partes, sus líneas (precio pagado, faltantes y devolución), la línea de"
        " tiempo (de pedido_transicion y los instantes de las partes, el cobro, las anulaciones, los retractos y las"
        " incidencias; nunca de la auditoría) y `acciones` con `monto_a_devolver` (P3). Sin datos de la persona, del"
        " grupo ni de la cuenta de la familia (C5). Se audita como operacion.pedido_ver (D-81-5)."
    ),
)
def ver_pedido(pedido_id: _ID, request: Request, operador: Operador, fabrica: Fabrica, reloj: RelojDep,
               respuesta: Response) -> PedidoDetalle:
    identificador = _uuid(pedido_id)
    base = _grupo_del_pedido(fabrica, identificador)
    ahora = reloj.ahora()
    with sesion_tenant(fabrica, grupo_id=base.grupo_id, rol="operacion") as sesion:
        pedido = sql.pedido(sesion, identificador)
        if pedido is None:
            raise ErrorMATU(404)
        partes = sql.partes(sesion, identificador)
        lineas = sql.lineas(sesion, identificador)
        cargo = sql.cargo(sesion, identificador)
        transacciones = [] if cargo is None else sql.transacciones(sesion, cargo.id)
        cobrado = 0 if cargo is None else int(cargo.monto_cobrado)
        devuelto = 0 if cargo is None else int(cargo.monto_devuelto)
        posibles = consola.acciones(pedido.estado, [EstadoParte(p.estado) for p in partes], _lineas_despacho(lineas),
                                    cobrado, devuelto)
        vista = PedidoDetalle(
            id=pedido.id, referencia=pedido.referencia, estado=pedido.estado, pagado_en=pedido.pagado_en,
            entregado_en=pedido.entregado_en, subtotal_productos=int(pedido.subtotal_productos),
            costo_envio=int(pedido.costo_envio), total_confirmado=int(pedido.total),
            partes=[
                ParteDetalle(
                    id=p.id, referencia=p.referencia,
                    comercio=ComercioOperacion(nombre_fantasia=p.nombre_fantasia, ficticio=bool(p.ficticio)),
                    estado=p.estado,
                    estado_codigo=estado_codigo(
                        generado_en=p.codigo_generado_en, con_hash=p.con_hash, expira_en=p.codigo_expira_en,
                        usado_en=p.codigo_usado_en, bloqueado_en=p.codigo_bloqueado_en, ahora=ahora,
                    ).value,  # type: ignore[arg-type]
                    codigo_expira_en=p.codigo_expira_en, enviado_en=p.enviado_en, preparando_en=p.preparando_en,
                    lista_en=p.lista_en, retirada_en=p.retirada_en, cancelada_en=p.cancelada_en,
                    motivo_cancelacion=p.motivo_cancelacion,
                )
                for p in partes
            ],
            lineas=[
                LineaDetalle(
                    id=f.id, parte_id=f.parte_id, producto=f.nombre, presentacion=f.presentacion,
                    cantidad=int(f.cantidad), precio_unitario=int(f.precio_unitario),
                    subtotal=int(f.precio_unitario) * int(f.cantidad), estado_linea=f.estado_linea,
                    unidades_faltantes=int(f.unidades_faltantes), monto_devuelto=int(f.monto_devuelto),
                    devolucion="en_curso" if f.en_curso else ("hecha" if f.monto_devuelto > 0 else "sin_devolucion"),
                )
                for f in lineas
            ],
            linea_de_tiempo=_linea_de_tiempo(sesion, pedido, partes, transacciones),
            acciones=[AccionDisponible(accion=a.accion, monto_a_devolver=a.monto_a_devolver)  # type: ignore[arg-type]
                      for a in posibles],
            retracto_plazo_hasta=None if pedido.entregado_en is None else plazo_por_correo(pedido.entregado_en),
        )
        _auditar(sesion, reloj, request, operador, AccionAuditoria.OPERACION_PEDIDO_VER, EntidadAuditoria.PEDIDO,
                 identificador, pedido.grupo_id, pedido.persona_cuidada_id)
    _no_store(respuesta)
    return vista


# --- Rutas 3 y 4: la conciliación ---------------------------------------------------------------------------------


@router.get(
    "/pedidos/{pedido_id}/cobro",
    response_model=CobroPedido,
    responses=_BASE,
    description=(
        "Ruta 3 (C17, C18, D-81-8): el total confirmado, lo cobrado, lo devuelto, cada venta (con buy_order) y cada"
        " anulación (motivo, monto, estado e instante). Nunca el token, el session_id, la respuesta de Transbank, la"
        " tarjeta, las cuotas ni el código de autorización. Se audita como operacion.pedido_ver (D-81-5)."
    ),
)
def ver_cobro(pedido_id: _ID, request: Request, operador: Operador, fabrica: Fabrica, reloj: RelojDep,
              respuesta: Response) -> CobroPedido:
    identificador = _uuid(pedido_id)
    base = _grupo_del_pedido(fabrica, identificador)
    with sesion_tenant(fabrica, grupo_id=base.grupo_id, rol="operacion") as sesion:
        cargo = sql.cargo(sesion, identificador)
        transacciones = [] if cargo is None else sql.transacciones(sesion, cargo.id)
        cobrado = 0 if cargo is None else int(cargo.monto_cobrado)
        devuelto = 0 if cargo is None else int(cargo.monto_devuelto)
        anulaciones = [
            AnulacionVista(id=t.id, motivo=t.motivo_anulacion, monto=int(t.monto),
                           estado=_ESTADO_ANULACION.get(t.estado, "en_curso"),  # type: ignore[arg-type]
                           producto=t.producto, en=t.creado_en)
            for t in transacciones if t.tipo == "anulacion"
        ]
        vista = CobroPedido(
            pedido_id=identificador, referencia=base.referencia, total_confirmado=int(base.total), cobrado=cobrado,
            devuelto=devuelto, queda_cobrado=max(0, cobrado - devuelto),
            estado_cargo="sin_cargo" if cargo is None else cargo.estado,
            ventas=[
                VentaVista(buy_order=t.buy_order, monto=int(t.monto), estado=t.estado, creada_en=t.creado_en,
                           respondida_en=t.retorno_recibido_en or t.cerrada_en)
                for t in transacciones if t.tipo == "venta"
            ],
            anulaciones=anulaciones,
            calza=cobrado <= int(base.total) and all(a.estado != "en_curso" for a in anulaciones),
        )
        _auditar(sesion, reloj, request, operador, AccionAuditoria.OPERACION_PEDIDO_VER, EntidadAuditoria.PEDIDO,
                 identificador, base.grupo_id, base.persona_cuidada_id)
    _no_store(respuesta)
    return vista


@router.get(
    "/cobros/pendientes",
    response_model=CobrosPendientes,
    responses=_BASE,
    description=(
        "Ruta 4 (C17): las ventas sin respuesta por más de 15 minutos y las anulaciones sin terminar, hasta 200 de"
        " cada una, de la más antigua a la más reciente. La tarea conciliacion_pagos las cierra o las reintenta cada"
        " 5 minutos: esta lista es para revisarlas. No se audita."
    ),
)
def cobros_pendientes(_operador: Operador, fabrica: Fabrica, reloj: RelojDep, respuesta: Response) -> CobrosPendientes:
    with sesion_tenant(fabrica, rol="operacion") as sesion:
        ventas = sql.ventas_pendientes(sesion, reloj.ahora() - SIN_RESPUESTA)
        anulaciones = sql.anulaciones_pendientes(sesion)
    _no_store(respuesta)
    return CobrosPendientes(
        ventas_sin_respuesta=[
            VentaPendiente(pedido_id=f.pedido_id, referencia=f.referencia, buy_order=f.buy_order, monto=int(f.monto),
                           creada_en=f.creado_en)
            for f in ventas
        ],
        anulaciones_sin_terminar=[
            AnulacionPendiente(pedido_id=f.pedido_id, referencia=f.referencia, motivo=f.motivo_anulacion,
                               monto=int(f.monto), creada_en=f.creado_en, intentos=int(f.intentos or 0))
            for f in anulaciones
        ],
    )


# --- Ruta 6: las incidencias --------------------------------------------------------------------------------------


def _etag(version: int) -> str:
    return f'"i{version}"'


def _incidencia(f: Any, operador: uuid.UUID) -> IncidenciaVista:
    return IncidenciaVista(
        id=f.id, pedido_id=f.pedido_id, referencia=f.referencia, tipo=f.tipo, estado=f.estado,
        descripcion=f.descripcion, resolucion=f.resolucion, creada_en=f.creada_en, resuelta_en=f.resuelta_en,
        asignada=f.asignada_a is not None, asignada_a_mi=f.asignada_a == operador, version=int(f.version),
    )


@router.get(
    "/incidencias",
    response_model=ListaIncidencias,
    responses={**_BASE, 422: {"description": "estado no es abierta, en_gestion ni resuelta", **_PROBLEMA}},
    description="Las incidencias, de la más nueva a la más antigua, hasta 200. Con `estado`, solo las de ese estado.",
)
def listar_incidencias(
    operador: Operador, fabrica: Fabrica, respuesta: Response,
    estado: Annotated[str | None, Query(pattern="^(abierta|en_gestion|resuelta)$")] = None,
) -> ListaIncidencias:
    with sesion_tenant(fabrica, rol="operacion") as sesion:
        filas = sql.incidencias(sesion, estado)
    _no_store(respuesta)
    return ListaIncidencias(incidencias=[_incidencia(f, operador) for f in filas])


@router.get("/incidencias/{incidencia_id}", response_model=IncidenciaVista, responses=_BASE,
            description="Una incidencia, con su versión en el ETag (P7).")
def ver_incidencia(incidencia_id: _ID, operador: Operador, fabrica: Fabrica, respuesta: Response) -> IncidenciaVista:
    with sesion_tenant(fabrica, rol="operacion") as sesion:
        fila = sql.incidencia(sesion, _uuid(incidencia_id))
    if fila is None:
        raise ErrorMATU(404)
    _no_store(respuesta)
    respuesta.headers["ETag"] = _etag(int(fila.version))
    return _incidencia(fila, operador)


@router.post(
    "/pedidos/{pedido_id}/incidencias",
    response_model=IncidenciaVista,
    status_code=status.HTTP_201_CREATED,
    responses={**_BASE, 422: {"description": "Cuerpo inválido: el tipo o la nota de 1 a 500 caracteres", **_PROBLEMA}},
    description=(
        "Anota lo que pasó con un pedido pagado (C10 a C14). La nota (`descripcion`) la puede leer la familia en la"
        " copia de sus datos: no lleva nombres, datos de salud ni la dirección. Se audita incidencia.crear sin el"
        " texto. El texto nunca va a logs, errores, eventos ni auditoría."
    ),
)
def crear_incidencia(pedido_id: _ID, solicitud: SolicitudIncidencia, request: Request, operador: Operador,
                     fabrica: Fabrica, reloj: RelojDep, respuesta: Response) -> IncidenciaVista:
    identificador = _uuid(pedido_id)
    base = _grupo_del_pedido(fabrica, identificador)
    with sesion_tenant(fabrica, usuario_id=operador, grupo_id=base.grupo_id, rol="operacion") as sesion:
        nueva = sql.crear_incidencia(sesion, identificador, solicitud.tipo, solicitud.descripcion,
                                     operador if solicitud.asignarme else None, reloj.ahora())
        _auditar(sesion, reloj, request, operador, AccionAuditoria.INCIDENCIA_CREAR, EntidadAuditoria.INCIDENCIA,
                 nueva, base.grupo_id, base.persona_cuidada_id)
        fila = sql.incidencia(sesion, nueva)
    _no_store(respuesta)
    respuesta.headers["ETag"] = _etag(int(fila.version))
    return _incidencia(fila, operador)


def _version_de(if_match: str | None, prefijo: str) -> str:
    if if_match is None:
        raise ErrorMATU(428, tipo="falta-version", detalle="Vuelve a abrir el contenido antes de cambiarlo")
    valor = if_match.strip().removeprefix("W/").strip('"')
    if not valor.startswith(prefijo) or not valor[len(prefijo):].isdigit():
        raise ErrorMATU(412, tipo="version-desactualizada", detalle="Otra persona del equipo cambió esto")
    return valor[len(prefijo):]


@router.patch(
    "/incidencias/{incidencia_id}",
    response_model=IncidenciaVista,
    responses={
        **_BASE, **_CON_VERSION,
        409: {"description": "incidencia-resuelta: una incidencia resuelta ya no cambia", **_PROBLEMA},
        422: {"description": "falta-resolucion: «resuelta» exige la resolución, o el cuerpo es inválido",
              **_PROBLEMA},
    },
    description=(
        "Cambia el estado, la asignación (`a_mi` o `sin_asignar`) o la resolución (C13). Exige If-Match con el ETag"
        " (P7): 428 sin él, 412 si otra persona la cambió. Resolverla se audita incidencia.resolver, sin el texto."
    ),
)
def editar_incidencia(incidencia_id: _ID, solicitud: SolicitudEditarIncidencia, request: Request,
                      operador: Operador, fabrica: Fabrica, reloj: RelojDep, respuesta: Response,
                      if_match: IfMatch = None) -> IncidenciaVista:
    identificador = _uuid(incidencia_id)
    with sesion_tenant(fabrica, rol="operacion") as sesion:
        actual = sql.incidencia(sesion, identificador)
    if actual is None:
        raise ErrorMATU(404)
    version = int(_version_de(if_match, "i"))
    if version != int(actual.version):
        raise ErrorMATU(412, tipo="version-desactualizada", detalle="Otra persona del equipo cambió esto")
    try:
        cambio = consola.nuevo_estado_incidencia(actual.estado, actual.resolucion, solicitud.estado,
                                                 solicitud.resolucion, reloj.ahora())
    except consola.IncidenciaResuelta:
        raise ErrorMATU(409, tipo="incidencia-resuelta", detalle="Esta incidencia ya se resolvió") from None
    except consola.FaltaResolucion:
        raise ErrorMATU(422, tipo="falta-resolucion", detalle="Escribe cómo se resolvió",
                        errores=[{"campo": "resolucion", "mensaje": "obligatoria para resolver",
                                  "tipo": "falta_resolucion"}]) from None
    asignada = actual.asignada_a
    if solicitud.asignacion == "a_mi":
        asignada = operador
    elif solicitud.asignacion == "sin_asignar":
        asignada = None
    with sesion_tenant(fabrica, grupo_id=actual.grupo_id, rol="operacion") as sesion:
        if not sql.editar_incidencia(sesion, identificador, version, cambio.estado, asignada, cambio.resolucion,
                                     cambio.resuelta_en):
            raise ErrorMATU(412, tipo="version-desactualizada", detalle="Otra persona del equipo cambió esto")
        if cambio.resuelve:
            _auditar(sesion, reloj, request, operador, AccionAuditoria.INCIDENCIA_RESOLVER,
                     EntidadAuditoria.INCIDENCIA, identificador, actual.grupo_id, actual.persona_cuidada_id)
        fila = sql.incidencia(sesion, identificador)
    _no_store(respuesta)
    respuesta.headers["ETag"] = _etag(int(fila.version))
    return _incidencia(fila, operador)


# --- Ruta 7: el catálogo de los comercios ficticios ---------------------------------------------------------------


def _etag_oferta(actualizado_en: Any) -> str:
    return f'"o{int(actualizado_en.timestamp() * 1_000_000)}"'


def _oferta(f: Any) -> OfertaConsola:
    return OfertaConsola(
        id=f.id, comercio=ComercioOperacion(nombre_fantasia=f.nombre_fantasia, ficticio=bool(f.ficticio)),
        producto=f.nombre, presentacion=f.presentacion, precio=int(f.precio), stock=int(f.stock),
        disponible=bool(f.disponible), editable=bool(f.ficticio), version=_etag_oferta(f.actualizado_en),
    )


@router.get("/catalogo", response_model=CatalogoConsola, responses=_BASE,
            description="Las ofertas de los comercios activos. `editable` solo en los comercios ficticios (D-81-7).")
def ver_catalogo(_operador: Operador, fabrica: Fabrica, respuesta: Response) -> CatalogoConsola:
    with sesion_tenant(fabrica, rol="operacion") as sesion:
        filas = sql.catalogo(sesion)
    _no_store(respuesta)
    return CatalogoConsola(ofertas=[_oferta(f) for f in filas])


@router.patch(
    "/ofertas/{oferta_id}",
    response_model=OfertaConsola,
    responses={
        **_BASE, **_CON_VERSION,
        409: {"description": "comercio-real: solo se editan las ofertas de los comercios ficticios (C1)", **_PROBLEMA},
        422: {"description": "Cuerpo inválido: el precio es un entero en pesos mayor que 0, con IVA", **_PROBLEMA},
    },
    description=(
        "Cambia el precio (pesos enteros con IVA incluido, mayor que 0), el stock o si se ofrece, solo en un comercio"
        " ficticio (C1, C2; la base lo exige con el trigger oferta_operacion_ficticia). Exige If-Match (C4). Un precio"
        " nuevo vale solo para las confirmaciones nuevas: no cambia los pedidos confirmados ni pagados (C3). Se audita"
        " catalogo.oferta_cambiar sin grupo y sin los valores."
    ),
)
def cambiar_oferta(oferta_id: _ID, solicitud: SolicitudOferta, request: Request, operador: Operador, fabrica: Fabrica,
                   reloj: RelojDep, respuesta: Response, if_match: IfMatch = None) -> OfertaConsola:
    identificador = _uuid(oferta_id)
    with sesion_tenant(fabrica, rol="operacion") as sesion:
        actual = sql.oferta(sesion, identificador)
        if actual is None:
            raise ErrorMATU(404)
        version = _version_de(if_match, "o")
        if f'"o{version}"' != _etag_oferta(actual.actualizado_en):
            raise ErrorMATU(412, tipo="version-desactualizada", detalle="Otra persona del equipo cambió esto")
        if not actual.ficticio:
            raise ErrorMATU(409, tipo="comercio-real", detalle="Solo se cambian los productos de los comercios de"
                            " prueba")
        ahora = reloj.ahora()
        try:
            sql.cambiar_oferta(
                sesion, identificador,
                actual.precio if solicitud.precio is None else solicitud.precio,
                actual.stock if solicitud.stock is None else solicitud.stock,
                actual.disponible if solicitud.disponible is None else solicitud.disponible,
                ahora,
            )
        except DBAPIError:
            raise ErrorMATU(409, tipo="comercio-real", detalle="Solo se cambian los productos de los comercios de"
                            " prueba") from None
        _auditar(sesion, reloj, request, operador, AccionAuditoria.CATALOGO_OFERTA_CAMBIAR, EntidadAuditoria.OFERTA,
                 identificador, None, None)
        nueva = sql.oferta(sesion, identificador)
    _no_store(respuesta)
    respuesta.headers["ETag"] = _etag_oferta(nueva.actualizado_en)
    return _oferta(nueva)
