"""Las reglas del despacho (MATU-63, D-63-3 a D-63-8 y D-63-11; O3 a O6 del orquestador). Puras: sin I/O ni reloj.

- Cada comercio prepara su parte del pedido (pedido_comercio): enviada → preparando → lista → retirada, o cancelada.
- El estado del pedido lo lleva el sistema a partir de sus partes (``avance``), nunca la sesión del comercio.
- El código de retiro: 6 cifras, una por parte, vale 90 minutos, sirve una vez y se bloquea al quinto intento fallido.
  Se guarda solo su HMAC-SHA256 (``huella_codigo``), con la parte en el mensaje: el mismo código en dos partes deja
  huellas distintas.
- Un faltante se devuelve por unidades (unidades_faltantes × precio pagado). Si no se entrega nada, se devuelve todo,
  envío incluido, y el pedido pasa a cancelado_con_devolucion (D-63-8, O3).
"""

import hashlib
import hmac
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

VIDA_CODIGO = timedelta(minutes=90)
MAX_INTENTOS = 5
CIFRAS_CODIGO = 6
# «Preparar antes de»: dos horas desde que la parte llega al comercio. [PENDIENTE: el plazo real lo fija el convenio]
PLAZO_PREPARAR = timedelta(hours=2)
# O6: la referencia opaca se dicta en el mostrador. Sin 0, O, 1, I ni L
ALFABETO_REFERENCIA = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
LARGO_REFERENCIA = 6


class EstadoParte(StrEnum):
    ENVIADA = "enviada"
    PREPARANDO = "preparando"
    LISTA = "lista"
    RETIRADA = "retirada"
    CANCELADA = "cancelada"


ABIERTAS = frozenset({EstadoParte.ENVIADA, EstadoParte.PREPARANDO, EstadoParte.LISTA})


class EstadoCodigo(StrEnum):
    """Lo que el comercio sabe del código de su parte, nunca el código ni su huella."""

    SIN_CODIGO = "sin_codigo"
    VIGENTE = "vigente"
    USADO = "usado"
    BLOQUEADO = "bloqueado"
    VENCIDO = "vencido"


class ResultadoCodigo(StrEnum):
    """Lo que responde la validación (comercio_validar_codigo, migración 0029)."""

    CORRECTO = "correcto"
    NO_ES = "no_es"
    BLOQUEADO = "bloqueado"
    VENCIDO = "vencido"
    USADO = "usado"
    CANCELADA = "cancelada"
    SIN_CODIGO = "sin_codigo"


class MarcaLinea(StrEnum):
    PREPARADA = "preparada"
    FALTANTE = "faltante"


def estado_codigo(
    *,
    generado_en: datetime | None,
    con_hash: bool,
    expira_en: datetime | None,
    usado_en: datetime | None,
    bloqueado_en: datetime | None,
    ahora: datetime,
) -> EstadoCodigo:
    if usado_en is not None:
        return EstadoCodigo.USADO
    if bloqueado_en is not None:
        return EstadoCodigo.BLOQUEADO
    if generado_en is None or expira_en is None:
        return EstadoCodigo.SIN_CODIGO
    if not con_hash or expira_en <= ahora:
        return EstadoCodigo.VENCIDO
    return EstadoCodigo.VIGENTE


def huella_codigo(secreto: bytes, parte_id: uuid.UUID, codigo: str) -> str:
    """HMAC-SHA256(secreto, "<parte>:<código>") en hex. Sin el secreto, seis cifras no se recuperan de la base."""
    if not secreto:
        raise ValueError("El secreto no puede estar vacío")
    return hmac.new(secreto, f"{parte_id}:{codigo}".encode(), hashlib.sha256).hexdigest()


def codigo_valido(codigo: str) -> bool:
    return len(codigo) == CIFRAS_CODIGO and codigo.isascii() and codigo.isdigit()


def preparar_antes_de(enviado_en: datetime) -> datetime:
    return enviado_en + PLAZO_PREPARAR


def referencia_valida(referencia: str) -> bool:
    return len(referencia) == LARGO_REFERENCIA and all(c in ALFABETO_REFERENCIA for c in referencia)


# --- El pedido a partir de sus partes ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Paso:
    """Una transición del pedido que el sistema escribe. ``por_comercio``: la causó una acción del comercio, y la
    línea de tiempo lleva al comercio como actor (D-63-12)."""

    desde: str
    hacia: str
    por_comercio: bool
    motivo: str | None = None


MOTIVO_PRODUCTO_FALTANTE = "producto_faltante"


def avance(estado_pedido: str, partes: Sequence[EstadoParte]) -> list[Paso]:
    """Las transiciones que le faltan al pedido según sus partes, en orden. Vacío si está al día.

    pagado → enviado_a_comercio en cuanto hay partes; → preparando cuando alguna empezó; → listo_retiro cuando ninguna
    sigue enviada ni preparando y alguna quedó lista o retirada; → cancelado_con_devolucion si todas se cancelaron
    (todo faltaba, O3); → retirado cuando ninguna sigue abierta."""
    pasos: list[Paso] = []
    estado = estado_pedido
    if not partes:
        return pasos
    if estado == "pagado":
        pasos.append(Paso("pagado", "enviado_a_comercio", por_comercio=False))
        estado = "enviado_a_comercio"
    if estado == "enviado_a_comercio" and any(p is not EstadoParte.ENVIADA for p in partes):
        pasos.append(Paso(estado, "preparando", por_comercio=True))
        estado = "preparando"
    if estado == "preparando" and not any(p in (EstadoParte.ENVIADA, EstadoParte.PREPARANDO) for p in partes):
        if all(p is EstadoParte.CANCELADA for p in partes):
            pasos.append(Paso(estado, "cancelado_con_devolucion", por_comercio=True, motivo=MOTIVO_PRODUCTO_FALTANTE))
            return pasos
        pasos.append(Paso(estado, "listo_retiro", por_comercio=True))
        estado = "listo_retiro"
    if estado == "listo_retiro" and not any(p in ABIERTAS for p in partes):
        pasos.append(Paso(estado, "retirado", por_comercio=True))
    return pasos


def todo_falta(partes: Sequence[EstadoParte]) -> bool:
    return bool(partes) and all(p is EstadoParte.CANCELADA for p in partes)


@dataclass(frozen=True)
class LineaDespacho:
    id: uuid.UUID
    parte_id: uuid.UUID | None
    cantidad: int
    unidades_faltantes: int
    precio_unitario: int
    monto_devuelto: int

    @property
    def entregadas(self) -> int:
        return self.cantidad - self.unidades_faltantes

    @property
    def monto_faltante(self) -> int:
        """Lo que se devuelve por lo que faltó (D-63-8): unidades faltantes × precio pagado."""
        return self.unidades_faltantes * self.precio_unitario


def monto_consumo(lineas: Sequence[LineaDespacho]) -> int:
    """Lo que MATU le debe al comercio por su parte entregada (RF-31), al precio de sus líneas, sin lo que faltó."""
    return sum(linea.entregadas * linea.precio_unitario for linea in lineas)


# Las transiciones de operación (D-63-6)
EN_CAMINO_DESDE = ("retirado", "reprogramado")
NO_ENTREGADO_DESDE = ("en_ruta",)
ENTREGADO_DESDE = ("en_ruta",)

# R15 (D-63-11): se cancela después de pagar mientras ningún comercio empezó a preparar
CANCELABLE_PAGADO = ("pagado", "enviado_a_comercio")


def cancelable_despues_de_pagar(estado_pedido: str, partes: Sequence[EstadoParte]) -> bool:
    return estado_pedido in CANCELABLE_PAGADO and all(p is EstadoParte.ENVIADA for p in partes)
