"""Rutas de «Se acaban pronto» y de las alertas (MATU-37, RF-12). Contrato: docs/api/openapi.json.

    GET  /v1/personas-cuidadas/{persona_id}/consumo/por-acabarse                     los cuatro roles. 200
    GET  /v1/personas-cuidadas/{persona_id}/consumo/alertas                          los cuatro roles. 200
    POST /v1/personas-cuidadas/{persona_id}/consumo/alertas/{alerta_id}/descartar    admin y cuidador. 200
    POST /v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}/resolver             admin y cuidador. 200

app.main registra este router antes que el de perfiles: las rutas fijas ``por-acabarse`` y ``alertas``
van antes que ``{perfil_id}`` (decisión 54). Rol, persona y autorización se verifican en las
dependencias, antes del cuerpo. Nada del nombre del insumo ni de una cantidad llega a los logs ni a la
auditoría.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Body, Header, Query, Request, Response, status
from fastapi.responses import JSONResponse

from app.core.errores import ErrorMATU, respuesta_problema
from app.modules.consumption.api.dependencias import (
    AlertaIdRuta,
    Auditoria,
    ParaEscribir,
    ParaLeer,
    PerfilIdRuta,
    RelojDep,
    Repositorio,
    RepositorioDeAlertas,
    uuid_o_404,
)
from app.modules.consumption.api.esquemas import (
    AlertaVista,
    InsumoPorAcabarseVista,
    ListaAlertas,
    ListaPorAcabarse,
    SolicitudResolver,
)
from app.modules.consumption.api.router import (
    _ERRORES_LECTURA,
    _PROBLEMA,
    NO_STORE,
    RUTA,
    _403,
    _cursor,
    _desde_cursor,
    _esquema_412,
    _peticion,
    _vista,
)
from app.modules.consumption.application import alertas
from app.modules.consumption.application.alertas import AlertaNoEncontrada, InsumoAvisado
from app.modules.consumption.application.perfiles import PerfilInactivo, PerfilNoEncontrado, VersionDesactualizada
from app.modules.consumption.application.ports import AlertaLeida
from app.modules.consumption.domain.alerta import (
    ABIERTAS,
    AlertaCerrada,
    EstadoAlerta,
    SinUnidadesPorEnvase,
    StockMaximo,
)
from app.modules.consumption.domain.perfil import CoberturaMaxima, FaltaVersion
from app.shared.puertos import Reloj

router = APIRouter(tags=["alertas"])

_404_ESCRIBIR = {
    "description": (
        "No miembro, rol que no alcanza (pagador u observador), persona de otro grupo o inexistente, o la alerta o"
        " el perfil no es de esa persona"
    ),
    **_PROBLEMA,
}
_409_CERRADA = {
    "description": "/errores/alerta-cerrada: la alerta ya está resuelta o descartada; trae el `estado` actual",
    **_PROBLEMA,
}


def _alerta(a: AlertaLeida) -> AlertaVista:
    return AlertaVista(
        id=a.id,
        perfil_id=a.perfil_id,
        fecha_prevista=a.fecha_prevista,
        estado=a.estado,
        creada_en=a.creada_en,
        notificada_en=a.notificada_en,
        cerrada_en=a.cerrada_en,
    )


def _insumo(i: InsumoAvisado, reloj: Reloj) -> InsumoPorAcabarseVista:
    return InsumoPorAcabarseVista(**_vista(i.leido, reloj).model_dump(), avisando=i.avisando, alerta_id=i.alerta_id)


MENSAJES_COMPRA = {
    "stock_maximo": "con esa cantidad, lo que queda pasa de 100.000",
    "cobertura_maxima": "con esa cantidad, lo que queda alcanza para más de 3650 días",
    "envases_o_cantidad": "indica envases o cantidad, solo uno",
    "sin_unidades_por_envase": "este insumo no tiene anotado cuánto trae cada envase: indica la cantidad",
}


def error_compra(campo: str, tipo: str) -> ErrorMATU:
    """Un 422 de una compra que nombra el campo y el tipo, nunca el valor (decisiones 137 y 144)."""
    return ErrorMATU(
        422,
        detalle="Revisa los campos indicados",
        errores=[{"campo": campo, "mensaje": MENSAJES_COMPRA[tipo], "tipo": tipo}],
    )


def _alerta_cerrada(error: AlertaCerrada) -> ErrorMATU:
    return ErrorMATU(
        409,
        tipo="alerta-cerrada",
        detalle="Esta alerta ya se cerró",
        extension={"estado": error.estado.value},
    )


@router.get(
    RUTA + "/por-acabarse",
    response_model=ListaPorAcabarse,
    responses=_ERRORES_LECTURA,
    summary="Qué se acaba pronto",
    description=(
        "Los perfiles activos con fecha_quiebre_estimada - hoy <= dias_aviso (hoy en America/Santiago con el"
        " Reloj), incluidos los ya pasados. Por fecha estimada y después por id, sin paginar. Sale de"
        " perfil_consumo, no de alerta_quiebre (decisión 53). Cada ítem trae avisando y alerta_id (decisión 74)"
    ),
)
def por_acabarse(
    request: Request, response: Response, autorizado: ParaLeer, repositorio: RepositorioDeAlertas, reloj: RelojDep
) -> ListaPorAcabarse:
    items = alertas.por_acabarse(_peticion(request, autorizado), reloj, repositorio)
    response.headers["Cache-Control"] = NO_STORE
    return ListaPorAcabarse(items=[_insumo(i, reloj) for i in items])


_ESTADOS = {e.value: e for e in EstadoAlerta}


@router.get(
    RUTA + "/alertas",
    response_model=ListaAlertas,
    responses={**_ERRORES_LECTURA, 422: {"description": "estado, cursor o limite inválidos", **_PROBLEMA}},
    summary="Ver las alertas de la persona",
    description=(
        "Por fecha_prevista y después por id. Sin estado, las abiertas (pendiente y notificada). Las crea el trabajo"
        " diario, una por perfil y fecha prevista, solo con la autorización para consumo vigente"
    ),
)
def listar_alertas(
    request: Request,
    response: Response,
    autorizado: ParaLeer,
    repositorio: RepositorioDeAlertas,
    estado: Annotated[
        list[str] | None,
        Query(
            description="Uno o más estados (?estado=pendiente&estado=notificada). Sin el parámetro, las abiertas",
            json_schema_extra={"items": {"enum": [e.value for e in EstadoAlerta]}},
        ),
    ] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ListaAlertas:
    if estado is None:
        estados = frozenset(ABIERTAS)
    elif not estado or len(estado) > len(_ESTADOS) or any(e not in _ESTADOS for e in estado):
        raise ErrorMATU(
            422,
            detalle="Revisa los campos indicados",
            errores=[
                {"campo": "estado", "mensaje": "admite pendiente, notificada, resuelta o descartada", "tipo": "enum"}
            ],
        )
    else:
        estados = frozenset(_ESTADOS[e] for e in estado)
    pagina = alertas.listar(_peticion(request, autorizado), estados, _desde_cursor(cursor), limite, repositorio)
    response.headers["Cache-Control"] = NO_STORE
    return ListaAlertas(items=[_alerta(a) for a in pagina.items], siguiente_cursor=_cursor(pagina.siguiente))


@router.post(
    RUTA + "/alertas/{alerta_id}/descartar",
    response_model=AlertaVista,
    responses={401: _ERRORES_LECTURA[401], 403: _403, 404: _404_ESCRIBIR, 409: _409_CERRADA},
    summary="No avisar esta vez",
    description=(
        "Pasa la alerta a descartada y fija cerrada_en con el Reloj. Nunca la borra. Sin cuerpo. Solo admin y"
        " cuidador (decisión 58). Desde resuelta o descartada, 409 alerta-cerrada. Registra alerta.descartar"
    ),
)
def descartar(
    request: Request,
    response: Response,
    autorizado: ParaEscribir,
    alerta_id: AlertaIdRuta,
    repositorio: RepositorioDeAlertas,
    auditoria: Auditoria,
    reloj: RelojDep,
) -> AlertaVista:
    try:
        cerrada = alertas.descartar(
            _peticion(request, autorizado), uuid_o_404(alerta_id), reloj, repositorio, auditoria
        )
    except AlertaNoEncontrada:
        raise ErrorMATU(404) from None
    except AlertaCerrada as error:
        raise _alerta_cerrada(error) from None
    response.headers["Cache-Control"] = NO_STORE
    return _alerta(cerrada)


_422_RESOLVER: dict[str, Any] = {
    "description": (
        "envases fuera de 1..99 o cantidad fuera de 1..10000 (decisiones 144 y 147); envases_o_cantidad (los dos"
        " a la vez, en cantidad); sin_unidades_por_envase (envases en un perfil sin unidades_por_envase, en"
        " envases); stock_maximo: lo que queda más lo comprado pasa de 100.000; o cobertura_maxima: con lo comprado"
        " alcanzaría para más de 3650 días, en el campo que vino. Nunca repite el valor"
    ),
    **_PROBLEMA,
}


@router.post(
    RUTA + "/{perfil_id}/resolver",
    response_model=InsumoPorAcabarseVista,
    responses={
        401: _ERRORES_LECTURA[401],
        403: _403,
        404: _404_ESCRIBIR,
        409: {
            "description": (
                "/errores/alerta-cerrada (la alerta de la fecha estimada actual ya está cerrada, con su `estado`) o"
                " /errores/perfil-inactivo"
            ),
            **_PROBLEMA,
        },
        412: {
            "description": (
                "El If-Match no es la versión vigente del perfil (otra persona o una pestaña anterior ya guardó):"
                " no se suma ni se cierra nada. `actual` trae el perfil vigente, con su etag y quién lo guardó"
            ),
            "content": {"application/problem+json": {"schema": _esquema_412()}},
        },
        422: _422_RESOLVER,
        428: {"description": "Falta If-Match, está vacío o es *", **_PROBLEMA},
    },
    summary="Ya lo resolví",
    description=(
        "Cierra el aviso del insumo para su fecha estimada actual, aunque el trabajo diario aún no haya creado la"
        " alerta (decisiones 76, 79 y 147). Sin envases ni cantidad: la alerta pasa a descartada (o se crea ya"
        " descartada) y el perfil no cambia; registra alerta.descartar. Con envases (× unidades_por_envase) o"
        " cantidad, como en «Compré»: el stock pasa a lo que MATU estima que queda hoy"
        " (nunca negativo) más la cantidad, medido hoy, con la fecha recalculada y un ETag nuevo; se anota una"
        " reposición declarada y la alerta queda resuelta; registra reposicion.declarar y alerta.resolver, sin la"
        " cantidad. Devuelve el insumo recalculado. Solo admin y cuidador. Nunca crea un pedido"
    ),
)
def resolver(
    request: Request,
    response: Response,
    autorizado: ParaEscribir,
    perfil_id: PerfilIdRuta,
    perfiles: Repositorio,
    repositorio: RepositorioDeAlertas,
    auditoria: Auditoria,
    reloj: RelojDep,
    solicitud: Annotated[SolicitudResolver | None, Body()] = None,
    if_match: Annotated[
        str | None,
        Header(
            alias="If-Match",
            description=(
                'ETag del perfil tal como se leyó (el campo etag del ítem), por ejemplo "v3". Obligatorio: vacío o *'
                " responde 428; otro valor que no coincide responde 412 sin sumar ni cerrar nada (decisión 80)"
            ),
        ),
    ] = None,
) -> InsumoPorAcabarseVista | JSONResponse:
    envases = None if solicitud is None else solicitud.envases
    cantidad = None if solicitud is None else solicitud.cantidad
    # Decisión 147: los dos a la vez es un 422 del cuerpo, antes del 404 del perfil
    if envases is not None and cantidad is not None:
        raise error_compra("cantidad", "envases_o_cantidad")
    campo = "envases" if envases is not None else "cantidad"
    try:
        resultado = alertas.resolver(
            _peticion(request, autorizado),
            uuid_o_404(perfil_id),
            cantidad,
            if_match,
            reloj,
            perfiles,
            repositorio,
            auditoria,
            envases=envases,
        )
    except PerfilNoEncontrado:
        raise ErrorMATU(404) from None
    except FaltaVersion:
        raise ErrorMATU(428, detalle="Vuelve a abrir el insumo e inténtalo de nuevo") from None
    except SinUnidadesPorEnvase:
        raise error_compra("envases", "sin_unidades_por_envase") from None
    except StockMaximo:
        raise error_compra(campo, "stock_maximo") from None
    except CoberturaMaxima:
        raise error_compra(campo, "cobertura_maxima") from None
    except PerfilInactivo:
        raise ErrorMATU(409, tipo="perfil-inactivo", detalle="Este insumo no se está siguiendo") from None
    except AlertaCerrada as error:
        raise _alerta_cerrada(error) from None
    if isinstance(resultado, VersionDesactualizada):
        actual = _vista(resultado.actual, reloj)
        quien = actual.actualizado_por.nombre if actual.actualizado_por is not None else "Otra persona"
        return respuesta_problema(
            request,
            status.HTTP_412_PRECONDITION_FAILED,
            detalle=f"{quien} cambió este insumo hace un momento. Revisa cuánto queda antes de anotar de nuevo",
            headers={"ETag": actual.etag, "Cache-Control": NO_STORE},
            extension={"actual": actual.model_dump(mode="json")},
        )
    vista = _insumo(resultado, reloj)
    response.headers["ETag"] = vista.etag
    response.headers["Cache-Control"] = NO_STORE
    return vista
