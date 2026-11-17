# Carga básica con k6 (MATU-80)

La prueba de carga de la estrategia de pruebas, sección 2: **50 usuarios concurrentes en el flujo de pedido, con el percentil 95 bajo 800 ms**. Cada usuario virtual es una familia sintética que entra una vez y repite: ve el catálogo, arma un pedido de un pañal, confirma el total, lo paga y vuelve de Webpay.

| Archivo | Qué hace |
|---|---|
| `preparar_carga.py` | Deja en la base **local** las 50 familias de carga (`carga01@example.com` a `carga50@example.com`), cada una con su persona cuidada, su dirección y la autorización de pedidos, y un comercio ficticio propio, «Comercio de Carga», con el pañal de la demo y el stock al tope (9999). Usa los casos de uso de la semilla de la demo, como `matu_app`. Es idempotente: cada corrida vuelve a dejar el stock al tope |
| `pedido.js` | El script de k6. Umbrales: `http_req_duration` p(95) < 800 ms, `checks` > 99% y `http_req_failed` < 1% |

## Dónde se corre, y dónde nunca

- **Sobre una copia local de la demo:** la API en tu equipo, con la semilla de la demo (`infra/semillas/demo.py`) y la preparación de carga, y `PASARELA_PAGO=falsa`.
- **Nunca contra Railway**, ni staging ni `matu-demo`: los dos tienen `ENTORNO=staging` y `PASARELA_PAGO=integracion`, así que cada pago abriría una venta en el ambiente de integración de Transbank, y la base es compartida.
- **Nunca contra Transbank.** La pasarela falsa aprueba la venta sola al volver, sin red.

Las dos guardas lo impiden: `preparar_carga.py` se niega a correr fuera de `ENTORNO=local` o `pruebas` y sin `PASARELA_PAGO=falsa` (la API tampoco admite la falsa en otro entorno), y `pedido.js` se niega a partir si `BASE_URL` no es `localhost` o `127.0.0.1`.

## Variables

Se definen en la terminal de quien corre la carga. **Nunca se escriben en el repositorio ni en el chat.**

| Variable | Para | Qué es |
|---|---|---|
| `SEMILLA_CONTRASENA` | `preparar_carga.py` | La contraseña de las cuentas de carga, de 8 a 128 caracteres. Inventa una para esta corrida |
| `CARGA_CONTRASENA` | `pedido.js` | La misma contraseña. Obligatoria |
| `BASE_URL` | `pedido.js` | La API local. Por omisión `http://localhost:8000` |
| `CARGA_USUARIOS` | `pedido.js` | Usuarios virtuales. Por omisión 50, tantos como cuentas preparadas |
| `CARGA_DURACION` | `pedido.js` | Por omisión `3m`. La estrategia da 15 minutos para toda la prueba |
| `CARGA_COMERCIO` | `pedido.js` | Por omisión `Comercio de Carga` |

El `.env` local de la API necesita, además de lo de siempre: `ENTORNO=local`, `PASARELA_PAGO=falsa` y `CAPA3_HABILITADA=true`.

## Cómo correrla

Desde la raíz del repositorio, con la base levantada (`docker compose -f infra/docker-compose.yml up -d`), migrada (`alembic upgrade head`) y el entorno virtual de `backend/` activo:

```bash
# 1. Las cuentas y el stock (también después de cada corrida, para reponer el stock)
export SEMILLA_CONTRASENA='<una contraseña inventada>'
python infra/carga/preparar_carga.py --cuentas 50

# 2. La API, con un solo proceso: la pasarela falsa vive en memoria y la vuelta de Webpay
#    tiene que llegar al mismo proceso que abrió la venta
cd backend && uvicorn app.main:app --port 8000 --workers 1

# 3. En otra terminal, la carga
export CARGA_CONTRASENA="$SEMILLA_CONTRASENA"
k6 run infra/carga/pedido.js
```

El resumen de k6 dice si se cumplió cada umbral (`✓` o `✗`) y separa los tiempos por paso con la etiqueta `paso` (`entrar`, `catalogo`, `pedido`, `confirmar`, `pagar` y `retorno`). Si un umbral falla, k6 termina con un código distinto de 0.

Antes de correrla por primera vez, `k6 inspect infra/carga/pedido.js` revisa la sintaxis y las opciones sin enviar nada.

## Qué queda en la base

Las 50 cuentas de carga, sus pedidos pagados y el «Comercio de Carga», que aparece en el catálogo de esa base local. No toca las familias de la demo. Las pruebas del backend vacían la base local (`test_aislamiento.py`): para volver a cargar, se repite el paso 1.
