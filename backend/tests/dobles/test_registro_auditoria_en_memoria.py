"""El doble RegistroAuditoriaEnMemoria cumple el puerto: guarda en orden, no se reescribe y sabe fallar."""

import uuid

import pytest

from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.puertos import RegistroAuditoria
from tests.dobles.registro_auditoria_en_memoria import RegistroAuditoriaEnMemoria

pytestmark = pytest.mark.rf("RF-08")


def _entrada(accion: AccionAuditoria) -> EntradaAuditoria:
    return EntradaAuditoria(
        grupo_id=uuid.uuid4(),
        actor_tipo=ActorTipo.USUARIO,
        actor_ref=uuid.uuid4(),
        accion=accion,
        entidad=EntidadAuditoria.PLAN_CUIDADO,
        entidad_id=uuid.uuid4(),
    )


def test_registra_en_orden() -> None:
    # Dado el doble, usado a través del puerto
    doble = RegistroAuditoriaEnMemoria()
    registro: RegistroAuditoria = doble
    leer, editar = _entrada(AccionAuditoria.PLAN_LEER), _entrada(AccionAuditoria.PLAN_EDITAR)

    # Cuando se registran dos entradas
    registro.registrar(leer)
    registro.registrar(editar)

    # Entonces quedan las dos, en orden
    assert doble.entradas == (leer, editar)


def test_lo_registrado_no_se_puede_borrar_desde_la_prueba() -> None:
    doble = RegistroAuditoriaEnMemoria()
    doble.registrar(_entrada(AccionAuditoria.PLAN_LEER))

    assert isinstance(doble.entradas, tuple)
    assert not hasattr(doble, "borrar")


def test_fallar_con_lanza_y_no_guarda() -> None:
    # Dado un doble que simula que la base rechaza la fila
    doble = RegistroAuditoriaEnMemoria()
    doble.fallar_con(RuntimeError("la base rechazó la fila"))

    # Cuando se registra, entonces lanza y no queda nada
    with pytest.raises(RuntimeError):
        doble.registrar(_entrada(AccionAuditoria.PLAN_EDITAR))
    assert doble.entradas == ()
