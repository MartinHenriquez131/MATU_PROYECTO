"""Lo que declaran en el OpenAPI POST /v1/relevo/presentacion y POST /v1/relevo/canje (MATU-106).

Solo documentación: las cabeceras las ponen MiddlewareCabecerasPrefijo (no-store, no-referrer y noindex en
todo /v1/relevo/, app/core/cabeceras.py) y app/core/logs.py (X-Request-ID), y los problemas los arma
app/core/errores.py. Sale de lo que declaraba docs/api/propuestos/relevo.openapi.yaml hasta MATU-106. Los
problemas van con su esquema en línea, como el 412 de la ficha, porque openapi.json no tiene un componente
Problema. Los ejemplos son sintéticos.
"""

from typing import Any

from app.core.cabeceras import CABECERAS_RELEVO
from app.core.errores import TIPO_PROBLEMA
from app.core.limite_ip import DETALLE_429, DETALLE_503

# --- Cabeceras -----------------------------------------------------------------------------------------

_X_REQUEST_ID: dict[str, Any] = {
    "description": "Identificador de la petición (UUID), el mismo request_id de los logs y del problema",
    "required": True,
    "schema": {"type": "string", "format": "uuid"},
}
_CACHE_CONTROL: dict[str, Any] = {
    "description": "Ninguna respuesta del relevo se guarda en una caché, del navegador ni intermedia",
    "required": True,
    "schema": {"type": "string", "const": CABECERAS_RELEVO["Cache-Control"]},
}
_REFERRER_POLICY: dict[str, Any] = {
    "description": "El navegador no envía la URL de la página del relevo como Referer a nadie",
    "required": True,
    "schema": {"type": "string", "const": CABECERAS_RELEVO["Referrer-Policy"]},
}
_X_ROBOTS_TAG: dict[str, Any] = {
    "description": "Ningún buscador indexa las respuestas del relevo",
    "required": True,
    "schema": {"type": "string", "const": CABECERAS_RELEVO["X-Robots-Tag"]},
}
_RETRY_AFTER: dict[str, Any] = {
    "description": "Segundos que faltan para que se abra la ventana del límite por IP, de 1 a 3600",
    "required": True,
    "schema": {"type": "integer", "minimum": 1, "maximum": 3600},
}
_SET_COOKIE: dict[str, Any] = {
    "description": (
        "Cookie de sesión de relevo. Max-Age es el menor entre 43200 (12 horas) y los segundos que le quedan "
        "al acceso"
    ),
    "required": True,
    "schema": {"type": "string"},
    "example": "__Secure-matu-relevo=<id-de-sesión>; Max-Age=43200; Path=/v1/relevo; HttpOnly; Secure; SameSite=Strict",
}

# Toda respuesta bajo /v1/relevo/, también las de error
CABECERAS: dict[str, Any] = {
    "X-Request-ID": _X_REQUEST_ID,
    "Cache-Control": _CACHE_CONTROL,
    "Referrer-Policy": _REFERRER_POLICY,
    "X-Robots-Tag": _X_ROBOTS_TAG,
}

# --- Problemas RFC 7807 --------------------------------------------------------------------------------

_ERROR_CAMPO: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["campo", "mensaje", "tipo"],
    "properties": {"campo": {"type": "string"}, "mensaje": {"type": "string"}, "tipo": {"type": "string"}},
}
_REQUEST_ID_EJEMPLO = "9b2f4c1e-0000-4000-8000-0000000000"


def _problema(tipos: list[str], status: int, extension: dict[str, Any] | None = None) -> dict[str, Any]:
    """El problema que arma app/core/errores.py, con su `type` y su `status` fijos."""
    tipo: dict[str, Any] = {"type": "string", "format": "uri-reference"}
    tipo |= {"const": tipos[0]} if len(tipos) == 1 else {"enum": tipos}
    propiedades: dict[str, Any] = {
        "type": tipo,
        "title": {"type": "string"},
        "status": {"type": "integer", "const": status},
        "detail": {"type": ["string", "null"]},
        "errores": {"type": "array", "items": _ERROR_CAMPO},
        "request_id": {"type": ["string", "null"], "format": "uuid"},
        **(extension or {}),
    }
    return {"type": "object", "required": list(propiedades), "properties": propiedades}


def _respuesta(
    descripcion: str,
    esquema: dict[str, Any],
    ejemplo: dict[str, Any],
    cabeceras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "description": descripcion,
        "headers": {**CABECERAS, **(cabeceras or {})},
        "content": {TIPO_PROBLEMA: {"schema": esquema, "example": ejemplo}},
    }


def _ejemplo(tipo: str, titulo: str, status: int, detalle: str, sufijo: str, **extra: Any) -> dict[str, Any]:
    return {
        "type": tipo, "title": titulo, "status": status, "detail": detalle, "errores": [],
        "request_id": _REQUEST_ID_EJEMPLO + sufijo, **extra,
    }


_NO_DISPONIBLE = _respuesta(
    "El enlace ya no sirve. Cuatro `type`, para que la página muestre el texto de cada estado: relevo-vencido, "
    "relevo-revocado (revocar no borra indice_token, así que un enlace revocado siempre responde este), "
    "relevo-no-disponible (el token no corresponde a ningún acceso: cortado al copiarlo, o ya purgado después de "
    "vencer) y relevo-pausado (la autorización de la persona no está vigente, decisión 33; el `detail` no dice "
    "el motivo). No cuenta como intento",
    _problema(
        [
            "/errores/relevo-vencido",
            "/errores/relevo-revocado",
            "/errores/relevo-no-disponible",
            "/errores/relevo-pausado",
        ],
        410,
    ),
    _ejemplo(
        "/errores/relevo-vencido", "Ya no está disponible", 410,
        "Este enlace venció. Pídele a quien te envió el enlace uno nuevo", "eb",
    ),
)
_BLOQUEADO = _respuesta(
    "El acceso está bloqueado por 5 PIN incorrectos, o este intento fue el 5.º. No se desbloquea: la familia "
    "revoca y crea un acceso nuevo",
    _problema(["/errores/relevo-bloqueado"], 423),
    _ejemplo(
        "/errores/relevo-bloqueado", "Bloqueado", 423,
        "El enlace se bloqueó por PIN incorrecto. Pídele a quien te envió el enlace uno nuevo", "ed",
    ),
)
_VALIDACION = _problema(["/errores/validacion"], 422)
_VALIDACION["properties"]["errores"] |= {"minItems": 1}


def _validacion(descripcion: str, campo: str, mensaje: str, tipo: str, sufijo: str) -> dict[str, Any]:
    ejemplo = _ejemplo("/errores/validacion", "Datos inválidos", 422, "Revisa los campos indicados", sufijo)
    ejemplo["errores"] = [{"campo": campo, "mensaje": mensaje, "tipo": tipo}]
    return _respuesta(descripcion, _VALIDACION, ejemplo)


def _demasiadas(descripcion: str, sufijo: str) -> dict[str, Any]:
    return _respuesta(
        descripcion,
        _problema(["/errores/demasiadas-peticiones"], 429),
        _ejemplo("/errores/demasiadas-peticiones", "Demasiadas peticiones", 429, DETALLE_429, sufijo),
        {"Retry-After": _RETRY_AFTER},
    )


_SIN_SERVICIO = _problema(["/errores/servicio-no-disponible"], 503)

# --- POST /v1/relevo/presentacion ----------------------------------------------------------------------

DESCRIPCION_PRESENTACION = """Ruta pública para la pantalla del PIN (decisión 28). Recibe solo el token, leído del \
fragmento `/r#<token>`, en el cuerpo y nunca en la URL, y responde los dos nombres de pila para que la página diga \
«Carmen te compartió la ficha de María» antes de pedir el PIN. Nada más sale de esta ruta: ni los campos, ni el \
vencimiento, ni el relevo.

Orden de evaluación, el mismo del canje hasta el estado:

1. Límite por IP de MATU-25: 30 presentaciones por hora, en un contador propio, separado del canje (decisión 29), \
en una ventana fija (decisión 114). Si se supera, 429. Sin Redis o sin PEPPER_LIMITES, 503.
2. Cuerpo válido. Si no, 422. Un cuerpo que no es JSON válido responde 422 antes del paso 1 y no cuenta en el \
límite (decisión 114); todo cuerpo JSON válido se cuenta en el paso 1, antes de validar sus campos.
3. El token corresponde a un acceso (indice_token). Si no, 410 relevo-no-disponible.
4. Revocado: 410 relevo-revocado. Vencido: 410 relevo-vencido (decisión 23).
5. Bloqueado (5 PIN incorrectos): 423.
6. Autorización de la persona no vigente: 410 relevo-pausado, sin decir el motivo (decisión 33).
7. Si no, 200 con los dos nombres.

No cuenta como intento de PIN, no crea sesión, no suma usos y no registra relevo.abrir. Cada 200 registra \
relevo.presentar, sin IP (decisión 30), y la familia lo ve en /plan/aperturas como `presentacion`."""

RESPUESTAS_PRESENTACION: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "Los dos nombres de pila del acceso",
        "headers": CABECERAS,
        "content": {
            "application/json": {"example": {"nombre_pila_comparte": "Carmen", "nombre_pila": "María"}},
        },
    },
    410: _NO_DISPONIBLE,
    422: _validacion(
        "Falta el token o el cuerpo trae un campo extra. No revela nada del acceso",
        "token", "Field required", "missing", "f1",
    ),
    423: _BLOQUEADO,
    429: _demasiadas(
        "Se superó el límite de 30 presentaciones por hora desde la misma IP (MATU-25), en un contador propio, "
        "separado del canje (decisión 29), cuya clave es una huella de la IP (decisión 27). El límite es más alto "
        "que el del canje porque muchos celulares en Chile comparten IP pública (CGNAT). No toca el acceso",
        "f2",
    ),
    503: _respuesta(
        "El límite por IP falla cerrado: Redis no responde o falta PEPPER_LIMITES (MATU-25, decisión 114)",
        _SIN_SERVICIO,
        _ejemplo("/errores/servicio-no-disponible", "Servicio no disponible", 503, DETALLE_503, "f3"),
    ),
}

EXTRA_PRESENTACION: dict[str, Any] = {
    "x-matu-historia": "MATU-19, MATU-23, MATU-25",
    "x-matu-auditoria": "relevo.presentar",
    "security": [],
    "requestBody": {
        "content": {
            "application/json": {
                "examples": {
                    "presentacion": {
                        "summary": "La página de Rosa pide los nombres con el token del enlace",
                        "value": {"token": "EjemploSinteticoDeTokenDeRelevoNoValido0000"},
                    }
                }
            }
        }
    },
}

# --- POST /v1/relevo/canje -----------------------------------------------------------------------------

DESCRIPCION_CANJE = """Ruta pública. Recibe el token (leído del fragmento `/r#<token>`) y el PIN en el cuerpo, \
nunca en la URL. Si son correctos responde 204 con la cookie de sesión de relevo, y la página lee la ficha con \
GET /v1/relevo/ficha.

Orden de evaluación:

1. Límite por IP: 10 canjes por hora, en un contador propio, separado de la presentación (MATU-25, decisión 29), \
en una ventana fija (decisión 114). Si se supera, 429, sin tocar el acceso. Sin Redis o sin PEPPER_LIMITES, 503.
2. Cuerpo válido (PIN de 4 dígitos). Si no, 422. No cuenta como intento. Un cuerpo que no es JSON válido responde \
422 antes del paso 1 y no cuenta en el límite (decisión 114).
3. El token corresponde a un acceso (indice_token). Si no, 410 relevo-no-disponible.
4. Revocado: 410 relevo-revocado. Vencido: 410 relevo-vencido (decisión 23). No cuenta como intento.
5. Bloqueado (5 PIN incorrectos): 423, aunque el PIN sea el correcto.
6. Autorización de la persona no vigente: 410 relevo-pausado (decisión 33). No cuenta como intento ni crea sesión.
7. Sin PEPPER_PIN: 503, sin comparar el PIN.
8. PIN incorrecto: suma un intento y registra relevo.pin_incorrecto. Del 1.º al 4.º responde 401 con \
intentos_restantes; el 5.º bloquea el acceso, registra relevo.bloqueo y responde 423.
9. PIN correcto: vuelve el contador a 0, registra relevo.canje, crea la sesión en Redis y responde 204 con \
Set-Cookie. Si Redis no responde, 503: el canje quedó registrado pero sin cookie, y la página vuelve a pedir el PIN.

La sesión dura hasta lo que ocurra primero: 12 horas o el vencimiento del acceso."""

RESPUESTAS_CANJE: dict[int | str, dict[str, Any]] = {
    204: {
        "description": "PIN correcto. La sesión de relevo queda en la cookie. Sin cuerpo",
        "headers": {**CABECERAS, "Set-Cookie": _SET_COOKIE},
    },
    401: _respuesta(
        "PIN incorrecto, del 1.º al 4.º intento. Solo dice cuántos intentos quedan: ni el nombre de la persona, ni "
        "quién compartió, ni cuándo vence. El 5.º intento responde 423",
        _problema(
            ["/errores/pin-incorrecto"],
            401,
            {
                "intentos_restantes": {
                    "type": "integer", "minimum": 1, "maximum": 4,
                    "description": "Intentos que quedan antes del bloqueo",
                }
            },
        ),
        _ejemplo(
            "/errores/pin-incorrecto", "PIN incorrecto", 401, "El PIN no coincide. Te quedan 3 intentos", "ea",
            intentos_restantes=3,
        ),
    ),
    410: _NO_DISPONIBLE,
    422: _validacion(
        "Falta el token o el PIN, o el PIN no son 4 dígitos. No cuenta como intento y no revela nada del acceso",
        "pin", "String should match pattern '^[0-9]{4}$'", "string_pattern_mismatch", "e9",
    ),
    423: _BLOQUEADO,
    429: _demasiadas(
        "Se superó el límite de 10 canjes por hora desde la misma IP (MATU-25), en un contador propio (decisión "
        "29) cuya clave es una huella de la IP (decisión 27). No toca el acceso ni cuenta como intento de PIN",
        "f0",
    ),
    503: _respuesta(
        "Falla cerrado. Antes que todo, el límite por IP sin Redis o sin PEPPER_LIMITES (MATU-25). Después de los "
        "410 y el 423, falta PEPPER_PIN (no cuenta como intento). O Redis no respondió al crear la sesión: el canje "
        "quedó registrado como relevo.canje, pero no hay cookie",
        _SIN_SERVICIO,
        _ejemplo(
            "/errores/servicio-no-disponible", "Servicio no disponible", 503,
            "La ficha no está disponible en este momento. Cita el request_id si lo reportas", "f4",
        ),
    ),
}

EXTRA_CANJE: dict[str, Any] = {
    "x-matu-historia": "MATU-19, MATU-25",
    "x-matu-auditoria": "relevo.canje, relevo.pin_incorrecto, relevo.bloqueo",
    "security": [],
    "requestBody": {
        "content": {
            "application/json": {
                "examples": {
                    "canje": {
                        "summary": "Rosa escribe el PIN que le dictó Carmen",
                        "value": {"token": "EjemploSinteticoDeTokenDeRelevoNoValido0000", "pin": "4821"},
                    }
                }
            }
        }
    },
}
