"""MATU-72, C7 (absorbe MATU-71) · Toda escritura de la ficha, sus secciones y el consumo lee la autorización con
FOR SHARE (decisión 155). Contra PostgreSQL.

Una prueba por ruta y por operación: un retiro o un borrado abierto (con la autorización bloqueada FOR UPDATE)
y la escritura en otro hilo. La escritura debe esperar el bloqueo y, al confirmarse el retiro o el borrado,
responder 403 sin escribir nada. Sin el FOR SHARE la escritura no espera: termina antes (el hilo ya no está vivo)
o escribe sobre una autorización que se está retirando, y la prueba falla.

Usa el entorno de MATU-19 (test_abrir_relevo_api), con la hora real. Solo datos sintéticos.
"""

import threading
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
from app.shared.auditoria_sql import RegistroAuditoriaSql
from tests.base_datos import requiere_base
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


@pytest.mark.parametrize("operacion", list(OPERACIONES))
@pytest.mark.parametrize("nombre", list(ESCRITURAS))
def test_la_escritura_espera_al_retiro_o_al_borrado_y_termina_en_403(
    entorno: EntornoAbrir, nombre: str, operacion: str
) -> None:
    escritura = ESCRITURAS[nombre]
    familia, valores = _preparar(entorno, escritura)
    cuidador = _cuidador(familia)
    cabeceras = {**entorno.ficha._cabeceras(cuidador, familia.grupo.id), **dict(escritura.cabeceras)}
    ruta = PERSONA.format(familia.persona.id) + escritura.sufijo.format(**valores)
    respuestas: list[Any] = []
    antes = _foto(familia)

    def escribir() -> None:
        respuestas.append(entorno.ficha.iam.cliente.request(escritura.metodo, ruta, json=escritura.cuerpo,
                                                            headers=cabeceras))

    with sesion_tenant(_fabrica(entorno), usuario_id=familia.admin.id, grupo_id=familia.grupo.id) as sesion:
        OPERACIONES[operacion](entorno, familia, sesion, escritura.finalidad)
        hilo = threading.Thread(target=escribir)
        hilo.start()
        hilo.join(timeout=1.0)
        assert hilo.is_alive(), f"{nombre} no esperó el bloqueo del {operacion}: {respuestas[0].status_code}"
    hilo.join(timeout=15)

    [respuesta] = respuestas
    assert respuesta.status_code == 403, respuesta.text
    assert respuesta.json()["type"] == "/errores/sin-consentimiento"
    despues = _foto(familia)
    if operacion == "retiro":
        # El retiro no borra nada: todo queda como antes, sin lo que la escritura habría hecho
        assert despues == antes
    else:
        # El borrado borró la ficha y los insumos, y la escritura no dejó nada después
        assert (despues["secciones"], despues["perfiles"], despues["reposiciones"]) == ([], [], [])
        assert (despues["accesos"], despues["del_que_escribe"]) == (antes["accesos"], [])
