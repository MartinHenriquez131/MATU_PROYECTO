"""MATU-46 · El teléfono del relevo se borra 30 días después de que el acceso vence o se corta (decisión 25).

Contra PostgreSQL, con la tarea como matu_scheduler y el puerto Reloj. La familia comparte por la API (entorno de
MATU-19) y las fechas de cada acceso se acortan como superusuario: el trigger token_vida_fija deja acortar, no
alargar. relevo_conservar exige un «ahora» que no pase de now() de la base, así que el fin de los accesos queda 30
días y 2 horas antes de la hora real. Solo datos sintéticos.
"""

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app import tareas
from app.core.config import obtener_configuracion
from app.core.logs import FormateadorJSON
from app.modules.care_plan.infrastructure.tarea_conservacion_relevo import ejecutar
from tests.base_datos import fabrica_scheduler, requiere_base
from tests.dobles.reloj_fijo import RelojFijo
from tests.fabricas import FamiliaCreada
from tests.modules.care_plan import test_abrir_relevo_api as abrir
from tests.modules.care_plan.test_abrir_relevo_api import RUTA_ACCESOS, EntornoAbrir, _ejecutar, _una
from tests.textos import aparece_celular

entorno = abrir.entorno
reloj_fijo = abrir.reloj_fijo

pytestmark = [requiere_base, pytest.mark.rf("RF-05")]

TELEFONO = "+56 9 5555 0146"
TELEFONO_GUARDADO = "+56955550146"
# El fin de los accesos que ya cumplieron el plazo
FIN = (datetime.now(UTC) - timedelta(days=30, hours=2)).replace(microsecond=0)

# Lo que se conserva 3 años: el nombre, el motivo y las fechas
_CONSERVADO = (
    "SELECT otorgado_a_nombre, motivo, creado_en, expira_en, revocado_en, nombre_pila_persona, nombre_pila_comparte,"
    " usos, secciones_permitidas FROM acceso_relevo WHERE id = %s"
)


def _telefono(acceso: uuid.UUID) -> tuple[Any, ...] | None:
    return _una("SELECT otorgado_a_telefono, telefono_borrado_en FROM acceso_relevo WHERE id = %s", acceso)


def _terminar(acceso: uuid.UUID, expira_en: datetime, revocado_en: datetime | None = None,
              pin_intentos: int = 0) -> None:
    """Acorta la vida del acceso (y lo corta, o lo bloquea) como superusuario."""
    _ejecutar("UPDATE acceso_relevo SET creado_en = %s, expira_en = %s, revocado_en = %s,"
              " pin_intentos_fallidos = %s WHERE id = %s",
              expira_en - timedelta(days=1), expira_en, revocado_en, pin_intentos, acceso)


def _tarea(instante: datetime) -> int:
    return ejecutar(fabrica_scheduler(), RelojFijo(instante)).telefonos_borrados


def _lista(entorno: EntornoAbrir, familia: FamiliaCreada) -> dict[str, dict[str, Any]]:
    respuesta = entorno.ficha.iam.cliente.get(RUTA_ACCESOS.format(familia.persona.id),
                                              headers=entorno.ficha._cabeceras(familia.admin, familia.grupo.id))
    assert respuesta.status_code == 200, respuesta.text
    return {item["id"]: item for item in respuesta.json()["items"]}


def test_telefono_relevo_se_borra_a_los_30_dias(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    vigente, vencido, cortado, bloqueado, reciente = (
        entorno.compartir(familia, telefono_relevo=TELEFONO)[0] for _ in range(5))
    _terminar(vencido, FIN)
    # C1: cortado antes de vencer, cuenta desde el corte
    _terminar(cortado, FIN + timedelta(days=5), revocado_en=FIN)
    # C2: bloqueado por el PIN, cuenta desde su vencimiento
    _terminar(bloqueado, FIN, pin_intentos=5)
    # Vencido hace un día: le quedan 29
    _terminar(reciente, datetime.now(UTC) - timedelta(days=1))
    terminados = (vencido, cortado, bloqueado)
    conservado = {a: _una(_CONSERVADO, a) for a in (vigente, *terminados, reciente)}

    # A los 29 días y 23 horas del fin, ninguno
    _tarea(FIN + timedelta(days=29, hours=23))
    for acceso in (vigente, *terminados, reciente):
        assert _telefono(acceso) == (TELEFONO_GUARDADO, None), acceso

    # MATU-107 (46-H2): a los 30 días exactos, todavía ninguno. La tarea descuenta los 5 minutos que relevo_conservar
    # admite de adelanto en el reloj, a favor de conservar
    _tarea(FIN + timedelta(days=30))
    for acceso in (vigente, *terminados, reciente):
        assert _telefono(acceso) == (TELEFONO_GUARDADO, None), acceso

    # A los 30 días y 5 minutos, los tres terminados, con el instante de la tarea. El vigente y el reciente, no
    instante = FIN + timedelta(days=30, minutes=5)
    assert _tarea(instante) >= 3
    for acceso in terminados:
        assert _telefono(acceso) == (None, instante), acceso
    for acceso in (vigente, reciente):
        assert _telefono(acceso) == (TELEFONO_GUARDADO, None), acceso
    # Solo el teléfono: el nombre, el motivo y las fechas no cambian
    for acceso, antes in conservado.items():
        assert _una(_CONSERVADO, acceso) == antes, acceso

    # Idempotente (C12): otra corrida no vuelve a contar ni cambia el instante
    _tarea(instante + timedelta(hours=1))
    for acceso in terminados:
        assert _telefono(acceso) == (None, instante), acceso

    # La API ya no lo entrega: telefono_relevo es null, y el resto del acceso sigue en la lista
    lista = _lista(entorno, familia)
    for acceso in terminados:
        item = lista[str(acceso)]
        assert item["telefono_relevo"] is None and item["nombre_relevo"] == "Rosa"
    assert lista[str(vigente)]["telefono_relevo"] == TELEFONO_GUARDADO
    assert lista[str(reciente)]["telefono_relevo"] == TELEFONO_GUARDADO


def test_la_tarea_no_lleva_el_telefono_al_log(entorno: EntornoAbrir, caplog: pytest.LogCaptureFixture) -> None:
    """C4 a C6: la corrida registra solo el contador. Ni el teléfono, ni el nombre del relevo, ni un id."""
    familia = entorno.familia_con_ficha()
    acceso, token, pin = entorno.compartir(familia, telefono_relevo=TELEFONO)
    _terminar(acceso, FIN)
    contexto = tareas.Contexto(
        config=obtener_configuracion(),
        fabrica=_Prohibida(),  # type: ignore[arg-type]
        reloj=RelojFijo(FIN + timedelta(days=30, minutes=5)),
        fabrica_scheduler=fabrica_scheduler(),
    )

    # Solo lo que registra la corrida: las peticiones de la familia ya llevan su grupo, como corresponde
    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        assert tareas.correr(["conservacion_relevo"], contexto) == tareas.SALIDA_OK

    assert _telefono(acceso) == (None, FIN + timedelta(days=30, minutes=5))
    formateador = FormateadorJSON()
    texto = "\n".join(formateador.format(r) for r in caplog.records) + caplog.text
    assert not aparece_celular(TELEFONO, texto)
    for dato in (str(acceso), str(familia.grupo.id), str(familia.persona.id), "Rosa", token, pin):
        assert dato not in texto
    [linea] = [json.loads(formateador.format(r)) for r in caplog.records if r.name == "matu.tareas"]
    assert linea["tarea"] == "conservacion_relevo" and linea["resultado"] == "ok"
    assert set(linea["contadores"]) == {"telefonos_borrados"} and linea["contadores"]["telefonos_borrados"] >= 1


def test_la_tarea_corre_dentro_de_los_borrados_diarios() -> None:
    """Ajuste de Jorge: va en BORRADOS_DIARIOS y corre siempre, sin depender de la capa 3."""
    assert "conservacion_relevo" in tareas.BORRADOS_DIARIOS
    assert tareas.nombres_de("borrados") == tareas.BORRADOS_DIARIOS
    assert tareas.DIARIAS.index("conservacion_relevo") < tareas.DIARIAS.index("quiebres")


class _Prohibida:
    """La fábrica de matu_app: la tarea del teléfono no la usa."""

    def __call__(self, **_: Any) -> Any:
        raise AssertionError("conservacion_relevo abrió una sesión de matu_app")
