import sys

from transbank.common.integration_api_keys import IntegrationApiKeys
from transbank.common.integration_commerce_codes import IntegrationCommerceCodes
from transbank.webpay.webpay_plus.transaction import Transaction

# Ambiente de integración, comercio de captura diferida (credenciales públicas de Transbank)
tx = Transaction.build_for_integration(IntegrationCommerceCodes.WEBPAY_PLUS_DEFERRED, IntegrationApiKeys.WEBPAY)

# Uso: python poc_reversa.py TOKEN [MONTO]
# Caso 3: revertir una autorización que no se capturó
token = sys.argv[1] if len(sys.argv) > 1 else "PEGA_AQUI_EL_TOKEN_WS"
monto_a_revertir = int(sys.argv[2]) if len(sys.argv) > 2 else 69000

print("--- 4. REVERSA ---")
respuesta = tx.refund(token=token, amount=monto_a_revertir)
print(respuesta)
