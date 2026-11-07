"""Reglas puras del retiro de una autorización y del estado que ve la familia (MATU-44, decisiones 123 a 135).

Sin I/O y sin reloj del sistema: el instante llega como argumento (puerto Reloj).

- Retiran admin y cuidador, sin importar quién dio la autorización (D1). Los demás roles: 404.
- Una autorización ya retirada no se retira otra vez (409, decisión 125).
- Con la revisión anual vencida también se retira (condición 3 del analista). Decidido por Jorge el 06-11 (P6):
  RETIRO_CON_REVISION_VENCIDA es la regla que lo dice.
- Lo guardado de una finalidad se borra 90 días después de su última revocación (decisiones 70 y 129).
- El estado de cada autorización (decisión 127) se decide aquí: la pantalla no suma 90 días.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from app.modules.care_circle.domain.personas import (
    FINALIDAD_CONSUMO,
    FINALIDAD_PLAN_CUIDADO,
    AutorizacionGuardada,
    EstadoAutorizacion,
    estado_autorizacion,
)

# Las finalidades que se retiran y que muestra la vista, en este orden (decisión 127)
FINALIDADES_RETIRABLES = (FINALIDAD_PLAN_CUIDADO, FINALIDAD_CONSUMO)

ROLES_QUE_RETIRAN = frozenset({"admin", "cuidador"})

# Lo guardado se conserva 90 días después del retiro (decisiones 70 y 129)
DIAS_HASTA_BORRAR = 90
PLAZO_BORRADO = timedelta(days=DIAS_HASTA_BORRAR)

# Decidido por Jorge el 06-11 (P6, C6): se puede retirar con la revisión anual vencida, como pide el analista
RETIRO_CON_REVISION_VENCIDA = True

MOTIVO_RETIRO = "retiro"
MOTIVO_RENOVACION = "renovacion"


class YaRetirada(Exception):
    """La autorización de esa finalidad ya estaba retirada. La API responde 409 ya-retirada."""


class RetiroNoPermitido(Exception):
    """La regla P6 no deja retirar con la revisión vencida. Hoy no ocurre (RETIRO_CON_REVISION_VENCIDA)."""


def puede_retirar(rol: str) -> bool:
    return rol in ROLES_QUE_RETIRAN


def finalidad_de(valor: str) -> str | None:
    """La finalidad del path, o None si no es una de las dos (la API responde 404)."""
    return valor if valor in FINALIDADES_RETIRABLES else None


@dataclass(frozen=True)
class AutorizacionRegistrada:
    """Una fila de consentimiento de la persona, sin la referencia, la evidencia ni quién la dio."""

    id: uuid.UUID
    finalidad: str
    calidad_otorgante: str
    otorgado_en: datetime
    revision_vence_en: datetime | None
    revocado_en: datetime | None


def exigir_retirable(actual: AutorizacionRegistrada, ahora: datetime) -> None:
    """Lanza YaRetirada si ya está revocada, y RetiroNoPermitido si la regla P6 lo impide."""
    if actual.revocado_en is not None:
        raise YaRetirada()
    vencida = (
        estado_autorizacion(AutorizacionGuardada(actual.calidad_otorgante, actual.revision_vence_en), ahora)
        is EstadoAutorizacion.REVISION_VENCIDA
    )
    if vencida and not RETIRO_CON_REVISION_VENCIDA:
        raise RetiroNoPermitido()


def borrado_desde(revocado_en: datetime) -> datetime:
    """Desde cuándo se borra lo guardado de una autorización revocada en ``revocado_en``."""
    return revocado_en + PLAZO_BORRADO


def plazo_cumplido(ultima_revocacion: datetime | None, ahora: datetime) -> bool:
    """Si ya pasaron los 90 días desde la última revocación. Sin revocación, False."""
    return ultima_revocacion is not None and borrado_desde(ultima_revocacion) <= ahora


class EstadoVista(StrEnum):
    VIGENTE = "vigente"
    REVISION_VENCIDA = "revision_vencida"
    RETIRADA = "retirada"
    BORRADA = "borrada"
    SIN_AUTORIZAR = "sin_autorizar"


@dataclass(frozen=True)
class EstadoDeAutorizacion:
    """Lo que dice la vista de una finalidad (decisión 127). ``autorizacion`` es None si nunca hubo una."""

    finalidad: str
    estado: EstadoVista
    autorizacion: AutorizacionRegistrada | None
    borrado_en: datetime | None
    borrada: bool


def estado_de(
    finalidad: str,
    autorizacion: AutorizacionRegistrada | None,
    retiro_anterior: AutorizacionRegistrada | None,
    ahora: datetime,
) -> EstadoDeAutorizacion:
    """El estado de una finalidad, solo con los consentimientos y el Reloj (decisión 127).

    ``autorizacion`` es la no revocada o, si no hay, la última revocada. ``retiro_anterior`` es, para una no
    revocada, el último retiro (motivo retiro) anterior a ella, o None.

    - Sin autorización: sin_autorizar.
    - Revocada: retirada antes de los 90 días y borrada desde el día 90 según ``ahora``, aunque la tarea no
      haya corrido (lo borrado nunca vuelve: decisión 128). ``borrado_en`` = revocado_en + 90 días.
    - No revocada: vigente o revision_vencida (decisión 33). Si se otorgó 90 días o más después del retiro
      anterior, lo de antes se borró: ``borrada`` y ``borrado_en`` lo dicen, y la ficha empezó en blanco.
    """
    if autorizacion is None:
        return EstadoDeAutorizacion(finalidad, EstadoVista.SIN_AUTORIZAR, None, None, False)
    if autorizacion.revocado_en is not None:
        borrada = plazo_cumplido(autorizacion.revocado_en, ahora)
        estado = EstadoVista.BORRADA if borrada else EstadoVista.RETIRADA
        return EstadoDeAutorizacion(finalidad, estado, autorizacion, borrado_desde(autorizacion.revocado_en), borrada)
    guardada = AutorizacionGuardada(autorizacion.calidad_otorgante, autorizacion.revision_vence_en)
    vigencia = estado_autorizacion(guardada, ahora)
    estado = EstadoVista.REVISION_VENCIDA if vigencia is EstadoAutorizacion.REVISION_VENCIDA else EstadoVista.VIGENTE
    anterior = None if retiro_anterior is None else retiro_anterior.revocado_en
    if anterior is not None and plazo_cumplido(anterior, autorizacion.otorgado_en):
        return EstadoDeAutorizacion(finalidad, estado, autorizacion, borrado_desde(anterior), True)
    return EstadoDeAutorizacion(finalidad, estado, autorizacion, None, False)
