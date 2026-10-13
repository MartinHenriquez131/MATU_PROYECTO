# MATU · Sistema de continuidad del cuidado

Repositorio de desarrollo de MATU · Proyecto de Capstone · Ingeniería en Informática · DUOC UC · segundo semestre 2026

MATU ayuda a que el cuidado de una persona mayor dependiente no dependa de una sola persona. Hace transferible lo que sabe quien cuida, con una ficha de relevo que se comparte por un enlace con vencimiento, y hace previsible el abastecimiento, anticipando cuándo se acaba cada insumo.

**La documentación del proyecto está en el repositorio [MATU](https://github.com/MartinHenriquez131/MATU)**, carpeta `docs/`: arquitectura, modelo de datos, estrategia de pruebas, backlog, prototipo y resultados de la validación. Ese repositorio reúne además las evidencias de cada fase del curso. Este contiene solo el código.

## Estado

| Parte | Estado |
|---|---|
| Entorno local (`infra/`) | PostgreSQL 16 y Redis 7 con Docker Compose |
| Base de la API (`backend/`) | FastAPI, SQLAlchemy y Alembic configurados |
| Modelo de datos (`backend/db/`) | Completo y probado: 49 tablas, 94 políticas RLS, 31 pruebas de aislamiento |
| Conexión del modelo con Alembic | Pendiente, historia MATU-02 del sprint 1 |

## Estructura

```
MATU_PROYECTO/
├── README.md
├── .github/
│   └── PULL_REQUEST_TEMPLATE.md   checklist de la definición de terminado
├── backend/
│   ├── database.py                conexión a la base
│   ├── models.py                  modelos de SQLAlchemy
│   ├── alembic.ini
│   ├── alembic/                   migraciones
│   └── db/                        modelo de datos ejecutable
│       ├── 00_roles.sql           los cuatro roles de base de datos
│       ├── 01_esquema.sql         49 tablas, restricciones e índices
│       ├── 02_rls.sql             94 políticas de aislamiento por fila
│       ├── 03_permisos.sql        permisos por rol
│       ├── rebuild.sh             reconstruye la base desde cero
│       ├── gen_diagramas.py       genera los diagramas desde la base
│       ├── gen_matriz.py          genera la matriz de acceso
│       └── tests/
│           └── test_aislamiento.py   31 pruebas contra PostgreSQL real
└── infra/
    └── docker-compose.yml         PostgreSQL 16 y Redis 7
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

**Entorno local.** Desde la raíz del repositorio:

```
docker compose -f infra/docker-compose.yml up -d
```

**Modelo de datos y pruebas de aislamiento.** Por ahora `rebuild.sh` se ejecuta contra un PostgreSQL 16 con el superusuario `postgres`, y el puerto y el host se ajustan con las variables `PGHOST` y `PGPORT`:

```
cd backend/db
PGHOST=localhost PGPORT=5432 ./rebuild.sh
MATU_TEST_DSN="host=localhost port=5432 user=postgres dbname=matu" pytest -q tests/
```

La integración de estos scripts con Docker Compose y Alembic es parte de la historia MATU-02. Cuando esté lista, esta sección se actualiza.

**Diagramas.** `gen_diagramas.py` y `gen_matriz.py` escriben en `../MATU/docs/diagramas/modelo-datos`, es decir, en el repositorio de documentación clonado en la misma carpeta que este. La ruta se cambia con la variable `MATU_DIAGRAMAS`.

## Forma de trabajo

- Cada cambio se hace en una rama propia (`feat/...`, `fix/...`, `chore/...`) y entra a `main` por pull request.
- La plantilla del pull request trae el checklist de la definición de terminado.
- Todo cambio que toque dinero o datos sensibles lo revisa la otra persona del equipo.
- Las tareas se gestionan en Trello, con el backlog de los sprints 1 a 3.

## Integrantes del equipo

* **Jorge Espinoza** · Product Owner / Developer
* **Martín Henríquez** · Scrum Master / Developer
