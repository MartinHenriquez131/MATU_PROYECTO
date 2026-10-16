"""Conexión de la aplicación a la base.

La API se conecta como matu_app, que no es dueño de ninguna tabla. Por eso las políticas
RLS lo alcanzan siempre (arquitectura, sección 7.7). La URL viene de DATABASE_URL.

El contexto de tenant (app.usuario_id, app.grupo_id) lo fija sesion_tenant, de MATU-02,
sobre las sesiones que entrega este módulo.
"""

from functools import lru_cache

from sqlalchemy import Engine, create_engine
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
