"""Rutas del perfil de consumo (MATU-36, RF-10 y RF-11). Contrato: docs/api/openapi.json.

    GET    /v1/personas-cuidadas/{persona_id}/consumo                         los cuatro roles. 200
    POST   /v1/personas-cuidadas/{persona_id}/consumo                         admin y cuidador. 201
    GET    /v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}             los cuatro roles. 200
    PATCH  /v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}             admin y cuidador. 200, If-Match
    DELETE /v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}             admin y cuidador. 204 (decisión 69)
    POST   /v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}/desactivar  admin y cuidador. 200
    POST   /v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}/activar     admin y cuidador. 200 (decisión 68)

El rol, la persona y la autorización para ``consumo`` se verifican en las dependencias, antes del
cuerpo. Un perfil_id que no es UUID o no es de la persona: 404, después del 403. unidades_por_envase
(MATU-60, decisión 121) es opcional y, en el PATCH, el único campo que admite null, que lo borra. nombre_libre nunca
llega a los logs: la línea de la petición lleva la plantilla de la ruta, el usuario y el grupo, y los
422 nombran el campo, nunca el valor. Toda respuesta lleva Cache-Control: no-store (app.main).
"""

import base64
import binascii
import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Header, Query, Request, Response, status
from fastapi.responses import JSONResponse

from app.core.errores import ErrorMATU, respuesta_problema
from app.modules.consumption.api.dependencias import (
    Auditoria,
    ParaEscribir,
    ParaLeer,
    PerfilIdRuta,
    RelojDep,
    Repositorio,
    uuid_o_404,
)
from app.modules.consumption.api.esquemas import (
    AutorPerfilVista,
    ListaPerfiles,
    PerfilConsumoVista,
    ProblemaVersionPerfilVista,
    ProductoResumen,
    SolicitudEdicionPerfil,
    SolicitudPerfil,
)
from app.modules.consumption.application import perfiles
from app.modules.consumption.application.perfiles import (
    DatosPerfil,
    PerfilDuplicado,
    PerfilInactivo,
    PerfilNoEncontrado,
    PeticionConsumo,
    ProductoNoAdmitido,
    UnidadDistinta,
    VersionDesactualizada,
)
from app.modules.consumption.application.ports import PerfilLeido
from app.modules.consumption.domain.perfil import (
    SIN_CAMBIO,
    CambiosPerfil,
    CoberturaMaxima,
    FaltaVersion,
    NombreLibreConProducto,
    dias_restantes,
    etag,
    hoy_en_chile,
)
from app.shared.puertos import Reloj

router = APIRouter(tags=["consumo"])

RUTA = "/personas-cuidadas/{persona_id}/consumo"
RUTA_PERFIL = RUTA + "/{perfil_id}"

NO_STORE = "no-store"

_PROBLEMA: dict[str, Any] = {"content": {"application/problem+json": {}}}
_401 = {"description": "Falta el access token, o es inválido o vencido", **_PROBLEMA}
_403 = {
    "description": (
        "Sin autorización vigente para consumo: /errores/sin-consentimiento o /errores/revision-vencida, con el"
        " miembro de extensión finalidad: consumo. Se evalúa antes de leer nada del consumo"
    ),
    **_PROBLEMA,
}
_404 = {
    "description": (
        "No miembro, rol que no alcanza para escribir (pagador u observador), persona de otro grupo o inexistente,"
        " o el perfil no es de esa persona"
    ),
    **_PROBLEMA,
}
_ERRORES_LECTURA: dict[int | str, dict[str, Any]] = {401: _401, 403: _403, 404: _404}
_422_CUERPO = {
    "description": (
        "Cuerpo inválido. errores[] nombra el campo y nunca repite el valor. Tipos propios: producto_o_nombre,"
        " producto_no_admitido, unidad_distinta, cobertura_maxima, nombre_libre_con_producto, null_no_admitido,"
        " cuerpo_vacio; value_error en nombre_libre si trae saltos de línea o caracteres de control."
        " unidades_por_envase fuera de 1 a 10.000 responde con los tipos de Pydantic"
    ),
    **_PROBLEMA,
}

def _esquema_412() -> dict[str, Any]:
    """El esquema del 412 con referencias a los componentes que ya registra PerfilConsumoVista."""
    esquema = ProblemaVersionPerfilVista.model_json_schema(
        ref_template="#/components/schemas/{model}", mode="serialization"
    )
    esquema.pop("$defs", None)
    return esquema


MENSAJES = {
    "producto_o_nombre": "indica producto_id o nombre_libre, solo uno",
    "producto_no_admitido": "ese producto no se puede seguir en MATU",
    "unidad_distinta": "la unidad no es la del producto",
    "cobertura_maxima": "con esa tasa, lo que queda alcanza para más de 3650 días",
    "nombre_libre_con_producto": "este insumo es de un producto: su nombre no se edita",
    "null_no_admitido": "no admite null: omite el campo si no cambia",
    # unidades_por_envase sí admite null en el PATCH: lo borra (decisión 121)
    "cuerpo_vacio": "indica al menos un campo",
}


# El único campo del PATCH que admite null, que lo borra (decisión 121)
_ADMITE_NULL = "unidades_por_envase"


def _error_422(campo: str, tipo: str) -> ErrorMATU:
    return ErrorMATU(
        422, detalle="Revisa los campos indicados", errores=[{"campo": campo, "mensaje": MENSAJES[tipo], "tipo": tipo}]
    )


def _peticion(request: Request, autorizado: Any) -> PeticionConsumo:
    return PeticionConsumo(
        grupo_id=autorizado.contexto.grupo_id,
        usuario_id=autorizado.contexto.usuario_id,
        persona_id=autorizado.persona_id,
        request_id=getattr(request.state, "request_id", None),
    )


def _vista(leido: PerfilLeido, reloj: Reloj) -> PerfilConsumoVista:
    p = leido.perfil
    producto = leido.producto
    autor = (
        None
        if p.actualizado_por is None or leido.actualizado_por_nombre is None
        else AutorPerfilVista(id=p.actualizado_por, nombre=leido.actualizado_por_nombre)
    )
    return PerfilConsumoVista(
        id=p.id,
        producto=None
        if producto is None
        else ProductoResumen(id=producto.id, nombre=producto.nombre, presentacion=producto.presentacion),
        nombre_libre=p.nombre_libre,
        unidad=p.unidad,
        tasa_unidades=p.tasa_unidades,
        tasa_dias=p.tasa_dias,
        stock_unidades=p.stock_unidades,
        stock_medido_en=p.stock_medido_en,
        dias_aviso=p.dias_aviso,
        unidades_por_envase=p.unidades_por_envase,
        fecha_quiebre_estimada=p.fecha_quiebre_estimada,
        dias_restantes=dias_restantes(p.fecha_quiebre_estimada, hoy_en_chile(reloj.ahora())),
        activo=p.activo,
        actualizado_por=autor,
        etag=etag(p.version),
    )


# --- Cursor --------------------------------------------------------------------------------------------


def _cursor(siguiente: tuple[date, uuid.UUID] | None) -> str | None:
    if siguiente is None:
        return None
    crudo = f"{siguiente[0].isoformat()}|{siguiente[1]}".encode()
    return base64.urlsafe_b64encode(crudo).decode().rstrip("=")


def _desde_cursor(cursor: str | None) -> tuple[date, uuid.UUID] | None:
    if cursor is None:
        return None
    try:
        crudo = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        fecha, ident = crudo.split("|")
        return date.fromisoformat(fecha), uuid.UUID(ident)
    except (ValueError, binascii.Error, UnicodeDecodeError):
        raise ErrorMATU(
            422,
            detalle="Revisa los campos indicados",
            errores=[{"campo": "cursor", "mensaje": "el cursor no es válido", "tipo": "cursor_invalido"}],
        ) from None


_FILTRO_ACTIVO = {"true": True, "false": False, "todos": None}


# --- Rutas ---------------------------------------------------------------------------------------------


@router.get(
    RUTA,
    response_model=ListaPerfiles,
    responses={**_ERRORES_LECTURA, 422: {"description": "cursor, limite o activo inválidos", **_PROBLEMA}},
    summary="Ver los insumos declarados de la persona",
)
def listar(
    request: Request,
    response: Response,
    autorizado: ParaLeer,
    repositorio: Repositorio,
    reloj: RelojDep,
    activo: Annotated[
        str,
        Query(
            description=(
                "`true` (por omisión) los que se siguen; `false` los desactivados; `todos` los dos, en una sola"
                " lista (decisión 72)"
            ),
            json_schema_extra={"enum": ["true", "false", "todos"]},
        ),
    ] = "true",
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ListaPerfiles:
    if activo not in _FILTRO_ACTIVO:
        raise ErrorMATU(
            422,
            detalle="Revisa los campos indicados",
            errores=[{"campo": "activo", "mensaje": "admite true, false o todos", "tipo": "enum"}],
        )
    pagina = perfiles.listar(
        _peticion(request, autorizado), _FILTRO_ACTIVO[activo], _desde_cursor(cursor), limite, repositorio
    )
    response.headers["Cache-Control"] = NO_STORE
    return ListaPerfiles(items=[_vista(i, reloj) for i in pagina.items], siguiente_cursor=_cursor(pagina.siguiente))


@router.post(
    RUTA,
    status_code=status.HTTP_201_CREATED,
    response_model=PerfilConsumoVista,
    responses={
        **_ERRORES_LECTURA,
        409: {"description": "/errores/perfil-duplicado: ya se sigue ese producto", **_PROBLEMA},
        422: _422_CUERPO,
    },
    summary="Anotar cuánto se usa de un insumo y cuánto queda",
)
def crear(
    request: Request,
    response: Response,
    autorizado: ParaEscribir,
    solicitud: SolicitudPerfil,
    repositorio: Repositorio,
    auditoria: Auditoria,
    reloj: RelojDep,
) -> PerfilConsumoVista:
    if (solicitud.producto_id is None) == (solicitud.nombre_libre is None):
        raise _error_422("nombre_libre", "producto_o_nombre")
    datos = DatosPerfil(
        producto_id=solicitud.producto_id,
        nombre_libre=solicitud.nombre_libre,
        unidad=solicitud.unidad,
        tasa_unidades=solicitud.tasa_unidades,
        tasa_dias=solicitud.tasa_dias,
        stock_unidades=solicitud.stock_unidades,
        dias_aviso=solicitud.dias_aviso,
        unidades_por_envase=solicitud.unidades_por_envase,
    )
    try:
        creado = perfiles.crear(_peticion(request, autorizado), datos, reloj, repositorio, auditoria)
    except ProductoNoAdmitido:
        raise _error_422("producto_id", "producto_no_admitido") from None
    except UnidadDistinta:
        raise _error_422("unidad", "unidad_distinta") from None
    except CoberturaMaxima:
        raise _error_422("stock_unidades", "cobertura_maxima") from None
    except PerfilDuplicado:
        raise ErrorMATU(
            409, tipo="perfil-duplicado", detalle="Ese producto ya está anotado para esta persona"
        ) from None
    vista = _vista(creado, reloj)
    response.headers["ETag"] = vista.etag
    response.headers["Cache-Control"] = NO_STORE
    response.headers["Location"] = f"/v1/personas-cuidadas/{autorizado.persona_id}/consumo/{vista.id}"
    return vista


def _guardado(response: Response, vista: PerfilConsumoVista) -> PerfilConsumoVista:
    response.headers["ETag"] = vista.etag
    response.headers["Cache-Control"] = NO_STORE
    return vista


@router.get(
    RUTA_PERFIL, response_model=PerfilConsumoVista, responses=_ERRORES_LECTURA, summary="Ver un insumo declarado"
)
def ver(
    request: Request,
    response: Response,
    autorizado: ParaLeer,
    perfil_id: PerfilIdRuta,
    repositorio: Repositorio,
    reloj: RelojDep,
) -> PerfilConsumoVista:
    try:
        leido = perfiles.ver(_peticion(request, autorizado), uuid_o_404(perfil_id), repositorio)
    except PerfilNoEncontrado:
        raise ErrorMATU(404) from None
    return _guardado(response, _vista(leido, reloj))


@router.patch(
    RUTA_PERFIL,
    response_model=PerfilConsumoVista,
    responses={
        **_ERRORES_LECTURA,
        409: {"description": "/errores/perfil-inactivo: un insumo que no se sigue no se edita", **_PROBLEMA},
        412: {
            "description": (
                "Otra persona cambió el perfil desde que se leyó. `actual` trae el perfil vigente, con su etag y"
                " quién lo guardó (actualizado_por)"
            ),
            "content": {"application/problem+json": {"schema": _esquema_412()}},
        },
        422: _422_CUERPO,
        428: {"description": "Falta If-Match, está vacío o es *", **_PROBLEMA},
    },
    summary="Corregir cuánto se usa o anotar cuánto queda",
)
def editar(
    request: Request,
    response: Response,
    autorizado: ParaEscribir,
    perfil_id: PerfilIdRuta,
    solicitud: SolicitudEdicionPerfil,
    repositorio: Repositorio,
    auditoria: Auditoria,
    reloj: RelojDep,
    if_match: Annotated[
        str | None,
        Header(
            alias="If-Match",
            description=(
                'ETag del perfil tal como se leyó, por ejemplo "v3". Obligatorio: vacío o * responde 428; otro'
                " valor que no coincide responde 412"
            ),
        ),
    ] = None,
) -> PerfilConsumoVista | JSONResponse:
    perfil = uuid_o_404(perfil_id)
    enviados = solicitud.model_fields_set
    if not enviados:
        raise _error_422("cuerpo", "cuerpo_vacio")
    for campo in sorted(enviados - {_ADMITE_NULL}):
        if getattr(solicitud, campo) is None:
            raise _error_422(campo, "null_no_admitido")
    cambios = CambiosPerfil(
        nombre_libre=solicitud.nombre_libre,
        tasa_unidades=solicitud.tasa_unidades,
        tasa_dias=solicitud.tasa_dias,
        stock_unidades=solicitud.stock_unidades,
        dias_aviso=solicitud.dias_aviso,
        unidades_por_envase=solicitud.unidades_por_envase if _ADMITE_NULL in enviados else SIN_CAMBIO,
    )
    try:
        resultado = perfiles.editar(
            _peticion(request, autorizado), perfil, cambios, if_match, reloj, repositorio, auditoria
        )
    except PerfilNoEncontrado:
        raise ErrorMATU(404) from None
    except NombreLibreConProducto:
        raise _error_422("nombre_libre", "nombre_libre_con_producto") from None
    except FaltaVersion:
        raise ErrorMATU(428, detalle="Vuelve a abrir el insumo y guarda de nuevo") from None
    except PerfilInactivo:
        raise ErrorMATU(409, tipo="perfil-inactivo", detalle="Este insumo ya no se sigue") from None
    except CoberturaMaxima:
        raise _error_422("stock_unidades", "cobertura_maxima") from None
    if isinstance(resultado, VersionDesactualizada):
        actual = _vista(resultado.actual, reloj)
        quien = actual.actualizado_por.nombre if actual.actualizado_por is not None else "Otra persona"
        return respuesta_problema(
            request,
            status.HTTP_412_PRECONDITION_FAILED,
            detalle=f"{quien} cambió este insumo mientras lo editabas. Revisa lo que guardó antes de guardar",
            headers={"ETag": actual.etag, "Cache-Control": NO_STORE},
            extension={"actual": actual.model_dump(mode="json")},
        )
    return _guardado(response, _vista(resultado, reloj))


@router.delete(
    RUTA_PERFIL,
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERRORES_LECTURA,
    summary="Eliminar un insumo",
    description=(
        "Borra el perfil en el acto, activo o desactivado (decisión 69). Sus reposiciones y alertas se borran"
        " con él. No se puede deshacer. Escriben admin y cuidador. Registra consumo.eliminar"
    ),
)
def eliminar(
    request: Request,
    autorizado: ParaEscribir,
    perfil_id: PerfilIdRuta,
    repositorio: Repositorio,
    auditoria: Auditoria,
) -> Response:
    try:
        perfiles.eliminar(_peticion(request, autorizado), uuid_o_404(perfil_id), repositorio, auditoria)
    except PerfilNoEncontrado:
        raise ErrorMATU(404) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": NO_STORE})


@router.post(
    RUTA_PERFIL + "/desactivar",
    response_model=PerfilConsumoVista,
    responses=_ERRORES_LECTURA,
    summary="Dejar de seguir un insumo",
    description=(
        "activo = false, sin borrar (decisión 46). Las alertas abiertas pasan a descartada. Idempotente, sin"
        " If-Match. Registra consumo.desactivar"
    ),
)
def desactivar(
    request: Request,
    response: Response,
    autorizado: ParaEscribir,
    perfil_id: PerfilIdRuta,
    repositorio: Repositorio,
    auditoria: Auditoria,
    reloj: RelojDep,
) -> PerfilConsumoVista:
    try:
        leido = perfiles.desactivar(
            _peticion(request, autorizado), uuid_o_404(perfil_id), reloj, repositorio, auditoria
        )
    except PerfilNoEncontrado:
        raise ErrorMATU(404) from None
    return _guardado(response, _vista(leido, reloj))


@router.post(
    RUTA_PERFIL + "/activar",
    response_model=PerfilConsumoVista,
    responses={
        **_ERRORES_LECTURA,
        409: {"description": "/errores/perfil-duplicado: ya se sigue ese producto en otro perfil", **_PROBLEMA},
    },
    summary="Volver a seguir un insumo",
    description=(
        "activo = true (decisión 68). Idempotente, sin cuerpo y sin If-Match, igual que desactivar. Conserva el"
        " stock y la fecha estimada que tenía. Registra consumo.activar"
    ),
)
def activar(
    request: Request,
    response: Response,
    autorizado: ParaEscribir,
    perfil_id: PerfilIdRuta,
    repositorio: Repositorio,
    auditoria: Auditoria,
    reloj: RelojDep,
) -> PerfilConsumoVista:
    try:
        leido = perfiles.activar(_peticion(request, autorizado), uuid_o_404(perfil_id), repositorio, auditoria)
    except PerfilNoEncontrado:
        raise ErrorMATU(404) from None
    except PerfilDuplicado:
        raise ErrorMATU(
            409, tipo="perfil-duplicado", detalle="Ese producto ya está anotado para esta persona"
        ) from None
    return _guardado(response, _vista(leido, reloj))

