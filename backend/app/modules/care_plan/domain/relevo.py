"""Reglas puras del acceso de relevo (MATU-18, RF-05). Contrato: docs/api/propuestos/relevo.openapi.yaml.

Sin I/O y sin reloj: el instante llega como argumento. Aquí viven el motivo enumerado, la vigencia
(24 horas por defecto, 30 días como máximo), el celular chileno normalizado, el nombre de pila y el
estado de un acceso. Generar el token y el PIN es un puerto (GeneradorCredencialesRelevo), y
calcular sus huellas vive en infrastructure/credenciales_relevo.py.

- Comparten admin y cuidador, los mismos que escriben la ficha (domain/ficha.puede_escribir).
- Listan admin, cuidador y pagador con puede_ver_plan (domain/ficha.puede_leer). El teléfono del
  relevo sale solo para admin y cuidador (decisión 31).
- Ningún error de este módulo lleva el valor recibido.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from app.modules.care_plan.domain.ficha import CAMPOS_FICHA, puede_escribir

VIGENCIA_POR_DEFECTO = timedelta(hours=24)
VIGENCIA_MAXIMA = timedelta(days=30)
INTENTOS_PIN_MAXIMOS = 5
LARGO_MAXIMO_NOMBRE_RELEVO = 60

ROLES_QUE_VEN_TELEFONO = frozenset({"admin", "cuidador"})

# 9 y ocho dígitos, con o sin +56 / 56 y con o sin espacios (contrato, SolicitudAcceso.telefono_relevo)
PATRON_CELULAR = r"^(\+?56 ?)?9( ?[0-9]){8}$"
_CELULAR = re.compile(PATRON_CELULAR)


class MotivoAcceso(StrEnum):
    """Enumerado sin texto libre (decisión 16): queda 3 años en la auditoría."""

    SALGO_UNAS_HORAS = "salgo_unas_horas"
    FIN_DE_SEMANA_FUERA = "fin_de_semana_fuera"
    TURNO_DE_NOCHE = "turno_de_noche"
    OTRO = "otro"


class EstadoAcceso(StrEnum):
    VIGENTE = "vigente"
    VENCIDO = "vencido"
    REVOCADO = "revocado"
    BLOQUEADO = "bloqueado"


class VigenciaInvalida(ValueError):
    """expira_en no es posterior a ahora o pasa de 30 días. ``tipo`` va en errores[] del 422."""

    def __init__(self, tipo: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.tipo = tipo
        self.mensaje = mensaje


def vigencia(ahora: datetime, expira_en: datetime | None) -> datetime:
    """Hasta cuándo vale el acceso: 24 horas por defecto; posterior a ahora y a lo más ahora + 30 días."""
    if expira_en is None:
        return ahora + VIGENCIA_POR_DEFECTO
    if expira_en <= ahora:
        raise VigenciaInvalida("vigencia_pasada", "El enlace debe vencer después de ahora")
    if expira_en > ahora + VIGENCIA_MAXIMA:
        raise VigenciaInvalida("vigencia_maxima", "El enlace puede durar como máximo 30 días")
    return expira_en


def normalizar_celular(valor: str) -> str | None:
    """El celular chileno como +569XXXXXXXX, o None si no es un celular (fijos incluidos)."""
    if not _CELULAR.match(valor):
        return None
    digitos = re.sub(r"\D", "", valor)
    return "+56" + digitos[-9:]


def nombre_pila(nombre: str) -> str:
    """La primera palabra del nombre: lo único de quien comparte que verá el relevo (decisión 28)."""
    partes = nombre.split()
    return partes[0] if partes else ""


def puede_ver_telefono(rol: str) -> bool:
    return rol in ROLES_QUE_VEN_TELEFONO


@dataclass(frozen=True)
class VidaAcceso:
    expira_en: datetime
    revocado_en: datetime | None
    pin_intentos_fallidos: int


def estado_acceso(acceso: VidaAcceso, ahora: datetime) -> EstadoAcceso:
    """En el orden del contrato: revocado, vencido (desde el instante exacto), bloqueado y vigente."""
    if acceso.revocado_en is not None:
        return EstadoAcceso.REVOCADO
    if acceso.expira_en <= ahora:
        return EstadoAcceso.VENCIDO
    if acceso.pin_intentos_fallidos >= INTENTOS_PIN_MAXIMOS:
        return EstadoAcceso.BLOQUEADO
    return EstadoAcceso.VIGENTE


# --- Abrir la ficha como relevo (MATU-19, RF-06) -----------------------------------------------------

# La sesión de relevo dura lo que ocurra primero: 12 horas o el vencimiento del acceso (decisión 14)
MAX_AGE_SESION = 43_200


def segundos_de_sesion(expira_en: datetime, ahora: datetime) -> int:
    """Max-Age de la cookie y TTL de la sesión: mín(43200, segundos enteros que le quedan al acceso).

    0 si el acceso ya venció: la sesión no se crea.
    """
    restantes = int((expira_en - ahora).total_seconds())
    return max(0, min(MAX_AGE_SESION, restantes))


@dataclass(frozen=True)
class IntentoFallido:
    """Cómo queda el acceso después de un PIN incorrecto."""

    intentos: int
    bloqueado: bool
    restantes: int


def intento_fallido(intentos_previos: int) -> IntentoFallido:
    """Suma un intento. El 5.º bloquea el acceso (contrato, canje paso 6). Nunca pasa de 5."""
    intentos = min(INTENTOS_PIN_MAXIMOS, intentos_previos + 1)
    return IntentoFallido(
        intentos=intentos, bloqueado=intentos >= INTENTOS_PIN_MAXIMOS, restantes=INTENTOS_PIN_MAXIMOS - intentos
    )


def tras_intento(intentos_actuales: int) -> IntentoFallido:
    """Cómo quedó el acceso según el contador que devolvió el incremento atómico de la base (C4).

    Se decide con el valor confirmado por la base, no con uno calculado desde una lectura previa:
    dos canjes simultáneos no se pisan.
    """
    intentos = min(INTENTOS_PIN_MAXIMOS, intentos_actuales)
    return IntentoFallido(
        intentos=intentos, bloqueado=intentos >= INTENTOS_PIN_MAXIMOS, restantes=INTENTOS_PIN_MAXIMOS - intentos
    )


def bloqueado(intentos: int) -> bool:
    return intentos >= INTENTOS_PIN_MAXIMOS


def campos_para_relevo(permitidos: tuple[str, ...], textos: dict[str, str]) -> dict[str, str | None]:
    """Solo los campos habilitados, en el orden de la ficha. Un campo vacío o nunca escrito es None
    ("Sin completar"). Un campo no habilitado no aparece aunque tenga texto."""
    return {
        c.value: (textos.get(c.value) or None) for c in CAMPOS_FICHA if c.value in permitidos
    }


# --- Revocar un acceso de relevo (MATU-20, RF-07) ----------------------------------------------------


def debe_revocar(acceso: VidaAcceso, ahora: datetime) -> bool:
    """Si revocar cambia el estado del acceso.

    Solo un acceso no revocado y no vencido se revoca. Uno ya revocado conserva su primer revocado_en
    (C15) y uno vencido queda vencido, sin revocado_en: los dos son un 204 sin cambios ni auditoría
    (C16). Un acceso bloqueado sí se revoca: el bloqueo no lo corta para siempre en la lista.
    """
    return acceso.revocado_en is None and acceso.expira_en > ahora


def puede_revocar(rol: str) -> bool:
    """Revocan admin y cuidador, los mismos que comparten. El pagador no, ni con puede_ver_plan."""
    return puede_escribir(rol)
