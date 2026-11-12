"""Esquemas de la API de iam.

Los mensajes de validación propios nunca incluyen el valor recibido: el manejador de 422 copia
el mensaje tal cual (app/core/errores.py), y el valor puede ser una contraseña.
"""

import re
import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

from app.modules.iam.domain.credenciales import (
    LARGO_MAXIMO_CONTRASENA,
    LARGO_MAXIMO_EMAIL,
    LARGO_MINIMO_CONTRASENA,
)
from app.modules.iam.domain.dispositivo import LARGO_MAXIMO_NOMBRE, LARGO_MAXIMO_PUSH, push_admitido
from app.shared.celular import normalizar_celular

# Forma básica: algo, una @, un dominio con al menos un punto, sin espacios. La verificación
# real del email llega con el adaptador de correo (sprint 3).
_FORMA_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SolicitudRegistro(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: Annotated[str, Field(min_length=1, max_length=100)]
    email: Annotated[str, Field(max_length=LARGO_MAXIMO_EMAIL)]
    contrasena: Annotated[str, Field(min_length=LARGO_MINIMO_CONTRASENA, max_length=LARGO_MAXIMO_CONTRASENA)]
    telefono: Annotated[
        str,
        Field(
            max_length=20,
            json_schema_extra={"pattern": r"^(\+?56 ?)?9( ?[0-9]){8}$", "examples": ["+56 9 1234 5678"]},
            description=(
                "Celular chileno, obligatorio (decisión 65): 9 y ocho dígitos, con o sin +56 y con o sin"
                " espacios. Se guarda en E.164 (+569XXXXXXXX). Sirve para recuperar el acceso (MATU-57)."
                " Nunca aparece en logs ni en la auditoría"
            ),
        ),
    ]

    # MATU-75 (decisiones D2 y D3): la casilla «Leí y acepto la política de privacidad.», obligatoria y en true
    acepta_politica: Annotated[
        bool,
        Field(
            strict=True,
            json_schema_extra={"const": True},
            description=(
                "Obligatorio y en true: la persona marcó «Leí y acepto la política de privacidad.» (MATU-75). Sin él"
                " o en false, 422 con errores[].campo = acepta_politica. El servidor guarda la versión y la huella"
                " vigentes, nunca las que diga el cliente"
            ),
        ),
    ]
    # MATU-75 (P2 de la decisión D2, obligatoria desde el cierre del analista, decisión 182): la huella de la política
    # que la pantalla mostró, la de GET /v1/politica
    huella_politica: Annotated[
        str,
        Field(
            pattern=r"^[0-9a-f]{64}$",
            description=(
                "Obligatoria. La huella (SHA-256 en hexadecimal) de la política que se mostró, tal como la entregó"
                " GET /v1/politica. Sin ella o mal formada, 422 con errores[].campo = huella_politica. Si no es la"
                " vigente, 409 politica-cambio y la cuenta no se crea"
            ),
        ),
    ]

    @field_validator("acepta_politica")
    @classmethod
    def _politica_aceptada(cls, valor: bool) -> bool:
        if valor is not True:
            raise PydanticCustomError("politica_no_aceptada", "marca que leíste la política de privacidad")
        return valor

    @field_validator("nombre")
    @classmethod
    def _nombre_no_vacio(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("el nombre no puede estar vacío")
        return valor

    @field_validator("email")
    @classmethod
    def _forma_de_email(cls, valor: str) -> str:
        if not _FORMA_EMAIL.match(valor.strip()):
            raise ValueError("no tiene la forma de un email")
        return valor

    @field_validator("telefono")
    @classmethod
    def _celular_chileno(cls, valor: str) -> str:
        normalizado = normalizar_celular(valor.strip())
        if normalizado is None:
            raise PydanticCustomError("celular_invalido", "no es un celular chileno (+56 9 y ocho dígitos)")
        return normalizado


class ProblemaEmailRegistradoVista(BaseModel):
    """409 de POST /v1/usuarios. Solo documenta el OpenAPI: la respuesta la arma app/core/errores.py."""

    type: Literal["/errores/email-registrado"]
    title: str
    status: Literal[409]
    detail: str | None
    errores: list[dict[str, str]]
    request_id: str | None


class ProblemaPoliticaCambioVista(BaseModel):
    """409 politica-cambio de POST /v1/usuarios (MATU-75). Solo documenta el OpenAPI."""

    type: Literal["/errores/politica-cambio"]
    title: str
    status: Literal[409]
    detail: str | None
    errores: list[dict[str, str]]
    request_id: str | None


class CuentaCreadaRespuesta(BaseModel):
    id: uuid.UUID
    nombre: str
    email: str


class SolicitudSesion(BaseModel):
    """Cuerpo de POST /v1/sesiones.

    Sin largo mínimo ni forma de email: un 422 por esas razones distinguiría casos que el login
    responde siempre con el mismo 401. Sí hay tope, para no hashear cuerpos enormes.
    """

    model_config = ConfigDict(extra="forbid")

    email: Annotated[str, Field(max_length=LARGO_MAXIMO_EMAIL)]
    contrasena: Annotated[str, Field(max_length=LARGO_MAXIMO_CONTRASENA)]


class SesionRespuesta(BaseModel):
    """Respuesta de POST /v1/sesiones y de POST /v1/sesiones/renovar. Nunca lleva el refresh."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    # Segundos de vida del access token
    expira_en: int


_CLASE = Annotated[
    Literal["telefono", "computador", "otro"],
    Field(
        description=(
            "MATU-55 (C7): qué sustantivo usa la pantalla, «teléfono», «computador» o «navegador». Lo deduce el"
            " servidor del sistema del nombre, que salió del agente de usuario al entrar (Android e iPhone son"
            " telefono; Windows, Mac, Linux y ChromeOS, computador; iPad y «Navegador web», otro). El agente no se"
            " guarda"
        )
    ),
]


class DispositivoVista(BaseModel):
    """Un dispositivo propio. Nunca lleva push_token, familia_id, hashes, la IP ni el agente de usuario."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    plataforma: Literal["android", "ios", "web"]
    nombre: Annotated[str, Field(max_length=LARGO_MAXIMO_NOMBRE)]
    clase: _CLASE
    creado_en: datetime
    ultimo_uso_en: datetime | None
    actual: bool
    push_activo: Annotated[
        bool,
        Field(
            description=(
                "MATU-55 (C5): si el dispositivo tiene un endpoint de push guardado («Avisos activados»). Nunca el"
                " endpoint"
            )
        ),
    ]


class ListaDispositivos(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DispositivoVista]


class SolicitudPush(BaseModel):
    """Cuerpo de PUT /v1/dispositivos/actual/push. El valor nunca se repite en un error."""

    model_config = ConfigDict(extra="forbid")

    push_token: Annotated[
        str,
        Field(
            min_length=12,
            max_length=LARGO_MAXIMO_PUSH,
            pattern=r"^https://[^\s]+$",
            json_schema_extra={"format": "uri", "writeOnly": True},
            description=(
                "Endpoint de Web Push del navegador (RFC 8030), solo escritura. https, de hasta 1024"
                " caracteres, con el host en la lista cerrada de servicios de push"
            ),
        ),
    ]

    @field_validator("push_token")
    @classmethod
    def _servicio_admitido(cls, valor: str) -> str:
        if not push_admitido(valor):
            raise PydanticCustomError("push_no_admitido", "el servicio de avisos de este navegador no está admitido")
        return valor


# --- MATU-55: Dónde entraste ------------------------------------------------------------------------


class PushActualVista(BaseModel):
    """GET /v1/dispositivos/actual/push (decisión 261). Nunca lleva el endpoint ni la clave privada."""

    model_config = ConfigDict(extra="forbid")

    clave_publica: Annotated[
        str | None,
        Field(
            pattern=r"^B[A-Za-z0-9_-]{86}$",
            description=(
                "Clave pública VAPID (RFC 8292): el punto P-256 sin comprimir (65 bytes) en base64url sin relleno, 87"
                " caracteres. Es la applicationServerKey de PushManager.subscribe(). null si VAPID_CLAVE_PRIVADA no"
                " está configurada"
            ),
        ),
    ]
    registrado: Annotated[
        bool, Field(description="Si el dispositivo del claim did tiene un endpoint de push guardado")
    ]
    envio_simulado: Annotated[
        bool,
        Field(description="true mientras no exista un adaptador real de push (decisión 112): no se envía nada a nadie"),
    ]


class DispositivoEventoVista(BaseModel):
    """El dispositivo de un evento (C3): nunca el id, la plataforma, el push_token, la IP ni el agente de usuario."""

    model_config = ConfigDict(extra="forbid")

    nombre: Annotated[str, Field(max_length=LARGO_MAXIMO_NOMBRE, examples=["Chrome en Android"])]
    clase: _CLASE
    actual: Annotated[
        bool,
        Field(
            description=(
                "true si es el dispositivo del claim did de esta sesión. Con un access token sin did, siempre false"
            )
        ),
    ]


class EventoCuentaVista(BaseModel):
    """Un evento de la propia cuenta: solo tipo, ocurrido_en y dispositivo (C3 a C5)."""

    model_config = ConfigDict(extra="forbid")

    tipo: Annotated[
        Literal[
            "entraste",
            "saliste",
            "cerraste_en_dispositivo",
            "salida_por_seguridad",
            "contrasena_cambiada",
            "celular_confirmado",
            "codigo_recuperacion_pedido",
            "avisos_cambiados",
            "avisos_activados",
            "avisos_desactivados",
            "pediste_una_copia",
        ],
        Field(
            description=(
                "Qué pasó, de una lista cerrada (decisión 254). No es el nombre de la acción de auditoría. La pantalla"
                " arma el texto con lenguaje.md e ignora un tipo que no conoce. MATU-54 (decisión 376):"
                " pediste_una_copia es la copia de «Tus datos»; la de una persona no entra"
            )
        ),
    ]
    ocurrido_en: Annotated[
        datetime, Field(description="El instante, en UTC. La pantalla lo muestra en America/Santiago")
    ]
    dispositivo: Annotated[
        DispositivoEventoVista | None,
        Field(
            description=(
                "El dispositivo del evento (en cerraste_en_dispositivo, el que se cerró; el de origen no se muestra), o"
                " null: siempre en contrasena_cambiada, celular_confirmado, codigo_recuperacion_pedido y"
                " avisos_cambiados, y en los demás si el dispositivo ya no existe porque la conservación lo borró"
                " (decisión 59)"
            )
        ),
    ]


class UltimosIngresosVista(BaseModel):
    """GET /v1/yo/ingresos (decisiones 253 a 256)."""

    model_config = ConfigDict(extra="forbid")

    eventos: Annotated[list[EventoCuentaVista], Field(max_length=20)]
    hay_mas: Annotated[
        bool,
        Field(
            description=(
                "true si en los últimos 90 días hay más de 20 eventos. No dice cuántos. Lo que no se muestra se pide"
                " por correo (política, §10)"
            )
        ),
    ]


# --- MATU-57: recuperar el acceso y verificar el celular ---------------------------------------------

_CODIGO = Annotated[
    str,
    Field(
        pattern=r"^[0-9]{6}$",
        json_schema_extra={"examples": ["123456"]},
        description="El código de 6 dígitos del mensaje. Nunca se registra ni se repite en un error",
    ),
]


class SolicitudCodigoRecuperacion(BaseModel):
    """Cuerpo de POST /v1/recuperacion/codigo. Solo el email: nunca se pide el celular para recuperar."""

    model_config = ConfigDict(extra="forbid")

    email: Annotated[str, Field(max_length=LARGO_MAXIMO_EMAIL)]
    canal: Annotated[
        Literal["correo"] | None,
        Field(
            description=(
                "Con \"correo\", el código va al correo aunque el celular esté verificado (reenviar al correo)."
                " Sin él, va al celular verificado o, si no hay, al correo. La respuesta nunca dice a cuál"
            )
        ),
    ] = None


class SolicitudCambioContrasena(BaseModel):
    """Cuerpo de POST /v1/recuperacion/contrasena. La contraseña nueva cumple lo mismo que en el alta."""

    model_config = ConfigDict(extra="forbid")

    email: Annotated[str, Field(max_length=LARGO_MAXIMO_EMAIL)]
    codigo: _CODIGO
    contrasena_nueva: Annotated[
        str, Field(min_length=LARGO_MINIMO_CONTRASENA, max_length=LARGO_MAXIMO_CONTRASENA)
    ]


class SolicitudVerificarCelular(BaseModel):
    """Cuerpo de POST /v1/cuenta/celular/verificar."""

    model_config = ConfigDict(extra="forbid")

    codigo: _CODIGO
    canal: Annotated[
        Literal["sms", "whatsapp"],
        Field(description="Canal preferido del celular, elegido al verificarlo (decisión 90). Por omisión sms"),
    ] = "sms"


class PoliticaAceptadaVista(BaseModel):
    """La última política que aceptó la cuenta (MATU-75): «Aceptaste la versión {version} el {DD/MM/AAAA}.»"""

    model_config = ConfigDict(extra="forbid")

    version: Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+$", examples=["0.11"])]
    huella: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$", description="SHA-256 del texto que se mostró")]
    aceptada_en: datetime


class CuentaVista(BaseModel):
    """GET /v1/cuenta: la cuenta propia. El celular va enmascarado, nunca completo."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    nombre: str
    email: str
    celular_enmascarado: Annotated[str | None, Field(examples=["+56 9 •••• ••37"])]
    celular_verificado: bool
    celular_canal: Literal["sms", "whatsapp"]
    politica_aceptada: Annotated[
        PoliticaAceptadaVista | None,
        Field(
            description=(
                "MATU-75: la última política que aceptó al crear la cuenta. null si la cuenta es anterior a MATU-75 y"
                " no tiene registro («No tenemos registro de qué versión aceptaste.»)"
            )
        ),
    ]


class PoliticaVista(BaseModel):
    """GET /v1/politica (MATU-75): la política de privacidad vigente, pública."""

    model_config = ConfigDict(extra="forbid")

    version: Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+$", examples=["0.11"])]
    actualizada_en: Annotated[
        date, Field(description="Fecha de la versión, AAAA-MM-DD. La pantalla la muestra DD/MM/AAAA")
    ]
    huella: Annotated[
        str,
        Field(
            pattern=r"^[0-9a-f]{64}$",
            description=(
                "SHA-256 en hexadecimal de texto, en UTF-8 con saltos LF. Es la que se envía al crear la cuenta"
            ),
        ),
    ]
    texto: Annotated[
        str,
        Field(
            description=(
                "La política en Markdown, desde «En un minuto» hasta el final, ya completa: el correo de contacto ya"
                " viene puesto. Se muestra tal cual, sin HTML crudo; es exactamente lo que entra en la huella"
            )
        ),
    ]
    correo_contacto: Annotated[
        str | None,
        Field(
            examples=["privacidad@example.com"],
            description=(
                "El correo de contacto para temas de privacidad (CORREO_PRIVACIDAD), para un mailto: en «Tu cuenta»."
                " null si no está configurado: la pantalla oculta ese párrafo"
            ),
        ),
    ]
