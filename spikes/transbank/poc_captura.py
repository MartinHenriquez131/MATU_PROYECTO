import sys

from transbank.common.integration_api_keys import IntegrationApiKeys
from transbank.common.integration_commerce_codes import IntegrationCommerceCodes
from transbank.webpay.webpay_plus.transaction import Transaction

# Ambiente de integración, comercio de captura diferida (credenciales públicas de Transbank)
tx = Transaction.build_for_integration(IntegrationCommerceCodes.WEBPAY_PLUS_DEFERRED, IntegrationApiKeys.WEBPAY)

# Uso: python poc_captura.py TOKEN CODIGO_AUTORIZACION ORDEN [MONTO]
# Caso 1: capturar el mismo monto autorizado. Caso 2: capturar menos (por defecto $51.340 de $69.000)
if len(sys.argv) < 4:
    sys.exit("Uso: python poc_captura.py TOKEN CODIGO_AUTORIZACION ORDEN [MONTO]")
token, codigo_autorizacion, orden = sys.argv[1], sys.argv[2], sys.argv[3]
monto_a_capturar = int(sys.argv[4]) if len(sys.argv) > 4 else 51340

print("--- 3. CAPTURA ---")
respuesta = tx.capture(
    token=token, buy_order=orden, authorization_code=codigo_autorizacion, capture_amount=monto_a_capturar
)
print(respuesta)
