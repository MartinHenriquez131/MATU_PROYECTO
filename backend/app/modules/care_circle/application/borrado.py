"""Caso de uso: borrar los datos de la persona al tiro, cuando se pide (MATU-72, decisiones 149 a 157).

care_circle es dueño de ``persona_cuidada`` y ``consentimiento`` y no importa care_plan ni consumption
(tests/test_arquitectura.py). Lo que el borrado hace en esos módulos llega por el mismo ``EfectoDelRetiro`` del
retiro (MATU-44), con su método ``borrar``: care_plan corta los enlaces con la regla del retiro, destruye la clave y
borra las secciones; consumption borra los perfiles. app.main los registra (infrastructure/efectos_retiro.py).

Todo corre en la transacción de la petición (sesion_de_grupo) y con un solo instante del Reloj (C1). Si algo
falla, la excepción sigue y sesion_tenant deshace todo: la marca, las revocaciones, los cortes, la clave y la
auditoría (C13).

Orden de los bloqueos (C1): 1) la persona (FOR UPDATE); 2) sus autorizaciones no revocadas (FOR UPDATE, en el
orden de orden_de_bloqueo); 3) y 4) los accesos y la clave, en el efecto de plan_cuidado.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.modules.care_circle.application.retiro import EfectoDelRetiro, EfectoNoDisponible, RepositorioRetiros
from app.modules.care_circle.domain.borrado import (
    PersonaParaBorrar,
    exigir_borrable,
    orden_de_bloqueo,
    puede_borrar,
)
from app.modules.care_circle.domain.retiro import FINALIDADES_RETIRABLES, MOTIVO_BORRADO, AutorizacionRegistrada
from app.shared.puertos import Reloj


class RolSinPermisoBorrado(Exception):
    """El rol no borra (pagador u observador). La API responde 404."""


class RepositorioBorrado(Protocol):
    """La persona y sus autorizaciones en la transacción del contexto de grupo.

    Implementación: RepositorioBorradoSQL (infrastructure/repositorio_borrado.py).
    """

    def bloquear_persona(self, persona_id: uuid.UUID) -> PersonaParaBorrar | None:
        """La fila de la persona del grupo, bloqueada (FOR UPDATE), aunque esté eliminada. None si no es del grupo."""
        ...

    def bloquear_vigentes(self, persona_id: uuid.UUID) -> list[AutorizacionRegistrada]:
        """Sus autorizaciones no revocadas de toda finalidad, bloqueadas (FOR UPDATE) en el orden de C1."""
        ...

    def anonimizar(
        self, persona: PersonaParaBorrar, ahora: datetime, usuario_id: uuid.UUID, request_id: str | None
    ) -> None:
        """Deja la fila sin datos y con la marca (D5), borra su dirección si nadie más la usa y registra
        persona.borrar."""
        ...


@dataclass(frozen=True)
class SolicitudBorrado:
    usuario_id: uuid.UUID
    rol: str
    persona_id: uuid.UUID
    request_id: str | None = None


@dataclass(frozen=True)
class PersonaBorrada:
    persona_id: uuid.UUID
    borrado_en: datetime
    enlaces_cortados: int
    autorizaciones_retiradas: int


def borrar_persona(
    solicitud: SolicitudBorrado,
    reloj: Reloj,
    repositorio: RepositorioBorrado,
    retiros: RepositorioRetiros,
    efectos: Mapping[str, EfectoDelRetiro],
) -> PersonaBorrada:
    """Borra al tiro todo lo guardado de la persona. Orden: rol (404), persona (404), ya borrada (409). Después,
    todo en la misma transacción y con un solo instante del Reloj."""
    if not puede_borrar(solicitud.rol):
        raise RolSinPermisoBorrado()
    persona = exigir_borrable(repositorio.bloquear_persona(solicitud.persona_id))
    # Falla cerrado: sin el efecto de una finalidad, lo de esa finalidad quedaría guardado
    if any(finalidad not in efectos for finalidad in FINALIDADES_RETIRABLES):
        raise EfectoNoDisponible()
    vigentes = repositorio.bloquear_vigentes(persona.id)
    ahora = reloj.ahora()

    for autorizacion in vigentes:
        retiros.retirar(autorizacion.id, ahora, solicitud.usuario_id, solicitud.request_id, motivo=MOTIVO_BORRADO)
    cortados = 0
    for finalidad in sorted(efectos, key=lambda f: (orden_de_bloqueo(f), f)):
        cortados += efectos[finalidad].borrar(persona.id, ahora, solicitud.usuario_id, solicitud.request_id)
    repositorio.anonimizar(persona, ahora, solicitud.usuario_id, solicitud.request_id)
    return PersonaBorrada(
        persona_id=persona.id, borrado_en=ahora, enlaces_cortados=cortados, autorizaciones_retiradas=len(vigentes)
    )
