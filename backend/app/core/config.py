"""Configuración de la API.

Todo valor sensible (contraseñas, claves, cadenas de conexión) se lee del entorno o del
archivo .env de la raíz del repositorio, nunca del código. En el pipeline las variables
ya vienen definidas y el .env no existe.

Cada historia agrega aquí lo suyo:
- MATU-05a: la clave y el algoritmo del JWT
- MATU-26: POLITICA_VERSION, la versión vigente de la política de privacidad. Por ahora es
  opcional; MATU-07 la exige fuera del ambiente de pruebas
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py → la raíz del repositorio está tres niveles más arriba
RAIZ_REPOSITORIO = Path(__file__).resolve().parents[3]


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=RAIZ_REPOSITORIO / ".env",
        env_file_encoding="utf-8",
        # El .env también tiene las variables de Alembic y de las pruebas de aislamiento
        extra="ignore",
    )

    entorno: Literal["local", "pruebas", "produccion"] = "local"
    log_nivel: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Conexión de la API como matu_app. Vacía solo en pruebas que no tocan la base.
    database_url: str = ""

    # Versión vigente de la política de privacidad (docs/legal/politica-privacidad.md del
    # repositorio MATU), en formato MAYOR.MENOR. Un valor con otro formato impide cargar la
    # configuración. Aquí es opcional: exigirla fuera del ambiente de pruebas es de MATU-07.
    politica_version: str | None = Field(default=None, pattern=r"^[0-9]+\.[0-9]+$")


@lru_cache
def obtener_configuracion() -> Configuracion:
    return Configuracion()
