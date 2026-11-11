"""Autorizaciones de la persona: darlas (MATU-36, decisión 37, y MATU-44, decisión 128), ver su estado y
retirarlas (MATU-44, decisiones 123 a 127).

    POST /v1/personas-cuidadas/{persona_id}/consentimientos                       admin y cuidador. 201
    GET  /v1/personas-cuidadas/{persona_id}/consentimientos                       todo miembro activo. 200
    POST /v1/personas-cuidadas/{persona_id}/consentimientos/{finalidad}/retiro    admin y cuidador. 200

Contrato: docs/api/openapi.json. Orden de evaluación del POST: 401, 404 (membresía, rol, persona), 422
(cuerpo y reglas de la calidad), 409 y 201. El rol y la persona se verifican en dependencias, antes de
validar el cuerpo: un observador recibe 404 aunque su cuerpo sea inválido. Registra consentimiento.otorgar,
sin la referencia al documento.

El retiro corre en una sola transacción: la revocación, consentimiento.revocar y el efecto de la finalidad
(cortar los accesos de relevo o descartar las alertas), que app.main registra en
infrastructure/efectos_retiro.py. Orden del retiro: 401, 404, 409 y 200. Nada de la persona va a los logs.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, Path, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import obtener_configuracion
from app.core.errores import ErrorMATU
from app.modules.care_circle.api.dependencias import ContextoGrupo, SesionDeGrupo
from app.modules.care_circle.api.esquemas_personas import (
    AvisoMostradoEntrada,
    AvisoVista,
    ConsentimientoVista,
    ReferenciaDocumento,
)
from app.modules.care_circle.api.router_personas import obtener_politica_version
from app.modules.care_circle.application.autorizaciones import (
    AutorizacionVigente,
    DeclaracionNoVigente,
    PersonaNoDisponible,
    RepositorioAutorizaciones,
    RolSinPermisoAutorizacion,
    SolicitudAutorizacion,
    otorgar_autorizacion,
)
from app.modules.care_circle.application.retiro import (
    AutorizacionNoEncontrada,
    EfectoDelRetiro,
    EfectoNoDisponible,
    RepositorioRetiros,
    RolSinPermisoRetiro,
    SolicitudRetiro,
    antes_de_otorgar,
    estado_autorizaciones,
    retirar_autorizacion,
)
from app.modules.care_circle.domain.personas import (
    FINALIDAD_DESPACHO,
    AvisoMostrado,
    CalidadOtorgante,
    OtorgamientoInvalido,
    puede_dar_de_alta,
)
from app.modules.care_circle.domain.retiro import (
    EstadoDeAutorizacion,
    EstadoVista,
    RetiroNoPermitido,
    YaRetirada,
    finalidad_de,
    finalidades_retirables,
)
from app.modules.care_circle.infrastructure.autorizacion import persona_con_autorizacion
from app.modules.care_circle.infrastructure.efectos_retiro import efectos_de
from app.modules.care_circle.infrastructure.repositorio_autorizaciones import RepositorioAutorizacionesSQL
from app.modules.care_circle.infrastructure.repositorio_retiros import RepositorioRetirosSQL
from app.modules.iam.api.dependencias import obtener_reloj
from app.shared.auditoria_sql import RegistroAuditoriaSql
from app.shared.puertos import RegistroAuditoria, Reloj
from app.shared.reloj_detenido import RelojDetenido

log = logging.getLogger("matu.care_circle.autorizaciones")

router = APIRouter(tags=["autorizaciones"])

RUTA = "/personas-cuidadas/{persona_id}/consentimientos"
RUTA_RETIRO = RUTA + "/{finalidad}/retiro"

_DETALLE_VIGENTE = {
    "consumo": "Esta persona ya tiene la autorización para calcular sus insumos",
    "plan_cuidado": "Esta persona ya tiene la autorización para usar su ficha",
    "despacho": "Esta persona ya tiene la autorización para pedir sus insumos",
}

_PROBLEMA: dict[str, Any] = {"content": {"application/problem+json": {}}}
_ERRORES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Falta el access token, o es inválido o vencido", **_PROBLEMA},
    404: {"description": "No miembro, rol que no alcanza, persona de otro grupo o inexistente", **_PROBLEMA},
    409: {"description": "/errores/autorizacion-vigente: ya hay una autorización no revocada", **_PROBLEMA},
    422: {"description": "Cuerpo inválido o una combinación que no cumple las reglas de la calidad", **_PROBLEMA},
}


class SolicitudAutorizacionEntrada(BaseModel):
    """Cuerpo de la autorización: ``consumo`` (MATU-36), ``plan_cuidado`` para volver a autorizar la ficha
    (MATU-44, decisión 128) o ``despacho``, la de pedidos (MATU-61, D1), solo con la capa 3. Un campo extra
    responde 422."""

    model_config = ConfigDict(extra="forbid")

    finalidad: Literal["consumo", "plan_cuidado", "despacho"]
    calidad_otorgante: CalidadOtorgante
    referencia_documento: ReferenciaDocumento | None = None
    aviso: AvisoMostradoEntrada | None = None
    huella_declaracion: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
        description=(
            "MATU-61 (P13): SHA-256 de la plantilla de declaracion_pedidos_<calidad> que se mostró, con {nombre_pila}"
            " sin reemplazar. Obligatoria con despacho y prohibida con las otras dos (422). Otra huella: 422"
            " declaracion_no_vigente"
        ),
    )


def finalidades_activas() -> tuple[str, ...]:
    """Las finalidades que existen: con la capa 3, también despacho (C2, decisión 217). Las pruebas la
    sobreescriben."""
    return finalidades_retirables(obtener_configuracion().capa3_habilitada)


Finalidades = Annotated[tuple[str, ...], Depends(finalidades_activas)]


class AutorizacionCreada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consentimiento: ConsentimientoVista
    aviso: AvisoVista | None


@dataclass(frozen=True)
class PersonaParaAutorizar:
    contexto: ContextoGrupo
    persona_id: uuid.UUID


def persona_para_autorizar(
    contexto: SesionDeGrupo, persona_id: Annotated[str, Path(json_schema_extra={"format": "uuid"})]
) -> PersonaParaAutorizar:
    """Dan, ven y retiran la autorización admin y cuidador; la persona debe ser del grupo. Si no, 404."""
    if not puede_dar_de_alta(contexto.rol):
        raise ErrorMATU(404)
    try:
        persona = uuid.UUID(persona_id)
    except ValueError:
        raise ErrorMATU(404) from None
    if persona_con_autorizacion(contexto.sesion, contexto.grupo_id, persona) is None:
        raise ErrorMATU(404)
    return PersonaParaAutorizar(contexto, persona)


def reloj_de_la_peticion(reloj: Annotated[Reloj, Depends(obtener_reloj)]) -> Reloj:
    """Un solo instante por petición (decisión 124): el caso de uso y la auditoría leen el mismo. FastAPI
    resuelve esta dependencia una vez por petición y entrega la misma instancia a todos."""
    return RelojDetenido(reloj.ahora())


def obtener_registro_autorizaciones(
    contexto: SesionDeGrupo, reloj: Annotated[Reloj, Depends(reloj_de_la_peticion)]
) -> RegistroAuditoria:
    """El registro de auditoría en la transacción de la petición."""
    return RegistroAuditoriaSql(contexto.sesion, reloj)


RegistroDep = Annotated[RegistroAuditoria, Depends(obtener_registro_autorizaciones)]


def obtener_repositorio_autorizaciones(contexto: SesionDeGrupo, registro: RegistroDep) -> RepositorioAutorizaciones:
    return RepositorioAutorizacionesSQL(contexto.sesion, contexto.grupo_id, registro)


def obtener_repositorio_retiros(contexto: SesionDeGrupo, registro: RegistroDep) -> RepositorioRetiros:
    return RepositorioRetirosSQL(contexto.sesion, contexto.grupo_id, registro)


def obtener_efectos_retiro(contexto: SesionDeGrupo, registro: RegistroDep) -> dict[str, EfectoDelRetiro]:
    """Los efectos del retiro de cada finalidad, en la transacción de la petición. Las pruebas lo pueden
    sobreescribir para hacer fallar un efecto."""
    return efectos_de(contexto.sesion, contexto.grupo_id, registro)


Efectos = Annotated[dict[str, EfectoDelRetiro], Depends(obtener_efectos_retiro)]
Retiros = Annotated[RepositorioRetiros, Depends(obtener_repositorio_retiros)]
RelojDep = Annotated[Reloj, Depends(reloj_de_la_peticion)]
Autorizar = Annotated[PersonaParaAutorizar, Depends(persona_para_autorizar)]


@router.post(
    RUTA,
    status_code=status.HTTP_201_CREATED,
    response_model=AutorizacionCreada,
    responses=_ERRORES,
    summary="Dar la autorización para calcular los insumos o para usar la ficha",
)
def otorgar(
    request: Request,
    response: Response,
    autorizar: Autorizar,
    solicitud: SolicitudAutorizacionEntrada,
    repositorio: Annotated[RepositorioAutorizaciones, Depends(obtener_repositorio_autorizaciones)],
    reloj: RelojDep,
    version_politica: Annotated[str, Depends(obtener_politica_version)],
    retiros: Retiros,
    efectos: Efectos,
    finalidades: Finalidades,
) -> AutorizacionCreada:
    contexto = autorizar.contexto
    aviso = solicitud.aviso
    request_id = getattr(request.state, "request_id", None)
    if solicitud.finalidad == FINALIDAD_DESPACHO and FINALIDAD_DESPACHO not in finalidades:
        # C2: sin la capa 3 no hay pedidos que autorizar
        raise ErrorMATU(
            422,
            detalle="Revisa los campos indicados",
            errores=[
                {"campo": "finalidad", "mensaje": "esta autorización no está disponible", "tipo": "literal_error"}
            ],
        )

    def preparar() -> None:
        # Decisión 128: una autorización 90 días o más después del retiro no recupera lo que se borró
        antes_de_otorgar(autorizar.persona_id, solicitud.finalidad, reloj.ahora(), request_id, retiros, efectos)

    try:
        resultado = otorgar_autorizacion(
            SolicitudAutorizacion(
                usuario_id=contexto.usuario_id,
                grupo_id=contexto.grupo_id,
                rol=contexto.rol,
                persona_id=autorizar.persona_id,
                calidad_otorgante=solicitud.calidad_otorgante,
                referencia_documento=solicitud.referencia_documento,
                aviso=None if aviso is None else AvisoMostrado(id=aviso.id, version=aviso.version),
                request_id=request_id,
                finalidad=solicitud.finalidad,
                huella_declaracion=solicitud.huella_declaracion,
            ),
            version_politica,
            reloj,
            repositorio,
            preparar,
        )
    except (RolSinPermisoAutorizacion, PersonaNoDisponible):
        raise ErrorMATU(404) from None
    except OtorgamientoInvalido as error:
        tipo = "declaracion_no_vigente" if isinstance(error, DeclaracionNoVigente) else "regla_calidad_otorgante"
        raise ErrorMATU(
            422,
            detalle="Revisa los campos indicados",
            errores=[{"campo": error.campo, "mensaje": error.mensaje, "tipo": tipo}],
        ) from None
    except AutorizacionVigente:
        raise ErrorMATU(409, tipo="autorizacion-vigente", detalle=_DETALLE_VIGENTE[solicitud.finalidad]) from None
    except EfectoNoDisponible:
        log.error("falta el efecto del retiro de una finalidad")
        raise ErrorMATU(500) from None

    response.headers["Cache-Control"] = "no-store"
    nueva = resultado.autorizacion
    a = resultado.aviso
    return AutorizacionCreada(
        consentimiento=ConsentimientoVista(
            id=nueva.id,
            calidad_otorgante=solicitud.calidad_otorgante,
            finalidad=nueva.finalidad,
            version_politica=nueva.version_politica,
            otorgado_en=nueva.otorgado_en,
            revision_vence_en=nueva.revision_vence_en,
        ),
        aviso=None
        if a is None
        else AvisoVista(id=a.id, version=a.version, titulo=a.titulo, parrafos=list(a.parrafos), sha256=a.sha256),
    )


# --- Estado y retiro (MATU-44) ------------------------------------------------------------------------

FinalidadVista = Literal["plan_cuidado", "consumo", "despacho"]


class AutorizacionVista(BaseModel):
    """El estado de una autorización (decisión 127, C1). Sin la referencia al documento, la evidencia, la
    versión de la política ni quién la dio. La pantalla no calcula fechas: ``borrado_en`` y ``borrada``
    salen de aquí."""

    model_config = ConfigDict(extra="forbid")

    finalidad: FinalidadVista
    estado: EstadoVista
    id: uuid.UUID | None
    calidad_otorgante: CalidadOtorgante | None
    otorgado_en: datetime | None
    revision_vence_en: datetime | None
    revocado_en: datetime | None
    borrado_en: datetime | None
    borrada: bool


class AutorizacionesPersona(BaseModel):
    """plan_cuidado y consumo, en ese orden, y despacho con la capa 3 (C2). Lo que ven admin y cuidador."""

    model_config = ConfigDict(extra="forbid")

    autorizaciones: list[AutorizacionVista]


class AutorizacionVistaResumen(BaseModel):
    """Lo que ven el pagador y el observador (P2 y C5 de Jorge): el estado y sus fechas, sin la calidad del
    otorgante. Es un DTO distinto, no la misma vista con el campo en null (arquitectura 11.1 y 11.2)."""

    model_config = ConfigDict(extra="forbid")

    finalidad: FinalidadVista
    estado: EstadoVista
    id: uuid.UUID | None
    otorgado_en: datetime | None
    revision_vence_en: datetime | None
    revocado_en: datetime | None
    borrado_en: datetime | None
    borrada: bool


class AutorizacionesPersonaResumen(BaseModel):
    """Los mismos ítems de AutorizacionesPersona. Lo que ven el pagador y el observador."""

    model_config = ConfigDict(extra="forbid")

    autorizaciones: list[AutorizacionVistaResumen]


class RetiroAutorizacion(BaseModel):
    """Respuesta del retiro. ``enlaces_cortados`` es 0 al retirar consumo y despacho (decisión 126, C2).
    ``pedidos_cancelados`` (MATU-61, decisión 192): los pedidos sin pagar que canceló el retiro de despacho; 0 con
    las otras finalidades."""

    model_config = ConfigDict(extra="forbid")

    autorizacion: AutorizacionVista
    enlaces_cortados: int
    pedidos_cancelados: int = Field(ge=0)


def _vista(estado: EstadoDeAutorizacion) -> AutorizacionVista:
    a = estado.autorizacion
    return AutorizacionVista(
        finalidad=cast(FinalidadVista, estado.finalidad),
        estado=estado.estado,
        id=None if a is None else a.id,
        calidad_otorgante=None if a is None else CalidadOtorgante(a.calidad_otorgante),
        otorgado_en=None if a is None else a.otorgado_en,
        revision_vence_en=None if a is None else a.revision_vence_en,
        revocado_en=None if a is None else a.revocado_en,
        borrado_en=estado.borrado_en,
        borrada=estado.borrada,
    )


def persona_para_ver(
    contexto: SesionDeGrupo, persona_id: Annotated[str, Path(json_schema_extra={"format": "uuid"})]
) -> PersonaParaAutorizar:
    """Ven el estado los cuatro roles (P2). La persona debe ser del grupo; si no, 404."""
    try:
        persona = uuid.UUID(persona_id)
    except ValueError:
        raise ErrorMATU(404) from None
    if persona_con_autorizacion(contexto.sesion, contexto.grupo_id, persona) is None:
        raise ErrorMATU(404)
    return PersonaParaAutorizar(contexto, persona)


def _resumen(estado: EstadoDeAutorizacion) -> AutorizacionVistaResumen:
    completa = _vista(estado)
    return AutorizacionVistaResumen.model_validate(completa.model_dump(exclude={"calidad_otorgante"}))


@router.get(
    RUTA,
    response_model=AutorizacionesPersona | AutorizacionesPersonaResumen,
    responses={
        401: _ERRORES[401],
        404: {"description": "No miembro, persona de otro grupo o inexistente", **_PROBLEMA},
    },
    summary="El estado de las autorizaciones de la persona: dos, o tres con la capa 3",
)
def estado(
    ver: Annotated[PersonaParaAutorizar, Depends(persona_para_ver)],
    retiros: Retiros,
    reloj: RelojDep,
    finalidades: Finalidades,
) -> AutorizacionesPersona | AutorizacionesPersonaResumen:
    estados = estado_autorizaciones(ver.persona_id, reloj, retiros, finalidades)
    # Cada rol recibe su propia proyección: el pagador y el observador nunca reciben la calidad del otorgante
    if puede_dar_de_alta(ver.contexto.rol):
        return AutorizacionesPersona(autorizaciones=[_vista(e) for e in estados])
    return AutorizacionesPersonaResumen(autorizaciones=[_resumen(e) for e in estados])


FinalidadRuta = Annotated[
    str,
    Path(
        description="plan_cuidado, consumo o, con la capa 3, despacho. Otro valor responde 404",
        json_schema_extra={"enum": ["plan_cuidado", "consumo", "despacho"]},
    ),
]


@router.post(
    RUTA_RETIRO,
    response_model=RetiroAutorizacion,
    responses={
        401: _ERRORES[401],
        404: {
            "description": "No miembro, rol que no alcanza, persona de otro grupo o inexistente, o una finalidad que"
            " no es una de las dos o que nunca se autorizó",
            **_PROBLEMA,
        },
        409: {"description": "/errores/ya-retirada: la autorización ya estaba retirada", **_PROBLEMA},
    },
    summary="Retirar la autorización de una finalidad y cortar lo que depende de ella",
)
def retirar(
    request: Request,
    autorizar: Autorizar,
    finalidad: FinalidadRuta,
    retiros: Retiros,
    efectos: Efectos,
    reloj: RelojDep,
    finalidades: Finalidades,
) -> RetiroAutorizacion:
    valida = finalidad_de(finalidad, finalidades)
    if valida is None:
        raise ErrorMATU(404)
    contexto = autorizar.contexto
    try:
        resultado = retirar_autorizacion(
            SolicitudRetiro(
                usuario_id=contexto.usuario_id,
                rol=contexto.rol,
                persona_id=autorizar.persona_id,
                finalidad=valida,
                request_id=getattr(request.state, "request_id", None),
            ),
            reloj,
            retiros,
            efectos,
            finalidades,
        )
    except (RolSinPermisoRetiro, AutorizacionNoEncontrada):
        raise ErrorMATU(404) from None
    except YaRetirada:
        raise ErrorMATU(409, tipo="ya-retirada", detalle="Esta autorización ya estaba retirada") from None
    except RetiroNoPermitido:  # pragma: no cover - RETIRO_CON_REVISION_VENCIDA (P6, decidido por Jorge el 06-11)
        raise ErrorMATU(409, tipo="ya-retirada", detalle="Esta autorización no se puede retirar") from None
    except EfectoNoDisponible:
        log.error("falta el efecto del retiro de una finalidad")
        raise ErrorMATU(500) from None
    return RetiroAutorizacion(
        autorizacion=_vista(resultado.estado),
        enlaces_cortados=resultado.enlaces_cortados,
        pedidos_cancelados=resultado.pedidos_cancelados,
    )
