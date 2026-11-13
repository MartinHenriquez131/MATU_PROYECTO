"""La vista del comercio (MATU-63; D-63-1, D-63-2, D-63-4, D-63-7; O2 a O6; decisiones 407 a 416).

Capa 3: va en ROUTERS_CAPA_3 de app/main.py. Cache-Control: no-store bajo /v1/comercio (app.main).

- El comercio lee y escribe solo por las funciones de la 0029, en su sesión (app.comercio_id, sin grupo).
- Cada acción sobre una parte termina en su transacción, y después de la respuesta (BackgroundTasks) el sistema lleva
  el pedido y devuelve lo que faltó en otra, con el grupo del pedido (D-63-8): nunca en la sesión del comercio. Si esa
  segunda transacción falla, la respuesta del comercio no cambia y la tarea ``despacho`` la repite.
- Una parte de otro comercio, o que no existe: 404 (nunca 403). La versión de la parte es su ETag; con If-Match que no
  calza, 412.
- El código va solo en el cuerpo. Nunca en la URL, los logs, la auditoría ni los eventos. Límite por cuenta en Redis.
"""

import logging
import uuid
from datetime import datetime, time
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Path, Request, Response
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import obtener_configuracion
from app.core.db import obtener_fabrica_sesiones
from app.core.errores import ErrorMATU
from app.modules.backoffice.api.dependencias import (
    Contador,
    PepperLimites,
    SecretoCodigo,
    SesionDeComercio,
    contar_intento_de_codigo,
)
from app.modules.backoffice.api.esquemas import (
    ComercioVista,
    LineaComercioVista,
    ListaPartes,
    ListaProductos,
    ParteResumen,
    ParteVista,
    ProductoLinea,
    ProductoVista,
    ResultadoCodigoVista,
    SolicitudCodigo,
    SolicitudMarca,
    SolicitudProducto,
)
from app.modules.backoffice.application.despacho import llevar
from app.modules.backoffice.infrastructure.sistema import AbrirDespachoSQL, resolver_parte
from app.modules.care_circle.api.router_autorizaciones import RelojDep
from app.modules.fulfillment.application.ports import ParteComercio, ProductoComercio
from app.modules.fulfillment.domain.despacho import (
    MarcaLinea,
    estado_codigo,
    huella_codigo,
    preparar_antes_de,
)
from app.modules.fulfillment.infrastructure.repositorio_comercio import RepositorioComercioSQL
from app.modules.payments.application.ports import PasarelaWebpay
from app.modules.payments.domain.retracto import ZONA_CHILE
from app.modules.payments.infrastructure.pasarela import obtener_pasarela
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.auditoria_sql import RegistroAuditoriaSql
from app.shared.puertos import Reloj

log = logging.getLogger("matu.backoffice.comercio")

router = APIRouter(prefix="/comercio", tags=["comercio"])

_PROBLEMA: dict[str, Any] = {"content": {"application/problem+json": {}}}
_Respuestas = dict[int | str, dict[str, Any]]
_ID = Annotated[str, Path(json_schema_extra={"format": "uuid"})]
IfMatch = Annotated[str | None, Header(alias="If-Match")]
PasarelaDep = Annotated[PasarelaWebpay | None, Depends(obtener_pasarela)]
Fabrica = Annotated[sessionmaker[Session], Depends(obtener_fabrica_sesiones)]

_RESPUESTAS: _Respuestas = {
    401: {"description": "no-autenticado o token-invalido", **_PROBLEMA},
    403: {"description": "comercio-inactivo: la cuenta o el comercio no están activos", **_PROBLEMA},
    404: {"description": "No es una cuenta de comercio, o la parte o la línea no son de este comercio", **_PROBLEMA},
}
_RESPUESTAS_ACCION: _Respuestas = {
    **_RESPUESTAS,
    409: {"description": "estado-parte: la parte no está en el estado que la acción pide", **_PROBLEMA},
    412: {"description": "version-desactualizada: el If-Match no es la versión actual de la parte", **_PROBLEMA},
    422: {"description": "Cuerpo inválido, o lineas-pendientes al marcar listo", **_PROBLEMA},
}


def _uuid(valor: str) -> uuid.UUID:
    try:
        return uuid.UUID(valor)
    except ValueError:
        raise ErrorMATU(404) from None


def _etag(version: int) -> str:
    return f'"v{version}"'


def _version(if_match: str | None) -> int | None:
    if if_match is None:
        return None
    valor = if_match.strip().removeprefix("W/").strip('"')
    if not valor.startswith("v") or not valor[1:].isdigit():
        raise ErrorMATU(412, tipo="version-desactualizada", detalle="Este pedido cambió mientras lo veías")
    return int(valor[1:])


def _resumen(p: ParteComercio, ahora: datetime) -> dict[str, object]:
    return {
        "id": p.id,
        "referencia": p.referencia,
        "estado": p.estado.value,
        "enviado_en": p.enviado_en,
        "preparar_antes_de": preparar_antes_de(p.enviado_en),
        "estado_codigo": estado_codigo(
            generado_en=p.codigo_generado_en,
            con_hash=p.codigo_con_hash,
            expira_en=p.codigo_expira_en,
            usado_en=p.codigo_usado_en,
            bloqueado_en=p.codigo_bloqueado_en,
            ahora=ahora,
        ).value,
        "numero_lineas": p.lineas,
        "retirada_en": p.retirada_en,
        "cancelada_en": p.cancelada_en,
    }


def _vista(repo: RepositorioComercioSQL, parte_id: uuid.UUID, ahora: datetime, respuesta: Response) -> ParteVista:
    parte = repo.parte(parte_id)
    if parte is None:
        raise ErrorMATU(404)
    lineas = [
        LineaComercioVista(
            id=x.id,
            producto=ProductoLinea(nombre=x.producto_nombre, presentacion=x.presentacion),
            cantidad=x.cantidad,
            estado_linea=x.estado_linea,  # type: ignore[arg-type]
            unidades_faltantes=x.unidades_faltantes,
        )
        for x in repo.lineas(parte_id)
    ]
    respuesta.headers["ETag"] = _etag(parte.version)
    return ParteVista(**_resumen(parte, ahora), lineas=lineas)  # type: ignore[arg-type]


def _auditar(contexto: SesionDeComercio, reloj: Reloj, accion: AccionAuditoria, entidad_id: uuid.UUID,
             entidad: EntidadAuditoria = EntidadAuditoria.PEDIDO_COMERCIO, request: Request | None = None) -> None:
    RegistroAuditoriaSql(contexto.sesion, reloj).registrar(
        EntradaAuditoria(
            grupo_id=None,
            actor_tipo=ActorTipo.COMERCIO,
            actor_ref=contexto.usuario_id,
            accion=accion,
            entidad=entidad,
            entidad_id=entidad_id,
            request_id=None if request is None else getattr(request.state, "request_id", None),
        )
    )


def _resultado(resultado: str) -> None:
    """El resultado de una función del comercio que no es ok, como problema RFC 7807."""
    if resultado == "no_encontrada":
        raise ErrorMATU(404)
    if resultado == "version":
        raise ErrorMATU(412, tipo="version-desactualizada", detalle="Este pedido cambió mientras lo veías")
    if resultado == "estado":
        raise ErrorMATU(409, tipo="estado-parte", detalle="Este pedido cambió mientras lo veías")
    if resultado == "invalida":
        raise ErrorMATU(422, detalle="Marca si lo tienes o cuántos te faltan, hasta la cantidad del pedido")
    if resultado == "lineas_pendientes":
        raise ErrorMATU(422, tipo="lineas-pendientes", detalle="Marca cada producto: si lo tienes o no")


def _llevar(fabrica: sessionmaker[Session], reloj: Reloj, pasarela: PasarelaWebpay | None,
            parte_id: uuid.UUID, comercio_id: uuid.UUID) -> None:
    """La transacción del sistema después de la del comercio (D-63-8). Si falla, la tarea despacho la repite."""
    try:
        ids = resolver_parte(fabrica, parte_id)
        if ids is None:
            return
        pedido_id, grupo_id = ids
        with AbrirDespachoSQL(fabrica, reloj)(grupo_id) as (unidad, _):
            llevar(unidad, pasarela, pedido_id, reloj.ahora(), comercio_id)
    except Exception as error:  # noqa: BLE001 - la acción del comercio ya quedó; la tarea despacho termina el resto
        log.warning("despacho pendiente", extra={"tipo_error": type(error).__name__})


@router.get("", response_model=ComercioVista, responses=_RESPUESTAS,
            description="El comercio de la cuenta: nombre de fantasía, si es de prueba y el contacto de MATU (O2).")
def ver_comercio(contexto: SesionDeComercio) -> ComercioVista:
    comercio = RepositorioComercioSQL(contexto.sesion).comercio()
    if comercio is None:
        raise ErrorMATU(404)
    return ComercioVista(
        nombre_fantasia=comercio.nombre_fantasia,
        ficticio=comercio.ficticio,
        contacto=obtener_configuracion().correo_privacidad,
    )


@router.get(
    "/partes",
    response_model=ListaPartes,
    responses=_RESPUESTAS,
    description=(
        "Las partes del comercio: las por preparar, preparando y listas, y las retiradas o canceladas hoy (fecha de"
        " Chile). Solo la proyección de D-63-1: referencia opaca, estado, cuándo llegó, «preparar antes de» (dos"
        " horas después), el estado del código y el número de productos."
    ),
)
def listar_partes(contexto: SesionDeComercio, reloj: RelojDep) -> ListaPartes:
    ahora = reloj.ahora()
    hoy = datetime.combine(ahora.astimezone(ZONA_CHILE).date(), time(0, 0), tzinfo=ZONA_CHILE)
    partes = RepositorioComercioSQL(contexto.sesion).partes(hoy)
    return ListaPartes(partes=[ParteResumen(**_resumen(p, ahora)) for p in partes])  # type: ignore[arg-type]


@router.get("/partes/{parte_id}", response_model=ParteVista, responses=_RESPUESTAS,
            description="Una parte con sus productos y lo marcado. El ETag es la versión de la parte.")
def ver_parte(parte_id: _ID, contexto: SesionDeComercio, reloj: RelojDep, respuesta: Response) -> ParteVista:
    return _vista(RepositorioComercioSQL(contexto.sesion), _uuid(parte_id), reloj.ahora(), respuesta)


@router.post("/partes/{parte_id}/preparar", response_model=ParteVista, responses=_RESPUESTAS_ACCION,
             description="«Empezar a preparar»: de enviada a preparando. Desde aquí la familia ya no cancela (R15).")
def preparar(
    parte_id: _ID, request: Request, contexto: SesionDeComercio, reloj: RelojDep, respuesta: Response,
    fabrica: Fabrica, pasarela: PasarelaDep, tareas: BackgroundTasks, if_match: IfMatch = None,
) -> ParteVista:
    identificador, repo = _uuid(parte_id), RepositorioComercioSQL(contexto.sesion)
    _resultado(repo.preparar(identificador, _version(if_match), reloj.ahora()))
    _auditar(contexto, reloj, AccionAuditoria.COMERCIO_PREPARAR, identificador, request=request)
    vista = _vista(repo, identificador, reloj.ahora(), respuesta)
    # Después de la respuesta, con la transacción del comercio ya cerrada
    tareas.add_task(_llevar, fabrica, reloj, pasarela, identificador, contexto.comercio_id)
    return vista


@router.put(
    "/partes/{parte_id}/lineas/{linea_id}",
    response_model=ParteVista,
    responses=_RESPUESTAS_ACCION,
    description=(
        "Marca un producto: «Lo tengo» (preparada) o «No lo tengo» (faltante, con cuántos faltan; sin el número,"
        " faltan todos). Se puede cambiar mientras la parte esté preparando (O4). No mueve dinero."
    ),
)
def marcar_linea(
    parte_id: _ID, linea_id: _ID, solicitud: SolicitudMarca, request: Request, contexto: SesionDeComercio,
    reloj: RelojDep, respuesta: Response, if_match: IfMatch = None,
) -> ParteVista:
    parte, linea = _uuid(parte_id), _uuid(linea_id)
    repo = RepositorioComercioSQL(contexto.sesion)
    if solicitud.estado == MarcaLinea.PREPARADA:
        faltantes = 0
    elif solicitud.unidades_faltantes is not None:
        faltantes = solicitud.unidades_faltantes
    else:
        actual = next((x for x in repo.lineas(parte) if x.id == linea), None)
        if actual is None:
            raise ErrorMATU(404)
        faltantes = actual.cantidad
    _resultado(repo.marcar_linea(parte, linea, solicitud.estado, faltantes, _version(if_match)))
    _auditar(contexto, reloj, AccionAuditoria.COMERCIO_MARCAR_LINEA, parte, request=request)
    return _vista(repo, parte, reloj.ahora(), respuesta)


@router.post(
    "/partes/{parte_id}/listo",
    response_model=ParteVista,
    responses=_RESPUESTAS_ACCION,
    description=(
        "«Listo para retirar»: con todo marcado, la parte queda lista, y lo preparado sale del stock (O5). Si no tiene"
        " ninguno, queda cancelada con motivo producto_faltante (O3). Después, el sistema devuelve lo que faltó a la"
        " misma tarjeta (D-63-8)."
    ),
)
def listo(
    parte_id: _ID, request: Request, contexto: SesionDeComercio, reloj: RelojDep, respuesta: Response,
    fabrica: Fabrica, pasarela: PasarelaDep, tareas: BackgroundTasks, if_match: IfMatch = None,
) -> ParteVista:
    identificador, repo = _uuid(parte_id), RepositorioComercioSQL(contexto.sesion)
    resultado = repo.listo(identificador, _version(if_match), reloj.ahora())
    if resultado not in ("lista", "cancelada"):
        _resultado(resultado)
    _auditar(contexto, reloj, AccionAuditoria.COMERCIO_LISTO, identificador, request=request)
    vista = _vista(repo, identificador, reloj.ahora(), respuesta)
    # Después de la respuesta, con la transacción del comercio ya cerrada
    tareas.add_task(_llevar, fabrica, reloj, pasarela, identificador, contexto.comercio_id)
    return vista


@router.post(
    "/partes/{parte_id}/validar-codigo",
    response_model=ResultadoCodigoVista,
    responses={
        **_RESPUESTAS,
        422: {"description": "El código no son 6 cifras. No cuenta como intento", **_PROBLEMA},
        429: {"description": "demasiados-intentos: 20 por hora por cuenta, con Retry-After", **_PROBLEMA},
        503: {"description": "Falta CODIGO_RETIRO_SECRETO o PEPPER_LIMITES, o Redis no responde", **_PROBLEMA},
    },
    description=(
        "Revisa el código que muestra quien retira. El código va solo en el cuerpo. Correcto: la parte queda"
        " retirada. Cinco intentos fallidos lo bloquean; vence a los 90 minutos y sirve una vez (D-63-4)."
    ),
)
def validar_codigo(
    parte_id: _ID, solicitud: SolicitudCodigo, request: Request, contexto: SesionDeComercio, reloj: RelojDep,
    respuesta: Response, fabrica: Fabrica, pasarela: PasarelaDep, secreto: SecretoCodigo, pepper: PepperLimites,
    contador: Contador, tareas: BackgroundTasks,
) -> ResultadoCodigoVista:
    identificador, repo = _uuid(parte_id), RepositorioComercioSQL(contexto.sesion)
    contar_intento_de_codigo(contexto.usuario_id, pepper, contador)
    ahora = reloj.ahora()
    huella = huella_codigo(secreto, identificador, solicitud.codigo)
    resultado, restantes = repo.validar_codigo(identificador, huella, ahora)
    if resultado in ("no_encontrada", "estado"):
        _resultado(resultado)
    accion = {
        "correcto": AccionAuditoria.COMERCIO_CODIGO_CORRECTO,
        "no_es": AccionAuditoria.COMERCIO_CODIGO_INCORRECTO,
        "bloqueado": AccionAuditoria.COMERCIO_CODIGO_BLOQUEO,
    }.get(resultado)
    if accion is not None:
        _auditar(contexto, reloj, accion, identificador, request=request)
    vista = _vista(repo, identificador, ahora, respuesta)
    if resultado == "correcto":
        tareas.add_task(_llevar, fabrica, reloj, pasarela, identificador, contexto.comercio_id)
    return ResultadoCodigoVista(resultado=resultado, intentos_restantes=restantes, parte=vista)  # type: ignore[arg-type]


def _etag_producto(p: ProductoComercio) -> str:
    return f'"o{int(p.actualizado_en.timestamp() * 1_000_000)}"'


def _producto(p: ProductoComercio) -> ProductoVista:
    return ProductoVista(
        oferta_id=p.oferta_id,
        nombre=p.nombre,
        presentacion=p.presentacion,
        precio=p.precio,
        stock=p.stock,
        apartado=p.apartado,
        disponibles=max(p.stock - p.apartado, 0),
        disponible=p.disponible,
        etag=_etag_producto(p),
    )


@router.get("/productos", response_model=ListaProductos, responses=_RESPUESTAS,
            description="Los productos del comercio: precio (solo lectura), stock, apartado y disponibles (O5).")
def listar_productos(contexto: SesionDeComercio, reloj: RelojDep) -> ListaProductos:
    productos = RepositorioComercioSQL(contexto.sesion).productos(reloj.ahora())
    return ListaProductos(productos=[_producto(p) for p in productos])


@router.patch(
    "/productos/{oferta_id}",
    response_model=ProductoVista,
    responses={**_RESPUESTAS, 412: _RESPUESTAS_ACCION[412], 422: _RESPUESTAS_ACCION[422]},
    description="Cambia cuántos tiene (0 a 9.999) y si lo ofrece en MATU. Nunca el precio (D-63-2).",
)
def cambiar_producto(
    oferta_id: _ID, solicitud: SolicitudProducto, request: Request, contexto: SesionDeComercio, reloj: RelojDep,
    respuesta: Response, if_match: IfMatch = None,
) -> ProductoVista:
    identificador, repo = _uuid(oferta_id), RepositorioComercioSQL(contexto.sesion)
    actual = next((p for p in repo.productos(reloj.ahora()) if p.oferta_id == identificador), None)
    if actual is None:
        raise ErrorMATU(404)
    antes = None
    if if_match is not None:
        if if_match.strip().removeprefix("W/") != _etag_producto(actual):
            raise ErrorMATU(412, tipo="version-desactualizada", detalle="Otra persona cambió este producto")
        antes = actual.actualizado_en
    cambio = repo.cambiar_producto(identificador, solicitud.stock, solicitud.disponible, antes, reloj.ahora())
    if cambio is None:
        raise ErrorMATU(404)
    if not cambio:
        raise ErrorMATU(412, tipo="version-desactualizada", detalle="Otra persona cambió este producto")
    _auditar(
        contexto, reloj, AccionAuditoria.COMERCIO_PRODUCTOS_CAMBIAR, identificador, EntidadAuditoria.OFERTA, request
    )
    nuevo = next(p for p in repo.productos(reloj.ahora()) if p.oferta_id == identificador)
    respuesta.headers["ETag"] = _etag_producto(nuevo)
    return _producto(nuevo)
