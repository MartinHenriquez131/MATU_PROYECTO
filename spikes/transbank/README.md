# Spike · Prueba de concepto de Transbank (captura diferida)

> **Estado al 13 de octubre de 2026: incompleta, se cierra en el sprint 1.**
> - **Caso 4 (débito): respondido.** El comercio de captura diferida solo ofrece tarjetas de crédito.
> - **Casos 1, 2, 3 y 5: pendientes.** Los dos intentos del 13 de octubre terminaron en `aborted` al confirmar el pago (`Transaction has an invalid finished state: aborted`). El pago no se completó en el navegador y la causa todavía no está identificada. Para diagnosticarlo está `poc_estado.py`.
> - La tarjeta de Trello "Liderar Prueba de Concepto Transbank" está en el Sprint 1.

Código de prueba del sprint 0. No forma parte del producto. Verifica el ADR-006 antes de construir el módulo de pagos: que Webpay Plus diferido permite **autorizar un monto, capturar por un monto menor y revertir**, que es lo que MATU necesita para cobrar el monto real de un pedido.

Los casos son los de la [estrategia de pruebas, sección 10](https://github.com/MartinHenriquez131/MATU/blob/main/docs/estrategia-pruebas.md). Los resultados se registran en [MATU · docs/pruebas-concepto/transbank.md](https://github.com/MartinHenriquez131/MATU/blob/main/docs/pruebas-concepto/transbank.md).

## Requisitos

- Python 3.10 o superior
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
