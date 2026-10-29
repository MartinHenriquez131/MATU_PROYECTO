"""Fixtures de la ficha de relevo (MATU-12): la API contra PostgreSQL con una familia sintética.

- Las cuentas, el grupo, la persona y su consentimiento los siembran las fábricas de MATU-30, con el
  mismo pepper que la API, así que cada miembro inicia sesión por POST /v1/sesiones.
- La custodia es CustodiaEnMemoria (fixture ``custodia``) por override de obtener_custodia: la
  misma que usa la fábrica para escribir fichas ya cifradas. Nunca se usa la KEK de un .env.
- La auditoría es un espía del puerto AuditoriaFicha: las pruebas de RF-08 lo quitan para usar la real.
- El reloj es el RelojFijo de entorno_iam: emite y valida los tokens y decide la vigencia del
  consentimiento.
- ``escribir`` envía por omisión la precondición correcta de MATU-13 (If-None-Match: * si el campo
  nunca se escribió, If-Match con su versión si existe), leída como superusuario: no pasa por la API
  ni registra plan.leer. Las pruebas de RF-04 pasan ``precondicion`` explícita (None: sin cabeceras).
"""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, cast

import psycopg
import pytest
from fastapi import FastAPI

from app.modules.care_plan.api.dependencias import obtener_auditoria_ficha, obtener_custodia
from app.modules.care_plan.application.ports import EventoFicha
from tests.base_datos import DSN
from tests.dobles.custodia_en_memoria import CustodiaEnMemoria
from tests.fabricas import Fabrica, FamiliaCreada, UsuarioCreado
from tests.modules.conftest import EntornoIam

RUTA_FICHA = "/v1/personas-cuidadas/{}/plan/ficha"

# Valor por omisión de ``precondicion`` en EntornoFicha.escribir: la correcta según la base
AUTO: Any = object()


def precondicion_correcta(persona: uuid.UUID | str, campo: str) -> dict[str, str]:
    """If-Match con la versión guardada del campo, o If-None-Match: * si nunca se escribió."""
    with psycopg.connect(DSN) as cx:
        fila = cx.execute(
            "SELECT s.version FROM plan_seccion s JOIN plan_cuidado p ON p.id = s.plan_id"
            " WHERE p.persona_cuidada_id::text = %s AND s.tipo = %s",
            (str(persona), campo),
        ).fetchone()
    return {"If-None-Match": "*"} if fila is None else {"If-Match": f'"v{fila[0]}"'}


@dataclass
class AuditoriaEspia:
    """Doble del puerto AuditoriaFicha: anota cada evento, en orden."""

    lecturas: list[EventoFicha] = field(default_factory=list)
    ediciones: list[EventoFicha] = field(default_factory=list)

    def registrar_lectura(self, evento: EventoFicha) -> None:
        self.lecturas.append(evento)

    def registrar_edicion(self, evento: EventoFicha) -> None:
        self.ediciones.append(evento)


@dataclass
class EntornoFicha:
    iam: EntornoIam
    fabrica: Fabrica
    custodia: CustodiaEnMemoria
    auditoria: AuditoriaEspia
    tokens: dict[uuid.UUID, str] = field(default_factory=dict)

    @property
    def app(self) -> FastAPI:
        return cast(FastAPI, self.iam.cliente.app)

    def familia(self, **opciones: Any) -> FamiliaCreada:
        return self.fabrica.familia(**opciones)

    def token(self, usuario: UsuarioCreado) -> str:
        if usuario.id not in self.tokens:
            assert usuario.contrasena is not None
            respuesta = self.iam.iniciar_sesion(email=usuario.email, contrasena=usuario.contrasena)
            assert respuesta.status_code == 200, respuesta.text
            self.tokens[usuario.id] = respuesta.json()["access_token"]
        return self.tokens[usuario.id]

    def _cabeceras(self, usuario: UsuarioCreado | None, grupo: uuid.UUID | str | None) -> dict[str, str]:
        cabeceras: dict[str, str] = {}
        if usuario is not None:
            cabeceras["Authorization"] = f"Bearer {self.token(usuario)}"
        if grupo is not None:
            cabeceras["X-Grupo-Id"] = str(grupo)
        return cabeceras

    def leer(self, usuario: UsuarioCreado | None, grupo: uuid.UUID | str | None, persona: uuid.UUID | str) -> Any:
        return self.iam.cliente.get(RUTA_FICHA.format(persona), headers=self._cabeceras(usuario, grupo))

    def escribir(
        self,
        usuario: UsuarioCreado | None,
        grupo: uuid.UUID | str | None,
        persona: uuid.UUID | str,
        campo: str,
        cuerpo: Any,
        precondicion: dict[str, str] | None = AUTO,
    ) -> Any:
        ruta = RUTA_FICHA.format(persona) + f"/{campo}"
        cabeceras = self._cabeceras(usuario, grupo)
        if precondicion is AUTO:
            precondicion = precondicion_correcta(persona, campo)
        cabeceras.update(precondicion or {})
        return self.iam.cliente.put(ruta, json=cuerpo, headers=cabeceras)


@pytest.fixture
def entorno_ficha(entorno_iam: EntornoIam, custodia: CustodiaEnMemoria) -> Iterator[EntornoFicha]:
    fabrica = Fabrica(pepper=entorno_iam.pepper)
    auditoria = AuditoriaEspia()
    app = cast(FastAPI, entorno_iam.cliente.app)
    app.dependency_overrides[obtener_custodia] = lambda: custodia
    app.dependency_overrides[obtener_auditoria_ficha] = lambda: auditoria
    try:
        yield EntornoFicha(iam=entorno_iam, fabrica=fabrica, custodia=custodia, auditoria=auditoria)
    finally:
        fabrica.limpiar()
