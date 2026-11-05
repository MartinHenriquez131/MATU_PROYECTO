# Staging en Railway (MATU-25)

Staging de MATU: la API por HTTPS en un subdominio `*.up.railway.app`, con PostgreSQL 16 y Redis 7
gestionados por Railway (ADR-019, plataforma decidida por Martín). **Solo datos sintéticos**: correos
`@example.com`, `.test` o `.invalid`, nombres inventados, nunca datos de una persona real.

| Archivo | Para qué |
|---|---|
| `Dockerfile` | Imagen de la API: Python 3.12, usuario sin privilegios, la página del relevo (`web/`) ya construida. Arranca con `python -m app.servidor` |
| `railway.json` | Build con el Dockerfile, `alembic upgrade head` antes de cada despliegue, revisión de salud en `/v1/salud` |
| `preparar_base.sh` | Crea en la base gestionada los roles de MATU, la base `matu` y `btree_gist`. Se puede correr más de una vez |
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
     El contexto de build es la raíz del repositorio.
   - **Networking → Generate Domain**: crea el subdominio `https://<algo>.up.railway.app`. Railway termina
     el HTTPS con su certificado; la API escucha en `$PORT` dentro de la red de Railway.

**Registra aquí la región elegida** (y en la tarjeta de MATU-25):

| Dato | Valor |
|---|---|
| Región de los tres servicios | `sfo` (US West, California), 05-11. Postgres 16 (`postgres-ssl:16`) y Redis 8.2 |
| Dominio de staging | `https://matu-api-production.up.railway.app` |
| `FORWARDED_ALLOW_IPS` fijado | *pendiente: ver paso 5* |

## 2. Variables de `matu-api`

Se cargan en *Variables* del servicio `matu-api`, nunca en el repositorio, en el chat ni en un `.env`
subido. Los valores secretos se generan solo para staging: **ninguno se copia de tu `.env` local**.

| Variable | Valor |
|---|---|
| `ENTORNO` | `staging`, siempre explícito (decisión 105). La imagen trae `produccion` por omisión; si el log de arranque no dice `entorno=staging`, el despliegue no se da por bueno |
| `LOG_NIVEL` | `INFO` |
| `POLITICA_VERSION` | La versión vigente de `docs/legal/politica-privacidad.md` del repositorio MATU |
| `PEPPER_EMAIL` | Secreto nuevo de staging, `python -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_CLAVE` | Secreto nuevo de staging, distinto de los demás |
| `PEPPER_PIN` | Secreto nuevo de staging, distinto de los demás |
| `PEPPER_RECUPERACION` | Secreto nuevo de staging, distinto de los demás (MATU-57). Sin él, recuperar el acceso responde 503 |
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

**No se cargan** en staging: `POSTGRES_PASSWORD`, `MATU_TEST_DSN` (son de las pruebas locales),
`ADMIN_DATABASE_URL` (solo se usa en tu computador, en el paso 3), `WEB_DIST` y `PORT` (los fijan la
imagen y Railway). La KEK por variable de entorno se admite en staging por la decisión 105, que amplía
la D-A del 28-10 (desvío del ADR-016): staging opera **solo con datos sintéticos**, el registro solo acepta
correos de dominios reservados y el staging se cierra al terminar el semestre.

La API se conecta siempre como `matu_app` (`DATABASE_URL`), que no es dueño ni superusuario: RLS la
alcanza siempre. `matu_owner` solo lo usa Alembic, en el `preDeployCommand`.

## 3. Preparar la base (una vez)

En el servicio `Postgres`, activa temporalmente el **TCP Proxy** (*Settings → Networking*) para tener
`DATABASE_PUBLIC_URL`. Desde la raíz del repositorio, en tu computador (con `psql` 16):

```
read -rs ADMIN_DATABASE_URL     # pega DATABASE_PUBLIC_URL del servicio Postgres
read -rs MATU_OWNER_PASSWORD    # la misma de las variables de matu-api
read -rs MATU_APP_PASSWORD
export ADMIN_DATABASE_URL MATU_OWNER_PASSWORD MATU_APP_PASSWORD
sh infra/railway/preparar_base.sh
unset ADMIN_DATABASE_URL MATU_OWNER_PASSWORD MATU_APP_PASSWORD
```

Crea los cuatro roles de `backend/db/00_roles.sql` si no existen (si existen solo algunos, se detiene),
fija las contraseñas, crea la base `matu` con `matu_owner` como dueño y habilita `btree_gist`. Se
detiene si un rol de MATU es `SUPERUSER` o `BYPASSRLS`. Las tablas las crea Alembic al desplegar.
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
curl -sS https://<algo>.up.railway.app/v1/salud
```

responde `{"estado":"ok"}` por HTTPS, con el certificado de Railway. Además:

- `curl -sSI http://<algo>.up.railway.app/v1/salud` no debe responder la API en claro: Railway redirige a
  `https://`. Si no redirige, anótalo como hallazgo.

- `https://<algo>.up.railway.app/docs`: con `ENTORNO=staging` se ve la documentación (solo se apaga con `produccion`, `app/main.py`). Pendiente de decisión de Jorge (05-11).
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

## Escalado y pendientes

- **Red del proxy de Railway.** Hasta comprobarla (paso 5), `FORWARDED_ALLOW_IPS` queda vacía y todas
  las peticiones de staging comparten un contador. Si Railway no conecta desde un rango fijo, decidir
  entre aceptar ese contador compartido en staging o confiar en una red más amplia de Railway. Lo
  deciden Martín y Jorge.
- **La ficha en staging.** Resuelto con la decisión 105 (Jorge, 04-11, PR #46): `CUSTODIA_KEK=entorno_sintetico`
  con una KEK propia de staging. Antes de datos reales se pasa a otra custodia (ADR-019).
- **Región.** Anotarla al crear el proyecto (paso 1).
