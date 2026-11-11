"""La venta en Webpay Plus, su resultado y las reglas del pago tardío (ADR-027; D-62-4, D-62-5, D-62-12; decisiones
228 a 233 y 236).

- Una venta (``transaccion_pasarela``, tipo venta) cobra el total confirmado una sola vez y queda atada a ese total:
  su monto y su ``total_confirmado_en`` (D-62-4).
- Regla 2 de D-62-4: un ``commit`` aprobado del **mismo** total se respeta aunque el total haya vencido mientras se
  pagaba (``vencido → pagado``).
- Regla 3: un ``commit`` aprobado de un total que ya no es el del pedido (se volvió a confirmar, se cambió, se canceló,
  o ya lo pagó otra venta) se anula completo el mismo día, a la misma tarjeta, y el pedido no cambia.
- **Ninguna regla distingue el medio de pago** (arquitectura 12.4, caso 2): el tipo de tarjeta es solo para el texto.
- El ``buy_order`` y el ``session_id`` son aleatorios y no derivan de ningún id ni dato de nadie (decisión 228).

Solo biblioteca estándar y sin reloj del sistema: el instante llega como argumento.
"""

import secrets
import uuid
from collections.abc import Callable, Collection
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

# ADR-027: el total confirmado vale 15 minutos. Es la misma regla de ordering (domain/estados.py), que este dominio no
# puede importar (test_arquitectura: domain/ solo importa su propio dominio)
VIGENCIA_TOTAL = timedelta(minutes=15)

# Decisión 233: con la venta en autorizando, como mucho un commit cada 10 segundos
ESPERA_ENTRE_COMMITS = timedelta(seconds=10)

# Decisión 232: la app repite la vuelta pendiente cada 15 segundos
VOLVER_A_PREGUNTAR_S = 15

# D-62-6 y arquitectura 12.4, caso 7: una venta sin respuesta o una anulación sin hacer por más de 15 minutos es una
# alerta a operación
ALERTA_TRAS = timedelta(minutes=15)

# Los límites de Transbank (SDK, ApiConstants): buy_order hasta 26 y session_id hasta 61
LARGO_BUY_ORDER = 26
LARGO_SESSION_ID = 61

# El código de autorización tiene hasta 6 caracteres (Comprobante.codigo_autorizacion)
LARGO_CODIGO_AUTORIZACION = 6


class EstadoVenta(StrEnum):
    """``transaccion_pasarela.estado`` (migración 0001). En una anulación: iniciada y error son «en curso»."""

    INICIADA = "iniciada"
    AUTORIZANDO = "autorizando"
    APROBADA = "aprobada"
    RECHAZADA = "rechazada"
    ERROR = "error"


class MotivoCierre(StrEnum):
    """Por qué se cerró una venta sin cobro (migración 0024)."""

    NO_APROBADA = "no_aprobada"
    USUARIO_SALIO = "usuario_salio"
    FORMULARIO_VENCIDO = "formulario_vencido"


class MotivoAnulacion(StrEnum):
    PAGO_TARDIO = "pago_tardio"
    PRODUCTO_NO_ENTREGADO = "producto_no_entregado"
    CANCELACION = "cancelacion"


class ResultadoPago(StrEnum):
    """Qué pasó con un intento, con los nombres del diseño (3.3, decisión 232). La pantalla elige el texto."""

    APROBADO = "aprobado"
    APROBADO_TARDIO = "aprobado_tardio"
    NO_APROBADO = "no_aprobado"
    ABANDONADO = "abandonado"
    TIEMPO_AGOTADO = "tiempo_agotado"
    PENDIENTE = "pendiente"
    ANULADO = "anulado"
    # Solo en GET …/pago: la persona está (o estuvo) en Webpay
    EN_WEBPAY = "en_webpay"


class TipoTarjeta(StrEnum):
    CREDITO = "credito"
    DEBITO = "debito"
    PREPAGO = "prepago"


class CasoRetorno(StrEnum):
    """Qué trajo la vuelta (decisión 232). Va a la línea del log como ``caso``, sin ningún valor."""

    COMMIT = "commit"
    REPETIDO = "repetido"
    USUARIO_SALIO = "usuario_salio"
    FORMULARIO_VENCIDO = "formulario_vencido"
    DESCONOCIDO = "desconocido"


@dataclass(frozen=True)
class Venta:
    """Una venta. Sin el número de tarjeta, que MATU nunca recibe, ni la respuesta de Transbank (D-62-9)."""

    id: uuid.UUID
    cargo_id: uuid.UUID
    participacion_id: uuid.UUID
    # Quien paga (la participación): para «pagaste tú» y «es tuyo» (D-62-2)
    usuario_id: uuid.UUID
    estado: EstadoVenta
    monto: int
    total_confirmado_en: datetime
    token: str | None
    buy_order: str
    session_id: str | None
    creado_en: datetime
    cerrada_en: datetime | None = None
    motivo_cierre: MotivoCierre | None = None
    tipo_tarjeta: TipoTarjeta | None = None
    ultimos4: str | None = None
    cuotas: int | None = None
    codigo_autorizacion: str | None = None
    anulacion_total: bool = False
    # La anulación total es la de la regla 3 (pago tardío), no una cancelación de MATU-63
    anulada_por_pago_tardio: bool = False
    retorno_recibido_en: datetime | None = None
    commit_intentado_en: datetime | None = None

    @property
    def vence_en(self) -> datetime:
        return self.total_confirmado_en + VIGENCIA_TOTAL

    @property
    def tardia(self) -> bool:
        """Se aprobó después de que venció su total (regla 2: se respetó)."""
        return self.estado is EstadoVenta.APROBADA and self.cerrada_en is not None and self.cerrada_en > self.vence_en


@dataclass(frozen=True)
class Anulacion:
    """Una anulación en Webpay de una venta aprobada, a la misma tarjeta (ADR-027, decisión 239)."""

    id: uuid.UUID
    venta_id: uuid.UUID
    cargo_id: uuid.UUID
    participacion_id: uuid.UUID
    monto: int
    motivo: MotivoAnulacion
    estado: EstadoVenta
    solicitada_en: datetime
    buy_order: str
    pedido_linea_id: uuid.UUID | None = None
    hecha_en: datetime | None = None
    intentos: int = 0

    @property
    def hecha(self) -> bool:
        return self.estado is EstadoVenta.APROBADA


@dataclass(frozen=True)
class RespuestaTransaccion:
    """Lo que MATU lee de ``commit`` o ``status`` de Transbank, y nada más (D-62-9). Nunca el número de tarjeta."""

    status: str
    response_code: int | None
    amount: int | None
    authorization_code: str | None = None
    payment_type_code: str | None = None
    card_last4: str | None = None
    installments_number: int | None = None
    balance: int | None = None


@dataclass(frozen=True)
class RespuestaAnulacion:
    """Lo que MATU lee de ``refund``: el tipo, el código y el saldo."""

    type: str
    response_code: int | None
    balance: int | None = None
    nullified_amount: int | None = None


# --- Lo que trae Transbank ----------------------------------------------------------------------------------------


def aprobada(respuesta: RespuestaTransaccion) -> bool:
    """En venta normal, el commit aprobado es el cobro: AUTHORIZED con response_code 0. Después de una anulación,
    Transbank responde PARTIALLY_NULLIFIED o NULLIFIED: la venta se aprobó igual (prueba del 10-11, H4)."""
    return respuesta.response_code == 0 and respuesta.status in ("AUTHORIZED", "PARTIALLY_NULLIFIED", "NULLIFIED")


def final_sin_cobro(respuesta: RespuestaTransaccion) -> bool:
    """Transbank dice que la venta terminó sin cobro (FAILED o un response_code distinto de 0)."""
    if aprobada(respuesta):
        return False
    return respuesta.status in ("FAILED", "REVERSED") or (
        respuesta.response_code is not None and respuesta.response_code != 0
    )


def tipo_tarjeta(payment_type_code: str | None) -> TipoTarjeta:
    """Desde payment_type_code: VD débito, VP prepago, el resto crédito. Solo para el texto (12.4, caso 2)."""
    if payment_type_code == "VD":
        return TipoTarjeta.DEBITO
    if payment_type_code == "VP":
        return TipoTarjeta.PREPAGO
    return TipoTarjeta.CREDITO


def ultimos4(card_last4: str | None) -> str | None:
    """Los últimos 4 de la tarjeta, solo si son cuatro cifras (CHECK transaccion_ultimos4)."""
    if card_last4 is None:
        return None
    cifras = card_last4.strip()[-4:]
    return cifras if len(cifras) == 4 and cifras.isdigit() else None


def cuotas(installments_number: int | None) -> int | None:
    """installments_number (P5). Las cuotas las reparte el banco: MATU cobra una sola vez."""
    if installments_number is None or not 0 <= installments_number <= 48:
        return None
    return installments_number


def codigo_autorizacion(codigo: str | None) -> str | None:
    if codigo is None:
        return None
    codigo = codigo.strip()
    return codigo[:LARGO_CODIGO_AUTORIZACION] or None


def anulacion_hecha(respuesta: RespuestaAnulacion) -> bool:
    """REVERSED (la reversa del mismo día) o NULLIFIED con response_code 0."""
    return respuesta.type == "REVERSED" or (respuesta.type == "NULLIFIED" and respuesta.response_code == 0)


# --- Las reglas de D-62-4 -----------------------------------------------------------------------------------------


class Decision(StrEnum):
    RESPETAR = "respetar"
    RESPETAR_TARDIO = "respetar_tardio"
    ANULAR = "anular"


ESTADOS_QUE_SE_PAGAN = frozenset({"total_confirmado", "vencido"})


def decidir_aprobacion(
    *,
    estado_pedido: str,
    total: int,
    total_confirmado_en: datetime | None,
    total_vence_en: datetime | None,
    pagado_en: datetime | None,
    venta: Venta,
    ahora: datetime,
) -> Decision:
    """Qué hacer con un commit aprobado (D-62-4, reglas 2 y 3).

    Se respeta solo si el pedido sigue sin pagar, en total_confirmado o vencido, con el mismo total y el mismo
    total_confirmado_en de la venta. Si el total ya venció según el Reloj (o la fila dice vencido), es tardío. En
    cualquier otro caso se anula completo y el pedido no cambia."""
    if pagado_en is not None or estado_pedido not in ESTADOS_QUE_SE_PAGAN:
        return Decision.ANULAR
    if total != venta.monto or total_confirmado_en != venta.total_confirmado_en:
        return Decision.ANULAR
    vencio = estado_pedido == "vencido" or (total_vence_en is not None and total_vence_en <= ahora)
    return Decision.RESPETAR_TARDIO if vencio else Decision.RESPETAR


def puede_reintentar_commit(commit_intentado_en: datetime | None, ahora: datetime) -> bool:
    """Decisión 233: con la venta en autorizando, otro commit solo 10 segundos después del anterior."""
    return commit_intentado_en is None or ahora - commit_intentado_en >= ESPERA_ENTRE_COMMITS


# --- Resultados ---------------------------------------------------------------------------------------------------

_POR_MOTIVO = {
    MotivoCierre.NO_APROBADA: ResultadoPago.NO_APROBADO,
    MotivoCierre.USUARIO_SALIO: ResultadoPago.ABANDONADO,
    MotivoCierre.FORMULARIO_VENCIDO: ResultadoPago.TIEMPO_AGOTADO,
}


def resultado_de(venta: Venta) -> ResultadoPago | None:
    """El resultado de una venta (ResultadoPago, decisión 232). None para una venta con error, que nunca llegó a
    Webpay y no es un intento (IntentoPago)."""
    if venta.estado is EstadoVenta.INICIADA:
        return ResultadoPago.EN_WEBPAY
    if venta.estado is EstadoVenta.AUTORIZANDO:
        return ResultadoPago.PENDIENTE
    if venta.estado is EstadoVenta.APROBADA:
        if venta.anulada_por_pago_tardio:
            return ResultadoPago.ANULADO
        return ResultadoPago.APROBADO_TARDIO if venta.tardia else ResultadoPago.APROBADO
    if venta.estado is EstadoVenta.RECHAZADA:
        return _POR_MOTIVO.get(venta.motivo_cierre or MotivoCierre.NO_APROBADA, ResultadoPago.NO_APROBADO)
    return None


def en_curso(venta: Venta, ahora: datetime, vida: timedelta) -> bool:
    """D-62-4, regla 1 (decisión 230): una venta autorizando, o iniciada hace menos de VIDA_VENTA_WEBPAY."""
    if venta.estado is EstadoVenta.AUTORIZANDO:
        return True
    return venta.estado is EstadoVenta.INICIADA and ahora - venta.creado_en < vida


# --- La vuelta ----------------------------------------------------------------------------------------------------


def clasificar_retorno(
    token_ws: str | None, tbk_token: str | None, tbk_orden: str | None, tbk_sesion: str | None
) -> CasoRetorno:
    """Qué trajo la dirección (decisión 232). TBK_TOKEN gana sobre token_ws: la persona anuló o hubo un error en el
    formulario, y nunca se hace commit. Solo TBK_ORDEN_COMPRA y TBK_ID_SESION, juntos: se acabó el tiempo."""
    if tbk_token:
        return CasoRetorno.USUARIO_SALIO
    if token_ws:
        return CasoRetorno.COMMIT
    if tbk_orden and tbk_sesion:
        return CasoRetorno.FORMULARIO_VENCIDO
    return CasoRetorno.DESCONOCIDO


# --- Identificadores aleatorios -----------------------------------------------------------------------------------


def nuevo_buy_order() -> str:
    """26 caracteres hexadecimales al azar (el máximo de Transbank). No deriva de ningún id ni dato de nadie."""
    return secrets.token_hex(LARGO_BUY_ORDER // 2)


def nuevo_session_id() -> str:
    return secrets.token_hex(20)


def nueva_clave_pasarela() -> str:
    """transaccion_pasarela.idempotency_key: la clave de MATU para Transbank, distinta de la del cliente (decisión
    229)."""
    return secrets.token_urlsafe(32)


AzarEntero = Callable[[int], int]


def nueva_referencia(existentes: Collection[str], azar: AzarEntero = secrets.randbelow) -> str:
    """«Pedido {referencia}» (decisión 238): un número corto y legible, de 4 a 6 cifras, al azar y único dentro del
    grupo. No es el buy_order ni deriva de un id. Empieza con 4 cifras y alarga solo si no encuentra una libre."""
    for cifras in (4, 5, 6):
        desde, hasta = 10 ** (cifras - 1), 10**cifras
        for _ in range(20):
            candidata = str(desde + azar(hasta - desde))
            if candidata not in existentes:
                return candidata
    raise RuntimeError("no hay una referencia libre")
