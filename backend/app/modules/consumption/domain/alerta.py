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
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from enum import StrEnum

from app.modules.consumption.domain.perfil import STOCK_MAXIMO, Perfil, dias_restantes, fecha_quiebre


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


def avisa_hoy(perfil: Perfil, estado_de_la_fecha: EstadoAlerta | None, hoy: date) -> bool:
    """``avisando`` de un perfil para hoy (decisión 74): activo, en su ventana y sin una alerta cerrada
    para su fecha estimada actual. ``estado_de_la_fecha`` es el de la alerta de esa fecha, o None si el
    trabajo diario aún no la creó. Lo usan «Se acaban pronto» y la lista de insumos (MATU-60, decisión
    117), así que la lista es siempre el subconjunto de «Se acaban pronto» con avisando = true."""
    ventana = perfil.activo and en_ventana(dias_restantes(perfil.fecha_quiebre_estimada, hoy), perfil.dias_aviso)
    return avisando(en_su_ventana=ventana, estado_de_la_fecha=estado_de_la_fecha)


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


# --- «Ya lo resolví» con cantidad (decisión 79) y «Compré» (MATU-51, decisiones 137 y 144) ------------------

# Lo comprado en la unidad del insumo, en «Ya lo resolví» y en «Compré» (ajuste de D de Jorge, 07-11)
CANTIDAD_MAXIMA = 10_000
# «Compré» en envases: de 1 a 99. envases × unidades_por_envase puede pasar de CANTIDAD_MAXIMA
ENVASES_MAXIMO = 99


class StockMaximo(ValueError):
    """Lo que queda hoy más lo comprado pasa de 100.000 (decisión 43). La API responde 422 stock_maximo."""


class SinUnidadesPorEnvase(ValueError):
    """«Compré» en envases sobre un perfil sin unidades_por_envase. La API responde 422."""


class EnvasesOCantidad(ValueError):
    """«Compré» trae los dos campos o ninguno. La API responde 422 envases_o_cantidad."""


def stock_estimado_hoy(perfil: Perfil, hoy: date) -> int:
    """Lo que MATU estima que queda hoy, en la unidad del insumo, en enteros y nunca negativo:
    ``piso(stock - dias_transcurridos * tasa_unidades / tasa_dias)``, o 0 si da negativo."""
    dias = max(0, (hoy - perfil.stock_medido_en).days)
    restante = (perfil.stock_unidades * perfil.tasa_dias - dias * perfil.tasa_unidades) // perfil.tasa_dias
    return max(0, restante)


def cantidad_comprada(perfil: Perfil, *, envases: int | None, cantidad: int | None) -> int:
    """Lo comprado en la unidad del insumo (decisión 137): ``envases × unidades_por_envase`` o ``cantidad``.

    Exactamente uno de los dos (si no, EnvasesOCantidad). envases de 1 a 99 y solo con unidades_por_envase
    (si no, SinUnidadesPorEnvase); cantidad de 1 a 10.000. Fuera de rango, ValueError con un mensaje fijo.
    """
    if (envases is None) == (cantidad is None):
        raise EnvasesOCantidad("indica envases o cantidad, solo uno")
    if envases is not None:
        if not 1 <= envases <= ENVASES_MAXIMO:
            raise ValueError("envases debe ser de 1 a 99")
        if perfil.unidades_por_envase is None:
            raise SinUnidadesPorEnvase("el insumo no tiene unidades por envase")
        return envases * perfil.unidades_por_envase
    assert cantidad is not None
    if not 1 <= cantidad <= CANTIDAD_MAXIMA:
        raise ValueError("la cantidad debe ser de 1 a 10000")
    return cantidad


def reponer(perfil: Perfil, cantidad: int, hoy: date, autor: uuid.UUID) -> Perfil:
    """Suma lo comprado a lo que queda hoy: stock nuevo, stock_medido_en = hoy, fecha recalculada y versión
    + 1. ``cantidad`` ya viene en la unidad del insumo (de cantidad_comprada o del cuerpo de «Ya lo resolví»).
    Lanza ValueError si no es positiva, StockMaximo si el stock pasa de 100.000 y CoberturaMaxima (del perfil)
    si pasa de 3650 días."""
    if cantidad < 1:
        raise ValueError("la cantidad debe ser positiva")
    stock = stock_estimado_hoy(perfil, hoy) + cantidad
    if stock > STOCK_MAXIMO:
        raise StockMaximo("lo que queda más lo comprado pasa del máximo")
    return replace(
        perfil,
        stock_unidades=stock,
        stock_medido_en=hoy,
        fecha_quiebre_estimada=fecha_quiebre(hoy, stock, perfil.tasa_unidades, perfil.tasa_dias),
        version=perfil.version + 1,
        actualizado_por=autor,
    )


# --- Las alertas abiertas después de «Compré» o «Me quedan N» (MATU-51, decisiones 138 y 139) ------------


def dejan_de_corresponder(perfil: Perfil, abiertas: tuple[AlertaAbierta, ...], hoy: date) -> tuple[uuid.UUID, ...]:
    """Las alertas abiertas que, con la fecha estimada nueva del perfil, ya no corresponden: las de otra fecha
    y, si salió de la ventana, todas. Es la regla del trabajo diario (``planificar``, decisión 75) con la
    autorización vigente, que la API ya verificó. Nunca pide materializar una alerta."""
    insumo = InsumoEnSeguimiento(
        perfil_id=perfil.id,
        persona_cuidada_id=perfil.persona_cuidada_id,
        fecha_quiebre_estimada=perfil.fecha_quiebre_estimada,
        dias_aviso=perfil.dias_aviso,
        autorizado=True,
        abiertas=abiertas,
    )
    descartar = planificar(insumo, hoy).descartar
    return descartar if perfil.activo else tuple(a.id for a in abiertas)
