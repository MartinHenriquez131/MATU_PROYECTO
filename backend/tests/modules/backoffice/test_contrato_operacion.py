"""MATU-81 · C5, C6, C18 y D-81-8 sobre el OpenAPI: ninguna respuesta de /v1/operacion trae datos de la persona
cuidada, del grupo ni de la cuenta de la familia, ni de la tarjeta o la sesión de Transbank. Recorre cada esquema de
respuesta con sus referencias, como test_contrato_comercio.py. Además: las vistas nuevas no admiten campos de más
(extra="forbid"), la referencia y el buy_order nunca van en la URL, y el contrato de la entrada en dos pasos.
Sin base."""

import io
from collections.abc import Iterator
from typing import Any

import pytest

pytestmark = [pytest.mark.rf("RF-40"), pytest.mark.rf("Ley-21.719")]

# C5, C6 y C18: lo que una respuesta de operación nunca trae
NUNCA_A_OPERACION = {
    "persona_cuidada_id", "persona_id", "persona", "nombre_pila", "nivel_apoyo", "grupo_id", "grupo",
    "nombre_grupo", "direccion", "calle", "numero", "comuna", "telefono", "telefono_contacto", "usuario_id",
    "creado_por", "solicitado_por", "resuelto_por", "pagado_por", "email", "correo", "correo_solicitante",
    "actor_ref", "token", "session_id", "payload_respuesta", "ultimos4", "tipo_tarjeta", "cuotas",
    "codigo_autorizacion", "codigo_hash", "asignada_a", "creada_por", "mfa_secreto_cifrado",
}


@pytest.fixture(scope="module")
def esquema() -> Iterator[dict[str, Any]]:
    from app.core import config
    from app.main import crear_app

    with pytest.MonkeyPatch.context() as parche:
        parche.setenv("CAPA3_HABILITADA", "true")
        config.obtener_configuracion.cache_clear()
        try:
            yield crear_app(io.StringIO()).openapi()
        finally:
            config.obtener_configuracion.cache_clear()


def _propiedades(esquema: dict[str, Any], nodo: Any, vistos: set[str]) -> set[str]:
    encontradas: set[str] = set()
    if isinstance(nodo, dict):
        referencia = nodo.get("$ref")
        if isinstance(referencia, str):
            nombre = referencia.rsplit("/", 1)[-1]
            if nombre in vistos:
                return encontradas
            vistos.add(nombre)
            return _propiedades(esquema, esquema["components"]["schemas"][nombre], vistos)
        encontradas |= set(nodo.get("properties", {}))
        for valor in nodo.values():
            encontradas |= _propiedades(esquema, valor, vistos)
    elif isinstance(nodo, list):
        for valor in nodo:
            encontradas |= _propiedades(esquema, valor, vistos)
    return encontradas


def _respuestas_de_operacion(esquema: dict[str, Any]) -> Iterator[tuple[str, str, dict[str, Any]]]:
    for ruta, operaciones in esquema["paths"].items():
        if ruta.startswith("/v1/operacion"):
            for metodo, operacion in operaciones.items():
                yield ruta, metodo, operacion


def test_ninguna_respuesta_de_operacion_trae_datos_de_la_familia_ni_de_la_tarjeta(esquema: dict[str, Any]) -> None:
    rutas = list(_respuestas_de_operacion(esquema))
    assert len(rutas) >= 20
    for ruta, metodo, operacion in rutas:
        for codigo, respuesta in operacion["responses"].items():
            if not codigo.startswith("2"):
                continue
            campos = _propiedades(esquema, respuesta.get("content", {}), set())
            assert not campos & NUNCA_A_OPERACION, (ruta, metodo, campos & NUNCA_A_OPERACION)


def test_las_vistas_de_la_consola_no_admiten_campos_de_mas() -> None:
    from app.modules.backoffice.api import esquemas_consola

    modelos = [m for m in vars(esquemas_consola).values()
               if isinstance(m, type) and issubclass(m, esquemas_consola._Vista) and m is not esquemas_consola._Vista]
    assert len(modelos) >= 20
    assert all(m.model_config.get("extra") == "forbid" for m in modelos)


def test_la_referencia_y_el_buy_order_nunca_van_en_la_url(esquema: dict[str, Any]) -> None:
    for ruta, _, operacion in _respuestas_de_operacion(esquema):
        nombres = {p["name"] for p in operacion.get("parameters", [])}
        assert not nombres & {"referencia", "buy_order", "ref", "codigo", "correo"}, ruta
    buscar = esquema["paths"]["/v1/operacion/pedidos/buscar"]
    assert set(buscar) == {"post"}


def test_el_detalle_trae_las_acciones_con_el_monto_que_calcula_el_servidor(esquema: dict[str, Any]) -> None:
    accion = esquema["components"]["schemas"]["AccionDisponible"]
    assert set(accion["properties"]) == {"accion", "monto_a_devolver"}
    assert set(accion["properties"]["accion"]["enum"]) == {"en_camino", "entregado", "no_entregado",
                                                            "cancelar_con_devolucion"}


@pytest.mark.rf("RF-37")
def test_la_entrada_en_dos_pasos_esta_en_el_contrato(esquema: dict[str, Any]) -> None:
    sesiones = esquema["paths"]["/v1/sesiones"]["post"]["responses"]["401"]
    propiedades = sesiones["content"]["application/problem+json"]["schema"]["properties"]
    assert {"desafio", "desafio_expira_en"} <= set(propiedades)
    mfa = esquema["paths"]["/v1/sesiones/mfa"]["post"]
    assert {"200", "401", "422", "429", "503"} <= set(mfa["responses"])
    cuerpo = mfa["requestBody"]["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[-1]
    assert set(esquema["components"]["schemas"][cuerpo]["properties"]) == {"desafio", "codigo"}
    assert not mfa.get("parameters")
