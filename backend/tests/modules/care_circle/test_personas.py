"""MATU-07 · Dar de alta a la persona cuidada con su consentimiento, contra PostgreSQL (RF-01, Ley 21.719).

Corren como matu_app, con cuentas registradas e iniciadas por la API, grupos sembrados como
superusuario y la versión de la política fijada en POLITICA_PRUEBAS. Las filas se revisan como
superusuario. Las de validación sin base están en test_personas_api.py.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, cast

import psycopg
import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import obtener_configuracion
from app.core.db import obtener_fabrica_sesiones
from app.modules.care_circle.api.dependencias import SesionDeGrupo
from app.modules.care_circle.api.router_personas import obtener_repositorio_personas
from app.modules.care_circle.application.ports import AltaPersona, RepositorioPersonas
from app.modules.care_circle.domain.avisos import AVISO_CUIDADOR_DE_HECHO
from app.modules.care_circle.infrastructure.repositorio_personas import RepositorioPersonasSQL
from app.modules.iam.api.dependencias import obtener_reloj
from app.modules.iam.domain.sesion import vencimiento
from app.modules.iam.infrastructure.tokens_jwt import EmisorJWT
from tests.base_datos import DSN, requiere_base
from tests.dobles.reloj_fijo import RelojFijo
from tests.modules.care_circle.conftest import POLITICA_PRUEBAS, EntornoPersonas, cuerpo_alta, direccion_sintetica

PROBLEMA = "application/problem+json"
OTORGADO_EN = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
CAMPOS_COMPLETOS = {"id", "nombre", "nombre_pila", "nivel_apoyo", "direccion", "consentimiento"}


def _una(sql: str, *parametros: Any) -> tuple[Any, ...] | None:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchone()


def _todas(sql: str, *parametros: Any) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchall()


def _contar(tabla: str, grupo_id: uuid.UUID) -> int:
    fila = _una(f"SELECT count(*) FROM {tabla} WHERE grupo_id = %s", grupo_id)  # tabla fija, nunca de la petición
    assert fila is not None
    return int(fila[0])


def _nada_en(grupo_id: uuid.UUID) -> bool:
    return all(_contar(t, grupo_id) == 0 for t in ("persona_cuidada", "direccion", "consentimiento", "auditoria"))


def _app(entorno: EntornoPersonas) -> FastAPI:
    return cast(FastAPI, entorno.base.iam.cliente.app)


# --- Camino feliz --------------------------------------------------------------------------


@requiere_base
@pytest.mark.rf("RF-01")
def test_alta_titular_crea_persona_direccion_consentimiento_y_auditoria(entorno_personas: EntornoPersonas) -> None:
    # Dado un admin de su grupo
    a = entorno_personas.cuenta()
    grupo = entorno_personas.grupo_con_roles(a)

    # Cuando da de alta a la persona que declara en su presencia, con dirección
    respuesta = entorno_personas.crear(a.token, grupo, cuerpo_alta("titular", direccion=direccion_sintetica()))

    # Entonces responde 201
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    persona_id = uuid.UUID(cuerpo["id"])
    consentimiento_id = uuid.UUID(cuerpo["consentimiento"]["id"])

    # Y la persona queda en su grupo, con su dirección de entrega
    persona = _una(
        "SELECT grupo_id, nombre, nombre_pila, nivel_apoyo, direccion_entrega_id FROM persona_cuidada WHERE id = %s",
        persona_id,
    )
    assert persona is not None
    assert persona[:4] == (grupo, "Persona Ficticia Uno", "Uno", "apoyo_parcial")
    direccion = _una(
        "SELECT grupo_id, etiqueta, calle, numero, depto, comuna, region, referencia, lat, lng"
        " FROM direccion WHERE id = %s",
        persona[4],
    )
    assert direccion == (grupo, "Casa", "Calle Ficticia", "100", None, "Comuna Sintética", "Metropolitana",
                         None, None, None)

    # Y el consentimiento para plan_cuidado, con la versión del servidor y el instante del reloj
    consentimiento = _una(
        "SELECT grupo_id, persona_cuidada_id, usuario_id, calidad_otorgante, finalidad, version_politica,"
        " evidencia, referencia_documento, otorgado_en, revision_vence_en, revocado_en"
        " FROM consentimiento WHERE id = %s",
        consentimiento_id,
    )
    assert consentimiento == (
        grupo,
        persona_id,
        a.id,
        "titular",
        "plan_cuidado",
        POLITICA_PRUEBAS,
        {
            "esquema": 1,
            "declaracion": {"id": "declaracion_titular", "version": POLITICA_PRUEBAS},
            "modalidad": "registrada_por_usuario_en_presencia_del_titular",
        },
        None,
        OTORGADO_EN,
        None,
        None,
    )

    # Y una fila de auditoría con identificadores, sin nombre, sin IP y sin motivo
    auditoria = _todas(
        "SELECT actor_tipo, actor_ref, accion, entidad, entidad_id, motivo, ip, request_id, ocurrido_en"
        " FROM auditoria WHERE grupo_id = %s",
        grupo,
    )
    assert auditoria == [
        ("usuario", a.id, "consentimiento.otorgar", "consentimiento", consentimiento_id, None, None,
         respuesta.headers["x-request-id"], OTORGADO_EN)
    ]

    # Y no se crea la clave de datos: es de MATU-11
    assert _una("SELECT count(*) FROM clave_datos WHERE persona_cuidada_id = %s", persona_id) == (0,)


@requiere_base
@pytest.mark.rf("RF-01")
def test_alta_sin_direccion_deja_la_entrega_en_null(entorno_personas: EntornoPersonas) -> None:
    a = entorno_personas.cuenta()
    grupo = entorno_personas.grupo_con_roles(a)

    respuesta = entorno_personas.crear(a.token, grupo, cuerpo_alta())

    assert respuesta.status_code == 201
    assert respuesta.json()["direccion"] is None
    persona = _una("SELECT direccion_entrega_id FROM persona_cuidada WHERE id = %s", uuid.UUID(respuesta.json()["id"]))
    assert persona == (None,)
    assert _contar("direccion", grupo) == 0


@requiere_base
@pytest.mark.rf("RF-01")
def test_cuidador_de_hecho_fija_revision(entorno_personas: EntornoPersonas) -> None:
    # Dado un cuidador del grupo
    a = entorno_personas.cuenta()
    c = entorno_personas.cuenta()
    grupo = entorno_personas.grupo_con_roles(a, {c.id: "cuidador"})

    # Cuando da de alta como cuidador de hecho, con el aviso vigente mostrado
    respuesta = entorno_personas.crear(c.token, grupo, cuerpo_alta("cuidador_de_hecho"))

    # Entonces la revisión vence 12 meses después del otorgamiento
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["consentimiento"]["revision_vence_en"] == "2027-10-20T12:00:00Z"
    fila = _una(
        "SELECT calidad_otorgante, usuario_id, otorgado_en, revision_vence_en, evidencia, referencia_documento"
        " FROM consentimiento WHERE id = %s",
        uuid.UUID(cuerpo["consentimiento"]["id"]),
    )
    assert fila == (
        "cuidador_de_hecho",
        c.id,
        OTORGADO_EN,
        datetime(2027, 10, 20, 12, 0, tzinfo=UTC),
        {
            "esquema": 1,
            "declaracion": {"id": "declaracion_cuidador_de_hecho", "version": POLITICA_PRUEBAS},
            "aviso": {"id": "aviso_cuidador_de_hecho", "version": "1.0", "sha256": AVISO_CUIDADOR_DE_HECHO.sha256},
        },
        None,
    )
    # Y la respuesta incluye el texto del aviso de limitación
    assert cuerpo["aviso"]["titulo"] == AVISO_CUIDADOR_DE_HECHO.titulo
    assert cuerpo["aviso"]["parrafos"] == list(AVISO_CUIDADOR_DE_HECHO.parrafos)
    assert cuerpo["aviso"]["sha256"] == AVISO_CUIDADOR_DE_HECHO.sha256


@requiere_base
@pytest.mark.rf("RF-01")
def test_cuidador_de_hecho_el_29_de_febrero_revisa_el_28(entorno_personas: EntornoPersonas) -> None:
    # Dado un admin, y el reloj en un 29 de febrero. El mismo reloj valida el token, así que se
    # emite uno para ese día con la clave de las pruebas
    a = entorno_personas.cuenta()
    grupo = entorno_personas.grupo_con_roles(a)
    bisiesto = datetime(2028, 2, 29, 15, 0, tzinfo=UTC)
    _app(entorno_personas).dependency_overrides[obtener_reloj] = lambda: RelojFijo(bisiesto)
    token = EmisorJWT(entorno_personas.base.iam.clave_jwt).emitir(a.id, bisiesto, vencimiento(bisiesto))

    # Cuando da de alta como cuidador de hecho
    respuesta = entorno_personas.crear(token, grupo, cuerpo_alta("cuidador_de_hecho"))

    # Entonces la revisión cae el 28 de febrero del año siguiente, que no es bisiesto

    assert respuesta.status_code == 201
    fila = _una(
        "SELECT otorgado_en, revision_vence_en FROM consentimiento WHERE id = %s",
        uuid.UUID(respuesta.json()["consentimiento"]["id"]),
    )
    assert fila == (datetime(2028, 2, 29, 15, 0, tzinfo=UTC), datetime(2029, 2, 28, 15, 0, tzinfo=UTC))


@requiere_base
@pytest.mark.rf("RF-01")
def test_representante_guarda_solo_la_referencia(entorno_personas: EntornoPersonas) -> None:
    a = entorno_personas.cuenta()
    grupo = entorno_personas.grupo_con_roles(a)

    respuesta = entorno_personas.crear(a.token, grupo, cuerpo_alta("representante_legal"))

    assert respuesta.status_code == 201
    fila = _una(
        "SELECT calidad_otorgante, referencia_documento, revision_vence_en, evidencia"
        " FROM consentimiento WHERE id = %s",
        uuid.UUID(respuesta.json()["consentimiento"]["id"]),
    )
    assert fila == (
        "representante_legal",
        "Resolución sintética 123-2026",
        None,
        {"esquema": 1, "declaracion": {"id": "declaracion_representante_legal", "version": POLITICA_PRUEBAS}},
    )
    assert "Resolución sintética" not in respuesta.text


# --- Atomicidad ----------------------------------------------------------------------------


class RepositorioConConsentimientoInvalido(RepositorioPersonasSQL):
    """Escribe la dirección y la persona de verdad, y después un consentimiento que la base rechaza
    (calidad fuera del CHECK). La transacción completa debe deshacerse."""

    intentadas: list[uuid.UUID] = []

    def _insertar_persona(self, alta: AltaPersona) -> None:
        super()._insertar_persona(alta)
        type(self).intentadas.append(alta.persona_id)

    def _insertar_consentimiento(self, alta: AltaPersona) -> None:
        self._sesion.execute(
            text(
                "INSERT INTO consentimiento (grupo_id, persona_cuidada_id, usuario_id, calidad_otorgante, finalidad,"
                " version_politica, evidencia) VALUES (:g, :p, :u, 'hija', 'plan_cuidado', '0.9', '{}'::jsonb)"
            ),
            {"g": alta.grupo_id, "p": alta.persona_id, "u": alta.usuario_id},
        )


def _repositorio_que_falla(contexto: SesionDeGrupo) -> RepositorioPersonas:
    return RepositorioConConsentimientoInvalido(contexto.sesion, contexto.grupo_id)


@requiere_base
@pytest.mark.rf("RF-01")
def test_alta_con_consentimiento_atomica(entorno_personas: EntornoPersonas) -> None:
    # Dado un repositorio cuyo consentimiento falla después de escribir la dirección y la persona
    a = entorno_personas.cuenta()
    grupo = entorno_personas.grupo_con_roles(a)
    RepositorioConConsentimientoInvalido.intentadas = []
    _app(entorno_personas).dependency_overrides[obtener_repositorio_personas] = _repositorio_que_falla

    # Cuando el admin da de alta
    respuesta = entorno_personas.crear(a.token, grupo, cuerpo_alta(direccion=direccion_sintetica()))

    # Entonces la petición falla sin exponer el error de la base
    assert respuesta.status_code == 500
    assert respuesta.headers["content-type"].startswith(PROBLEMA)
    assert "hija" not in respuesta.text
    # Y el INSERT de la persona sí corrió, pero no quedó nada: ni persona, ni dirección, ni
    # consentimiento, ni auditoría
    [intentada] = RepositorioConConsentimientoInvalido.intentadas
    assert _una("SELECT 1 FROM persona_cuidada WHERE id = %s", intentada) is None
    assert _nada_en(grupo)

    # Y sin el defecto, la misma alta crea todo junto
    del _app(entorno_personas).dependency_overrides[obtener_repositorio_personas]
    assert entorno_personas.crear(a.token, grupo, cuerpo_alta(direccion=direccion_sintetica())).status_code == 201
    assert [_contar(t, grupo) for t in ("persona_cuidada", "direccion", "consentimiento", "auditoria")] == [1, 1, 1, 1]


# --- Roles ---------------------------------------------------------------------------------


@requiere_base
@pytest.mark.rf("RF-01")
@pytest.mark.parametrize("rol", ["observador", "pagador"])
def test_observador_no_da_de_alta(entorno_personas: EntornoPersonas, rol: str) -> None:
    # Dado un observador (o pagador) activo del grupo
    a = entorno_personas.cuenta()
    o = entorno_personas.cuenta()
    grupo = entorno_personas.grupo_con_roles(a, {o.id: rol})

    # Cuando intenta dar de alta, con un cuerpo válido
    respuesta = entorno_personas.crear(o.token, grupo, cuerpo_alta())

    # Entonces recibe 404, nunca 403, y no se crea nada
    assert respuesta.status_code == 404
    assert respuesta.headers["content-type"].startswith(PROBLEMA)
    assert respuesta.json()["type"] == "/errores/no-encontrado"
    assert _nada_en(grupo)


@requiere_base
@pytest.mark.rf("RF-01")
def test_cuidador_da_de_alta(entorno_personas: EntornoPersonas) -> None:
    a = entorno_personas.cuenta()
    c = entorno_personas.cuenta()
    grupo = entorno_personas.grupo_con_roles(a, {c.id: "cuidador"})

    respuesta = entorno_personas.crear(c.token, grupo, cuerpo_alta())

    assert respuesta.status_code == 201
    assert _una("SELECT usuario_id FROM consentimiento WHERE grupo_id = %s", grupo) == (c.id,)


# --- Aislamiento ---------------------------------------------------------------------------


@requiere_base
@pytest.mark.rf("RF-01")
def test_otro_grupo_no_ve_persona_404(entorno_personas: EntornoPersonas) -> None:
    # Dados A con una persona en su grupo, y B admin de otro grupo
    a = entorno_personas.cuenta()
    b = entorno_personas.cuenta()
    grupo_a = entorno_personas.grupo_con_roles(a)
    grupo_b = entorno_personas.grupo_con_roles(b)
    assert entorno_personas.crear(a.token, grupo_a, cuerpo_alta(nombre="Persona Ficticia de A")).status_code == 201

    # Cuando B pide la lista del grupo de A, con la cabecera de A o con la suya
    con_cabecera_ajena = entorno_personas.listar(b.token, grupo_a)
    con_su_cabecera = entorno_personas.listar(b.token, grupo_b, grupo_path=grupo_a)
    # o intenta crear en él
    crear_ajeno = entorno_personas.crear(b.token, grupo_b, cuerpo_alta(), grupo_path=grupo_a)

    # Entonces recibe 404, nunca 403, y no aparece la persona de A
    for respuesta in (con_cabecera_ajena, con_su_cabecera, crear_ajeno):
        assert respuesta.status_code == 404
        assert respuesta.headers["content-type"].startswith(PROBLEMA)
        assert "Persona Ficticia de A" not in respuesta.text
    # Y su propio grupo sigue vacío, sin la persona de A
    propia = entorno_personas.listar(b.token, grupo_b)
    assert propia.status_code == 200
    assert propia.json() == []
    assert [_contar("persona_cuidada", g) for g in (grupo_a, grupo_b)] == [1, 0]


@requiere_base
@pytest.mark.rf("RF-01")
def test_path_de_otro_grupo_propio_404(entorno_personas: EntornoPersonas) -> None:
    # Dado A, admin de dos grupos
    a = entorno_personas.cuenta()
    grupo_1 = entorno_personas.grupo_con_roles(a)
    grupo_2 = entorno_personas.grupo_con_roles(a)

    # Cuando el path dice un grupo y X-Grupo-Id el otro
    crear = entorno_personas.crear(a.token, grupo_2, cuerpo_alta(), grupo_path=grupo_1)
    listar = entorno_personas.listar(a.token, grupo_2, grupo_path=grupo_1)

    # Entonces 404, y no se crea nada en ninguno
    assert crear.status_code == 404
    assert listar.status_code == 404
    assert _nada_en(grupo_1)
    assert _nada_en(grupo_2)


# --- Lista por rol -------------------------------------------------------------------------


@requiere_base
@pytest.mark.rf("RF-01")
def test_lista_proyecta_por_rol(entorno_personas: EntornoPersonas) -> None:
    # Dado un grupo con los cuatro roles y una persona dada de alta por un cuidador de hecho
    a = entorno_personas.cuenta()
    c = entorno_personas.cuenta()
    p = entorno_personas.cuenta()
    o = entorno_personas.cuenta()
    grupo = entorno_personas.grupo_con_roles(a, {c.id: "cuidador", p.id: "pagador", o.id: "observador"})
    alta = entorno_personas.crear(a.token, grupo, cuerpo_alta("cuidador_de_hecho", direccion=direccion_sintetica()))
    assert alta.status_code == 201
    persona_id = alta.json()["id"]

    # Cuando cada uno lista
    listas = {rol: entorno_personas.listar(cuenta.token, grupo) for rol, cuenta in
              {"admin": a, "cuidador": c, "pagador": p, "observador": o}.items()}

    # Entonces admin y cuidador ven todo, con el consentimiento vigente y su revisión
    direccion = alta.json()["direccion"]
    completa = {
        "id": persona_id,
        "nombre": "Persona Ficticia Uno",
        "nombre_pila": "Uno",
        "nivel_apoyo": "apoyo_parcial",
        "direccion": direccion,
        "consentimiento": alta.json()["consentimiento"],
    }
    assert completa["consentimiento"]["revision_vence_en"] == "2027-10-20T12:00:00Z"
    for rol in ("admin", "cuidador"):
        assert listas[rol].status_code == 200
        assert listas[rol].json() == [completa]
    # El pagador, nombre y dirección
    assert listas["pagador"].json() == [{"id": persona_id, "nombre": "Persona Ficticia Uno", "direccion": direccion}]
    # El observador, solo el nombre
    assert listas["observador"].json() == [{"id": persona_id, "nombre": "Persona Ficticia Uno"}]
    for rol in ("pagador", "observador"):
        assert "nombre_pila" not in listas[rol].text
        assert "cuidador_de_hecho" not in listas[rol].text
        assert "apoyo_parcial" not in listas[rol].text


@requiere_base
@pytest.mark.rf("RF-01")
def test_lista_sin_consentimiento_vigente_lo_muestra_null(entorno_personas: EntornoPersonas) -> None:
    a = entorno_personas.cuenta()
    grupo = entorno_personas.grupo_con_roles(a)
    alta = entorno_personas.crear(a.token, grupo, cuerpo_alta())
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute("UPDATE consentimiento SET revocado_en = now() WHERE grupo_id = %s", (grupo,))

    lista = entorno_personas.listar(a.token, grupo)

    assert lista.status_code == 200
    [persona] = lista.json()
    assert persona["id"] == alta.json()["id"]
    assert set(persona) == CAMPOS_COMPLETOS
    assert persona["consentimiento"] is None


# --- Logs ----------------------------------------------------------------------------------


@requiere_base
@pytest.mark.rf("RF-01")
def test_logs_sin_datos_de_la_persona(entorno_personas: EntornoPersonas) -> None:
    a = entorno_personas.cuenta()
    grupo = entorno_personas.grupo_con_roles(a)
    cuerpo = cuerpo_alta(
        "representante_legal",
        nombre="Persona Inventada Zeta",
        nombre_pila="Zetita",
        referencia_documento="Escritura sintética 987",
        direccion=direccion_sintetica(calle="Pasaje Imaginario", comuna="Comuna Irreal", referencia="Portón verde"),
    )

    creada = entorno_personas.crear(a.token, grupo, cuerpo)
    lista = entorno_personas.listar(a.token, grupo)

    assert creada.status_code == 201
    assert lista.status_code == 200
    log = entorno_personas.base.iam.texto_log()
    for dato in ("Inventada", "Zetita", "Escritura sintética", "Pasaje Imaginario", "Comuna Irreal", "Portón verde"):
        assert dato not in log
    assert a.token not in log
    peticiones = [linea for linea in entorno_personas.base.iam.lineas_log() if linea["mensaje"] == "peticion"]
    assert [(p["metodo"], p["ruta"], p["usuario_id"], p["grupo_id"]) for p in peticiones[-2:]] == [
        ("POST", "/v1/grupos/{grupo_id}/personas-cuidadas", str(a.id), str(grupo)),
        ("GET", "/v1/grupos/{grupo_id}/personas-cuidadas", str(a.id), str(grupo)),
    ]


@requiere_base
@pytest.mark.rf("RF-01")
def test_lista_responde_en_utc_aunque_la_base_use_otra_zona(entorno_personas: EntornoPersonas) -> None:
    # Dada una alta, y una conexión cuya sesión de PostgreSQL usa la zona de Santiago
    a = entorno_personas.cuenta()
    grupo = entorno_personas.grupo_con_roles(a)
    assert entorno_personas.crear(a.token, grupo, cuerpo_alta("cuidador_de_hecho")).status_code == 201
    engine = create_engine(
        obtener_configuracion().database_url, connect_args={"options": "-c timezone=America/Santiago"}
    )
    fabrica = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    _app(entorno_personas).dependency_overrides[obtener_fabrica_sesiones] = lambda: fabrica
    try:
        # Cuando el admin lista
        lista = entorno_personas.listar(a.token, grupo)
    finally:
        engine.dispose()

    # Entonces los instantes salen en UTC, igual que en la respuesta del alta (arquitectura 9.1)
    assert lista.status_code == 200
    [persona] = lista.json()
    assert persona["consentimiento"]["otorgado_en"] == "2026-10-20T12:00:00Z"
    assert persona["consentimiento"]["revision_vence_en"] == "2027-10-20T12:00:00Z"
