"""Casos de uso: retirar una autorización, ver el estado de las dos y lo que hace falta antes de volver a
autorizar (MATU-44, decisiones 123 a 135).

care_circle es dueño de ``consentimiento`` y no importa care_plan ni consumption (tests/test_arquitectura.py).
Lo que el retiro corta en otros módulos llega como un ``EfectoDelRetiro`` por finalidad, que implementan
care_plan (los accesos de relevo y la clave de la ficha) y consumption (las alertas y los perfiles), y que
app.main registra al armar la aplicación (care_circle/infrastructure/efectos_retiro.py).

Todo corre en la transacción de la petición (sesion_de_grupo): si un efecto falla, la excepción sigue y
sesion_tenant deshace también la revocación y su auditoría (condición 4 del analista).
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Protocol

from app.modules.care_circle.domain.retiro import (
    FINALIDADES_RETIRABLES,
    AutorizacionRegistrada,
    EstadoDeAutorizacion,
    YaRetirada,
    estado_de,
    exigir_retirable,
    plazo_cumplido,
    puede_retirar,
)
from app.shared.puertos import Reloj


class RolSinPermisoRetiro(Exception):
    """El rol no retira ni ve el estado (pagador u observador). La API responde 404."""


class AutorizacionNoEncontrada(LookupError):
    """La persona nunca tuvo una autorización para esa finalidad. La API responde 404."""


class EfectoNoDisponible(RuntimeError):
    """No hay un efecto registrado para la finalidad: el retiro no se hace (falla cerrado, 500)."""

    def __init__(self) -> None:
        super().__init__("falta el efecto del retiro")


class EfectoDelRetiro(Protocol):
    """Lo que cada módulo hace al retirar una finalidad, en la transacción de la petición."""

    def aplicar(self, persona_id: uuid.UUID, ahora: datetime, usuario_id: uuid.UUID, request_id: str | None) -> int:
        """Corta lo que depende de la autorización retirada. Devuelve cuántos enlaces cortó (0 si no aplica)."""
        ...

    def borrar_vencido(self, persona_id: uuid.UUID, ahora: datetime, request_id: str | None) -> None:
        """Borra lo guardado de una autorización cuyo plazo de 90 días ya se cumplió (decisión 128)."""
        ...

    def destruido_en(self, persona_id: uuid.UUID) -> datetime | None:
        """Cuándo se destruyó lo guardado, si se sabe (la clave de la ficha). None si no."""
        ...


class RepositorioRetiros(Protocol):
    """Lectura y revocación del consentimiento en la transacción del contexto de grupo.

    Implementación: RepositorioRetirosSQL (infrastructure/repositorio_retiros.py).
    """

    def bloquear_vigente(self, persona_id: uuid.UUID, finalidad: str) -> AutorizacionRegistrada | None:
        """La autorización no revocada, con la fila bloqueada (FOR UPDATE). None si no hay."""
        ...

    def ultima(self, persona_id: uuid.UUID, finalidad: str) -> AutorizacionRegistrada | None:
        """La no revocada o, si no hay, la de revocación más reciente. None si nunca hubo."""
        ...

    def retirar(
        self, consentimiento_id: uuid.UUID, ahora: datetime, usuario_id: uuid.UUID, request_id: str | None
    ) -> None:
        """Fija revocado_en y revocacion_motivo = 'retiro' y registra consentimiento.revocar."""
        ...


@dataclass(frozen=True)
class SolicitudRetiro:
    usuario_id: uuid.UUID
    rol: str
    persona_id: uuid.UUID
    finalidad: str
    request_id: str | None = None


@dataclass(frozen=True)
class AutorizacionRetirada:
    estado: EstadoDeAutorizacion
    enlaces_cortados: int


def retirar_autorizacion(
    solicitud: SolicitudRetiro,
    reloj: Reloj,
    repositorio: RepositorioRetiros,
    efectos: Mapping[str, EfectoDelRetiro],
) -> AutorizacionRetirada:
    """Retira la autorización de la finalidad. Orden: rol (404), finalidad o nunca autorizada (404),
    ya retirada (409). Después, todo en la misma transacción y con un solo instante del Reloj."""
    if not puede_retirar(solicitud.rol):
        raise RolSinPermisoRetiro()
    if solicitud.finalidad not in FINALIDADES_RETIRABLES:
        raise AutorizacionNoEncontrada()
    vigente = repositorio.bloquear_vigente(solicitud.persona_id, solicitud.finalidad)
    if vigente is None:
        if repositorio.ultima(solicitud.persona_id, solicitud.finalidad) is None:
            raise AutorizacionNoEncontrada()
        raise YaRetirada()
    ahora = reloj.ahora()
    exigir_retirable(vigente, ahora)
    efecto = efectos.get(solicitud.finalidad)
    if efecto is None:
        raise EfectoNoDisponible()

    repositorio.retirar(vigente.id, ahora, solicitud.usuario_id, solicitud.request_id)
    cortados = efecto.aplicar(solicitud.persona_id, ahora, solicitud.usuario_id, solicitud.request_id)
    retirada = replace(vigente, revocado_en=ahora)
    return AutorizacionRetirada(
        estado=estado_de(solicitud.finalidad, retirada, efecto.destruido_en(solicitud.persona_id), ahora),
        enlaces_cortados=cortados,
    )


def estado_autorizaciones(
    rol: str,
    persona_id: uuid.UUID,
    reloj: Reloj,
    repositorio: RepositorioRetiros,
    efectos: Mapping[str, EfectoDelRetiro],
) -> list[EstadoDeAutorizacion]:
    """Las dos finalidades, en el orden de la vista (decisión 127). Solo admin y cuidador."""
    if not puede_retirar(rol):
        raise RolSinPermisoRetiro()
    ahora = reloj.ahora()
    estados = []
    for finalidad in FINALIDADES_RETIRABLES:
        efecto = efectos.get(finalidad)
        destruido = None if efecto is None else efecto.destruido_en(persona_id)
        estados.append(estado_de(finalidad, repositorio.ultima(persona_id, finalidad), destruido, ahora))
    return estados


def antes_de_otorgar(
    persona_id: uuid.UUID,
    finalidad: str,
    ahora: datetime,
    request_id: str | None,
    repositorio: RepositorioRetiros,
    efectos: Mapping[str, EfectoDelRetiro],
) -> None:
    """Antes de una autorización nueva: si la anterior se retiró hace 90 días o más, borra lo que quedaba
    aunque la tarea no haya corrido (decisión 128). Una autorización tardía no recupera nada."""
    ultima = repositorio.ultima(persona_id, finalidad)
    if ultima is None or ultima.revocado_en is None or not plazo_cumplido(ultima.revocado_en, ahora):
        return
    efecto = efectos.get(finalidad)
    if efecto is None:
        raise EfectoNoDisponible()
    efecto.borrar_vencido(persona_id, ahora, request_id)
