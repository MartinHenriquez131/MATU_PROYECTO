"""MATU-80 · Los seis recorridos críticos de MATU-64, de punta a punta contra la API (objetivo específico 7).

Cada recorrido hace por la API lo que haría la persona: crea su cuenta, su grupo y la persona cuidada, da las
autorizaciones, anota, pide, paga y retira. La base solo se toca para preparar lo que ninguna ruta crea (el catálogo,
la cuenta del comercio y la de operación) y para leer el evento que el publicador le entregaría al consumidor.

Los dobles son los de la estrategia de pruebas, sección 4: el RelojFijo de entorno_iam (20-10-2026 09:00 en
Santiago), la PasarelaFalsa (nunca Transbank), los enviadores en memoria (correo y push simulados), la custodia de
claves en memoria y el comercio simulado (CatalogoComercioSimulado). La API es la de crear_app, con la capa 3 montada
como lo haría incluir_capa_3 (tests/modules/backoffice/conftest.py), sin depender de CAPA3_HABILITADA del .env.

Lo que el recorrido crea por la API se anota en la fábrica del pedido, que lo borra al terminar: la cuenta y el grupo,
y con el grupo todo lo que cuelga de él (persona, autorizaciones, ficha, insumos, pedidos y pago). Solo datos
sintéticos: correos de example.com y nombres inventados.
"""

import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any, cast

import pytest
from fastapi import FastAPI

from app.modules.care_circle.api.router_personas import obtener_politica_version
from app.modules.care_circle.domain.declaraciones import huella_declaracion_pedidos
from app.modules.care_circle.domain.personas import CalidadOtorgante
from app.modules.care_plan.api.dependencias import obtener_custodia
from app.modules.catalog.api.router import obtener_catalogo_comercio
from app.modules.catalog.api.router import router as router_catalogo
from app.modules.catalog.infrastructure.catalogo_simulado import CatalogoComercioSimulado
from app.modules.payments.infrastructure.pasarela_falsa import PasarelaFalsa
from tests.dobles.custodia_en_memoria import CustodiaEnMemoria
from tests.fabricas import UsuarioCreado
from tests.modules.backoffice.conftest import Despacho, despacho  # noqa: F401
from tests.modules.backoffice.conftest import rutas_de_prueba as rutas_del_despacho
from tests.modules.catalog.conftest import catalogo_sintetico  # noqa: F401
from tests.modules.conftest import EntornoIam, entorno_iam  # noqa: F401
from tests.modules.ordering.conftest import COSTO_ENVIO, Existencias, entorno_pedido, existencias  # noqa: F401
from tests.modules.payments.conftest import cuerpo_pagar, pasarela_falsa  # noqa: F401
from tests.politica import VERSION_PRUEBAS

__all__ = ["COSTO_ENVIO", "FamiliaApi", "Recorrido"]

DIRECCION = {"calle": "Calle de Prueba", "numero": "123", "depto": "4B", "comuna": "Comuna Sintética"}
TELEFONO_CONTACTO = "+56 9 5555 0177"


@pytest.fixture
def rutas_de_prueba(
    existencias: Existencias,  # noqa: F811
    pasarela_falsa: PasarelaFalsa,  # noqa: F811
    custodia: CustodiaEnMemoria,
) -> Callable[[FastAPI], None]:
    """La capa 3 completa (pedido, pago, comercio, operación y la familia después de pagar) más el catálogo, con el
    comercio simulado, la pasarela falsa y la custodia en memoria."""
    montar_despacho = rutas_del_despacho.__wrapped__(existencias, pasarela_falsa)  # type: ignore[attr-defined]

    def montar(app: FastAPI) -> None:
        montar_despacho(app)
        app.include_router(router_catalogo, prefix="/v1")
        app.dependency_overrides[obtener_catalogo_comercio] = lambda: CatalogoComercioSimulado(existencias.por_comercio)
        app.dependency_overrides[obtener_custodia] = lambda: custodia
        # La versión de la política la fija el servidor: la de las pruebas, sin depender del .env del equipo
        app.dependency_overrides[obtener_politica_version] = lambda: VERSION_PRUEBAS

    return montar


@dataclass(frozen=True)
class FamiliaApi:
    """Lo que dejó el alta por la API: la cuenta (con su contraseña sintética, para entrar), el grupo y la persona."""

    cuenta: UsuarioCreado
    grupo_id: uuid.UUID
    persona_id: uuid.UUID


@dataclass
class Recorrido:
    """La persona frente a la API. ``d`` trae el comercio y operación (MATU-63), y ``d.e`` el pedido (MATU-61)."""

    d: Despacho
    claves: list[str] = field(default_factory=list)

    @property
    def iam(self) -> EntornoIam:
        return self.d.e.iam

    @property
    def app(self) -> FastAPI:
        return cast(FastAPI, self.iam.cliente.app)

    def logs(self) -> str:
        return self.iam.salida_logs.getvalue()

    # --- Recorrido 1: la cuenta, el grupo y la persona cuidada -------------------------------------------------

    def crear_cuenta(self, nombre: str = "Carmen Sintética") -> UsuarioCreado:
        email = f"cuidadora.{uuid.uuid4().hex[:12]}@example.com"
        contrasena = f"clave-{uuid.uuid4().hex[:16]}"
        registro = self.iam.registrar(nombre=nombre, email=email, contrasena=contrasena)
        assert registro.status_code == 201, registro.text
        cuenta = UsuarioCreado(id=uuid.UUID(registro.json()["id"]), nombre=nombre, email=email, contrasena=contrasena)
        self.d.e.fabrica.anotar("usuario", cuenta.id)
        return cuenta

    def cabeceras(self, cuenta: UsuarioCreado, grupo: uuid.UUID | None = None, **extra: str) -> dict[str, str]:
        cabeceras = {"Authorization": f"Bearer {self.d.e.token(cuenta)}", **extra}
        if grupo is not None:
            cabeceras["X-Grupo-Id"] = str(grupo)
        return cabeceras

    def crear_grupo(self, cuenta: UsuarioCreado) -> uuid.UUID:
        r = self.iam.cliente.post("/v1/grupos", json={"nombre": "Familia Sintética"}, headers=self.cabeceras(cuenta))
        assert r.status_code == 201, r.text
        grupo_id = uuid.UUID(r.json()["id"])
        # Después de la cuenta: limpiar() borra en orden inverso, primero el grupo con todo lo suyo
        self.d.e.fabrica.anotar("grupo_familiar", grupo_id)
        return grupo_id

    def dar_de_alta(self, cuenta: UsuarioCreado, grupo_id: uuid.UUID) -> Any:
        """POST de la persona cuidada, como titular que se autoriza a sí misma, con su dirección de entrega."""
        cuerpo = {
            "nombre": "Elena Ficticia Rojas",
            "nombre_pila": "Elena",
            "nivel_apoyo": "apoyo_parcial",
            "calidad_otorgante": "titular",
            "direccion": DIRECCION,
        }
        return self.iam.cliente.post(
            f"/v1/grupos/{grupo_id}/personas-cuidadas", json=cuerpo, headers=self.cabeceras(cuenta, grupo_id)
        )

    def familia(self) -> FamiliaApi:
        """El recorrido 1 hasta la persona cuidada, para los recorridos que parten de una familia ya creada."""
        cuenta = self.crear_cuenta()
        grupo_id = self.crear_grupo(cuenta)
        alta = self.dar_de_alta(cuenta, grupo_id)
        assert alta.status_code == 201, alta.text
        return FamiliaApi(cuenta=cuenta, grupo_id=grupo_id, persona_id=uuid.UUID(alta.json()["id"]))

    # --- Peticiones de la familia ------------------------------------------------------------------------------

    def pedir(self, f: FamiliaApi, metodo: str, ruta: str, json: Any = None, **cabeceras: str) -> Any:
        return self.iam.cliente.request(
            metodo, ruta, json=json, headers=self.cabeceras(f.cuenta, f.grupo_id, **cabeceras)
        )

    def de_la_persona(self, f: FamiliaApi, metodo: str, sufijo: str, json: Any = None, **cabeceras: str) -> Any:
        return self.pedir(f, metodo, f"/v1/personas-cuidadas/{f.persona_id}{sufijo}", json, **cabeceras)

    def clave(self) -> str:
        """Una Idempotency-Key nueva, como la que genera la pantalla por cada intento."""
        self.claves.append(f"clave-e2e-{uuid.uuid4().hex}")
        return self.claves[-1]

    def autorizar(self, f: FamiliaApi, finalidad: str) -> Any:
        cuerpo: dict[str, Any] = {"finalidad": finalidad, "calidad_otorgante": "titular"}
        if finalidad == "despacho":
            # La huella del texto exacto de la declaración que la pantalla mostró (MATU-61, P13)
            cuerpo["huella_declaracion"] = huella_declaracion_pedidos(CalidadOtorgante.TITULAR)
        return self.de_la_persona(f, "POST", "/consentimientos", cuerpo)

    def anotar_insumo(self, f: FamiliaApi, **cuerpo: Any) -> dict[str, Any]:
        r = self.de_la_persona(f, "POST", "/consumo", cuerpo)
        assert r.status_code == 201, r.text
        return dict(r.json())

    # --- Recorrido 5: el pedido desde la lista y el pago -------------------------------------------------------

    def pagar_desde_la_lista(self, f: FamiliaApi) -> tuple[dict[str, Any], str, int]:
        """Desde una familia con su lista: arma el pedido con lo sugerido, confirma el total y lo paga con la
        PasarelaFalsa. Devuelve el pedido confirmado, el token de la venta y el total que la familia vio."""
        e = self.d.e
        assert self.autorizar(f, "consumo").status_code == 201
        assert self.autorizar(f, "despacho").status_code == 201
        producto_id = str(e.catalogo.productos["panal"])
        # 24 pañales a 4 por día: se acaban en 6 días y avisa con 7. El producto es del catálogo (envases de 30)
        self.anotar_insumo(f, producto_id=producto_id, tasa_unidades=4, stock_unidades=24)

        # La lista sugiere cuánto comprar para 30 días (lo que falta: 120 - 24) y dice qué producto es
        lista = self.de_la_persona(f, "GET", "/consumo/lista")
        assert lista.status_code == 200, lista.text
        [linea] = lista.json()["items"]
        assert (linea["producto_id"], linea["unidades_sugeridas"]) == (producto_id, 96)

        # En el catálogo elige el comercio que lo tiene, con su precio exacto
        e.hay("panal", "uno")
        catalogo = self.iam.cliente.get("/v1/catalogo", headers=self.cabeceras(f.cuenta))
        assert catalogo.status_code == 200, catalogo.text
        [producto] = [p for c in catalogo.json()["categorias"] for p in c["productos"] if p["id"] == producto_id]
        [oferta] = [o for o in producto["comercios"] if o["disponible"]]
        assert oferta["oferta_id"] == e.oferta("panal", "uno")
        precio = oferta["precio"]
        # La pantalla lleva lo sugerido a envases del catálogo, hacia arriba (cantidadDesdeLista de web/, MATU-61
        # 6.3): 96 pañales en paquetes de 30 son 4 paquetes
        assert linea["unidad"] == producto["unidad"]
        envases = -(-linea["unidades_sugeridas"] // producto["unidades_por_envase"])

        creado = self.de_la_persona(
            f,
            "POST",
            "/pedidos",
            {"lineas": [{"oferta_id": oferta["oferta_id"], "cantidad": envases}]},
            **{"Idempotency-Key": self.clave()},
        )
        assert creado.status_code == 201, creado.text
        confirmado = self.pedir(
            f,
            "POST",
            f"/v1/pedidos/{creado.json()['id']}/confirmar",
            {"telefono_contacto": TELEFONO_CONTACTO},
            **{"Idempotency-Key": self.clave()},
        )
        assert confirmado.status_code == 200, confirmado.text
        pedido = dict(confirmado.json())
        total = precio * envases + COSTO_ENVIO

        pago = self.pedir(
            f,
            "POST",
            f"/v1/pedidos/{pedido['id']}/pagar",
            cuerpo_pagar(),
            **{"Idempotency-Key": self.clave(), "If-Match": pedido["etag"]},
        )
        assert pago.status_code == 201, pago.text
        token = pago.json()["token"]
        # La persona paga en el formulario (falso) de Webpay, y Webpay la devuelve a MATU, sin la sesión
        self.d.pasarela.pagar(token)
        vuelta = self.iam.cliente.post("/v1/pagos/retorno", json={"token_ws": token})
        assert vuelta.status_code == 200, vuelta.text
        assert vuelta.json()["resultado"] == "aprobado"
        return pedido, token, total

    def tus_pedidos(self, f: FamiliaApi) -> list[dict[str, Any]]:
        r = self.de_la_persona(f, "GET", "/pedidos")
        assert r.status_code == 200, r.text
        return list(r.json()["items"])


@pytest.fixture
def recorrido(despacho: Despacho) -> Iterator[Recorrido]:  # noqa: F811
    yield Recorrido(despacho)
