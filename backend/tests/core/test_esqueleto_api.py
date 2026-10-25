"""S0-A · Esqueleto de la API.

Criterio de cierre (backlog v1.3, sección 3): app/main.py, configuración, errores RFC 7807
y logs JSON con request_id y sin cuerpos de petición.
"""

import io
import json
import logging
import uuid

from app.core.logs import FormateadorJSON
from tests.core.conftest import Entorno

PROBLEMA = "application/problem+json"


# --- Arranque ------------------------------------------------------------------------------


def test_salud_responde_200(entorno: Entorno) -> None:
    respuesta = entorno.cliente.get("/v1/salud")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}


# --- request_id ----------------------------------------------------------------------------


def test_cada_respuesta_lleva_request_id(entorno: Entorno) -> None:
    respuesta = entorno.cliente.get("/v1/salud")

    uuid.UUID(respuesta.headers["X-Request-ID"])


def test_request_id_entrante_valido_se_respeta(entorno: Entorno) -> None:
    propio = str(uuid.uuid4())

    respuesta = entorno.cliente.get("/v1/salud", headers={"X-Request-ID": propio})

    assert respuesta.headers["X-Request-ID"] == propio


def test_request_id_entrante_que_no_es_uuid_se_reemplaza(entorno: Entorno) -> None:
    respuesta = entorno.cliente.get("/v1/salud", headers={"X-Request-ID": "texto inyectado"})

    assert respuesta.headers["X-Request-ID"] != "texto inyectado"
    uuid.UUID(respuesta.headers["X-Request-ID"])


# --- Errores RFC 7807 ----------------------------------------------------------------------


def test_error_de_negocio_responde_problem_json(entorno: Entorno) -> None:
    respuesta = entorno.cliente.get("/prueba/conflicto")

    assert respuesta.status_code == 409
    assert respuesta.headers["content-type"].startswith(PROBLEMA)
    cuerpo = respuesta.json()
    assert cuerpo["type"] == "/errores/email-registrado"
    assert cuerpo["title"] == "Conflicto"
    assert cuerpo["status"] == 409
    assert cuerpo["detail"] == "Ese email ya tiene una cuenta"
    assert cuerpo["errores"] == []
    assert cuerpo["request_id"] == respuesta.headers["X-Request-ID"]


def test_ruta_inexistente_responde_404_problem_json(entorno: Entorno) -> None:
    respuesta = entorno.cliente.get("/v1/no-existe")

    assert respuesta.status_code == 404
    assert respuesta.headers["content-type"].startswith(PROBLEMA)
    assert respuesta.json()["type"] == "/errores/no-encontrado"


def test_validacion_responde_422_con_campos_y_sin_valores(entorno: Entorno, secreto: str) -> None:
    # Dado un cuerpo cuya edad inválida es un valor sensible
    cuerpo = {"nombre": "Ana", "edad": secreto}

    # Cuando se envía
    respuesta = entorno.cliente.post("/prueba/eco", json=cuerpo)

    # Entonces el 422 dice qué campo falló, pero no repite el valor recibido
    assert respuesta.status_code == 422
    assert respuesta.headers["content-type"].startswith(PROBLEMA)
    assert [e["campo"] for e in respuesta.json()["errores"]] == ["edad"]
    assert secreto not in respuesta.text


def test_error_inesperado_responde_500_sin_el_mensaje(entorno: Entorno, secreto: str) -> None:
    respuesta = entorno.cliente.post("/prueba/falla", json={"valor": secreto})

    assert respuesta.status_code == 500
    assert respuesta.headers["content-type"].startswith(PROBLEMA)
    assert respuesta.json()["type"] == "/errores/error-interno"
    assert secreto not in respuesta.text
    uuid.UUID(respuesta.json()["request_id"])


# --- Logs ----------------------------------------------------------------------------------


def test_cada_linea_de_log_es_json_con_request_id(entorno: Entorno) -> None:
    respuesta = entorno.cliente.get("/v1/salud")

    lineas = entorno.lineas_log()
    peticion = [linea for linea in lineas if linea["mensaje"] == "peticion"]
    assert len(peticion) == 1
    assert peticion[0]["request_id"] == respuesta.headers["X-Request-ID"]
    assert peticion[0]["metodo"] == "GET"
    assert peticion[0]["ruta"] == "/v1/salud"
    assert peticion[0]["estado"] == 200


def test_log_no_contiene_cuerpo_ni_query_string(entorno: Entorno, secreto: str) -> None:
    # Dado un secreto en el cuerpo y otro en el query string
    entorno.cliente.post(f"/prueba/eco?token={secreto}", json={"nombre": secreto, "edad": 70})

    # Entonces ninguno llega al log
    assert entorno.lineas_log()
    assert secreto not in entorno.texto_log()


def test_log_de_validacion_fallida_no_contiene_el_valor(entorno: Entorno, secreto: str) -> None:
    entorno.cliente.post("/prueba/eco", json={"nombre": "Ana", "edad": secreto})

    assert secreto not in entorno.texto_log()


def test_error_inesperado_se_registra_con_tipo_y_sin_mensaje(entorno: Entorno, secreto: str) -> None:
    # Dado un error cuyo mensaje trae un valor de la fila
    respuesta = entorno.cliente.post("/prueba/falla", json={"valor": secreto})

    # Entonces el log tiene el tipo de error y el request_id, pero no el valor
    errores = [linea for linea in entorno.lineas_log() if linea["mensaje"] == "error no controlado"]
    assert len(errores) == 1
    assert errores[0]["tipo_error"] == "RuntimeError"
    assert errores[0]["request_id"] == respuesta.json()["request_id"]
    assert "traza" in errores[0]
    assert secreto not in entorno.texto_log()


def _linea_peticion(entorno: Entorno) -> dict[str, object]:
    lineas = [linea for linea in entorno.lineas_log() if linea["mensaje"] == "peticion"]
    assert len(lineas) == 1
    return lineas[0]


def test_log_registra_la_plantilla_de_la_ruta_y_no_el_path(entorno: Entorno, secreto: str) -> None:
    # Dado un valor sensible en un parámetro de la ruta
    entorno.cliente.get(f"/prueba/item/{secreto}")

    # Entonces el log registra la plantilla, no el valor
    assert _linea_peticion(entorno)["ruta"] == "/prueba/item/{item_id}"
    assert secreto not in entorno.texto_log()


def test_log_de_ruta_con_prefijo_registra_la_plantilla_completa(entorno: Entorno) -> None:
    entorno.cliente.get("/v1/salud")

    assert _linea_peticion(entorno)["ruta"] == "/v1/salud"


def test_log_de_ruta_con_prefijo_y_parametro_registra_la_plantilla(entorno: Entorno, secreto: str) -> None:
    entorno.cliente.get(f"/prueba-v1/grupos/{secreto}/cosas")

    assert _linea_peticion(entorno)["ruta"] == "/prueba-v1/grupos/{grupo_id}/cosas"
    assert secreto not in entorno.texto_log()


def test_log_de_ruta_inexistente_no_registra_el_path(entorno: Entorno, secreto: str) -> None:
    respuesta = entorno.cliente.get(f"/v1/no-existe/{secreto}")

    assert respuesta.status_code == 404
    assert _linea_peticion(entorno)["ruta"] == "sin-ruta"
    assert secreto not in entorno.texto_log()


def test_log_sin_usuario_ni_grupo_no_los_inventa(entorno: Entorno) -> None:
    entorno.cliente.get("/v1/salud")

    linea = _linea_peticion(entorno)
    assert "usuario_id" not in linea
    assert "grupo_id" not in linea


def _formatear(nombre_logger: str, mensaje: str, *args: object) -> dict[str, object]:
    salida = io.StringIO()
    manejador = logging.StreamHandler(salida)
    manejador.setFormatter(FormateadorJSON())
    logger = logging.getLogger(nombre_logger)
    logger.addHandler(manejador)
    try:
        logger.warning(mensaje, *args)
    finally:
        logger.removeHandler(manejador)
    datos: dict[str, object] = json.loads(salida.getvalue())
    return datos


def test_log_de_tercero_no_deja_el_query_string_de_una_url(secreto: str) -> None:
    # Dado un WARNING de urllib3 con una URL absoluta y una línea de petición con path y query
    url = f"https://pasarela.ejemplo.cl/api/v1/estado?token={secreto}&otro=1"  # pragma: allowlist secret
    datos = _formatear("urllib3.connectionpool", "Retrying after connection broken: %s", url)
    linea = _formatear(
        "urllib3.connectionpool", 'https://pasarela.ejemplo.cl:443 "GET /api/v1/estado?token=%s HTTP/1.1" 200', secreto
    )

    # Entonces se conserva la URL sin su query string
    assert datos["mensaje"] == "Retrying after connection broken: https://pasarela.ejemplo.cl/api/v1/estado"
    assert linea["mensaje"] == 'https://pasarela.ejemplo.cl:443 "GET /api/v1/estado HTTP/1.1" 200'
    assert secreto not in json.dumps([datos, linea])


def test_log_de_tercero_no_deja_el_fragmento_de_una_url(secreto: str) -> None:
    datos = _formatear("httpx", "GET %s", f"https://matu.ejemplo.cl/r#{secreto}")

    assert datos["mensaje"] == "GET https://matu.ejemplo.cl/r"


def test_log_de_matu_no_se_altera() -> None:
    datos = _formatear("matu.prueba", "consulta /v1/grupos?pagina=2")

    assert datos["mensaje"] == "consulta /v1/grupos?pagina=2"
