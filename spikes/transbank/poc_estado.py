import sys

from transbank.common.integration_api_keys import IntegrationApiKeys
from transbank.common.integration_commerce_codes import IntegrationCommerceCodes
from transbank.webpay.webpay_plus.transaction import Transaction

# Ambiente de integración, comercio de captura diferida (credenciales públicas de Transbank)
tx = Transaction.build_for_integration(IntegrationCommerceCodes.WEBPAY_PLUS_DEFERRED, IntegrationApiKeys.WEBPAY)

# Uso: python poc_estado.py TOKEN
# Consulta cómo terminó una transacción. Sirve para diagnosticar un pago que no quedó autorizado
if len(sys.argv) < 2:
    sys.exit("Uso: python poc_estado.py TOKEN")
token = sys.argv[1]

print("--- ESTADO DE LA TRANSACCIÓN ---")
try:
    print(tx.status(token=token))
except Exception as e:
    print("Error:", e)
