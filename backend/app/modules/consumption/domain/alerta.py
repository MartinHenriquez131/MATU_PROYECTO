"""Reglas puras de la predicción de quiebre y de las alertas (MATU-37, RF-12, ADR-012).

Sin I/O y sin reloj del sistema: "hoy" llega calculado con el puerto Reloj (``hoy_en_chile``).

- La fecha de quiebre es la de MATU-36 (``perfil.fecha_quiebre``), entera:
  ``stock_medido_en + piso(stock_unidades * tasa_dias / tasa_unidades)`` días. No se duplica aquí.
- Un insumo está en su ventana de aviso cuando ``dias_restantes <= dias_aviso`` (incluidos los ya
  pasados, con días negativos).
- Solo se calcula una alerta para un insumo activo de una persona con autorización vigente para
  ``consumo``. Sin ella, el trabajo diario no crea alertas ni avisa.
- La alerta es una fila materializada, una por perfil y fecha prevista (ADR-012). Cerrarla
  (resuelta o descartada) es una transición, nunca un borrado. Una alerta nunca genera un pedido.
- El aviso (MATU-41) llega por defecto a admin y cuidador; pagador y observador solo si lo activan
  en preferencia_notificacion (decisión de Jorge, 78).
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum

from app.modules.consumption.domain.perfil import dias_restantes


class EstadoAlerta(StrEnum):
    PENDIENTE = "pendiente"
    NOTIFICADA = "notificada"
    RESUELTA = "resuelta"
    DESCARTADA = "descartada"


ABIERTAS = frozenset({EstadoAlerta.PENDIENTE, EstadoAlerta.NOTIFICADA})
CERRADAS = frozenset({EstadoAlerta.RESUELTA, EstadoAlerta.DESCARTADA})

# Decisión 78: quién recibe el aviso sin haberlo pedido
ROLES_AVISADOS_POR_DEFECTO = frozenset({"admin", "cuidador"})

# Decisión 77: conservación
CONSERVACION_ALERTAS = timedelta(days=90)
CONSERVACION_EVENTOS = timedelta(days=30)


def avisa_por_defecto(rol: str) -> bool:
    return rol in ROLES_AVISADOS_POR_DEFECTO


def en_ventana(restantes: int, dias_aviso: int) -> bool:
    """Hay que avisar con ``dias_aviso`` o menos días restantes (0 = hoy; negativo = ya pasó)."""
    return restantes <= dias_aviso


def corresponde_alerta(*, activo: bool, autorizado: bool, fecha_quiebre: date, dias_aviso: int, hoy: date) -> bool:
    """Si el insumo debe tener una alerta para su fecha estimada actual."""
    return activo and autorizado and en_ventana(dias_restantes(fecha_quiebre, hoy), dias_aviso)


def avisando(*, en_su_ventana: bool, estado_de_la_fecha: EstadoAlerta | None) -> bool:
    """Lo que la pantalla marca como «Te estamos avisando»: en ventana y sin una alerta cerrada para la
    fecha estimada actual. Después de cerrar deja de aparecer, hasta que cambie la fecha."""
    return en_su_ventana and estado_de_la_fecha not in CERRADAS


class AlertaCerrada(Exception):
    """La alerta ya está resuelta o descartada. La API responde 409 alerta-cerrada."""

    def __init__(self, estado: EstadoAlerta) -> None:
        super().__init__("la alerta ya está cerrada")
        self.estado = estado


def exigir_abierta(estado: EstadoAlerta) -> None:
    if estado in CERRADAS:
        raise AlertaCerrada(estado)


# --- El trabajo diario -----------------------------------------------------------------------------


@dataclass(frozen=True)
class AlertaAbierta:
    id: uuid.UUID
    fecha_prevista: date


@dataclass(frozen=True)
class InsumoEnSeguimiento:
    """Lo que el trabajo diario sabe de un perfil activo: sin nombre ni cantidades."""

    perfil_id: uuid.UUID
    persona_cuidada_id: uuid.UUID
    fecha_quiebre_estimada: date
    dias_aviso: int
    autorizado: bool
    abiertas: tuple[AlertaAbierta, ...] = ()
    # Si ya existe una alerta (de cualquier estado) para la fecha estimada actual
    hay_alerta_de_la_fecha: bool = False


@dataclass(frozen=True)
class PlanAlertas:
    materializar: bool
    descartar: tuple[uuid.UUID, ...]


def planificar(insumo: InsumoEnSeguimiento, hoy: date) -> PlanAlertas:
    """Qué hace el trabajo diario con un insumo (decisión 75).

    - Sin autorización vigente: nada (ni crea, ni avisa, ni cierra).
    - Las alertas abiertas de otra fecha (la familia anotó de nuevo cuánto queda) se descartan.
    - Si corresponde alerta y no hay ninguna para la fecha actual, se materializa. Si ya hay una
      (abierta o cerrada por la familia), no se crea otra: la restricción única lo repite.
    - Si ya no corresponde (salió de la ventana), las abiertas se descartan.
    """
    if not insumo.autorizado:
        return PlanAlertas(materializar=False, descartar=())
    corresponde = corresponde_alerta(
        activo=True,
        autorizado=True,
        fecha_quiebre=insumo.fecha_quiebre_estimada,
        dias_aviso=insumo.dias_aviso,
        hoy=hoy,
    )
    descartar = tuple(
        a.id for a in insumo.abiertas if not corresponde or a.fecha_prevista != insumo.fecha_quiebre_estimada
    )
    return PlanAlertas(materializar=corresponde and not insumo.hay_alerta_de_la_fecha, descartar=descartar)


# --- Conservación ----------------------------------------------------------------------------------


def limites_conservacion(ahora: datetime) -> tuple[datetime, datetime]:
    """(límite de alertas y notificaciones, límite de eventos publicados)."""
    if ahora.tzinfo is None or ahora.utcoffset() is None:
        raise ValueError("El instante debe tener zona horaria")
    return ahora - CONSERVACION_ALERTAS, ahora - CONSERVACION_EVENTOS
