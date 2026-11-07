"""Ruta de la lista de insumos (MATU-60, RF-15, ADR-031). Contrato: docs/api/openapi.json.

    GET /v1/personas-cuidadas/{persona_id}/consumo/lista    los cuatro roles. 200

app.main registra este router antes que el de perfiles: la ruta fija ``lista`` va antes que
``{perfil_id}`` (decisión 54). Rol, persona y autorización para ``consumo`` se verifican en
``consumo_para_leer``, en el orden 401, 404 y 403, igual que las demás lecturas del consumo. Toda respuesta,
también 401, 403 y 404, lleva Cache-Control: no-store (middleware de /v1/personas-cuidadas/ en app.main).

Es una lectura pura: sin auditoría (decisión 52), sin eventos y sin crear ni cerrar alertas. No existe
POST …/exportar ni una ruta pública para la lista (decisión 122). El nombre de un insumo nunca llega a los
logs: la línea de la petición lleva la plantilla de la ruta, no la respuesta.
"""

from fastapi import APIRouter, Request, Response

from app.modules.consumption.api.dependencias import ParaLeer, RelojDep, RepositorioDeAlertas
from app.modules.consumption.api.esquemas import LineaListaInsumos, ListaInsumos
from app.modules.consumption.api.router import _ERRORES_LECTURA, _PROBLEMA, NO_STORE, RUTA, _403, _peticion
from app.modules.consumption.application import lista
from app.modules.consumption.domain.lista import LineaLista

router = APIRouter(tags=["consumo"])

_404_LISTA = {
    "description": (
        "Falta X-Grupo-Id o no es un UUID, no miembro activo del grupo, o la persona es de otro grupo, no existe o"
        " su id no es un UUID. Leen los cuatro roles, así que el rol nunca es la causa"
    ),
    **_PROBLEMA,
}


def _linea(linea: LineaLista) -> LineaListaInsumos:
    return LineaListaInsumos(
        perfil_id=linea.perfil_id,
        nombre=linea.nombre,
        unidad=linea.unidad,
        dias_restantes=linea.dias_restantes,
        unidades_sugeridas=linea.unidades_sugeridas,
        unidades_por_envase=linea.unidades_por_envase,
        envases_sugeridos=linea.envases_sugeridos,
    )


@router.get(
    RUTA + "/lista",
    response_model=ListaInsumos,
    responses={401: _ERRORES_LECTURA[401], 403: _403, 404: _404_LISTA},
    summary="Lista de insumos",
    description=(
        "Lo que se acaba pronto, con una cantidad sugerida para 30 días (MATU-60, RF-15, ADR-031). Entra cada"
        " insumo de «Se acaban pronto» con avisando = true, calculado al momento: activo, en su ventana y sin una"
        " alerta resuelta ni descartada para su fecha estimada actual (decisión 117). La cantidad es lo que falta"
        " para 30 días, descontando lo que MATU estima que queda hoy, al menos 1, y en envases enteros si el"
        " perfil tiene unidades_por_envase (decisiones 119 a 121). Orden: fecha estimada, nombre sin tildes,"
        " nombre y perfil_id. Sin el nombre de la persona, la ficha ni acciones. Leen los cuatro roles. No se"
        " audita y no crea ni cierra alertas. No hay exportación ni enlace (decisión 122)"
    ),
)
def ver_lista(
    request: Request, response: Response, autorizado: ParaLeer, repositorio: RepositorioDeAlertas, reloj: RelojDep
) -> ListaInsumos:
    resultado = lista.lista_de_insumos(_peticion(request, autorizado), reloj, repositorio)
    response.headers["Cache-Control"] = NO_STORE
    return ListaInsumos(fecha=resultado.fecha, items=[_linea(linea) for linea in resultado.lineas])
