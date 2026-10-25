# Spike · Prueba de concepto de Transbank (captura diferida)

> **Estado al 25 de octubre de 2026: completa.** Los cinco casos tienen su resultado real en el ambiente de integración (24/10, y el caso 2 repetido el 25/10 con capturas).
> - **Casos 1, 2 y 3: cumplen.** La captura diferida cobra el monto real (de $69.000 autorizados se capturan $51.340) y revierte sin cobrar.
> - **Caso 4 (débito):** el comercio de captura diferida solo ofrece crédito. Decisión del 24/10: MATU no limita las formas de pago, y el débito usa el plan B del ADR-006.
> - **Caso 5: un solo cobro.** El segundo commit **no falla**: devuelve la transacción ya capturada. El módulo de pagos detecta el duplicado por su propio registro del token.
> - Resultados, evidencia y capturas: [MATU · docs/pruebas-concepto/transbank.md](https://github.com/MartinHenriquez131/MATU/blob/main/docs/pruebas-concepto/transbank.md).

Código de prueba del sprint 0. No forma parte del producto. Verifica el ADR-006 antes de construir el módulo de pagos: que Webpay Plus diferido permite **autorizar un monto, capturar por un monto menor y revertir**, que es lo que MATU necesita para cobrar el monto real de un pedido.

Los casos son los de la [estrategia de pruebas, sección 10](https://github.com/MartinHenriquez131/MATU/blob/main/docs/estrategia-pruebas.md). Los resultados se registran en [MATU · docs/pruebas-concepto/transbank.md](https://github.com/MartinHenriquez131/MATU/blob/main/docs/pruebas-concepto/transbank.md).

## Requisitos

- Python 3.12, la misma versión del backend
- `pip install -r requirements.txt` (transbank-sdk 6.1.0)

Usa el ambiente de **integración** de Transbank con las credenciales públicas de captura diferida (código de comercio 597055555540). No hay claves propias en el código.

## Datos de prueba

- En Webpay: tarjeta VISA de crédito `4051 8856 0044 6623`, CVV `123`, cualquier fecha de vencimiento futura
- En la página del banco simulado: RUT `11.111.111-1` (o `111111111`) y clave `123`, y aceptar la compra

## Scripts

Todos se ejecutan desde esta carpeta, en Git Bash. Los datos van como argumentos, no hay que editar los archivos.

| Script | Uso | Para qué |
|---|---|---|
| `poc_autorizacion.py` | `python poc_autorizacion.py ORDEN [MONTO]` | Crea la transacción e imprime el enlace de pago. Monto por defecto $69.000 |
| `poc_commit.py` | `python poc_commit.py TOKEN` | Confirma la retención. Entrega el `authorization_code` |
| `poc_captura.py` | `python poc_captura.py TOKEN CODIGO ORDEN [MONTO]` | Captura. Monto por defecto $51.340 |
| `poc_reversa.py` | `python poc_reversa.py TOKEN [MONTO]` | Revierte una autorización sin capturar |
| `poc_estado.py` | `python poc_estado.py TOKEN` | Muestra cómo terminó una transacción |

## Los cinco casos

Cada caso usa una orden nueva. Después de pagar, el navegador vuelve a `localhost:8000/retorno-simulado`. La página no carga, y es esperado: el `token_ws` queda en la barra de direcciones. **Si la dirección dice `TBK_TOKEN`, el pago se anuló y hay que empezar de nuevo.** El commit se hace apenas se vuelve del pago.

| Caso | Pasos | Resultado esperado |
|---|---|---|
| 1 · Capturar el mismo monto | `poc_autorizacion.py orden-poc-101` → pagar → `poc_commit.py TOKEN` → `poc_captura.py TOKEN CODIGO orden-poc-101 69000` | Captura aprobada por $69.000 |
| 2 · Capturar menos | `poc_autorizacion.py orden-poc-102` → pagar → commit → `poc_captura.py TOKEN CODIGO orden-poc-102` | Captura aprobada por $51.340 |
| 3 · Revertir sin capturar | `poc_autorizacion.py orden-poc-103` → pagar → commit → `poc_reversa.py TOKEN` | `type: NULLIFIED` o `REVERSED`, nada cobrado |
| 4 · Débito | Abrir el enlace de pago y revisar los medios disponibles | **Respondido:** solo crédito |
| 5 · Retorno recibido dos veces | En el caso 1, ejecutar `poc_commit.py TOKEN` una segunda vez | El segundo commit falla y hay un solo cobro |

Se guarda la salida de la consola de cada paso. Es la evidencia.

**Para capturar el `token_ws` sin depender de la barra de direcciones:** basta un servidor local mínimo en `localhost:8000` que registre los parámetros del retorno, que llegan por GET. Así se hizo el 24/10, sin ningún anulado.

**Si el commit responde `aborted`:** antes de reintentar, ejecutar `python poc_estado.py TOKEN` y guardar su salida. Muestra si Webpay registró el pago y en qué estado quedó, que es lo que falta para identificar la causa.
