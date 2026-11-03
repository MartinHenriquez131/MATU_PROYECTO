"""Fixtures del consumo (MATU-36): la API contra PostgreSQL con una familia sintética.

Las cuentas, el grupo y la persona los siembran las fábricas de MATU-30 con el mismo pepper que la
API, así que cada miembro inicia sesión por POST /v1/sesiones. El reloj es el RelojFijo de entorno_iam
(20-10-2026 12:00 UTC, 09:00 en Santiago): emite los tokens, decide la vigencia de la autorización y
fija "hoy".
"""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest

from tests.fabricas import Fabrica, FamiliaCreada, UsuarioCreado
from tests.modules.conftest import EntornoIam

RUTA = "/v1/personas-cuidadas/{}/consumo"


@dataclass
class EntornoConsumo:
    iam: EntornoIam
    fabrica: Fabrica
    tokens: dict[uuid.UUID, str] = field(default_factory=dict)

    def familia(self, *, con_autorizacion: bool = True, **opciones: Any) -> FamiliaCreada:
        familia = self.fabrica.familia(**opciones)
        if con_autorizacion:
            self.fabrica.autorizacion_consumo(familia.persona, otorgante=familia.admin)
        return familia

    def token(self, usuario: UsuarioCreado) -> str:
        if usuario.id not in self.tokens:
            assert usuario.contrasena is not None
            respuesta = self.iam.iniciar_sesion(email=usuario.email, contrasena=usuario.contrasena)
            assert respuesta.status_code == 200, respuesta.text
            self.tokens[usuario.id] = respuesta.json()["access_token"]
        return self.tokens[usuario.id]

    def cabeceras(self, usuario: UsuarioCreado, grupo: uuid.UUID | str, **extra: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token(usuario)}", "X-Grupo-Id": str(grupo), **extra}

    def pedir(
        self,
        metodo: str,
        usuario: UsuarioCreado,
        familia: FamiliaCreada,
        sufijo: str = "",
        *,
        persona: uuid.UUID | str | None = None,
        json: Any = None,
        params: dict[str, Any] | None = None,
        **cabeceras: str,
    ) -> Any:
        ruta = RUTA.format(persona or familia.persona.id) + sufijo
        return self.iam.cliente.request(
            metodo,
            ruta,
            json=json,
            params=params,
            headers=self.cabeceras(usuario, familia.grupo.id, **{k.replace("_", "-"): v for k, v in cabeceras.items()}),
        )

    def crear(self, usuario: UsuarioCreado, familia: FamiliaCreada, **cuerpo: Any) -> Any:
        base: dict[str, Any] = {"nombre_libre": "Pañal adulto M", "tasa_unidades": 4, "stock_unidades": 24}
        base.update(cuerpo)
        return self.pedir("POST", usuario, familia, json=base)


@pytest.fixture
def entorno_consumo(entorno_iam: EntornoIam) -> Iterator[EntornoConsumo]:
    fabrica = Fabrica(pepper=entorno_iam.pepper)
    try:
        yield EntornoConsumo(iam=entorno_iam, fabrica=fabrica)
    finally:
        fabrica.limpiar()
