"""MATU-72, C7 (absorbe MATU-71) · Toda escritura de la ficha, sus secciones y el consumo lee la autorización con
FOR SHARE (decisión 155). Contra PostgreSQL.

Una prueba por ruta y por operación: un retiro o un borrado abierto (con la autorización bloqueada FOR UPDATE)
y la escritura en otro hilo. La escritura debe esperar el bloqueo y, al confirmarse el retiro o el borrado,
responder 403 sin escribir nada. Sin el FOR SHARE la escritura no espera: termina antes o escribe sobre una
autorización que se está retirando, y la prueba falla.

MATU-96 · Qué responde la escritura cuando el borrado gana. Depende de qué vio la escritura antes de esperar:

- **La escritura ya esperaba el bloqueo** (leyó la persona viva y se formó en el FOR SHARE de la autorización):
  al confirmarse el borrado, PostgreSQL reevalúa la fila, la autorización ya está revocada y la respuesta es
  **403 sin-consentimiento** (decisión 155). Es la carrera que importa: la escritura no se cuela.
- **El borrado confirmó antes de que la escritura leyera la persona:** la persona ya está eliminada y la
  respuesta es **404**, como toda ruta de una persona borrada (decisión 153: un recurso borrado responde 404,
  nunca 403). No es una carrera: es una petición que llega después del borrado.

Las dos respuestas son correctas y el contrato no cambia. El retiro no tiene esta diferencia: antes o después
del retiro la persona sigue ahí y la respuesta es 403 igual.

La prueba fallaba a veces (dos veces el 11-11, en ``me-quedan-borrado`` y ``consumo-borrar-borrado``) porque
asumía el primer caso tras esperar un segundo con ``hilo.join(timeout=1.0)``: si el hilo de la escritura no había
llegado aún al bloqueo, el borrado confirmaba antes, la escritura caía en el segundo caso y respondía 404. Ahora
el orden es explícito: ``esperar_bloqueada_por`` (tests/concurrencia.py) pregunta a PostgreSQL con
``pg_blocking_pids`` hasta que la escritura espera el bloqueo de la sesión del retiro o del borrado, y solo
entonces se confirma. ``test_una_escritura_lenta_…`` lo demuestra con la escritura retrasada: sin la
sincronización falla (xfail estricto) y con ella pasa. ``test_si_el_borrado_ya_confirmo_…`` fija el segundo caso.

Usa el entorno de MATU-19 (test_abrir_relevo_api), con la hora real. Solo datos sintéticos.
"""

import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest

from app.core.db import sesion_tenant
from app.modules.care_circle.application.borrado import SolicitudBorrado, borrar_persona
from app.modules.care_circle.application.retiro import SolicitudRetiro, retirar_autorizacion
from app.modules.care_circle.infrastructure.efectos_retiro import efectos_de
from app.modules.care_circle.infrastructure.repositorio_borrado import RepositorioBorradoSQL
from app.modules.care_circle.infrastructure.repositorio_retiros import RepositorioRetirosSQL
from app.modules.care_plan.api import dependencias as dependencias_ficha
from app.modules.consumption.api import dependencias as dependencias_consumo
from app.shared.auditoria_sql import RegistroAuditoriaSql
from tests.base_datos import requiere_base
from tests.concurrencia import esperar_bloqueada_por, pid_de
from tests.fabricas import FamiliaCreada
from tests.modules.care_plan import test_abrir_relevo_api as abrir
from tests.modules.care_plan.test_abrir_relevo_api import EntornoAbrir, _ejecutar, _todas, _una
from tests.modules.care_plan.test_retiro_autorizacion_api import _fabrica

entorno = abrir.entorno
reloj_fijo = abrir.reloj_fijo

pytestmark = [requiere_base, pytest.mark.rf("RF-02")]

PERSONA = "/v1/personas-cuidadas/{}"
V1 = '"v1"'


@dataclass(frozen=True)
class Escritura:
    finalidad: str
    metodo: str
    sufijo: str  # con {perfil} y {alerta} si hace falta
    cuerpo: Any = None
    cabeceras: tuple[tuple[str, str], ...] = ()
    perfil_activo: bool = True
    con_alerta: bool = False
    con_complementaria: bool = False


ESCRITURAS = {
    "ficha-campo": Escritura("plan_cuidado", "PUT", "/plan/ficha/rutina", {"texto": "Otra rutina"},
                             (("If-Match", V1),)),
    "seccion-agregar": Escritura("plan_cuidado", "PUT", "/plan/secciones/movilidad", {"texto": "Camina con bastón"},
                                 (("If-None-Match", "*"),)),
    "seccion-quitar": Escritura("plan_cuidado", "DELETE", "/plan/secciones/alimentacion", None,
                                (("If-Match", V1),), con_complementaria=True),
    "compartir": Escritura("plan_cuidado", "POST", "/plan/accesos-relevo", {
        "nombre_relevo": "Rosa", "telefono_relevo": "+56 9 5555 0137", "motivo": "otro", "relevo_informado": True}),
    "consumo-crear": Escritura("consumo", "POST", "/consumo", {
        "nombre_libre": "Toallas húmedas", "tasa_unidades": 2, "stock_unidades": 40}),
    "consumo-editar": Escritura("consumo", "PATCH", "/consumo/{perfil}", {"stock_unidades": 30}, (("If-Match", V1),)),
    "consumo-borrar": Escritura("consumo", "DELETE", "/consumo/{perfil}"),
    "consumo-desactivar": Escritura("consumo", "POST", "/consumo/{perfil}/desactivar"),
    "consumo-activar": Escritura("consumo", "POST", "/consumo/{perfil}/activar", perfil_activo=False),
    "ya-lo-resolvi": Escritura("consumo", "POST", "/consumo/{perfil}/resolver", {"cantidad": 10},
                               (("If-Match", V1),), con_alerta=True),
    "no-avisar": Escritura("consumo", "POST", "/consumo/alertas/{alerta}/descartar", con_alerta=True),
    "compre": Escritura("consumo", "POST", "/consumo/{perfil}/reponer", {"cantidad": 10}, (("If-Match", V1),)),
    "me-quedan": Escritura("consumo", "POST", "/consumo/{perfil}/recontar", {"stock_unidades": 5},
                           (("If-Match", V1),)),
}


def _cuidador(familia: FamiliaCreada) -> Any:
    return familia.miembros["cuidador"].usuario


def _preparar(entorno: EntornoAbrir, escritura: Escritura) -> tuple[FamiliaCreada, dict[str, str]]:
    familia = entorno.familia_con_ficha()
    cabeceras = entorno.ficha._cabeceras(familia.admin, familia.grupo.id)
    if escritura.con_complementaria:
        creada = entorno.ficha.iam.cliente.put(PERSONA.format(familia.persona.id) + "/plan/secciones/alimentacion",
                                               json={"texto": "Come sin sal"}, headers={**cabeceras,
                                                                                        "If-None-Match": "*"})
        assert creada.status_code == 201, creada.text
    entorno.ficha.fabrica.autorizacion_consumo(familia.persona, otorgante=familia.admin)
    perfil = entorno.ficha.fabrica.perfil_consumo(familia.persona, activo=escritura.perfil_activo)
    valores = {"perfil": str(perfil), "alerta": str(uuid.uuid4())}
    if escritura.con_alerta:
        fila = _una("SELECT fecha_quiebre_estimada FROM perfil_consumo WHERE id = %s", perfil)
        assert fila is not None
        _ejecutar("INSERT INTO alerta_quiebre (perfil_id, fecha_prevista) VALUES (%s, %s)", perfil, fila[0])
        alerta = _una("SELECT id FROM alerta_quiebre WHERE perfil_id = %s", perfil)
        assert alerta is not None
        valores["alerta"] = str(alerta[0])
    return familia, valores


def _foto(familia: FamiliaCreada) -> dict[str, Any]:
    """Lo que una escritura cambiaría: secciones, perfiles, compras, accesos y la auditoría del que escribe."""
    persona = familia.persona.id
    return {
        "secciones": _todas("SELECT s.tipo, s.version FROM plan_seccion s JOIN plan_cuidado p ON p.id = s.plan_id"
                            " WHERE p.persona_cuidada_id = %s ORDER BY 1", persona),
        "perfiles": _todas("SELECT id, version, activo, stock_unidades FROM perfil_consumo"
                           " WHERE persona_cuidada_id = %s ORDER BY 1", persona),
        "reposiciones": _todas("SELECT r.id FROM reposicion r JOIN perfil_consumo p ON p.id = r.perfil_id"
                               " WHERE p.persona_cuidada_id = %s", persona),
        "accesos": _todas("SELECT id FROM acceso_relevo WHERE grupo_id = %s", familia.grupo.id),
        "del_que_escribe": _todas("SELECT accion FROM auditoria WHERE grupo_id = %s AND actor_ref = %s",
                                  familia.grupo.id, _cuidador(familia).id),
    }


def _retirar(entorno: EntornoAbrir, familia: FamiliaCreada, sesion: Any, finalidad: str) -> None:
    registro = RegistroAuditoriaSql(sesion, entorno.reloj)
    retirar_autorizacion(
        SolicitudRetiro(usuario_id=familia.admin.id, rol="admin", persona_id=familia.persona.id, finalidad=finalidad),
        entorno.reloj, RepositorioRetirosSQL(sesion, familia.grupo.id, registro),
        efectos_de(sesion, familia.grupo.id, registro),
    )


def _borrar(entorno: EntornoAbrir, familia: FamiliaCreada, sesion: Any, finalidad: str) -> None:
    registro = RegistroAuditoriaSql(sesion, entorno.reloj)
    borrar_persona(
        SolicitudBorrado(usuario_id=familia.admin.id, rol="admin", persona_id=familia.persona.id),
        entorno.reloj, RepositorioBorradoSQL(sesion, familia.grupo.id, registro),
        RepositorioRetirosSQL(sesion, familia.grupo.id, registro), efectos_de(sesion, familia.grupo.id, registro),
    )


OPERACIONES: dict[str, Callable[[EntornoAbrir, FamiliaCreada, Any, str], None]] = {
    "retiro": _retirar,
    "borrado": _borrar,
}


def _escritura(entorno: EntornoAbrir, nombre: str) -> tuple[FamiliaCreada, Callable[[], Any], dict[str, Any]]:
    """La familia preparada, la petición de la escritura (como el cuidador) y la foto de antes."""
    escritura = ESCRITURAS[nombre]
    familia, valores = _preparar(entorno, escritura)
    cabeceras = {**entorno.ficha._cabeceras(_cuidador(familia), familia.grupo.id), **dict(escritura.cabeceras)}
    ruta = PERSONA.format(familia.persona.id) + escritura.sufijo.format(**valores)

    def pedir() -> Any:
        return entorno.ficha.iam.cliente.request(escritura.metodo, ruta, json=escritura.cuerpo, headers=cabeceras)

    return familia, pedir, _foto(familia)


def _correr_contra(
    entorno: EntornoAbrir,
    familia: FamiliaCreada,
    pedir: Callable[[], Any],
    operacion: str,
    finalidad: str,
    *,
    sincronizada: bool = True,
) -> Any:
    """Abre el retiro o el borrado, lanza la escritura en otro hilo y confirma. Con ``sincronizada`` (MATU-96)
    confirma solo cuando PostgreSQL dice que la escritura espera su bloqueo; sin ella, como antes, tras un segundo
    con el hilo vivo."""
    respuestas: list[Any] = []
    hilo = threading.Thread(target=lambda: respuestas.append(pedir()))
    with sesion_tenant(_fabrica(entorno), usuario_id=familia.admin.id, grupo_id=familia.grupo.id) as sesion:
        OPERACIONES[operacion](entorno, familia, sesion, finalidad)
        pid = pid_de(sesion)
        hilo.start()
        if sincronizada:
            esperar_bloqueada_por(pid, hilo)
        else:
            hilo.join(timeout=1.0)
            assert hilo.is_alive(), "la escritura no esperó el bloqueo"
    hilo.join(timeout=15)
    assert not hilo.is_alive(), "la escritura no terminó después de confirmar"
    [respuesta] = respuestas
    return respuesta


def _sin_escribir(familia: FamiliaCreada, operacion: str, antes: dict[str, Any]) -> None:
    despues = _foto(familia)
    if operacion == "retiro":
        # El retiro no borra nada: todo queda como antes, sin lo que la escritura habría hecho
        assert despues == antes
    else:
        # El borrado borró la ficha y los insumos, y la escritura no dejó nada después
        assert (despues["secciones"], despues["perfiles"], despues["reposiciones"]) == ([], [], [])
        assert (despues["accesos"], despues["del_que_escribe"]) == (antes["accesos"], [])


@pytest.mark.parametrize("operacion", list(OPERACIONES))
@pytest.mark.parametrize("nombre", list(ESCRITURAS))
def test_la_escritura_espera_al_retiro_o_al_borrado_y_termina_en_403(
    entorno: EntornoAbrir, nombre: str, operacion: str
) -> None:
    familia, pedir, antes = _escritura(entorno, nombre)

    respuesta = _correr_contra(entorno, familia, pedir, operacion, ESCRITURAS[nombre].finalidad)

    assert respuesta.status_code == 403, respuesta.text
    assert respuesta.json()["type"] == "/errores/sin-consentimiento"
    _sin_escribir(familia, operacion, antes)


@pytest.mark.parametrize("nombre", list(ESCRITURAS))
def test_si_el_borrado_ya_confirmo_la_escritura_responde_404(entorno: EntornoAbrir, nombre: str) -> None:
    """MATU-96 · El borrado gana del todo: confirma antes de que la escritura lea la persona. 404, como toda ruta de
    una persona borrada (decisión 153), sin escribir nada. Es lo que veía la prueba de arriba cuando fallaba."""
    familia, pedir, antes = _escritura(entorno, nombre)
    with sesion_tenant(_fabrica(entorno), usuario_id=familia.admin.id, grupo_id=familia.grupo.id) as sesion:
        _borrar(entorno, familia, sesion, ESCRITURAS[nombre].finalidad)

    respuesta = pedir()

    assert respuesta.status_code == 404, respuesta.text
    _sin_escribir(familia, "borrado", antes)


# Más que el segundo que esperaba la versión anterior, con margen
RETRASO = 2.0
# Las dos que fallaron el 11-11 y una de la ficha (care_plan tiene su propia dependencia)
LENTAS = ["me-quedan", "consumo-borrar", "ficha-campo"]


@pytest.mark.parametrize(
    "sincronizada",
    [
        True,
        pytest.param(False, marks=pytest.mark.xfail(
            strict=True, reason="MATU-96: sin sincronizar, el borrado confirma antes de que la escritura lea: 404")),
    ],
)
@pytest.mark.parametrize("nombre", LENTAS)
def test_una_escritura_lenta_espera_igual_el_bloqueo_del_borrado(
    entorno: EntornoAbrir, monkeypatch: pytest.MonkeyPatch, nombre: str, sincronizada: bool
) -> None:
    """MATU-96 · La escritura tarda RETRASO segundos en llegar a leer la persona, como en una máquina cargada. Sin la
    sincronización (la versión anterior, con un segundo de espera) el borrado confirma antes y la respuesta es 404:
    falla siempre, y el xfail estricto lo exige. Con ella, el borrado confirma solo cuando la escritura ya espera:
    403. El retraso simula la lentitud; el orden no depende de él."""
    familia, pedir, antes = _escritura(entorno, nombre)

    for modulo in (dependencias_ficha, dependencias_consumo):

        def lenta(*args: Any, _original: Any = modulo.persona_con_autorizacion, **kwargs: Any) -> Any:
            time.sleep(RETRASO)
            return _original(*args, **kwargs)

        monkeypatch.setattr(modulo, "persona_con_autorizacion", lenta)

    respuesta = _correr_contra(
        entorno, familia, pedir, "borrado", ESCRITURAS[nombre].finalidad, sincronizada=sincronizada
    )

    assert respuesta.status_code == 403, respuesta.text
    assert respuesta.json()["type"] == "/errores/sin-consentimiento"
    _sin_escribir(familia, "borrado", antes)
