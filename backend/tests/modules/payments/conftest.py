"""Fixtures del pago con base (MATU-62): las del pedido (MATU-61) más el router del pago y la PasarelaFalsa.

El router del pago es capa 3 y crear_app lo monta solo con CAPA3_HABILITADA: aquí se agrega con rutas_de_prueba, junto
con los del pedido. La vuelta (POST /v1/pagos/retorno) la monta crear_app siempre (D-62-17). La pasarela es una
PasarelaFalsa nueva por prueba: nunca se llama a Transbank desde las pruebas.
"""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI

from app.modules.care_circle.api.router_autorizaciones import finalidades_activas
from app.modules.care_circle.domain.personas import FINALIDAD_DESPACHO
from app.modules.care_circle.domain.retiro import finalidades_retirables
from app.modules.care_circle.infrastructure.efectos_retiro import registrar_efecto
from app.modules.catalog.infrastructure.catalogo_simulado import CatalogoComercioSimulado
from app.modules.ordering.api.router import obtener_catalogo_comercio_pedido, obtener_costo_envio
from app.modules.ordering.api.router import router as router_pedidos
from app.modules.ordering.api.router_condiciones import router as router_condiciones
from app.modules.ordering.infrastructure.condiciones import condiciones_vigentes
from app.modules.ordering.infrastructure.efecto_retiro import EfectoRetiroPedidos
from app.modules.payments.api.router import router as router_pago
from app.modules.payments.infrastructure.pasarela import obtener_pasarela
from app.modules.payments.infrastructure.pasarela_falsa import PasarelaFalsa
from tests.fabricas import FamiliaCreada, UsuarioCreado
from tests.modules.catalog.conftest import catalogo_sintetico  # noqa: F401
from tests.modules.ordering.conftest import (  # noqa: F401
    COSTO_ENVIO,
    EntornoPedido,
    Existencias,
    entorno_pedido,
    existencias,
)


@pytest.fixture
def pasarela_falsa() -> PasarelaFalsa:
    return PasarelaFalsa()


@pytest.fixture
def rutas_de_prueba(existencias: Existencias, pasarela_falsa: PasarelaFalsa) -> Callable[[FastAPI], None]:  # noqa: F811
    def montar(app: FastAPI) -> None:
        app.include_router(router_pedidos, prefix="/v1")
        app.include_router(router_condiciones, prefix="/v1")
        app.include_router(router_pago, prefix="/v1")
        registrar_efecto(FINALIDAD_DESPACHO, EfectoRetiroPedidos)
        app.dependency_overrides[finalidades_activas] = lambda: finalidades_retirables(True)
        app.dependency_overrides[obtener_costo_envio] = lambda: COSTO_ENVIO
        app.dependency_overrides[obtener_catalogo_comercio_pedido] = lambda: CatalogoComercioSimulado(
            existencias.por_comercio
        )
        app.dependency_overrides[obtener_pasarela] = lambda: pasarela_falsa

    return montar


def cuerpo_pagar() -> dict[str, Any]:
    vigentes = condiciones_vigentes()
    return {"acepta_condiciones": True, "condiciones": {"version": vigentes.version, "huella": vigentes.huella}}


def pedido_confirmado(e: EntornoPedido, familia: FamiliaCreada | None = None) -> tuple[FamiliaCreada, dict[str, Any]]:
    """Una familia con despacho y dirección, y un pedido de 2 pañales con el total confirmado."""
    familia = e.lista_para_pedir(familia or e.fabrica.familia())
    e.hay("panal", "uno")
    creado = e.crear(familia, [{"oferta_id": e.oferta("panal", "uno"), "cantidad": 2}])
    assert creado.status_code == 201, creado.text
    confirmado = e.confirmar(familia, creado.json()["id"])
    assert confirmado.status_code == 200, confirmado.text
    return familia, confirmado.json()


def pagar(
    e: EntornoPedido,
    familia: FamiliaCreada,
    pedido: dict[str, Any],
    usuario: UsuarioCreado | None = None,
    *,
    etag: str | None = None,
    clave: str | None = None,
    cuerpo: dict[str, Any] | None = None,
) -> Any:
    return e.pedir(
        "POST",
        f"/v1/pedidos/{pedido['id']}/pagar",
        usuario or familia.admin,
        familia,
        cuerpo_pagar() if cuerpo is None else cuerpo,
        **{"Idempotency-Key": clave or e.clave(), "If-Match": etag or pedido["etag"]},
    )


def sin_sesion_volver(e: EntornoPedido, cuerpo: dict[str, Any], token: str | None = None) -> Any:
    cabeceras = {"Authorization": f"Bearer {token}"} if token else {}
    return e.iam.cliente.post("/v1/pagos/retorno", json=cuerpo, headers=cabeceras)


def nuevo_id() -> str:
    return str(uuid.uuid4())
