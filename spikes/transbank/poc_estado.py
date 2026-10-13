import sys

from transbank.common.integration_api_keys import IntegrationApiKeys
from transbank.common.integration_commerce_codes import IntegrationCommerceCodes
from transbank.webpay.webpay_plus.transaction import Transaction

# Ambiente de integración, comercio de captura diferida (credenciales públicas de Transbank)
tx = Transaction.build_for_integration(IntegrationCommerceCodes.WEBPAY_PLUS_DEFERRED, IntegrationApiKeys.WEBPAY)

# Uso: python poc_estado.py TOKEN
# Consulta cómo terminó una transacción. Sirve para diagnosticar un pago que no quedó autorizado
token = sys.argv[1] if len(sys.argv) > 1 else "PEGA_AQUI_EL_TOKEN_WS"

print("--- ESTADO DE LA TRANSACCIÓN ---")
try:
    print(tx.status(token=token))
except Exception as e:
    print("Error:", e)
