"""MATU-42 · docs/api/openapi.json coincide con la API en las invitaciones y los miembros, y el propuesto quedó marcado
como implementado (docs/api/README.md, decisiones 290 a 317 y 318 en adelante). Sin base (RF-38)."""

import io
import json
import re
from pathlib import Path
from typing import Any

import pytest

from app.main import crear_app

pytestmark = pytest.mark.rf("RF-38")

DOCS = Path(__file__).resolve().parents[4] / "docs" / "api"
OPERACIONES = {
    ("/v1/grupos/{grupo_id}/invitaciones", "post"): ("crearInvitacion", {"201", "401", "404", "422", "429", "503"}),
    ("/v1/grupos/{grupo_id}/invitaciones", "get"): ("listarInvitaciones", {"200", "401", "404"}),
    ("/v1/grupos/{grupo_id}/invitaciones/{invitacion_id}", "delete"): (
        "anularInvitacion", {"204", "401", "404", "409"}),
    ("/v1/invitaciones/presentacion", "post"): ("presentarInvitacion", {"200", "410", "422", "423", "429", "503"}),
    ("/v1/invitaciones/verificacion", "post"): (
        "verificarCodigoInvitacion", {"200", "410", "422", "423", "429", "503"}),
    ("/v1/invitaciones/aceptacion", "post"): (
        "aceptarInvitacion", {"201", "401", "409", "410", "422", "423", "429", "503"}),
    ("/v1/grupos/{grupo_id}/miembros", "get"): ("listarMiembros", {"200", "401", "404"}),
    ("/v1/grupos/{grupo_id}/miembros/{membresia_id}", "patch"): (
        "cambiarMiembro", {"200", "401", "404", "409", "412", "422", "428"}),
    ("/v1/grupos/{grupo_id}/miembros/{membresia_id}", "delete"): ("sacarMiembro", {"200", "401", "404", "409"}),
    ("/v1/grupos/{grupo_id}/salida", "post"): ("salirDelGrupo", {"200", "401", "404", "409"}),
}
COMPONENTES = ("SolicitudInvitacion", "InvitacionCreada", "InvitadaPor", "InvitacionVista", "ListaInvitaciones",
               "SolicitudPresentacionInvitacion", "PresentacionInvitacion", "SolicitudCanjeInvitacion",
               "VerificacionInvitacion", "Union", "MiembroVista", "ListaMiembros", "SolicitudCambioMiembro",
               "ResultadoCambioMiembro", "ResultadoSalida", "AutorVista", "AutorAccesoVista", "AutorPerfilVista",
               "AutorizacionVista")
# Lo que nunca sale de un miembro ni de una invitación (C9, C24)
PROHIBIDOS = {"email", "celular", "telefono", "usuario_id", "token", "token_hash", "codigo_hash", "intentos",
              "codigo_intentos_fallidos", "destino_email", "destino_telefono", "ip"}


@pytest.fixture(scope="module")
def esquema() -> dict[str, Any]:
    return crear_app(io.StringIO()).openapi()


def test_openapi_json_coincide_con_la_api(esquema: dict[str, Any]) -> None:
    exportado = json.loads((DOCS / "openapi.json").read_text(encoding="utf-8"))
    for ruta in {r for r, _ in OPERACIONES}:
        assert exportado["paths"][ruta] == esquema["paths"][ruta], f"vuelve a exportar {ruta}"
    for nombre in COMPONENTES:
        assert exportado["components"]["schemas"][nombre] == esquema["components"]["schemas"][nombre], nombre


def test_operaciones_y_codigos_del_contrato_sin_403(esquema: dict[str, Any]) -> None:
    for (ruta, metodo), (operacion, codigos) in OPERACIONES.items():
        declarada = esquema["paths"][ruta][metodo]
        assert declarada["operationId"] == operacion
        assert codigos <= set(declarada["responses"]), (operacion, set(declarada["responses"]))
        assert "403" not in declarada["responses"], operacion


def test_ningun_esquema_trae_contacto_ni_secretos(esquema: dict[str, Any]) -> None:
    esquemas = esquema["components"]["schemas"]
    for nombre in COMPONENTES[:15]:
        assert esquemas[nombre]["additionalProperties"] is False, nombre
        # Las solicitudes traen el token del enlace; las respuestas, nunca
        if not nombre.startswith("Solicitud"):
            assert not set(esquemas[nombre]["properties"]) & PROHIBIDOS, nombre
    assert set(esquemas["MiembroVista"]["properties"]) == {
        "id", "nombre", "rol", "puede_ver_plan", "unido_en", "eres_tu", "etag", "enlaces_vigentes"}
    assert set(esquemas["SolicitudInvitacion"]["properties"]) == {"rol"}
    # Decisión 325: sin intentos_restantes en la verificación correcta
    assert "intentos_restantes" not in esquemas["VerificacionInvitacion"]["properties"]


def test_el_autor_que_ya_no_esta(esquema: dict[str, Any]) -> None:
    for nombre in ("AutorVista", "AutorAccesoVista", "AutorPerfilVista"):
        autor = esquema["components"]["schemas"][nombre]
        assert set(autor["required"]) == {"id", "nombre", "autor_activo"}, nombre
        assert {"type": "null"} in autor["properties"]["nombre"]["anyOf"], nombre


def test_el_propuesto_queda_como_implementado() -> None:
    texto = (DOCS / "propuestos" / "invitar-familiar.openapi.yaml").read_text(encoding="utf-8")
    assert "version: 0.3.0-implementado" in texto
    assert "**Implementado en MATU-42 (12-11): manda `docs/api/openapi.json`.**" in texto
    readme = (DOCS / "README.md").read_text(encoding="utf-8")
    assert "### Preguntas abiertas (MATU-42)" not in readme
    for numero in range(290, 332):
        assert re.search(rf"\n{numero}\. \*\*", readme), numero
