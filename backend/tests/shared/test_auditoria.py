"""MATU-14 · Los tipos de la auditoría son catálogos cerrados y solo llevan identificadores (RF-08).

Sin base ni SQLAlchemy: app.shared.auditoria es solo biblioteca estándar.
"""

import dataclasses
import uuid
from typing import Any

import pytest

from app.shared.auditoria import (
    AccionAuditoria,
    ActorTipo,
    EntidadAuditoria,
    EntradaAuditoria,
    MotivoAuditoria,
)

pytestmark = pytest.mark.rf("RF-08")

GRUPO = uuid.UUID("00000000-0000-0000-0000-0000000014a1")
USUARIO = uuid.UUID("00000000-0000-0000-0000-0000000014a2")
PLAN = uuid.UUID("00000000-0000-0000-0000-0000000014a3")


def _campos(**cambios: Any) -> dict[str, Any]:
    campos: dict[str, Any] = {
        "grupo_id": GRUPO,
        "actor_tipo": ActorTipo.USUARIO,
        "actor_ref": USUARIO,
        "accion": AccionAuditoria.PLAN_LEER,
        "entidad": EntidadAuditoria.PLAN_CUIDADO,
        "entidad_id": PLAN,
    }
    campos.update(cambios)
    return campos


def test_catalogo_de_acciones_es_exactamente_el_acordado() -> None:
    assert {a.value for a in AccionAuditoria} == {
        "plan.leer",
        "plan.editar",
        "consentimiento.otorgar",
        "consentimiento.revocar",
        "relevo.compartir",
        "relevo.revocar",
        "relevo.presentar",
        "relevo.canje",
        "relevo.pin_incorrecto",
        "relevo.bloqueo",
        "relevo.abrir",
        "sesion.iniciar",
        "sesion.inicio_fallido",
        "sesion.reutilizacion_detectada",
        "sesion.cerrar",
        "dispositivo.sacar",
        "dispositivo.push_registrar",
        "dispositivo.push_borrar",
        "consumo.crear",
        "consumo.editar",
        "consumo.desactivar",
        "consumo.activar",
        "consumo.eliminar",
    }


def test_catalogo_de_motivos_es_el_de_la_decision_16() -> None:
    assert {m.value for m in MotivoAuditoria} == {"salgo_unas_horas", "fin_de_semana_fuera", "turno_de_noche", "otro"}


def test_actores_y_entidades_son_los_que_se_usan_hoy() -> None:
    assert {a.value for a in ActorTipo} == {"usuario", "relevo", "sistema"}
    assert {e.value for e in EntidadAuditoria} == {
        "plan_cuidado",
        "plan_seccion",
        "consentimiento",
        "acceso_relevo",
        "usuario",
        "dispositivo",
        "perfil_consumo",
    }


@pytest.mark.parametrize(
    ("catalogo", "valor"),
    [
        pytest.param(AccionAuditoria, "plan.borrar", id="accion-desconocida"),
        pytest.param(AccionAuditoria, "PLAN.LEER", id="accion-en-mayusculas"),
        pytest.param(MotivoAuditoria, "se fue al hospital", id="motivo-texto-libre"),
        pytest.param(MotivoAuditoria, "", id="motivo-vacio"),
        pytest.param(ActorTipo, "comercio", id="actor-aun-no-usado"),
        pytest.param(EntidadAuditoria, "persona_cuidada", id="entidad-fuera-de-catalogo"),
    ],
)
def test_catalogo_rechaza_un_valor_fuera_de_el(catalogo: type, valor: str) -> None:
    with pytest.raises(ValueError):
        catalogo(valor)


def test_entrada_se_arma_con_los_enumerados() -> None:
    entrada = EntradaAuditoria(**_campos(motivo=MotivoAuditoria.TURNO_DE_NOCHE, request_id="req-sintetico-1"))

    assert entrada.accion is AccionAuditoria.PLAN_LEER
    assert entrada.motivo is MotivoAuditoria.TURNO_DE_NOCHE


def test_entrada_tiene_motivo_entidad_id_y_request_id_opcionales() -> None:
    entrada = EntradaAuditoria(**_campos(entidad_id=None))

    assert (entrada.entidad_id, entrada.motivo, entrada.request_id) == (None, None, None)


def test_entrada_solo_lleva_identificadores_sin_ip_ni_contenido() -> None:
    nombres = {c.name for c in dataclasses.fields(EntradaAuditoria)}

    assert nombres == {
        "grupo_id",
        "actor_tipo",
        "actor_ref",
        "accion",
        "entidad",
        "entidad_id",
        "motivo",
        "request_id",
        "sesiones_revocadas",
    }
    assert "ip" not in nombres
    # El momento lo pone el adaptador con el Reloj, no quien llama
    assert "ocurrido_en" not in nombres


def test_entrada_es_inmutable() -> None:
    entrada = EntradaAuditoria(**_campos())

    with pytest.raises(dataclasses.FrozenInstanceError):
        entrada.accion = AccionAuditoria.PLAN_EDITAR  # type: ignore[misc]


def test_entrada_no_acepta_un_campo_ip() -> None:
    with pytest.raises(TypeError):
        EntradaAuditoria(**_campos(ip="192.0.2.10"))


@pytest.mark.parametrize(
    "cambio",
    [
        pytest.param({"accion": "plan.leer"}, id="accion-como-str"),
        pytest.param({"motivo": "otro"}, id="motivo-como-str"),
        pytest.param({"actor_tipo": "usuario"}, id="actor-como-str"),
        pytest.param({"entidad": "plan_cuidado"}, id="entidad-como-str"),
        pytest.param({"grupo_id": None}, id="sin-grupo"),
        pytest.param({"grupo_id": str(GRUPO)}, id="grupo-como-str"),
        pytest.param({"actor_ref": None}, id="sin-actor"),
        pytest.param({"entidad_id": str(PLAN)}, id="entidad-id-como-str"),
    ],
)
def test_entrada_rechaza_str_libre_o_grupo_ausente(cambio: dict[str, Any]) -> None:
    # Aunque "plan.leer" == AccionAuditoria.PLAN_LEER, un str suelto no pasa: el catálogo es el tipo
    with pytest.raises(TypeError):
        EntradaAuditoria(**_campos(**cambio))


# --- MATU-38: acciones de la cuenta, sin grupo, y detalle acotado (RF-37) ---------------------

HUELLA = "ab" * 32


@pytest.mark.rf("RF-37")
def test_accion_de_cuenta_va_sin_grupo() -> None:
    entrada = EntradaAuditoria(
        grupo_id=None,
        actor_tipo=ActorTipo.USUARIO,
        actor_ref=USUARIO,
        accion=AccionAuditoria.SESION_INICIAR,
        entidad=EntidadAuditoria.DISPOSITIVO,
    )
    assert entrada.grupo_id is None and entrada.detalle() is None


@pytest.mark.rf("RF-37")
def test_inicio_fallido_va_sin_actor_ni_detalle() -> None:
    entrada = EntradaAuditoria(
        grupo_id=None,
        actor_tipo=ActorTipo.SISTEMA,
        actor_ref=None,
        accion=AccionAuditoria.SESION_INICIO_FALLIDO,
        entidad=EntidadAuditoria.USUARIO,
    )
    assert entrada.detalle() is None


@pytest.mark.rf("RF-37")
def test_la_entrada_no_admite_la_huella_del_email() -> None:
    # Decisión 64: la huella del email no se guarda en la auditoría
    with pytest.raises(TypeError):
        EntradaAuditoria(
            grupo_id=None,
            actor_tipo=ActorTipo.SISTEMA,
            actor_ref=None,
            accion=AccionAuditoria.SESION_INICIO_FALLIDO,
            entidad=EntidadAuditoria.USUARIO,
            huella_email=HUELLA,  # type: ignore[call-arg]
        )


@pytest.mark.rf("RF-37")
def test_sacar_dispositivo_lleva_la_cantidad() -> None:
    entrada = EntradaAuditoria(
        grupo_id=None,
        actor_tipo=ActorTipo.USUARIO,
        actor_ref=USUARIO,
        accion=AccionAuditoria.DISPOSITIVO_SACAR,
        entidad=EntidadAuditoria.DISPOSITIVO,
        sesiones_revocadas=2,
    )
    assert entrada.detalle() == {"sesiones_revocadas": 2}


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize(
    "cambio",
    [
        pytest.param({"sesiones_revocadas": 1}, id="cantidad-en-otra-accion"),
        pytest.param({"actor_tipo": ActorTipo.USUARIO}, id="usuario-sin-actor-ref"),
        pytest.param({"accion": AccionAuditoria.PLAN_LEER}, id="accion-de-familia-sin-grupo"),
        pytest.param({"sesiones_revocadas": -1, "accion": AccionAuditoria.DISPOSITIVO_SACAR}, id="cantidad-negativa"),
    ],
)
def test_detalle_y_grupo_fuera_de_lo_acotado_se_rechazan(cambio: dict[str, Any]) -> None:
    campos: dict[str, Any] = {
        "grupo_id": None,
        "actor_tipo": ActorTipo.SISTEMA,
        "actor_ref": None,
        "accion": AccionAuditoria.SESION_INICIO_FALLIDO,
        "entidad": EntidadAuditoria.USUARIO,
    }
    campos.update(cambio)
    with pytest.raises(TypeError):
        EntradaAuditoria(**campos)
