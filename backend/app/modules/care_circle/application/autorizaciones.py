"""Caso de uso: dar la autorización para calcular cuándo se acaban los insumos (MATU-36, decisión 37).

Reutiliza el alta de MATU-07: la misma calidad del otorgante, las mismas reglas cruzadas
(validar_otorgamiento), el mismo aviso del cuidador de hecho y la misma revisión anual. Cambian la
finalidad (``consumo``) y la declaración de la evidencia (``declaracion_consumo_<calidad>``).

El consentimiento es inalterable (migración 0006) y hay uno solo no revocado por persona y finalidad
(consentimiento_vigente_uq): si ya existe, AutorizacionVigente (409), aunque su revisión haya vencido.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.modules.care_circle.domain.avisos import Aviso
from app.modules.care_circle.domain.personas import (
    FINALIDAD_CONSUMO,
    AvisoMostrado,
    CalidadOtorgante,
    aviso_de,
    evidencia,
    puede_dar_de_alta,
    revision_vence_en,
    validar_otorgamiento,
)
from app.shared.puertos import Reloj


class RolSinPermisoAutorizacion(Exception):
    """El rol no da la autorización (pagador u observador). La API responde 404."""


class AutorizacionVigente(Exception):
    """La persona ya tiene una autorización no revocada para esa finalidad. La API responde 409."""


@dataclass(frozen=True)
class NuevaAutorizacion:
    """Lo que se escribe: el consentimiento y su fila de auditoría (consentimiento.otorgar)."""

    id: uuid.UUID
    grupo_id: uuid.UUID
    persona_id: uuid.UUID
    usuario_id: uuid.UUID
    calidad_otorgante: str
    finalidad: str
    version_politica: str
    evidencia: dict[str, Any]
    referencia_documento: str | None
    otorgado_en: datetime
    revision_vence_en: datetime | None
    request_id: str | None


class RepositorioAutorizaciones(Protocol):
    """Persistencia del consentimiento en la transacción del contexto de grupo.

    Implementación: RepositorioAutorizacionesSQL (infrastructure/repositorio_autorizaciones.py).
    """

    def hay_vigente(self, persona_id: uuid.UUID, finalidad: str) -> bool:
        """Si hay un consentimiento no revocado de la persona para la finalidad."""
        ...

    def guardar(self, autorizacion: NuevaAutorizacion) -> None:
        """Inserta el consentimiento y la auditoría. Lanza AutorizacionVigente si choca con
        consentimiento_vigente_uq (dos peticiones a la vez)."""
        ...


@dataclass(frozen=True)
class SolicitudAutorizacion:
    usuario_id: uuid.UUID
    grupo_id: uuid.UUID
    rol: str
    persona_id: uuid.UUID
    calidad_otorgante: CalidadOtorgante
    referencia_documento: str | None
    aviso: AvisoMostrado | None
    request_id: str | None = None


@dataclass(frozen=True)
class AutorizacionOtorgada:
    autorizacion: NuevaAutorizacion
    aviso: Aviso | None


def otorgar_autorizacion_consumo(
    solicitud: SolicitudAutorizacion, version_politica: str, reloj: Reloj, repositorio: RepositorioAutorizaciones
) -> AutorizacionOtorgada:
    """Registra el consentimiento para ``consumo``. Orden: rol (404), reglas de la calidad (422),
    autorización ya vigente (409). Nada se escribe si algo falla."""
    if not puede_dar_de_alta(solicitud.rol):
        raise RolSinPermisoAutorizacion()
    validar_otorgamiento(solicitud.calidad_otorgante, solicitud.referencia_documento, solicitud.aviso)
    if repositorio.hay_vigente(solicitud.persona_id, FINALIDAD_CONSUMO):
        raise AutorizacionVigente()

    otorgado_en = reloj.ahora()
    nueva = NuevaAutorizacion(
        id=uuid.uuid4(),
        grupo_id=solicitud.grupo_id,
        persona_id=solicitud.persona_id,
        usuario_id=solicitud.usuario_id,
        calidad_otorgante=solicitud.calidad_otorgante.value,
        finalidad=FINALIDAD_CONSUMO,
        version_politica=version_politica,
        evidencia=evidencia(solicitud.calidad_otorgante, version_politica, FINALIDAD_CONSUMO),
        referencia_documento=solicitud.referencia_documento or None,
        otorgado_en=otorgado_en,
        revision_vence_en=revision_vence_en(solicitud.calidad_otorgante, otorgado_en),
        request_id=solicitud.request_id,
    )
    repositorio.guardar(nueva)
    return AutorizacionOtorgada(autorizacion=nueva, aviso=aviso_de(solicitud.calidad_otorgante))
