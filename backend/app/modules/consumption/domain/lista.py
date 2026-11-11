"""Reglas puras de la lista de insumos (MATU-60, RF-15, ADR-031). Decisiones 117 a 121 de docs/api/README.md.

Sin I/O y sin reloj del sistema: "hoy" llega calculado con el puerto Reloj (``hoy_en_chile``).

- **Qué entra** (decisión 117, ajuste de Jorge del 06-11): el insumo que hoy está en «Se acaban pronto»
  con ``avisando = true`` (``alerta.avisa_hoy``, decisión 74). No depende de que el trabajo diario haya
  creado la alerta.
- **Cuánto** (decisiones 119 y 120, opción B de Jorge): lo que falta para 30 días, descontando lo que
  MATU estima que queda hoy (``alerta.stock_estimado_hoy``, la fórmula de la decisión 79), al menos 1:
  ``max(1, techo(30 * tasa_unidades / tasa_dias) - queda_hoy)``. En envases enteros si el perfil tiene
  ``unidades_por_envase``, que sale solo del perfil y nunca del catálogo (decisión 121). Todo en enteros.
- **Orden** (decisión 117): fecha estimada, nombre sin marcas diacríticas y con casefold, nombre con
  casefold y perfil_id. En el dominio, no en SQL, para no depender de la colación de la base.
- El nombre puede decir algo de la salud de la persona: este módulo nunca lo pone en un mensaje de error.
"""

import unicodedata
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from app.modules.consumption.domain.alerta import EstadoAlerta, avisa_hoy, stock_estimado_hoy
from app.modules.consumption.domain.perfil import Perfil, UnidadConsumo, dias_restantes

COBERTURA_LISTA_DIAS = 30


def techo_division(dividendo: int, divisor: int) -> int:
    """techo(dividendo / divisor) para dividendo >= 0 y divisor >= 1, sin punto flotante."""
    if dividendo < 0 or divisor < 1:
        raise ValueError("techo_division admite dividendo >= 0 y divisor >= 1")
    return (dividendo + divisor - 1) // divisor


def unidades_para_cobertura(tasa_unidades: int, tasa_dias: int, dias: int = COBERTURA_LISTA_DIAS) -> int:
    """techo(dias * tasa_unidades / tasa_dias): lo que se usa en ``dias`` días."""
    if tasa_unidades < 1 or tasa_dias < 1:
        raise ValueError("tasa fuera de rango")
    return techo_division(dias * tasa_unidades, tasa_dias)


def unidades_sugeridas(perfil: Perfil, hoy: date) -> int:
    """Lo que falta para 30 días: max(1, techo(30 * tasa_unidades / tasa_dias) - queda_hoy).

    El mínimo de 1 hace falta porque lo que queda puede cubrir 30 días o más (dias_aviso admite hasta 60).
    """
    falta = unidades_para_cobertura(perfil.tasa_unidades, perfil.tasa_dias) - stock_estimado_hoy(perfil, hoy)
    return max(1, falta)


def envases_sugeridos(unidades: int, unidades_por_envase: int | None) -> int | None:
    """techo(unidades / unidades_por_envase), o None si el perfil no tiene el dato."""
    if unidades_por_envase is None:
        return None
    return techo_division(unidades, unidades_por_envase)


def sin_marcas(texto: str) -> str:
    """El texto sin marcas diacríticas (NFD sin la categoría Mn) y con casefold: «Óleo» -> «oleo»."""
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn").casefold()


@dataclass(frozen=True)
class InsumoCandidato:
    """Un perfil que podría ir en la lista: el perfil, su nombre para mostrar (producto.nombre o
    nombre_libre) y el estado de la alerta de su fecha estimada actual, o None si no existe."""

    perfil: Perfil
    nombre: str
    estado_de_la_fecha: EstadoAlerta | None


@dataclass(frozen=True)
class LineaLista:
    perfil_id: uuid.UUID
    nombre: str
    unidad: UnidadConsumo
    dias_restantes: int
    unidades_sugeridas: int
    unidades_por_envase: int | None
    envases_sugeridos: int | None
    # Para ordenar; no se publica
    fecha_quiebre_estimada: date
    # MATU-61 (decisión 215, D10): el producto del catálogo del perfil, o None si se anotó con nombre_libre
    producto_id: uuid.UUID | None = None


def entra(candidato: InsumoCandidato, hoy: date) -> bool:
    """Decisión 117: el insumo está en «Se acaban pronto» con avisando = true."""
    return avisa_hoy(candidato.perfil, candidato.estado_de_la_fecha, hoy)


def linea(candidato: InsumoCandidato, hoy: date) -> LineaLista:
    p = candidato.perfil
    unidades = unidades_sugeridas(p, hoy)
    return LineaLista(
        perfil_id=p.id,
        nombre=candidato.nombre,
        unidad=p.unidad,
        dias_restantes=dias_restantes(p.fecha_quiebre_estimada, hoy),
        unidades_sugeridas=unidades,
        unidades_por_envase=p.unidades_por_envase,
        envases_sugeridos=envases_sugeridos(unidades, p.unidades_por_envase),
        fecha_quiebre_estimada=p.fecha_quiebre_estimada,
        producto_id=p.producto_id,
    )


def clave_orden(linea: LineaLista) -> tuple[date, str, str, str]:
    """Decisión 117: fecha estimada, nombre sin marcas y con casefold, nombre con casefold (en NFC, para
    que «ñ» compuesta y descompuesta empaten igual) y perfil_id en minúsculas."""
    return (
        linea.fecha_quiebre_estimada,
        sin_marcas(linea.nombre),
        unicodedata.normalize("NFC", linea.nombre).casefold(),
        str(linea.perfil_id).lower(),
    )


def armar_lista(candidatos: Iterable[InsumoCandidato], hoy: date) -> list[LineaLista]:
    """Las líneas de la lista de hoy: solo los candidatos que entran, en el orden de la decisión 117."""
    return sorted((linea(c, hoy) for c in candidatos if entra(c, hoy)), key=clave_orden)
