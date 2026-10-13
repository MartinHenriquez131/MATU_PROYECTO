import sys

from transbank.common.integration_api_keys import IntegrationApiKeys
from transbank.common.integration_commerce_codes import IntegrationCommerceCodes
from transbank.webpay.webpay_plus.transaction import Transaction

# Ambiente de integración, comercio de captura diferida (credenciales públicas de Transbank)
tx = Transaction.build_for_integration(IntegrationCommerceCodes.WEBPAY_PLUS_DEFERRED, IntegrationApiKeys.WEBPAY)

# Uso: python poc_autorizacion.py [orden] [monto]
orden = sys.argv[1] if len(sys.argv) > 1 else "orden-poc-matu-001"
monto_total = int(sys.argv[2]) if len(sys.argv) > 2 else 69000  # Monto del caso 2 de la estrategia de pruebas
sesion = "sesion-poc-matu"
url_retorno = "http://localhost:8000/retorno-simulado"  # URL ficticia: solo sirve para ver el token

respuesta = tx.create(buy_order=orden, session_id=sesion, amount=monto_total, return_url=url_retorno)

print("--- 1. INICIO DE TRANSACCIÓN ---")
print(f"Orden {orden} por ${monto_total}")
print(f"Paga en este link: {respuesta['url']}?token_ws={respuesta['token']}")
print("Al volver, copia el token_ws de la barra de direcciones para el siguiente paso.")
