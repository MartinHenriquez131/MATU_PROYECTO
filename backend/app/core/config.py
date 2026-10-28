"""Configuración de la API.

Todo valor sensible (contraseñas, claves, cadenas de conexión) se lee del entorno o del
archivo .env de la raíz del repositorio, nunca del código. En el pipeline las variables
ya vienen definidas y el .env no existe.

Cada historia agrega aquí lo suyo:
- MATU-04: PEPPER_EMAIL, la llave del HMAC de indice_credencial
- MATU-05a: JWT_CLAVE, la clave del access token. El algoritmo (HS256) y la duración
  (15 minutos) son fijos y viven en el código, no aquí
- MATU-26: POLITICA_VERSION, la versión vigente de la política de privacidad
- MATU-07: POLITICA_VERSION pasa a ser obligatoria fuera del ambiente de pruebas. Sin ella la
  configuración no carga y la API no arranca. Con ENTORNO=pruebas, si falta, se usa
  POLITICA_VERSION_FABRICA
- MATU-12: CUSTODIA_KEK, KEK_ENTORNO y KEK_VERSION, la KEK en variable de entorno (decisión D-A de
  Jorge del 28-10, desvío explícito del ADR-016). Solo con ENTORNO local o pruebas y datos
  sintéticos: con cualquier otro entorno, definir una de ellas impide cargar la configuración y la
  API no arranca. Ver app/modules/care_plan/infrastructure/custodia_kek_entorno.py
"""

import base64
import binascii
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py → la raíz del repositorio está tres niveles más arriba
RAIZ_REPOSITORIO = Path(__file__).resolve().parents[3]

# Versión de la política que usan las pruebas cuando POLITICA_VERSION no está definida (MATU-07).
# 0.0 no es una versión publicada: un consentimiento guardado con ella es, a la vista, sintético.
POLITICA_VERSION_FABRICA = "0.0"

# Entornos donde se admite la KEK en variable de entorno (MATU-12, decisión D-A). Lista permitida:
# produccion, o un valor nuevo, quedan fuera
ENTORNOS_KEK_SINTETICA = frozenset({"local", "pruebas"})
LARGO_KEK = 32


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
    # configuración. Fuera del ambiente de pruebas es obligatoria (MATU-07): cada consentimiento
    # guarda esta versión, y el cliente nunca la envía. Después de validar, nunca es None.
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

    # Custodia de la KEK de la ficha (MATU-12, decisión D-A). Apagada por omisión: sin ella las rutas
    # de la ficha responden 503. "entorno_sintetico" la enciende con la KEK de KEK_ENTORNO, solo en
    # local o pruebas y solo con datos sintéticos. El proveedor de producción lo decide el ADR-019.
    custodia_kek: Literal["entorno_sintetico"] | None = None

    # La KEK: 32 bytes aleatorios en base64. Nunca en el repositorio ni en docker-compose. Genérala
    # con: python -c "import base64, secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())"
    kek_entorno: SecretStr | None = None

    # Versión fija de la KEK. Si la clave cambia, cambia la versión: una DEK envuelta con otra clave
    # bajo la misma versión no se desenvuelve, y nunca se reemplaza por una nueva.
    kek_version: int = Field(default=1, ge=1)

    @field_validator("pepper_email", "jwt_clave", "kek_entorno", "custodia_kek", mode="before")
    @classmethod
    def _secreto_vacio_es_ausente(cls, valor: object) -> object:
        # PEPPER_EMAIL=, JWT_CLAVE=, KEK_ENTORNO= o CUSTODIA_KEK= en el .env cuentan como no definidas
        return None if valor == "" else valor

    @field_validator("kek_entorno")
    @classmethod
    def _kek_de_32_bytes(cls, valor: SecretStr | None) -> SecretStr | None:
        # El mensaje es fijo: nunca lleva la clave (y hide_input_in_errors oculta el valor recibido)
        if valor is None:
            return None
        try:
            crudo = base64.b64decode(valor.get_secret_value(), validate=True)
        except (binascii.Error, ValueError):
            crudo = b""
        if len(crudo) != LARGO_KEK:
            raise ValueError("KEK_ENTORNO debe ser una clave de 32 bytes aleatorios en base64")
        return valor

    @model_validator(mode="after")
    def _kek_solo_en_entornos_sinteticos(self) -> "Configuracion":
        # Condición (a) del analista normativo: lista permitida. Con produccion, una KEK en el entorno
        # o la custodia encendida impiden cargar la configuración, y la API no arranca.
        if (self.custodia_kek is not None or self.kek_entorno is not None) and (
            self.entorno not in ENTORNOS_KEK_SINTETICA
        ):
            raise ValueError("La KEK en variable de entorno solo se admite con ENTORNO local o pruebas")
        return self

    @model_validator(mode="after")
    def _kek_distinta_de_otros_secretos(self) -> "Configuracion":
        # Condición (c): la KEK no reutiliza otro secreto. Se compara el texto y los bytes. El mensaje
        # nombra las variables, nunca sus valores.
        if self.kek_entorno is None:
            return self
        kek = self.kek_entorno.get_secret_value()
        kek_bytes = base64.b64decode(kek)
        for nombre, secreto in (("JWT_CLAVE", self.jwt_clave), ("PEPPER_EMAIL", self.pepper_email)):
            if secreto is None:
                continue
            valor = secreto.get_secret_value()
            if valor == kek or valor.encode("utf-8") == kek_bytes:
                raise ValueError(f"KEK_ENTORNO y {nombre} deben ser claves distintas")
        if kek in self.database_url:
            raise ValueError("KEK_ENTORNO no puede ser parte de DATABASE_URL")
        return self

    @model_validator(mode="after")
    def _jwt_clave_distinta_de_pepper(self) -> "Configuracion":
        # Condición del analista normativo: firmar tokens y calcular el HMAC del email con la misma
        # clave acopla ambos secretos. El mensaje nombra las variables, nunca sus valores.
        if (
            self.pepper_email is not None
            and self.jwt_clave is not None
            and self.pepper_email.get_secret_value() == self.jwt_clave.get_secret_value()
        ):
            raise ValueError("JWT_CLAVE y PEPPER_EMAIL deben ser claves distintas")
        return self

    @model_validator(mode="after")
    def _politica_version_obligatoria(self) -> "Configuracion":
        # MATU-07: sin la versión de la política no se puede registrar un consentimiento válido.
        # Fuera de pruebas la configuración no carga y la API no arranca (app.main crea la app al
        # importarse). En pruebas se usa la versión de fábrica.
        if self.politica_version is None:
            if self.entorno != "pruebas":
                raise ValueError("Falta POLITICA_VERSION: fuera del ambiente de pruebas la API no arranca sin ella")
            self.politica_version = POLITICA_VERSION_FABRICA
        return self


@lru_cache
def obtener_configuracion() -> Configuracion:
    return Configuracion()
