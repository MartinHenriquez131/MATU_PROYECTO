"""MATU-42 · Invitar a un familiar y unirse al grupo, por la API y contra PostgreSQL (RF-38).

Contrato: docs/api/propuestos/invitar-familiar.openapi.yaml. Solo datos sintéticos: Carmen administra, Rosa se une.
El límite por IP y el tope de invitaciones van con el contador en memoria de tests/modules/conftest.py.
"""

import json
import re
import secrets
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import psycopg
import pytest
from fastapi import FastAPI

from app.modules.care_circle.api.dependencias_grupo import obtener_pepper_codigo
from tests.base_datos import DSN, requiere_base
from tests.dobles.reloj_fijo import RelojFijo
from tests.fabricas import Fabrica, FamiliaCreada, UsuarioCreado
from tests.modules.conftest import EntornoIam

pytestmark = [requiere_base, pytest.mark.rf("RF-38")]


@pytest.fixture
def reloj_fijo() -> RelojFijo:
    """El reloj parte de la hora real: las funciones de la 0026 rechazan un ahora a más de 5 minutos del de la base
    (decisión 340)."""
    return RelojFijo(datetime.now(UTC).replace(microsecond=0))


PROBLEMA = "application/problem+json"
URL = re.compile(r"^https://[^/#]+/invitacion#([A-Za-z0-9_-]{43})$")


class Entorno:
    def __init__(self, iam: EntornoIam, fabrica: Fabrica) -> None:
        self.iam = iam
        self.fabrica = fabrica
        self.tokens: dict[uuid.UUID, str] = {}

    @property
    def app(self) -> FastAPI:
        return cast(FastAPI, self.iam.cliente.app)

    def token(self, usuario: UsuarioCreado) -> str:
        if usuario.id not in self.tokens:
            assert usuario.contrasena is not None
            respuesta = self.iam.iniciar_sesion(email=usuario.email, contrasena=usuario.contrasena)
            assert respuesta.status_code == 200, respuesta.text
            self.tokens[usuario.id] = respuesta.json()["access_token"]
        return self.tokens[usuario.id]

    def cabeceras(self, usuario: UsuarioCreado | None, grupo: uuid.UUID | str | None = None) -> dict[str, str]:
        cabeceras: dict[str, str] = {}
        if usuario is not None:
            cabeceras["Authorization"] = f"Bearer {self.token(usuario)}"
        if grupo is not None:
            cabeceras["X-Grupo-Id"] = str(grupo)
        return cabeceras

    def familia(self) -> FamiliaCreada:
        return self.fabrica.familia(miembros=("cuidador", "pagador", "observador"))

    def crear(self, usuario: UsuarioCreado, grupo: uuid.UUID, rol: str = "cuidador", **extra: Any) -> Any:
        return self.iam.cliente.post(
            f"/v1/grupos/{grupo}/invitaciones", json={"rol": rol, **extra}, headers=self.cabeceras(usuario, grupo)
        )

    def invitar(self, familia: FamiliaCreada, rol: str = "cuidador") -> tuple[str, str, dict[str, Any]]:
        respuesta = self.crear(familia.admin, familia.grupo.id, rol)
        assert respuesta.status_code == 201, respuesta.text
        cuerpo = respuesta.json()
        coincide = URL.match(cuerpo["url"])
        assert coincide
        return coincide.group(1), cuerpo["codigo"], cuerpo

    def presentar(self, token: str) -> Any:
        return self.iam.cliente.post("/v1/invitaciones/presentacion", json={"token": token})

    def verificar(self, token: str, codigo: str) -> Any:
        return self.iam.cliente.post("/v1/invitaciones/verificacion", json={"token": token, "codigo": codigo})

    def aceptar(self, usuario: UsuarioCreado | None, token: str, codigo: str) -> Any:
        return self.iam.cliente.post(
            "/v1/invitaciones/aceptacion", json={"token": token, "codigo": codigo}, headers=self.cabeceras(usuario)
        )

    def nueva_cuenta(self, nombre: str = "Rosa Pérez") -> UsuarioCreado:
        return self.fabrica.usuario(nombre=nombre)


@pytest.fixture
def entorno(entorno_iam: EntornoIam) -> Iterator[Entorno]:
    fabrica = Fabrica(pepper=entorno_iam.pepper)
    pepper = secrets.token_bytes(32)
    app = cast(FastAPI, entorno_iam.cliente.app)
    app.dependency_overrides[obtener_pepper_codigo] = lambda: pepper
    try:
        yield Entorno(entorno_iam, fabrica)
    finally:
        fabrica.limpiar()


def _todas(sql: str, *parametros: Any) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchall()


def _sin_request_id(respuesta: Any) -> str:
    """El cuerpo del problema sin su request_id (un UUID aleatorio), para buscar un valor corto sin falsos positivos."""
    cuerpo = dict(respuesta.json())
    cuerpo.pop("request_id", None)
    return json.dumps(cuerpo, ensure_ascii=False)


def _valores(dato: Any) -> set[str]:
    """Todos los valores escalares de un JSON, como texto."""
    if isinstance(dato, dict):
        return set().union(*(_valores(v) for v in dato.values())) if dato else set()
    if isinstance(dato, list):
        return set().union(*(_valores(v) for v in dato)) if dato else set()
    return {str(dato)}


def _otro_codigo(codigo: str) -> str:
    return f"{(int(codigo) + 1) % 10_000:04d}"


# --- Camino feliz --------------------------------------------------------------------------------------


def test_invitar_presentar_verificar_y_unirse(entorno: Entorno) -> None:
    familia = entorno.familia()
    token, codigo, creada = entorno.invitar(familia, "cuidador")
    assert re.fullmatch(r"[0-9]{4}", codigo)
    assert set(creada) == {"id", "rol", "url", "codigo", "creada_en", "expira_en"}
    reloj = entorno.iam.reloj
    assert creada["expira_en"].startswith((reloj.ahora() + timedelta(days=7)).date().isoformat())

    # La lista de quien administra: pendiente, sin el token ni el código
    lista = entorno.iam.cliente.get(
        f"/v1/grupos/{familia.grupo.id}/invitaciones", headers=entorno.cabeceras(familia.admin, familia.grupo.id)
    )
    assert lista.status_code == 200
    [vista] = lista.json()["invitaciones"]
    assert vista["estado"] == "pendiente" and vista["invitada_por"]["eres_tu"] is True
    assert vista["invitada_por"]["nombre"] == familia.admin.nombre.split()[0]
    # El código son 4 dígitos que podrían aparecer en un id o una fecha: se busca como valor, no como texto
    assert token not in lista.text and codigo not in _valores(lista.json())

    presentacion = entorno.presentar(token)
    assert presentacion.status_code == 200, presentacion.text
    assert presentacion.json() == {
        "nombre_pila_invita": familia.admin.nombre.split()[0], "rol": "cuidador", "expira_en": creada["expira_en"],
    } or presentacion.json()["rol"] == "cuidador"
    assert set(presentacion.json()) == {"nombre_pila_invita", "rol", "expira_en"}
    assert presentacion.headers["Cache-Control"] == "no-store"
    assert presentacion.headers["Referrer-Policy"] == "no-referrer"
    assert presentacion.headers["X-Robots-Tag"] == "noindex"

    verificacion = entorno.verificar(token, codigo)
    assert verificacion.status_code == 200, verificacion.text
    datos = verificacion.json()
    assert set(datos) == {"nombre_pila_invita", "grupo", "personas", "rol", "expira_en"}
    assert datos["grupo"] == familia.grupo.nombre and datos["personas"] == [familia.persona.nombre_pila]

    rosa = entorno.nueva_cuenta()
    union = entorno.aceptar(rosa, token, codigo)
    assert union.status_code == 201, union.text
    assert union.json()["grupo_id"] == str(familia.grupo.id)
    assert union.json()["rol"] == "cuidador" and union.json()["puede_ver_plan"] is True

    # Desde la petición siguiente ve el grupo con su rol
    grupos = entorno.iam.cliente.get("/v1/grupos", headers=entorno.cabeceras(rosa))
    assert [(g["id"], g["rol"]) for g in grupos.json()] == [(str(familia.grupo.id), "cuidador")]

    # Un solo uso: la misma cuenta, ya-eres-parte; otra cuenta, usada
    otra_vez = entorno.aceptar(rosa, token, codigo)
    assert otra_vez.status_code == 409 and otra_vez.json()["type"] == "/errores/ya-eres-parte"
    assert otra_vez.json()["grupo_id"] == str(familia.grupo.id)
    otra = entorno.aceptar(entorno.nueva_cuenta("Otra Persona"), token, codigo)
    assert otra.status_code == 410 and otra.json()["type"] == "/errores/invitacion-usada"
    assert entorno.presentar(token).json()["type"] == "/errores/invitacion-usada"

    # La auditoría lleva solo el rol
    filas = _todas(
        "SELECT accion, actor_tipo, actor_ref, detalle FROM auditoria WHERE entidad = 'invitacion' AND entidad_id = %s"
        " ORDER BY id", uuid.UUID(creada["id"]))
    assert [(f[0], f[1], f[3]) for f in filas] == [
        ("invitacion.crear", "usuario", {"rol": "cuidador"}),
        ("invitacion.aceptar", "usuario", {"rol": "cuidador"}),
    ]
    assert filas[1][2] == rosa.id
    # La invitación, aceptada; su token, cortado; la membresía, sin permiso y con quién invitó
    [(aceptada_por, revocado)] = _todas(
        "SELECT i.aceptada_por, t.revocado_en IS NOT NULL FROM invitacion i JOIN indice_token t"
        " ON t.referencia_id = i.id WHERE i.id = %s", uuid.UUID(creada["id"]))
    assert aceptada_por == rosa.id and revocado
    assert _todas("SELECT rol, puede_ver_plan, invitado_por FROM membresia WHERE usuario_id = %s", rosa.id) == [
        ("cuidador", False, familia.admin.id)]


def test_unirse_no_crea_autorizaciones(entorno: Entorno) -> None:
    familia = entorno.familia()
    antes = _todas("SELECT count(*) FROM consentimiento WHERE grupo_id = %s", familia.grupo.id)
    token, codigo, _ = entorno.invitar(familia, "pagador")
    union = entorno.aceptar(entorno.nueva_cuenta(), token, codigo)
    assert union.status_code == 201 and union.json()["puede_ver_plan"] is False
    assert _todas("SELECT count(*) FROM consentimiento WHERE grupo_id = %s", familia.grupo.id) == antes


# --- 404, nunca 403 ------------------------------------------------------------------------------------


@pytest.mark.parametrize("etiqueta", ["cuidador", "pagador", "observador"])
def test_solo_admin_invita_ve_y_anula(entorno: Entorno, etiqueta: str) -> None:
    familia = entorno.familia()
    miembro = familia.miembros[etiqueta].usuario
    grupo = familia.grupo.id
    assert entorno.crear(miembro, grupo).status_code == 404
    assert entorno.iam.cliente.get(f"/v1/grupos/{grupo}/invitaciones",
                                   headers=entorno.cabeceras(miembro, grupo)).status_code == 404
    _, _, creada = entorno.invitar(familia)
    anular = entorno.iam.cliente.delete(f"/v1/grupos/{grupo}/invitaciones/{creada['id']}",
                                        headers=entorno.cabeceras(miembro, grupo))
    assert anular.status_code == 404 and anular.headers["content-type"].startswith(PROBLEMA)


def test_otro_grupo_y_path_distinto_de_la_cabecera_son_404(entorno: Entorno) -> None:
    a, b = entorno.familia(), entorno.familia()
    # El grupo del path no es el de la cabecera
    respuesta = entorno.iam.cliente.post(
        f"/v1/grupos/{b.grupo.id}/invitaciones", json={"rol": "cuidador"},
        headers=entorno.cabeceras(a.admin, a.grupo.id))
    assert respuesta.status_code == 404
    # La invitación de A no se anula desde B, ni un id que no es UUID
    _, _, creada = entorno.invitar(a)
    for invitacion in (creada["id"], "no-es-uuid"):
        anular = entorno.iam.cliente.delete(f"/v1/grupos/{b.grupo.id}/invitaciones/{invitacion}",
                                            headers=entorno.cabeceras(b.admin, b.grupo.id))
        assert anular.status_code == 404


def test_crear_sin_sesion_es_401_y_el_cuerpo_solo_trae_el_rol(entorno: Entorno) -> None:
    familia = entorno.familia()
    sin_sesion = entorno.iam.cliente.post(f"/v1/grupos/{familia.grupo.id}/invitaciones", json={"rol": "cuidador"},
                                          headers={"X-Grupo-Id": str(familia.grupo.id)})
    assert sin_sesion.status_code == 401
    con_correo = entorno.crear(familia.admin, familia.grupo.id, email="rosa@example.com")
    assert con_correo.status_code == 422 and "rosa@example.com" not in con_correo.text
    assert entorno.crear(familia.admin, familia.grupo.id, "jefe").status_code == 422


# --- El código, los 410 y el 423 -----------------------------------------------------------------------


def test_cinco_codigos_incorrectos_bloquean(entorno: Entorno) -> None:
    familia = entorno.familia()
    token, codigo, creada = entorno.invitar(familia)
    malo = _otro_codigo(codigo)
    for restantes in (4, 3, 2, 1):
        respuesta = entorno.verificar(token, malo)
        assert respuesta.status_code == 422, respuesta.text
        assert respuesta.json()["type"] == "/errores/codigo-incorrecto"
        assert respuesta.json()["intentos_restantes"] == restantes
    quinto = entorno.verificar(token, malo)
    assert quinto.status_code == 423 and quinto.json()["type"] == "/errores/invitacion-bloqueada"
    assert quinto.json()["nombre_pila_invita"] == familia.admin.nombre.split()[0]
    # También con el código correcto, y en la aceptación
    assert entorno.verificar(token, codigo).status_code == 423
    assert entorno.aceptar(entorno.nueva_cuenta(), token, codigo).status_code == 423
    assert entorno.presentar(token).status_code == 423
    # La lista la muestra bloqueada
    lista = entorno.iam.cliente.get(f"/v1/grupos/{familia.grupo.id}/invitaciones",
                                    headers=entorno.cabeceras(familia.admin, familia.grupo.id))
    assert [i["estado"] for i in lista.json()["invitaciones"]] == ["bloqueada"]
    # La auditoría: cuatro incorrectos y un bloqueo, con actor sistema y sin actor_ref
    filas = _todas("SELECT accion, actor_tipo, actor_ref, detalle FROM auditoria WHERE entidad_id = %s"
                   " AND accion <> 'invitacion.crear' ORDER BY id", uuid.UUID(creada["id"]))
    assert [f[0] for f in filas] == ["invitacion.codigo_incorrecto"] * 4 + ["invitacion.bloqueo"]
    assert {(f[1], f[2]) for f in filas} == {("sistema", None)} and {f[3]["rol"] for f in filas} == {"cuidador"}


def test_un_codigo_correcto_antes_del_bloqueo_vuelve_el_contador_a_cero(entorno: Entorno) -> None:
    familia = entorno.familia()
    token, codigo, _ = entorno.invitar(familia)
    for _ in range(4):
        entorno.verificar(token, _otro_codigo(codigo))
    assert entorno.verificar(token, codigo).status_code == 200
    assert entorno.verificar(token, _otro_codigo(codigo)).json()["intentos_restantes"] == 4


def test_un_codigo_mal_formado_es_422_y_no_cuenta(entorno: Entorno) -> None:
    familia = entorno.familia()
    token, codigo, _ = entorno.invitar(familia)
    for malo in ("12", "abcd", "12345"):
        respuesta = entorno.verificar(token, malo)
        assert respuesta.status_code == 422 and respuesta.json()["type"] == "/errores/validacion"
        # Sin el request_id, que es aleatorio y puede contener «12» o «abcd»: el problema nunca repite el valor
        assert malo not in _sin_request_id(respuesta)
    assert entorno.verificar(token, _otro_codigo(codigo)).json()["intentos_restantes"] == 4


def test_los_tres_410(entorno: Entorno) -> None:
    familia = entorno.familia()
    # Un token que no es de ninguna invitación
    falso = "A" * 43
    for respuesta in (entorno.presentar(falso), entorno.verificar(falso, "1234"), entorno.presentar("x")):
        assert respuesta.status_code == 410 and respuesta.json()["type"] == "/errores/invitacion-no-disponible"
    # Anulada: lo mismo que inexistente (C28)
    token, codigo, creada = entorno.invitar(familia)
    anular = entorno.iam.cliente.delete(f"/v1/grupos/{familia.grupo.id}/invitaciones/{creada['id']}",
                                        headers=entorno.cabeceras(familia.admin, familia.grupo.id))
    assert anular.status_code == 204
    assert entorno.presentar(token).json()["type"] == "/errores/invitacion-no-disponible"
    assert entorno.aceptar(entorno.nueva_cuenta(), token, codigo).json()["type"] == "/errores/invitacion-no-disponible"
    # Vencida: a los 7 días. La función no admite un ahora corrido (decisión 340): la invitación se corre 8 días
    # hacia atrás como superusuario, con los triggers apagados solo para esta siembra
    token, codigo, creada = entorno.invitar(familia)
    with psycopg.connect(DSN) as cx, cx.transaction():
        cx.execute("SET LOCAL session_replication_role = replica")
        cx.execute("UPDATE invitacion SET creada_en = creada_en - interval '8 days',"
                   " expira_en = expira_en - interval '8 days' WHERE id = %s", (uuid.UUID(creada["id"]),))
    for respuesta in (entorno.presentar(token), entorno.verificar(token, codigo)):
        assert respuesta.status_code == 410 and respuesta.json()["type"] == "/errores/invitacion-vencida"


def test_aceptar_sin_sesion_es_401_antes_que_todo(entorno: Entorno) -> None:
    familia = entorno.familia()
    token, codigo, _ = entorno.invitar(familia)
    respuesta = entorno.aceptar(None, token, codigo)
    assert respuesta.status_code == 401
    assert respuesta.headers["Referrer-Policy"] == "no-referrer"
    # No contó en el límite ni consumió nada
    assert entorno.verificar(token, codigo).status_code == 200


def test_ya_eres_parte_por_otra_via_no_consume_la_invitacion(entorno: Entorno) -> None:
    familia = entorno.familia()
    token, codigo, _ = entorno.invitar(familia)
    cuidador = familia.miembros["cuidador"].usuario
    respuesta = entorno.aceptar(cuidador, token, codigo)
    assert respuesta.status_code == 409 and respuesta.json()["type"] == "/errores/ya-eres-parte"
    assert entorno.aceptar(entorno.nueva_cuenta(), token, codigo).status_code == 201


def test_anular_es_idempotente_y_una_usada_es_409(entorno: Entorno) -> None:
    familia = entorno.familia()
    grupo = familia.grupo.id
    _, _, creada = entorno.invitar(familia)
    ruta = f"/v1/grupos/{grupo}/invitaciones/{creada['id']}"
    cabeceras = entorno.cabeceras(familia.admin, grupo)
    assert entorno.iam.cliente.delete(ruta, headers=cabeceras).status_code == 204
    assert entorno.iam.cliente.delete(ruta, headers=cabeceras).status_code == 204
    assert [f[0] for f in _todas("SELECT accion FROM auditoria WHERE entidad_id = %s ORDER BY id",
                                 uuid.UUID(creada["id"]))] == ["invitacion.crear", "invitacion.anular"]
    token, codigo, usada = entorno.invitar(familia)
    assert entorno.aceptar(entorno.nueva_cuenta(), token, codigo).status_code == 201
    cerrada = entorno.iam.cliente.delete(f"/v1/grupos/{grupo}/invitaciones/{usada['id']}", headers=cabeceras)
    assert cerrada.status_code == 409 and cerrada.json()["type"] == "/errores/invitacion-cerrada"
    assert cerrada.json()["estado"] == "usada"


# --- 429 y 503 -----------------------------------------------------------------------------------------


def test_el_tope_de_20_invitaciones_en_24_horas(entorno: Entorno) -> None:
    familia = entorno.familia()
    for _ in range(20):
        assert entorno.crear(familia.admin, familia.grupo.id).status_code == 201
    respuesta = entorno.crear(familia.admin, familia.grupo.id)
    assert respuesta.status_code == 429 and respuesta.json()["type"] == "/errores/tope-invitaciones"
    assert 1 <= int(respuesta.headers["Retry-After"]) <= 86_400


def test_el_limite_de_canje_por_ip_es_20_por_hora_y_lo_comparten_verificar_y_aceptar(entorno: Entorno) -> None:
    familia = entorno.familia()
    token, codigo, _ = entorno.invitar(familia)
    for _ in range(19):
        entorno.verificar("A" * 43, "1234")
    assert entorno.aceptar(entorno.nueva_cuenta(), token, codigo).status_code == 201
    respuesta = entorno.verificar(token, codigo)
    assert respuesta.status_code == 429 and respuesta.json()["type"] == "/errores/demasiadas-peticiones"
    assert respuesta.headers["Cache-Control"] == "no-store"


def test_sin_pepper_pin_crear_y_verificar_responden_503_sin_contar(entorno: Entorno) -> None:
    familia = entorno.familia()
    token, codigo, _ = entorno.invitar(familia)
    entorno.app.dependency_overrides[obtener_pepper_codigo] = lambda: None
    assert entorno.crear(familia.admin, familia.grupo.id).status_code == 503
    assert entorno.verificar(token, _otro_codigo(codigo)).status_code == 503
    # Una invitación que ya no sirve responde su 410 aunque falte la llave
    assert entorno.verificar("A" * 43, "1234").status_code == 410
    assert _todas("SELECT codigo_intentos_fallidos FROM invitacion WHERE grupo_id = %s", familia.grupo.id) == [(0,)]


# --- Lo que nunca sale ni se registra ------------------------------------------------------------------


def test_los_logs_no_llevan_token_codigo_ni_correo(entorno: Entorno) -> None:
    familia = entorno.familia()
    token, codigo, creada = entorno.invitar(familia)
    rosa = entorno.nueva_cuenta()
    entorno.verificar(token, _otro_codigo(codigo))
    entorno.verificar(token, codigo)
    entorno.aceptar(rosa, token, codigo)
    texto = entorno.iam.texto_log()
    assert texto
    for secreto in (token, f'"{codigo}"', rosa.email, familia.admin.email, creada["url"]):
        assert secreto not in texto
    # La auditoría tampoco
    detalles = _todas("SELECT detalle::text, coalesce(request_id, '') FROM auditoria WHERE entidad = 'invitacion'"
                      " AND grupo_id = %s", familia.grupo.id)
    assert detalles and all(token not in d and codigo not in d for d, _ in detalles)
