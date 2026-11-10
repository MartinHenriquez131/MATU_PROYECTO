"""Spike MATU-62 · Webpay Plus en venta normal (ADR-027), contra el ambiente de integración.

No es código del producto. Sirve para correr a mano los casos de la estrategia de pruebas, sección 10.2.

Uso, desde esta carpeta:
    python vn.py crear ORDEN MONTO      crea la transacción e imprime el enlace de pago
    python vn.py confirmar TOKEN        confirma (commit) al volver del pago
    python vn.py anular TOKEN MONTO     anulación parcial o total (refund)
    python vn.py estado TOKEN           muestra cómo quedó la transacción

Usa las credenciales públicas de integración de Transbank (comercio de venta normal). No hay claves propias.
"""

import json
import sys

from transbank.common.integration_api_keys import IntegrationApiKeys
from transbank.common.integration_commerce_codes import IntegrationCommerceCodes
from transbank.webpay.webpay_plus.transaction import Transaction

tx = Transaction.build_for_integration(
    IntegrationCommerceCodes.WEBPAY_PLUS, IntegrationApiKeys.WEBPAY
)
URL_RETORNO = "http://localhost:8000/retorno"  # la recibe retorno.py
CAMPOS = (
    "vci",
    "amount",
    "status",
    "buy_order",
    "card_detail",
    "transaction_date",
    "authorization_code",
    "payment_type_code",
    "response_code",
    "installments_number",
    "balance",
    "type",
    "nullified_amount",
)


def mostrar(titulo: str, respuesta: dict) -> None:
    print(f"--- {titulo} ---")
    print(
        json.dumps(
            {k: v for k, v in respuesta.items() if k in CAMPOS},
            ensure_ascii=False,
            indent=2,
        )
    )


def main(args: list[str]) -> None:
    if len(args) < 2:
        sys.exit(__doc__)
    accion = args[0]
    if accion == "crear" and len(args) == 3:
        orden, monto = args[1], int(args[2])
        r = tx.create(
            buy_order=orden,
            session_id="sesion-spike-matu",
            amount=monto,
            return_url=URL_RETORNO,
        )
        print(f"--- CREAR · orden {orden} por ${monto:,}".replace(",", ".") + " ---")
        print(f"Abre este enlace en el navegador: {r['url']}?token_ws={r['token']}")
    elif accion == "confirmar" and len(args) == 2:
        mostrar("CONFIRMAR (commit)", tx.commit(token=args[1]))
    elif accion == "anular" and len(args) == 3:
        mostrar(
            f"ANULAR ${int(args[2]):,}".replace(",", "."),
            tx.refund(token=args[1], amount=int(args[2])),
        )
    elif accion == "estado" and len(args) == 2:
        mostrar("ESTADO", tx.status(token=args[1]))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
