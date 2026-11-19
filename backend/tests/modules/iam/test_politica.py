"""MATU-75 · La política de privacidad visible: el texto, su huella, la tabla de versiones y GET /v1/politica.

Sin base de datos. Las pruebas de la aceptación al crear la cuenta están en test_politica_api.py.
"""

import hashlib
import importlib.util
import io
import json
import re
import sys
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient

from app.core import config
from app.main import crear_app
from app.modules.iam.api.router_politica import obtener_politica_vigente
from app.modules.iam.application.politica import politica_vigente
from app.modules.iam.domain.politica import (
    PoliticaCambio,
    PoliticaNoDisponible,
    aceptar,
    armar_politica,
)
from app.modules.iam.infrastructure import textos_politica
from app.modules.iam.infrastructure.textos_politica import PUBLICADAS, archivo_de, texto_publicado
from tests.politica import CORREO_PRUEBAS, ENTORNO_POLITICA, FECHA_PRUEBAS, POLITICA_PRUEBAS

pytestmark = pytest.mark.rf("RF-37")

BACKEND = Path(__file__).resolve().parents[3]
DOCS = BACKEND.parent / "docs" / "api"
AHORA = datetime(2026, 11, 9, 12, tzinfo=UTC)

# Lo que nunca debe llegar a la persona: el encabezado interno y las referencias del equipo
ENCABEZADO_INTERNO = (
    "# Política de privacidad de MATU",
    "**Estado:**",
    "**Aprobación:**",
    "Identificador de versión en el sistema",
    "POLITICA_VERSION",
)
_HUELLA_64 = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])")


def _generador() -> ModuleType:
    ruta = BACKEND / "scripts" / "generar_politica.py"
    especificacion = importlib.util.spec_from_file_location("generar_politica", ruta)
    assert especificacion is not None and especificacion.loader is not None
    modulo = importlib.util.module_from_spec(especificacion)
    sys.modules["generar_politica"] = modulo
    especificacion.loader.exec_module(modulo)
    return modulo


# --- La tabla de versiones: el archivo no cambia sin una versión nueva ------------------------------------------


@pytest.mark.parametrize("version", sorted(PUBLICADAS))
def test_cada_version_publicada_tiene_su_archivo_con_su_huella(version: str) -> None:
    """Si el texto de una versión cambia, esta prueba falla: un texto nuevo es una versión nueva (POLITICA_VERSION,
    otro archivo y otra fila en PUBLICADAS). Nunca se corrige cambiando la huella de una versión ya servida."""
    contenido = archivo_de(version).read_bytes()
    assert b"\r" not in contenido, "el archivo va con saltos LF"
    assert hashlib.sha256(contenido).hexdigest() == PUBLICADAS[version]


def test_la_carpeta_no_tiene_textos_sin_version_publicada() -> None:
    archivos = {p.name for p in textos_politica.CARPETA.glob("politica-*.md")}
    assert archivos == {f"politica-{v}.md" for v in PUBLICADAS}


def test_la_011_es_la_vigente_de_las_publicadas() -> None:
    # D1: POLITICA_VERSION pasa a 0.11
    assert "0.11" in PUBLICADAS


def test_un_texto_que_cambia_sin_cambiar_su_huella_no_se_sirve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = archivo_de("0.11").read_text(encoding="utf-8")
    (tmp_path / "politica-0.11.md").write_text(original.replace("piloto académico", "piloto"), encoding="utf-8")
    monkeypatch.setattr(textos_politica, "CARPETA", tmp_path)
    texto_publicado.cache_clear()
    try:
        with pytest.raises(PoliticaNoDisponible):
            texto_publicado("0.11")
    finally:
        texto_publicado.cache_clear()


def test_una_version_sin_texto_publicado_no_se_sirve() -> None:
    with pytest.raises(PoliticaNoDisponible):
        texto_publicado("0.10")


# --- El texto que se muestra ----------------------------------------------------------------------------------


def test_el_texto_empieza_en_en_un_minuto_y_no_trae_nada_interno() -> None:
    texto = POLITICA_PRUEBAS.texto
    assert texto.startswith("## En un minuto\n")
    for prohibido in ("ADR-", "MATU-", "[PENDIENTE", *ENCABEZADO_INTERNO):
        assert prohibido not in texto, prohibido


def test_el_texto_no_tiene_marcadores_ni_comentarios() -> None:
    texto = POLITICA_PRUEBAS.texto
    for marcador in ("{", "}", "[PROVEEDOR", "[PAÍS]", "<!--", "-->"):
        assert marcador not in texto, marcador
    assert re.search(r"\[[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ :]*\]", texto) is None


def test_el_texto_no_muestra_identificadores_internos_ni_huellas() -> None:
    texto = POLITICA_PRUEBAS.texto
    assert "declaracion_" not in texto
    assert "aviso_cuidador_de_hecho" not in texto
    assert "`" not in texto
    assert _HUELLA_64.search(texto) is None


def test_el_correo_de_la_configuracion_es_el_del_texto() -> None:
    """La prueba de coincidencia, con el valor real: CORREO_PRIVACIDAD de .env.example (el que se despliega) aparece
    en el texto de la política. Así «Tu cuenta» (correo_contacto) y la política no se desalinean."""
    correo = dotenv_values(BACKEND.parent / ".env.example")["CORREO_PRIVACIDAD"]
    assert correo == "cuidaconmatu@gmail.com"
    texto = texto_publicado("0.11")
    assert correo in texto
    # Ningún otro correo en el texto
    assert set(re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", texto)) == {correo}


def test_la_huella_es_el_sha256_del_texto_que_se_sirve() -> None:
    assert POLITICA_PRUEBAS.huella == hashlib.sha256(POLITICA_PRUEBAS.texto.encode("utf-8")).hexdigest()
    assert POLITICA_PRUEBAS.huella == PUBLICADAS["0.11"]
    assert "\r" not in POLITICA_PRUEBAS.texto


def test_la_huella_no_depende_de_la_configuracion() -> None:
    """El texto se sirve tal cual: otro correo en la configuración no cambia el texto ni la huella."""
    otra = politica_vigente(
        version="0.11", actualizada_en=FECHA_PRUEBAS, correo="otra@example.org", texto_de=texto_publicado
    )
    assert (otra.texto, otra.huella) == (POLITICA_PRUEBAS.texto, POLITICA_PRUEBAS.huella)
    assert otra.correo_contacto == "otra@example.org"


# --- Dominio y caso de uso -----------------------------------------------------------------------------------


def test_armar_sirve_el_texto_tal_cual_con_su_huella() -> None:
    politica = armar_politica(
        version="9.9", actualizada_en=date(2026, 1, 2), texto="Hola\r\nescribe a a@example.org.\n",
        correo="a@example.org",
    )
    assert politica.texto == "Hola\nescribe a a@example.org.\n"
    assert politica.huella == hashlib.sha256(b"Hola\nescribe a a@example.org.\n").hexdigest()
    assert politica.correo_contacto == "a@example.org"
    assert politica.texto not in repr(politica)


@pytest.mark.parametrize(
    "texto",
    [
        "escribe a {correo_privacidad}.",
        "**[PROVEEDOR DEL CORREO]**, en Chile.",
        "Gmail, en [PAÍS].",
        "un {marcador_desconocido}",
    ],
)
def test_un_texto_con_marcadores_no_se_publica(texto: str) -> None:
    with pytest.raises(PoliticaNoDisponible):
        armar_politica(version="9.9", actualizada_en=date(2026, 1, 2), texto=texto, correo="a@example.org")


def test_sin_correo_se_publica_con_correo_contacto_null() -> None:
    politica = armar_politica(version="9.9", actualizada_en=date(2026, 1, 2), texto="completo\n", correo=None)
    assert politica.correo_contacto is None and politica.texto == "completo\n"


@pytest.mark.parametrize(
    ("version", "fecha"), [(None, FECHA_PRUEBAS), ("0.11", None)], ids=["sin-version", "sin-fecha"]
)
def test_sin_version_o_fecha_no_hay_politica(version: str | None, fecha: date | None) -> None:
    with pytest.raises(PoliticaNoDisponible):
        politica_vigente(version=version, actualizada_en=fecha, correo=CORREO_PRUEBAS, texto_de=texto_publicado)


def test_aceptar_estampa_la_version_y_la_huella_vigentes() -> None:
    aceptacion = aceptar(POLITICA_PRUEBAS, POLITICA_PRUEBAS.huella, AHORA)
    assert (aceptacion.version, aceptacion.huella, aceptacion.aceptada_en) == ("0.11", POLITICA_PRUEBAS.huella, AHORA)


def test_aceptar_con_otra_huella_falla() -> None:
    with pytest.raises(PoliticaCambio):
        aceptar(POLITICA_PRUEBAS, "0" * 64, AHORA)


# --- El generador ---------------------------------------------------------------------------------------------

FUENTE_SINTETICA = """# Política de privacidad de MATU

**Versión 9.9 · 1 de enero de 2026** · nota interna (MATU-99)
**Estado:** borrador.
**Identificador de versión en el sistema:** `9.9`

---

## En un minuto

- Algo para la persona (MATU-41).
- Otra cosa (aprobado por Jorge el 28-10, MATU-14).

## 2. Contacto

> ADR-027 (27-10), aprobado por Jorge.

<!-- Nota interna: declaracion_titular, MATU-75 y
[PENDIENTE: algo] en varias líneas -->
- **Contacto:** [PENDIENTE: correo de contacto]
- **Plazo:** [PENDIENTE: plazo legal]
- **[PROVEEDOR DEL CORREO]**, en [PAÍS], guarda lo que escribes a {correo_privacidad}. <!-- ADR-099 --> Nada más.

Este es el texto exacto. Su identificador en el sistema es `aviso_x`, versión 1.1:

Su huella en el sistema (SHA-256) es `8dfbca33f5c58a2c1f5c43a672b3e0fcd2ed4adcc971dcccd0f8879814b10489`.

Cada declaración tiene un identificador: `declaracion_titular`. Su versión es la de esta política. \
Las aprobó Jorge el 03-11.
"""

ESPERADO = """## En un minuto

- Algo para la persona.
- Otra cosa.

## 2. Contacto

- **Contacto:** {correo_privacidad}
- **Plazo:** Todavía no lo definimos.
- **[PROVEEDOR DEL CORREO]**, en [PAÍS], guarda lo que escribes a {correo_privacidad}. Nada más.

Este es el texto exacto.

Su versión es la de esta política.
"""


def test_un_texto_generado_con_marcadores_no_se_publica() -> None:
    """Si la fuente todavía trae el correo, el proveedor o el país sin completar, el archivo se genera, pero la API
    no lo publica: nunca se acepta un texto con marcadores."""
    texto = _generador().convertir(FUENTE_SINTETICA)
    with pytest.raises(PoliticaNoDisponible):
        armar_politica(version="9.9", actualizada_en=date(2026, 1, 2), texto=texto, correo=CORREO_PRUEBAS)


def test_el_generador_convierte_la_fuente_siempre_igual() -> None:
    generador = _generador()
    assert generador.convertir(FUENTE_SINTETICA) == ESPERADO
    assert generador.convertir(FUENTE_SINTETICA.replace("\n", "\r\n")) == ESPERADO


def test_el_generador_falla_si_queda_algo_interno() -> None:
    generador = _generador()
    with pytest.raises(ValueError, match="referencias internas"):
        generador.convertir("## En un minuto\n\nVer MATU-12 sin paréntesis.\n")
    with pytest.raises(ValueError, match="referencias internas"):
        generador.convertir("## En un minuto\n\nEl [RESPONSABLE] responde.\n")
    with pytest.raises(ValueError, match="la sección"):
        generador.convertir("# Sin la sección\n")


def test_el_generador_avisa_las_frases_rotas() -> None:
    generador = _generador()
    texto = generador.convertir("## En un minuto\n\nRespondemos dentro de [PENDIENTE: plazo]. Es gratis.\n")
    assert generador.frases_rotas(texto) == ["Respondemos dentro de Todavía no lo definimos. Es gratis."]


def test_el_generador_escribe_el_archivo_y_su_huella(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    generador = _generador()
    fuente = tmp_path / "politica-privacidad.md"
    fuente.write_text(FUENTE_SINTETICA, encoding="utf-8")
    monkeypatch.setattr(generador, "CARPETA", tmp_path)

    assert generador.main([str(fuente), "9.9"]) == 0

    escrito = (tmp_path / "politica-9.9.md").read_bytes()
    assert escrito == ESPERADO.encode("utf-8")
    assert hashlib.sha256(escrito).hexdigest() in capsys.readouterr().out
    assert generador.main([str(fuente), "nueve"]) == 2


# --- GET /v1/politica -----------------------------------------------------------------------------------------


@pytest.fixture
def cliente() -> Iterator[tuple[TestClient, io.StringIO]]:
    salida = io.StringIO()
    app = crear_app(stream_logs=salida)
    app.dependency_overrides[obtener_politica_vigente] = lambda: POLITICA_PRUEBAS
    with TestClient(app, raise_server_exceptions=False) as cliente:
        yield cliente, salida


def test_get_politica_sin_sesion_trae_version_fecha_huella_texto_y_correo(
    cliente: tuple[TestClient, io.StringIO],
) -> None:
    http, salida = cliente
    respuesta = http.get("/v1/politica")

    assert respuesta.status_code == 200
    assert respuesta.headers["cache-control"] == "no-cache"
    assert "set-cookie" not in respuesta.headers
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"version", "actualizada_en", "huella", "texto", "correo_contacto"}
    assert cuerpo["version"] == "0.11"
    assert cuerpo["actualizada_en"] == "2026-11-09"
    assert cuerpo["correo_contacto"] == CORREO_PRUEBAS
    assert cuerpo["huella"] == hashlib.sha256(cuerpo["texto"].encode("utf-8")).hexdigest()
    for prohibido in ("ADR-", "MATU-", "[PENDIENTE", "declaracion_", *ENCABEZADO_INTERNO):
        assert prohibido not in cuerpo["texto"], prohibido
    # El texto nunca va a un log
    assert "En un minuto" not in salida.getvalue()


def test_get_politica_no_registra_auditoria(cliente: tuple[TestClient, io.StringIO]) -> None:
    http, salida = cliente
    http.get("/v1/politica")
    lineas = [json.loads(linea) for linea in salida.getvalue().splitlines() if linea.strip()]
    assert all("auditoria" not in str(linea.get("logger", "")) for linea in lineas)
    assert all("usuario_id" not in linea or linea["usuario_id"] is None for linea in lineas)


@pytest.fixture
def configuracion_politica(configuracion_sin_env: None, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for variable, valor in ENTORNO_POLITICA.items():
        monkeypatch.setenv(variable, valor)
    config.obtener_configuracion.cache_clear()
    yield


def test_la_dependencia_lee_la_configuracion(configuracion_politica: None) -> None:
    politica = obtener_politica_vigente()
    assert politica == POLITICA_PRUEBAS


@pytest.mark.parametrize(
    ("variable", "valor"),
    [("POLITICA_VERSION", "0.10"), ("POLITICA_ACTUALIZADA_EN", "")],
)
def test_sin_politica_completa_get_responde_503_y_el_log_no_trae_valores(
    configuracion_politica: None, monkeypatch: pytest.MonkeyPatch, variable: str, valor: str
) -> None:
    monkeypatch.setenv(variable, valor)
    config.obtener_configuracion.cache_clear()
    salida = io.StringIO()
    with TestClient(crear_app(stream_logs=salida), raise_server_exceptions=False) as http:
        respuesta = http.get("/v1/politica")
    assert respuesta.status_code == 503
    assert respuesta.headers["content-type"].startswith("application/problem+json")
    assert "politica no disponible" in salida.getvalue()
    assert CORREO_PRUEBAS not in salida.getvalue() + respuesta.text


def test_un_texto_publicado_con_marcadores_responde_503(
    configuracion_politica: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Si el texto de la versión todavía trae [PROVEEDOR DEL CORREO], [PAÍS] o {correo_privacidad}, la API no lo
    publica, aunque esté en PUBLICADAS con su huella."""
    texto = "## En un minuto\n\n- **[PROVEEDOR DEL CORREO]**, en [PAÍS], escribe a {correo_privacidad}.\n"
    (tmp_path / "politica-0.11.md").write_text(texto, encoding="utf-8")
    monkeypatch.setattr(textos_politica, "CARPETA", tmp_path)
    monkeypatch.setitem(PUBLICADAS, "0.11", hashlib.sha256(texto.encode("utf-8")).hexdigest())
    texto_publicado.cache_clear()
    salida = io.StringIO()
    try:
        with TestClient(crear_app(stream_logs=salida), raise_server_exceptions=False) as http:
            respuesta = http.get("/v1/politica")
    finally:
        texto_publicado.cache_clear()
    assert respuesta.status_code == 503
    assert "marcador" in salida.getvalue()


def test_sin_correo_configurado_se_publica_con_correo_contacto_null(
    configuracion_politica: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CORREO_PRIVACIDAD", "")
    config.obtener_configuracion.cache_clear()
    with TestClient(crear_app(stream_logs=io.StringIO())) as http:
        respuesta = http.get("/v1/politica")
    assert respuesta.status_code == 200
    assert respuesta.json()["correo_contacto"] is None
    assert respuesta.json()["huella"] == PUBLICADAS["0.11"]


def test_un_correo_configurado_que_no_es_el_del_texto_deja_un_aviso_sin_el_valor(
    configuracion_politica: None,
) -> None:
    salida = io.StringIO()
    with TestClient(crear_app(stream_logs=salida)) as http:
        assert http.get("/v1/politica").status_code == 200
    assert "CORREO_PRIVACIDAD no aparece en el texto" in salida.getvalue()
    assert CORREO_PRUEBAS not in salida.getvalue()


def test_la_salud_no_depende_de_la_politica(configuracion_politica: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLITICA_ACTUALIZADA_EN", "")
    config.obtener_configuracion.cache_clear()
    with TestClient(crear_app(stream_logs=io.StringIO())) as http:
        assert http.get("/v1/salud").status_code == 200


def test_correo_con_forma_invalida_no_carga_la_configuracion(
    configuracion_politica: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pydantic import ValidationError

    monkeypatch.setenv("CORREO_PRIVACIDAD", "{correo_privacidad}")
    config.obtener_configuracion.cache_clear()
    with pytest.raises(ValidationError):
        config.obtener_configuracion()


# --- El contrato ---------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def esquema() -> dict[str, Any]:
    return crear_app(io.StringIO()).openapi()


def test_openapi_json_coincide_con_la_api(esquema: dict[str, Any]) -> None:
    exportado = json.loads((DOCS / "openapi.json").read_text(encoding="utf-8"))
    for ruta in ("/v1/politica", "/v1/usuarios", "/v1/cuenta"):
        assert exportado["paths"][ruta] == esquema["paths"][ruta], f"vuelve a exportar {ruta}"
    for nombre in ("PoliticaVista", "PoliticaAceptadaVista", "CuentaVista", "SolicitudRegistro"):
        assert exportado["components"]["schemas"][nombre] == esquema["components"]["schemas"][nombre], nombre


def test_el_contrato_declara_los_codigos_y_los_campos(esquema: dict[str, Any]) -> None:
    assert {"200", "503"} <= set(esquema["paths"]["/v1/politica"]["get"]["responses"])
    assert "security" not in esquema["paths"]["/v1/politica"]["get"]
    assert {"201", "409", "422", "429", "503"} <= set(esquema["paths"]["/v1/usuarios"]["post"]["responses"])
    registro = esquema["components"]["schemas"]["SolicitudRegistro"]
    assert {"acepta_politica", "huella_politica"} <= set(registro["required"])
    assert registro["properties"]["acepta_politica"]["const"] is True
    politica = esquema["components"]["schemas"]["PoliticaVista"]
    assert set(politica["properties"]) == {"version", "actualizada_en", "huella", "texto", "correo_contacto"}
    assert "politica_aceptada" in esquema["components"]["schemas"]["CuentaVista"]["properties"]


def test_la_0_12_sigue_publicada_para_quien_la_acepto() -> None:
    """MATU-61 (D11): la 0.12 agrega los pedidos; la 0.11 sigue publicada para quien ya la aceptó."""
    assert {"0.11", "0.12"} <= set(PUBLICADAS)
    texto = texto_publicado("0.12")
    assert "La autorización para los pedidos" in texto and texto != texto_publicado("0.11")


@pytest.mark.rf("RF-25")
def test_la_0_13_sigue_publicada_para_quien_la_acepto() -> None:
    """MATU-62 (D11): la 0.13 agrega el pago con Transbank; la 0.11 y la 0.12 siguen publicadas."""
    assert {"0.11", "0.12", "0.13"} <= set(PUBLICADAS)
    texto = texto_publicado("0.13")
    assert texto != texto_publicado("0.12")
    for parte in (
        "pagarlo en la página de Transbank",
        "MATU no ve el número de tu tarjeta",
        "sin cobros reales",
        # Cierre del analista: la auditoría del pago y lo que ve el observador (§6)
        "crea, confirma, paga o cancela un pedido",
        "ve los productos del pedido y si está pagado",
        # P3 de MATU-94: todos los campos de la dirección, con la región y su nombre (§4)
        "calle, número, depto, comuna, región, un nombre para reconocerla",
    ):
        assert parte in texto, parte
    # Las declaraciones de la autorización de pedidos (MATU-61) siguen en el texto vigente
    from app.modules.care_circle.domain.declaraciones import DECLARACIONES_PEDIDOS

    assert all(declaracion in texto for declaracion in DECLARACIONES_PEDIDOS.values())


@pytest.mark.rf("RF-25")
def test_la_0_14_sigue_publicada_para_quien_la_acepto() -> None:
    """MATU-55 (P7 del analista): la 0.14 agrega «Dónde entraste», el registro de la cuenta y los avisos en los
    teléfonos; la 0.11, la 0.12 y la 0.13 siguen publicadas para quien las aceptó."""
    assert {"0.11", "0.12", "0.13", "0.14"} <= set(PUBLICADAS)
    texto = texto_publicado("0.14")
    assert texto != texto_publicado("0.13")
    for parte in (
        "**El registro de tu cuenta.**",
        "Nunca guardamos tu dirección IP, tu ubicación, tu navegador ni tu email en este registro",
        "lo que pasó en tu cuenta en los últimos 90 días, hasta 20 líneas",
        "**Registro de tu cuenta** (sección 4): 3 años",
        "los avisos en el teléfono se activan solo en teléfonos del equipo de MATU",
        "No te pedimos aceptar de nuevo esta política",
    ):
        assert parte in texto, parte
    # Lo de la 0.13 sigue en el texto vigente: el pago y las declaraciones de pedidos (MATU-61)
    assert "MATU no ve el número de tu tarjeta" in texto
    from app.modules.care_circle.domain.declaraciones import DECLARACIONES_PEDIDOS

    assert all(declaracion in texto for declaracion in DECLARACIONES_PEDIDOS.values())


@pytest.mark.rf("RF-38")
def test_la_0_15_sigue_publicada_para_quien_la_acepto() -> None:
    """MATU-42 y MATU-53: la 0.15 agrega las invitaciones sin correo ni teléfono, quiénes forman el grupo, el cambio de
    rol, salir y los 30 días de las invitaciones; de la 0.11 a la 0.14 siguen publicadas para quien las aceptó."""
    assert {"0.11", "0.12", "0.13", "0.14", "0.15"} <= set(PUBLICADAS)
    texto = texto_publicado("0.15")
    assert texto != texto_publicado("0.14")
    for parte in (
        "no guardamos el correo ni el teléfono de la persona que invitas",
        "el código no va en el mensaje",
        "**Quiénes forman el grupo:**",
        "No ven el email, el celular ni un número que identifique la cuenta",
        "### Salir de un grupo",
        "**Invitaciones a un grupo:** 30 días desde que se aceptan, se anulan, se bloquean o vencen",
        "La versión 0.15 agrega las invitaciones a tu grupo",
        "No te pedimos aceptar de nuevo esta política",
    ):
        assert parte in texto, parte
    # Lo de la 0.14 sigue en el texto vigente
    assert "**El registro de tu cuenta.**" in texto and "MATU no ve el número de tu tarjeta" in texto



@pytest.mark.rf("RF-05")
def test_la_0_16_sigue_publicada_para_quien_la_acepto() -> None:
    """MATU-46: la 0.16 dice que el teléfono del relevo se borra a los 30 días de que el acceso vence o se corta, y al
    borrar a la persona, y que el borrado a los 3 años todavía no existe; sigue publicada para quien la aceptó."""
    assert {"0.11", "0.12", "0.13", "0.14", "0.15", "0.16"} <= set(PUBLICADAS)
    texto = texto_publicado("0.16")
    assert texto != texto_publicado("0.15")
    for parte in (
        "El teléfono del relevo se borra 30 días después de que el acceso vence o se corta, lo que ocurra primero",
        "borramos el teléfono de cada relevo",
        "Todavía no se borran solos a los 3 años",
        "La versión 0.16 borra solo el teléfono del relevo a los 30 días",
        "solo acorta plazos",
    ):
        assert parte in texto, parte
    # Lo de la 0.15 sigue en el texto vigente
    assert "**Quiénes forman el grupo:**" in texto and "### Salir de un grupo" in texto


@pytest.mark.rf("Ley-21.719")
def test_la_0_17_sigue_publicada_para_quien_la_acepto() -> None:
    """MATU-54: la 0.17 agrega ver y descargar los datos desde la aplicación, en «Datos de» y en «Tus datos», con los
    90 días en pantalla y todo en el archivo, y nadie vuelve a aceptar; sigue publicada para quien la aceptó."""
    assert {"0.11", "0.12", "0.13", "0.14", "0.15", "0.16", "0.17"} <= set(PUBLICADAS)
    texto = texto_publicado("0.17")
    assert texto != texto_publicado("0.16")
    for parte in (
        "### Ver y descargar los datos desde la aplicación",
        "**Tus datos.** En «Tu cuenta», «Tus datos», ves lo que MATU guarda de tu cuenta",
        "**En la pantalla** ves los últimos 90 días de cada registro. **El archivo** trae todo lo guardado",
        "La versión 0.17 agrega ver y descargar los datos desde la aplicación. No te pedimos aceptar de nuevo esta"
        " política ni volver a dar las autorizaciones",
    ):
        assert parte in texto, parte
    # Lo de la 0.16 sigue en el texto vigente
    assert "La versión 0.16 borra solo el teléfono del relevo a los 30 días" in texto


@pytest.mark.rf("Ley-21.719")
def test_la_0_18_sigue_publicada_para_quien_la_acepto() -> None:
    """MATU-107: la 0.18 aclara en la sección 6 lo que ve quien cuida en «Datos de». MATU-63 la publica con el mismo
    archivo y la misma huella que MATU-107, para que las dos ramas se fusionen sin chocar."""
    huella = "1bdbac25460ead431a9bd1d39025440a3561e072e8d26cb26b3f5d3e6ed1316d"  # pragma: allowlist secret
    assert PUBLICADAS["0.18"] == huella
    texto = texto_publicado("0.18")
    assert texto != texto_publicado("0.17")
    assert "- La versión 0.18 aclara en la sección 6 lo que ve quien cuida en «Datos de» la persona." in texto


@pytest.mark.rf("Ley-21.719")
@pytest.mark.rf("RF-26")
def test_la_0_19_sigue_publicada_para_quien_la_acepto() -> None:
    """MATU-63 (D-63-16): la 0.19 agrega cómo los comercios preparan el pedido, el código de retiro y arrepentirse de
    la compra. Nadie vuelve a aceptar; sigue publicada para quien la aceptó."""
    huella = "c5b79d87898f6624cb97996ded97df9d50334ba5b717b12901a9a5efd93a1ff9"  # pragma: allowlist secret
    assert PUBLICADAS["0.19"] == huella
    texto = texto_publicado("0.19")
    assert texto != texto_publicado("0.18")
    for parte in (
        "Quien retira por MATU le dice un código de retiro, y el comercio solo puede revisar si es correcto: no lo ve.",
        "Quienes trabajan en el comercio entran a MATU con su propia cuenta.",
        "Arrepentirse de la compra lo pueden pedir quien administra y quien pagó.",
        "- La versión 0.19 agrega cómo los comercios preparan tu pedido y el código de retiro, y arrepentirte de una"
        " compra. No te pedimos aceptar de nuevo esta política",
    ):
        assert parte in texto, parte
    # Lo de la 0.18 sigue en el texto vigente
    assert "- La versión 0.18 aclara en la sección 6" in texto


@pytest.mark.rf("Ley-21.719")
@pytest.mark.rf("RF-26")
def test_la_0_20_sigue_publicada() -> None:
    """MATU-92: la 0.20 agrega «Tus pedidos», con los pedidos pagados de la persona según el rol, y arrepentirse de la
    compra o cancelar un pedido pagado desde la aplicación. No agrega datos, usos ni destinatarios: nadie vuelve a
    aceptar. De la 0.11 a la 0.19 siguen publicadas."""
    assert {"0.11", "0.12", "0.13", "0.14", "0.15", "0.16", "0.17", "0.18", "0.19", "0.20"} <= set(PUBLICADAS)
    huella = "5aab1f67299092cb6a47aa4c922f335b0ba0b42f1849b3ebc963ba385791c63d"  # pragma: allowlist secret
    assert PUBLICADAS["0.20"] == huella
    texto = texto_publicado("0.20")
    assert texto != texto_publicado("0.19")
    for parte in (
        "**Tus pedidos.** En «Tus pedidos» ves los pedidos pagados de la persona, con su estado, el comprobante y lo"
        " devuelto, según tu rol (sección 6).",
        "por correo se aceptan retractos hasta 90 días desde la entrega, y el equipo de MATU lo registra a tu nombre.",
        "- La versión 0.20 agrega «Tus pedidos»",
        "No te pedimos aceptar de nuevo esta política ni volver a dar las autorizaciones: cada persona del grupo ve lo"
        " mismo que antes, según su rol.",
        "Decreto 52 de 2022 del Ministerio de Economía (exclusión del derecho a retracto)",
        # §8, cierre del analista: el plazo se cuenta desde el cierre del pedido
        "- **Pedidos pagados y comprobantes de entrega:** 2 años desde que el pedido se cierra, es decir, desde que se"
        " entrega o se cancela con devolución. Mientras un pedido sigue en curso, el plazo no empieza.",
        "lo que pediste se guarda con el pedido, 2 años desde su cierre,",
        # §12, pedido de Martín antes de fusionar: el cambio de la 0.20 dice el plazo de los pedidos pagados
        "Desde esta versión, los pedidos pagados se guardan 2 años desde que el pedido se cierra, es decir, desde que"
        " se entrega o se cancela con devolución (sección 8).",
    ):
        assert parte in texto, parte
    # Arrepentirse y cancelar desde la aplicación ya no figuran como pendientes
    assert "- «Arrepentirme de la compra» y cancelar un pedido pagado desde la aplicación. Mientras tanto" not in texto
    # Lo de la 0.19 sigue en el texto vigente
    assert "- La versión 0.19 agrega cómo los comercios preparan tu pedido" in texto


@pytest.mark.rf("Ley-21.719")
@pytest.mark.rf("RF-26")
def test_la_0_21_sigue_publicada() -> None:
    """MATU-81: la 0.21 agrega la consola del equipo de MATU: qué ve de cada pedido, que entra con su contraseña y un
    código de su teléfono, que MATU registra cuándo revisa un pedido y lo que anota si hay un problema, que la familia
    ve en la copia de sus datos. El equipo ve menos que antes: nadie vuelve a aceptar. De la 0.11 a la 0.20 siguen
    publicadas. Desde MATU-113 la vigente es la 0.22."""
    assert {"0.11", "0.12", "0.13", "0.14", "0.15", "0.16", "0.17", "0.18", "0.19", "0.20", "0.21"} <= set(PUBLICADAS)
    huella = "15f6be576879d2a1dbf3a58df28a4394cb690d5f42c1aaff1899ef9fc3bf1ba7"  # pragma: allowlist secret
    assert PUBLICADAS["0.21"] == huella
    texto = texto_publicado("0.21")
    assert texto != texto_publicado("0.20")
    for parte in (
        # §6: la entrada en dos pasos del equipo
        "Entra con su contraseña y un código de su teléfono",
        # O3 del analista: en su consola no ve la dirección ni el teléfono
        "En su consola no ve la dirección de entrega ni el teléfono de contacto.",
        "No ve el nombre de la persona que cuidas, su ficha ni el consumo de insumos.",
        "MATU registra cuándo revisa tu pedido.",
        # Opción B de Jorge (17-11): la nota se guarda cifrada con una clave propia
        "lo anota con lo que pasó y cómo se resolvió. Esa nota se guarda cifrada, y la ves en la copia de tus datos.",
        # §8: los plazos de lo que anota el equipo y del registro de revisión
        "- **Lo que pasó con un pedido:** si hay un problema con un pedido, lo que anota el equipo de MATU sigue al"
        " pedido: se guarda cifrado, 2 años desde que el pedido se cierra, y se borra con él.",
        # Decisión de Jorge del 17-11: la nota queda ilegible solo al borrar los datos de la persona (§8, §9 y §10)
        "Si pides borrar los datos de la persona, lo anotado hasta ese momento queda ilegible, porque destruimos la"
        " clave con que se guardó. Lo que el equipo anote después, de un pedido que todavía se guarda, va con una clave"
        " nueva y sigue el plazo del pedido.",
        "- Lo que el equipo de MATU anota de un pedido se cifra con una clave propia de cada persona cuidada, distinta"
        " de la de la ficha y protegida por la misma clave maestra.",
        "- Lo que el equipo de MATU anotó de sus pedidos queda ilegible en ese momento. Si después hay que anotar algo"
        " de un pedido pagado que todavía se guarda, se guarda con una clave nueva y se borra con el pedido.",
        "Que alguien de tu grupo mire un pedido o un pago no se registra.",
        # Cierre del analista (17-11): §9 dice dónde se ve la nota y §10 la suma a la copia de la persona
        "y quien administra el grupo o quien cuida a la persona lo ve en la copia de sus datos, en «Datos de» la"
        " persona.",
        "lo que anotó el equipo de MATU si hubo un problema con un pedido y cada vez que el equipo revisó un pedido,",
        "- La versión 0.21 agrega la consola del equipo de MATU",
        "Suma dos registros sobre tu pedido: la nota de lo que pasó, guardada cifrada, y el registro de cuándo el"
        " equipo revisa tu pedido, que ves en la copia de tus datos.",
        # §13: con comercios ficticios, el retiro y la entrega se marcan sin un pedido real (decisión del 17-11)
        "el retiro y la entrega se marcan en MATU sin llevar un pedido real",
        "No te pedimos aceptar de nuevo esta política ni volver a dar las autorizaciones: el equipo ve menos que antes,"
        " y lo que anota es parte de responder por tu pedido.",
    ):
        assert parte in texto, parte
    # La frase de la 0.21 sin el cifrado de la nota ya no está
    assert "lo anota con lo que pasó y cómo se resolvió, y lo ves en la copia de tus datos." not in texto
    # La frase anterior del equipo, que decía que veía «los pedidos y los pagos» para soporte, ya no está
    assert "**El equipo de MATU:** para dar soporte ve los pedidos y los pagos." not in texto
    # La frase anterior de §13, que decía que el equipo de MATU hacía el retiro y la entrega, ya no está
    assert "El retiro y la entrega los hace el equipo de MATU." not in texto
    # Lo de la 0.20 sigue en el texto vigente
    assert "- La versión 0.20 agrega «Tus pedidos»" in texto


@pytest.mark.rf("Ley-21.719")
@pytest.mark.rf("RF-21")
@pytest.mark.rf("RF-26")
def test_la_0_22_sigue_publicada() -> None:
    """MATU-113: la 0.22 dice en §6 que quien «Se informa» ve los productos del pedido, su estado y las fechas del pago
    y de la entrega, sin precios, envío, total ni lo devuelto. Ve menos que antes: nadie vuelve a aceptar. De la 0.11
    a la 0.21 siguen publicadas. Desde MATU-76 la vigente es la 0.23."""
    anteriores = {"0.11", "0.12", "0.13", "0.14", "0.15", "0.16", "0.17", "0.18", "0.19", "0.20", "0.21"}
    assert anteriores | {"0.22"} <= set(PUBLICADAS)
    huella = "c1313a5e812a04c50bd539d0e27403a2152011887d2b6c1b9593cffb28293d3e"  # pragma: allowlist secret
    assert PUBLICADAS["0.22"] == huella
    texto = texto_publicado("0.22")
    assert texto != texto_publicado("0.21")
    for parte in (
        # §6: la frase nueva del observador
        "No ve lo que cuesta ni lo que se pagó por lo que se pidió: ni los precios del pedido, ni el envío, ni el"
        " total, ni lo devuelto.",
        "- **Observador:** ve los productos del pedido, cuántos de cada uno y de qué comercio, y en qué estado está,",
        "con la fecha en que se pagó y la de la entrega.",
        "Los precios del catálogo los ve, como todas las personas del grupo.",
        # §12: el cambio de la 0.22 y por qué nadie vuelve a aceptar
        "- La versión 0.22 aclara que quien «Se informa» ve los productos del pedido",
        "No te pedimos aceptar de nuevo esta política ni volver a dar las autorizaciones: el estado y las fechas son"
        " del mismo pedido que ya veía, y deja de ver los montos.",
    ):
        assert parte in texto, parte
    # La frase anterior del observador, que no decía que no ve los montos, ya no está
    assert (
        "- **Observador:** ve los productos del pedido y si está pagado, sin la dirección, el teléfono de contacto, el"
        " resumen ni el pago." not in texto
    )
    # Lo de la 0.21 sigue en el texto vigente
    assert "- La versión 0.21 agrega la consola del equipo de MATU" in texto


@pytest.mark.rf("Ley-21.719")
@pytest.mark.rf("RF-39")
@pytest.mark.rf("RF-26")
def test_la_0_23_sigue_publicada() -> None:
    """MATU-76: la 0.23 agrega en §6 los avisos de un pedido, que le llegan solo a quien lo pagó, y deja un solo texto
    para la notificación en el teléfono («Tienes una novedad»). Avisar del pedido es parte de responder por él: nadie
    vuelve a aceptar. De la 0.11 a la 0.22 siguen publicadas. Desde MATU-114 la vigente es la 0.24."""
    anteriores = {"0.11", "0.12", "0.13", "0.14", "0.15", "0.16", "0.17", "0.18", "0.19", "0.20", "0.21", "0.22"}
    assert anteriores | {"0.23"} <= set(PUBLICADAS)
    huella = "d3a606c71399a0bccf90c274bab44cb228c7689893fe0270caeca8aef519247f"  # pragma: allowlist secret
    assert PUBLICADAS["0.23"] == huella
    texto = texto_publicado("0.23")
    assert texto != texto_publicado("0.22")
    for parte in (
        # §6: el push genérico, el mismo para todo lo que MATU avisa
        "y la notificación en el teléfono, «MATU · Tienes una novedad. Abre la app para verla.», que es el mismo texto"
        " para todo lo que MATU avisa.",
        # §6: los avisos del pedido, solo a quien pagó y sin datos del pedido
        "Le avisamos solo a quien pagó, sea cual sea su rol en el grupo, y no al resto del grupo.",
        "el correo dice «Hay una novedad en un pedido. Abre la app para verla.»",
        "**El correo que es sobre tu dinero te llega igual**: el de una devolución, un producto que faltó o una"
        " cancelación.",
        # §12: el cambio de la 0.23 y por qué nadie vuelve a aceptar
        "- La versión 0.23 agrega los avisos de tus pedidos, que le llegan solo a quien pagó,",
        # §12, desde el cierre del analista: la base son las condiciones que aceptó quien pagó
        "No te pedimos aceptar de nuevo esta política ni volver a dar las autorizaciones: avisarte de un pedido que"
        " pagaste es parte de responder por esa compra, y las condiciones del pedido que aceptaste al pagar ya dicen"
        " que te avisamos.",
    ):
        assert parte in texto, parte
    # El texto de §12 antes del cierre del analista ya no está
    assert "y eso ya lo autorizaste" not in texto
    # El texto anterior de la notificación, que nombraba el insumo, ya no está
    assert "El aviso dice solo «MATU: un insumo se está acabando." not in texto
    # Lo de la 0.22 sigue en el texto vigente
    assert "- La versión 0.22 aclara que quien «Se informa» ve los productos del pedido" in texto


@pytest.mark.rf("Ley-21.719")
@pytest.mark.rf("RF-40")
def test_la_0_24_sigue_publicada() -> None:
    """MATU-114: la 0.24 dice en §6 que tu email y tu celular los ves solo tú, también frente al equipo que opera MATU.
    El equipo ve menos que antes: nadie vuelve a aceptar. De la 0.11 a la 0.23 siguen publicadas. Desde MATU-116 la
    vigente es la 0.25."""
    anteriores = {"0.11", "0.12", "0.13", "0.14", "0.15", "0.16", "0.17", "0.18", "0.19", "0.20", "0.21", "0.22",
                  "0.23"}
    assert anteriores | {"0.24"} <= set(PUBLICADAS)
    huella = "7d7af6d9ae62a7e3811db09feaff6a4acddedc45658f3a58c12dc34e18a7d219"  # pragma: allowlist secret
    assert PUBLICADAS["0.24"] == huella
    texto = texto_publicado("0.24")
    assert texto != texto_publicado("0.23")
    for parte in (
        # §6: el email y el celular, solo para quien tiene la cuenta
        "**Tu cuenta:** tu email y tu celular los ves solo tú. Las personas de tus grupos no los ven, y el equipo que"
        " opera MATU tampoco los ve desde sus herramientas.",
        "Si nos escribes al correo de la sección 10, te respondemos a ese correo.",
        # §6 (N2 del cierre del analista): el intento registrado sin el correo
        "Si alguien de la familia pide por correo arrepentirse de una compra y el equipo lo intenta registrar con un"
        " correo que no es de quien administra el grupo, MATU también lo registra, sin el correo.",
        # §10: lo ve quien pide «Datos de» la persona
        "cada vez que el equipo revisó un pedido o intentó registrar un arrepentimiento con un correo que no"
        " correspondía",
        # §12: el cambio de la 0.24 y por qué nadie vuelve a aceptar
        "- La versión 0.24 aclara que el equipo que opera MATU no ve tu email ni tu celular, y agrega que MATU"
        " registra, sin el correo, cuando el equipo intenta registrar un arrepentimiento con un correo que no es de"
        " quien administra el grupo.",
        "el equipo ve menos que antes, y ese registro protege tu pedido.",
        # §13: lo que falta construir, el borrado a los 3 años de ese registro
        "o intentó registrar un arrepentimiento por correo. Mientras no exista, MATU no trata datos reales.",
    ):
        assert parte in texto, parte
    # La frase anterior, que decía que el equipo los veía, ya no está
    assert "tu email y tu celular los ven solo tú y el equipo que opera MATU" not in texto
    # Lo de la 0.23 sigue en el texto vigente
    assert "- La versión 0.23 agrega los avisos de tus pedidos, que le llegan solo a quien pagó," in texto


@pytest.mark.rf("Ley-21.719")
@pytest.mark.rf("RF-37")
@pytest.mark.rf("R3")
def test_la_0_25_esta_publicada_y_es_la_de_env_example() -> None:
    """MATU-116: la 0.25 dice en §6 que quien pagó y pasó a «Se informa» sigue viendo ese pedido como quien pagó, y en
    §10 que «Tus datos» trae sus pagos aunque haya cambiado de rol o salido del grupo. Solo ve más de sus propios
    datos: nadie vuelve a aceptar. De la 0.11 a la 0.24 siguen publicadas."""
    anteriores = {"0.11", "0.12", "0.13", "0.14", "0.15", "0.16", "0.17", "0.18", "0.19", "0.20", "0.21", "0.22",
                  "0.23", "0.24"}
    assert anteriores | {"0.25"} <= set(PUBLICADAS)
    huella = "aa1167e62cdc0c3467972d4789f55020da11ef2f7f98cba1a45a1a499ebc64c8"  # pragma: allowlist secret
    assert PUBLICADAS["0.25"] == huella
    valores = dotenv_values(BACKEND.parent / ".env.example")
    assert (valores["POLITICA_VERSION"], valores["POLITICA_ACTUALIZADA_EN"]) == ("0.25", "2026-11-18")
    texto = texto_publicado("0.25")
    assert texto != texto_publicado("0.24")
    for parte in (
        # §6: quien pagó y pasó a «Se informa»
        "Si pagaste un pedido y después pasaste a «Se informa», ese pedido lo sigues viendo como quien pagó",
        # §6 (aprobada por Jorge el 18-11, fuente 32f85fc): el retracto por correo, a nombre de quien pagó
        "Si pediste por correo arrepentirte de una compra que pagaste, el equipo lo registra a tu nombre aunque ya no"
        " estés en el grupo, porque la devolución va a tu tarjeta.",
        # §6 (D1 del cierre del analista, aprobado por Jorge el 18-11, fuente 1b52afd): el intento fallido es solo el
        # del correo que no es de quien administra ni de quien pagó ese pedido
        "el equipo lo intenta registrar con un correo que no es de quien administra el grupo ni de quien pagó ese"
        " pedido, MATU también lo registra, sin el correo.",
        "sin la dirección ni el teléfono de contacto, y puedes arrepentirte de la compra.",
        # §10: «Tus datos», también de los grupos que dejó
        "Si pagaste un pedido, también tus pagos, aunque hayas cambiado de rol o ya no estés en ese grupo, con el"
        " nombre del grupo (o «Un grupo del que saliste»)",
        "Si pediste arrepentirte de una compra, también cómo se resolvió, y qué productos, mientras sigas en el grupo.",
        # §12: el cambio de la 0.25 y por qué nadie vuelve a aceptar
        "- La versión 0.25 aclara que quien pagó un pedido sigue viendo sus pagos en «Tus datos», aunque cambie de rol"
        " o salga del grupo,",
        "solo ves más de tus propios datos, sin nuevos usos, destinatarios ni declaraciones.",
    ):
        assert parte in texto, parte
    # Lo de la 0.24 sigue en el texto vigente
    assert "- La versión 0.24 aclara que el equipo que opera MATU no ve tu email ni tu celular" in texto
