"""Reglas puras de «Dónde entraste»: los últimos ingresos de la propia cuenta (MATU-55, RF-37; decisiones 254 a 256).

Sin I/O ni reloj del sistema: el instante llega desde afuera.

- Qué entra: una lista cerrada de acciones de la auditoría, cada una con su propio nombre de la API (TipoEventoCuenta).
  El nombre de la acción nunca sale. Los fallidos, el pedido del código del celular y toda fila con grupo no entran.
- Ventana y tope: los últimos 90 días, hasta 20, del más reciente al más antiguo. Se piden 21 para saber si hay más.
- Forma: solo el tipo, el instante y el dispositivo (nombre, clase y si es el actual) o None. Nunca un id, la IP, el
  request_id ni el detalle.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from app.modules.iam.domain.dispositivo import ClaseDispositivo, clase_dispositivo
from app.shared.auditoria import AccionAuditoria

VENTANA_INGRESOS = timedelta(days=90)
TOPE_INGRESOS = 20


class TipoEventoCuenta(StrEnum):
    """El tipo de un evento de la cuenta, tal como sale en la API (TipoEventoCuenta del contrato)."""

    ENTRASTE = "entraste"
    SALISTE = "saliste"
    CERRASTE_EN_DISPOSITIVO = "cerraste_en_dispositivo"
    SALIDA_POR_SEGURIDAD = "salida_por_seguridad"
    CONTRASENA_CAMBIADA = "contrasena_cambiada"  # pragma: allowlist secret
    CELULAR_CONFIRMADO = "celular_confirmado"
    CODIGO_RECUPERACION_PEDIDO = "codigo_recuperacion_pedido"
    AVISOS_CAMBIADOS = "avisos_cambiados"
    AVISOS_ACTIVADOS = "avisos_activados"
    AVISOS_DESACTIVADOS = "avisos_desactivados"
    # MATU-54 (C-2 y C-3, decisión 376): «Pediste una copia de tus datos». Solo la de la cuenta: la de una persona va
    # con su grupo y nunca entra aquí
    PEDISTE_UNA_COPIA = "pediste_una_copia"


# La lista cerrada (decisión 254). Una acción que no está aquí no se muestra nunca
TIPO_POR_ACCION: dict[AccionAuditoria, TipoEventoCuenta] = {
    AccionAuditoria.SESION_INICIAR: TipoEventoCuenta.ENTRASTE,
    AccionAuditoria.SESION_CERRAR: TipoEventoCuenta.SALISTE,
    AccionAuditoria.DISPOSITIVO_SACAR: TipoEventoCuenta.CERRASTE_EN_DISPOSITIVO,
    AccionAuditoria.SESION_REUTILIZACION_DETECTADA: TipoEventoCuenta.SALIDA_POR_SEGURIDAD,
    AccionAuditoria.CUENTA_CONTRASENA_CAMBIAR: TipoEventoCuenta.CONTRASENA_CAMBIADA,
    AccionAuditoria.CUENTA_CELULAR_VERIFICAR: TipoEventoCuenta.CELULAR_CONFIRMADO,
    AccionAuditoria.CUENTA_RECUPERAR_SOLICITAR: TipoEventoCuenta.CODIGO_RECUPERACION_PEDIDO,
    AccionAuditoria.AVISOS_PREFERENCIA: TipoEventoCuenta.AVISOS_CAMBIADOS,
    AccionAuditoria.DISPOSITIVO_PUSH_REGISTRAR: TipoEventoCuenta.AVISOS_ACTIVADOS,
    AccionAuditoria.DISPOSITIVO_PUSH_BORRAR: TipoEventoCuenta.AVISOS_DESACTIVADOS,
    AccionAuditoria.CUENTA_DATOS_DESCARGAR: TipoEventoCuenta.PEDISTE_UNA_COPIA,
}

# Las que nunca entran, aunque sean de la cuenta (D1): los fallidos y el pedido del código del celular (Q5)
ACCIONES_EXCLUIDAS = frozenset(
    {
        AccionAuditoria.SESION_INICIO_FALLIDO,
        AccionAuditoria.CUENTA_RECUPERAR_VERIFICAR_FALLIDO,
        AccionAuditoria.CUENTA_CELULAR_VERIFICAR_FALLIDO,
        AccionAuditoria.CUENTA_CELULAR_SOLICITAR,
    }
)

# Los tipos de la cuenta, que no son de un dispositivo: su dispositivo es siempre None
TIPOS_SIN_DISPOSITIVO = frozenset(
    {
        TipoEventoCuenta.CONTRASENA_CAMBIADA,
        TipoEventoCuenta.CELULAR_CONFIRMADO,
        TipoEventoCuenta.CODIGO_RECUPERACION_PEDIDO,
        TipoEventoCuenta.AVISOS_CAMBIADOS,
        TipoEventoCuenta.PEDISTE_UNA_COPIA,
    }
)


def inicio_ventana(ahora: datetime) -> datetime:
    """El instante desde el que se muestran los eventos: ahora menos 90 días (incluido)."""
    if ahora.tzinfo is None or ahora.utcoffset() is None:
        raise ValueError("El instante debe tener zona horaria")
    return ahora - VENTANA_INGRESOS


@dataclass(frozen=True)
class FilaIngreso:
    """Una fila de la auditoría de la cuenta, como la lee el repositorio: la acción, el instante y, si la fila es de un
    dispositivo que todavía existe, su id y su nombre."""

    accion: str
    ocurrido_en: datetime
    dispositivo_id: uuid.UUID | None
    dispositivo_nombre: str | None

    def __repr__(self) -> str:
        return f"FilaIngreso(accion={self.accion!r})"


@dataclass(frozen=True)
class DispositivoDelEvento:
    nombre: str
    clase: ClaseDispositivo
    actual: bool

    def __repr__(self) -> str:
        # El nombre del dispositivo no va a los logs (decisión 270)
        return f"DispositivoDelEvento(clase={self.clase.value!r}, actual={self.actual})"


@dataclass(frozen=True)
class EventoCuenta:
    tipo: TipoEventoCuenta
    ocurrido_en: datetime
    dispositivo: DispositivoDelEvento | None


@dataclass(frozen=True)
class UltimosIngresos:
    eventos: tuple[EventoCuenta, ...]
    hay_mas: bool

    def __repr__(self) -> str:
        return f"UltimosIngresos(eventos={len(self.eventos)}, hay_mas={self.hay_mas})"


def armar_ingresos(
    filas: Sequence[FilaIngreso], *, dispositivo_actual: uuid.UUID | None, tope: int = TOPE_INGRESOS
) -> UltimosIngresos:
    """Los eventos de las filas, ya ordenadas del más reciente al más antiguo.

    Descarta las acciones que no están en la lista cerrada (por si el repositorio trae alguna), recorta a tope y dice si
    había más. actual compara con el claim did: sin did, siempre False. El instante sale en UTC."""
    eventos: list[EventoCuenta] = []
    for fila in filas:
        try:
            tipo = TIPO_POR_ACCION[AccionAuditoria(fila.accion)]
        except (ValueError, KeyError):
            continue
        dispositivo = None
        if tipo not in TIPOS_SIN_DISPOSITIVO and fila.dispositivo_id is not None and fila.dispositivo_nombre:
            dispositivo = DispositivoDelEvento(
                nombre=fila.dispositivo_nombre,
                clase=clase_dispositivo(fila.dispositivo_nombre),
                actual=dispositivo_actual is not None and fila.dispositivo_id == dispositivo_actual,
            )
        eventos.append(EventoCuenta(tipo=tipo, ocurrido_en=fila.ocurrido_en.astimezone(UTC), dispositivo=dispositivo))
    return UltimosIngresos(eventos=tuple(eventos[:tope]), hay_mas=len(eventos) > tope)
