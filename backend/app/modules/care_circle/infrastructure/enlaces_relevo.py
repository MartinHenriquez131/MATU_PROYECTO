"""Registro de los enlaces de relevo que cada persona compartió (MATU-42, decisión 305).

care_circle no importa care_plan (tests/test_arquitectura.py). care_plan ofrece una fábrica que recibe la sesión de la
petición, el grupo y el registro de auditoría y devuelve su EnlacesDeRelevo; app.main la registra con
registrar_enlaces. Sin ella, sacar, salir y cambiar el rol fallan cerrado (500): nunca se retira a alguien dejando
vivos los enlaces que compartió.
"""

import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.modules.care_circle.application.ports_grupo import EnlacesDeRelevo
from app.shared.puertos import RegistroAuditoria

FabricaEnlaces = Callable[[Session, uuid.UUID, RegistroAuditoria], EnlacesDeRelevo]

_FABRICA: list[FabricaEnlaces] = []


class EnlacesNoDisponibles(RuntimeError):
    """Nadie registró los enlaces de relevo: la ruta responde 500 y no cambia nada."""


def registrar_enlaces(fabrica: FabricaEnlaces) -> None:
    """Registra (o reemplaza) la fábrica. Idempotente."""
    _FABRICA[:] = [fabrica]


def enlaces_de(sesion: Session, grupo_id: uuid.UUID, registro: RegistroAuditoria) -> EnlacesDeRelevo:
    if not _FABRICA:
        raise EnlacesNoDisponibles("no hay enlaces de relevo registrados")
    return _FABRICA[0](sesion, grupo_id, registro)
