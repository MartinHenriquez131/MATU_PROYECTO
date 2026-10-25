"""Casos de uso: dar de alta a la persona cuidada con su consentimiento y listar las personas del
grupo según el rol (MATU-07, RF-01, Ley 21.719).

No crea la clave de datos ni cifra nada: la clave se crea en la primera escritura de la ficha (MATU-11).
"""

import uuid
from dataclasses import dataclass

from app.modules.care_circle.application.ports import (
    AltaPersona,
    DatosDireccion,
    PersonaCompleta,
    PersonaNombreYDireccion,
    PersonaSoloNombre,
    RepositorioPersonas,
)
from app.modules.care_circle.domain.avisos import Aviso
from app.modules.care_circle.domain.personas import (
    FINALIDAD_PLAN_CUIDADO,
    AvisoMostrado,
    CalidadOtorgante,
    VistaPersona,
    aviso_de,
    evidencia,
    puede_dar_de_alta,
    revision_vence_en,
    validar_otorgamiento,
    vista_para_rol,
)
from app.shared.puertos import Reloj


class RolSinPermiso(Exception):
    """El rol del usuario en el grupo no da de alta. La API responde 404, nunca 403."""


@dataclass(frozen=True)
class SolicitudAlta:
    usuario_id: uuid.UUID
    grupo_id: uuid.UUID
    rol: str
    nombre: str
    nombre_pila: str
    nivel_apoyo: str
    calidad_otorgante: CalidadOtorgante
    referencia_documento: str | None
    aviso: AvisoMostrado | None
    direccion: DatosDireccion | None
    request_id: str | None = None


@dataclass(frozen=True)
class PersonaDadaDeAlta:
    alta: AltaPersona
    # El aviso que se mostró, para devolverlo en la respuesta. None si la calidad no lleva aviso
    aviso: Aviso | None


def dar_de_alta(
    solicitud: SolicitudAlta, version_politica: str, reloj: Reloj, repositorio: RepositorioPersonas
) -> PersonaDadaDeAlta:
    """Crea la persona, su dirección si llegó, su consentimiento para plan_cuidado y la auditoría,
    en la transacción del repositorio: todo o nada.

    La versión de la política la fija el servidor. Los instantes salen del Reloj.

    Lanza RolSinPermiso si el rol no es admin ni cuidador, y OtorgamientoInvalido si la calidad no
    calza con el aviso o con la referencia al documento. En ambos casos no escribe nada.
    """
    if not puede_dar_de_alta(solicitud.rol):
        raise RolSinPermiso()
    validar_otorgamiento(solicitud.calidad_otorgante, solicitud.referencia_documento, solicitud.aviso)

    otorgado_en = reloj.ahora()
    alta = AltaPersona(
        grupo_id=solicitud.grupo_id,
        usuario_id=solicitud.usuario_id,
        persona_id=uuid.uuid4(),
        nombre=solicitud.nombre,
        nombre_pila=solicitud.nombre_pila,
        nivel_apoyo=solicitud.nivel_apoyo,
        direccion_id=uuid.uuid4() if solicitud.direccion is not None else None,
        direccion=solicitud.direccion,
        consentimiento_id=uuid.uuid4(),
        calidad_otorgante=solicitud.calidad_otorgante.value,
        finalidad=FINALIDAD_PLAN_CUIDADO,
        version_politica=version_politica,
        evidencia=evidencia(solicitud.calidad_otorgante, version_politica),
        referencia_documento=solicitud.referencia_documento or None,
        otorgado_en=otorgado_en,
        revision_vence_en=revision_vence_en(solicitud.calidad_otorgante, otorgado_en),
        request_id=solicitud.request_id,
    )
    repositorio.guardar_alta(alta)
    return PersonaDadaDeAlta(alta=alta, aviso=aviso_de(solicitud.calidad_otorgante))


PersonaListada = PersonaCompleta | PersonaNombreYDireccion | PersonaSoloNombre


def listar_personas(rol: str, repositorio: RepositorioPersonas) -> list[PersonaListada]:
    """Las personas del grupo, con la proyección del rol (arquitectura 11.2).

    Cada vista sale de su propia consulta: lo que el rol no ve ni siquiera se lee de la base.
    """
    vista = vista_para_rol(rol)
    if vista is VistaPersona.COMPLETA:
        return list(repositorio.listar_completas())
    if vista is VistaPersona.NOMBRE_Y_DIRECCION:
        return list(repositorio.listar_nombre_y_direccion())
    return list(repositorio.listar_solo_nombre())
