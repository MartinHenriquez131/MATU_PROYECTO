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
- MATU-18: PEPPER_PIN, la llave del HMAC del PIN del acceso de relevo, y ORIGEN_WEB, el origen https
  del enlace /r#<token> que se entrega al compartir
- MATU-19: REDIS_URL, el Redis de las sesiones de relevo
- MATU-23: WEB_DIST, la carpeta del build de web/ que la API sirve en /r. Por omisión <repo>/web/dist.
  Si no existe (el CI no hace build), la API arranca igual y /r responde 404 RFC 7807
- MATU-38: PEPPER_LIMITES, la llave del HMAC de las huellas de la IP y del email de la demora
  progresiva de la entrada (decisión 49). Distinta de los demás secretos. Sin ella, la entrada
  responde 503 y falla cerrada
- MATU-57: PEPPER_RECUPERACION, la llave del HMAC de los códigos de recuperación y de verificación
  del celular (decisión 81). Distinta de los demás secretos. Sin ella, esas rutas responden 503.
  ENVIADOR_CODIGOS=simulado enciende el envío simulado (decisión 82): no envía nada y deja el mensaje
  en un registro de desarrollo. Solo con ENTORNO local o pruebas: con produccion la API no arranca
- MATU-25: ENTORNO admite staging (decisión 105, que amplía la D-A). La KEK en variable de entorno y el
  envío simulado tienen cada uno su lista permitida (ENTORNOS_KEK_SINTETICA y ENTORNOS_ENVIO_SIMULADO),
  y en staging el registro de cuentas solo acepta correos de dominios reservados
- MATU-41: ENVIADOR_AVISOS=simulado enciende el envío simulado de los avisos por correo y push (decisión 112):
  no envía nada y deja notificacion_id, usuario_id, canal y plantilla, sin el destino ni el texto, en
  REGISTRO_AVISOS (por omisión .dev/avisos.jsonl). Solo con ENTORNO en ENTORNOS_ENVIO_SIMULADO: con
  produccion la configuración no carga. Sin ENVIADOR_AVISOS, el publicador de avisos no envía nada y no
  consume los eventos
- MATU-25 (decisión 114, punto 7): DIAGNOSTICO_PROXY, el diagnóstico temporal de X-Forwarded-For
  (app/core/proxy.py). Apagado por omisión; con ENTORNO=produccion, encendido impide cargar la
  configuración. PROXY_SALTOS y FORWARDED_ALLOW_IPS no viven aquí: los valida app/servidor.py
- MATU-58: WEB_DIST también es la app de familia, que la API entrega en toda ruta que no sea de la API
  (decisión 115). /docs y /openapi.json solo se publican en ENTORNOS_DOCUMENTACION (local y pruebas)
- MATU-40: CAPA3_HABILITADA, si la API monta los routers de la capa 3, el despacho (ADR-002). Apagada
  por omisión: las capas 1 y 2 no dependen de ella y la API arranca igual. Ver app/main.py
- MATU-75: POLITICA_ACTUALIZADA_EN, la fecha de la versión vigente de la política (AAAA-MM-DD), y CORREO_PRIVACIDAD,
  el correo de contacto que GET /v1/politica entrega aparte del texto (decisiones D5 y D7). Opcionales para cargar
  la configuración: sin la fecha, o si POLITICA_VERSION no tiene un texto publicado sin marcadores, GET /v1/politica
  y POST /v1/usuarios responden 503 y el resto de la API funciona igual
- MATU-74 (hallazgos H2 y H4): SCHEDULER_DATABASE_URL y PUBLISHER_DATABASE_URL, las conexiones de las tareas como
  matu_scheduler y matu_publisher (app/tareas.py). La API nunca las usa. Vacías, la configuración carga igual y la
  tarea que las necesita falla con un error que nombra la variable, sin caer a matu_app. El envío simulado de avisos
  escribe REGISTRO_AVISOS solo con ENTORNO en ENTORNOS_REGISTRO_AVISOS (local y pruebas): en staging el registro de
  los avisos es la tabla notificacion
"""

import base64
import binascii
from datetime import date
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

# Los valores de ENTORNO. Se comparan tal cual, sin normalizar mayúsculas ni espacios: "Staging", "stage"
# o "prod" no cargan la configuración
Entorno = Literal["local", "pruebas", "staging", "produccion"]

# Entornos donde se admite la KEK en variable de entorno (MATU-12, decisión D-A; staging por la decisión
# 105). Lista permitida: produccion, o un valor nuevo, quedan fuera. El adaptador CustodiaKekEntorno usa
# esta misma lista
ENTORNOS_KEK_SINTETICA: frozenset[str] = frozenset({"local", "pruebas", "staging"})

# Entornos donde se admite ENVIADOR_CODIGOS=simulado (decisión 82; staging por la decisión 105). Es otra
# lista, aunque hoy tenga los mismos valores: ampliar una no amplía la otra
ENTORNOS_ENVIO_SIMULADO: frozenset[str] = frozenset({"local", "pruebas", "staging"})

# Entornos que publican la documentación de la API, /docs y /openapi.json (MATU-58, decisión 115). Lista
# permitida, como las anteriores: en staging y produccion, o con un valor nuevo, responden 404
ENTORNOS_DOCUMENTACION: frozenset[str] = frozenset({"local", "pruebas"})

# Entornos donde el registro de cuentas solo acepta correos de dominios reservados (decisión 105, (i)):
# staging tiene solo datos sintéticos
ENTORNOS_SOLO_DOMINIOS_RESERVADOS: frozenset[str] = frozenset({"staging"})

# Entornos donde el envío simulado de avisos escribe REGISTRO_AVISOS (MATU-74, hallazgo H4). En staging el archivo
# se perdía con cada contenedor del cron, y el registro de lo enviado ya es la tabla notificacion (estado y enviada_en)
ENTORNOS_REGISTRO_AVISOS: frozenset[str] = frozenset({"local", "pruebas"})

# Entornos donde se admite DIAGNOSTICO_PROXY encendido (MATU-25, decisión 114, punto 7). Otra lista más:
# produccion, o un valor nuevo, quedan fuera
ENTORNOS_DIAGNOSTICO_PROXY: frozenset[str] = frozenset({"local", "pruebas", "staging"})
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

    entorno: Entorno = "local"
    log_nivel: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Conexión de la API como matu_app. Vacía solo en pruebas que no tocan la base.
    database_url: str = ""

    # MATU-74 (H2): las conexiones de las tareas, nunca de la API. SCHEDULER_DATABASE_URL como matu_scheduler, para
    # enumerar los grupos y llamar a las funciones de borrado y conservación; PUBLISHER_DATABASE_URL como
    # matu_publisher, para las funciones del outbox. El trabajo por grupo sigue con DATABASE_URL (matu_app y RLS)
    scheduler_database_url: str = ""
    publisher_database_url: str = ""

    # Versión vigente de la política de privacidad (docs/legal/politica-privacidad.md del
    # repositorio MATU), en formato MAYOR.MENOR. Un valor con otro formato impide cargar la
    # configuración. Fuera del ambiente de pruebas es obligatoria (MATU-07): cada consentimiento
    # guarda esta versión, y el cliente nunca la envía. Después de validar, nunca es None.
    politica_version: str | None = Field(default=None, pattern=r"^[0-9]+\.[0-9]+$")

    # MATU-75: fecha de la versión vigente de la política, en AAAA-MM-DD. GET /v1/politica la entrega con el texto
    # («Versión 0.11 · actualizada el DD/MM/AAAA»). Sin ella, esa ruta y crear una cuenta responden 503
    politica_actualizada_en: date | None = None

    # MATU-75 (decisiones D5 y D7): el correo de contacto para temas de privacidad, una dirección de la función y
    # nunca personal (cuidaconmatu@gmail.com). GET /v1/politica lo entrega aparte (correo_contacto) para el mailto: de
    # «Tu cuenta»; el texto de la política ya lo trae escrito. No es un secreto. Sin él, correo_contacto es null
    correo_privacidad: str | None = Field(default=None, max_length=254, pattern=r"^[^@\s{}]+@[^@\s{}]+\.[^@\s{}]+$")

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
    # local, pruebas o staging y solo con datos sintéticos. El proveedor de producción lo decide el ADR-019.
    custodia_kek: Literal["entorno_sintetico"] | None = None

    # La KEK: 32 bytes aleatorios en base64. Nunca en el repositorio ni en docker-compose. Genérala
    # con: python -c "import base64, secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())"
    kek_entorno: SecretStr | None = None

    # Versión fija de la KEK. Si la clave cambia, cambia la versión: una DEK envuelta con otra clave
    # bajo la misma versión no se desenvuelve, y nunca se reemplaza por una nueva.
    kek_version: int = Field(default=1, ge=1)

    # Llave del HMAC-SHA256 del PIN del acceso de relevo (MATU-18, contrato: notas para implementar).
    # Vive fuera de la base: sin ella, una copia de acceso_relevo no basta para recuperar un PIN de 4
    # dígitos por fuerza bruta. Distinta de los otros secretos. Opcional para cargar la configuración;
    # sin ella, compartir responde 503 y falla cerrado.
    pepper_pin: SecretStr | None = Field(default=None, min_length=32)

    # Llave del HMAC-SHA256 de las huellas de la demora progresiva de la entrada (MATU-38, decisión 49):
    # la IP y el email nunca llegan en claro a Redis. MATU-25 puede compartirla con otro prefijo.
    # Distinta de los otros secretos. Opcional para cargar la configuración; sin ella, POST /v1/sesiones
    # responde 503 y falla cerrada.
    pepper_limites: SecretStr | None = Field(default=None, min_length=32)

    # Llave del HMAC-SHA256 de los códigos de 6 dígitos de MATU-57 (decisión 81): Redis guarda solo la
    # huella del código, nunca el código. Distinta de los otros secretos. Opcional para cargar la
    # configuración; sin ella, las rutas de recuperación y del celular responden 503 y fallan cerradas.
    # Genérala con: python -c "import secrets; print(secrets.token_urlsafe(48))"
    pepper_recuperacion: SecretStr | None = Field(default=None, min_length=32)

    # Cómo se envían los códigos (decisión 82). En el semestre solo existe "simulado": no envía nada y
    # deja el mensaje en un registro de desarrollo (en memoria y, si se define, en REGISTRO_ENVIOS).
    # Sin valor, las rutas que envían responden 503. Con ENTORNO=produccion, "simulado" impide cargar
    # la configuración y la API no arranca.
    enviador_codigos: Literal["simulado"] | None = None

    # Archivo JSON Lines donde el envío simulado deja cada mensaje, para probar a mano. Debe estar en
    # una carpeta ignorada por git (por ejemplo .dev/envios.jsonl). Nunca es un log de la aplicación
    registro_envios: Path | None = None

    # Cómo se envían los avisos por correo y push de MATU-41 (decisión 112). En el semestre solo "simulado":
    # no envía nada y deja en REGISTRO_AVISOS el id de la notificación, la persona, el canal y la plantilla,
    # nunca el destino ni el texto. Sin valor, el publicador de avisos no envía ni consume. Con
    # ENTORNO=produccion, "simulado" impide cargar la configuración
    enviador_avisos: Literal["simulado"] | None = None

    # Archivo JSON Lines del envío simulado de avisos, en una carpeta ignorada por git. Por omisión
    # <repositorio>/.dev/avisos.jsonl. Nunca es un log de la aplicación
    registro_avisos: Path | None = None

    # Origen https de la aplicación web, sin barra final: el enlace del relevo es <origen>/r#<token>
    origen_web: str = Field(default="https://localhost", pattern=r"^https://[^/#?]+$")

    # Redis de las sesiones de relevo (MATU-19). Local por omisión; en otro entorno, desde .env
    redis_url: str = "redis://127.0.0.1:6379/0"

    # Build de la aplicación web (MATU-23, ADR-026): la API sirve index.html en /r y en las rutas de la
    # app de familia (MATU-58), y los archivos de /assets, en el mismo origen. Sin la carpeta, /r y las
    # rutas de la app responden 404 y el resto de la API no cambia
    web_dist: Path = RAIZ_REPOSITORIO / "web" / "dist"

    # Diagnóstico temporal del proxy (MATU-25, decisión 114, punto 7): una línea por petición de origen
    # confiable con la cantidad y la clase de los elementos de X-Forwarded-For, nunca una IP. Solo lo usa
    # python -m app.servidor. Apagado por omisión; con ENTORNO=produccion, encendido no carga
    diagnostico_proxy: bool = False

    # Capa 3, el despacho (MATU-40, ADR-002): con true, la API monta los routers de ROUTERS_CAPA_3 de
    # app/main.py. Apagada por omisión: sin convenio no hay despacho, y la ficha, el relevo y el consumo
    # funcionan igual. No es un secreto
    capa3_habilitada: bool = False

    # MATU-61 (C5 y P12): el envío único de cada pedido, en pesos enteros con IVA incluido. Uno por pedido aunque lo
    # preparen varios comercios (ADR-027). El valor de ejemplo de la arquitectura 8.2. No es un secreto
    costo_envio: int = Field(default=3990, ge=0, le=100_000)

    @field_validator(
        "pepper_email", "jwt_clave", "kek_entorno", "custodia_kek", "pepper_pin", "pepper_limites",
        "pepper_recuperacion", "enviador_codigos", "registro_envios", "enviador_avisos", "registro_avisos",
        "politica_actualizada_en", "correo_privacidad",
        mode="before",
    )
    @classmethod
    def _secreto_vacio_es_ausente(cls, valor: object) -> object:
        # PEPPER_EMAIL=, JWT_CLAVE=, KEK_ENTORNO= o CUSTODIA_KEK= en el .env cuentan como no definidas
        return None if valor == "" else valor

    @field_validator("diagnostico_proxy", mode="before")
    @classmethod
    def _diagnostico_vacio_es_apagado(cls, valor: object) -> object:
        # DIAGNOSTICO_PROXY= en el .env cuenta como apagado
        return False if valor == "" else valor

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
            raise ValueError("La KEK en variable de entorno solo se admite con ENTORNO local, pruebas o staging")
        return self

    @model_validator(mode="after")
    def _custodia_encendida_exige_kek(self) -> "Configuracion":
        # Condición (b): encender la custodia sin la clave es un error de configuración y la API no
        # arranca, en vez de quedar en silencio respondiendo 503. Sin CUSTODIA_KEK la ficha sigue
        # fallando cerrada con 503. El mensaje nombra las variables, nunca sus valores.
        if self.custodia_kek is not None and self.kek_entorno is None:
            raise ValueError("CUSTODIA_KEK está encendida pero falta KEK_ENTORNO")
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
    def _pepper_pin_distinto_de_otros_secretos(self) -> "Configuracion":
        # El mensaje nombra las variables, nunca sus valores
        if self.pepper_pin is None:
            return self
        pin = self.pepper_pin.get_secret_value()
        for nombre, secreto in (
            ("PEPPER_EMAIL", self.pepper_email), ("JWT_CLAVE", self.jwt_clave), ("KEK_ENTORNO", self.kek_entorno)
        ):
            if secreto is not None and secreto.get_secret_value() == pin:
                raise ValueError(f"PEPPER_PIN y {nombre} deben ser claves distintas")
        return self

    @model_validator(mode="after")
    def _pepper_limites_distinto_de_otros_secretos(self) -> "Configuracion":
        # El mensaje nombra las variables, nunca sus valores
        if self.pepper_limites is None:
            return self
        limites = self.pepper_limites.get_secret_value()
        for nombre, secreto in (
            ("PEPPER_EMAIL", self.pepper_email),
            ("JWT_CLAVE", self.jwt_clave),
            ("KEK_ENTORNO", self.kek_entorno),
            ("PEPPER_PIN", self.pepper_pin),
        ):
            if secreto is not None and secreto.get_secret_value() == limites:
                raise ValueError(f"PEPPER_LIMITES y {nombre} deben ser claves distintas")
        return self

    @model_validator(mode="after")
    def _pepper_recuperacion_distinto_de_otros_secretos(self) -> "Configuracion":
        # El mensaje nombra las variables, nunca sus valores
        if self.pepper_recuperacion is None:
            return self
        recuperacion = self.pepper_recuperacion.get_secret_value()
        for nombre, secreto in (
            ("PEPPER_EMAIL", self.pepper_email),
            ("JWT_CLAVE", self.jwt_clave),
            ("KEK_ENTORNO", self.kek_entorno),
            ("PEPPER_PIN", self.pepper_pin),
            ("PEPPER_LIMITES", self.pepper_limites),
        ):
            if secreto is not None and secreto.get_secret_value() == recuperacion:
                raise ValueError(f"PEPPER_RECUPERACION y {nombre} deben ser claves distintas")
        return self

    @model_validator(mode="after")
    def _envio_simulado_solo_fuera_de_produccion(self) -> "Configuracion":
        # Decisión 82: el envío simulado no llega a nadie. En produccion la API no arranca con él.
        # Su lista es ENTORNOS_ENVIO_SIMULADO, no la de la KEK (decisión 105)
        if self.enviador_codigos == "simulado" and self.entorno not in ENTORNOS_ENVIO_SIMULADO:
            raise ValueError("ENVIADOR_CODIGOS=simulado solo se admite con ENTORNO local, pruebas o staging")
        return self

    @model_validator(mode="after")
    def _avisos_simulados_solo_fuera_de_produccion(self) -> "Configuracion":
        # MATU-41 (decisión 112): los avisos simulados no llegan a nadie. Misma lista que el envío de códigos
        if self.enviador_avisos == "simulado" and self.entorno not in ENTORNOS_ENVIO_SIMULADO:
            raise ValueError("ENVIADOR_AVISOS=simulado solo se admite con ENTORNO local, pruebas o staging")
        return self

    @model_validator(mode="after")
    def _diagnostico_proxy_solo_fuera_de_produccion(self) -> "Configuracion":
        # Condición 2 del analista normativo (MATU-25): el diagnóstico es temporal y de staging. En
        # produccion la API no arranca con él encendido. El mensaje nombra la variable, nunca su valor
        if self.diagnostico_proxy and self.entorno not in ENTORNOS_DIAGNOSTICO_PROXY:
            raise ValueError("DIAGNOSTICO_PROXY solo se admite con ENTORNO local, pruebas o staging")
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
