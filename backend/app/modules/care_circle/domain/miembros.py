"""Reglas puras de quiénes forman el grupo (MATU-42, RF-38, decisiones 302 a 307).

Sin I/O ni reloj: la persistencia es un puerto (application/ports.py) y el instante llega por argumento.
"""

from dataclasses import dataclass
from enum import StrEnum

ROL_ADMIN = "admin"
ROL_CUIDADOR = "cuidador"
ROL_PAGADOR = "pagador"
ROL_OBSERVADOR = "observador"
ROLES = (ROL_ADMIN, ROL_CUIDADOR, ROL_PAGADOR, ROL_OBSERVADOR)

# Quienes comparten la ficha con un relevo (app_escribe_plan, 0013). Dejar de estar aquí corta sus enlaces (305)
ROLES_QUE_COMPARTEN = frozenset({ROL_ADMIN, ROL_CUIDADOR})


class FaltaVersion(Exception):
    """PATCH sin If-Match, vacío o con *: 428 falta-version (decisión 303)."""


class PermisoSoloPagador(ValueError):
    """puede_ver_plan: true con un rol que no queda en pagador: 422 permiso_solo_pagador. Sin valores."""

    def __init__(self) -> None:
        super().__init__("puede_ver_plan solo se da al rol pagador")


class NoPuedeSalir(StrEnum):
    """Por qué alguien no puede dejar el grupo (C12, P14). Es el type del 409."""

    ULTIMO_ADMIN = "ultimo-admin"
    UNICA_PERSONA = "unica-persona"


def etag(version: int) -> str:
    """El etag de la membresía: "v<version>" (decisión 303)."""
    return f'"v{version}"'


def version_de_if_match(valor: str | None) -> int | None:
    """La versión que trae If-Match. FaltaVersion si falta, está vacío o es *. None si no tiene la forma "v<n>":
    no coincide con ninguna versión y responde 412."""
    if valor is None or not valor.strip() or valor.strip() == "*":
        raise FaltaVersion()
    limpio = valor.strip()
    if limpio.startswith("W/"):
        limpio = limpio[2:]
    if len(limpio) < 4 or not (limpio.startswith('"v') and limpio.endswith('"')) or not limpio[2:-1].isdigit():
        return None
    return int(limpio[2:-1])


@dataclass(frozen=True)
class RolYPermiso:
    rol: str
    puede_ver_plan: bool


def aplicar_cambio(actual: RolYPermiso, rol: str | None, puede_ver_plan: bool | None) -> RolYPermiso:
    """Cómo queda la membresía con el cambio pedido (D-42-5, C18).

    - El rol nuevo, o el mismo si no se pide.
    - puede_ver_plan: true solo si el rol que queda es pagador (PermisoSoloPagador si no).
    - Al dejar de ser pagador vuelve a false. Al pasar a pagador queda en false salvo que se pida true. Si sigue en
      pagador y no se pide, no cambia.
    """
    rol_final = rol if rol is not None else actual.rol
    if rol_final not in ROLES:
        raise ValueError("rol desconocido")
    if puede_ver_plan is True and rol_final != ROL_PAGADOR:
        raise PermisoSoloPagador()
    if rol_final != ROL_PAGADOR:
        permiso = False
    elif puede_ver_plan is not None:
        permiso = puede_ver_plan
    else:
        permiso = actual.puede_ver_plan if actual.rol == ROL_PAGADOR else False
    return RolYPermiso(rol=rol_final, puede_ver_plan=permiso)


def deja_de_compartir(antes: str, despues: str | None) -> bool:
    """Si deja de poder compartir la ficha: de admin o cuidador a pagador, observador o fuera del grupo (None).
    Entonces se cortan los enlaces de relevo que compartió (C13, C19, decisión 305)."""
    return antes in ROLES_QUE_COMPARTEN and (despues is None or despues not in ROLES_QUE_COMPARTEN)


def deja_de_ser_admin(antes: str, despues: str | None) -> bool:
    """Si deja de administrar: entonces se anulan sus invitaciones sin usar (decisión 307)."""
    return antes == ROL_ADMIN and despues != ROL_ADMIN


def deja_sin_admin(antes: str, despues: str | None, admins_activos: int) -> bool:
    """Si el cambio deja al grupo sin nadie que lo administre (C11). despues None es salir o ser sacado."""
    return deja_de_ser_admin(antes, despues) and admins_activos <= 1


def no_puede_salir(rol: str, admins_activos: int, miembros_activos: int) -> NoPuedeSalir | None:
    """Por qué no puede salir (o ser sacado), o None si puede. La única persona del grupo primero (P14)."""
    if miembros_activos <= 1:
        return NoPuedeSalir.UNICA_PERSONA
    if deja_sin_admin(rol, None, admins_activos):
        return NoPuedeSalir.ULTIMO_ADMIN
    return None


def permiso_visible(rol: str, puede_ver_plan: bool) -> bool | None:
    """puede_ver_plan de la lista: solo del pagador; null para los demás, que la ven siempre o nunca (302)."""
    return puede_ver_plan if rol == ROL_PAGADOR else None


def ve_enlaces(quien_mira_es_admin: bool, eres_tu: bool) -> bool:
    """enlaces_vigentes: quien administra en todas las filas y cada persona en la propia (P5, P13)."""
    return quien_mira_es_admin or eres_tu


def sin_cambios(actual: RolYPermiso, nuevo: RolYPermiso) -> bool:
    return actual == nuevo
