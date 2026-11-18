"""Las rutas de operación del despacho (MATU-63; D-63-5, D-63-6, D-63-10; decisiones 417 a 421). La pantalla es de
MATU-81: mientras tanto, en la demo se opera por estas rutas.

Solo una cuenta con usuario.es_operacion; otra: 404. Cada acción corre con app.rol = 'operacion' y el grupo del pedido,
sin cuenta (trigger pedido_escritura_del_pago), y se audita con la cuenta de quien opera y la persona del pedido.

- POST …/partes/{id}/codigo genera o regenera el código de una parte lista y lo devuelve **una sola vez**: la base
  guarda solo su HMAC. Regenerar borra el uso, los intentos y el bloqueo anteriores (D-63-4).
- «En camino», «entregado» (fija entregado_en, el inicio del retracto, y registra lo que MATU debe a cada comercio,
  RF-31) y «no entregado» (D-63-6). Desde MATU-76, «no entregado» emite PedidoNoEntregado (D-76-5).
- Resolver un retracto: devolver a la misma tarjeta o rechazar (D-63-10).
"""

import logging
import re
import secrets
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Request, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import obtener_fabrica_sesiones, sesion_tenant
from app.core.errores import ErrorMATU
from app.core.limite_ip import DETALLE_503, ContadorNoDisponible, ContadorVentana, clave_de
from app.modules.backoffice.api.dependencias import Contador, Operador, PepperLimites, SecretoCodigo
from app.modules.backoffice.api.esquemas import (
    CodigoGenerado,
    EstadoPedidoVista,
    LineaRetractoOperacion,
    ListaPedidosOperacion,
    ListaRetractosOperacion,
    ParteOperacion,
    PedidoOperacion,
    RetractoOperacion,
    SolicitudResolverRetracto,
    SolicitudRetractoPorCorreo,
)
from app.modules.backoffice.application import consola
from app.modules.backoffice.application.despacho import (
    PEDIDO_ENTREGADO,
    PEDIDO_NO_ENTREGADO,
    NoCancelable,
    UnidadDespacho,
    cancelar_por_operacion,
)
from app.modules.backoffice.infrastructure import consola_sql
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
from app.modules.iam.api.router import obtener_pepper_email
from app.modules.iam.domain.credenciales import indice_email, normalizar_email
from app.modules.payments.application import retractos as casos_retracto
from app.modules.payments.application.ports import PasarelaWebpay
from app.modules.payments.application.retractos import Retracto
from app.modules.payments.domain.cargo import DevolucionInvalida
from app.modules.payments.domain.retracto import RetractoInvalido
from app.modules.payments.infrastructure.pasarela import obtener_pasarela
from app.modules.payments.infrastructure.repositorio_retractos import RepositorioRetractosSQL
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.auditoria_sql import RegistroAuditoriaSql
from app.shared.limite_ip import LimitePorIp, excedido, retry_after
from app.shared.limite_ip import huella as huella_limite

log = logging.getLogger("matu.backoffice.operacion")

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

_PARTES_DEL_PEDIDO = text(
    "SELECT pc.id AS parte_id, co.nombre_fantasia, pc.referencia AS referencia_parte,"
    " pc.estado AS estado_parte, pc.codigo_generado_en, pc.codigo_vigente AS con_hash, pc.codigo_expira_en,"
    " pc.codigo_usado_en, pc.codigo_bloqueado_en"
    " FROM pedido p JOIN pedido_comercio pc ON pc.pedido_id = p.id JOIN comercio co ON co.id = pc.comercio_id"
    " WHERE p.id = :id ORDER BY pc.creado_en, pc.id"
)
# Los estados en curso: la lista sin filtro, como desde MATU-63
EN_CURSO = ("pagado", "enviado_a_comercio", "preparando", "listo_retiro", "asignado", "sin_repartidor", "retirado",
            "en_ruta", "entregado", "no_entregado", "reprogramado")
GRUPOS_LISTA = "^(por_atender|en_camino|con_problema|cerrados|cancelados|todos)$"
ESTADOS_LISTA = (
    "^(pagado|enviado_a_comercio|preparando|listo_retiro|asignado|sin_repartidor|retirado|en_ruta|entregado|"
    "no_entregado|reprogramado|cerrado|cancelado|cancelado_con_devolucion)$"
)
_GRUPO_DE_PEDIDO = text("SELECT grupo_id FROM pedido WHERE id = :id")
_GRUPO_DE_PARTE = text("SELECT pedido_id, grupo_id FROM pedido_comercio WHERE id = :id")
# H2 y MATU-114 (C8): a nombre de quién va el retracto por correo, con la regla de la base: quien pagó, el admin activo
# que se indique o el admin activo con la huella del correo (D-81-9). Solo el id, o NULL: operación no lee las
# membresías (migración 0031). Exige app.usuario_id de una cuenta de operación activa
_SOLICITANTE = text("SELECT operacion_solicitante_retracto(:pedido, :hash, :solicitado_por)")
_PERSONA_DEL_PEDIDO = text("SELECT persona_cuidada_id FROM pedido WHERE id = :id")
# C9: el mismo 422 en todos los casos (huella sin cuenta, de otro grupo, no admin, inactiva, o los dos campos): nunca
# dice cuál
DETALLE_SOLICITANTE = "Va a nombre de quien pagó o de un administrador activo de la familia del pedido"
# C11 (J1): hasta 5 correos que no calzan por hora y por cuenta de operación
LIMITE_CORREO_RETRACTO = LimitePorIp("retracto-correo", 5)
DETALLE_TOPE_CORREO = "Hubo muchos intentos en poco tiempo. Vuelve a intentarlo más tarde"
_GRUPO_DE_RETRACTO = text("SELECT grupo_id FROM retracto WHERE id = :id")
# MATU-81: los chips de la consola, «Por resolver» (solicitado), «Devueltos» y «Sin devolución» (rechazado)
ESTADOS_RETRACTO = ("solicitado", "devuelto", "rechazado")


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


def pedidos_de_filas(sesion: Session, filas: list[Any], ahora: Any, hay_mas: bool) -> ListaPedidosOperacion:
    """Las filas de la lista o de la búsqueda (consola_sql), cada una con sus partes y el estado de su código."""
    pedidos = []
    for f in filas[: consola_sql.LIMITE_LISTA]:
        partes = [
            ParteOperacion(
                id=x.parte_id,
                comercio=x.nombre_fantasia,
                referencia=x.referencia_parte,
                estado=x.estado_parte,
                estado_codigo=estado_codigo(
                    generado_en=x.codigo_generado_en, con_hash=x.con_hash, expira_en=x.codigo_expira_en,
                    usado_en=x.codigo_usado_en, bloqueado_en=x.codigo_bloqueado_en, ahora=ahora,
                ).value,  # type: ignore[arg-type]
            )
            for x in sesion.execute(_PARTES_DEL_PEDIDO, {"id": f.id})
        ]
        pedidos.append(
            PedidoOperacion(
                id=f.id, estado=f.estado, referencia=f.referencia, entregado_en=f.entregado_en, partes=partes,
                pagado_en=f.pagado_en, total_confirmado=int(f.total), numero_partes=int(f.numero_partes),
                incidencia_abierta=bool(f.incidencia_abierta), devolucion_sin_terminar=bool(f.devolucion_sin_terminar),
            )
        )
    return ListaPedidosOperacion(pedidos=pedidos, hay_mas=hay_mas)


@router.get(
    "/pedidos",
    response_model=ListaPedidosOperacion,
    responses={**_RESPUESTAS, 422: {"description": "grupo o estado no son de la lista", **_PROBLEMA}},
    description=(
        "Los pedidos pagados con sus partes y el estado del código de cada una, del pago más reciente al más antiguo,"
        " hasta 200 (`hay_mas`). MATU-81 (P4, C8): `grupo` (por_atender, en_camino, con_problema, cerrados, cancelados"
        " o todos) y `estado` repetido se suman; con_problema suma los pedidos con una incidencia abierta o una"
        " devolución sin terminar. Sin ninguno, los que están en curso (todos menos cerrado y cancelados), como desde"
        " MATU-63. No se audita."
    ),
)
def listar_pedidos(
    _operador: Operador, fabrica: Fabrica, reloj: RelojDep, respuesta: Response,
    grupo: Annotated[str | None, Query(pattern=GRUPOS_LISTA)] = None,
    estado: Annotated[list[str] | None, Query(description="Uno o más estados del pedido")] = None,
) -> ListaPedidosOperacion:
    if estado and any(re.fullmatch(ESTADOS_LISTA, e) is None for e in estado):
        raise ErrorMATU(422, detalle="Revisa los campos indicados",
                        errores=[{"campo": "estado", "mensaje": "no es un estado del pedido", "tipo": "estado"}])
    filtro = (consola.Filtro(EN_CURSO, False, False) if grupo is None and not estado
              else consola.estados_del_filtro(grupo, estado or ()))
    with sesion_tenant(fabrica, rol="operacion") as sesion:
        filas = consola_sql.lista(sesion, filtro.estados, filtro.todos, filtro.con_problema)
        vista = pedidos_de_filas(sesion, filas, reloj.ahora(), hay_mas=len(filas) > consola_sql.LIMITE_LISTA)
    respuesta.headers["Cache-Control"] = "no-store"
    return vista


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
        _auditar(u, operador, AccionAuditoria.CODIGO_RETIRO_GENERAR, EntidadAuditoria.PEDIDO_COMERCIO,
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
            u.despacho.emitir(PEDIDO_ENTREGADO, identificador, grupo_id, ahora)
        elif desde == "no_entregado":
            # MATU-76 (D-76-5): en la misma transacción que el cambio de estado, solo con el id del pedido
            u.despacho.emitir(PEDIDO_NO_ENTREGADO, identificador, grupo_id, ahora)
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
             description=("en_ruta → no_entregado: nadie recibió el pedido (D-63-6). Emite PedidoNoEntregado, que avisa"
                          " a quien pagó (MATU-76, D-76-5)."))
def no_entregado(pedido_id: _ID, request: Request, operador: Operador, fabrica: Fabrica,
                 reloj: RelojDep) -> EstadoPedidoVista:
    pasos = {desde: ["no_entregado"] for desde in NO_ENTREGADO_DESDE}
    return _mover(fabrica, reloj, request, operador, pedido_id, pasos, AccionAuditoria.DESPACHO_NO_ENTREGADO)


def _retracto_vista(sesion: Session, r: Retracto, monto: int) -> RetractoOperacion:
    detalle, lineas = consola_sql.retracto_detalle(sesion, r.id)
    return RetractoOperacion(
        id=r.id, pedido_id=r.pedido_id, estado=r.estado,  # type: ignore[arg-type]
        solicitado_en=r.solicitado_en, plazo_hasta=r.plazo_hasta, incluye_envio=r.incluye_envio, monto=monto,
        origen=r.origen,  # type: ignore[arg-type]
        resuelto_en=r.resuelto_en,
        referencia=None if detalle is None else detalle.referencia,
        motivo_rechazo=None if detalle is None else detalle.motivo_rechazo,
        lineas=[
            LineaRetractoOperacion(linea_id=x.pedido_linea_id, producto=x.nombre, presentacion=x.presentacion,
                                   cantidad=int(x.cantidad), monto=int(x.cantidad) * int(x.precio_unitario))
            for x in lineas
        ],
    )


def _sesion_de(u: UnidadDespacho) -> Session:
    return u.pagos.repositorio._sesion  # type: ignore[attr-defined,no-any-return]


@router.post(
    "/pedidos/{pedido_id}/cancelar-con-devolucion",
    response_model=EstadoPedidoVista,
    responses={
        **_RESPUESTAS,
        503: {"description": "Sin PASARELA_PAGO no se puede devolver: no se cancela", **_PROBLEMA},
    },
    description=(
        "H1 y H2 del cierre del analista: operación cancela y devuelve todo, envío incluido, a la misma tarjeta. Desde"
        " no_entregado (nadie lo recibió y no hay segunda ventana), o cuando la familia pidió por correo cancelar un"
        " pedido pagado que ningún comercio empezó a preparar (R15). Otro estado: 409 no-cancelable."
    ),
)
def cancelar_con_devolucion(
    pedido_id: _ID, request: Request, operador: Operador, fabrica: Fabrica, reloj: RelojDep, pasarela: PasarelaDep
) -> EstadoPedidoVista:
    identificador = _uuid(pedido_id)
    grupo_id = _consultar_grupo(fabrica, _GRUPO_DE_PEDIDO, identificador).grupo_id
    if pasarela is None:
        raise ErrorMATU(503, tipo="pasarela-no-disponible", detalle="No se puede devolver en este momento")
    with AbrirDespachoSQL(fabrica, reloj, rol="operacion")(grupo_id) as (u, _):
        try:
            cancelar_por_operacion(u, pasarela, identificador, operador, reloj.ahora())
        except NoCancelable:
            raise ErrorMATU(409, tipo="no-cancelable", detalle="El estado del pedido no permite cancelarlo") from None
    return EstadoPedidoVista(pedido_id=identificador, estado="cancelado_con_devolucion")


def _clave_limite_correo(operador: uuid.UUID, pepper: bytes | None) -> str:
    """La clave del límite: la huella HMAC de la cuenta de operación. Ni el id, ni el correo ni su huella llegan a
    Redis."""
    if pepper is None:
        log.error("falta PEPPER_LIMITES: el retracto por correo falla cerrado")
        raise ErrorMATU(503, detalle=DETALLE_503)
    return clave_de(LIMITE_CORREO_RETRACTO, huella_limite(pepper, LIMITE_CORREO_RETRACTO.prefijo, str(operador)))


def reservar_intento(contador: ContadorVentana, clave: str) -> None:
    """C11 (MATU-114, cierre del analista): reserva un intento antes de buscar el correo, con un INCR atómico. Si el
    conteo que devuelve pasa de 5, 429 sin consultar: con peticiones en paralelo, a lo más 5 llegan a la base. Sin
    Redis, 503 sin consultar. Si el correo calza, devolver_reserva() la resta: solo quedan los fallidos."""
    try:
        conteo = contador.sumar(clave, LIMITE_CORREO_RETRACTO.ventana_segundos)
    except ContadorNoDisponible:
        log.error("Redis no responde: el retracto por correo falla cerrado")
        raise ErrorMATU(503, detalle=DETALLE_503) from None
    if excedido(conteo.conteo, LIMITE_CORREO_RETRACTO):
        raise ErrorMATU(
            429,
            tipo="demasiados-intentos",
            detalle=DETALLE_TOPE_CORREO,
            headers={"Retry-After": str(retry_after(conteo.ttl_segundos, LIMITE_CORREO_RETRACTO))},
        )


def devolver_reserva(contador: ContadorVentana, clave: str) -> None:
    """El correo calzó: el intento no cuenta. Si Redis no responde, la reserva queda (cuenta como fallido, que es lo
    prudente) y el retracto sigue: ya se consultó y el correo era válido."""
    try:
        contador.devolver(clave)
    except ContadorNoDisponible:
        log.error("Redis no responde: la reserva del retracto por correo queda contada")


def _correo_fallido(
    fabrica: sessionmaker[Session], reloj: RelojDep, operador: uuid.UUID, pedido_id: uuid.UUID, grupo_id: uuid.UUID,
    request: Request,
) -> None:
    """J2: el intento fallido ya quedó contado por su reserva (reservar_intento); se audita en su propia transacción
    (el 422 que sigue no la revierte), con el grupo y la persona del pedido y sin el correo."""
    with sesion_tenant(fabrica, grupo_id=grupo_id, rol="operacion") as sesion:
        persona_id = sesion.execute(_PERSONA_DEL_PEDIDO, {"id": pedido_id}).scalar_one()
        RegistroAuditoriaSql(sesion, reloj).registrar(
            EntradaAuditoria(
                grupo_id=grupo_id,
                actor_tipo=ActorTipo.OPERACION,
                actor_ref=operador,
                accion=AccionAuditoria.OPERACION_RETRACTO_CORREO_FALLIDO,
                entidad=EntidadAuditoria.PEDIDO,
                entidad_id=pedido_id,
                persona_cuidada_id=persona_id,
                request_id=getattr(request.state, "request_id", None),
            )
        )


@router.post(
    "/pedidos/{pedido_id}/retractos",
    response_model=RetractoOperacion,
    status_code=status.HTTP_201_CREATED,
    responses={
        **_RESPUESTAS,
        409: {"description": "fuera-de-plazo: pasaron los 90 días desde la entrega (CL-54)", **_PROBLEMA},
        422: {"description": "producto-no-retractable, o solicitante-invalido: solicitado_por no es quien pagó ni un"
              " admin activo, correo_solicitante no es de un admin activo del grupo (D-81-9), o vienen los dos. El"
              " mismo cuerpo en todos los casos: nunca dice cuál ni quiénes son (MATU-114, C9)", **_PROBLEMA},
        429: {"description": "demasiados-intentos: 5 correos que no calzan en una hora para la cuenta de operación"
              " (MATU-114, C11), con Retry-After. No dice si el último correo era válido", **_PROBLEMA},
        503: {"description": "Falta PEPPER_EMAIL o PEPPER_LIMITES, o Redis no responde, con correo_solicitante: no se"
              " busca el correo", **_PROBLEMA},
    },
    description=(
        "H2: registra a nombre de la familia el retracto que pidió por correo (origen correo), hasta 90 días desde la"
        " entrega. Va a nombre de quien pagó, o del admin que se indique. Se resuelve como cualquier retracto."
        " MATU-114: con correo_solicitante, hasta 5 correos que no calzan por hora y por cuenta de operación (429);"
        " cada uno se registra en la auditoría del pedido, sin el correo."
    ),
)
def registrar_retracto_por_correo(
    pedido_id: _ID, solicitud: SolicitudRetractoPorCorreo, request: Request, operador: Operador, fabrica: Fabrica,
    reloj: RelojDep, pepper_email: Annotated[bytes, Depends(obtener_pepper_email)], pepper_limites: PepperLimites,
    contador: Contador,
) -> RetractoOperacion:
    identificador = _uuid(pedido_id)
    grupo_id = _consultar_grupo(fabrica, _GRUPO_DE_PEDIDO, identificador).grupo_id
    pedidas: dict[uuid.UUID, int] = {}
    for linea in solicitud.lineas:
        pedidas[linea.linea_id] = pedidas.get(linea.linea_id, 0) + linea.cantidad
    if solicitud.correo_solicitante is not None and solicitud.solicitado_por is not None:
        # N1 (cierre del analista): los dos campos juntos no son un correo que no calzó. El mismo 422 (C9), sin contar
        # ni auditar
        raise ErrorMATU(422, tipo="solicitante-invalido", detalle=DETALLE_SOLICITANTE)
    clave_limite = None
    huella = None
    if solicitud.correo_solicitante is not None:
        # C11: se reserva el intento antes de buscar el correo. Sin PEPPER_LIMITES o sin Redis, 503 sin consultar
        clave_limite = _clave_limite_correo(operador, pepper_limites)
        reservar_intento(contador, clave_limite)
        # D-81-9: el correo nunca va al log ni a un error. Solo su huella llega a la base
        huella = indice_email(pepper_email, normalizar_email(solicitud.correo_solicitante))
    with sesion_tenant(fabrica, usuario_id=operador, rol="operacion") as sesion:
        solicitado_por = sesion.execute(
            _SOLICITANTE, {"pedido": identificador, "hash": huella, "solicitado_por": solicitud.solicitado_por}
        ).scalar()
    if solicitado_por is None:
        if clave_limite is not None:
            _correo_fallido(fabrica, reloj, operador, identificador, grupo_id, request)
        raise ErrorMATU(422, tipo="solicitante-invalido", detalle=DETALLE_SOLICITANTE)
    if clave_limite is not None:
        devolver_reserva(contador, clave_limite)
    with AbrirDespachoSQL(fabrica, reloj, rol="operacion")(grupo_id) as (u, retractos):
        sesion = _sesion_de(u)
        try:
            r = casos_retracto.solicitar(
                u.pagos, retractos, grupo_id, identificador, solicitado_por, pedidas, reloj.ahora(),
                origen="correo", actor=ActorTipo.OPERACION, actor_ref=operador,
            )
        except casos_retracto.SinPedidoEntregado:
            raise ErrorMATU(404) from None
        except casos_retracto.FueraDePlazo as error:
            raise ErrorMATU(409, tipo="fuera-de-plazo", detalle="Pasaron los 90 días desde la entrega",
                            extension={"plazo_hasta": error.plazo.isoformat()}) from None
        except RetractoInvalido:
            raise ErrorMATU(422, tipo="producto-no-retractable",
                            detalle="Elige productos entregados, hasta lo que queda por devolver") from None
        return _retracto_vista(sesion, r, casos_retracto.monto_de(u.pagos, retractos, r))


@router.get(
    "/retractos",
    response_model=ListaRetractosOperacion,
    responses={**_RESPUESTAS, 422: {"description": "estado no es solicitado, devuelto ni rechazado", **_PROBLEMA}},
    description=(
        "Los retractos con lo que se devuelve, la referencia, los productos y, si se rechazó, el motivo (P6). MATU-81:"
        " `estado` repetido (solicitado, devuelto o rechazado) se suma; sin él, solicitado (por resolver). Primero los"
        " por resolver, del más antiguo al más reciente, y después los resueltos, del resuelto más reciente al más"
        " antiguo, hasta 200 (`hay_mas`). No se audita."
    ),
)
def listar_retractos(
    _operador: Operador, fabrica: Fabrica, reloj: RelojDep, respuesta: Response,
    estado: Annotated[list[str] | None, Query(description="solicitado, devuelto o rechazado; repetible")] = None,
) -> ListaRetractosOperacion:
    estados = list(dict.fromkeys(estado or ["solicitado"]))
    if any(e not in ESTADOS_RETRACTO for e in estados):
        raise ErrorMATU(422, detalle="Revisa los campos indicados",
                        errores=[{"campo": "estado", "mensaje": "no es un estado del retracto", "tipo": "estado"}])
    with sesion_tenant(fabrica, rol="operacion") as sesion:
        encontrados = RepositorioRetractosSQL(sesion).por_estado(estados, consola_sql.LIMITE_LISTA + 1)
    vistas = []
    for r in encontrados[: consola_sql.LIMITE_LISTA]:
        with AbrirDespachoSQL(fabrica, reloj, rol="operacion")(r.grupo_id) as (u, retractos):
            vistas.append(_retracto_vista(_sesion_de(u), r, casos_retracto.monto_de(u.pagos, retractos, r)))
    respuesta.headers["Cache-Control"] = "no-store"
    return ListaRetractosOperacion(retractos=vistas, hay_mas=len(encontrados) > consola_sql.LIMITE_LISTA)


@router.get("/retractos/{retracto_id}", response_model=RetractoOperacion, responses=_RESPUESTAS,
            description="MATU-81 (ruta 5): un retracto, resuelto o no, con sus productos, la referencia y el motivo.")
def ver_retracto(retracto_id: _ID, _operador: Operador, fabrica: Fabrica, reloj: RelojDep,
                 respuesta: Response) -> RetractoOperacion:
    identificador = _uuid(retracto_id)
    grupo_id = _consultar_grupo(fabrica, _GRUPO_DE_RETRACTO, identificador).grupo_id
    with AbrirDespachoSQL(fabrica, reloj, rol="operacion")(grupo_id) as (u, retractos):
        r = retractos.retracto(identificador)
        if r is None:
            raise ErrorMATU(404)
        vista = _retracto_vista(_sesion_de(u), r, casos_retracto.monto_de(u.pagos, retractos, r))
    respuesta.headers["Cache-Control"] = "no-store"
    return vista


@router.post(
    "/retractos/{retracto_id}/resolver",
    response_model=RetractoOperacion,
    responses={
        **_RESPUESTAS,
        422: {"description": "motivo-rechazo: rechazar exige `motivo` (sello_abierto o producto_no_recibido), y"
              " devolver no lo lleva (C24)", **_PROBLEMA},
        503: {"description": "Sin PASARELA_PAGO no se puede devolver", **_PROBLEMA},
    },
    description=(
        "Operación recibió el producto. «devolver»: anula a la misma tarjeta los productos y, si corresponde, el envío"
        " (motivo retracto). «rechazar»: el sello no venía intacto. Antes de 45 días desde la solicitud (D-63-10)."
    ),
)
def resolver_retracto(
    retracto_id: _ID, solicitud: SolicitudResolverRetracto, operador: Operador, fabrica: Fabrica, reloj: RelojDep,
    pasarela: PasarelaDep,
) -> RetractoOperacion:
    identificador = _uuid(retracto_id)
    devolver = solicitud.decision == "devolver"
    if devolver == (solicitud.motivo is not None):
        raise ErrorMATU(422, tipo="motivo-rechazo", detalle="Rechazar pide el motivo; devolver no lo lleva",
                        errores=[{"campo": "motivo", "mensaje": "solo y siempre al rechazar", "tipo": "motivo"}])
    grupo_id = _consultar_grupo(fabrica, _GRUPO_DE_RETRACTO, identificador).grupo_id
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
        if solicitud.motivo is not None:
            consola_sql.fijar_motivo_rechazo(_sesion_de(u), identificador, solicitud.motivo)
        return _retracto_vista(_sesion_de(u), resuelto, casos_retracto.monto_de(u.pagos, retractos, resuelto))
