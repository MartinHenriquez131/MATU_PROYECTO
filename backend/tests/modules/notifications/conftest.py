"""Fixtures de los avisos (MATU-41): una familia sintética, su evento QuiebreProximo y el consumidor con
enviadores en memoria, contra PostgreSQL como matu_app.

El reloj parte el 20-10-2026 a las 12:00 UTC, 09:00 en Santiago: ya se puede avisar. El perfil por omisión de
la fábrica (24 unidades a 4 por día, anotado ese día) se acaba en 6 días y avisa con 7, así que el trabajo
diario de MATU-37 materializa su alerta y publica el evento. Solo datos sintéticos.
"""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import psycopg
import pytest

from app.core.db import fabrica_sesiones
from app.modules.consumption.infrastructure.tarea_quiebres import recalcular_grupo
from app.modules.notifications.application.avisos import ConsumidorQuiebreProximo
from app.modules.notifications.infrastructure.repositorio_avisos import UnidadAvisosSQL
from app.shared.outbox import EventoTomado, ResultadoConsumo
from tests.base_datos import DSN
from tests.dobles.enviadores_en_memoria import EnviadorCorreoEnMemoria, EnviadorPushEnMemoria
from tests.dobles.reloj_fijo import RelojFijo
from tests.fabricas import Fabrica, FamiliaCreada, UsuarioCreado

ORIGEN = "https://matu.example"
INICIO = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def filas(sql: str, *parametros: Any) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchall()


def ejecutar(sql: str, *parametros: Any) -> None:
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute(sql, parametros)


@dataclass
class Avisado:
    """Lo que dejó el trabajo diario: el perfil, la alerta y el evento, tal como lo toma el publicador."""

    perfil_id: uuid.UUID
    alerta_id: uuid.UUID
    evento: EventoTomado


@dataclass
class EntornoAvisos:
    fabrica: Fabrica
    reloj: RelojFijo
    correo: EnviadorCorreoEnMemoria = field(default_factory=EnviadorCorreoEnMemoria)
    push: EnviadorPushEnMemoria = field(default_factory=EnviadorPushEnMemoria)

    def consumidor(self) -> ConsumidorQuiebreProximo:
        return ConsumidorQuiebreProximo(
            unidad=UnidadAvisosSQL(fabrica_sesiones()),
            correo=self.correo,
            push=self.push,
            reloj=self.reloj,
            origen_web=ORIGEN,
        )

    def familia(self, *, calidad: str = "titular", otorgado_en: datetime | None = None) -> FamiliaCreada:
        """Admin, cuidador, pagador y observador, con la autorización para consumo vigente."""
        familia = self.fabrica.familia(miembros=("cuidador", "pagador", "observador"))
        self.fabrica.autorizacion_consumo(
            familia.persona, otorgante=familia.admin, calidad=calidad, otorgado_en=otorgado_en or self.reloj.ahora()
        )
        return familia

    def avisar(self, familia: FamiliaCreada) -> Avisado:
        perfil = self.fabrica.perfil_consumo(familia.persona)
        assert recalcular_grupo(fabrica_sesiones(), familia.grupo.id, self.reloj).materializadas == 1
        [(alerta_id,)] = filas("SELECT id FROM alerta_quiebre WHERE perfil_id = %s", perfil)
        [(evento_id, grupo_id, tipo, payload, intentos)] = filas(
            "SELECT id, grupo_id, tipo, payload, intentos FROM evento_outbox WHERE grupo_id = %s", familia.grupo.id
        )
        return Avisado(perfil, alerta_id, EventoTomado(evento_id, grupo_id, tipo, payload, intentos))

    def consumir(self, avisado: Avisado) -> ResultadoConsumo:
        return self.consumidor().consumir(avisado.evento)

    def dispositivo(self, usuario: UsuarioCreado, token: str | None = None) -> uuid.UUID:
        """Un dispositivo web del usuario, con push_token (sintético) si se entrega."""
        dispositivo_id = uuid.uuid4()
        ejecutar(
            "INSERT INTO dispositivo (id, usuario_id, plataforma, push_token) VALUES (%s, %s, 'web', %s)",
            dispositivo_id, usuario.id, token,
        )
        return dispositivo_id

    def preferencia(self, usuario: UsuarioCreado, canal: str, activo: bool) -> None:
        ejecutar(
            "INSERT INTO preferencia_notificacion (usuario_id, tipo_evento, canal, activo)"
            " VALUES (%s, 'quiebre_proximo', %s, %s)",
            usuario.id, canal, activo,
        )

    def avisos(self, familia: FamiliaCreada) -> dict[tuple[uuid.UUID, str], tuple[str, str | None]]:
        """(usuario_id, canal) -> (estado, error) de las notificaciones del grupo."""
        return {
            (u, c): (e, err)
            for u, c, e, err in filas(
                "SELECT usuario_id, canal, estado, error FROM notificacion WHERE grupo_id = %s", familia.grupo.id
            )
        }

    def estado_alerta(self, avisado: Avisado) -> tuple[str, bool]:
        [(estado, notificada)] = filas(
            "SELECT estado, notificada_en IS NOT NULL FROM alerta_quiebre WHERE id = %s", avisado.alerta_id
        )
        return estado, notificada


@pytest.fixture
def entorno_avisos() -> Iterator[EntornoAvisos]:
    fabrica = Fabrica()
    try:
        yield EntornoAvisos(fabrica=fabrica, reloj=RelojFijo(INICIO))
    finally:
        fabrica.limpiar()
