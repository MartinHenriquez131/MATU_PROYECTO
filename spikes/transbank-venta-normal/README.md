# Spike · Webpay Plus en venta normal (MATU-62, ADR-027)

Código de prueba, no del producto. Sirve para correr a mano, **antes de construir el pago**, los casos de la [estrategia de pruebas, sección 10.2](https://github.com/MartinHenriquez131/MATU/blob/main/docs/estrategia-pruebas.md). El ADR-027 cambió la captura diferida por la venta normal, así que los scripts de `spikes/transbank` (ADR-006) ya no aplican. Los resultados van en [MATU · docs/pruebas-concepto/transbank.md](https://github.com/MartinHenriquez131/MATU/blob/main/docs/pruebas-concepto/transbank.md).

## Requisitos

- Python 3.12 y `pip install -r requirements.txt` (transbank-sdk 6.1.0)
- Ambiente de **integración** de Transbank, con las credenciales públicas del comercio de venta normal. No hay claves propias.

## Tarjetas de prueba (publicadas por Transbank)

| Tipo | Número | Datos |
|---|---|---|
| Crédito AMEX | `3700 0000 0002 032` | CVV `1234`, cualquier vencimiento futuro. En este comercio, la VISA (`4051 8856 0044 6623`) y la Mastercard (`5186 0595 5959 0568`) de crédito de prueba se rechazan con «Intenta pagar con otra tarjeta» (10-11) |
| Débito Redcompra | `4051 8842 3993 7763` | Sin CVV |

En el banco simulado: RUT `11.111.111-1` y clave `123`, y aceptar.

Nunca una tarjeta real.

## Cómo se corre

Usa dos ventanas de Git Bash, las dos en esta carpeta:
1. **En la ventana A:** `python retorno.py`. Queda esperando y muestra el token cuando Webpay vuelve.
2. **En la ventana B:** los pasos de cada caso con `vn.py`.

| Comando | Para qué |
|---|---|
| `python vn.py crear ORDEN MONTO` | Crea la transacción y entrega el enlace de pago |
| `python vn.py confirmar TOKEN` | Confirma el pago al volver (`commit`) |
| `python vn.py anular TOKEN MONTO` | Anulación parcial o total (`refund`) |
| `python vn.py estado TOKEN` | Muestra cómo quedó la transacción |

Si la ventana A dice **ANULADO**, el pago se canceló en Webpay. Empieza el caso con una orden nueva.

## Los casos (estrategia de pruebas, 10.2)

| # | Pasos | Esperado |
|---|---|---|
| 1 · Crédito | `crear vn-102 57460`, pagar con crédito y `confirmar` | `AUTHORIZED` por $57.460, `payment_type_code` VN |
| 2 · Débito | `crear vn-101 57460`, pagar con débito y `confirmar` | `AUTHORIZED` por $57.460, `payment_type_code` VD |
| 3a · Anulación parcial con crédito | `anular TOKEN_102 8990` y `estado TOKEN_102` | `type: NULLIFIED`, se devuelven $8.990 y el saldo baja a $48.470 |
| 3b · Anulación parcial con débito | `anular TOKEN_101 8990` y `estado TOKEN_101` | Lo mismo que 3a. **Si falla, es el riesgo del ADR-027** |
| 4 · Retorno duplicado | `confirmar TOKEN_102` por segunda vez | Un solo cobro. Se registra si falla o si repite la respuesta |

Guarda la salida de la consola de cada paso. Es la evidencia, y no lleva datos personales.
