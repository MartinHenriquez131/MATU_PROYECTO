"""Reglas puras del retiro de una autorización y del estado que ve la familia (MATU-44, decisiones 123 a 135).

Sin I/O y sin reloj del sistema: el instante llega como argumento (puerto Reloj).

- Retiran admin y cuidador, sin importar quién dio la autorización (D1). Los demás roles: 404.
- Una autorización ya retirada no se retira otra vez (409, decisión 125).
- Con la revisión anual vencida también se retira (condición 3 del analista). Decidido por Jorge el 06-11 (P6):
  RETIRO_CON_REVISION_VENCIDA es la regla que lo dice.
- Lo guardado de una finalidad se borra 90 días después de su última revocación (decisiones 70 y 129).
- El estado de cada autorización (decisión 127) se decide aquí: la pantalla no suma 90 días.
- MATU-72 (decisión 154): una revocación con motivo borrado borró lo guardado en ese instante, sin esperar 90
  días. Lo borrado nunca vuelve.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from app.modules.care_circle.domain.personas import (
    FINALIDAD_CONSUMO,
    FINALIDAD_DESPACHO,
    FINALIDAD_PLAN_CUIDADO,
    AutorizacionGuardada,
    EstadoAutorizacion,
    estado_autorizacion,
)

# Las finalidades que se retiran y que muestra la vista, en este orden (decisión 127). Son las de las capas 1 y 2
FINALIDADES_RETIRABLES = (FINALIDAD_PLAN_CUIDADO, FINALIDAD_CONSUMO)
# MATU-61 (C2, decisión 217): la autorización de pedidos existe solo con la capa 3 encendida, después de las dos
FINALIDADES_CAPA_3 = (FINALIDAD_DESPACHO,)


def finalidades_retirables(capa3: bool) -> tuple[str, ...]:
    """Las finalidades activas, en el orden de la vista: con la capa 3, también despacho (tres ítems); sin ella,
    las dos de siempre (C2)."""
    return FINALIDADES_RETIRABLES + FINALIDADES_CAPA_3 if capa3 else FINALIDADES_RETIRABLES

ROLES_QUE_RETIRAN = frozenset({"admin", "cuidador"})

# Lo guardado se conserva 90 días después del retiro (decisiones 70 y 129)
DIAS_HASTA_BORRAR = 90
PLAZO_BORRADO = timedelta(days=DIAS_HASTA_BORRAR)

# Decidido por Jorge el 06-11 (P6, C6): se puede retirar con la revisión anual vencida, como pide el analista
RETIRO_CON_REVISION_VENCIDA = True

MOTIVO_RETIRO = "retiro"
MOTIVO_RENOVACION = "renovacion"
# MATU-72 (D2): la persona pidió borrar sus datos. Lo guardado se borra en el acto
MOTIVO_BORRADO = "borrado"


class YaRetirada(Exception):
    """La autorización de esa finalidad ya estaba retirada. La API responde 409 ya-retirada."""


class RetiroNoPermitido(Exception):
    """La regla P6 no deja retirar con la revisión vencida. Hoy no ocurre (RETIRO_CON_REVISION_VENCIDA)."""


def puede_retirar(rol: str) -> bool:
    return rol in ROLES_QUE_RETIRAN


def finalidad_de(valor: str, finalidades: tuple[str, ...] = FINALIDADES_RETIRABLES) -> str | None:
    """La finalidad del path, o None si no es una de las activas (la API responde 404)."""
    return valor if valor in finalidades else None


@dataclass(frozen=True)
class AutorizacionRegistrada:
    """Una fila de consentimiento de la persona, sin la referencia, la evidencia ni quién la dio."""

    id: uuid.UUID
    finalidad: str
    calidad_otorgante: str
    otorgado_en: datetime
    revision_vence_en: datetime | None
    revocado_en: datetime | None
    # retiro, renovacion o borrado (migración 0016 y 0018). None si no está revocada
    revocacion_motivo: str | None = None
    # MATU-42 (D-42-9 a, decisión 311): si quien la registró sigue como miembro activo del grupo. Nunca quién es
    otorgante_activo: bool = True


def autorizo_alguien_que_ya_no_esta(autorizacion: AutorizacionRegistrada | None) -> bool:
    """True si la autorización no está retirada y quien la registró ya no es miembro activo (P10). Sigue vigente."""
    return autorizacion is not None and autorizacion.revocado_en is None and not autorizacion.otorgante_activo


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


def fue_borrado(revocada: AutorizacionRegistrada) -> bool:
    """Si la revocación fue un borrado a pedido (MATU-72): lo guardado se borró en ese instante."""
    return revocada.revocado_en is not None and revocada.revocacion_motivo == MOTIVO_BORRADO


def lo_guardado_ya_no_esta(revocada: AutorizacionRegistrada, ahora: datetime) -> bool:
    """Si lo guardado de esa revocación ya se borró según ``ahora``: con un borrado, siempre; con un retiro,
    desde el día 90 (decisión 128 y MATU-72, decisión 154). Sin revocación, False."""
    return fue_borrado(revocada) or plazo_cumplido(revocada.revocado_en, ahora)


def _cuando_se_borra(revocada: AutorizacionRegistrada) -> datetime:
    assert revocada.revocado_en is not None
    return revocada.revocado_en if fue_borrado(revocada) else borrado_desde(revocada.revocado_en)


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
    revocada, el último retiro (motivo retiro o borrado) anterior a ella, o None.

    - Sin autorización: sin_autorizar.
    - Revocada: retirada antes de los 90 días y borrada desde el día 90 según ``ahora``, aunque la tarea no
      haya corrido (lo borrado nunca vuelve: decisión 128). ``borrado_en`` = revocado_en + 90 días. Con motivo
      borrado (MATU-72), borrada desde ese instante y ``borrado_en`` = revocado_en.
    - No revocada: vigente o revision_vencida (decisión 33). Si se otorgó 90 días o más después del retiro
      anterior, lo de antes se borró: ``borrada`` y ``borrado_en`` lo dicen, y la ficha empezó en blanco.
      Si lo anterior fue un borrado, también, sin importar los días.
    """
    if autorizacion is None:
        return EstadoDeAutorizacion(finalidad, EstadoVista.SIN_AUTORIZAR, None, None, False)
    if autorizacion.revocado_en is not None:
        borrada = lo_guardado_ya_no_esta(autorizacion, ahora)
        estado = EstadoVista.BORRADA if borrada else EstadoVista.RETIRADA
        return EstadoDeAutorizacion(finalidad, estado, autorizacion, _cuando_se_borra(autorizacion), borrada)
    guardada = AutorizacionGuardada(autorizacion.calidad_otorgante, autorizacion.revision_vence_en)
    vigencia = estado_autorizacion(guardada, ahora)
    estado = EstadoVista.REVISION_VENCIDA if vigencia is EstadoAutorizacion.REVISION_VENCIDA else EstadoVista.VIGENTE
    if retiro_anterior is not None and lo_guardado_ya_no_esta(retiro_anterior, autorizacion.otorgado_en):
        return EstadoDeAutorizacion(finalidad, estado, autorizacion, _cuando_se_borra(retiro_anterior), True)
    return EstadoDeAutorizacion(finalidad, estado, autorizacion, None, False)
