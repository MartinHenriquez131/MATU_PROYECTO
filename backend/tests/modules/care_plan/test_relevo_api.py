"""MATU-18 · Compartir la ficha con un relevo, por la API y contra PostgreSQL (RF-05).

Corren como matu_app con la familia sintética de las fábricas. El pepper del PIN es aleatorio por
prueba (override de obtener_pepper_pin); nunca se usa el de un .env. Lo que quedó en la base se revisa
como superusuario. Contrato: docs/api/propuestos/relevo.openapi.yaml.

Solo datos sintéticos: Rosa reemplaza a la cuidadora y los teléfonos son de la serie 5555.
"""

import base64
import hashlib
import hmac
import re
import secrets
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import psycopg
import pytest
from fastapi import FastAPI

from app.modules.care_plan.api.dependencias import obtener_pepper_pin
from tests.base_datos import DSN, requiere_base
from tests.fabricas import FamiliaCreada, UsuarioCreado
from tests.modules.care_plan.conftest import EntornoFicha

pytestmark = [requiere_base, pytest.mark.rf("RF-05")]

PROBLEMA = "application/problem+json"
RUTA = "/v1/personas-cuidadas/{}/plan/accesos-relevo"
AHORA = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)  # el RelojFijo de las pruebas
URL = re.compile(r"^https://[^/#]+/r#([A-Za-z0-9_-]{43})$")
CLAVES_CREADO = {"id", "url", "pin", "campos", "expira_en", "nombre_relevo", "nombre_pila_persona"}


def _cuerpo(**cambios: Any) -> dict[str, Any]:
    cuerpo: dict[str, Any] = {
        "nombre_relevo": "Rosa",
        "telefono_relevo": "+56 9 5555 0137",
        "campos": ["rutina", "manejo_situaciones", "red_apoyo"],
        "motivo": "fin_de_semana_fuera",
    }
    cuerpo.update(cambios)
    return {k: v for k, v in cuerpo.items() if v is not None}


class EntornoRelevo:
    def __init__(self, ficha: EntornoFicha, pepper: bytes) -> None:
        self.ficha = ficha
        self.pepper = pepper

    def familia(self, **opciones: Any) -> FamiliaCreada:
        return self.ficha.familia(**opciones)

    def _cabeceras(self, usuario: UsuarioCreado | None, grupo: uuid.UUID | str | None) -> dict[str, str]:
        return self.ficha._cabeceras(usuario, grupo)

    def crear(self, usuario: UsuarioCreado | None, grupo: Any, persona: Any, cuerpo: Any) -> Any:
        return self.ficha.iam.cliente.post(RUTA.format(persona), json=cuerpo, headers=self._cabeceras(usuario, grupo))

    def listar(self, usuario: UsuarioCreado | None, grupo: Any, persona: Any, **query: Any) -> Any:
        return self.ficha.iam.cliente.get(RUTA.format(persona), params=query, headers=self._cabeceras(usuario, grupo))


@pytest.fixture
def entorno(entorno_ficha: EntornoFicha) -> Iterator[EntornoRelevo]:
    pepper = secrets.token_bytes(32)
    app = cast(FastAPI, entorno_ficha.iam.cliente.app)
    app.dependency_overrides[obtener_pepper_pin] = lambda: pepper
    yield EntornoRelevo(entorno_ficha, pepper)


def _una(sql: str, *parametros: Any) -> tuple[Any, ...] | None:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchone()


def _todas(sql: str, *parametros: Any) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchall()


def _token(url: str) -> str:
    coincide = URL.match(url)
    assert coincide, "el enlace no lleva el token en el fragmento"
    return coincide.group(1)


def _crudo(token: str) -> bytes:
    return base64.urlsafe_b64decode(token + "=")


# --- Las tres pruebas del backlog ------------------------------------------------------------------------


def test_acceso_guarda_solo_hash(entorno: EntornoRelevo) -> None:
    familia = entorno.familia()
    respuesta = entorno.crear(familia.admin, familia.grupo.id, familia.persona.id, _cuerpo())

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.headers["cache-control"] == "no-store"
    creado = respuesta.json()
    assert set(creado) == CLAVES_CREADO
    token, pin = _token(creado["url"]), creado["pin"]
    assert re.fullmatch(r"[0-9]{4}", pin)
    assert len(_crudo(token)) == 32  # 256 bits
    acceso_id = uuid.UUID(creado["id"])

    fila = _una(
        "SELECT token_hash, pin_hash, a::text FROM acceso_relevo a WHERE id = %s", acceso_id
    )
    assert fila is not None
    token_hash, pin_hash, fila_texto = fila
    assert bytes(token_hash) == hashlib.sha256(_crudo(token)).digest()
    esperado = hmac.new(entorno.pepper, f"{acceso_id}:{pin}".encode(), hashlib.sha256).hexdigest()
    assert pin_hash == esperado
    assert token not in fila_texto
    assert pin != pin_hash

    indice = _una(
        "SELECT token_hash, tipo, grupo_id, referencia_id, expira_en, i::text FROM indice_token i"
        " WHERE referencia_id = %s",
        acceso_id,
    )
    assert indice is not None
    assert bytes(indice[0]) == bytes(token_hash)
    assert indice[1:5] == ("relevo", familia.grupo.id, acceso_id, AHORA + timedelta(hours=24))
    assert token not in indice[5]

    auditoria = _todas(
        "SELECT actor_tipo, actor_ref, motivo, ip, a::text FROM auditoria a"
        " WHERE accion = 'relevo.compartir' AND entidad_id = %s",
        acceso_id,
    )
    assert len(auditoria) == 1
    assert auditoria[0][:4] == ("usuario", familia.admin.id, "fin_de_semana_fuera", None)
    assert token not in auditoria[0][4] and "Rosa" not in auditoria[0][4] and "5555" not in auditoria[0][4]

    # Ni el token ni el PIN en los logs, ni en las cabeceras, ni en la lista
    log = entorno.ficha.iam.texto_log()
    assert token not in log and creado["url"] not in log
    assert f'"{pin}"' not in log and f"pin={pin}" not in log
    assert token not in str(respuesta.headers)
    lista = entorno.listar(familia.admin, familia.grupo.id, familia.persona.id).text
    assert token not in lista and "pin" not in lista


def test_vigencia_maxima_30_dias(entorno: EntornoRelevo) -> None:
    familia = entorno.familia()
    grupo, persona = familia.grupo.id, familia.persona.id

    justo = entorno.crear(familia.admin, grupo, persona, _cuerpo(expira_en=(AHORA + timedelta(days=30)).isoformat()))
    assert justo.status_code == 201, justo.text
    assert datetime.fromisoformat(justo.json()["expira_en"]) == AHORA + timedelta(days=30)

    casos = {
        "vigencia_maxima": AHORA + timedelta(days=30, seconds=1),
        "vigencia_pasada": AHORA - timedelta(minutes=1),
    }
    for tipo, instante in casos.items():
        respuesta = entorno.crear(familia.admin, grupo, persona, _cuerpo(expira_en=instante.isoformat()))
        assert respuesta.status_code == 422
        assert respuesta.headers["content-type"] == PROBLEMA
        assert respuesta.json()["errores"] == [
            {"campo": "expira_en", "mensaje": respuesta.json()["errores"][0]["mensaje"], "tipo": tipo}
        ]
    # Sin zona horaria tampoco
    sin_zona = entorno.crear(familia.admin, grupo, persona, _cuerpo(expira_en="2026-10-21T12:00:00"))
    assert sin_zona.status_code == 422
    assert _una("SELECT count(*) FROM acceso_relevo WHERE grupo_id = %s", grupo) == (1,)


def test_acceso_con_ficha_incompleta(entorno: EntornoRelevo) -> None:
    # Sin plan: nadie escribió la ficha. El acceso se crea y el plan nace vacío, sin clave de datos
    vacia = entorno.familia()
    respuesta = entorno.crear(vacia.admin, vacia.grupo.id, vacia.persona.id, _cuerpo(campos=["red_apoyo"]))
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["campos"] == ["red_apoyo"]
    assert _una(
        "SELECT modo, completitud_pct FROM plan_cuidado WHERE persona_cuidada_id = %s", vacia.persona.id
    ) == ("ficha_relevo", 0)
    assert _una("SELECT count(*) FROM clave_datos WHERE persona_cuidada_id = %s", vacia.persona.id) == (0,)

    # Con un solo campo escrito: el acceso usa el plan existente
    incompleta = entorno.familia()
    escrito = entorno.ficha.escribir(
        incompleta.admin, incompleta.grupo.id, incompleta.persona.id, "rutina", {"texto": "08:00 Desayuno"}
    )
    assert escrito.status_code == 201
    respuesta = entorno.crear(incompleta.admin, incompleta.grupo.id, incompleta.persona.id, _cuerpo())
    assert respuesta.status_code == 201
    assert _una(
        "SELECT count(*) FROM acceso_relevo a JOIN plan_cuidado p ON p.id = a.plan_id"
        " WHERE p.persona_cuidada_id = %s",
        incompleta.persona.id,
    ) == (1,)


# --- Lo que guarda el acceso ----------------------------------------------------------------------------


def test_acceso_guarda_los_nombres_de_pila_y_el_telefono_normalizado(entorno: EntornoRelevo) -> None:
    familia = entorno.familia()
    cuidador = familia.miembros["cuidador"].usuario
    respuesta = entorno.crear(
        cuidador, familia.grupo.id, familia.persona.id,
        _cuerpo(nombre_relevo="  Rosa  ", campos=["red_apoyo", "rutina"], motivo="otro"),
    )
    assert respuesta.status_code == 201, respuesta.text
    creado = respuesta.json()
    assert creado["nombre_relevo"] == "Rosa"
    assert creado["nombre_pila_persona"] == familia.persona.nombre_pila
    assert creado["campos"] == ["rutina", "red_apoyo"]  # en el orden de la ficha
    fila = _una(
        "SELECT otorgado_por, otorgado_a_nombre, otorgado_a_telefono, nombre_pila_persona, nombre_pila_comparte,"
        " secciones_permitidas, motivo FROM acceso_relevo WHERE id = %s",
        uuid.UUID(creado["id"]),
    )
    assert fila == (
        cuidador.id, "Rosa", "+56955550137", familia.persona.nombre_pila, cuidador.nombre.split()[0],
        ["rutina", "red_apoyo"], "otro",
    )


@pytest.mark.parametrize(
    ("cambios", "campo"),
    [
        ({"motivo": "me voy al doctor"}, "motivo"),
        ({"telefono_relevo": "+56 2 5555 0137"}, "telefono_relevo"),
        ({"campos": ["rutina", "rutina"]}, "campos"),
        ({"campos": []}, "campos"),
        ({"campos": ["alimentacion"]}, "campos"),
        ({"nombre_relevo": "   "}, "nombre_relevo"),
        ({"nombre_relevo": "R" * 61}, "nombre_relevo"),
        ({"nombre_relevo": "Rosa\nSoto"}, "nombre_relevo"),
        ({"pin": "1234"}, "pin"),
    ],
)
def test_cuerpo_invalido_422_sin_repetir_el_valor(entorno: EntornoRelevo, cambios: dict[str, Any], campo: str) -> None:
    familia = entorno.familia()
    respuesta = entorno.crear(familia.admin, familia.grupo.id, familia.persona.id, _cuerpo(**cambios))
    assert respuesta.status_code == 422
    errores = respuesta.json()["errores"]
    assert any(e["campo"].startswith(campo) for e in errores), errores
    for valor in cambios.values():
        if isinstance(valor, str) and valor.strip():
            assert valor not in respuesta.text
    assert _una("SELECT count(*) FROM acceso_relevo WHERE grupo_id = %s", familia.grupo.id) == (0,)


def test_falta_un_campo_obligatorio_422(entorno: EntornoRelevo) -> None:
    familia = entorno.familia()
    for falta in ("nombre_relevo", "telefono_relevo", "campos", "motivo"):
        cuerpo = _cuerpo()
        del cuerpo[falta]
        respuesta = entorno.crear(familia.admin, familia.grupo.id, familia.persona.id, cuerpo)
        assert respuesta.status_code == 422, falta


# --- Quién comparte -------------------------------------------------------------------------------------


@pytest.mark.parametrize("etiqueta", ["pagador", "pagador_con_plan", "observador"])
def test_otros_roles_no_comparten_404(entorno: EntornoRelevo, etiqueta: str) -> None:
    familia = entorno.familia()
    usuario = familia.miembros[etiqueta].usuario
    respuesta = entorno.crear(usuario, familia.grupo.id, familia.persona.id, _cuerpo())
    assert respuesta.status_code == 404
    assert respuesta.json()["type"] == "/errores/no-encontrado"
    # El rol se revisa antes que el cuerpo: también 404 con un cuerpo inválido
    assert entorno.crear(usuario, familia.grupo.id, familia.persona.id, {}).status_code == 404


def test_persona_de_otro_grupo_404(entorno: EntornoRelevo) -> None:
    a, b = entorno.familia(), entorno.familia()
    for respuesta in (
        entorno.crear(a.admin, a.grupo.id, b.persona.id, _cuerpo()),
        entorno.crear(a.admin, b.grupo.id, b.persona.id, _cuerpo()),
        entorno.crear(a.admin, a.grupo.id, "no-es-uuid", _cuerpo()),
        entorno.crear(a.admin, None, a.persona.id, _cuerpo()),
        entorno.listar(a.admin, a.grupo.id, b.persona.id),
    ):
        assert respuesta.status_code == 404
    assert _una("SELECT count(*) FROM acceso_relevo WHERE grupo_id = %s", b.grupo.id) == (0,)


def test_sin_token_401(entorno: EntornoRelevo) -> None:
    familia = entorno.familia()
    assert entorno.crear(None, familia.grupo.id, familia.persona.id, _cuerpo()).status_code == 401
    assert entorno.listar(None, familia.grupo.id, familia.persona.id).status_code == 401


def test_sin_consentimiento_403_y_la_lista_sigue_permitida(entorno: EntornoRelevo) -> None:
    familia = entorno.familia(con_consentimiento=False)
    respuesta = entorno.crear(familia.admin, familia.grupo.id, familia.persona.id, {"motivo": "texto libre"})
    assert respuesta.status_code == 403
    assert respuesta.json()["type"] == "/errores/sin-consentimiento"
    assert _una("SELECT count(*) FROM plan_cuidado WHERE persona_cuidada_id = %s", familia.persona.id) == (0,)
    lista = entorno.listar(familia.admin, familia.grupo.id, familia.persona.id)
    assert lista.status_code == 200
    assert lista.json() == {"items": [], "siguiente_cursor": None}


def test_revision_vencida_403_al_compartir(entorno: EntornoRelevo) -> None:
    fabrica = entorno.ficha.fabrica
    admin = fabrica.usuario()
    grupo = fabrica.grupo(admin=admin)
    persona = fabrica.persona_cuidada(grupo, calidad="cuidador_de_hecho", otorgado_en=AHORA - timedelta(days=366))

    respuesta = entorno.crear(admin, grupo.id, persona.id, _cuerpo())
    assert respuesta.status_code == 403
    assert respuesta.headers["content-type"] == PROBLEMA
    assert respuesta.json()["type"] == "/errores/revision-vencida"
    assert entorno.listar(admin, grupo.id, persona.id).status_code == 200


def test_sin_pepper_503_y_falla_cerrado(entorno: EntornoRelevo) -> None:
    familia = entorno.familia()
    app = cast(FastAPI, entorno.ficha.iam.cliente.app)
    app.dependency_overrides[obtener_pepper_pin] = lambda: None
    respuesta = entorno.crear(familia.admin, familia.grupo.id, familia.persona.id, _cuerpo())
    assert respuesta.status_code == 503
    assert _una("SELECT count(*) FROM acceso_relevo WHERE grupo_id = %s", familia.grupo.id) == (0,)


# --- La lista -------------------------------------------------------------------------------------------


def test_lista_con_estado_telefono_por_rol_y_cursor(entorno: EntornoRelevo) -> None:
    familia = entorno.familia()
    grupo, persona = familia.grupo.id, familia.persona.id
    ids = []
    for motivo in ("salgo_unas_horas", "turno_de_noche", "otro"):
        respuesta = entorno.crear(familia.admin, grupo, persona, _cuerpo(motivo=motivo))
        assert respuesta.status_code == 201
        ids.append(respuesta.json()["id"])
    with psycopg.connect(DSN, autocommit=True) as cx:
        # Mismo creado_en (RelojFijo): el orden lo desempata el id. Se fijan estados a mano
        cx.execute("UPDATE acceso_relevo SET revocado_en = %s WHERE id = %s", (AHORA, ids[0]))
        cx.execute("UPDATE acceso_relevo SET pin_intentos_fallidos = 5 WHERE id = %s", (ids[1],))

    lista = entorno.listar(familia.admin, grupo, persona)
    assert lista.status_code == 200
    assert lista.headers["cache-control"] == "no-store"
    items = lista.json()["items"]
    assert [i["id"] for i in items] == sorted(ids, reverse=True)
    estados = {i["id"]: i["estado"] for i in items}
    assert estados == {ids[0]: "revocado", ids[1]: "bloqueado", ids[2]: "vigente"}
    primero = items[0]
    assert primero["telefono_relevo"] == "+56955550137"
    assert primero["otorgado_por"] == {"id": str(familia.admin.id), "nombre": familia.admin.nombre}
    assert primero["usos"] == 0 and primero["ultimo_uso_en"] is None

    # El pagador con permiso ve la lista sin la propiedad telefono_relevo
    pagador = familia.miembros["pagador_con_plan"].usuario
    del_pagador = entorno.listar(pagador, grupo, persona).json()["items"]
    assert len(del_pagador) == 3 and all("telefono_relevo" not in i for i in del_pagador)
    for etiqueta in ("pagador", "observador"):
        assert entorno.listar(familia.miembros[etiqueta].usuario, grupo, persona).status_code == 404

    # Filtro y paginación
    vigentes = entorno.listar(familia.admin, grupo, persona, estado="vigente").json()["items"]
    assert [i["id"] for i in vigentes] == [ids[2]]
    pagina = entorno.listar(familia.admin, grupo, persona, limite=2).json()
    assert len(pagina["items"]) == 2 and pagina["siguiente_cursor"]
    resto = entorno.listar(familia.admin, grupo, persona, limite=2, cursor=pagina["siguiente_cursor"]).json()
    assert [i["id"] for i in pagina["items"] + resto["items"]] == [i["id"] for i in items]
    assert resto["siguiente_cursor"] is None

    for query in ({"cursor": "no-es-un-cursor"}, {"limite": 0}, {"limite": 101}, {"estado": "otro"}):
        assert entorno.listar(familia.admin, grupo, persona, **query).status_code == 422, query


def test_lista_marca_vencido_con_el_reloj(entorno: EntornoRelevo) -> None:
    familia = entorno.familia()
    respuesta = entorno.crear(
        familia.admin, familia.grupo.id, familia.persona.id,
        _cuerpo(expira_en=(AHORA + timedelta(hours=1)).isoformat()),
    )
    assert respuesta.status_code == 201
    entorno.ficha.iam.reloj.avanzar(timedelta(hours=1))
    entorno.ficha.tokens.clear()  # el access token dura 15 minutos: se vuelve a iniciar sesión
    items = entorno.listar(familia.admin, familia.grupo.id, familia.persona.id).json()["items"]
    assert [i["estado"] for i in items] == ["vencido"]
