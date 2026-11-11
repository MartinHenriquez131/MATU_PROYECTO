"""PasarelaTransbank: el adaptador de Webpay Plus, venta normal, con el SDK oficial (transbank-sdk 6.1, el del spike
de MATU-62, PR #77). Detrás del puerto PasarelaWebpay: el dominio y los casos de uso no lo conocen.

- Integración: el código de comercio y la llave públicas que publica el SDK (IntegrationCommerceCodes.WEBPAY_PLUS e
  IntegrationApiKeys.WEBPAY). No son secretos de MATU y no se copian al código: se leen del SDK.
- Producción: WEBPAY_CODIGO_COMERCIO y WEBPAY_LLAVE desde el entorno (pydantic-settings), nunca del código.

**MATU nunca recibe ni guarda datos de tarjeta**: de cada respuesta se leen solo el estado, el código de respuesta, el
monto, el código de autorización, el tipo de pago, los últimos 4 (que Transbank ya entrega enmascarados), las cuotas y
el saldo (D-62-9). El resto del diccionario se descarta sin guardarlo.

Errores: el mensaje de Transbank o de requests nunca sube (puede traer el token en la URL): se traduce a
PasarelaNoDisponible (red, tiempo agotado, 5xx) o PasarelaRechazo (4xx), con mensaje fijo y sin la causa. El log de
urllib3 queda en WARNING: en DEBUG escribiría la ruta del commit, que lleva el token.
"""

import logging
from typing import Any

from app.modules.payments.application.ports import InicioVenta, PasarelaNoDisponible, PasarelaRechazo
from app.modules.payments.domain.venta import RespuestaAnulacion, RespuestaTransaccion

# La ruta de commit, status y refund lleva el token: urllib3 no la escribe nunca
logging.getLogger("urllib3").setLevel(logging.WARNING)

# Segundos de espera por cada llamada a Transbank. El SDK trae 600 por omisión
TIEMPO_ESPERA_S = 15

URL_INTEGRACION = "https://webpay3gint.transbank.cl/webpayserver/initTransaction"
URL_PRODUCCION = "https://webpay3g.transbank.cl/webpayserver/initTransaction"


def _entero(valor: Any) -> int | None:
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    return None


def _texto(valor: Any) -> str | None:
    return valor if isinstance(valor, str) else None


def _transaccion(respuesta: Any) -> RespuestaTransaccion:
    if not isinstance(respuesta, dict):
        raise PasarelaNoDisponible()
    tarjeta = respuesta.get("card_detail")
    return RespuestaTransaccion(
        status=_texto(respuesta.get("status")) or "",
        response_code=_entero(respuesta.get("response_code")),
        amount=_entero(respuesta.get("amount")),
        authorization_code=_texto(respuesta.get("authorization_code")),
        payment_type_code=_texto(respuesta.get("payment_type_code")),
        card_last4=_texto(tarjeta.get("card_number")) if isinstance(tarjeta, dict) else None,
        installments_number=_entero(respuesta.get("installments_number")),
        balance=_entero(respuesta.get("balance")),
    )


class PasarelaTransbank:
    def __init__(self, *, produccion: bool, codigo_comercio: str | None = None, llave: str | None = None) -> None:
        from transbank.common.integration_api_keys import IntegrationApiKeys
        from transbank.common.integration_commerce_codes import IntegrationCommerceCodes
        from transbank.common.integration_type import IntegrationType
        from transbank.common.options import WebpayOptions
        from transbank.webpay.webpay_plus.transaction import Transaction

        if produccion:
            if not codigo_comercio or not llave:
                raise ValueError("faltan WEBPAY_CODIGO_COMERCIO y WEBPAY_LLAVE")
            opciones = WebpayOptions(codigo_comercio, llave, IntegrationType.LIVE, TIEMPO_ESPERA_S)
        else:
            opciones = WebpayOptions(
                IntegrationCommerceCodes.WEBPAY_PLUS, IntegrationApiKeys.WEBPAY, IntegrationType.TEST, TIEMPO_ESPERA_S
            )
        self._tx = Transaction(opciones)
        self._produccion = produccion

    def __repr__(self) -> str:
        # Nunca el código de comercio ni la llave
        return f"PasarelaTransbank(produccion={self._produccion})"

    @property
    def url_formulario(self) -> str:
        return URL_PRODUCCION if self._produccion else URL_INTEGRACION

    @property
    def pago_de_prueba(self) -> bool:
        return not self._produccion

    def _llamar(self, operacion: Any, *argumentos: Any) -> Any:
        from transbank.error.transbank_error import TransbankError

        try:
            return operacion(*argumentos)
        except TransbankError as error:
            codigo = error.code if isinstance(error.code, int) else 0
            if 400 <= codigo < 500:
                raise PasarelaRechazo() from None
            raise PasarelaNoDisponible() from None
        except Exception:  # noqa: BLE001 - red, tiempo agotado o una respuesta que no es JSON: sin el mensaje
            raise PasarelaNoDisponible() from None

    def crear(self, buy_order: str, session_id: str, monto: int, return_url: str) -> InicioVenta:
        respuesta = self._llamar(self._tx.create, buy_order, session_id, monto, return_url)
        if not isinstance(respuesta, dict):
            raise PasarelaNoDisponible()
        url, token = _texto(respuesta.get("url")), _texto(respuesta.get("token"))
        if not url or not token:
            raise PasarelaNoDisponible()
        return InicioVenta(url=url, token=token)

    def confirmar(self, token: str) -> RespuestaTransaccion:
        return _transaccion(self._llamar(self._tx.commit, token))

    def consultar(self, token: str) -> RespuestaTransaccion:
        return _transaccion(self._llamar(self._tx.status, token))

    def anular(self, token: str, monto: int) -> RespuestaAnulacion:
        respuesta = self._llamar(self._tx.refund, token, monto)
        if not isinstance(respuesta, dict):
            raise PasarelaNoDisponible()
        return RespuestaAnulacion(
            type=_texto(respuesta.get("type")) or "",
            response_code=_entero(respuesta.get("response_code")),
            balance=_entero(respuesta.get("balance")),
            nullified_amount=_entero(respuesta.get("nullified_amount")),
        )
