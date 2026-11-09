"""Rutas de «Compré» y «Me quedan N» (MATU-51, RF-10 y RF-11, decisiones 136 a 143). Contrato: docs/api/openapi.json.

    POST /v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}/reponer    admin y cuidador. 200, If-Match
    POST /v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}/recontar   admin y cuidador. 200, If-Match

Rol, persona y autorización (con FOR SHARE, ParaEscribir) se verifican en las dependencias, antes
del cuerpo. La cantidad viaja solo en el cuerpo, que no admite fecha. Nada del nombre del insumo ni de una
cantidad llega a los logs, la auditoría ni los errores. No hay ruta de historial de compras.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Header, Request, Response, status
from fastapi.responses import JSONResponse

from app.core.errores import ErrorMATU, respuesta_problema
from app.modules.consumption.api.dependencias import (
    Auditoria,
    ParaEscribir,
    PerfilIdRuta,
    RelojDep,
    Repositorio,
    RepositorioDeAlertas,
    uuid_o_404,
)
from app.modules.consumption.api.esquemas import InsumoPorAcabarseVista, SolicitudRecuento, SolicitudReposicion
from app.modules.consumption.api.router import (
    _ERRORES_LECTURA,
    _PROBLEMA,
    NO_STORE,
    RUTA_PERFIL,
    _403,
    _error_422,
    _esquema_412,
    _peticion,
    _vista,
)
from app.modules.consumption.api.router_alertas import _404_ESCRIBIR, _insumo, error_compra
from app.modules.consumption.application import reposiciones
from app.modules.consumption.application.alertas import InsumoAvisado
from app.modules.consumption.application.perfiles import PerfilInactivo, PerfilNoEncontrado, VersionDesactualizada
from app.modules.consumption.domain.alerta import EnvasesOCantidad, SinUnidadesPorEnvase, StockMaximo
from app.modules.consumption.domain.perfil import CoberturaMaxima, FaltaVersion
from app.shared.puertos import Reloj

router = APIRouter(tags=["consumo"])

_IF_MATCH = Header(
    alias="If-Match",
    description=(
        'ETag del perfil tal como se leyó (el campo etag), por ejemplo "v3". Obligatorio: vacío o * responde 428;'
        " otro valor que no coincide responde 412 sin cambiar nada (decisión 141)"
    ),
)


def _respuestas(descripcion_422: str) -> dict[int | str, dict[str, Any]]:
    return {
        401: _ERRORES_LECTURA[401],
        403: _403,
        404: _404_ESCRIBIR,
        409: {"description": "/errores/perfil-inactivo: un insumo que no se sigue no anota compras ni recuentos",
              **_PROBLEMA},
        412: {
            "description": (
                "El If-Match no es la versión vigente del perfil: no se suma, no se anota la compra y no se cierra"
                " nada. `actual` trae el perfil vigente, con su etag y quién lo guardó"
            ),
            "content": {"application/problem+json": {"schema": _esquema_412()}},
        },
        422: {"description": descripcion_422, **_PROBLEMA},
        428: {"description": "Falta If-Match, está vacío o es *", **_PROBLEMA},
    }


def _responder(
    request: Request, response: Response, resultado: InsumoAvisado | VersionDesactualizada, reloj: Reloj
) -> InsumoPorAcabarseVista | JSONResponse:
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


@router.post(
    RUTA_PERFIL + "/reponer",
    response_model=InsumoPorAcabarseVista,
    responses=_respuestas(
        "Cuerpo inválido, sin repetir el valor: envases fuera de 1..99 o cantidad fuera de 1..10000 (tipos de"
        " Pydantic); envases_o_cantidad (los dos o ninguno, en cantidad); sin_unidades_por_envase (envases en un"
        " perfil sin unidades_por_envase, en envases); stock_maximo (lo que queda más lo comprado pasa de 100.000)"
        " o cobertura_maxima (más de 3650 días), en el campo que vino"
    ),
    summary="Compré",
    description=(
        "Suma lo comprado a lo que MATU estima que queda hoy (nunca negativo), en cualquier insumo activo, tenga"
        " alerta o no (decisiones 137 y 138). Exactamente uno de envases (× unidades_por_envase) o cantidad. El"
        " stock queda medido hoy, con la fecha recalculada y un ETag nuevo. Anota una compra (`reposicion`) con la"
        " fecha de hoy según el Reloj; la API no acepta fecha. La alerta abierta de la fecha anterior queda"
        " resuelta y las demás abiertas que dejan de corresponder, descartadas; nunca crea una alerta y no"
        " responde 409 si la de la fecha ya estaba cerrada. Registra reposicion.declarar (y alerta.resolver o"
        " alerta.descartar), sin la cantidad. Solo admin y cuidador. Nunca crea un pedido"
    ),
)
def reponer(
    request: Request,
    response: Response,
    autorizado: ParaEscribir,
    perfil_id: PerfilIdRuta,
    solicitud: SolicitudReposicion,
    perfiles: Repositorio,
    alertas: RepositorioDeAlertas,
    auditoria: Auditoria,
    reloj: RelojDep,
    if_match: Annotated[str | None, _IF_MATCH] = None,
) -> InsumoPorAcabarseVista | JSONResponse:
    # Un 422 del cuerpo va antes del 404 del perfil (decisión 141)
    if (solicitud.envases is None) == (solicitud.cantidad is None):
        raise error_compra("cantidad", "envases_o_cantidad")
    perfil = uuid_o_404(perfil_id)
    campo = "envases" if solicitud.envases is not None else "cantidad"
    try:
        resultado = reposiciones.comprar(
            _peticion(request, autorizado),
            perfil,
            solicitud.envases,
            solicitud.cantidad,
            if_match,
            reloj,
            perfiles,
            alertas,
            auditoria,
        )
    except PerfilNoEncontrado:
        raise ErrorMATU(404) from None
    except FaltaVersion:
        raise ErrorMATU(428, detalle="Vuelve a abrir el insumo e inténtalo de nuevo") from None
    except PerfilInactivo:
        raise ErrorMATU(409, tipo="perfil-inactivo", detalle="Este insumo no se está siguiendo") from None
    except EnvasesOCantidad:  # pragma: no cover - el router ya lo revisó
        raise error_compra("cantidad", "envases_o_cantidad") from None
    except SinUnidadesPorEnvase:
        raise error_compra("envases", "sin_unidades_por_envase") from None
    except StockMaximo:
        raise error_compra(campo, "stock_maximo") from None
    except CoberturaMaxima:
        raise error_compra(campo, "cobertura_maxima") from None
    return _responder(request, response, resultado, reloj)


@router.post(
    RUTA_PERFIL + "/recontar",
    response_model=InsumoPorAcabarseVista,
    responses=_respuestas(
        "Cuerpo inválido, sin repetir el valor: stock_unidades falta o está fuera de 0..100000 (tipos de"
        " Pydantic), o cobertura_maxima en stock_unidades (más de 3650 días)"
    ),
    summary="Me quedan",
    description=(
        "Reemplaza lo que queda por lo que se contó hoy, como un PATCH con solo stock_unidades (decisión 139):"
        " medido hoy, con la fecha recalculada y un ETag nuevo. No anota una compra. Las alertas abiertas que"
        " con la fecha nueva dejan de corresponder quedan descartadas; no crea alertas. Registra consumo.editar"
        " (y alerta.descartar), sin el stock. Solo admin y cuidador"
    ),
)
def recontar(
    request: Request,
    response: Response,
    autorizado: ParaEscribir,
    perfil_id: PerfilIdRuta,
    solicitud: SolicitudRecuento,
    perfiles: Repositorio,
    alertas: RepositorioDeAlertas,
    auditoria: Auditoria,
    reloj: RelojDep,
    if_match: Annotated[str | None, _IF_MATCH] = None,
) -> InsumoPorAcabarseVista | JSONResponse:
    perfil = uuid_o_404(perfil_id)
    try:
        resultado = reposiciones.anotar_lo_que_queda(
            _peticion(request, autorizado),
            perfil,
            solicitud.stock_unidades,
            if_match,
            reloj,
            perfiles,
            alertas,
            auditoria,
        )
    except PerfilNoEncontrado:
        raise ErrorMATU(404) from None
    except FaltaVersion:
        raise ErrorMATU(428, detalle="Vuelve a abrir el insumo e inténtalo de nuevo") from None
    except PerfilInactivo:
        raise ErrorMATU(409, tipo="perfil-inactivo", detalle="Este insumo no se está siguiendo") from None
    except CoberturaMaxima:
        raise _error_422("stock_unidades", "cobertura_maxima") from None
    return _responder(request, response, resultado, reloj)
