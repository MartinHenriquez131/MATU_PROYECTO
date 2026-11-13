"""Fixtures del despacho con base (MATU-63): las del pago (MATU-62) más los routers de backoffice, una cuenta de
comercio para cada comercio del catálogo sintético y una cuenta de operación.

Las cuentas se crean como superusuario con la fábrica (la de operación con un secreto de MFA sintético: el CHECK
usuario_operacion_mfa lo exige). El enlace usuario_comercio se borra al final, antes que las cuentas y el catálogo.
"""

import secrets
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import psycopg
import pytest
from fastapi import FastAPI

from app.modules.backoffice.api.dependencias import obtener_secreto_codigo
from app.modules.backoffice.api.router_comercio import router as router_comercio
from app.modules.backoffice.api.router_familia import router as router_familia
from app.modules.backoffice.api.router_operacion import router as router_operacion
from app.modules.payments.infrastructure.pasarela_falsa import PasarelaFalsa
from tests.base_datos import DSN
from tests.fabricas import FamiliaCreada, UsuarioCreado
from tests.modules.catalog.conftest import catalogo_sintetico  # noqa: F401
from tests.modules.ordering.conftest import EntornoPedido, Existencias, entorno_pedido, existencias  # noqa: F401
from tests.modules.payments.conftest import (  # noqa: F401
    pagar,
    pasarela_falsa,
    pedido_confirmado,
    sin_sesion_volver,
)
from tests.modules.payments.conftest import rutas_de_prueba as rutas_del_pago

SECRETO_CODIGO = secrets.token_bytes(32)


@pytest.fixture
def rutas_de_prueba(existencias: Existencias, pasarela_falsa: PasarelaFalsa) -> Callable[[FastAPI], None]:  # noqa: F811
    montar_pago = rutas_del_pago.__wrapped__(existencias, pasarela_falsa)  # type: ignore[attr-defined]

    def montar(app: FastAPI) -> None:
        montar_pago(app)
        app.include_router(router_comercio, prefix="/v1")
        app.include_router(router_operacion, prefix="/v1")
        app.include_router(router_familia, prefix="/v1")
        app.dependency_overrides[obtener_secreto_codigo] = lambda: SECRETO_CODIGO

    return montar


@dataclass
class Despacho:
    e: EntornoPedido
    pasarela: PasarelaFalsa
    encargados: dict[str, UsuarioCreado] = field(default_factory=dict)
    operador: UsuarioCreado | None = None

    def sql(self, sentencia: str, *parametros: Any) -> list[tuple[Any, ...]]:
        with psycopg.connect(DSN) as cx:
            filas = cx.execute(sentencia, parametros)
            return [tuple(f) for f in filas] if filas.description else []

    def como(self, usuario: UsuarioCreado, metodo: str, ruta: str, json: Any = None, **cabeceras: str) -> Any:
        return self.e.iam.cliente.request(
            metodo, ruta, json=json, headers={"Authorization": f"Bearer {self.e.token(usuario)}", **cabeceras}
        )

    def comercio(self, clave: str, metodo: str, ruta: str, json: Any = None, **cabeceras: str) -> Any:
        return self.como(self.encargados[clave], metodo, f"/v1/comercio{ruta}", json, **cabeceras)

    def operacion(self, metodo: str, ruta: str, json: Any = None) -> Any:
        assert self.operador is not None
        return self.como(self.operador, metodo, f"/v1/operacion{ruta}", json)

    def pagado(self, familia: FamiliaCreada | None = None) -> tuple[FamiliaCreada, dict[str, Any]]:
        """Una familia con un pedido de 2 pañales del comercio «uno», pagado."""
        familia, pedido = pedido_confirmado(self.e, familia)
        token = pagar(self.e, familia, pedido).json()["token"]
        self.pasarela.pagar(token)
        assert sin_sesion_volver(self.e, {"token_ws": token}).json()["resultado"] == "aprobado"
        return familia, pedido

    def parte_de(self, pedido_id: str) -> str:
        [(parte,)] = self.sql("SELECT id FROM pedido_comercio WHERE pedido_id = %s", uuid.UUID(pedido_id))
        return str(parte)

    def estado_pedido(self, pedido_id: str) -> str:
        return str(self.sql("SELECT estado FROM pedido WHERE id = %s", uuid.UUID(pedido_id))[0][0])

    def cargo(self, pedido_id: str) -> tuple[str, int, int]:
        [(estado, cobrado, devuelto)] = self.sql(
            "SELECT estado, monto_cobrado, monto_devuelto FROM cargo WHERE pedido_id = %s", uuid.UUID(pedido_id)
        )
        return estado, int(cobrado), int(devuelto)


@pytest.fixture
def despacho(entorno_pedido: EntornoPedido, pasarela_falsa: PasarelaFalsa) -> Iterator[Despacho]:  # noqa: F811
    d = Despacho(entorno_pedido, pasarela_falsa)
    fabrica = entorno_pedido.fabrica
    for clave, comercio_id in entorno_pedido.catalogo.comercios.items():
        if clave == "suspendido":
            continue
        encargado = fabrica.usuario()
        d.sql("INSERT INTO usuario_comercio (usuario_id, comercio_id) VALUES (%s, %s)", encargado.id, comercio_id)
        d.encargados[clave] = encargado
    d.operador = fabrica.usuario()
    d.sql(
        "UPDATE usuario SET es_operacion = true, mfa_secreto_cifrado = %s WHERE id = %s",
        secrets.token_bytes(16), d.operador.id,
    )
    try:
        yield d
    finally:
        ids = [u.id for u in d.encargados.values()]
        d.sql("DELETE FROM usuario_comercio WHERE usuario_id = ANY(%s)", ids)
