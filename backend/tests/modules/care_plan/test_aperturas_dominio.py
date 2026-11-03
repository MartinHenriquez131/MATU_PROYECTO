"""MATU-45 · Ver quién abrió la ficha (RF-08): reglas puras, caso de uso con dobles y cursor, sin base."""

import base64
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from app.core.errores import ErrorMATU
from app.modules.care_plan.api.router_relevo import codificar_cursor_apertura, decodificar_cursor_apertura
from app.modules.care_plan.application.aperturas import listar_aperturas
from app.modules.care_plan.application.ficha import PeticionFicha
from app.modules.care_plan.application.ports import FilaApertura, PlanGuardado, PosicionApertura
from app.modules.care_plan.domain.aperturas import ACCIONES_DE_APERTURA, TipoApertura, tipo_de_accion

pytestmark = pytest.mark.rf("RF-08")

AHORA = datetime(2026, 10, 31, 13, 2, tzinfo=UTC)
PLAN = uuid.UUID("00000000-0000-4000-8000-0000000002a0")
ACCESO = uuid.UUID("2e8a6b40-0000-4000-8000-0000000000b1")
PETICION = PeticionFicha(
    grupo_id=uuid.uuid4(), usuario_id=uuid.uuid4(), persona_cuidada_id=uuid.uuid4(), request_id=None
)


# --- Dominio ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("accion", "tipo"), [
    ("relevo.presentar", TipoApertura.PRESENTACION),
    ("relevo.abrir", TipoApertura.APERTURA),
    ("relevo.pin_incorrecto", TipoApertura.PIN_INCORRECTO),
    ("relevo.bloqueo", TipoApertura.BLOQUEO),
])
def test_cada_accion_del_relevo_tiene_su_tipo(accion: str, tipo: TipoApertura) -> None:
    assert tipo_de_accion(accion) is tipo


@pytest.mark.parametrize("accion", ["relevo.canje", "relevo.compartir", "relevo.revocar", "plan.leer", "x", ""])
def test_otras_acciones_no_se_listan(accion: str) -> None:
    assert tipo_de_accion(accion) is None


def test_el_enumerado_es_el_del_contrato() -> None:
    assert [t.value for t in TipoApertura] == ["presentacion", "apertura", "pin_incorrecto", "bloqueo"]
    assert ACCIONES_DE_APERTURA == ("relevo.presentar", "relevo.abrir", "relevo.pin_incorrecto", "relevo.bloqueo")


# --- Caso de uso con dobles ------------------------------------------------------------------------------


@dataclass
class FichasFalsas:
    plan: PlanGuardado | None

    def obtener_plan(self, persona_cuidada_id: uuid.UUID) -> PlanGuardado | None:
        return self.plan


@dataclass
class AperturasFalsas:
    filas: list[FilaApertura]
    pedidos: list[tuple[uuid.UUID, tuple[str, ...], PosicionApertura | None, int]] = field(default_factory=list)

    def listar(
        self, plan_id: uuid.UUID, acciones: tuple[str, ...], despues_de: PosicionApertura | None, limite: int
    ) -> list[FilaApertura]:
        self.pedidos.append((plan_id, acciones, despues_de, limite))
        return self.filas[:limite]


def _fila(i: int, accion: str = "relevo.abrir") -> FilaApertura:
    return FilaApertura(
        id=100 - i, ocurrido_en=AHORA - timedelta(minutes=i), accion=accion, acceso_id=ACCESO, nombre_relevo="Rosa"
    )


def _plan() -> PlanGuardado:
    return PlanGuardado(id=PLAN)


def test_sin_plan_no_hay_aperturas_ni_consulta() -> None:
    repo = AperturasFalsas([_fila(0)])
    pagina = listar_aperturas(PETICION, FichasFalsas(None), repo, None, 20)  # type: ignore[arg-type]
    assert pagina.aperturas == [] and pagina.siguiente is None
    assert repo.pedidos == []


def test_pide_uno_mas_y_traduce_el_tipo() -> None:
    repo = AperturasFalsas([_fila(0, "relevo.abrir"), _fila(1, "relevo.pin_incorrecto"), _fila(2, "relevo.presentar")])
    pagina = listar_aperturas(PETICION, FichasFalsas(_plan()), repo, None, 20)  # type: ignore[arg-type]
    assert repo.pedidos == [(PLAN, ACCIONES_DE_APERTURA, None, 21)]
    assert [a.tipo for a in pagina.aperturas] == [
        TipoApertura.APERTURA, TipoApertura.PIN_INCORRECTO, TipoApertura.PRESENTACION,
    ]
    assert all(a.acceso_id == ACCESO and a.nombre_relevo == "Rosa" for a in pagina.aperturas)
    assert pagina.siguiente is None


def test_pagina_llena_entrega_la_posicion_de_la_ultima() -> None:
    repo = AperturasFalsas([_fila(i) for i in range(3)])
    pagina = listar_aperturas(PETICION, FichasFalsas(_plan()), repo, None, 2)  # type: ignore[arg-type]
    assert len(pagina.aperturas) == 2
    assert pagina.siguiente == PosicionApertura(ocurrido_en=AHORA - timedelta(minutes=1), id=99)


def test_una_accion_ajena_no_se_muestra() -> None:
    repo = AperturasFalsas([_fila(0, "relevo.canje"), _fila(1)])
    pagina = listar_aperturas(PETICION, FichasFalsas(_plan()), repo, None, 20)  # type: ignore[arg-type]
    assert [a.tipo for a in pagina.aperturas] == [TipoApertura.APERTURA]


# --- Cursor opaco ----------------------------------------------------------------------------------------


def test_cursor_ida_y_vuelta() -> None:
    posicion = PosicionApertura(ocurrido_en=AHORA.replace(microsecond=123456), id=42)
    cursor = codificar_cursor_apertura(posicion)
    assert "=" not in cursor and len(cursor) <= 200
    assert decodificar_cursor_apertura(cursor) == posicion


def _b64(texto: str) -> str:
    return base64.urlsafe_b64encode(texto.encode()).rstrip(b"=").decode()


@pytest.mark.parametrize("cursor", [
    "%%%", _b64("sin-separador"), _b64("2026-10-31T13:02:00|42"), _b64("2026-10-31T13:02:00+00:00|abc"),
    _b64("2026-10-31T13:02:00+00:00|0"), _b64("2026-10-31T13:02:00+00:00|-3"), _b64("a|b|c"),
])
def test_cursor_invalido_es_422_sin_repetir_el_valor(cursor: str) -> None:
    with pytest.raises(ErrorMATU) as error:
        decodificar_cursor_apertura(cursor)
    assert error.value.status == 422
    assert cursor not in str(error.value.__dict__)
