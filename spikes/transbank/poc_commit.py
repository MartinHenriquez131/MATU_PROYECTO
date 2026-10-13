import sys

from transbank.common.integration_api_keys import IntegrationApiKeys
from transbank.common.integration_commerce_codes import IntegrationCommerceCodes
from transbank.webpay.webpay_plus.transaction import Transaction

# Ambiente de integración, comercio de captura diferida (credenciales públicas de Transbank)
tx = Transaction.build_for_integration(IntegrationCommerceCodes.WEBPAY_PLUS_DEFERRED, IntegrationApiKeys.WEBPAY)

# Uso: python poc_commit.py TOKEN
# Ejecutarlo dos veces con el mismo token es el caso 5 (retorno recibido dos veces)
token = sys.argv[1] if len(sys.argv) > 1 else "PEGA_AQUI_EL_TOKEN_WS"

print("--- 2. COMMIT (CONFIRMACIÓN DE LA RETENCIÓN) ---")
respuesta = tx.commit(token=token)
print(respuesta)
print("\nGuarda el 'authorization_code' y el 'buy_order' para la captura.")
