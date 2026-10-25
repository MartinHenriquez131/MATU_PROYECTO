"""Rutas de personas cuidadas: el alta con su consentimiento y la lista del grupo (MATU-07, RF-01).

    POST /v1/grupos/{grupo_id}/personas-cuidadas   admin y cuidador. 201
    GET  /v1/grupos/{grupo_id}/personas-cuidadas   todo miembro activo, con la vista de su rol

Las dos usan sesion_de_grupo (cabecera X-Grupo-Id): nunca fijan el contexto por su cuenta. Si el
grupo del path no es el del contexto, o el rol no da de alta, responden el mismo 404 que un grupo
ajeno, nunca 403. Esas verificaciones son dependencias: corren antes de validar el cuerpo, así que
un observador recibe 404 aunque su cuerpo sea inválido.

Nada de la persona se registra en los logs: ni nombre, ni nombre de pila, ni referencia del
documento, ni dirección. La línea de la petición lleva solo la plantilla de la ruta, el usuario y
el grupo.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.core.config import obtener_configuracion
from app.core.errores import ErrorMATU
from app.modules.care_circle.api.dependencias import ContextoGrupo, SesionDeGrupo
from app.modules.care_circle.api.esquemas_personas import (
    AvisoVista,
    ConsentimientoVista,
    DireccionVista,
    PersonaCreada,
    PersonaVistaCompleta,
    PersonaVistaObservador,
    PersonaVistaPagador,
    SolicitudPersona,
)
from app.modules.care_circle.application.personas import (
    PersonaListada,
    RolSinPermiso,
    SolicitudAlta,
    dar_de_alta,
    listar_personas,
)
from app.modules.care_circle.application.ports import (
    DatosDireccion,
    PersonaCompleta,
    PersonaNombreYDireccion,
    RepositorioPersonas,
)
from app.modules.care_circle.domain.avisos import Aviso
from app.modules.care_circle.domain.personas import AvisoMostrado, OtorgamientoInvalido, puede_dar_de_alta
from app.modules.care_circle.infrastructure.repositorio_personas import RepositorioPersonasSQL
from app.modules.iam.api.dependencias import obtener_reloj
from app.shared.puertos import Reloj

router = APIRouter(tags=["personas cuidadas"])

RUTA = "/grupos/{grupo_id}/personas-cuidadas"


def obtener_politica_version() -> str:
    """La versión vigente de la política. La fija el servidor; el cliente nunca la envía."""
    version = obtener_configuracion().politica_version
    if version is None:  # pragma: no cover - la configuración no carga sin ella fuera de pruebas
        raise RuntimeError("Falta POLITICA_VERSION")
    return version


def contexto_del_grupo(grupo_id: str, contexto: SesionDeGrupo) -> ContextoGrupo:
    """El contexto de grupo, si el grupo del path es el mismo de X-Grupo-Id. Si no, 404."""
    try:
        del_path = uuid.UUID(grupo_id)
    except ValueError:
        raise ErrorMATU(404) from None
    if del_path != contexto.grupo_id:
        raise ErrorMATU(404)
    return contexto


ContextoDelGrupo = Annotated[ContextoGrupo, Depends(contexto_del_grupo)]


def contexto_que_da_de_alta(contexto: ContextoDelGrupo) -> ContextoGrupo:
    """El contexto, si el rol da de alta (admin o cuidador). pagador y observador reciben 404."""
    if not puede_dar_de_alta(contexto.rol):
        raise ErrorMATU(404)
    return contexto


def obtener_repositorio_personas(contexto: SesionDeGrupo) -> RepositorioPersonas:
    return RepositorioPersonasSQL(contexto.sesion, contexto.grupo_id)


def _direccion_dominio(solicitud: SolicitudPersona) -> DatosDireccion | None:
    d = solicitud.direccion
    if d is None:
        return None
    return DatosDireccion(
        etiqueta=d.etiqueta,
        calle=d.calle,
        numero=d.numero,
        depto=d.depto,
        comuna=d.comuna,
        region=d.region,
        referencia=d.referencia,
    )


def _direccion_vista(d: DatosDireccion | None) -> DireccionVista | None:
    if d is None:
        return None
    return DireccionVista(
        etiqueta=d.etiqueta,
        calle=d.calle,
        numero=d.numero,
        depto=d.depto,
        comuna=d.comuna,
        region=d.region,
        referencia=d.referencia,
    )


def _aviso_vista(aviso: Aviso | None) -> AvisoVista | None:
    if aviso is None:
        return None
    return AvisoVista(
        id=aviso.id, version=aviso.version, titulo=aviso.titulo, parrafos=list(aviso.parrafos), sha256=aviso.sha256
    )


@router.post(RUTA, status_code=status.HTTP_201_CREATED, response_model=PersonaCreada)
def crear(
    request: Request,
    solicitud: SolicitudPersona,
    contexto: Annotated[ContextoGrupo, Depends(contexto_que_da_de_alta)],
    repositorio: Annotated[RepositorioPersonas, Depends(obtener_repositorio_personas)],
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
    version_politica: Annotated[str, Depends(obtener_politica_version)],
) -> PersonaCreada:
    aviso = solicitud.aviso
    alta_solicitada = SolicitudAlta(
        usuario_id=contexto.usuario_id,
        grupo_id=contexto.grupo_id,
        rol=contexto.rol,
        nombre=solicitud.nombre,
        nombre_pila=solicitud.nombre_pila,
        nivel_apoyo=solicitud.nivel_apoyo,
        calidad_otorgante=solicitud.calidad_otorgante,
        referencia_documento=solicitud.referencia_documento,
        aviso=None if aviso is None else AvisoMostrado(id=aviso.id, version=aviso.version),
        direccion=_direccion_dominio(solicitud),
        request_id=getattr(request.state, "request_id", None),
    )
    try:
        resultado = dar_de_alta(alta_solicitada, version_politica, reloj, repositorio)
    except RolSinPermiso:
        raise ErrorMATU(404) from None
    except OtorgamientoInvalido as error:
        # El mensaje es fijo y nombra el campo, nunca el valor
        raise ErrorMATU(
            422,
            detalle="Revisa los campos indicados",
            errores=[{"campo": error.campo, "mensaje": error.mensaje, "tipo": "regla_calidad_otorgante"}],
        ) from None

    alta = resultado.alta
    return PersonaCreada(
        id=alta.persona_id,
        nombre=alta.nombre,
        nombre_pila=alta.nombre_pila,
        nivel_apoyo=solicitud.nivel_apoyo,
        direccion=_direccion_vista(alta.direccion),
        consentimiento=ConsentimientoVista(
            id=alta.consentimiento_id,
            calidad_otorgante=solicitud.calidad_otorgante,
            finalidad=alta.finalidad,
            version_politica=alta.version_politica,
            otorgado_en=alta.otorgado_en,
            revision_vence_en=alta.revision_vence_en,
        ),
        aviso=_aviso_vista(resultado.aviso),
    )


VistaPersona = PersonaVistaCompleta | PersonaVistaPagador | PersonaVistaObservador


def _vista(persona: PersonaListada) -> VistaPersona:
    # Cada vista se arma desde su propia proyección: el pagador y el observador nunca reciben un
    # objeto completo con campos ocultos (arquitectura 11.1)
    if isinstance(persona, PersonaCompleta):
        return PersonaVistaCompleta.model_validate(persona, from_attributes=True)
    if isinstance(persona, PersonaNombreYDireccion):
        return PersonaVistaPagador.model_validate(persona, from_attributes=True)
    return PersonaVistaObservador.model_validate(persona, from_attributes=True)


@router.get(
    RUTA,
    response_model=list[PersonaVistaCompleta] | list[PersonaVistaPagador] | list[PersonaVistaObservador],
)
def listar(
    contexto: ContextoDelGrupo,
    repositorio: Annotated[RepositorioPersonas, Depends(obtener_repositorio_personas)],
) -> list[VistaPersona]:
    return [_vista(p) for p in listar_personas(contexto.rol, repositorio)]
