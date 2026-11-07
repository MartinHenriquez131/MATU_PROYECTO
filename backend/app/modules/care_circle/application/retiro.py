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

    def antes_de_otorgar(
        self, persona_id: uuid.UUID, ahora: datetime, request_id: str | None, plazo_cumplido: bool
    ) -> None:
        """Antes de una autorización nueva: con ``plazo_cumplido`` borra lo que quedaba (decisión 128), y deja
        lista una ficha en blanco si lo anterior ya no se puede leer (decisión 130)."""
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

    def retiro_anterior(
        self, persona_id: uuid.UUID, finalidad: str, antes_de: datetime
    ) -> AutorizacionRegistrada | None:
        """El último retiro (motivo retiro) revocado en ``antes_de`` o antes. None si no hay."""
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
    return AutorizacionRetirada(estado=estado_de(solicitud.finalidad, retirada, None, ahora), enlaces_cortados=cortados)


def estado_autorizaciones(
    persona_id: uuid.UUID, reloj: Reloj, repositorio: RepositorioRetiros
) -> list[EstadoDeAutorizacion]:
    """Las dos finalidades, en el orden de la vista (decisión 127). La ven los cuatro roles (P2): la API
    elige la proyección del rol. Sale solo de los consentimientos y del Reloj, sin leer la ficha."""
    ahora = reloj.ahora()
    estados = []
    for finalidad in FINALIDADES_RETIRABLES:
        actual = repositorio.ultima(persona_id, finalidad)
        anterior = (
            None
            if actual is None or actual.revocado_en is not None
            else repositorio.retiro_anterior(persona_id, finalidad, actual.otorgado_en)
        )
        estados.append(estado_de(finalidad, actual, anterior, ahora))
    return estados


def antes_de_otorgar(
    persona_id: uuid.UUID,
    finalidad: str,
    ahora: datetime,
    request_id: str | None,
    repositorio: RepositorioRetiros,
    efectos: Mapping[str, EfectoDelRetiro],
) -> None:
    """Antes de una autorización nueva. Si la anterior se retiró hace 90 días o más, el efecto borra lo que
    quedaba aunque la tarea no haya corrido (decisión 128): una autorización tardía no recupera nada. Si
    nunca hubo una autorización revocada, no hace nada."""
    ultima = repositorio.ultima(persona_id, finalidad)
    if ultima is None or ultima.revocado_en is None:
        return
    efecto = efectos.get(finalidad)
    if efecto is None:
        raise EfectoNoDisponible()
    efecto.antes_de_otorgar(persona_id, ahora, request_id, plazo_cumplido(ultima.revocado_en, ahora))
