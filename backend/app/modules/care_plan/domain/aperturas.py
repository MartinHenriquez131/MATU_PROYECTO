"""Reglas puras de las aperturas de la ficha por un relevo (MATU-45, RF-08).

Contrato: GET /v1/personas-cuidadas/{persona_id}/plan/aperturas (relevo.openapi.yaml). Cada fila de
auditoria que dejó un relevo con una de cuatro acciones se muestra a la familia con un tipo enumerado.
relevo.canje no se muestra: el contrato no lo enumera (la apertura de la ficha es relevo.abrir).

Sin I/O: aquí solo vive la correspondencia entre la acción auditada y el tipo que ve la familia, y
(MATU-50) qué secciones complementarias se mostraron en una apertura, leídas del detalle de relevo.abrir.
"""

from collections.abc import Iterable
from enum import StrEnum

from app.modules.care_plan.domain.secciones import SECCIONES_COMPLEMENTARIAS, SeccionComplementaria
from app.shared.auditoria import AccionAuditoria


class TipoApertura(StrEnum):
    PRESENTACION = "presentacion"
    APERTURA = "apertura"
    PIN_INCORRECTO = "pin_incorrecto"
    BLOQUEO = "bloqueo"


_TIPO_DE_ACCION: dict[AccionAuditoria, TipoApertura] = {
    AccionAuditoria.RELEVO_PRESENTAR: TipoApertura.PRESENTACION,
    AccionAuditoria.RELEVO_ABRIR: TipoApertura.APERTURA,
    AccionAuditoria.RELEVO_PIN_INCORRECTO: TipoApertura.PIN_INCORRECTO,
    AccionAuditoria.RELEVO_BLOQUEO: TipoApertura.BLOQUEO,
}

# Las acciones que se leen de auditoria, en un orden fijo (las mismas de la política de 0010)
ACCIONES_DE_APERTURA: tuple[str, ...] = tuple(a.value for a in _TIPO_DE_ACCION)


def tipo_de_accion(accion: str) -> TipoApertura | None:
    """El tipo que ve la familia, o None si la acción no se lista (otra acción o desconocida)."""
    try:
        return _TIPO_DE_ACCION.get(AccionAuditoria(accion))
    except ValueError:
        return None


def secciones_de_apertura(
    tipo: TipoApertura, guardadas: Iterable[str]
) -> tuple[SeccionComplementaria, ...] | None:
    """Las secciones que se mostraron en una apertura, en el orden de ADR-028, o None si el ítem no es una
    apertura (los demás tipos no traen ``secciones``). Una apertura anterior a MATU-50 no guardó ninguna:
    viene vacía. Un valor desconocido en el detalle se ignora (el CHECK de la base no lo deja entrar)."""
    if tipo is not TipoApertura.APERTURA:
        return None
    guardadas = set(guardadas)
    return tuple(s for s in SECCIONES_COMPLEMENTARIAS if s.value in guardadas)
