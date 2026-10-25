"""MATU-07 · Alta de la persona cuidada: validación, roles y respuesta, sin base (RF-01, Ley 21.719).

La API corre de verdad (errores RFC 7807, logs, validación), pero sesion_de_grupo se reemplaza por
un contexto sintético con el rol que pide la prueba, y el repositorio por uno en memoria. Las
pruebas contra PostgreSQL están en test_personas.py.
"""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Annotated, Any, cast

import pytest
from fastapi import FastAPI, Header
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import obtener_fabrica_sesiones
from app.core.errores import ErrorMATU
from app.modules.care_circle.api.dependencias import ContextoGrupo, sesion_de_grupo
from app.modules.care_circle.api.router_personas import obtener_politica_version, obtener_repositorio_personas
from app.modules.care_circle.application.ports import (
    AltaPersona,
    PersonaCompleta,
    PersonaNombreYDireccion,
    PersonaSoloNombre,
)
from app.modules.care_circle.domain.avisos import AVISO_CUIDADOR_DE_HECHO
from tests.modules.care_circle.conftest import POLITICA_PRUEBAS, RUTA_PERSONAS, cuerpo_alta, direccion_sintetica
from tests.modules.conftest import EntornoIam

PROBLEMA = "application/problem+json"
DIAGNOSTICO = "Alzheimer"


class RepositorioEnMemoria:
    """Doble del puerto RepositorioPersonas: guarda las altas en una lista."""

    def __init__(self) -> None:
        self.altas: list[AltaPersona] = []

    def guardar_alta(self, alta: AltaPersona) -> None:
        self.altas.append(alta)

    def listar_completas(self) -> list[PersonaCompleta]:
        return [
            PersonaCompleta(
                id=a.persona_id,
                nombre=a.nombre,
                nombre_pila=a.nombre_pila,
                nivel_apoyo=a.nivel_apoyo,
                direccion=a.direccion,
                consentimiento=None,
            )
            for a in self.altas
        ]

    def listar_nombre_y_direccion(self) -> list[PersonaNombreYDireccion]:
        return [PersonaNombreYDireccion(id=a.persona_id, nombre=a.nombre, direccion=a.direccion) for a in self.altas]

    def listar_solo_nombre(self) -> list[PersonaSoloNombre]:
        return [PersonaSoloNombre(id=a.persona_id, nombre=a.nombre) for a in self.altas]


@dataclass
class EntornoSinBase:
    iam: EntornoIam
    repositorio: RepositorioEnMemoria
    usuario_id: uuid.UUID = field(default_factory=uuid.uuid4)
    grupo_id: uuid.UUID = field(default_factory=uuid.uuid4)
    rol: str = "admin"

    def crear(self, cuerpo: Any, grupo_path: uuid.UUID | str | None = None) -> Any:
        ruta = RUTA_PERSONAS.format(grupo_path if grupo_path is not None else self.grupo_id)
        return self.iam.cliente.post(ruta, json=cuerpo, headers={"X-Grupo-Id": str(self.grupo_id)})

    def listar(self) -> Any:
        return self.iam.cliente.get(RUTA_PERSONAS.format(self.grupo_id), headers={"X-Grupo-Id": str(self.grupo_id)})

    def errores(self, respuesta: Any) -> list[str]:
        assert respuesta.status_code == 422
        assert respuesta.headers["content-type"].startswith(PROBLEMA)
        return [e["campo"] for e in respuesta.json()["errores"]]


@pytest.fixture
def sin_base(entorno_iam: EntornoIam) -> Iterator[EntornoSinBase]:
    entorno = EntornoSinBase(iam=entorno_iam, repositorio=RepositorioEnMemoria())
    app = cast(FastAPI, entorno_iam.cliente.app)

    def contexto_sintetico(x_grupo_id: Annotated[str | None, Header(alias="X-Grupo-Id")] = None) -> ContextoGrupo:
        # Imita a sesion_de_grupo: el grupo sale de la cabecera, el rol lo fija la prueba
        if x_grupo_id is None:
            raise ErrorMATU(404)
        return ContextoGrupo(
            usuario_id=entorno.usuario_id, grupo_id=uuid.UUID(x_grupo_id), sesion=cast(Session, None), rol=entorno.rol
        )

    app.dependency_overrides[sesion_de_grupo] = contexto_sintetico
    app.dependency_overrides[obtener_repositorio_personas] = lambda: entorno.repositorio
    app.dependency_overrides[obtener_politica_version] = lambda: POLITICA_PRUEBAS
    yield entorno


# --- Camino feliz, sin base ----------------------------------------------------------------


@pytest.mark.rf("RF-01")
def test_alta_titular_responde_201_con_su_consentimiento(sin_base: EntornoSinBase) -> None:
    respuesta = sin_base.crear(cuerpo_alta("titular", nombre="  Persona Ficticia Uno  "))

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"id", "nombre", "nombre_pila", "nivel_apoyo", "direccion", "consentimiento", "aviso"}
    assert cuerpo["nombre"] == "Persona Ficticia Uno"
    assert cuerpo["direccion"] is None
    assert cuerpo["aviso"] is None
    assert cuerpo["consentimiento"] == {
        "id": cuerpo["consentimiento"]["id"],
        "calidad_otorgante": "titular",
        "finalidad": "plan_cuidado",
        "version_politica": POLITICA_PRUEBAS,
        "otorgado_en": "2026-10-20T12:00:00Z",
        "revision_vence_en": None,
    }
    # Lo que se guarda: el instante del reloj fijo, la versión del servidor y la evidencia mínima
    [alta] = sin_base.repositorio.altas
    assert alta.persona_id == uuid.UUID(cuerpo["id"])
    assert alta.grupo_id == sin_base.grupo_id
    assert alta.usuario_id == sin_base.usuario_id
    assert alta.otorgado_en == datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
    assert alta.version_politica == POLITICA_PRUEBAS
    assert alta.evidencia["modalidad"] == "registrada_por_usuario_en_presencia_del_titular"
    assert alta.direccion is None and alta.direccion_id is None
    assert alta.request_id == respuesta.headers["x-request-id"]


@pytest.mark.rf("RF-01")
def test_alta_cuidador_de_hecho_devuelve_el_aviso_canonico(sin_base: EntornoSinBase) -> None:
    respuesta = sin_base.crear(cuerpo_alta("cuidador_de_hecho"))

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["aviso"] == {
        "id": "aviso_cuidador_de_hecho",
        "version": "1.0",
        "titulo": "Aviso: tu autorización tiene un límite",
        "parrafos": list(AVISO_CUIDADOR_DE_HECHO.parrafos),
        "sha256": AVISO_CUIDADOR_DE_HECHO.sha256,
    }
    assert cuerpo["consentimiento"]["revision_vence_en"] == "2027-10-20T12:00:00Z"


@pytest.mark.rf("RF-01")
def test_alta_con_direccion_la_devuelve_sin_coordenadas(sin_base: EntornoSinBase) -> None:
    respuesta = sin_base.crear(cuerpo_alta(direccion=direccion_sintetica(depto="21")))

    assert respuesta.status_code == 201
    assert respuesta.json()["direccion"] == {
        "etiqueta": "Casa",
        "calle": "Calle Ficticia",
        "numero": "100",
        "depto": "21",
        "comuna": "Comuna Sintética",
        "region": "Metropolitana",
        "referencia": None,
    }
    [alta] = sin_base.repositorio.altas
    assert alta.direccion_id is not None


@pytest.mark.rf("RF-01")
def test_cuidador_tambien_da_de_alta(sin_base: EntornoSinBase) -> None:
    sin_base.rol = "cuidador"

    assert sin_base.crear(cuerpo_alta()).status_code == 201


# --- Diagnóstico y campos extra ------------------------------------------------------------


@pytest.mark.rf("RF-01")
def test_campo_diagnostico_422(sin_base: EntornoSinBase) -> None:
    # Dado un cuerpo válido con un diagnóstico agregado
    respuesta = sin_base.crear(cuerpo_alta(diagnostico=DIAGNOSTICO))

    # Entonces responde 422 nombrando el campo, y no se crea nada
    assert sin_base.errores(respuesta) == ["diagnostico"]
    assert sin_base.repositorio.altas == []
    # Y el valor no aparece ni en la respuesta (sin input ni ctx) ni en los logs
    assert DIAGNOSTICO not in respuesta.text
    assert [set(e) for e in respuesta.json()["errores"]] == [{"campo", "mensaje", "tipo"}]
    assert DIAGNOSTICO not in sin_base.iam.texto_log()


@pytest.mark.rf("RF-01")
@pytest.mark.parametrize(
    ("extra", "campo"),
    [
        ({"lat": -33.45, "lng": -70.66}, ["direccion.lat", "direccion.lng"]),
        ({"diagnostico": DIAGNOSTICO}, ["direccion.diagnostico"]),
    ],
    ids=["coordenadas", "diagnostico-anidado"],
)
def test_direccion_con_campos_extra_422(sin_base: EntornoSinBase, extra: dict[str, Any], campo: list[str]) -> None:
    respuesta = sin_base.crear(cuerpo_alta(direccion=direccion_sintetica(**extra)))

    assert sin_base.errores(respuesta) == campo
    assert sin_base.repositorio.altas == []
    assert DIAGNOSTICO not in respuesta.text
    assert DIAGNOSTICO not in sin_base.iam.texto_log()


@pytest.mark.rf("RF-01")
@pytest.mark.parametrize(
    "extra",
    [
        {"version_politica": "9.9"},
        {"grupo_id": str(uuid.uuid4())},
        {"usuario_id": str(uuid.uuid4())},
        {"otorgado_en": "2020-01-01T00:00:00Z"},
        {"revision_vence_en": "2099-01-01T00:00:00Z"},
    ],
    ids=lambda e: next(iter(e)),
)
def test_lo_que_fija_el_servidor_no_se_acepta_del_cliente(sin_base: EntornoSinBase, extra: dict[str, Any]) -> None:
    respuesta = sin_base.crear(cuerpo_alta(**extra))

    assert sin_base.errores(respuesta) == list(extra)
    assert sin_base.repositorio.altas == []


@pytest.mark.rf("RF-01")
def test_aviso_con_campos_extra_422(sin_base: EntornoSinBase) -> None:
    aviso = {"id": "aviso_cuidador_de_hecho", "version": "1.0", "titulo": "otro texto"}

    respuesta = sin_base.crear(cuerpo_alta("cuidador_de_hecho", aviso=aviso))

    assert sin_base.errores(respuesta) == ["aviso.titulo"]


# --- Reglas por calidad --------------------------------------------------------------------


@pytest.mark.rf("RF-01")
@pytest.mark.parametrize(
    "referencia",
    [None, "", "    "],
    ids=["ausente", "vacia", "solo-espacios"],
)
def test_representante_sin_documento_422(sin_base: EntornoSinBase, referencia: str | None) -> None:
    # Dado un representante legal sin referencia al documento que lo acredita
    cuerpo = cuerpo_alta("representante_legal")
    if referencia is None:
        del cuerpo["referencia_documento"]
    else:
        cuerpo["referencia_documento"] = referencia

    # Cuando da de alta
    respuesta = sin_base.crear(cuerpo)

    # Entonces responde 422 nombrando el campo, y no se crea nada
    assert sin_base.errores(respuesta) == ["referencia_documento"]
    assert respuesta.json()["errores"][0]["tipo"] == "regla_calidad_otorgante"
    assert sin_base.repositorio.altas == []


@pytest.mark.rf("RF-01")
def test_representante_con_documento_guarda_la_referencia_sin_devolverla(sin_base: EntornoSinBase) -> None:
    referencia = "Resolución sintética 456-2026"

    respuesta = sin_base.crear(cuerpo_alta("representante_legal", referencia_documento=f"  {referencia} "))

    assert respuesta.status_code == 201
    assert referencia not in respuesta.text
    assert sin_base.repositorio.altas[0].referencia_documento == referencia
    assert sin_base.repositorio.altas[0].revision_vence_en is None
    assert referencia not in sin_base.iam.texto_log()


@pytest.mark.rf("RF-01")
@pytest.mark.parametrize(
    ("calidad", "cambios", "campo"),
    [
        ("titular", {"aviso": {"id": "aviso_cuidador_de_hecho", "version": "1.0"}}, "aviso"),
        ("titular", {"referencia_documento": "Documento sintético"}, "referencia_documento"),
        ("representante_legal", {"aviso": {"id": "aviso_cuidador_de_hecho", "version": "1.0"}}, "aviso"),
        ("cuidador_de_hecho", {"aviso": None}, "aviso"),
        ("cuidador_de_hecho", {"aviso": {"id": "aviso_cuidador_de_hecho", "version": "0.1"}}, "aviso"),
        ("cuidador_de_hecho", {"aviso": {"id": "aviso_titular", "version": "1.0"}}, "aviso"),
        ("cuidador_de_hecho", {"referencia_documento": "Documento sintético"}, "referencia_documento"),
    ],
    ids=[
        "titular-con-aviso",
        "titular-con-referencia",
        "representante-con-aviso",
        "cuidador-sin-aviso",
        "cuidador-aviso-no-vigente",
        "cuidador-aviso-de-otro-id",
        "cuidador-con-referencia",
    ],
)
def test_reglas_cruzadas_por_calidad_422(
    sin_base: EntornoSinBase, calidad: str, cambios: dict[str, Any], campo: str
) -> None:
    respuesta = sin_base.crear(cuerpo_alta(calidad, **cambios))

    assert sin_base.errores(respuesta) == [campo]
    assert sin_base.repositorio.altas == []
    assert "Documento sintético" not in respuesta.text


@pytest.mark.rf("RF-01")
@pytest.mark.parametrize(
    "referencia",
    ["R" * 201, "línea uno\nlínea dos", "con\x00nulo", 12345, ["Documento"], {"archivo": "base64"}],
    ids=["201-caracteres", "salto-de-linea", "caracter-nulo", "numero", "lista", "objeto"],
)
def test_referencia_solo_texto_de_hasta_200(sin_base: EntornoSinBase, referencia: Any) -> None:
    respuesta = sin_base.crear(cuerpo_alta("representante_legal", referencia_documento=referencia))

    assert sin_base.errores(respuesta) == ["referencia_documento"]
    assert sin_base.repositorio.altas == []
    if isinstance(referencia, str):
        assert referencia not in respuesta.text


@pytest.mark.rf("RF-01")
def test_referencia_de_200_caracteres_se_acepta(sin_base: EntornoSinBase) -> None:
    respuesta = sin_base.crear(cuerpo_alta("representante_legal", referencia_documento="R" * 200))

    assert respuesta.status_code == 201


@pytest.mark.rf("RF-01")
@pytest.mark.parametrize(
    ("cambios", "campo"),
    [
        ({"nombre": "   "}, "nombre"),
        ({"nombre": "N" * 121}, "nombre"),
        ({"nombre_pila": ""}, "nombre_pila"),
        ({"nivel_apoyo": "postrada"}, "nivel_apoyo"),
        ({"calidad_otorgante": "hija"}, "calidad_otorgante"),
        ({"direccion": {"calle": "Calle Ficticia"}}, "direccion.numero"),
    ],
    ids=[
        "nombre-vacio", "nombre-largo", "nombre-pila-vacio",
        "nivel-invalido", "calidad-invalida", "direccion-incompleta",
    ],
)
def test_campos_invalidos_422(sin_base: EntornoSinBase, cambios: dict[str, Any], campo: str) -> None:
    respuesta = sin_base.crear(cuerpo_alta(**cambios))

    assert campo in sin_base.errores(respuesta)
    assert sin_base.repositorio.altas == []


# --- Roles y contexto ----------------------------------------------------------------------


@pytest.mark.rf("RF-01")
@pytest.mark.parametrize("rol", ["pagador", "observador"])
def test_pagador_u_observador_reciben_404_aunque_el_cuerpo_sea_invalido(sin_base: EntornoSinBase, rol: str) -> None:
    # El rol se verifica antes que el cuerpo: un 422 revelaría que la ruta existe para él
    sin_base.rol = rol

    respuesta = sin_base.crear(cuerpo_alta(diagnostico=DIAGNOSTICO))

    assert respuesta.status_code == 404
    assert respuesta.headers["content-type"].startswith(PROBLEMA)
    assert sin_base.repositorio.altas == []
    assert DIAGNOSTICO not in sin_base.iam.texto_log()


@pytest.mark.rf("RF-01")
@pytest.mark.parametrize("grupo_path", [uuid.uuid4(), "no-es-un-uuid"], ids=["otro-grupo", "no-uuid"])
def test_grupo_del_path_distinto_del_contexto_404(sin_base: EntornoSinBase, grupo_path: Any) -> None:
    crear = sin_base.crear(cuerpo_alta(), grupo_path=grupo_path)
    listar = sin_base.iam.cliente.get(
        RUTA_PERSONAS.format(grupo_path), headers={"X-Grupo-Id": str(sin_base.grupo_id)}
    )

    for respuesta in (crear, listar):
        assert respuesta.status_code == 404
        assert respuesta.headers["content-type"].startswith(PROBLEMA)
    assert sin_base.repositorio.altas == []


@pytest.mark.rf("RF-01")
def test_sin_token_401(entorno_iam: EntornoIam) -> None:
    # Sin el contexto sintético: sesion_de_grupo real exige el token antes de abrir la base
    def fabrica_que_falla() -> Session:
        raise AssertionError("esta petición no debía abrir una sesión")

    app = cast(FastAPI, entorno_iam.cliente.app)
    app.dependency_overrides[obtener_fabrica_sesiones] = lambda: cast(sessionmaker[Session], fabrica_que_falla)
    grupo = str(uuid.uuid4())

    crear = entorno_iam.cliente.post(RUTA_PERSONAS.format(grupo), json=cuerpo_alta(), headers={"X-Grupo-Id": grupo})
    listar = entorno_iam.cliente.get(RUTA_PERSONAS.format(grupo), headers={"X-Grupo-Id": grupo})

    for respuesta in (crear, listar):
        assert respuesta.status_code == 401
        assert respuesta.headers["www-authenticate"] == "Bearer"


# --- Lista por rol, sin base ---------------------------------------------------------------


@pytest.mark.rf("RF-01")
@pytest.mark.parametrize(
    ("rol", "campos"),
    [
        ("admin", {"id", "nombre", "nombre_pila", "nivel_apoyo", "direccion", "consentimiento"}),
        ("cuidador", {"id", "nombre", "nombre_pila", "nivel_apoyo", "direccion", "consentimiento"}),
        ("pagador", {"id", "nombre", "direccion"}),
        ("observador", {"id", "nombre"}),
    ],
)
def test_lista_con_la_vista_del_rol(sin_base: EntornoSinBase, rol: str, campos: set[str]) -> None:
    assert sin_base.crear(cuerpo_alta(direccion=direccion_sintetica())).status_code == 201
    sin_base.rol = rol

    respuesta = sin_base.listar()

    assert respuesta.status_code == 200
    [persona] = respuesta.json()
    assert set(persona) == campos
    assert persona["nombre"] == "Persona Ficticia Uno"


@pytest.mark.rf("RF-01")
def test_contrato_openapi_de_personas_cuidadas(sin_base: EntornoSinBase) -> None:
    esquema = sin_base.iam.cliente.get("/openapi.json").json()
    ruta = esquema["paths"]["/v1/grupos/{grupo_id}/personas-cuidadas"]

    assert set(ruta) == {"get", "post"}
    assert "201" in ruta["post"]["responses"]
    solicitud = esquema["components"]["schemas"]["SolicitudPersona"]
    assert solicitud["additionalProperties"] is False
    assert "diagnostico" not in solicitud["properties"]
    assert "version_politica" not in solicitud["properties"]
    assert esquema["components"]["schemas"]["DireccionNueva"]["additionalProperties"] is False
    assert {"lat", "lng"}.isdisjoint(esquema["components"]["schemas"]["DireccionNueva"]["properties"])
