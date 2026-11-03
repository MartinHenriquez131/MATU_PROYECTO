"""Reglas puras del perfil de consumo (MATU-36, RF-10 y RF-11, arquitectura 7.3).

Sin I/O y sin reloj del sistema: "hoy" se calcula desde el instante del puerto Reloj, en
America/Santiago (decisión 42).

- La fecha estimada de quiebre es entera, sin punto flotante:
  ``dias = piso(stock_unidades * tasa_dias / tasa_unidades)`` y
  ``fecha_quiebre_estimada = stock_medido_en + dias``. Solo esta fórmula: la predicción completa y las
  alertas son de MATU-37.
- Topes (decisión 43): tasa_unidades 1..10000, tasa_dias 1..90, stock 0..100000, dias_aviso 0..60
  y una cobertura de 3650 días como máximo.
- Leen los cuatro roles del grupo (admin, cuidador, pagador y observador). Escriben (crear, editar,
  desactivar, activar y eliminar) solo admin y cuidador (decisión 71). Un rol que no alcanza recibe
  404, nunca 403.
- Toda edición es condicional con ``If-Match: "v<version>"`` (decisión 41).
- ``nombre_libre`` nunca va en un mensaje de error, un log, la auditoría ni un evento.
"""

import uuid
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

ZONA_CHILE = ZoneInfo("America/Santiago")

TASA_UNIDADES_MAXIMA = 10_000
TASA_DIAS_MAXIMA = 90
STOCK_MAXIMO = 100_000
DIAS_AVISO_MAXIMO = 60
DIAS_AVISO_POR_OMISION = 7
COBERTURA_MAXIMA_DIAS = 3650
LARGO_MAXIMO_NOMBRE_LIBRE = 60

ROLES_QUE_LEEN = frozenset({"admin", "cuidador", "pagador", "observador"})
ROLES_QUE_ESCRIBEN = frozenset({"admin", "cuidador"})

# Decisión 70: el consumo de una persona se borra 90 días después de que termina su autorización
CONSERVACION_CONSUMO = timedelta(days=90)


class UnidadConsumo(StrEnum):
    UNIDAD = "unidad"
    SOBRE = "sobre"
    ML = "ml"
    G = "g"


def puede_leer(rol: str) -> bool:
    return rol in ROLES_QUE_LEEN


def puede_escribir(rol: str) -> bool:
    return rol in ROLES_QUE_ESCRIBEN


class CoberturaMaxima(ValueError):
    """El stock cubre más de 3650 días con esa tasa (decisión 43). La API responde 422."""


def hoy_en_chile(ahora: datetime) -> date:
    """La fecha de hoy en America/Santiago para un instante con zona horaria."""
    if ahora.tzinfo is None or ahora.utcoffset() is None:
        raise ValueError("El instante debe tener zona horaria")
    return ahora.astimezone(ZONA_CHILE).date()


def dias_cobertura(stock_unidades: int, tasa_unidades: int, tasa_dias: int) -> int:
    """piso(stock_unidades * tasa_dias / tasa_unidades), en enteros. Lanza CoberturaMaxima si pasa de 3650."""
    if tasa_unidades < 1 or tasa_dias < 1 or stock_unidades < 0:
        raise ValueError("tasa y stock fuera de rango")
    dias = (stock_unidades * tasa_dias) // tasa_unidades
    if dias > COBERTURA_MAXIMA_DIAS:
        raise CoberturaMaxima("el stock cubre más días de los que se admiten")
    return dias


def fecha_quiebre(stock_medido_en: date, stock_unidades: int, tasa_unidades: int, tasa_dias: int) -> date:
    """stock_medido_en + dias_cobertura."""
    return stock_medido_en + timedelta(days=dias_cobertura(stock_unidades, tasa_unidades, tasa_dias))


def dias_restantes(fecha_quiebre_estimada: date, hoy: date) -> int:
    """fecha_quiebre_estimada - hoy. 0 = se acaba hoy; negativo = la fecha ya pasó."""
    return (fecha_quiebre_estimada - hoy).days


def nombre_libre_valido(valor: str) -> str:
    """Quita los espacios de los extremos y exige 1 a 60 caracteres, una línea, sin caracteres de
    control. Lanza ValueError con un mensaje fijo, sin el valor."""
    limpio = valor.strip()
    if not 1 <= len(limpio) <= LARGO_MAXIMO_NOMBRE_LIBRE:
        raise ValueError("debe tener entre 1 y 60 caracteres")
    if any(ord(c) < 32 or 127 <= ord(c) < 160 or c in "  " for c in limpio):
        raise ValueError("solo admite texto, sin saltos de línea ni caracteres de control")
    return limpio


def nombre_de_pila(nombre: str | None) -> str | None:
    """La primera palabra del nombre de la cuenta, para decir quién guardó (sin el apellido)."""
    if not nombre:
        return None
    partes = nombre.split()
    return partes[0] if partes else None


# --- ETag y precondición (como la ficha de MATU-13) ---------------------------------------------------


def etag(version: int) -> str:
    return f'"v{version}"'


class FaltaVersion(Exception):
    """Sin If-Match, vacío o ``*``: la edición no es condicional. La API responde 428."""


def exigir_if_match(if_match: str | None) -> str:
    """Devuelve el If-Match a comparar. Lanza FaltaVersion si falta, está vacío o es ``*``.

    Nunca es 422: cualquier otro valor se compara en forma fuerte y, si no coincide, es 412.
    """
    if if_match is None or not if_match.strip() or if_match.strip() == "*":
        raise FaltaVersion()
    return if_match.strip()


def coincide(if_match: str, version: int) -> bool:
    return if_match == etag(version)


# --- El perfil -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Perfil:
    """Un perfil de consumo tal como está guardado."""

    id: uuid.UUID
    persona_cuidada_id: uuid.UUID
    producto_id: uuid.UUID | None
    nombre_libre: str | None
    unidad: UnidadConsumo
    tasa_unidades: int
    tasa_dias: int
    stock_unidades: int
    stock_medido_en: date
    dias_aviso: int
    fecha_quiebre_estimada: date
    activo: bool
    version: int
    actualizado_por: uuid.UUID | None


def nuevo_perfil(
    *,
    perfil_id: uuid.UUID,
    persona_cuidada_id: uuid.UUID,
    producto_id: uuid.UUID | None,
    nombre_libre: str | None,
    unidad: UnidadConsumo,
    tasa_unidades: int,
    tasa_dias: int,
    stock_unidades: int,
    dias_aviso: int,
    hoy: date,
    autor: uuid.UUID,
) -> Perfil:
    """Un perfil nuevo con stock_medido_en = hoy y la fecha estimada ya calculada."""
    if (producto_id is None) == (nombre_libre is None):
        raise ValueError("producto_id o nombre_libre, exactamente uno")
    return Perfil(
        id=perfil_id,
        persona_cuidada_id=persona_cuidada_id,
        producto_id=producto_id,
        nombre_libre=nombre_libre,
        unidad=unidad,
        tasa_unidades=tasa_unidades,
        tasa_dias=tasa_dias,
        stock_unidades=stock_unidades,
        stock_medido_en=hoy,
        dias_aviso=dias_aviso,
        fecha_quiebre_estimada=fecha_quiebre(hoy, stock_unidades, tasa_unidades, tasa_dias),
        activo=True,
        version=1,
        actualizado_por=autor,
    )


@dataclass(frozen=True)
class CambiosPerfil:
    """Los campos que trajo el PATCH. None = no vino (null no se admite en la API)."""

    nombre_libre: str | None = None
    tasa_unidades: int | None = None
    tasa_dias: int | None = None
    stock_unidades: int | None = None
    dias_aviso: int | None = None


class NombreLibreConProducto(ValueError):
    """Se quiso editar nombre_libre de un perfil de producto. La API responde 422."""


def aplicar_cambios(perfil: Perfil, cambios: CambiosPerfil, hoy: date, autor: uuid.UUID) -> Perfil:
    """Aplica el PATCH (decisiones 41 y 42) y suma 1 a la versión.

    - Si viene stock_unidades, aunque sea el mismo, stock_medido_en pasa a hoy.
    - La fecha estimada se recalcula siempre desde stock_medido_en.
    Lanza NombreLibreConProducto o CoberturaMaxima sin cambiar nada.
    """
    if cambios.nombre_libre is not None and perfil.producto_id is not None:
        raise NombreLibreConProducto("nombre_libre solo se edita en un perfil sin producto")
    stock = perfil.stock_unidades if cambios.stock_unidades is None else cambios.stock_unidades
    medido_en = perfil.stock_medido_en if cambios.stock_unidades is None else hoy
    tasa_u = perfil.tasa_unidades if cambios.tasa_unidades is None else cambios.tasa_unidades
    tasa_d = perfil.tasa_dias if cambios.tasa_dias is None else cambios.tasa_dias
    return replace(
        perfil,
        nombre_libre=perfil.nombre_libre if cambios.nombre_libre is None else cambios.nombre_libre,
        tasa_unidades=tasa_u,
        tasa_dias=tasa_d,
        stock_unidades=stock,
        stock_medido_en=medido_en,
        dias_aviso=perfil.dias_aviso if cambios.dias_aviso is None else cambios.dias_aviso,
        fecha_quiebre_estimada=fecha_quiebre(medido_en, stock, tasa_u, tasa_d),
        version=perfil.version + 1,
        actualizado_por=autor,
    )


def con_activo(perfil: Perfil, activo: bool, autor: uuid.UUID) -> Perfil:
    """Desactivar o activar. Si ya está en ese estado, el mismo perfil (idempotente, sin versión nueva)."""
    if perfil.activo is activo:
        return perfil
    return replace(perfil, activo=activo, version=perfil.version + 1, actualizado_por=autor)


# --- Conservación (decisión 70) ------------------------------------------------------------------------


def limite_conservacion(ahora: datetime) -> datetime:
    """Antes de este instante, una autorización de consumo terminada deja borrar el consumo."""
    if ahora.tzinfo is None or ahora.utcoffset() is None:
        raise ValueError("El instante debe tener zona horaria")
    return ahora - CONSERVACION_CONSUMO


def consumo_se_borra(hay_autorizacion_no_revocada: bool, ultima_revocacion: datetime | None, limite: datetime) -> bool:
    """La misma regla de consumo_conservar (migración 0009): sin autorización no revocada para consumo
    y con la última revocada hace 90 días o más."""
    return not hay_autorizacion_no_revocada and ultima_revocacion is not None and ultima_revocacion <= limite
