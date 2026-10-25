"""Conexión de la aplicación a la base y contexto de tenant (arquitectura, sección 7.7).

La API se conecta como matu_app, que no es dueño de ninguna tabla. Por eso las políticas
RLS lo alcanzan siempre. La URL viene de DATABASE_URL.

Toda transacción que toque tablas con RLS se abre con sesion_tenant, que fija el contexto
(app.usuario_id, app.grupo_id, ...) local a esa transacción.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import obtener_configuracion


class Base(DeclarativeBase):
    """Base de los modelos ORM. Cada módulo declara los suyos en su carpeta infrastructure/,
    calzando con las tablas que ya crea la migración 0001."""


@lru_cache
def obtener_engine() -> Engine:
    url = obtener_configuracion().database_url
    if not url:
        raise RuntimeError("Falta DATABASE_URL. Copia .env.example a .env y complétalo.")
    return create_engine(url, pool_pre_ping=True)


@lru_cache
def fabrica_sesiones() -> sessionmaker[Session]:
    return sessionmaker(bind=obtener_engine(), autoflush=False, expire_on_commit=False)


def obtener_fabrica_sesiones() -> sessionmaker[Session]:
    """Dependencia de FastAPI que entrega la fábrica de sesiones. Las pruebas la sobreescriben."""
    return fabrica_sesiones()


# Valores de app.rol que el helper acepta (db/02_rls.sql). Sin rol, app_rol() es 'ninguno'.
ROLES_CONTEXTO = frozenset({"sistema", "relevo", "operacion"})

_SET_CONFIG = text("SELECT set_config(:clave, :valor, true)")


@contextmanager
def sesion_tenant(
    fabrica: sessionmaker[Session],
    *,
    usuario_id: uuid.UUID | None = None,
    grupo_id: uuid.UUID | None = None,
    comercio_id: uuid.UUID | None = None,
    repartidor_id: uuid.UUID | None = None,
    acceso_relevo_id: uuid.UUID | None = None,
    rol: str | None = None,
) -> Iterator[Session]:
    """Abre una sesión con una transacción y fija el contexto de tenant (arquitectura, sección 7.7).

    - Fija con set_config(clave, valor, true), local a la transacción: al terminar, la conexión
      vuelve al pool sin contexto y la petición siguiente no lo hereda.
    - El orden importa: primero app.usuario_id, después app.grupo_id, app.comercio_id,
      app.repartidor_id, app.acceso_relevo_id y app.rol. La política membresia_propia depende de
      app.usuario_id, y la verificación de membresía corre dentro de este contexto.
    - Solo fija las variables que llegan. Las demás quedan sin valor y sus políticas no alcanzan nada.
    - Al salir sin error hace commit. Si hay una excepción, rollback, y la excepción sigue.

    No verifica la membresía: core no conoce la tabla membresia. Lo hace la dependencia de
    care_circle (sesion_de_grupo), dentro de este mismo contexto.

    Lanza ValueError si rol no está en ROLES_CONTEXTO, o si la sesión es de relevo (rol 'relevo'
    o acceso_relevo_id) y además trae grupo_id: el relevo nunca fija app.grupo_id, porque
    heredaría todas las políticas de familia (modelo de datos, sección 5.4, hallazgo 2).
    """
    if rol is not None and rol not in ROLES_CONTEXTO:
        raise ValueError(f"rol de contexto no permitido: {rol!r}")
    if grupo_id is not None and (acceso_relevo_id is not None or rol == "relevo"):
        raise ValueError("una sesión de relevo nunca fija app.grupo_id (modelo de datos, sección 5.4, hallazgo 2)")

    contexto = (
        ("app.usuario_id", usuario_id),
        ("app.grupo_id", grupo_id),
        ("app.comercio_id", comercio_id),
        ("app.repartidor_id", repartidor_id),
        ("app.acceso_relevo_id", acceso_relevo_id),
        ("app.rol", rol),
    )
    with fabrica() as sesion, sesion.begin():
        for clave, valor in contexto:
            if valor is not None:
                sesion.execute(_SET_CONFIG, {"clave": clave, "valor": str(valor)})
        yield sesion
