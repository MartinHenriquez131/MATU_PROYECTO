"""Rutas del pedido sin pagar (MATU-61, RF-21, ADR-027; decisiones 193 a 209, 211 a 213 y 218).

    POST /v1/personas-cuidadas/{persona_id}/pedidos          admin y cuidador. 201
    GET  /v1/personas-cuidadas/{persona_id}/pedido-en-curso  los cuatro roles. 200 o 404
    GET  /v1/pedidos/{pedido_id}                             los cuatro roles. 200
    PUT  /v1/pedidos/{pedido_id}/lineas                      admin y cuidador. 200
    PUT  /v1/pedidos/{pedido_id}/reglas-faltante             admin y cuidador. 200
    POST /v1/pedidos/{pedido_id}/confirmar                   admin y cuidador. 200
    PUT  /v1/pedidos/{pedido_id}/contacto                    admin y cuidador. 200
    POST /v1/pedidos/{pedido_id}/cambiar                     admin y cuidador. 200
    POST /v1/pedidos/{pedido_id}/cancelar                    admin y cuidador. 200

Es capa 3: va en ROUTERS_CAPA_3 de app/main.py y existe solo con CAPA3_HABILITADA. Un pedido o una persona de otro
grupo, un rol que no alcanza o un id que no es UUID: 404, nunca 403. El único 403 es la autorización despacho (C21),
en todo lo que escribe salvo cancelar. Orden: 401, 404, 403, 428, 422 (cabeceras y cuerpo), idempotencia, 412, 409.

Cache-Control: no-store en toda respuesta (prefijos /v1/pedidos y /v1/personas-cuidadas/ en app.main). Nada del
pedido ni la Idempotency-Key van a los logs: la línea de la petición lleva la plantilla de la ruta.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Header, Path, Request, Response, status

from app.core.config import obtener_configuracion
from app.core.errores import ErrorMATU
from app.core.limite_ip import obtener_pepper_limites
from app.modules.care_circle.api.dependencias import ContextoGrupo, SesionDeGrupo
from app.modules.care_circle.api.router_autorizaciones import RegistroDep, RelojDep
from app.modules.catalog.application.ports import CatalogoComercio
from app.modules.catalog.infrastructure.catalogo_simulado import CatalogoComercioDesdeOfertas
from app.modules.catalog.infrastructure.repositorio_catalogo import existencias_publicadas
from app.modules.ordering.api.esquemas import (
    PedidoVista,
    PedidoVistaObservador,
    SolicitudConfirmar,
    SolicitudContacto,
    SolicitudLineas,
    SolicitudPedido,
    SolicitudReglasFaltante,
)
from app.modules.ordering.api.vistas import vista_pedido
from app.modules.ordering.application import pedidos as casos
from app.modules.ordering.application.pedidos import (
    Actor,
    CelularInvalido,
    PedidoAbierto,
    PedidoNoEncontrado,
    PedidoVacio,
    SinAutorizacionPedidos,
    SinDireccion,
    TelefonoRequerido,
    VersionDesactualizada,
)
from app.modules.ordering.application.ports import RepositorioIdempotencia, RepositorioPedidos
from app.modules.ordering.domain import idempotencia
from app.modules.ordering.domain.estados import TransicionInvalida
from app.modules.ordering.domain.pedido import (
    CarritoInvalido,
    LineaPedida,
    NadaDisponible,
    Pedido,
    ReglaPedida,
)
from app.modules.ordering.infrastructure.condiciones import condiciones_vigentes
from app.modules.ordering.infrastructure.repositorio_idempotencia import RepositorioIdempotenciaSQL
from app.modules.ordering.infrastructure.repositorio_pedidos import RepositorioPedidosSQL
from app.shared.puertos import Reloj

router = APIRouter(tags=["pedidos"])

RUTA_PERSONA = "/personas-cuidadas/{persona_id}"
RUTA_PEDIDO = "/pedidos/{pedido_id}"

_PROBLEMA: dict[str, Any] = {"content": {"application/problem+json": {}}}
_ERRORES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Falta el access token, o es inválido o vencido", **_PROBLEMA},
    403: {
        "description": "/errores/sin-autorizacion-pedidos o /errores/revision-vencida, con finalidad: despacho",
        **_PROBLEMA,
    },
    404: {
        "description": "No miembro, rol que no alcanza, pedido o persona de otro grupo, inexistente o eliminada",
        **_PROBLEMA,
    },
    409: {
        "description": "/errores/estado-pedido (con estado), sin-direccion, pedido-vacio, nada-disponible,"
        " pedido-abierto (con pedido_id) o idempotencia-en-curso",
        **_PROBLEMA,
    },
    412: {"description": "/errores/version-desactualizada, con el pedido vigente en actual", **_PROBLEMA},
    422: {
        "description": "Cuerpo o cabeceras inválidos (nombra el campo, nunca el valor), o"
        " /errores/idempotencia-reutilizada",
        **_PROBLEMA,
    },
    428: {"description": "/errores/falta-version (If-Match) o /errores/falta-idempotencia", **_PROBLEMA},
}
# Los POST no llevan If-Match: sin 412
_SIN_412: dict[int | str, dict[str, Any]] = {k: v for k, v in _ERRORES.items() if k != 412}
_LECTURA: dict[int | str, dict[str, Any]] = {401: _ERRORES[401], 404: _ERRORES[404]}
Vista = PedidoVista | PedidoVistaObservador


# --- Dependencias --------------------------------------------------------------------------------------------------


def obtener_repositorio_pedidos(contexto: SesionDeGrupo) -> RepositorioPedidos:
    return RepositorioPedidosSQL(contexto.sesion, contexto.grupo_id)


def obtener_catalogo_comercio_pedido(contexto: SesionDeGrupo) -> CatalogoComercio:
    """El CatalogoComercio de la confirmación: hoy el simulado, con el stock de oferta. Las pruebas lo sobreescriben."""
    return CatalogoComercioDesdeOfertas(lambda comercios: existencias_publicadas(contexto.sesion, comercios))


def obtener_costo_envio() -> int:
    return obtener_configuracion().costo_envio


Repositorio = Annotated[RepositorioPedidos, Depends(obtener_repositorio_pedidos)]
Comercios = Annotated[CatalogoComercio, Depends(obtener_catalogo_comercio_pedido)]
CostoEnvio = Annotated[int, Depends(obtener_costo_envio)]


def _actor(request: Request, contexto: ContextoGrupo) -> Actor:
    return Actor(
        usuario_id=contexto.usuario_id,
        grupo_id=contexto.grupo_id,
        rol=contexto.rol,
        request_id=getattr(request.state, "request_id", None),
    )


def _uuid(valor: str) -> uuid.UUID:
    try:
        return uuid.UUID(valor)
    except ValueError:
        raise ErrorMATU(404) from None


def _sin_autorizacion(error: SinAutorizacionPedidos) -> ErrorMATU:
    if error.revision_vencida:
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
class PersonaParaPedir:
    contexto: ContextoGrupo
    actor: Actor
    persona_id: uuid.UUID


def persona_para_pedir(
    request: Request,
    contexto: SesionDeGrupo,
    persona_id: Annotated[str, Path(json_schema_extra={"format": "uuid"})],
    repositorio: Repositorio,
    reloj: RelojDep,
) -> PersonaParaPedir:
    """404 y 403 antes de las cabeceras y el cuerpo."""
    actor = _actor(request, contexto)
    persona = _uuid(persona_id)
    try:
        casos.exigir_escritura(actor, persona, reloj.ahora(), repositorio, pide_autorizacion=True)
    except PedidoNoEncontrado:
        raise ErrorMATU(404) from None
    except SinAutorizacionPedidos as error:
        raise _sin_autorizacion(error) from None
    return PersonaParaPedir(contexto, actor, persona)


@dataclass(frozen=True)
class PedidoParaEscribir:
    contexto: ContextoGrupo
    actor: Actor
    pedido: Pedido


def _pedido_para_escribir(pide_autorizacion: bool) -> Callable[..., PedidoParaEscribir]:
    def dependencia(
        request: Request,
        contexto: SesionDeGrupo,
        pedido_id: Annotated[str, Path(json_schema_extra={"format": "uuid"})],
        repositorio: Repositorio,
        reloj: RelojDep,
    ) -> PedidoParaEscribir:
        actor = _actor(request, contexto)
        try:
            pedido = casos.pedido_para_escribir(
                actor, _uuid(pedido_id), reloj.ahora(), repositorio, pide_autorizacion=pide_autorizacion
            )
        except PedidoNoEncontrado:
            raise ErrorMATU(404) from None
        except SinAutorizacionPedidos as error:
            raise _sin_autorizacion(error) from None
        return PedidoParaEscribir(contexto, actor, pedido)

    return dependencia


Escribir = Annotated[PedidoParaEscribir, Depends(_pedido_para_escribir(True))]
Cancelar = Annotated[PedidoParaEscribir, Depends(_pedido_para_escribir(False))]


def if_match_obligatorio(if_match: Annotated[str | None, Header(alias="If-Match")] = None) -> str:
    if if_match is None or not if_match.strip() or if_match.strip() == "*":
        raise ErrorMATU(428, detalle="Falta la versión del pedido: envía If-Match con su etag")
    return if_match


def clave_idempotencia(clave: Annotated[str | None, Header(alias="Idempotency-Key")] = None) -> str:
    if clave is None or not clave.strip():
        raise ErrorMATU(
            428,
            tipo="falta-idempotencia",
            titulo="Falta la clave de idempotencia",
            detalle="Envía Idempotency-Key, una clave nueva por cada toque",
        )
    try:
        return idempotencia.exigir_forma(clave.strip())
    except idempotencia.ClaveInvalida:
        raise ErrorMATU(
            422,
            detalle="Revisa las cabeceras indicadas",
            errores=[
                {"campo": "Idempotency-Key", "mensaje": "de 16 a 64 caracteres A-Z, a-z, 0-9, _ y -", "tipo": "forma"}
            ],
        ) from None


IfMatch = Annotated[str, Depends(if_match_obligatorio)]
Clave = Annotated[str, Depends(clave_idempotencia)]


def obtener_repositorio_idempotencia(contexto: SesionDeGrupo, reloj: RelojDep) -> RepositorioIdempotencia:
    return RepositorioIdempotenciaSQL(contexto.sesion, contexto.grupo_id, reloj.ahora())


Idempotencia = Annotated[RepositorioIdempotencia, Depends(obtener_repositorio_idempotencia)]


def llave_idempotencia(pepper: Annotated[bytes | None, Depends(obtener_pepper_limites)]) -> bytes:
    """La llave del HMAC de la huella de la petición (PEPPER_LIMITES). Sin ella, 503: falla cerrado."""
    if not pepper:
        raise ErrorMATU(
            503, detalle="El servicio no está disponible en este momento. Cita el request_id si lo reportas"
        )
    return pepper


Llave = Annotated[bytes, Depends(llave_idempotencia)]


# --- Respuestas ----------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Proyeccion:
    """Lo que la vista necesita además del pedido."""

    rol: str
    reloj: Reloj
    costo_envio: int
    comercios: CatalogoComercio
    repositorio: RepositorioPedidos

    def de(self, pedido: Pedido) -> Vista:
        return vista_pedido(
            pedido,
            rol=self.rol,
            ahora=self.reloj.ahora(),
            costo_envio_vigente=self.costo_envio,
            precios_de_ejemplo=self.comercios.precios_de_ejemplo,
            condiciones=condiciones_vigentes(),
            celular_de_quien_lee=self.repositorio.celular_verificado(),
        )


def _proyeccion(
    contexto: SesionDeGrupo, reloj: RelojDep, costo: CostoEnvio, comercios: Comercios, repositorio: Repositorio
) -> Proyeccion:
    return Proyeccion(contexto.rol, reloj, costo, comercios, repositorio)


Proyectar = Annotated[Proyeccion, Depends(_proyeccion)]


def _responder(response: Response, vista: Vista) -> Vista:
    response.headers["Cache-Control"] = "no-store"
    if isinstance(vista, PedidoVista):
        response.headers["ETag"] = vista.etag
    return vista


def _errores_de(error: CarritoInvalido) -> ErrorMATU:
    return ErrorMATU(
        422,
        detalle="Revisa los campos indicados",
        errores=[{"campo": e.campo, "mensaje": e.mensaje, "tipo": e.tipo} for e in error.errores],
    )


def _traducir(error: Exception, proyectar: Proyeccion) -> ErrorMATU:
    """Los errores de negocio, en RFC 7807. Ninguno lleva un dato del pedido salvo el estado y el id."""
    if isinstance(error, PedidoNoEncontrado):
        return ErrorMATU(404)
    if isinstance(error, SinAutorizacionPedidos):
        return _sin_autorizacion(error)
    if isinstance(error, CarritoInvalido):
        return _errores_de(error)
    if isinstance(error, TelefonoRequerido):
        return ErrorMATU(
            422,
            detalle="Revisa los campos indicados",
            errores=[
                {"campo": "telefono_contacto", "mensaje": "falta un teléfono de contacto", "tipo": "telefono_requerido"}
            ],
        )
    if isinstance(error, CelularInvalido):
        return ErrorMATU(
            422,
            detalle="Revisa los campos indicados",
            errores=[{"campo": "telefono_contacto", "mensaje": "no es un celular chileno", "tipo": "celular_invalido"}],
        )
    if isinstance(error, VersionDesactualizada):
        actual = proyectar.de(error.actual)
        return ErrorMATU(
            412,
            detalle="Otra persona cambió el pedido. Revisa el vigente",
            headers={"ETag": error.actual.etag},
            extension={"actual": actual.model_dump(mode="json")},
        )
    if isinstance(error, TransicionInvalida):
        return ErrorMATU(
            409,
            tipo="estado-pedido",
            detalle="El estado del pedido no permite esta acción",
            extension={"estado": error.estado.value},
        )
    if isinstance(error, PedidoAbierto):
        return ErrorMATU(
            409,
            tipo="pedido-abierto",
            detalle="Esta persona ya tiene un pedido sin pagar",
            extension={"pedido_id": str(error.pedido_id)},
        )
    if isinstance(error, PedidoVacio):
        return ErrorMATU(409, tipo="pedido-vacio", detalle="El pedido no tiene productos")
    if isinstance(error, SinDireccion):
        return ErrorMATU(409, tipo="sin-direccion", detalle="Falta la dirección de entrega")
    if isinstance(error, NadaDisponible):
        return ErrorMATU(409, tipo="nada-disponible", detalle="Ningún comercio tiene los productos del pedido")
    raise error


ERRORES_DE_NEGOCIO = (
    PedidoNoEncontrado,
    SinAutorizacionPedidos,
    CarritoInvalido,
    TelefonoRequerido,
    CelularInvalido,
    VersionDesactualizada,
    TransicionInvalida,
    PedidoAbierto,
    PedidoVacio,
    SinDireccion,
    NadaDisponible,
)


@dataclass(frozen=True)
class Repeticion:
    """Una petición repetida con la misma clave: el código guardado y el pedido como está ahora."""

    estado_http: int
    pedido_id: uuid.UUID


def _reservar(
    repositorio: RepositorioIdempotencia,
    endpoint: str,
    clave: str,
    actor: Actor,
    cuerpo: Any,
    reloj: Reloj,
    llave: bytes,
) -> Repeticion | None:
    """None si la petición es nueva y quedó reservada; una Repeticion si ya terminó antes con la misma clave."""
    ahora = reloj.ahora()
    huella = idempotencia.huella_peticion(endpoint, cuerpo, llave)
    vence = idempotencia.expira_en(ahora)
    existente = repositorio.reservar(endpoint, clave, actor.usuario_id, huella, vence)
    decision = idempotencia.decidir(existente, actor.usuario_id, huella, ahora)
    if decision is idempotencia.Decision.NUEVA:
        if existente is not None:
            repositorio.reemplazar(endpoint, clave, huella, vence)
        return None
    if decision is idempotencia.Decision.REUTILIZADA:
        raise ErrorMATU(
            422,
            tipo="idempotencia-reutilizada",
            titulo="Clave de idempotencia reutilizada",
            detalle="Esa Idempotency-Key ya se usó con otra petición: usa una nueva",
        )
    if decision is idempotencia.Decision.EN_CURSO:
        raise ErrorMATU(
            409, tipo="idempotencia-en-curso", detalle="Una petición con esta clave todavía no termina: reintenta"
        )
    assert existente is not None and existente.estado_http is not None and existente.pedido_id is not None
    return Repeticion(existente.estado_http, existente.pedido_id)


def _repetir(response: Response, repeticion: Repeticion, actor: Actor, proyectar: Proyeccion) -> Vista:
    try:
        pedido = casos.leer(actor, repeticion.pedido_id, proyectar.repositorio)
    except PedidoNoEncontrado:
        raise ErrorMATU(404) from None
    response.status_code = repeticion.estado_http
    return _responder(response, proyectar.de(pedido))


# --- Rutas ---------------------------------------------------------------------------------------------------------


@router.post(
    RUTA_PERSONA + "/pedidos",
    status_code=status.HTTP_201_CREATED,
    response_model=PedidoVista,
    responses=_SIN_412,
    summary="Crear el carrito (borrador) con productos del catálogo",
    description=(
        "MATU-61 (decisiones 193 a 196). admin y cuidador, con la autorización despacho vigente. Idempotency-Key"
        " obligatoria. Un solo pedido sin pagar por persona (409 pedido-abierto, C4). El servidor fija el precio y el"
        " comercio de cada línea desde la oferta (C15) y no lee el consumo (C20). Registra pedido.crear. Capa 3"
    ),
)
def crear_pedido(
    response: Response,
    persona: Annotated[PersonaParaPedir, Depends(persona_para_pedir)],
    clave: Clave,
    solicitud: SolicitudPedido,
    repositorio: Repositorio,
    idem: Idempotencia,
    llave: Llave,
    registro: RegistroDep,
    reloj: RelojDep,
    costo: CostoEnvio,
    proyectar: Proyectar,
) -> Vista:
    endpoint = f"POST /v1/personas-cuidadas/{persona.persona_id}/pedidos"
    repeticion = _reservar(idem, endpoint, clave, persona.actor, solicitud.model_dump(mode="json"), reloj, llave)
    if repeticion is not None:
        vista = _repetir(response, repeticion, persona.actor, proyectar)
        response.headers["Location"] = f"/v1/pedidos/{repeticion.pedido_id}"
        return vista
    pedidas = [LineaPedida(oferta_id=x.oferta_id, cantidad=x.cantidad) for x in solicitud.lineas]
    try:
        pedido = casos.crear(persona.actor, persona.persona_id, pedidas, reloj.ahora(), costo, repositorio, registro)
    except ERRORES_DE_NEGOCIO as error:
        raise _traducir(error, proyectar) from None
    idem.completar(endpoint, clave, status.HTTP_201_CREATED, pedido.id)
    response.headers["Location"] = f"/v1/pedidos/{pedido.id}"
    return _responder(response, proyectar.de(pedido))


@router.get(
    RUTA_PERSONA + "/pedido-en-curso",
    response_model=Vista,
    responses=_LECTURA,
    summary="El pedido sin pagar de la persona, para volver al carrito",
    description=(
        "MATU-61 (decisión 197, C4). Los cuatro roles, con la proyección del rol (C3). 404 si la persona no tiene un"
        " pedido sin pagar. No pide la autorización despacho. No se audita. Capa 3"
    ),
)
def ver_en_curso(
    request: Request,
    response: Response,
    contexto: SesionDeGrupo,
    persona_id: Annotated[str, Path(json_schema_extra={"format": "uuid"})],
    proyectar: Proyectar,
) -> Vista:
    try:
        pedido = casos.en_curso(_actor(request, contexto), _uuid(persona_id), proyectar.repositorio)
    except PedidoNoEncontrado:
        raise ErrorMATU(404) from None
    return _responder(response, proyectar.de(pedido))


@router.get(
    RUTA_PEDIDO,
    response_model=Vista,
    responses=_LECTURA,
    summary="Leer el pedido, con el resumen antes de pagar si el total está confirmado",
    description=(
        "MATU-61 (decisiones 198 y 205). Los cuatro roles: PedidoVista para admin, cuidador y pagador, y"
        " PedidoVistaObservador, sin entrega ni resumen, para el observador (C3). El vencimiento lo dice el Reloj."
        " No se audita. Capa 3"
    ),
)
def ver_pedido(
    request: Request,
    response: Response,
    contexto: SesionDeGrupo,
    pedido_id: Annotated[str, Path(json_schema_extra={"format": "uuid"})],
    proyectar: Proyectar,
) -> Vista:
    try:
        pedido = casos.leer(_actor(request, contexto), _uuid(pedido_id), proyectar.repositorio)
    except PedidoNoEncontrado:
        raise ErrorMATU(404) from None
    return _responder(response, proyectar.de(pedido))


@router.put(
    RUTA_PEDIDO + "/lineas",
    response_model=PedidoVista,
    responses=_ERRORES,
    summary="Ajustar el carrito: cantidades, agregar y sacar productos",
    description=(
        "MATU-61 (decisión 199). Solo en borrador (con el total confirmado, primero POST …/cambiar). Reemplaza todas"
        " las líneas; admite []. If-Match obligatorio. No se audita. Capa 3"
    ),
)
def reemplazar_lineas(
    response: Response,
    escribir: Escribir,
    if_match: IfMatch,
    solicitud: SolicitudLineas,
    reloj: RelojDep,
    proyectar: Proyectar,
) -> Vista:
    pedidas = [LineaPedida(oferta_id=x.oferta_id, cantidad=x.cantidad) for x in solicitud.lineas]
    try:
        pedido = casos.reemplazar_lineas(
            escribir.actor, escribir.pedido, pedidas, if_match, reloj.ahora(), proyectar.repositorio
        )
    except ERRORES_DE_NEGOCIO as error:
        raise _traducir(error, proyectar) from None
    return _responder(response, proyectar.de(pedido))


@router.put(
    RUTA_PEDIDO + "/reglas-faltante",
    response_model=PedidoVista,
    responses=_ERRORES,
    summary="Qué hacer si falta cada producto (RF-21)",
    description=(
        "MATU-61 (decisión 200). otro_comercio o quitar, nunca otra marca. En borrador, total confirmado y vencido;"
        " no cambia el total ni el plazo. If-Match obligatorio. Registra pedido.regla_faltante, sin las acciones."
        " Capa 3"
    ),
)
def reemplazar_reglas(
    response: Response,
    escribir: Escribir,
    if_match: IfMatch,
    solicitud: SolicitudReglasFaltante,
    registro: RegistroDep,
    reloj: RelojDep,
    proyectar: Proyectar,
) -> Vista:
    pedidas = [ReglaPedida(producto_id=x.producto_id, regla=x.accion) for x in solicitud.reglas]
    try:
        pedido = casos.reemplazar_reglas(
            escribir.actor, escribir.pedido, pedidas, if_match, reloj.ahora(), proyectar.repositorio, registro
        )
    except ERRORES_DE_NEGOCIO as error:
        raise _traducir(error, proyectar) from None
    return _responder(response, proyectar.de(pedido))


@router.post(
    RUTA_PEDIDO + "/confirmar",
    response_model=PedidoVista,
    responses=_SIN_412,
    summary="Confirmar que haya cada producto y fijar el total por 15 minutos",
    description=(
        "MATU-61 (decisiones 201 a 205; C1 y C5). Desde borrador, vencido o un total vigente, que se reemplaza. Una"
        " consulta de stock por comercio. Con otro_comercio busca el mismo producto en el comercio de menor precio;"
        " con quitar, lo que falta sale. Total = subtotal + un envío, con IVA incluido. Idempotency-Key obligatoria."
        " Registra pedido.confirmar. No crea el cargo (MATU-62). Capa 3"
    ),
)
def confirmar(
    response: Response,
    escribir: Escribir,
    clave: Clave,
    idem: Idempotencia,
    llave: Llave,
    registro: RegistroDep,
    reloj: RelojDep,
    costo: CostoEnvio,
    comercios: Comercios,
    proyectar: Proyectar,
    solicitud: Annotated[SolicitudConfirmar | None, Body()] = None,
) -> Vista:
    cuerpo = solicitud or SolicitudConfirmar()
    endpoint = f"POST /v1/pedidos/{escribir.pedido.id}/confirmar"
    repeticion = _reservar(idem, endpoint, clave, escribir.actor, cuerpo.model_dump(mode="json"), reloj, llave)
    if repeticion is not None:
        return _repetir(response, repeticion, escribir.actor, proyectar)
    try:
        pedido = casos.confirmar(
            escribir.actor,
            escribir.pedido,
            cuerpo.telefono_contacto,
            reloj.ahora(),
            costo,
            proyectar.repositorio,
            comercios,
            registro,
        )
    except ERRORES_DE_NEGOCIO as error:
        raise _traducir(error, proyectar) from None
    idem.completar(endpoint, clave, status.HTTP_200_OK, pedido.id)
    return _responder(response, proyectar.de(pedido))


@router.put(
    RUTA_PEDIDO + "/contacto",
    response_model=PedidoVista,
    responses=_ERRORES,
    summary="Cambiar el teléfono de contacto desde el resumen",
    description=(
        "MATU-61 (decisión 203). En total confirmado y vencido; no toca el total ni el plazo. If-Match obligatorio."
        " No se audita. Capa 3"
    ),
)
def cambiar_contacto(
    response: Response,
    escribir: Escribir,
    if_match: IfMatch,
    solicitud: SolicitudContacto,
    reloj: RelojDep,
    proyectar: Proyectar,
) -> Vista:
    try:
        pedido = casos.cambiar_contacto(
            escribir.actor, escribir.pedido, solicitud.telefono_contacto, if_match, reloj.ahora(), proyectar.repositorio
        )
    except ERRORES_DE_NEGOCIO as error:
        raise _traducir(error, proyectar) from None
    return _responder(response, proyectar.de(pedido))


@router.post(
    RUTA_PEDIDO + "/cambiar",
    response_model=PedidoVista,
    responses=_SIN_412,
    summary="Volver al carrito desde el total confirmado o vencido («Cambiar el pedido»)",
    description=(
        "MATU-61 (decisión 218; C1 y C9). total_confirmado o vencido → borrador: descarta el total, las partes por"
        " comercio y la entrega; cada línea vuelve al carrito. Idempotency-Key obligatoria. No se audita. Capa 3"
    ),
)
def cambiar_pedido(
    response: Response,
    escribir: Escribir,
    clave: Clave,
    idem: Idempotencia,
    llave: Llave,
    reloj: RelojDep,
    proyectar: Proyectar,
) -> Vista:
    endpoint = f"POST /v1/pedidos/{escribir.pedido.id}/cambiar"
    repeticion = _reservar(idem, endpoint, clave, escribir.actor, {}, reloj, llave)
    if repeticion is not None:
        return _repetir(response, repeticion, escribir.actor, proyectar)
    try:
        pedido = casos.cambiar_pedido(escribir.actor, escribir.pedido, reloj.ahora(), proyectar.repositorio)
    except ERRORES_DE_NEGOCIO as error:
        raise _traducir(error, proyectar) from None
    idem.completar(endpoint, clave, status.HTTP_200_OK, pedido.id)
    return _responder(response, proyectar.de(pedido))


@router.post(
    RUTA_PEDIDO + "/cancelar",
    response_model=PedidoVista,
    responses={k: v for k, v in _ERRORES.items() if k not in (403, 412)},
    summary="Cancelar un pedido sin pagar, sin costo",
    description=(
        "MATU-61 (decisión 206). Desde borrador, total confirmado o vencido; borra la copia de la entrega. No pide la"
        " autorización despacho. Idempotency-Key obligatoria: la repetición responde 200. Registra pedido.cancelar."
        " Capa 3"
    ),
)
def cancelar(
    response: Response,
    escribir: Cancelar,
    clave: Clave,
    idem: Idempotencia,
    llave: Llave,
    registro: RegistroDep,
    reloj: RelojDep,
    proyectar: Proyectar,
) -> Vista:
    endpoint = f"POST /v1/pedidos/{escribir.pedido.id}/cancelar"
    repeticion = _reservar(idem, endpoint, clave, escribir.actor, {}, reloj, llave)
    if repeticion is not None:
        return _repetir(response, repeticion, escribir.actor, proyectar)
    try:
        pedido = casos.cancelar(escribir.actor, escribir.pedido, reloj.ahora(), proyectar.repositorio, registro)
    except ERRORES_DE_NEGOCIO as error:
        raise _traducir(error, proyectar) from None
    idem.completar(endpoint, clave, status.HTTP_200_OK, pedido.id)
    return _responder(response, proyectar.de(pedido))
