# MATU · Sistema de continuidad del cuidado

Repositorio de desarrollo de MATU · Proyecto de Capstone · Ingeniería en Informática · DUOC UC · segundo semestre 2026

MATU ayuda a que el cuidado de una persona mayor dependiente no dependa de una sola persona. Hace transferible lo que sabe quien cuida, con una ficha de relevo que se comparte por un enlace con vencimiento, y hace previsible el abastecimiento, anticipando cuándo se acaba cada insumo.

**La documentación del proyecto está en el repositorio [MATU](https://github.com/MartinHenriquez131/MATU)**, carpeta `docs/`: arquitectura, modelo de datos, estrategia de pruebas, backlog, prototipo y resultados de la validación. Ese repositorio reúne además las evidencias de cada fase del curso. Este contiene solo el código.

## Estado

| Parte | Estado |
|---|---|
| Entorno local (`infra/`) | PostgreSQL 16 y Redis 7 con Docker Compose. La base arranca con los cuatro roles creados |
| API (`backend/app/`) | Esqueleto de FastAPI (S0-A): configuración con `pydantic-settings`, errores RFC 7807, logs JSON con `request_id` y sin cuerpos de petición, y `GET /v1/salud`. `app/core/db.py` se conecta como `matu_app` |
| Modelo de datos (`backend/db/`) | Completo: 49 tablas y 94 políticas RLS, con RLS forzado en 45 tablas (las 4 de infraestructura van sin RLS y se acotan por permisos) |
| Migraciones | `0001_esquema_inicial` aplica el modelo completo y tiene vuelta atrás |
| Pruebas | 31 pruebas de aislamiento contra PostgreSQL real, una que verifica que la app se conecta como `matu_app` y las del esqueleto de la API (`tests/core/`) |
| Integración continua | GitHub Actions en cada push: estilo, tipos, secretos, migraciones y pruebas. En verde |
| Prueba de concepto de Transbank (`spikes/`) | Parcial: el débito no admite captura diferida. Los demás casos se cierran en el sprint 1 |

## Estructura

```
MATU_PROYECTO/
├── README.md
├── .env.example                   plantilla de variables locales (copiar a .env)
├── .gitattributes                 saltos de línea LF para que los scripts funcionen en Linux
├── .secrets.baseline              hallazgos conocidos de detect-secrets
├── .github/
│   ├── PULL_REQUEST_TEMPLATE.md   checklist de la definición de terminado
│   └── workflows/
│       └── ci.yml                 pipeline de integración continua
├── backend/
│   ├── pyproject.toml             dependencias y configuración de ruff, mypy y pytest
│   ├── app/
│   │   ├── main.py                crea la app y registra los routers de cada historia
│   │   └── core/
│   │       ├── config.py          configuración desde el entorno y el .env
│   │       ├── db.py              conexión de la app, como matu_app
│   │       ├── errores.py         errores RFC 7807
│   │       └── logs.py            logs JSON con request_id
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py                 migra como matu_owner
│   │   ├── script.py.mako         plantilla de migraciones nuevas
│   │   └── versions/
│   │       └── 0001_esquema_inicial.py
│   ├── db/                        modelo de datos en SQL
│   │   ├── 00_roles.sql           los cuatro roles de base de datos
│   │   ├── 01_esquema.sql         49 tablas, restricciones e índices
│   │   ├── 02_rls.sql             94 políticas de aislamiento por fila
│   │   ├── 03_permisos.sql        permisos por rol
│   │   ├── gen_diagramas.py       genera los diagramas desde la base
│   │   └── gen_matriz.py          genera la matriz de acceso
│   └── tests/
│       ├── core/                  pruebas del esqueleto de la API
│       ├── test_aislamiento.py    31 pruebas contra PostgreSQL real
│       └── test_conexion_app.py   la app se conecta como matu_app
├── infra/
│   ├── docker-compose.yml         PostgreSQL 16 y Redis 7
│   └── postgres/init/
│       └── 10_matu.sh             crea roles, base y btree_gist al primer arranque
└── spikes/                        código de prueba que no es parte del producto
    └── transbank/                 prueba de concepto de captura diferida (incompleta, ver su README)
```

A medida que avancen los sprints se suman `mobile/` (Flutter) y `web/` (React y TypeScript), según la estructura comprometida en el anexo 19.1 del documento de arquitectura.

## Tecnologías

| Área | Tecnología |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2 |
| Base de datos | PostgreSQL 16 con Row Level Security |
| Acceso a datos | SQLAlchemy 2, Alembic |
| Trabajos asíncronos | ARQ sobre Redis |
| Aplicación móvil | Flutter |
| Panel web | React + TypeScript |
| Pagos | Transbank, Webpay Plus diferido y OneClick |
| Infraestructura | Docker, Docker Compose |
| Integración continua | GitHub Actions |

## Cómo ejecutarlo

Requiere Docker y Python 3.12. Los comandos son para Git Bash, desde la raíz del repositorio.

**1. Variables de entorno.** Copia la plantilla y cambia las contraseñas. La de `MIGRATIONS_DATABASE_URL` debe coincidir con `MATU_OWNER_PASSWORD`, la de `DATABASE_URL` con `MATU_APP_PASSWORD` y la de `MATU_TEST_DSN` con `POSTGRES_PASSWORD`. Usa solo letras, números y guiones.

```
cp .env.example .env
```

**2. Base de datos.** La primera vez que se crea el volumen, el script `infra/postgres/init/10_matu.sh` crea los cuatro roles, la base `matu` y la extensión `btree_gist`.

**Si ya habías levantado el entorno anterior** (el que usaba `matu_owner` como superusuario), borra primero su volumen, porque si el volumen existe el script de arranque no se vuelve a ejecutar:

```
docker compose -f infra/docker-compose.yml down -v
```

Después:

```
docker compose --env-file .env -f infra/docker-compose.yml up -d --wait
```

Si ya tienes un PostgreSQL instalado en el computador usando el puerto 5432, hay que detenerlo antes.

**3. Dependencias y migraciones.**

```
cd backend
python -m venv .venv
source .venv/Scripts/activate
pip install -e ".[dev]"
alembic upgrade head
```

En macOS o Linux, el segundo comando es `source .venv/bin/activate`. En Windows, si `python` no es la versión 3.12, se crea con `py -3.12 -m venv .venv`.

**4. Pruebas.**

```
pytest -q
```

**5. Levantar la API.** Desde `backend/`, con el entorno virtual activo:

```
uvicorn app.main:app --reload
```

`http :8000/v1/salud` responde `{"estado": "ok"}`, y la documentación interactiva queda en `http://localhost:8000/docs`. Los logs salen en JSON, una línea por petición.

Las pruebas borran los datos de la base local antes de sembrar los suyos. No guardes datos de trabajo en ella.

Para volver a empezar con la base vacía: `docker compose --env-file .env -f infra/docker-compose.yml down -v` (borra el volumen) y repetir desde el paso 2. Para rehacer solo el esquema sin tocar los roles: `alembic downgrade base` y `alembic upgrade head`.

**Migraciones nuevas.** Se crean con `alembic revision --rev-id 0002 -m "descripción"`, para mantener la numeración correlativa.

**Diagramas.** `gen_diagramas.py` y `gen_matriz.py` escriben en `../MATU/docs/diagramas/modelo-datos`, es decir, en el repositorio de documentación clonado en la misma carpeta que este. La ruta se cambia con la variable `MATU_DIAGRAMAS`. La matriz necesita matplotlib: `pip install -e ".[dev,diagramas]"`.

## Integración continua

`.github/workflows/ci.yml` corre en cada push y en cada pull request, contra un PostgreSQL 16 desechable:

1. **ruff**: estilo del código
2. **mypy**: tipos
3. **detect-secrets**: que no se suban contraseñas ni claves. Los valores de ejemplo y los del pipeline ya están registrados en `.secrets.baseline`
4. **Migraciones**: subida, bajada y subida de nuevo
5. **pytest**: las pruebas de aislamiento contra la base migrada y las de la API

Si se agrega un valor de ejemplo que detect-secrets marca por error, se registra desde la raíz del repositorio con `detect-secrets scan --baseline .secrets.baseline`.

## Forma de trabajo

- Desde el sprint 1, cada historia va en su propia rama (`matu-04-crear-cuenta`, `s0a-esqueleto-api`) y entra a `main` por pull request, con el pipeline en verde y la revisión de la otra persona.
- La plantilla del pull request trae el checklist de la definición de terminado.
- Todo cambio que toque dinero o datos sensibles lo revisa la otra persona del equipo.
- Las tareas se gestionan en Trello, con el backlog de los sprints 1 a 3.
- Los sprints corren de viernes a jueves. El calendario está en el repositorio de documentación, `docs/sprints/calendario-sprints.md`.
- El desarrollo es asistido por IA. El código generado cumple la misma definición de terminado que el escrito a mano, y nunca se entregan datos reales ni secretos al asistente.

## Integrantes del equipo

* **Jorge Espinoza** · Product Owner y desarrollador
* **Martín Henríquez** · Scrum Master y desarrollador
