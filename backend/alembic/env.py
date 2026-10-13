"""Entorno de Alembic para MATU.

Las migraciones se ejecutan como matu_owner, el dueño del esquema. La URL se lee
de la variable MIGRATIONS_DATABASE_URL, nunca del repositorio.

No hay autogenerate: el esquema se escribe en SQL (backend/db) porque las
políticas RLS, los CHECK y los EXCLUDE no se expresan bien con el ORM.
"""

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool

# Busca el .env en la raíz del repositorio. En el pipeline las variables ya vienen definidas.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None

# La tabla de versiones de Alembic vive en su propio esquema. Si estuviera en public,
# 02_rls.sql le activaría RLS como a cualquier tabla de negocio y Alembic no podría
# registrar la versión.
ESQUEMA_VERSIONES = "alembic"


def url_migraciones() -> str:
    url = os.environ.get("MIGRATIONS_DATABASE_URL")
    if not url:
        raise RuntimeError("Falta MIGRATIONS_DATABASE_URL. Copia .env.example a .env y complétalo.")
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=url_migraciones(),
        target_metadata=target_metadata,
        literal_binds=True,
        version_table_schema=ESQUEMA_VERSIONES,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(url_migraciones(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        connection.exec_driver_sql(f"CREATE SCHEMA IF NOT EXISTS {ESQUEMA_VERSIONES}")
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=ESQUEMA_VERSIONES,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
