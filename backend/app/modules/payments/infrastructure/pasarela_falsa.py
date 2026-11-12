"""PasarelaFalsa: Webpay Plus en venta normal, en memoria y sin red (arquitectura 12.4; informe de Martín del 10-11).

Responde como Transbank en lo que MATU usa:

- create entrega un token de 64 caracteres y la url del formulario.
- commit de una venta pagada: AUTHORIZED con response_code 0, el código de autorización, VN (crédito) o VD (débito),
  los últimos 4 y las cuotas. Rechazada por el banco: FAILED con response_code distinto de 0. **Un commit repetido no
  falla: devuelve la misma transacción** (caso 4 de la estrategia 10.2, y H4).
- commit de un token que nadie pagó (la persona salió o se le acabó el tiempo): error (PasarelaRechazo), como el 422
  de Transbank.
- refund: REVERSED si anula el total la primera vez, NULLIFIED si es parcial; el saldo baja. Después de una anulación
  parcial, status responde **PARTIALLY_NULLIFIED con el balance** (H4); anulado todo, NULLIFIED con balance 0. Nunca
  devuelve más que el saldo (PasarelaRechazo).
- ``caida = True`` hace que toda llamada lance PasarelaNoDisponible (casos 6 y 7: Webpay no responde).

Las pruebas simulan el formulario con ``pagar(token, ...)``. Con ``aprueba_sola`` (el modo local, PASARELA_PAGO=falsa)
un commit sin ``pagar`` aprueba con una tarjeta de crédito sintética. Nunca guarda un número de tarjeta: solo los 4
últimos sintéticos que la prueba le da. ``llamadas`` registra el nombre de cada operación, sin valores.
"""

import secrets
from dataclasses import dataclass, field

from app.modules.payments.application.ports import InicioVenta, PasarelaNoDisponible, PasarelaRechazo
from app.modules.payments.domain.venta import RespuestaAnulacion, RespuestaTransaccion

URL_FALSA = "https://webpay.falsa.invalid/webpayserver/initTransaction"


@dataclass
class _Pago:
    aprobada: bool
    payment_type_code: str
    ultimos4: str
    cuotas: int


@dataclass
class _Transaccion:
    buy_order: str
    session_id: str
    monto: int
    pago: _Pago | None = None
    confirmada: RespuestaTransaccion | None = None
    anulado: int = 0
    anulaciones: list[int] = field(default_factory=list)
    codigo: str = ""

    @property
    def saldo(self) -> int:
        return self.monto - self.anulado


class PasarelaFalsa:
    def __init__(self, *, aprueba_sola: bool = False) -> None:
        self.aprueba_sola = aprueba_sola
        self.caida = False
        self.transacciones: dict[str, _Transaccion] = {}
        self.llamadas: list[str] = []

    def __repr__(self) -> str:
        # Nunca los tokens ni los montos
        return f"PasarelaFalsa(transacciones={len(self.transacciones)})"

    @property
    def url_formulario(self) -> str:
        return URL_FALSA

    @property
    def pago_de_prueba(self) -> bool:
        return True

    def _llamar(self, operacion: str) -> None:
        self.llamadas.append(operacion)
        if self.caida:
            raise PasarelaNoDisponible()

    def _transaccion(self, token: str) -> _Transaccion:
        tx = self.transacciones.get(token)
        if tx is None:
            raise PasarelaRechazo()
        return tx

    # --- Lo que hace la persona en el formulario de Webpay (solo pruebas)

    def pagar(
        self, token: str, *, aprobada: bool = True, debito: bool = False, ultimos4: str = "2032", cuotas: int = 0
    ) -> None:
        self._transaccion(token).pago = _Pago(
            aprobada=aprobada, payment_type_code="VD" if debito else "VN", ultimos4=ultimos4, cuotas=cuotas
        )

    def token_de(self, buy_order: str) -> str:
        return next(t for t, tx in self.transacciones.items() if tx.buy_order == buy_order)

    # --- El puerto PasarelaWebpay

    def crear(self, buy_order: str, session_id: str, monto: int, return_url: str) -> InicioVenta:
        self._llamar("create")
        if monto <= 0 or not buy_order or len(buy_order) > 26 or not session_id or len(session_id) > 61:
            raise PasarelaRechazo()
        token = secrets.token_hex(32)
        self.transacciones[token] = _Transaccion(buy_order=buy_order, session_id=session_id, monto=monto)
        return InicioVenta(url=URL_FALSA, token=token)

    def confirmar(self, token: str) -> RespuestaTransaccion:
        self._llamar("commit")
        tx = self._transaccion(token)
        if tx.confirmada is not None:
            # H4: un commit repetido devuelve la misma transacción, con un solo cobro
            return tx.confirmada
        if tx.pago is None:
            if not self.aprueba_sola:
                raise PasarelaRechazo()
            tx.pago = _Pago(aprobada=True, payment_type_code="VN", ultimos4="0000", cuotas=0)
        if tx.pago.aprobada:
            tx.codigo = f"{secrets.randbelow(10**6):06d}"
            tx.confirmada = RespuestaTransaccion(
                status="AUTHORIZED",
                response_code=0,
                amount=tx.monto,
                authorization_code=tx.codigo,
                payment_type_code=tx.pago.payment_type_code,
                card_last4=tx.pago.ultimos4,
                installments_number=tx.pago.cuotas,
                balance=tx.monto,
            )
        else:
            tx.confirmada = RespuestaTransaccion(status="FAILED", response_code=-1, amount=tx.monto)
        return tx.confirmada

    def consultar(self, token: str) -> RespuestaTransaccion:
        self._llamar("status")
        tx = self._transaccion(token)
        if tx.confirmada is None:
            return RespuestaTransaccion(status="INITIALIZED", response_code=None, amount=tx.monto)
        if tx.confirmada.status != "AUTHORIZED":
            return tx.confirmada
        status = "AUTHORIZED" if tx.anulado == 0 else ("NULLIFIED" if tx.saldo == 0 else "PARTIALLY_NULLIFIED")
        return RespuestaTransaccion(
            status=status,
            response_code=0,
            amount=tx.monto,
            authorization_code=tx.codigo,
            payment_type_code=tx.confirmada.payment_type_code,
            card_last4=tx.confirmada.card_last4,
            installments_number=tx.confirmada.installments_number,
            balance=tx.saldo,
        )

    def anular(self, token: str, monto: int) -> RespuestaAnulacion:
        self._llamar("refund")
        tx = self._transaccion(token)
        if tx.confirmada is None or tx.confirmada.status != "AUTHORIZED" or monto <= 0 or monto > tx.saldo:
            raise PasarelaRechazo()
        total = monto == tx.monto and tx.anulado == 0
        tx.anulado += monto
        tx.anulaciones.append(monto)
        if total:
            return RespuestaAnulacion(type="REVERSED", response_code=None, balance=0, nullified_amount=monto)
        return RespuestaAnulacion(type="NULLIFIED", response_code=0, balance=tx.saldo, nullified_amount=monto)

    # --- Para las pruebas: lo cobrado de verdad, por token

    def cobrado(self, token: str) -> int:
        tx = self._transaccion(token)
        if tx.confirmada is None or tx.confirmada.status != "AUTHORIZED":
            return 0
        return tx.monto - tx.anulado
