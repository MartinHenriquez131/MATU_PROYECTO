"""Fixtures del pedido (MATU-61): la API con la capa 3 encendida para el pedido, un catálogo sintético y una familia
con la autorización de pedidos y la dirección.

Los routers del pedido son capa 3 y crear_app los monta solo con CAPA3_HABILITADA: aquí se agregan con
rutas_de_prueba, como lo haría incluir_capa_3, y se registra el efecto del retiro de despacho. finalidades_activas
queda con despacho (C2). El stock de cada comercio lo da un CatalogoComercioSimulado con existencias que la prueba
fija, sin red. El catálogo se siembra con catalogo_sintetico de MATU-59 y se borra después de los pedidos.
"""

import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI

from app.modules.care_circle.api.router_autorizaciones import finalidades_activas
from app.modules.care_circle.domain.declaraciones import huella_declaracion_pedidos
from app.modules.care_circle.domain.personas import FINALIDAD_DESPACHO, CalidadOtorgante
from app.modules.care_circle.domain.retiro import finalidades_retirables
from app.modules.care_circle.infrastructure.efectos_retiro import registrar_efecto
from app.modules.catalog.infrastructure.catalogo_simulado import CatalogoComercioSimulado
from app.modules.ordering.api.router import obtener_catalogo_comercio_pedido, obtener_costo_envio
from app.modules.ordering.api.router import router as router_pedidos
from app.modules.ordering.api.router_condiciones import router as router_condiciones
from app.modules.ordering.infrastructure.efecto_retiro import EfectoRetiroPedidos
from tests.fabricas import Fabrica, FamiliaCreada, UsuarioCreado
from tests.modules.catalog.conftest import CatalogoSintetico, catalogo_sintetico  # noqa: F401
from tests.modules.conftest import EntornoIam

COSTO_ENVIO = 3990
DIRECCION = {"calle": "Calle de Prueba", "numero": "123", "depto": "4B", "comuna": "Comuna Sintética"}
TELEFONO = "+56 9 5555 0177"


@dataclass
class Existencias:
    """El stock que el comercio simulado dice tener, por (comercio, producto). Sin anotar, no lo tiene."""

    por_comercio: dict[tuple[uuid.UUID, uuid.UUID], int] = field(default_factory=dict)


@pytest.fixture
def existencias() -> Existencias:
    return Existencias()


@pytest.fixture
def rutas_de_prueba(existencias: Existencias) -> Callable[[FastAPI], None]:
    def montar(app: FastAPI) -> None:
        app.include_router(router_pedidos, prefix="/v1")
        app.include_router(router_condiciones, prefix="/v1")
        registrar_efecto(FINALIDAD_DESPACHO, EfectoRetiroPedidos)
        app.dependency_overrides[finalidades_activas] = lambda: finalidades_retirables(True)
        app.dependency_overrides[obtener_costo_envio] = lambda: COSTO_ENVIO
        app.dependency_overrides[obtener_catalogo_comercio_pedido] = lambda: CatalogoComercioSimulado(
            existencias.por_comercio
        )

    return montar


@dataclass
class EntornoPedido:
    iam: EntornoIam
    fabrica: Fabrica
    catalogo: CatalogoSintetico
    existencias: Existencias
    tokens: dict[uuid.UUID, str] = field(default_factory=dict)
    claves: int = 0

    def token(self, usuario: UsuarioCreado) -> str:
        if usuario.id not in self.tokens:
            assert usuario.contrasena is not None
            respuesta = self.iam.iniciar_sesion(email=usuario.email, contrasena=usuario.contrasena)
            assert respuesta.status_code == 200, respuesta.text
            self.tokens[usuario.id] = respuesta.json()["access_token"]
        return self.tokens[usuario.id]

    def avanzar(self, tiempo: timedelta) -> None:
        """Avanza el Reloj de la API. El access token dura 15 minutos con el mismo reloj: se vuelve a entrar."""
        self.iam.reloj.avanzar(tiempo)
        self.tokens.clear()

    def clave(self) -> str:
        self.claves += 1
        return f"clave-de-prueba-{uuid.uuid4().hex}"

    def cabeceras(self, usuario: UsuarioCreado, familia: FamiliaCreada, **extra: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token(usuario)}", "X-Grupo-Id": str(familia.grupo.id), **extra}

    def pedir(
        self, metodo: str, ruta: str, usuario: UsuarioCreado, familia: FamiliaCreada, json: Any = None, **extra: str
    ) -> Any:
        return self.iam.cliente.request(metodo, ruta, headers=self.cabeceras(usuario, familia, **extra), json=json)

    def usuario(self, familia: FamiliaCreada, rol: str) -> UsuarioCreado:
        return familia.admin if rol == "admin" else familia.miembros[rol].usuario

    def oferta(self, producto: str, comercio: str) -> str:
        return str(self.catalogo.ofertas[(producto, comercio)])

    def hay(self, producto: str, comercio: str, cantidad: int = 99) -> None:
        clave = (self.catalogo.comercios[comercio], self.catalogo.productos[producto])
        self.existencias.por_comercio[clave] = cantidad

    def autorizar_pedidos(self, familia: FamiliaCreada, usuario: UsuarioCreado | None = None) -> Any:
        cuerpo = {
            "finalidad": "despacho",
            "calidad_otorgante": "titular",
            "huella_declaracion": huella_declaracion_pedidos(CalidadOtorgante.TITULAR),
        }
        return self.pedir(
            "POST",
            f"/v1/personas-cuidadas/{familia.persona.id}/consentimientos",
            usuario or familia.admin,
            familia,
            cuerpo,
        )

    def guardar_direccion(self, familia: FamiliaCreada, etag: str = '"v1"', **cambios: Any) -> Any:
        """La fábrica crea la persona con una dirección (versión 1): se cambia con If-Match."""
        return self.pedir(
            "PUT",
            f"/v1/personas-cuidadas/{familia.persona.id}/direccion",
            familia.admin,
            familia,
            {**DIRECCION, **cambios},
            **{"If-Match": etag},
        )

    def crear(
        self,
        familia: FamiliaCreada,
        lineas: list[dict[str, Any]],
        usuario: UsuarioCreado | None = None,
        clave: str | None = None,
    ) -> Any:
        return self.pedir(
            "POST",
            f"/v1/personas-cuidadas/{familia.persona.id}/pedidos",
            usuario or familia.admin,
            familia,
            {"lineas": lineas},
            **{"Idempotency-Key": clave or self.clave()},
        )

    def confirmar(
        self,
        familia: FamiliaCreada,
        pedido_id: str,
        usuario: UsuarioCreado | None = None,
        cuerpo: Any = None,
        clave: str | None = None,
    ) -> Any:
        return self.pedir(
            "POST",
            f"/v1/pedidos/{pedido_id}/confirmar",
            usuario or familia.admin,
            familia,
            {"telefono_contacto": TELEFONO} if cuerpo is None else cuerpo,
            **{"Idempotency-Key": clave or self.clave()},
        )

    def lista_para_pedir(self, familia: FamiliaCreada) -> FamiliaCreada:
        """Con la autorización de pedidos y la dirección."""
        assert self.autorizar_pedidos(familia).status_code == 201
        assert self.guardar_direccion(familia).status_code == 200
        return familia


@pytest.fixture
def entorno_pedido(
    entorno_iam: EntornoIam,
    catalogo_sintetico: CatalogoSintetico,  # noqa: F811
    existencias: Existencias,
) -> Iterator[EntornoPedido]:
    fabrica = Fabrica(pepper=entorno_iam.pepper)
    try:
        yield EntornoPedido(iam=entorno_iam, fabrica=fabrica, catalogo=catalogo_sintetico, existencias=existencias)
    finally:
        fabrica.limpiar()
