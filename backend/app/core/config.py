"""Configuración de la API.

Todo valor sensible (contraseñas, claves, cadenas de conexión) se lee del entorno o del
archivo .env de la raíz del repositorio, nunca del código. En el pipeline las variables
ya vienen definidas y el .env no existe.

Cada historia agrega aquí lo suyo:
- MATU-04: PEPPER_EMAIL, la llave del HMAC de indice_credencial
- MATU-05a: JWT_CLAVE, la clave del access token. El algoritmo (HS256) y la duración
  (15 minutos) son fijos y viven en el código, no aquí
- MATU-26: POLITICA_VERSION, la versión vigente de la política de privacidad. Por ahora es
  opcional; MATU-07 la exige fuera del ambiente de pruebas
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py → la raíz del repositorio está tres niveles más arriba
RAIZ_REPOSITORIO = Path(__file__).resolve().parents[3]


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=RAIZ_REPOSITORIO / ".env",
        env_file_encoding="utf-8",
        # El .env también tiene las variables de Alembic y de las pruebas de aislamiento
        extra="ignore",
        # Un error de validación no copia el valor recibido: puede ser un secreto (PEPPER_EMAIL o
        # JWT_CLAVE demasiado cortas) y el error termina en el log de arranque
        hide_input_in_errors=True,
    )

    entorno: Literal["local", "pruebas", "produccion"] = "local"
    log_nivel: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Conexión de la API como matu_app. Vacía solo en pruebas que no tocan la base.
    database_url: str = ""

    # Versión vigente de la política de privacidad (docs/legal/politica-privacidad.md del
    # repositorio MATU), en formato MAYOR.MENOR. Un valor con otro formato impide cargar la
    # configuración. Aquí es opcional: exigirla fuera del ambiente de pruebas es de MATU-07.
    politica_version: str | None = Field(default=None, pattern=r"^[0-9]+\.[0-9]+$")

    # Llave del HMAC-SHA256 del email en indice_credencial (modelo de datos, hallazgo 4). Vive
    # fuera de la base y del repositorio: sin ella, el hash no se revierte con un diccionario de
    # emails. Cambiarla deja inservibles los índices ya guardados. Opcional para cargar la
    # configuración; crear una cuenta sin ella falla.
    pepper_email: SecretStr | None = Field(default=None, min_length=32)

    # Clave HMAC con que se firman y verifican los access tokens (JWT HS256, MATU-05a). Vive fuera
    # del repositorio. Cambiarla invalida todos los tokens emitidos. Opcional para cargar la
    # configuración; emitir o validar un token sin ella falla.
    jwt_clave: SecretStr | None = Field(default=None, min_length=32)

    @field_validator("pepper_email", "jwt_clave", mode="before")
    @classmethod
    def _secreto_vacio_es_ausente(cls, valor: object) -> object:
        # PEPPER_EMAIL= o JWT_CLAVE= en el .env cuentan como no definidas
        return None if valor == "" else valor


@lru_cache
def obtener_configuracion() -> Configuracion:
    return Configuracion()
