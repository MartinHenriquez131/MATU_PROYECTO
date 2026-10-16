"""S0-A · Esqueleto de la API.

Criterio de cierre (backlog v1.3, sección 3): app/main.py, configuración, errores RFC 7807
y logs JSON con request_id y sin cuerpos de petición.
"""

import uuid

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
