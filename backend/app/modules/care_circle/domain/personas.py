"""Reglas puras del alta de la persona cuidada y de su consentimiento (MATU-07, RF-01, Ley 21.719).

Sin I/O y sin reloj del sistema: el instante del otorgamiento llega desde afuera (puerto Reloj) y
la persistencia es un puerto (application/ports.py).

- La persona cuidada no tiene diagnóstico (arquitectura, sección 11.3). nivel_apoyo es operacional.
- El consentimiento para plan_cuidado se otorga en una de tres calidades (sección 11.5), cada una
  con sus reglas: qué se exige, qué se prohíbe y qué queda como evidencia.
- La evidencia es mínima: identificadores y versiones. Sin IP, sin agente de usuario y sin el texto
  completo de lo que se mostró.
- Ningún mensaje de error de este módulo lleva el valor recibido.
"""

import calendar
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.modules.care_circle.domain.avisos import AVISO_CUIDADOR_DE_HECHO, Aviso

# --- La persona ---------------------------------------------------------------------------------

NIVELES_APOYO = ("autovalente_con_supervision", "apoyo_parcial", "apoyo_total")

LARGO_MAXIMO_NOMBRE = 120
LARGO_MAXIMO_NOMBRE_PILA = 60

# --- El consentimiento ----------------------------------------------------------------------------


class CalidadOtorgante(StrEnum):
    TITULAR = "titular"
    REPRESENTANTE_LEGAL = "representante_legal"
    CUIDADOR_DE_HECHO = "cuidador_de_hecho"


FINALIDAD_PLAN_CUIDADO = "plan_cuidado"

# Recordatorio anual del cuidador de hecho (arquitectura 11.5, política v0.9 sección 5)
MESES_REVISION_CUIDADOR_DE_HECHO = 12

# La referencia al documento que acredita la representación. Nunca el documento
LARGO_MAXIMO_REFERENCIA = 200

ESQUEMA_EVIDENCIA = 1
MODALIDAD_TITULAR = "registrada_por_usuario_en_presencia_del_titular"

# Roles que dan de alta. pagador y observador reciben 404, nunca 403
ROLES_QUE_DAN_DE_ALTA = frozenset({"admin", "cuidador"})


class OtorgamientoInvalido(ValueError):
    """La combinación de calidad, aviso y referencia no cumple las reglas de la calidad.

    ``campo`` es el campo del cuerpo que falló. El mensaje es fijo y nunca lleva el valor recibido.
    """

    def __init__(self, campo: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.campo = campo
        self.mensaje = mensaje


@dataclass(frozen=True)
class AvisoMostrado:
    """El aviso que el cliente declara haber mostrado: solo su identificador y su versión."""

    id: str
    version: str


def aviso_de(calidad: CalidadOtorgante) -> Aviso | None:
    """El aviso que se muestra al elegir esa calidad, o None si no lleva aviso."""
    return AVISO_CUIDADOR_DE_HECHO if calidad is CalidadOtorgante.CUIDADOR_DE_HECHO else None


def validar_otorgamiento(
    calidad: CalidadOtorgante, referencia_documento: str | None, aviso: AvisoMostrado | None
) -> None:
    """Aplica las reglas cruzadas de cada calidad. Lanza OtorgamientoInvalido con el primer campo que falla.

    | calidad             | aviso                                  | referencia_documento |
    |---------------------|----------------------------------------|----------------------|
    | titular             | prohibido                              | prohibida            |
    | representante_legal | prohibido                              | obligatoria          |
    | cuidador_de_hecho   | obligatorio, y debe ser el vigente     | prohibida            |

    La referencia llega ya sin espacios en los extremos. Vacía cuenta como ausente.
    """
    tiene_referencia = bool(referencia_documento)

    if calidad is CalidadOtorgante.REPRESENTANTE_LEGAL:
        if not tiene_referencia:
            raise OtorgamientoInvalido(
                "referencia_documento", "un representante legal debe indicar la referencia al documento que lo acredita"
            )
    elif tiene_referencia:
        raise OtorgamientoInvalido(
            "referencia_documento", "la referencia al documento solo corresponde a un representante legal"
        )

    vigente = aviso_de(calidad)
    if vigente is None:
        if aviso is not None:
            raise OtorgamientoInvalido("aviso", "esta calidad no lleva aviso")
        return
    if aviso is None:
        raise OtorgamientoInvalido("aviso", "falta el aviso que se mostró al elegir esta calidad")
    if (aviso.id, aviso.version) != (vigente.id, vigente.version):
        raise OtorgamientoInvalido("aviso", "el aviso no es el vigente: vuelve a mostrarlo")


def evidencia(calidad: CalidadOtorgante, version_politica: str) -> dict[str, Any]:
    """La evidencia mínima del consentimiento (consentimiento.evidencia).

    Lo demás ya vive en columnas: usuario_id, calidad_otorgante, finalidad, version_politica,
    otorgado_en, revision_vence_en y referencia_documento.
    """
    datos: dict[str, Any] = {
        "esquema": ESQUEMA_EVIDENCIA,
        "declaracion": {"id": f"declaracion_{calidad.value}", "version": version_politica},
    }
    aviso = aviso_de(calidad)
    if aviso is not None:
        datos["aviso"] = {"id": aviso.id, "version": aviso.version, "sha256": aviso.sha256}
    if calidad is CalidadOtorgante.TITULAR:
        datos["modalidad"] = MODALIDAD_TITULAR
    return datos


def sumar_meses(instante: datetime, meses: int) -> datetime:
    """El mismo día y la misma hora, ``meses`` meses de calendario después.

    Si ese día no existe en el mes de destino (29 de febrero en un año no bisiesto, o el 31 en un
    mes de 30 días), se usa el último día de ese mes.
    """
    indice = instante.month - 1 + meses
    anio, mes = instante.year + indice // 12, indice % 12 + 1
    dia = min(instante.day, calendar.monthrange(anio, mes)[1])
    return instante.replace(year=anio, month=mes, day=dia)


def revision_vence_en(calidad: CalidadOtorgante, otorgado_en: datetime) -> datetime | None:
    """Cuándo vence la revisión: 12 meses después para el cuidador de hecho, ninguna para las demás."""
    if calidad is CalidadOtorgante.CUIDADOR_DE_HECHO:
        return sumar_meses(otorgado_en, MESES_REVISION_CUIDADOR_DE_HECHO)
    return None


def puede_dar_de_alta(rol: str) -> bool:
    return rol in ROLES_QUE_DAN_DE_ALTA


# --- Qué ve cada rol (arquitectura 11.2) -----------------------------------------------------------


class VistaPersona(StrEnum):
    """Proyección de la persona cuidada según el rol: un DTO distinto, no campos ocultos en la interfaz."""

    COMPLETA = "completa"  # admin y cuidador: todo, incluido el consentimiento vigente
    NOMBRE_Y_DIRECCION = "nombre_y_direccion"  # pagador
    NOMBRE = "nombre"  # observador


_VISTA_POR_ROL = {
    "admin": VistaPersona.COMPLETA,
    "cuidador": VistaPersona.COMPLETA,
    "pagador": VistaPersona.NOMBRE_Y_DIRECCION,
    "observador": VistaPersona.NOMBRE,
}


def vista_para_rol(rol: str) -> VistaPersona:
    """La vista del rol. Un rol desconocido recibe la más restringida."""
    return _VISTA_POR_ROL.get(rol, VistaPersona.NOMBRE)
