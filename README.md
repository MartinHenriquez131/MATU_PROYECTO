# MATU · Sistema de continuidad del cuidado

Repositorio de desarrollo de MATU · Proyecto de Capstone · Ingeniería en Informática · DUOC UC · segundo semestre 2026

MATU ayuda a que el cuidado de una persona mayor dependiente no dependa de una sola persona. Hace transferible lo que sabe quien cuida, con una ficha de relevo que se comparte por un enlace con vencimiento, y hace previsible el abastecimiento, anticipando cuándo se acaba cada insumo.

**La documentación del proyecto está en el repositorio [MATU](https://github.com/MartinHenriquez131/MATU)**, carpeta `docs/`: arquitectura, modelo de datos, estrategia de pruebas, backlog, prototipo y resultados de la validación. Ese repositorio reúne además las evidencias de cada fase del curso. Este contiene solo el código.

## Estado

| Parte | Estado |
|---|---|
| Entorno local (`infra/`) | PostgreSQL 16 y Redis 7 con Docker Compose. La base arranca con los cuatro roles creados |
| Base de la API (`backend/`) | FastAPI, SQLAlchemy y Alembic configurados. La app se conecta como `matu_app` |
| Modelo de datos (`backend/db/`) | Completo: 49 tablas, 94 políticas RLS forzadas, permisos por rol |
| Migraciones | `0001_esquema_inicial` aplica el modelo completo y tiene vuelta atrás |
| Pruebas | 31 pruebas de aislamiento contra PostgreSQL real |
| Integración continua | GitHub Actions en cada push: estilo, tipos, secretos, migraciones y pruebas |

## Estructura

```
MATU_PROYECTO/
├── README.md
├── .env.example                   plantilla de variables locales (copiar a .env)
├── .secrets.baseline              hallazgos conocidos de detect-secrets
├── .github/
│   ├── PULL_REQUEST_TEMPLATE.md   checklist de la definición de terminado
│   └── workflows/
│       └── ci.yml                 pipeline de integración continua
├── backend/
│   ├── pyproject.toml             dependencias y configuración de ruff, mypy y pytest
│   ├── database.py                conexión de la app, como matu_app
│   ├── models.py                  modelos ORM (se agregan con cada historia)
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py                 migra como matu_owner
│   │   └── versions/
│   │       └── 0001_esquema_inicial.py
│   ├── db/                        modelo de datos en SQL
│   │   ├── 00_roles.sql           los cuatro roles de base de datos
│   │   ├── 01_esquema.sql         49 tablas, restricciones e índices
│   │   ├── 02_rls.sql             94 políticas de aislamiento por fila
│   │   ├── 03_permisos.sql        permisos por rol
│   │   ├── rebuild.sh             reconstrucción rápida sin Alembic, solo para uso local
│   │   ├── gen_diagramas.py       genera los diagramas desde la base
│   │   └── gen_matriz.py          genera la matriz de acceso
│   └── tests/
│       └── test_aislamiento.py    31 pruebas contra PostgreSQL real
└── infra/
    ├── docker-compose.yml         PostgreSQL 16 y Redis 7
    └── postgres/init/
        └── 10_matu.sh             crea roles, base y btree_gist al primer arranque
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

**1. Variables de entorno.** Copia la plantilla y cambia las contraseñas. Las de las URL tienen que calzar con las de arriba.

```
cp .env.example .env
```

**2. Base de datos.** La primera vez que se crea el volumen, el script `infra/postgres/init/10_matu.sh` crea los cuatro roles, la base `matu` y la extensión `btree_gist`.

```
docker compose --env-file .env -f infra/docker-compose.yml up -d
```

**3. Dependencias y migraciones.**

```
cd backend
python -m venv .venv
source .venv/Scripts/activate
pip install -e ".[dev]"
alembic upgrade head
```

**4. Pruebas.**

```
pytest -q
```

Para volver a empezar con la base vacía: `docker compose --env-file .env -f infra/docker-compose.yml down -v` (borra el volumen) y repetir desde el paso 2.

**Diagramas.** `gen_diagramas.py` y `gen_matriz.py` escriben en `../MATU/docs/diagramas/modelo-datos`, es decir, en el repositorio de documentación clonado en la misma carpeta que este. La ruta se cambia con la variable `MATU_DIAGRAMAS`.

## Integración continua

`.github/workflows/ci.yml` corre en cada push y en cada pull request, contra un PostgreSQL 16 desechable:

1. **ruff**: estilo del código
2. **mypy**: tipos
3. **detect-secrets**: que no se suban contraseñas ni claves. Los valores de ejemplo y los del pipeline ya están registrados en `.secrets.baseline`
4. **Migraciones**: subida, bajada y subida de nuevo
5. **pytest**: las pruebas de aislamiento contra la base migrada

Si se agrega un valor de ejemplo que detect-secrets marca por error, se registra con `detect-secrets scan > .secrets.baseline`.

## Forma de trabajo

- Cada cambio se hace en una rama propia (`feat/...`, `fix/...`, `chore/...`) y entra a `main` por pull request.
- La plantilla del pull request trae el checklist de la definición de terminado.
- Todo cambio que toque dinero o datos sensibles lo revisa la otra persona del equipo.
- Las tareas se gestionan en Trello, con el backlog de los sprints 1 a 3.

## Integrantes del equipo

* **Jorge Espinoza** · Product Owner / Developer
* **Martín Henríquez** · Scrum Master / Developer
