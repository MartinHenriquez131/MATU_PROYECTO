"""Rutas del pago de la familia (MATU-62, ADR-027; decisiones 224 a 230 y 236 a 239).

    POST /v1/pedidos/{pedido_id}/pagar                       admin y pagador. 201
    GET  /v1/pedidos/{pedido_id}/pago                        los cuatro roles (el observador, solo pagado o no). 200
    GET  /v1/personas-cuidadas/{persona_id}/pedido-pagado    los cuatro roles. 200 o 404

Son capa 3: van en ROUTERS_CAPA_3 de app/main.py. La vuelta de Webpay está en router_retorno.py y no se apaga con la
capa (decisión 241). Un pedido o una persona de otro grupo, un rol que no alcanza o un id que no es UUID: 404, nunca
403. El único 403 es la autorización despacho, en pagar. Orden de pagar: 401, 404, 403, 428, 422, idempotencia, 409
estado-pedido, 409 pago-en-curso, 412, 409 condiciones-cambiaron, 503 y 201.

Cache-Control: no-store en toda respuesta (prefijos /v1/pedidos y /v1/personas-cuidadas/ en app.main). Nada del pago
va a los logs ni a los errores: ni montos, ni el token, ni el buy_order, ni la tarjeta (decisión 247).
"""

import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Request, Response, status
from fastapi.responses import JSONResponse

from app.core.config import obtener_configuracion
from app.core.errores import ErrorMATU, respuesta_problema
from app.modules.care_circle.api.dependencias import SesionDeGrupo
from app.modules.care_circle.api.router_autorizaciones import RegistroDep, RelojDep
from app.modules.care_circle.domain.personas import FINALIDAD_DESPACHO, EstadoAutorizacion, estado_autorizacion
from app.modules.care_circle.infrastructure.autorizacion import persona_con_autorizacion
from app.modules.ordering.api.router import (
    Clave,
    Comercios,
    Idempotencia,
    IfMatch,
    Llave,
    Proyectar,
    Repositorio,
    reservar_clave,
    traducir_error,
)
from app.modules.ordering.application.pedidos import Actor, VersionDesactualizada
from app.modules.ordering.domain.estados import TransicionInvalida
from app.modules.ordering.domain.pedido import Pedido
from app.modules.ordering.infrastructure.condiciones import CondicionesNoDisponibles, condiciones_vigentes
from app.modules.payments.api.esquemas import InicioPago, PagoVista, PagoVistaObservador, SolicitudPago
from app.modules.payments.api.vistas import vista_observador, vista_pago
from app.modules.payments.application import lectura
from app.modules.payments.application import pagar as casos
from app.modules.payments.application.pagar import (
    Aceptacion,
    CondicionesCambiaron,
    Inicio,
    PagoEnCurso,
    PagoNoIniciado,
    SinPasarela,
)
from app.modules.payments.application.ports import PasarelaWebpay, PedidoCobro, RepositorioPagos
from app.modules.payments.infrastructure.pasarela import obtener_pasarela, url_retorno
from app.modules.payments.infrastructure.repositorio_pagos import RepositorioPagosSQL

router = APIRouter(tags=["pago"])

ROLES_QUE_PAGAN = frozenset({"admin", "pagador"})
REINTENTAR_EN_S = 30

_PROBLEMA: dict[str, Any] = {"content": {"application/problem+json": {}}}
_ERRORES_PAGAR: dict[int | str, dict[str, Any]] = {
    401: {"description": "Falta el access token, o es inválido o vencido", **_PROBLEMA},
    403: {
        "description": "/errores/sin-autorizacion-pedidos o /errores/revision-vencida, con finalidad: despacho",
        **_PROBLEMA,
    },
    404: {
        "description": "No miembro, cuidador u observador, pedido de otro grupo, inexistente o de una persona"
        " eliminada",
        **_PROBLEMA,
    },
    409: {
        "description": "/errores/estado-pedido (con estado; con el total vencido, vencido), /errores/pago-en-curso,"
        " /errores/condiciones-cambiaron (con version_vigente) o /errores/idempotencia-en-curso",
        **_PROBLEMA,
    },
    412: {
        "description": "/errores/version-desactualizada, con el pedido vigente en actual. No se cobró nada",
        **_PROBLEMA,
    },
    422: {"description": "Cuerpo o cabeceras inválidos, o /errores/idempotencia-reutilizada", **_PROBLEMA},
    428: {"description": "/errores/falta-idempotencia o /errores/falta-version", **_PROBLEMA},
    503: {
        "description": "/errores/pasarela-no-disponible, con Retry-After: Webpay no respondió y no se cobró nada",
        **_PROBLEMA,
    },
}
_ERRORES_LECTURA: dict[int | str, dict[str, Any]] = {
    401: _ERRORES_PAGAR[401],
    404: {"description": "No miembro, pedido o persona de otro grupo, inexistente o eliminada", **_PROBLEMA},
    422: {"description": "Un identificador que no es UUID responde 404; 422 queda para la forma", **_PROBLEMA},
}
VistaPago = PagoVista | PagoVistaObservador


def _vida() -> timedelta:
    return timedelta(minutes=obtener_configuracion().vida_venta_webpay_minutos)


def obtener_repositorio_pagos(contexto: SesionDeGrupo) -> RepositorioPagos:
    return RepositorioPagosSQL(contexto.sesion, contexto.grupo_id)


def obtener_return_url() -> str:
    return url_retorno(obtener_configuracion())


Pagos = Annotated[RepositorioPagos, Depends(obtener_repositorio_pagos)]
Pasarela = Annotated[PasarelaWebpay | None, Depends(obtener_pasarela)]
ReturnUrl = Annotated[str, Depends(obtener_return_url)]


def _uuid(valor: str) -> uuid.UUID:
    try:
        return uuid.UUID(valor)
    except ValueError:
        raise ErrorMATU(404) from None


def _sin_autorizacion(revision_vencida: bool) -> ErrorMATU:
    if revision_vencida:
        return ErrorMATU(
            403,
            tipo="revision-vencida",
            detalle="Hay que renovar la autorización para pedir insumos para esta persona",
            extension={"finalidad": "despacho"},
        )
    return ErrorMATU(
        403,
        tipo="sin-autorizacion-pedidos",
        detalle="Falta la autorización para pedir insumos para esta persona",
        extension={"finalidad": "despacho"},
    )


@dataclass(frozen=True)
class PedidoParaPagar:
    actor: Actor
    pedido: Pedido


def pedido_para_pagar(
    request: Request,
    contexto: SesionDeGrupo,
    pedido_id: Annotated[str, Path(json_schema_extra={"format": "uuid"})],
    repositorio: Repositorio,
    reloj: RelojDep,
) -> PedidoParaPagar:
    """404 (rol, grupo, persona eliminada) y 403 (despacho), antes de las cabeceras y el cuerpo (D-62-8)."""
    actor = Actor(
        usuario_id=contexto.usuario_id,
        grupo_id=contexto.grupo_id,
        rol=contexto.rol,
        request_id=getattr(request.state, "request_id", None),
    )
    if actor.rol not in ROLES_QUE_PAGAN:
        raise ErrorMATU(404)
    identificador = _uuid(pedido_id)
    # El pagador bloquea el pedido sin pagar por pedido_pagador_condiciones; uno ya pagado no se bloquea y responde
    # 409 estado-pedido en el caso de uso
    pedido = repositorio.cargar(identificador, bloquear=True) or repositorio.cargar(identificador)
    if pedido is None:
        raise ErrorMATU(404)
    # Sin FOR SHARE: el pagador no puede bloquear el consentimiento (lo retiran admin y cuidador) y un retiro con un
    # pago en curso no se bloquea (D-62-4): si la venta se aprueba después, se anula completa (regla 3)
    persona = persona_con_autorizacion(
        contexto.sesion, contexto.grupo_id, pedido.persona_id, FINALIDAD_DESPACHO, bloquear=False
    )
    if persona is None:
        raise ErrorMATU(404)
    estado = estado_autorizacion(persona.autorizacion, reloj.ahora())
    if estado is not EstadoAutorizacion.VIGENTE:
        raise _sin_autorizacion(estado is EstadoAutorizacion.REVISION_VENCIDA)
    return PedidoParaPagar(actor, pedido)


def _inicio(inicio: Inicio) -> InicioPago:
    venta = inicio.venta
    return InicioPago(
        intento_id=venta.id,
        estado=venta.estado.value,
        monto=venta.monto,
        total_confirmado_en=venta.total_confirmado_en,
        url=inicio.url,
        token=inicio.token,
    )


def _pasarela_no_disponible(request: Request) -> JSONResponse:
    # Se responde (no se lanza): la transacción guarda la venta en error y libera la clave (decisiones 228 y 229)
    return respuesta_problema(
        request,
        503,
        tipo="/errores/pasarela-no-disponible",
        titulo="Webpay no responde",
        detalle="Webpay no responde ahora. No se cobró nada. Inténtalo en unos minutos",
        headers={"Retry-After": str(REINTENTAR_EN_S), "Cache-Control": "no-store"},
    )


@router.post(
    "/pedidos/{pedido_id}/pagar",
    status_code=status.HTTP_201_CREATED,
    response_model=InicioPago,
    responses=_ERRORES_PAGAR,
    summary="Aceptar las condiciones y abrir el pago del total confirmado en Webpay",
    description=(
        "MATU-62 (decisiones 224 a 230). admin y pagador, con la autorización despacho vigente. El total tiene que"
        " estar"
        " vigente (con el total vencido, 409 estado-pedido con vencido, sin llamar a la pasarela). If-Match e"
        " Idempotency-Key obligatorios. Un solo pago en curso por pedido (409 pago-en-curso). Guarda la aceptación de"
        " las condiciones, crea o reutiliza el cargo y abre la venta de Webpay Plus por el total confirmado; el cuerpo"
        " no trae montos. Registra pago.iniciar. Capa 3"
    ),
)
def pagar(
    request: Request,
    response: Response,
    para_pagar: Annotated[PedidoParaPagar, Depends(pedido_para_pagar)],
    clave: Clave,
    if_match: IfMatch,
    solicitud: SolicitudPago,
    idem: Idempotencia,
    llave: Llave,
    pagos: Pagos,
    pasarela: Pasarela,
    registro: RegistroDep,
    reloj: RelojDep,
    return_url: ReturnUrl,
    proyectar: Proyectar,
) -> InicioPago | JSONResponse:
    actor, pedido = para_pagar.actor, para_pagar.pedido
    endpoint = f"POST /v1/pedidos/{pedido.id}/pagar"
    ahora, vida = reloj.ahora(), _vida()
    repeticion = reservar_clave(idem, endpoint, clave, actor, solicitud.model_dump(mode="json"), reloj, llave)
    response.headers["Location"] = f"/v1/pedidos/{pedido.id}/pago"
    response.headers["Cache-Control"] = "no-store"
    if repeticion is not None:
        venta_id = pagos.venta_de_clave(endpoint, clave)
        venta = None if venta_id is None else pagos.venta(venta_id)
        if venta is None:
            raise ErrorMATU(404)
        response.status_code = repeticion.estado_http
        return _inicio(casos.repetir(venta, pasarela, ahora, vida))
    try:
        vigentes = condiciones_vigentes()
    except CondicionesNoDisponibles:
        raise ErrorMATU(503, detalle="Las condiciones del pedido no están disponibles en este momento") from None
    try:
        inicio = casos.pagar(
            actor,
            pedido,
            if_match,
            Aceptacion(solicitud.condiciones.version, solicitud.condiciones.huella),
            Aceptacion(vigentes.version, vigentes.huella),
            ahora,
            vida,
            return_url,
            pagos,
            pasarela,
            registro,
        )
    except (TransicionInvalida, VersionDesactualizada) as error:
        raise traducir_error(error, proyectar) from None
    except PagoEnCurso:
        raise ErrorMATU(
            409, tipo="pago-en-curso", titulo="Hay un pago en curso", detalle="Ya hay un pago en curso para este pedido"
        ) from None
    except CondicionesCambiaron as error:
        raise ErrorMATU(
            409,
            tipo="condiciones-cambiaron",
            titulo="Las condiciones cambiaron",
            detalle="Las condiciones del pedido cambiaron",
            extension={"version_vigente": error.version_vigente},
        ) from None
    except (PagoNoIniciado, SinPasarela):
        pagos.liberar_clave(endpoint, clave)
        return _pasarela_no_disponible(request)
    idem.completar(endpoint, clave, status.HTTP_201_CREATED, pedido.id)
    pagos.asociar_clave(endpoint, clave, inicio.venta.id)
    return _inicio(inicio)


# --- Lecturas -------------------------------------------------------------------------------------------------------


def _vista(
    contexto: SesionDeGrupo,
    pedido: PedidoCobro,
    pagos: RepositorioPagos,
    pasarela: PasarelaWebpay | None,
    comercios_precios_de_ejemplo: bool,
    reloj: RelojDep,
) -> VistaPago:
    if contexto.rol not in lectura.ROLES_QUE_VEN_EL_PAGO:
        return vista_observador(lectura.vista_observador(pedido))
    estado = lectura.estado_del_pago(
        pagos,
        pedido,
        contexto.usuario_id,
        pagos.correo_propio(),
        reloj.ahora(),
        _vida(),
        precios_de_ejemplo=comercios_precios_de_ejemplo,
        # Sin pasarela configurada no se movió dinero: el sello de prueba va igual (D-62-7)
        pago_de_prueba=pasarela.pago_de_prueba if pasarela is not None else True,
    )
    return vista_pago(estado)


@router.get(
    "/pedidos/{pedido_id}/pago",
    response_model=VistaPago,
    responses=_ERRORES_LECTURA,
    summary="El estado del pago del pedido, sus devoluciones y el comprobante",
    description=(
        "MATU-62 (decisiones 236, 238 y 239). admin, cuidador y pagador: PagoVista; la tarjeta, el código de"
        " autorización y el correo solo para quien pagó. observador: PagoVistaObservador (pagado o sin_pagar). Sin"
        " cargo, 200 con sin_intento. No pide despacho. No se audita. Capa 3"
    ),
)
def ver_pago(
    response: Response,
    contexto: SesionDeGrupo,
    pedido_id: Annotated[str, Path(json_schema_extra={"format": "uuid"})],
    repositorio: Repositorio,
    pagos: Pagos,
    pasarela: Pasarela,
    comercios: Comercios,
    reloj: RelojDep,
) -> VistaPago:
    if contexto.rol not in lectura.ROLES_QUE_LEEN:
        raise ErrorMATU(404)
    identificador = _uuid(pedido_id)
    # De una persona eliminada o de otro grupo: 404 (cargar filtra las dos cosas)
    if repositorio.cargar(identificador) is None:
        raise ErrorMATU(404)
    pedido = pagos.pedido(identificador)
    if pedido is None:
        raise ErrorMATU(404)
    response.headers["Cache-Control"] = "no-store"
    return _vista(contexto, pedido, pagos, pasarela, comercios.precios_de_ejemplo, reloj)


@router.get(
    "/personas-cuidadas/{persona_id}/pedido-pagado",
    response_model=VistaPago,
    responses=_ERRORES_LECTURA,
    summary="El último pedido pagado de la persona, con su comprobante",
    description=(
        "MATU-62 (decisión 237). El pedido de pagado_en más reciente de la persona, con las vistas por rol de GET"
        " …/pago. 404 si no hay pedido pagado. No pide despacho. MATU-63 la reemplaza por el seguimiento. Capa 3"
    ),
)
def ver_pedido_pagado(
    response: Response,
    contexto: SesionDeGrupo,
    persona_id: Annotated[str, Path(json_schema_extra={"format": "uuid"})],
    repositorio: Repositorio,
    pagos: Pagos,
    pasarela: Pasarela,
    comercios: Comercios,
    reloj: RelojDep,
) -> VistaPago:
    if contexto.rol not in lectura.ROLES_QUE_LEEN:
        raise ErrorMATU(404)
    persona = _uuid(persona_id)
    if not repositorio.persona_del_grupo(persona):
        raise ErrorMATU(404)
    pedido_id = pagos.ultimo_pagado_de(persona)
    pedido = None if pedido_id is None else pagos.pedido(pedido_id)
    if pedido is None:
        raise ErrorMATU(404)
    response.headers["Cache-Control"] = "no-store"
    return _vista(contexto, pedido, pagos, pasarela, comercios.precios_de_ejemplo, reloj)
