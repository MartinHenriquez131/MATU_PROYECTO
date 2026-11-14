# Staging en Railway (MATU-25)

Staging de MATU: la API por HTTPS en un subdominio `*.up.railway.app`, con PostgreSQL 16 y Redis 7
gestionados por Railway (ADR-019, plataforma decidida por Martín). **Solo datos sintéticos**: correos
`@example.com`, `.test` o `.invalid`, nombres inventados, nunca datos de una persona real.

| Archivo | Para qué |
|---|---|
| `Dockerfile` | Imagen de la API: Python 3.12, usuario sin privilegios, la página del relevo (`web/`) ya construida. Arranca con `python -m app.servidor` |
| `railway.json` | **Referencia** de la configuración del servicio (build con el Dockerfile, `alembic upgrade head` antes de cada despliegue, revisión de salud en `/v1/salud`). Railway **no lo lee**: los valores se cargan a mano en el panel (paso 1). Si cambias uno, cámbialo en los dos lugares |
| `preparar_base.sh` | Crea en la base gestionada los roles de MATU, fija sus contraseñas (también las de `matu_scheduler` y `matu_publisher`, MATU-74), la base `matu` y `btree_gist`. Se puede correr más de una vez |
| `pares_tcp.py` | Muestra desde qué direcciones conecta el proxy de Railway, para fijar `FORWARDED_ALLOW_IPS` |

## 1. Servicios

En un proyecto nuevo de Railway (por ejemplo `matu-staging`), en **una sola región**:

1. **PostgreSQL**: el servicio de base de datos de Railway, en versión **16**. Llámalo `Postgres`.
2. **Redis**: el servicio Redis de Railway (la plantilla trae la 8.2; MATU usa solo `INCR`, `EXPIRE`, Lua y hashes). Llámalo `Redis`.
3. **API**: un servicio desde el repositorio de GitHub, llamado `matu-api`. En *Settings*:
   - **Build y deploy** con los valores de `railway.json` de este directorio. Desde noviembre de 2026 Railway
     ya no acepta un *Config file path* nuevo (pide migrar a `.railway/railway.ts`), así que se cargan a
     mano en el servicio: *Dockerfile path* `infra/railway/Dockerfile`, *Pre-deploy* `alembic upgrade head`,
     *Start* `python -m app.servidor`, *Healthcheck* `/v1/salud` (60 s) y reinicio `ON_FAILURE` (5).
     El contexto de build es la raíz del repositorio. `railway.json` queda como la referencia escrita de
     estos valores, pero Railway no lo lee: un cambio en el archivo no llega al servicio, y un cambio en el
     panel no llega al archivo. Cambia siempre los dos a la vez.
   - **Networking → Generate Domain**: crea el subdominio `https://<algo>.up.railway.app`. Railway termina
     el HTTPS con su certificado; la API escucha en `$PORT` dentro de la red de Railway.

**Registra aquí la región elegida** (y en la tarjeta de MATU-25):

| Dato | Valor |
|---|---|
| Región de los tres servicios | `sfo` (US West, California), 05-11. Postgres 16 (`postgres-ssl:16`) y Redis 8.2 |
| Dominio de staging | `https://matu-api-production.up.railway.app` |
| `FORWARDED_ALLOW_IPS` fijado | `100.64.0.0/10`, la red del proxy interno de Railway (Martín, 05-11) |
| `PROXY_SALTOS` fijado | `1`, verificado en el paso 5 (Martín, 05-11): 3 lotes de 6 intentos dieron cinco `422` y un `429`; en los 18, `xff_cabeceras=1`, `xff_elementos=2`, `publica`/`publica` e `ip_contada=xff`. Railway **reemplaza** la cabecera |
| `DIAGNOSTICO_PROXY` encendido | 05-11, 11:56 (Chile), Martín |
| `DIAGNOSTICO_PROXY` apagado | 05-11, 12:25 (Chile), Martín |

## 2. Variables de `matu-api`

Se cargan en *Variables* del servicio `matu-api`, nunca en el repositorio, en el chat ni en un `.env`
subido. Los valores secretos se generan solo para staging: **ninguno se copia de tu `.env` local**.

| Variable | Valor |
|---|---|
| `ENTORNO` | `staging`, siempre explícito (decisión 105). La imagen trae `produccion` por omisión; si el log de arranque no dice `entorno=staging`, el despliegue no se da por bueno |
| `LOG_NIVEL` | `INFO` |
| `POLITICA_VERSION` | La versión vigente de `docs/legal/politica-privacidad.md` del repositorio MATU: `0.11` desde MATU-75. Debe tener su texto en `backend/app/modules/iam/politica/`, sin marcadores; si no, `GET /v1/politica` y crear una cuenta responden 503 |
| `POLITICA_ACTUALIZADA_EN` | MATU-75: la fecha de esa versión, `AAAA-MM-DD` (la 0.11, `2026-11-09`). Sin ella, `GET /v1/politica` y crear una cuenta responden 503 |
| `CORREO_PRIVACIDAD` | MATU-75: `cuidaconmatu@gmail.com`, el mismo que trae escrito el texto de la política. `GET /v1/politica` lo entrega aparte para el `mailto:` de «Tu cuenta»; sin él sale `null` |
| `PEPPER_EMAIL` | Secreto nuevo de staging, `python -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_CLAVE` | Secreto nuevo de staging, distinto de los demás |
| `PEPPER_PIN` | Secreto nuevo de staging, distinto de los demás |
| `PEPPER_RECUPERACION` | Secreto nuevo de staging, distinto de los demás (MATU-57). Sin él, recuperar el acceso responde 503 |
| `CODIGO_RETIRO_SECRETO` | MATU-63 (D-63-4): secreto nuevo de staging, de 32 caracteres o más y distinto de los demás. Llave del HMAC del código de retiro: la base guarda solo su huella. En `matu-api` y, como referencia, en `matu-cron-despacho` (el comando del código). Sin él, generar y validar el código de retiro responden 503 |
| `CUSTODIA_KEK` | `entorno_sintetico` (decisión 105): enciende la ficha y el relevo |
| `KEK_ENTORNO` | KEK nueva **propia de staging**, 32 bytes en base64: `python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"`. Nunca la de un `.env` local |
| `KEK_VERSION` | `1` |
| `ENVIADOR_CODIGOS` | `simulado` (decisión 105): no envía nada |
| `REGISTRO_ENVIOS` | `/tmp/matu-envios.jsonl`: dentro del contenedor, donde el usuario `matu` puede escribir, y no servido por la API. Se lee con `railway ssh`. Se borra en cada despliegue |
| `PEPPER_LIMITES` | Secreto nuevo **propio de staging**, distinto de los demás. Sin él, registro, canje, presentación y entrada responden 503 |
| `ORIGEN_WEB` | `https://<algo>.up.railway.app`, sin barra final |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` (referencia de Railway a la red privada) |
| `MATU_OWNER_PASSWORD` | Secreto nuevo, solo letras, números y guiones |
| `MATU_APP_PASSWORD` | Secreto nuevo, distinto, solo letras, números y guiones |
| `MIGRATIONS_DATABASE_URL` | `postgresql+psycopg://matu_owner:${{MATU_OWNER_PASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/matu` |
| `DATABASE_URL` | `postgresql+psycopg://matu_app:${{MATU_APP_PASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/matu` |
| `FORWARDED_ALLOW_IPS` | Vacía al principio (127.0.0.1). Se fija en el paso 5 |
| `PROXY_SALTOS` | Vacía al principio (0). `1` en Railway, en el paso 5 |
| `DIAGNOSTICO_PROXY` | **No se carga**, salvo durante la verificación del paso 5: `true` y después se borra |
| `PASARELA_PAGO` | MATU-62: `integracion` en staging. Webpay Plus en el ambiente de integración de Transbank, con el código de comercio y la llave públicas que trae su SDK: no se cargan. Sin la variable, pagar responde 503 y no se cobra nada. `falsa` no carga fuera de local y pruebas |
| `VIDA_VENTA_WEBPAY_MINUTOS` | MATU-62: opcional, `8` por omisión (decisión 230; MATU-94: la venta de integración vence a los 7 minutos). Cuánto dura un pago en curso con la venta iniciada. Va en `matu-api` y en los cron |

**No se cargan** en staging: `POSTGRES_PASSWORD`, `MATU_TEST_DSN` (son de las pruebas locales),
`ADMIN_DATABASE_URL` (solo se usa en tu computador, en el paso 3), `WEB_DIST` y `PORT` (los fijan la
imagen y Railway). La KEK por variable de entorno se admite en staging por la decisión 105, que amplía
la D-A del 28-10 (desvío del ADR-016): staging opera **solo con datos sintéticos**, el registro solo acepta
correos de dominios reservados y el staging se cierra al terminar el semestre.

La API se conecta siempre como `matu_app` (`DATABASE_URL`), que no es dueño ni superusuario: RLS la
alcanza siempre. `matu_owner` solo lo usa Alembic, en el `preDeployCommand`. **`matu-api` no lleva**
`SCHEDULER_DATABASE_URL` ni `PUBLISHER_DATABASE_URL`: son solo de los cron de las tareas (paso 6).

## 3. Preparar la base (una vez)

En el servicio `Postgres`, activa temporalmente el **TCP Proxy** (*Settings → Networking*) para tener
`DATABASE_PUBLIC_URL`. Desde la raíz del repositorio, en tu computador (con `psql` 16):

```
read -rs ADMIN_DATABASE_URL     # pega DATABASE_PUBLIC_URL del servicio Postgres
read -rs MATU_OWNER_PASSWORD    # la misma de las variables de matu-api
read -rs MATU_APP_PASSWORD
read -rs MATU_SCHEDULER_PASSWORD   # la de SCHEDULER_DATABASE_URL de los cron (paso 6)
read -rs MATU_PUBLISHER_PASSWORD   # la de PUBLISHER_DATABASE_URL del cron de avisos
export ADMIN_DATABASE_URL MATU_OWNER_PASSWORD MATU_APP_PASSWORD MATU_SCHEDULER_PASSWORD MATU_PUBLISHER_PASSWORD
sh infra/railway/preparar_base.sh
unset ADMIN_DATABASE_URL MATU_OWNER_PASSWORD MATU_APP_PASSWORD MATU_SCHEDULER_PASSWORD MATU_PUBLISHER_PASSWORD
```

Crea los cuatro roles de `backend/db/00_roles.sql` si no existen (si existen solo algunos, se detiene),
fija las cuatro contraseñas, crea la base `matu` con `matu_owner` como dueño y habilita `btree_gist`. Se
detiene si un rol de MATU es `SUPERUSER`, `BYPASSRLS`, `CREATEROLE`, `CREATEDB` o `REPLICATION`, o si
`matu_scheduler` o `matu_publisher` es miembro de otro rol. Las tablas las crea Alembic al desplegar.

**Si la base ya estaba preparada antes de MATU-74**, vuelve a correr el script con las cinco variables: deja
los roles y la base como estaban y solo fija las contraseñas. Hazlo **antes** de desplegar la migración 0022:
desde ella, los cron de las tareas ya no pueden usar `matu_app`.
Después, desactiva el TCP Proxy de `Postgres`: la API llega a la base por la red privada.

## 4. Desplegar: un comando

Con la [CLI de Railway](https://docs.railway.com/guides/cli) (`railway login` y `railway link` al
proyecto, una vez), desde la raíz del repositorio:

```
railway up --service matu-api --ci
```

Sube el repositorio (sin lo que ignora `.gitignore`, así que nunca el `.env`), construye la imagen con
`infra/railway/Dockerfile`, corre `alembic upgrade head` como `matu_owner` y, si la migración sale bien,
arranca la API y espera a que `/v1/salud` responda. Si la migración falla, el despliegue anterior sigue
arriba.

**Sembrar la demo (una vez, después del primer despliegue).** Con datos sintéticos de `@example.com`
(decisión 105). La contraseña de las cuentas se pide sin mostrarla y no queda en ningún archivo:

```
railway ssh --service matu-api
read -rs SEMILLA_CONTRASENA; export SEMILLA_CONTRASENA
python /app/infra/semillas/demo.py
unset SEMILLA_CONTRASENA
```

La semilla es idempotente, se niega a correr con `ENTORNO=produccion` y solo entra como `matu_app`.

## 5. Verificar

```
curl -sS https://matu-api-production.up.railway.app/v1/salud
```

responde `{"estado":"ok"}` por HTTPS, con el certificado de Railway. Además:

- `curl -sSI http://matu-api-production.up.railway.app/v1/salud` no debe responder la API en claro: Railway redirige a
  `https://`. Si no redirige, anótalo como hallazgo.

- `https://matu-api-production.up.railway.app/docs` y `/openapi.json` responden 404 en staging: la documentación solo se publica con `ENTORNO` local o pruebas (decisión 115, MATU-58).
- **Límite por IP:** seis `POST /v1/usuarios` con cuerpo `{}` desde la misma red: los cinco primeros
  responden 422 y el sexto 429 con `Retry-After`. Gasta el cupo de esa IP por una hora.
- **Logs:** `railway logs --service matu-api` muestra una línea JSON por petición, con la plantilla de la
  ruta y sin IP, cuerpo, token ni PIN. Tras correr el e2e, `grep` del token y del PIN sobre esa salida
  no encuentra nada. El token del relevo viaja en el fragmento (`/r#<token>`), que el navegador no envía.

**Fijar `FORWARDED_ALLOW_IPS`.** Con el valor por omisión (127.0.0.1) la API no confía en el proxy:
todas las peticiones cuentan con la IP del proxy, así que toda la gente comparte el límite por IP y la
demora de la entrada. Es más estricto, nunca más permisivo, pero en una demostración con varias personas
puede dar 429. Para fijarlo:

1. Abre la API desde el teléfono y, al mismo tiempo, en una sesión interactiva:
   ```
   railway ssh --service matu-api
   python /app/infra/railway/pares_tcp.py
   ```
   Muestra las direcciones desde donde conecta el proxy de Railway (no las de las personas). No las
   escribe en ningún log.
2. Repite en otro momento y tras un nuevo despliegue. **Si siempre caen en una red fija y privada**
   (por ejemplo una sola red `/16` o `/24` interna), carga esa red en `FORWARDED_ALLOW_IPS` y despliega.
   Nunca `*` ni `0.0.0.0/0`: la API no arranca con eso.
3. Comprueba con dos redes distintas (wifi y datos del teléfono): agota el cupo de `POST /v1/usuarios`
   desde una (sexto intento, 429) y la otra debe seguir respondiendo 422.
4. Anota el valor en la tabla del paso 1.

**Si Railway no conecta desde una red fija o no la publica**, no se adivina: queda con el valor por
omisión y se escala a Martín y Jorge (ver abajo).

**Fijar `PROXY_SALTOS` (decisión 114, punto 7).** El borde de Railway entrega
`X-Forwarded-For: <cliente>, <borde>`: agrega su propia IP a la derecha, y el borde se turna entre varios
servidores con IP públicas que Railway no publica. Con `PROXY_SALTOS` vacía (0) la API toma la IP de más a
la derecha que no es de confianza, la del borde: el límite cuenta por servidor de borde y no por persona
(hallazgo de Martín del 05-11: seis intentos dieron seis 422, sin 429). Con `PROXY_SALTOS=1` la API toma
la IP que queda justo a la izquierda del borde, nunca la primera de la lista: si alguien antepone una IP
inventada o basura, no le sirve, porque lo que queda a la izquierda de esa IP se ignora por completo. Si
la lista trae menos IP de las esperadas, o el cliente o el borde no son una IP, cuenta la del proxy, que
es lo más estricto. Solo se aplica a conexiones desde `FORWARDED_ALLOW_IPS`.

Los comandos son de **bash**: córrelos en Git Bash (o en macOS o Linux). En PowerShell `curl` es un alias
de `Invoke-WebRequest` y no entiende estas opciones; ahí usa `curl.exe` y cambia `$BASE`, el `for` y las
`\` del final de línea por su equivalente. Primero fija el dominio de staging (el de la tabla del paso 1):

```
BASE=https://matu-api-production.up.railway.app
```

1. En *Variables* de `matu-api`, carga `PROXY_SALTOS=1` y, **solo para esta verificación**,
   `DIAGNOSTICO_PROXY=true`. Anota la fecha y hora de encendido en la tabla del paso 1. Despliega: el log
   de arranque dice `proxy_saltos=1 diagnostico_proxy=encendido` (con `ENTORNO=produccion` la API no
   arranca con el diagnóstico encendido).
2. Seis intentos normales, desde la misma red:
   ```
   for i in 1 2 3 4 5 6; do curl -sS -o /dev/null -w "%{http_code}\n" -X POST \
     -H "Content-Type: application/json" -d '{}' "$BASE/v1/usuarios"; done
   ```
   Deben dar cinco `422` y un `429`.
3. En `railway logs --service matu-api`, las líneas `"mensaje": "diagnostico_proxy"` de esos intentos
   deben decir `"xff_elementos": 2`, `"xff_clases": ["publica", "publica"]` e `"ip_contada": "xff"`.
   La línea no lleva ninguna IP, solo cantidades y clases. **Si trae 3 elementos** sin que tú hayas
   mandado un `X-Forwarded-For`, Railway agrega otro salto propio: sube `PROXY_SALTOS` a `2`, despliega y
   repite desde el paso 2. Si trae 1, o `"ip_contada": "socket"`, no se ajusta a ciegas: se escala.
4. Seis intentos con un `X-Forwarded-For` falsificado que cambia cada vez, desde **otra red** (datos del
   teléfono) o una hora después, porque el paso 2 ya gastó el cupo de tu IP:
   ```
   for i in 1 2 3 4 5 6; do curl -sS -o /dev/null -w "%{http_code}\n" -X POST \
     -H "Content-Type: application/json" -H "X-Forwarded-For: 198.51.100.$i" \
     -d '{}' "$BASE/v1/usuarios"; done
   ```
   También deben dar cinco `422` y un `429`: la IP falsa no cambia el contador. El diagnóstico muestra 2
   elementos si Railway reemplaza la cabecera, o 3 si concatena la tuya; con `PROXY_SALTOS=1` las dos
   formas cuentan tu IP.
5. Seis intentos con **basura** en `X-Forwarded-For`, desde una red con cupo (una tercera, o una hora
   después del paso 2 o del 4):
   ```
   for i in 1 2 3 4 5 6; do curl -sS -o /dev/null -w "%{http_code}\n" -X POST \
     -H "Content-Type: application/json" -H "X-Forwarded-For: basura" \
     -d '{}' "$BASE/v1/usuarios"; done
   ```
   También deben dar cinco `422` y un `429`, en el contador de tu IP y no en el compartido del proxy. Si
   Railway concatena, el diagnóstico muestra 3 elementos, el primero `invalida`, e `"ip_contada": "xff"`.
6. **Apaga el diagnóstico:** borra `DIAGNOSTICO_PROXY` de las *Variables* y despliega. El log de arranque
   dice `diagnostico_proxy=apagado`. Anota la fecha y hora de apagado y el valor final de `PROXY_SALTOS`
   en la tabla del paso 1.

## 6. Cron de las tareas (MATU-74)

Tres servicios de cron, desde el mismo repositorio y la misma imagen (`infra/railway/Dockerfile`), con
`restartPolicyType=NEVER` y sin healthcheck ni pre-deploy. El cron de Railway se evalúa en **UTC**; los horarios
y su porqué están en `backend/README.md` (hallazgos H3 y H5):

| Servicio | Comando | Cron (UTC) | Chile en verano / invierno |
|---|---|---|---|
| `matu-cron-borrados` | `python -m app.tareas borrados` | `0 6 * * *` | 03:00 / 02:00 |
| `matu-cron-quiebres` | `python -m app.tareas quiebres` | `0 8 * * *` | 05:00 / 04:00 |
| `matu-cron-avisos` | `python -m app.tareas avisos` | `*/5 * * * *` | cada 5 minutos, el mínimo de Railway |
| `matu-cron-conciliacion` | `python -m app.tareas conciliacion_pagos` | `*/5 * * * *` | cada 5 minutos (MATU-62) |
| `matu-cron-despacho` | `python -m app.tareas despacho` | `*/5 * * * *` | cada 5 minutos (MATU-63): lleva los pedidos pagados al día y devuelve lo que faltó. Con las variables de `conciliacion` (`DATABASE_URL`, `SCHEDULER_DATABASE_URL` y `PASARELA_PAGO`) |

**El código de retiro en la demo (MATU-63).** En la demo, operación genera el código con este comando hasta MATU-81:
`railway run --service matu-cron-despacho python -m app.tareas codigo-retiro <parte_id>`, desde `backend/`. Necesita
`SCHEDULER_DATABASE_URL` y `CODIGO_RETIRO_SECRETO` (el mismo valor que `matu-api`, como referencia
`${{matu-api.CODIGO_RETIRO_SECRETO}}` en `matu-cron-despacho`). Escribe el código una sola vez en la consola, nunca en
el log.

Variables de cada cron. `DATABASE_URL`, `POLITICA_VERSION` y `ORIGEN_WEB` van como referencia a `matu-api`
(`${{matu-api.DATABASE_URL}}`), sin copiar valores:

| Variable | `borrados` | `quiebres` | `avisos` |
|---|---|---|---|
| `ENTORNO` | `staging` | `staging` | `staging` |
| `DATABASE_URL` | referencia | referencia | referencia |
| `POLITICA_VERSION` | referencia | referencia | referencia |
| `MATU_SCHEDULER_PASSWORD` | secreto nuevo, solo letras, números y guiones | el mismo | — |
| `SCHEDULER_DATABASE_URL` | `postgresql+psycopg://matu_scheduler:${{MATU_SCHEDULER_PASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/matu` | la misma | — |
| `MATU_PUBLISHER_PASSWORD` | — | — | secreto nuevo, distinto |
| `PUBLISHER_DATABASE_URL` | — | — | `postgresql+psycopg://matu_publisher:${{MATU_PUBLISHER_PASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/matu` |
| `ENVIADOR_AVISOS` | — | — | `simulado` |
| `ORIGEN_WEB` | — | — | referencia |

Desde MATU-61, `borrados` corre además `conservacion_pedidos` (los pedidos no pagados a los 30 días, migración
0023). Corre siempre, con la capa 3 encendida o apagada (decisión 220): no necesita `CAPA3_HABILITADA`. Sin
variables nuevas: usa `SCHEDULER_DATABASE_URL`.

Desde MATU-42, `borrados` corre además `conservacion_invitaciones` (las invitaciones al grupo cerradas hace 30
días, migración 0026, D-42-6). Sin variables nuevas: usa `SCHEDULER_DATABASE_URL`.

Desde MATU-46, `borrados` corre además `conservacion_relevo` (el teléfono del relevo 30 días después de que el
acceso vence o se corta, migración 0027). Corre siempre, con la capa 3 encendida o apagada. Sin variables nuevas: usa
`SCHEDULER_DATABASE_URL`. Si se restaura una copia de respaldo, corre `python -m app.tareas borrados` antes de
reabrir la base (C14 del analista).

Desde MATU-62, `matu-cron-conciliacion` cierra los pagos de Webpay sin respuesta y reintenta las anulaciones
(D-62-5 y D-62-6), también con la capa 3 apagada (D-62-17). Lleva las variables de `borrados`
(`SCHEDULER_DATABASE_URL` para `pagos_por_conciliar`, `DATABASE_URL` para cerrar cada venta) más
`PASARELA_PAGO` como referencia a `matu-api`. Sin `PASARELA_PAGO` la corrida no llama a nadie.

`REGISTRO_AVISOS` **ya no se carga** en el cron de avisos: con `ENTORNO=staging` el envío simulado no escribe el
archivo, que se perdía con cada contenedor (hallazgo H4). Lo enviado queda en la tabla `notificacion`, con su
estado y `enviada_en`. Si quedó cargada, se puede borrar: no cambia nada.

Cada contraseña debe ser la misma que se fijó con `preparar_base.sh` (paso 3). Si falta la URL de su rol, o
es de otro usuario, la tarea falla con `"tipo_error": "FaltaConexion"` y `"falta": "SCHEDULER_DATABASE_URL"`
(o `PUBLISHER_DATABASE_URL`) en su línea de log, y la corrida sale con `1`: nunca usa `matu_app` en su lugar.

**Verificar:** en `railway logs` de cada cron, después de su primera corrida, la línea `"mensaje": "tarea"`
con `"resultado": "ok"` (o `"apagada"` en avisos, sin `ENVIADOR_AVISOS`). Con `railway ssh --service
matu-cron-borrados`, `python -m app.tareas borrados` corre a mano igual.

## Escalado y pendientes

- **Red del proxy de Railway.** Resuelto: `FORWARDED_ALLOW_IPS=100.64.0.0/10` y `PROXY_SALTOS=1`
  (Martín, 05-11). El borde reemplaza `X-Forwarded-For` por `cliente, borde`, y lo que manda el cliente
  se descarta. Si Railway cambia ese formato (otro salto, o la cabecera concatenada), el límite vuelve a
  fallar: se repite el paso 5 con el diagnóstico y, si no muestra 2 elementos, se escala a Martín y Jorge.
- **La ficha en staging.** Resuelto con la decisión 105 (Jorge, 04-11, PR #46): `CUSTODIA_KEK=entorno_sintetico`
  con una KEK propia de staging. Antes de datos reales se pasa a otra custodia (ADR-019).
- **Región.** Resuelto: anotada en la tabla de datos del proyecto (línea 33), `sfo` (US West, California), 05-11.
