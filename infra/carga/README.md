# Carga básica con k6 (MATU-80)

La prueba de carga de la estrategia de pruebas, sección 2: **50 usuarios concurrentes en el flujo de pedido, con el percentil 95 bajo 800 ms**. Cada usuario virtual es una familia sintética que entra una vez y repite: ve el catálogo, arma un pedido de un pañal, confirma el total, lo paga y vuelve de Webpay.

| Archivo | Qué hace |
|---|---|
| `preparar_carga.py` | Deja en la base **local** las 50 familias de carga (`carga01@example.com` a `carga50@example.com`), cada una con su persona cuidada, su dirección y la autorización de pedidos, y un comercio ficticio propio, «Comercio de Carga», con el pañal de la demo y el stock al tope (9999). Usa los casos de uso de la semilla de la demo, como `matu_app`. Es idempotente: cada corrida vuelve a dejar el stock al tope |
| `pedido.js` | El script de k6. Umbrales: `http_req_duration` p(95) < 800 ms en total y en cada paso del flujo, `checks` > 99% y `http_req_failed` < 1%. Al final muestra los tiempos por paso |

## Dónde se corre, y dónde nunca

- **Sobre una copia local de la demo:** la API en tu equipo, con la semilla de la demo (`infra/semillas/demo.py`) y la preparación de carga, y `PASARELA_PAGO=falsa`.
- **Nunca contra Railway**, ni staging ni `matu-demo`: los dos tienen `ENTORNO=staging` y `PASARELA_PAGO=integracion`, así que cada pago abriría una venta en el ambiente de integración de Transbank, y la base es compartida.
- **Nunca contra Transbank.** La pasarela falsa aprueba la venta sola al volver, sin red.

Las guardas lo impiden:

- `preparar_carga.py` se niega a correr fuera de `ENTORNO=local` o `pruebas` y sin `PASARELA_PAGO=falsa` (la API tampoco admite la falsa en otro entorno).
- `preparar_carga.py` se detiene antes de conectar si `DATABASE_URL` no apunta a una **base local**: `localhost`, `127.0.0.1`, `::1` o un socket local. También revisa los parámetros `host` y `hostaddr` de la URL y, si la URL no trae host, `PGHOST` y `PGHOSTADDR`, y rechaza un servicio (`service` o `PGSERVICE`). Así, un `.env` con `ENTORNO=local` que apunte a Railway no siembra nada. El mensaje es fijo («La carga solo se prepara contra una base local.») y no muestra la URL, el host ni credenciales.
- `pedido.js` se niega a partir si `BASE_URL` no es `localhost` o `127.0.0.1`.

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

El `.env` local de la API necesita, además de lo de siempre: `ENTORNO=local`, `PASARELA_PAGO=falsa`, `CAPA3_HABILITADA=true` y un `DATABASE_URL` que apunte a la base de tu equipo (`localhost` o `127.0.0.1`), como `matu_app`.

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

Si un umbral falla, k6 termina con un código distinto de 0.

Antes de correrla por primera vez, `k6 inspect infra/carga/pedido.js` revisa la sintaxis y las opciones sin enviar nada.

## Cómo leer el resultado

Cada petición lleva la etiqueta `paso`, y cada paso tiene su umbral. RNF-05 (arquitectura, sección 2.2) pide el flujo de catálogo a pedido a pago bajo 800 ms en el percentil 95 con 50 usuarios concurrentes:

| Paso | Qué peticiones | Umbral | Por qué |
|---|---|---|---|
| `catalogo` | `GET /v1/catalogo` | p(95) < 800 ms | Parte del flujo de RNF-05 |
| `pedido` | `POST .../pedidos` y, si quedó uno sin pagar de otra corrida, `GET .../pedido-en-curso` y `POST .../cancelar` | p(95) < 800 ms | Parte del flujo de RNF-05 |
| `confirmar` | `POST /v1/pedidos/{id}/confirmar` | p(95) < 800 ms | Parte del flujo de RNF-05 |
| `pagar` | `POST /v1/pedidos/{id}/pagar` | p(95) < 800 ms | Parte del flujo de RNF-05 |
| `retorno` | `POST /v1/pagos/retorno` | p(95) < 800 ms | Con la pasarela falsa la venta se aprueba en memoria, sin red: mide solo el trabajo de MATU al cerrar el pago. La latencia de Transbank no se mide aquí |
| `entrar` | `POST /v1/sesiones`, `GET /v1/grupos` y `GET .../personas-cuidadas` | Ninguno (`max>=0`, que siempre se cumple) | No es parte de RNF-05: ocurre una vez por usuario, y argon2id es lento a propósito. Los 50 usuarios entran a la vez al partir. Se mide para verlo, sin exigirle la meta |
| total | Todas | p(95) < 800 ms | El umbral de la estrategia de pruebas. Incluye `entrar`, así que es más exigente que RNF-05 |

Al terminar, en vez del resumen de siempre, k6 muestra una tabla con la mediana (p50), el p95 y el p99 de cada paso y del total, y si cumple su umbral, más `checks`, `http_req_failed` y las iteraciones completas. Usa solo métricas agregadas: no muestra correos, tokens, ids ni cuerpos.

```
paso       meta p95  p50      p95       p99       umbral
---------  --------  -------  --------  --------  -----------
entrar     se mide   ...                          no se exige
catalogo   < 800 ms  ...                          cumple
pedido     < 800 ms  ...                          NO CUMPLE
...
total      < 800 ms  ...                          NO CUMPLE
```

**Qué significa que falle uno:**

- **Falla un paso del flujo** (`NO CUMPLE` en `catalogo`, `pedido`, `confirmar`, `pagar` o `retorno`): ese paso es el lento. Es por donde se empieza a buscar (consultas, bloqueos, trabajo por petición).
- **Fallan todos los pasos a la vez y con tiempos parecidos:** lo más probable es que la API esté encolando las peticiones (un solo proceso con 50 usuarios) o que la máquina sume latencia (Docker sobre WSL), más que un paso en particular. Conviene repetir con otra máquina antes de optimizar.
- **Falla solo el total y pasan los pasos:** lo que lo empuja es `entrar`, que no es parte de RNF-05.
- **Aparecen 503 `/errores/servicio-no-disponible` con `Retry-After`** (y en el log de la API `"evento": "pool_agotado"`): el pool de conexiones se llenó y la petición esperó más de `DB_POOL_TIMEOUT`. Es el hallazgo K1 de la corrida del 20-11, que antes salía como 500. El pool se configura con `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` y `DB_POOL_TIMEOUT` (por omisión 10, 20 y 10 s, en `.env.example`). Esa corrida no sirve para medir los pasos: mide la espera por una conexión.
- **`retorno` tarda segundos y crece de una corrida a la siguiente, sin 503 ni bloqueos:** era el hallazgo K2 de la corrida del 20-11. Con unas 300 ventas en la base, el costo estimado de las consultas de `transaccion_pasarela` (sus políticas RLS se expanden en más de 200 subplanes) superaba `jit_above_cost` y PostgreSQL compilaba cada una con JIT, de 2,5 a 7 s por consulta. Desde K2 cada conexión de la API y de las tareas abre su sesión con `jit=off` (`app/core/db.py`, `OPCIONES_SESION`), sin variables nuevas. Si vuelve a pasar, revisa que la API corra con ese código. Lo que queda es la planificación de esas mismas consultas, unos 150 ms cada una, que se decide aparte.
- **Fallan `checks` o `http_req_failed`:** el flujo no funcionó (cuentas sin preparar, stock agotado, la capa 3 apagada). Los tiempos de esa corrida no sirven.

**Dónde se anota y qué se decide:** el resultado se anota en `TESTER/` del repositorio MATU, en el informe de la corrida, con la tabla por paso, la máquina y cuántos procesos tenía la API. Con la medida por paso se decide una de dos cosas: optimizar el paso que falla, o, si la meta no es realista para el piloto, ajustar la meta de RNF-05 en la arquitectura. Esa decisión la toman Jorge y Martín, no el script.

## Qué queda en la base

Las 50 cuentas de carga, sus pedidos pagados y el «Comercio de Carga», que aparece en el catálogo de esa base local. No toca las familias de la demo. Las pruebas del backend vacían la base local (`test_aislamiento.py`): para volver a cargar, se repite el paso 1.
