"""Registro de los efectos del retiro por finalidad (MATU-44, decisión 124).

care_circle no importa care_plan ni consumption (tests/test_arquitectura.py). Cada uno ofrece una fábrica
que recibe la sesión de la petición, el grupo y el registro de auditoría y devuelve su EfectoDelRetiro.
app.main, que arma la aplicación, las registra con registrar_efecto. Sin el efecto de una finalidad, el
retiro de esa finalidad no se hace (EfectoNoDisponible, 500): falla cerrado.
"""

import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.modules.care_circle.application.retiro import EfectoDelRetiro
from app.shared.puertos import RegistroAuditoria

FabricaEfecto = Callable[[Session, uuid.UUID, RegistroAuditoria], EfectoDelRetiro]

_FABRICAS: dict[str, FabricaEfecto] = {}


def registrar_efecto(finalidad: str, fabrica: FabricaEfecto) -> None:
    """Registra (o reemplaza) la fábrica del efecto de ``finalidad``. Idempotente."""
    _FABRICAS[finalidad] = fabrica


def efectos_de(sesion: Session, grupo_id: uuid.UUID, registro: RegistroAuditoria) -> dict[str, EfectoDelRetiro]:
    """Los efectos registrados, construidos para esta transacción."""
    return {finalidad: fabrica(sesion, grupo_id, registro) for finalidad, fabrica in _FABRICAS.items()}


def finalidades_registradas() -> frozenset[str]:
    return frozenset(_FABRICAS)
