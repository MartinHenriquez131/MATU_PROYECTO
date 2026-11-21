# Carga básica con k6 (MATU-80)

La prueba de carga de la estrategia de pruebas, sección 2, contra la meta de RNF-05 (arquitectura, sección 2.2). Cada usuario virtual es una familia sintética que entra una vez y repite: ve el catálogo, arma un pedido de un pañal, confirma el total, lo paga y vuelve de Webpay.

La meta tiene dos modos, y `CARGA_META` elige cuál exige el script:

| Modo | Usuarios por omisión | Qué se exige | Qué se informa |
|---|---|---|---|
| `piloto` (por omisión) | 10 | 0 % de fallos (`http_req_failed` `rate==0`) y la **mediana bajo 800 ms en cada paso** (`med<800`), del catálogo al retorno del pago | El p95 y el p99 de cada paso y del total, sin exigirlos |
| `produccion` | 50 | El **p95 bajo 800 ms en cada paso y en total** (`p(95)<800`) y menos de 1 % de fallos (`rate<0.01`), en un equipo representativo | La mediana y el p99 |

En los dos modos `checks` tiene que pasar del 99 %, y `entrar` se mide sin exigirle la meta.

| Archivo | Qué hace |
|---|---|
| `preparar_carga.py` | Deja en la base **local** las 50 familias de carga (`carga01@example.com` a `carga50@example.com`), cada una con su persona cuidada, su dirección y la autorización de pedidos, y un comercio ficticio propio, «Comercio de Carga», con el pañal de la demo y el stock al tope (9999). Usa los casos de uso de la semilla de la demo, como `matu_app`. Es idempotente: cada corrida vuelve a dejar el stock al tope |
| `pedido.js` | El script de k6. Exige la meta de `CARGA_META`: en `piloto`, `med<800` en cada paso del flujo y `http_req_failed` `rate==0`; en `produccion`, `p(95)<800` en total y en cada paso y `http_req_failed` < 1%. En los dos, `checks` > 99%. Al final muestra los tiempos por paso contra la meta activa |

## Dónde se corre, y dónde nunca

- **Sobre una copia local de la demo:** la API en tu equipo, con la semilla de la demo (`infra/semillas/demo.py`) y la preparación de carga, y `PASARELA_PAGO=falsa`.
- **Nunca contra Railway**, ni staging ni `matu-demo`: los dos tienen `ENTORNO=staging` y `PASARELA_PAGO=integracion`, así que cada pago abriría una venta en el ambiente de integración de Transbank, y la base es compartida.
- **Nunca contra Transbank.** La pasarela falsa aprueba la venta sola al volver, sin red.

Las guardas lo impiden:

- `preparar_carga.py` se niega a correr fuera de `ENTORNO=local` o `pruebas` y sin `PASARELA_PAGO=falsa` (la API tampoco admite la falsa en otro entorno).
- `preparar_carga.py` se detiene antes de conectar si `DATABASE_URL` no apunta a una **base local**: `localhost`, `127.0.0.1`, `::1` o un socket local. También revisa los parámetros `host` y `hostaddr` de la URL y, si la URL no trae host, `PGHOST` y `PGHOSTADDR`, y rechaza un servicio (`service` o `PGSERVICE`). Así, un `.env` con `ENTORNO=local` que apunte a Railway no siembra nada. El mensaje es fijo («La carga solo se prepara contra una base local.») y no muestra la URL, el host ni credenciales.
- `pedido.js` se niega a partir si `BASE_URL` no es `localhost` o `127.0.0.1`, y si `CARGA_META` no es `piloto` ni `produccion`.

## Variables

Se definen en la terminal de quien corre la carga. **Nunca se escriben en el repositorio ni en el chat.**

| Variable | Para | Qué es |
|---|---|---|
| `SEMILLA_CONTRASENA` | `preparar_carga.py` | La contraseña de las cuentas de carga, de 8 a 128 caracteres. Inventa una para esta corrida |
| `CARGA_CONTRASENA` | `pedido.js` | La misma contraseña. Obligatoria |
| `BASE_URL` | `pedido.js` | La API local. Por omisión `http://localhost:8000` |
| `CARGA_META` | `pedido.js` | La meta que se exige: `piloto` (por omisión: 10 usuarios, 0 % de fallos y mediana bajo 800 ms en cada paso; el p95 se informa) o `produccion` (50 usuarios y p95 bajo 800 ms en cada paso y en total). Con otro valor el script no parte |
| `CARGA_USUARIOS` | `pedido.js` | Usuarios virtuales. Por omisión los de la meta: 10 en `piloto` y 50 en `produccion`. Nunca más que las cuentas preparadas |
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

# 3. En otra terminal, la carga con la meta del piloto (10 usuarios, la mediana de cada paso)
export CARGA_CONTRASENA="$SEMILLA_CONTRASENA"
k6 run infra/carga/pedido.js

# O con la meta de producción (50 usuarios, el p95), en un equipo representativo
CARGA_META=produccion k6 run infra/carga/pedido.js
```

Si un umbral falla, k6 termina con un código distinto de 0.

Antes de correrla por primera vez, `k6 inspect infra/carga/pedido.js` revisa la sintaxis y las opciones sin enviar nada.

## Cómo leer el resultado

Cada petición lleva la etiqueta `paso`, y cada paso tiene su umbral, el de la meta activa. RNF-05 (arquitectura, sección 2.2) pide, en el piloto, 0 % de fallos y la mediana de cada paso bajo 800 ms con 10 usuarios concurrentes, y el p95 se informa. En producción pide el p95 bajo 800 ms con 50 usuarios, en un equipo representativo:

| Paso | Qué peticiones | Umbral en `piloto` | Umbral en `produccion` | Por qué |
|---|---|---|---|---|
| `catalogo` | `GET /v1/catalogo` | med < 800 ms | p(95) < 800 ms | Parte del flujo de RNF-05 |
| `pedido` | `POST .../pedidos` y, si quedó uno sin pagar de otra corrida, `GET .../pedido-en-curso` y `POST .../cancelar` | med < 800 ms | p(95) < 800 ms | Parte del flujo de RNF-05 |
| `confirmar` | `POST /v1/pedidos/{id}/confirmar` | med < 800 ms | p(95) < 800 ms | Parte del flujo de RNF-05 |
| `pagar` | `POST /v1/pedidos/{id}/pagar` | med < 800 ms | p(95) < 800 ms | Parte del flujo de RNF-05 |
| `retorno` | `POST /v1/pagos/retorno` | med < 800 ms | p(95) < 800 ms | Con la pasarela falsa la venta se aprueba en memoria, sin red: mide solo el trabajo de MATU al cerrar el pago. La latencia de Transbank no se mide aquí |
| `entrar` | `POST /v1/sesiones`, `GET /v1/grupos` y `GET .../personas-cuidadas` | Ninguno (`max>=0`, que siempre se cumple) | Ninguno (`max>=0`) | No es parte de RNF-05: ocurre una vez por usuario, y argon2id es lento a propósito. Todos los usuarios entran a la vez al partir. Se mide para verlo, sin exigirle la meta |
| total | Todas | Ninguno: se mide y se informa | p(95) < 800 ms | En producción, el umbral de la estrategia de pruebas. Incluye `entrar`, así que es más exigente que RNF-05. El piloto exige cada paso, no el total |

Al terminar, en vez del resumen de siempre, k6 muestra la meta activa y los usuarios virtuales, y una tabla con la mediana (`med`), el p95 y el p99 de cada paso y del total, la meta de cada fila y si la cumple (`CUMPLE` o `NO CUMPLE`), más `checks`, `http_req_failed` y las iteraciones completas. Las tres estadísticas salen en los dos modos: en el piloto el p95 se informa sin exigirlo. Usa solo métricas agregadas: no muestra correos, tokens, ids ni cuerpos.

```
MATU-80 · Tiempos por paso (RNF-05), meta piloto: 10 usuarios, 0 % de fallos y mediana < 800 ms en cada paso; el p95 se informa
usuarios virtuales: 10

paso       meta          med     p95      p99      estado
---------  ------------  ------  -------  -------  -----------
entrar     se mide       ...                       no se exige
catalogo   med < 800 ms  ...                       CUMPLE
pedido     med < 800 ms  ...                       NO CUMPLE
...
total      se mide       ...                       no se exige
```

Con `CARGA_META=produccion` la meta de cada paso dice `p95 < 800 ms`, y el total también se exige.

**Qué significa que falle uno:**

- **Falla un paso del flujo** (`NO CUMPLE` en `catalogo`, `pedido`, `confirmar`, `pagar` o `retorno`): ese paso es el lento. Es por donde se empieza a buscar (consultas, bloqueos, trabajo por petición).
- **Fallan todos los pasos a la vez y con tiempos parecidos:** lo más probable es que la API esté encolando las peticiones (un solo proceso con 50 usuarios) o que la máquina sume latencia (Docker sobre WSL), más que un paso en particular. Conviene repetir con otra máquina antes de optimizar.
- **Falla solo el total y pasan los pasos** (solo en `produccion`, porque el piloto no exige el total): lo que lo empuja es `entrar`, que no es parte de RNF-05.
- **Aparecen 503 `/errores/servicio-no-disponible` con `Retry-After`** (y en el log de la API `"evento": "pool_agotado"`): el pool de conexiones se llenó y la petición esperó más de `DB_POOL_TIMEOUT`. Es el hallazgo K1 de la corrida del 20-11, que antes salía como 500. El pool se configura con `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` y `DB_POOL_TIMEOUT` (por omisión 10, 20 y 10 s, en `.env.example`). Esa corrida no sirve para medir los pasos: mide la espera por una conexión.
- **`retorno` tarda segundos y crece de una corrida a la siguiente, sin 503 ni bloqueos:** era el hallazgo K2 de la corrida del 20-11. Con unas 300 ventas en la base, el costo estimado de las consultas de `transaccion_pasarela` (sus políticas RLS se expanden en más de 200 subplanes) superaba `jit_above_cost` y PostgreSQL compilaba cada una con JIT, de 2,5 a 7 s por consulta. Desde K2 cada conexión de la API y de las tareas abre su sesión con `jit=off` (`app/core/db.py`, `OPCIONES_SESION`), sin variables nuevas. Si vuelve a pasar, revisa que la API corra con ese código.
- **`retorno` tarda segundos al partir y después baja a unos cientos de ms:** es la planificación de esas mismas consultas, de 60 a 125 ms cada una por las políticas RLS. Desde el ajuste de RNF-05 cada conexión prepara cada consulta la primera vez y usa su plan genérico (`app/core/db.py`, `PREPARAR_DESDE` y `plan_cache_mode`): la paga una vez por conexión, no en cada vuelta. Por eso las primeras vueltas de cada conexión del pool siguen lentas, y también las que vienen justo después de que PostgreSQL analiza una tabla del pago (`autoanalyze`), que invalida los planes guardados. En una corrida corta pesan en el p95: conviene descartar el primer minuto o correr más tiempo. Quitar la causa de fondo, las políticas que se expanden en más de 200 subplanes, lleva una migración.
- **Fallan `checks` o `http_req_failed`:** el flujo no funcionó (cuentas sin preparar, stock agotado, la capa 3 apagada). Los tiempos de esa corrida no sirven. En `piloto` basta una petición fallida para que `http_req_failed` no cumpla: la meta es 0 % de fallos.

**Dónde se anota y qué se decide:** el resultado se anota en `TESTER/` del repositorio MATU, en el informe de la corrida, con la tabla por paso, la máquina y cuántos procesos tenía la API. Con la medida por paso se decide una de dos cosas: optimizar el paso que falla, o, si la meta no es realista para el piloto, ajustar la meta de RNF-05 en la arquitectura. Esa decisión la toman Jorge y Martín, no el script. Así se fijó el 20-11 la meta del piloto, con 10 usuarios y la mediana (arquitectura, sección 2.2), y el p95 con 50 usuarios quedó como meta de producción.

## Qué queda en la base

Las 50 cuentas de carga, sus pedidos pagados y el «Comercio de Carga», que aparece en el catálogo de esa base local. No toca las familias de la demo. Las pruebas del backend vacían la base local (`test_aislamiento.py`): para volver a cargar, se repite el paso 1.
