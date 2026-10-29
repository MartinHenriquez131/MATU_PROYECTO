"""Rutas de los accesos de relevo de la familia (MATU-18, RF-05). Contrato: docs/api/propuestos/relevo.openapi.yaml.

    POST /v1/personas-cuidadas/{persona_id}/plan/accesos-relevo   admin y cuidador. 201 con el enlace y el PIN
    GET  /v1/personas-cuidadas/{persona_id}/plan/accesos-relevo   admin, cuidador y pagador con puede_ver_plan
    DELETE /v1/accesos-relevo/{acceso_id}                          admin y cuidador. 204 sin cuerpo (MATU-20)

Orden del POST: token (401), membresía y rol (404), persona (404), consentimiento y revisión anual
(403), PEPPER_PIN (503) y recién después el cuerpo (422). El GET no exige consentimiento (decisión 18).

El token y el PIN salen solo en el cuerpo del 201: nunca en una cabecera, un log ni un error. La línea
de log de la petición lleva la plantilla de la ruta. Las dos respuestas llevan Cache-Control: no-store.
"""

import base64
import binascii
import logging
import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.core.config import obtener_configuracion
from app.core.errores import ErrorMATU
from app.modules.care_plan.api.dependencias import (
    AccesoARevocar,
    FichaAutorizada,
    acceso_para_compartir,
    acceso_para_revocar,
    huellas_para_compartir,
    obtener_generador_credenciales,
    obtener_repositorio_accesos,
    obtener_repositorio_ficha,
    persona_para_listar,
)
from app.modules.care_plan.api.esquemas_relevo import (
    AccesoCreadoVista,
    AccesoResumenVista,
    AutorAccesoVista,
    ListaAccesosVista,
    SolicitudAccesoVista,
)
from app.modules.care_plan.application.ficha import PeticionFicha, PlanNoDisponible
from app.modules.care_plan.application.ports import (
    GeneradorCredencialesRelevo,
    HuellasRelevo,
    Posicion,
    RepositorioAccesos,
    RepositorioFicha,
)
from app.modules.care_plan.application.relevo import (
    AccesoNoEncontrado,
    PeticionRevocar,
    SolicitudCompartir,
    compartir,
    listar,
    revocar,
)
from app.modules.care_plan.domain.relevo import (
    EstadoAcceso,
    MotivoAcceso,
    VidaAcceso,
    VigenciaInvalida,
    estado_acceso,
    normalizar_celular,
    puede_ver_telefono,
)
from app.modules.iam.api.dependencias import obtener_reloj
from app.shared.puertos import Reloj

log = logging.getLogger("matu.care_plan.relevo")

router = APIRouter(tags=["accesos de relevo"])

RUTA_ACCESOS = "/personas-cuidadas/{persona_id}/plan/accesos-relevo"
RUTA_ACCESO = "/accesos-relevo/{acceso_id}"
NO_STORE = "no-store"

_PROBLEMA: dict[str, Any] = {"content": {"application/problem+json": {}}}
_ERRORES_LISTA: dict[int | str, dict[str, Any]] = {
    401: {"description": "Falta el access token, o es inválido o vencido", **_PROBLEMA},
    404: {"description": "No miembro, rol que no alcanza, persona de otro grupo o inexistente", **_PROBLEMA},
    422: {"description": "cursor inválido o limite fuera de 1 a 100", **_PROBLEMA},
}
_ERRORES_REVOCAR: dict[int | str, dict[str, Any]] = {
    401: _ERRORES_LISTA[401],
    404: {"description": "No miembro, rol que no alcanza, acceso de otro grupo, inexistente o id no UUID", **_PROBLEMA},
}
_ERRORES_CREAR: dict[int | str, dict[str, Any]] = {
    **_ERRORES_LISTA,
    403: {"description": "Sin consentimiento vigente para plan_cuidado, o revisión anual vencida", **_PROBLEMA},
    422: {"description": "Cuerpo inválido. errores[] nombra el campo, nunca el valor", **_PROBLEMA},
    500: {"description": "Error inesperado", **_PROBLEMA},
    503: {"description": "Falta PEPPER_PIN: compartir falla cerrado", **_PROBLEMA},
}


def _peticion(request: Request, ficha: FichaAutorizada) -> PeticionFicha:
    return PeticionFicha(
        grupo_id=ficha.contexto.grupo_id,
        usuario_id=ficha.contexto.usuario_id,
        persona_cuidada_id=ficha.persona_id,
        request_id=getattr(request.state, "request_id", None),
    )


def _error_422(campo: str, mensaje: str, tipo: str) -> ErrorMATU:
    errores = [{"campo": campo, "mensaje": mensaje, "tipo": tipo}]
    return ErrorMATU(422, detalle="Revisa los campos indicados", errores=errores)


# --- Cursor opaco: base64url de "<creado_en ISO>|<id>" ------------------------------------------------


def codificar_cursor(posicion: Posicion) -> str:
    crudo = f"{posicion.creado_en.isoformat()}|{posicion.id}".encode("ascii")
    return base64.urlsafe_b64encode(crudo).rstrip(b"=").decode("ascii")


def decodificar_cursor(cursor: str) -> Posicion:
    try:
        crudo = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode("ascii")
        instante, identificador = crudo.split("|")
        creado_en = datetime.fromisoformat(instante)
        if creado_en.tzinfo is None:
            raise ValueError
        return Posicion(creado_en=creado_en, id=uuid.UUID(identificador))
    except (binascii.Error, UnicodeDecodeError, ValueError):
        raise _error_422("cursor", "El cursor no es válido", "cursor_invalido") from None


@router.post(
    RUTA_ACCESOS,
    response_model=AccesoCreadoVista,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORES_CREAR,
)
def crear_acceso(
    request: Request,
    response: Response,
    autorizado: Annotated[FichaAutorizada, Depends(acceso_para_compartir)],
    huellas: Annotated[HuellasRelevo, Depends(huellas_para_compartir)],
    generador: Annotated[GeneradorCredencialesRelevo, Depends(obtener_generador_credenciales)],
    fichas: Annotated[RepositorioFicha, Depends(obtener_repositorio_ficha)],
    accesos: Annotated[RepositorioAccesos, Depends(obtener_repositorio_accesos)],
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
    solicitud: SolicitudAccesoVista,
) -> AccesoCreadoVista:
    telefono = normalizar_celular(solicitud.telefono_relevo)
    if telefono is None:  # el patrón ya lo valida; esto es defensa en profundidad
        raise _error_422("telefono_relevo", "No es un celular chileno", "celular_invalido")
    try:
        entregado = compartir(
            _peticion(request, autorizado),
            SolicitudCompartir(
                nombre_relevo=solicitud.nombre_relevo,
                telefono_relevo=telefono,
                campos=tuple(solicitud.campos),
                motivo=solicitud.motivo,
                expira_en=solicitud.expira_en,
            ),
            fichas,
            accesos,
            generador,
            huellas,
            reloj,
        )
    except VigenciaInvalida as error:
        raise _error_422("expira_en", error.mensaje, error.tipo) from None
    except PlanNoDisponible:
        log.error("no se pudo crear el acceso de relevo: falta el plan, la persona o quien comparte")
        raise ErrorMATU(500, detalle="No pudimos compartir la ficha. Cita el request_id si lo reportas") from None
    response.headers["Cache-Control"] = NO_STORE
    return AccesoCreadoVista(
        id=entregado.id,
        url=f"{obtener_configuracion().origen_web}/r#{entregado.token}",
        pin=entregado.pin,
        campos=list(entregado.campos),
        expira_en=entregado.expira_en,
        nombre_relevo=entregado.nombre_relevo,
        nombre_pila_persona=entregado.nombre_pila_persona,
    )


@router.get(
    RUTA_ACCESOS,
    response_model=ListaAccesosVista,
    response_model_exclude_unset=True,
    responses=_ERRORES_LISTA,
)
def listar_accesos(
    request: Request,
    response: Response,
    autorizado: Annotated[FichaAutorizada, Depends(persona_para_listar)],
    fichas: Annotated[RepositorioFicha, Depends(obtener_repositorio_ficha)],
    accesos: Annotated[RepositorioAccesos, Depends(obtener_repositorio_accesos)],
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
    estado: EstadoAcceso | None = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ListaAccesosVista:
    despues_de = None if cursor is None else decodificar_cursor(cursor)
    pagina = listar(
        _peticion(request, autorizado),
        fichas,
        accesos,
        reloj,
        None if estado is None else estado.value,
        despues_de,
        limite,
    )
    ahora = reloj.ahora()
    con_telefono = puede_ver_telefono(autorizado.contexto.rol)
    items = []
    for a in pagina.accesos:
        datos: dict[str, Any] = {
            "id": a.id,
            "nombre_relevo": a.nombre_relevo,
            "campos": list(a.campos),
            "motivo": MotivoAcceso(a.motivo),
            "estado": estado_acceso(VidaAcceso(a.expira_en, a.revocado_en, a.pin_intentos_fallidos), ahora),
            "creado_en": a.creado_en,
            "expira_en": a.expira_en,
            "revocado_en": a.revocado_en,
            "usos": a.usos,
            "ultimo_uso_en": a.ultimo_uso_en,
            "otorgado_por": None
            if a.otorgado_por is None
            else AutorAccesoVista(id=a.otorgado_por.id, nombre=a.otorgado_por.nombre),
        }
        if con_telefono:
            datos["telefono_relevo"] = a.telefono_relevo
        items.append(AccesoResumenVista(**datos))
    response.headers["Cache-Control"] = NO_STORE
    return ListaAccesosVista(
        items=items,
        siguiente_cursor=None if pagina.siguiente is None else codificar_cursor(pagina.siguiente),
    )


@router.delete(
    RUTA_ACCESO,
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=_ERRORES_REVOCAR,
)
def revocar_acceso(
    request: Request,
    autorizado: Annotated[AccesoARevocar, Depends(acceso_para_revocar)],
    accesos: Annotated[RepositorioAccesos, Depends(obtener_repositorio_accesos)],
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
) -> Response:
    """Revoca el acceso en la transacción de la petición. Idempotente: ya revocado o vencido, 204."""
    peticion = PeticionRevocar(
        grupo_id=autorizado.contexto.grupo_id,
        usuario_id=autorizado.contexto.usuario_id,
        acceso_id=autorizado.acceso_id,
        request_id=getattr(request.state, "request_id", None),
    )
    try:
        revocar(peticion, accesos, reloj)
    except AccesoNoEncontrado:
        raise ErrorMATU(404) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": NO_STORE})
