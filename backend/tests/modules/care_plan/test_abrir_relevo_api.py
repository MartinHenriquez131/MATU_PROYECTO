"""MATU-19 · Abrir la ficha como relevo con enlace y PIN, por la API y contra PostgreSQL (RF-06).

La familia comparte por su ruta (MATU-18) y el relevo usa un cliente https (base_url
"https://testserver"), porque la cookie __Secure-matu-relevo es Secure. Las sesiones van en
SesionesRelevoEnMemoria (el pipeline no tiene Redis); el adaptador Redis tiene su propia prueba.

El reloj de estas pruebas parte de la hora real: las políticas RLS del relevo usan now() de la base,
y un acceso creado con el reloj sintético de 2026-10-20 ya estaría vencido para la base.

Solo datos sintéticos: Rosa reemplaza a la cuidadora, los textos son inventados.
"""

import re
import secrets
import uuid
from collections.abc import Iterator
from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.care_plan.api import router_relevo_publico
from app.modules.care_plan.api.dependencias import obtener_pepper_pin
from app.modules.care_plan.api.router_relevo_publico import obtener_fabrica_registro, obtener_sesiones_relevo
from app.shared.puertos import RegistroAuditoria
from tests.base_datos import DSN, requiere_base
from tests.dobles.reloj_fijo import RelojFijo
from tests.dobles.sesiones_relevo_en_memoria import SesionesRelevoEnMemoria
from tests.fabricas import FamiliaCreada
from tests.modules.care_plan.conftest import EntornoFicha

pytestmark = [requiere_base, pytest.mark.rf("RF-06")]

PROBLEMA = "application/problem+json"
RUTA_ACCESOS = "/v1/personas-cuidadas/{}/plan/accesos-relevo"
COOKIE = "__Secure-matu-relevo"
URL = re.compile(r"^https://[^/#]+/r#([A-Za-z0-9_-]{43})$")
RUTINA = "08:00 se levanta y toma desayuno en la cocina"
RED = "Hija: Carmen, +56 9 5555 0101"


@pytest.fixture
def reloj_fijo() -> RelojFijo:
    return RelojFijo(datetime.now(UTC).replace(microsecond=0))


class EntornoAbrir:
    def __init__(self, ficha: EntornoFicha, sesiones: SesionesRelevoEnMemoria) -> None:
        self.ficha = ficha
        self.sesiones = sesiones
        self.relevo = TestClient(ficha.app, base_url="https://testserver", raise_server_exceptions=False)

    @property
    def reloj(self) -> RelojFijo:
        return self.ficha.iam.reloj

    def familia_con_ficha(self, textos: dict[str, str] | None = None, **opciones: Any) -> FamiliaCreada:
        familia = self.ficha.familia(**opciones)
        self.ficha.fabrica.ficha(
            familia.persona, actualizado_por=familia.admin.id, custodia=self.ficha.custodia,
            textos={"rutina": RUTINA, "manejo_situaciones": "", "red_apoyo": RED} if textos is None else textos,
        )
        return familia

    def compartir(self, familia: FamiliaCreada, **cambios: Any) -> tuple[uuid.UUID, str, str]:
        cuerpo: dict[str, Any] = {
            "nombre_relevo": "Rosa", "telefono_relevo": "+56 9 5555 0137",
            "campos": ["rutina", "manejo_situaciones"], "motivo": "turno_de_noche", "relevo_informado": True,
        }
        cuerpo.update(cambios)
        respuesta = self.ficha.iam.cliente.post(
            RUTA_ACCESOS.format(familia.persona.id), json=cuerpo,
            headers=self.ficha._cabeceras(familia.admin, familia.grupo.id),
        )
        assert respuesta.status_code == 201, respuesta.text
        creado = respuesta.json()
        coincide = URL.match(creado["url"])
        assert coincide
        return uuid.UUID(creado["id"]), coincide.group(1), creado["pin"]

    def presentar(self, token: str) -> Any:
        return self.relevo.post("/v1/relevo/presentacion", json={"token": token})

    def canjear(self, token: str, pin: str) -> Any:
        return self.relevo.post("/v1/relevo/canje", json={"token": token, "pin": pin})

    def leer(self) -> Any:
        return self.relevo.get("/v1/relevo/ficha")

    def abrir(self, token: str, pin: str) -> Any:
        canje = self.canjear(token, pin)
        assert canje.status_code == 204, canje.text
        return self.leer()


@pytest.fixture
def entorno(entorno_ficha: EntornoFicha) -> Iterator[EntornoAbrir]:
    app = cast(FastAPI, entorno_ficha.iam.cliente.app)
    pepper = secrets.token_bytes(32)
    sesiones = SesionesRelevoEnMemoria(entorno_ficha.iam.reloj)
    app.dependency_overrides[obtener_pepper_pin] = lambda: pepper
    app.dependency_overrides[obtener_sesiones_relevo] = lambda: sesiones
    entorno = EntornoAbrir(entorno_ficha, sesiones)
    with entorno.relevo:
        yield entorno


def _una(sql: str, *parametros: Any) -> tuple[Any, ...] | None:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchone()


def _todas(sql: str, *parametros: Any) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchall()


def _ejecutar(sql: str, *parametros: Any) -> None:
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute(sql, parametros)


def _acciones(acceso_id: uuid.UUID) -> list[str]:
    return [f[0] for f in _todas(
        "SELECT accion FROM auditoria WHERE actor_ref = %s ORDER BY id", acceso_id)]


def _cabeceras_relevo(respuesta: Any) -> None:
    assert respuesta.headers["cache-control"] == "no-store"
    assert respuesta.headers["referrer-policy"] == "no-referrer"
    assert respuesta.headers["x-robots-tag"] == "noindex"


def _problema(respuesta: Any, status: int, tipo: str) -> dict[str, Any]:
    assert respuesta.status_code == status, respuesta.text
    assert respuesta.headers["content-type"] == PROBLEMA
    cuerpo = cast(dict[str, Any], respuesta.json())
    assert cuerpo["type"] == f"/errores/{tipo}"
    _cabeceras_relevo(respuesta)
    return cuerpo


def _cookie_borrada(respuesta: Any) -> None:
    borrar = f"{COOKIE}=; Max-Age=0; Path=/v1/relevo; HttpOnly; Secure; SameSite=Strict"
    assert respuesta.headers["set-cookie"] == borrar


# --- Las cinco pruebas del backlog ---------------------------------------------------------------------


def test_relevo_ve_solo_campos_habilitados(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    _, token, pin = entorno.compartir(familia)

    respuesta = entorno.abrir(token, pin)

    assert respuesta.status_code == 200, respuesta.text
    _cabeceras_relevo(respuesta)
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"nombre_pila", "nombre_pila_comparte", "vence_en", "campos"}
    # Habilitados: rutina con texto y manejo_situaciones vacío (null). red_apoyo no se compartió
    assert cuerpo["campos"] == {"rutina": {"texto": RUTINA}, "manejo_situaciones": {"texto": None}}
    assert "Hija" not in respuesta.text and "0101" not in respuesta.text
    assert cuerpo["nombre_pila"] == familia.persona.nombre_pila
    assert familia.persona.nombre not in respuesta.text  # el nombre completo nunca


def test_relevo_vencido_410(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    expira = entorno.reloj.ahora() + timedelta(hours=1)
    _, token, pin = entorno.compartir(familia, expira_en=expira.isoformat())
    canje = entorno.canjear(token, pin)
    assert canje.status_code == 204
    # Max-Age = lo que le queda al acceso, menos de 12 horas
    assert "Max-Age=3600;" in canje.headers["set-cookie"]

    entorno.reloj.avanzar(timedelta(hours=1))  # vence en el instante exacto, según el Reloj

    _problema(entorno.presentar(token), 410, "relevo-vencido")
    _problema(entorno.canjear(token, pin), 410, "relevo-vencido")
    # La cookie del canje anterior ya no abre: 410, borra la cookie y descarta la sesión
    entorno.sesiones.guardadas = {k: (v[0], v[1] + timedelta(days=1)) for k, v in entorno.sesiones.guardadas.items()}
    ficha = entorno.leer()
    _problema(ficha, 410, "relevo-vencido")
    _cookie_borrada(ficha)
    assert entorno.sesiones.guardadas == {}


def test_cinco_pin_incorrectos_423(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    acceso_id, token, pin = entorno.compartir(familia)
    malo = "0000" if pin != "0000" else "1111"
    # Una sesión abierta antes del ataque
    assert entorno.canjear(token, pin).status_code == 204

    for restantes in (4, 3, 2, 1):
        cuerpo = _problema(entorno.canjear(token, malo), 401, "pin-incorrecto")
        assert cuerpo["intentos_restantes"] == restantes
        assert set(cuerpo) == {"type", "title", "status", "detail", "errores", "request_id", "intentos_restantes"}
    _problema(entorno.canjear(token, malo), 423, "relevo-bloqueado")
    # Bloqueado: ni el PIN correcto, ni la presentación, ni la sesión abierta
    _problema(entorno.canjear(token, pin), 423, "relevo-bloqueado")
    _problema(entorno.presentar(token), 423, "relevo-bloqueado")
    ficha = entorno.leer()
    _problema(ficha, 423, "relevo-bloqueado")
    _cookie_borrada(ficha)

    assert _una("SELECT pin_intentos_fallidos FROM acceso_relevo WHERE id = %s", acceso_id) == (5,)
    assert _acciones(acceso_id).count("relevo.pin_incorrecto") == 5
    assert _acciones(acceso_id).count("relevo.bloqueo") == 1


def test_relevo_no_hereda_nada_de_la_familia(entorno: EntornoAbrir, monkeypatch: pytest.MonkeyPatch) -> None:
    contextos: list[dict[str, Any]] = []
    original = router_relevo_publico.sesion_tenant

    def espia(fabrica: Any, **contexto: Any) -> AbstractContextManager[Any]:
        contextos.append(contexto)
        return original(fabrica, **contexto)

    monkeypatch.setattr(router_relevo_publico, "sesion_tenant", espia)
    familia = entorno.familia_con_ficha()
    acceso_id, token, pin = entorno.compartir(familia)

    assert entorno.presentar(token).status_code == 200
    respuesta = entorno.abrir(token, pin)
    assert respuesta.status_code == 200

    # C1: solo el contexto de relevo o ninguno (indice_token). Nunca grupo, usuario ni 'sistema'
    assert contextos
    for contexto in contextos:
        assert contexto in ({}, {"acceso_relevo_id": acceso_id, "rol": "relevo"}), contexto
    # Lo que ve: nada de la persona fuera del nombre de pila, nada del grupo
    texto = respuesta.text
    assert str(familia.grupo.id) not in texto and str(familia.persona.id) not in texto
    assert familia.admin.email not in texto and "direccion" not in texto
    # Un Bearer de la familia no le da nada más a la ruta del relevo
    otra = entorno.relevo.get("/v1/relevo/ficha", headers=entorno.ficha._cabeceras(familia.admin, familia.grupo.id))
    assert otra.status_code == 200 and otra.json() == respuesta.json()


def test_apertura_auditada(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    acceso_id, token, pin = entorno.compartir(familia)

    assert entorno.abrir(token, pin).status_code == 200

    filas = _todas(
        "SELECT grupo_id, actor_tipo, actor_ref, entidad, entidad_id, motivo, ip, a::text FROM auditoria a"
        " WHERE accion = 'relevo.abrir' AND actor_ref = %s", acceso_id)
    assert len(filas) == 1
    grupo, actor_tipo, actor_ref, entidad, entidad_id, motivo, ip, fila = filas[0]
    plan = _una("SELECT id FROM plan_cuidado WHERE persona_cuidada_id = %s", familia.persona.id)
    assert plan is not None
    assert (grupo, actor_tipo, actor_ref, entidad, entidad_id) == (
        familia.grupo.id, "relevo", acceso_id, "plan_cuidado", plan[0])
    assert motivo is None and ip is None  # C8
    assert token not in fila and pin not in fila.replace(str(acceso_id), "") and "Rosa" not in fila
    usos, ultimo = cast(tuple[int, datetime], _una(
        "SELECT usos, ultimo_uso_en FROM acceso_relevo WHERE id = %s", acceso_id))
    assert usos == 1 and ultimo == entorno.reloj.ahora()
    assert _acciones(acceso_id) == ["relevo.canje", "relevo.abrir"]


# --- Condiciones del analista normativo y camino de error --------------------------------------------


def test_pin_incorrecto_confirma_contador_y_auditoria(entorno: EntornoAbrir) -> None:
    """C6: tras un 401 el contador y la fila relevo.pin_incorrecto quedaron confirmados en la base."""
    familia = entorno.familia_con_ficha()
    acceso_id, token, pin = entorno.compartir(familia)
    _problema(entorno.canjear(token, "0000" if pin != "0000" else "1111"), 401, "pin-incorrecto")
    assert _una("SELECT pin_intentos_fallidos FROM acceso_relevo WHERE id = %s", acceso_id) == (1,)
    assert _todas(
        "SELECT actor_tipo, ip FROM auditoria WHERE accion = 'relevo.pin_incorrecto' AND actor_ref = %s", acceso_id
    ) == [("relevo", None)]
    # El PIN correcto vuelve el contador a 0
    assert entorno.canjear(token, pin).status_code == 204
    assert _una("SELECT pin_intentos_fallidos FROM acceso_relevo WHERE id = %s", acceso_id) == (0,)


def test_presentacion_y_canje_no_traen_nada_de_la_ficha(entorno: EntornoAbrir) -> None:
    """C2: el 200 de la presentación y el 204 del canje no traen texto ni campos."""
    familia = entorno.familia_con_ficha()
    acceso_id, token, pin = entorno.compartir(familia)
    presentacion = entorno.presentar(token)
    assert presentacion.status_code == 200
    _cabeceras_relevo(presentacion)
    assert presentacion.json() == {"nombre_pila_comparte": familia.admin.nombre.split()[0],
                                   "nombre_pila": familia.persona.nombre_pila}
    canje = entorno.canjear(token, pin)
    assert canje.status_code == 204 and canje.content == b""
    _cabeceras_relevo(canje)
    assert RUTINA not in presentacion.text + canje.text
    # La presentación no cuenta intento, no suma usos y se audita
    assert _una("SELECT pin_intentos_fallidos, usos FROM acceso_relevo WHERE id = %s", acceso_id) == (0, 0)
    assert _acciones(acceso_id) == ["relevo.presentar", "relevo.canje"]


def test_cookie_de_sesion_efimera(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    acceso_id, token, pin = entorno.compartir(familia)  # 24 horas: Max-Age = 12 horas
    canje = entorno.canjear(token, pin)
    cookie = canje.headers["set-cookie"]
    valor = re.match(rf"^{COOKIE}=([A-Za-z0-9_-]+); Max-Age=43200; Path=/v1/relevo; HttpOnly; Secure; SameSite=Strict$",
                     cookie)
    assert valor and len(valor.group(1)) >= 22  # ≥ 128 bits
    assert "Domain" not in cookie
    assert entorno.sesiones.ttls == [43200]
    assert entorno.sesiones.acceso_de(valor.group(1)) == acceso_id
    # Pasadas 12 horas la sesión ya no existe: 401, y se vuelve a escribir el PIN
    entorno.reloj.avanzar(timedelta(hours=12))
    _problema(entorno.leer(), 401, "sin-sesion-relevo")


def test_sin_cookie_o_cookie_alterada_401(entorno: EntornoAbrir) -> None:
    _problema(entorno.leer(), 401, "sin-sesion-relevo")
    entorno.relevo.cookies.set(COOKIE, "alterada", path="/v1/relevo")
    _problema(entorno.leer(), 401, "sin-sesion-relevo")


def test_token_desconocido_o_cortado_410(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    _, token, pin = entorno.compartir(familia)
    for otro in (token[:-3], secrets.token_urlsafe(32), "no es un token"):
        _problema(entorno.presentar(otro), 410, "relevo-no-disponible")
        _problema(entorno.canjear(otro, pin), 410, "relevo-no-disponible")


def test_cuerpo_invalido_422_con_cabeceras(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    acceso_id, token, _ = entorno.compartir(familia)
    _problema(entorno.relevo.post("/v1/relevo/canje", json={"token": token, "pin": "12a4"}), 422, "validacion")
    _problema(entorno.relevo.post("/v1/relevo/presentacion", json={"token": token, "extra": 1}), 422, "validacion")
    assert _una("SELECT pin_intentos_fallidos FROM acceso_relevo WHERE id = %s", acceso_id) == (0,)


def test_revocado_410_aunque_la_cookie_sea_valida(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    acceso_id, token, pin = entorno.compartir(familia)
    assert entorno.canjear(token, pin).status_code == 204
    # Lo que hará MATU-20, en la misma transacción
    _ejecutar("UPDATE acceso_relevo SET revocado_en = now() WHERE id = %s", acceso_id)
    _ejecutar("UPDATE indice_token SET revocado_en = now() WHERE referencia_id = %s", acceso_id)
    _problema(entorno.presentar(token), 410, "relevo-revocado")
    _problema(entorno.canjear(token, pin), 410, "relevo-revocado")
    ficha = entorno.leer()
    _problema(ficha, 410, "relevo-revocado")
    _cookie_borrada(ficha)


def test_indice_vigente_pero_rls_sin_filas_410_vencido(entorno: EntornoAbrir) -> None:
    """C5: indice_token dice vigente según el Reloj, pero now() de la base ya lo venció."""
    familia = entorno.familia_con_ficha()
    acceso_id, token, pin = entorno.compartir(familia)
    _ejecutar("UPDATE acceso_relevo SET creado_en = now() - interval '2 days', expira_en = now() - interval '1 minute'"
              " WHERE id = %s", acceso_id)
    _problema(entorno.presentar(token), 410, "relevo-vencido")
    _problema(entorno.canjear(token, pin), 410, "relevo-vencido")


@pytest.mark.parametrize("motivo", ["consentimiento_revocado", "revision_vencida"])
def test_relevo_pausado_410_y_vuelve_al_renovar(entorno: EntornoAbrir, motivo: str) -> None:
    """Decisión 33 en el relevo: sin autorización vigente, 410 relevo-pausado sin decir por qué."""
    calidad = "cuidador_de_hecho" if motivo == "revision_vencida" else "titular"
    familia = entorno.familia_con_ficha(calidad=calidad)
    acceso_id, token, pin = entorno.compartir(familia)
    assert entorno.canjear(token, pin).status_code == 204
    consentimiento = familia.persona.consentimiento_id
    if motivo == "revision_vencida":
        _ejecutar("UPDATE consentimiento SET revision_vence_en = %s WHERE id = %s",
                  entorno.reloj.ahora() + timedelta(minutes=5), consentimiento)
        entorno.reloj.avanzar(timedelta(minutes=5))
    else:
        _ejecutar("UPDATE consentimiento SET revocado_en = now() WHERE id = %s", consentimiento)

    for respuesta in (entorno.presentar(token), entorno.canjear(token, pin)):
        cuerpo = _problema(respuesta, 410, "relevo-pausado")
        assert cuerpo["title"] == "Ya no está disponible"
        assert "consentimiento" not in cuerpo["detail"].lower() and "revisión" not in cuerpo["detail"].lower()
    ficha = entorno.leer()
    _problema(ficha, 410, "relevo-pausado")
    _cookie_borrada(ficha)
    assert entorno.sesiones.guardadas == {}
    # No cuenta como intento
    assert _una("SELECT pin_intentos_fallidos FROM acceso_relevo WHERE id = %s", acceso_id) == (0,)

    # Renovada la autorización, el mismo enlace vuelve a servir
    if motivo == "revision_vencida":
        _ejecutar("UPDATE consentimiento SET revision_vence_en = %s WHERE id = %s",
                  entorno.reloj.ahora() + timedelta(days=365), consentimiento)
    else:
        _ejecutar("UPDATE consentimiento SET revocado_en = NULL WHERE id = %s", consentimiento)
    assert entorno.abrir(token, pin).status_code == 200


def test_si_falla_la_auditoria_no_sale_texto(entorno: EntornoAbrir) -> None:
    """C7: relevo.abrir en la misma transacción que la lectura. Sin auditoría, ni texto ni usos."""
    familia = entorno.familia_con_ficha()
    acceso_id, token, pin = entorno.compartir(familia)
    assert entorno.canjear(token, pin).status_code == 204

    class Falla:
        def registrar(self, entrada: Any) -> None:
            raise RuntimeError("la base rechazó la fila")

    def fabrica_que_falla() -> Any:
        return lambda sesion: cast(RegistroAuditoria, Falla())

    entorno.ficha.app.dependency_overrides[obtener_fabrica_registro] = fabrica_que_falla
    respuesta = entorno.leer()
    assert respuesta.status_code == 500
    assert RUTINA not in respuesta.text
    assert _una("SELECT usos FROM acceso_relevo WHERE id = %s", acceso_id) == (0,)


def test_logs_sin_token_pin_ni_sesion(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    _, token, pin = entorno.compartir(familia)
    entorno.presentar(token)
    entorno.canjear(token, "0000" if pin != "0000" else "1111")
    canje = entorno.canjear(token, pin)
    sesion = canje.headers["set-cookie"].split(";")[0].split("=", 1)[1]
    entorno.leer()
    log = entorno.ficha.iam.texto_log()
    assert token not in log and sesion not in log and RUTINA not in log
    assert f'"{pin}"' not in log
    rutas = {linea.get("ruta") for linea in entorno.ficha.iam.lineas_log()}
    assert {"/v1/relevo/presentacion", "/v1/relevo/canje", "/v1/relevo/ficha"} <= rutas


@pytest.mark.parametrize("hilos", [2, 8])
def test_canjes_simultaneos_no_pierden_intentos_ni_pasan_de_cinco(entorno: EntornoAbrir, hilos: int) -> None:
    """C4: varios canjes con PIN incorrecto a la vez, en conexiones distintas. El contador refleja cada
    intento aceptado y nunca se aceptan más de 5."""
    import threading

    from app.core.db import fabrica_sesiones, sesion_tenant
    from app.modules.care_plan.application.canje_relevo import AccesoBloqueadoAhora, PinIncorrecto, canjear
    from app.modules.care_plan.infrastructure.credenciales_relevo import HuellasHmac
    from app.modules.care_plan.infrastructure.repositorio_relevo import RepositorioAccesoRelevoSQL
    from app.shared.auditoria_sql import RegistroAuditoriaSql

    familia = entorno.familia_con_ficha()
    acceso_id, _, pin = entorno.compartir(familia)
    malo = "0000" if pin != "0000" else "1111"
    pepper = entorno.ficha.app.dependency_overrides[obtener_pepper_pin]()
    fabrica = fabrica_sesiones()
    barrera: threading.Barrier
    resultados: list[str] = []

    def intentar() -> None:
        barrera.wait()
        try:
            with sesion_tenant(fabrica, acceso_relevo_id=acceso_id, rol="relevo") as sesion:
                resultado = canjear(
                    malo, RepositorioAccesoRelevoSQL(sesion), HuellasHmac(pepper),
                    RegistroAuditoriaSql(sesion, entorno.reloj), entorno.sesiones, entorno.reloj, None,
                )
            resultados.append("aceptado" if isinstance(resultado, PinIncorrecto | AccesoBloqueadoAhora) else "otro")
        except Exception as error:  # noqa: BLE001 - el bloqueo de otro hilo es un resultado esperado
            resultados.append(type(error).__name__)

    # 8 intentos en total: una ronda de 8 hilos, o cuatro rondas de 2 hilos simultáneos
    for _ronda in range(8 // hilos):
        barrera = threading.Barrier(hilos)
        trabajadores = [threading.Thread(target=intentar) for _ in range(hilos)]
        for t in trabajadores:
            t.start()
        for t in trabajadores:
            t.join(timeout=30)

    aceptados = resultados.count("aceptado")
    assert set(resultados) <= {"aceptado", "RelevoBloqueado"}, resultados
    assert len(resultados) == 8 and aceptados == 5
    [(contador,)] = _todas("SELECT pin_intentos_fallidos FROM acceso_relevo WHERE id = %s", acceso_id)
    assert contador == aceptados
    assert _acciones(acceso_id).count("relevo.pin_incorrecto") == aceptados
    assert _acciones(acceso_id).count("relevo.bloqueo") == (1 if aceptados == 5 else 0)
