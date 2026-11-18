"""MATU-76 · P3 del QA: los valores que «no pueden faltar» se comprueban de forma explícita, no con ``assert``.

Un ``assert`` desaparece con ``python -O``. Cada prueba fuerza el caso en que el valor falta y falla sin el cambio:
antes se lanzaba ``AssertionError`` (o, con ``-O``, se seguía con ``None``). Sin base de datos: dobles en memoria.
"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import Response

from app.modules.notifications.api import router as router_avisos
from app.modules.notifications.application import avisos_pedido
from app.modules.notifications.application.ports import MiembroAviso, NotificacionLeida
from app.modules.notifications.application.preferencias import (
    PreferenciaAvisos,
    PreferenciaCanales,
    canales_del_pedido_leidos,
)
from app.modules.notifications.domain.aviso import (
    PEDIDO_ENTREGADO,
    Canal,
    CodigoAviso,
    EstadoNotificacion,
)
from app.modules.notifications.infrastructure import copia_avisos

pytestmark = pytest.mark.rf("RF-39")

SIN_PEDIDO = PreferenciaAvisos(correo=True, push=False, pedido=None)


def test_la_preferencia_leida_entrega_la_del_pedido() -> None:
    pedido = PreferenciaCanales(correo=False, push=True)
    assert canales_del_pedido_leidos(PreferenciaAvisos(correo=True, push=True, pedido=pedido)) is pedido


def test_sin_la_del_pedido_falla_con_runtimeerror_sin_datos() -> None:
    with pytest.raises(RuntimeError, match="no trae la del pedido"):
        canales_del_pedido_leidos(SIN_PEDIDO)


def test_la_vista_de_la_ruta_falla_controlada_sin_la_del_pedido() -> None:
    with pytest.raises(RuntimeError):
        router_avisos._vista(SIN_PEDIDO, Response())


def test_la_copia_de_tus_datos_falla_controlada_sin_la_del_pedido(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(copia_avisos, "leer_preferencia", lambda _repo, _usuario: SIN_PEDIDO)
    sesion = SimpleNamespace(execute=lambda _sql: SimpleNamespace(all=list))
    ctx: Any = SimpleNamespace(sesion=sesion, usuario_id=uuid.uuid4(), ahora=datetime(2026, 11, 18, tzinfo=UTC))
    with pytest.raises(RuntimeError):
        copia_avisos.avisos(ctx)


class _RepoSinCorreo:
    """El miembro sigue activo y el canal también, pero la cuenta no trae correo."""

    def __init__(self, usuario_id: uuid.UUID) -> None:
        self._miembro = MiembroAviso(usuario_id=usuario_id, rol="pagador", activo=True, preferencias={})
        self.actualizadas: list[tuple[uuid.UUID, EstadoNotificacion, CodigoAviso | None, datetime | None]] = []

    def miembro(self, _usuario_id: uuid.UUID, _tipo: str) -> MiembroAviso:
        return self._miembro

    def correo(self, _usuario_id: uuid.UUID) -> str | None:
        return None

    def destinos_push(self, _usuario_id: uuid.UUID) -> list[Any]:
        return []

    def actualizar(
        self, fila_id: uuid.UUID, estado: EstadoNotificacion, codigo: CodigoAviso | None, enviada: datetime | None
    ) -> None:
        self.actualizadas.append((fila_id, estado, codigo, enviada))


class _CorreoQueNoDebeLlamarse:
    def __init__(self) -> None:
        self.envios: list[Any] = []

    def enviar(self, envio: Any) -> Any:
        self.envios.append(envio)
        raise AssertionError("no se envía a un correo que falta")


def test_el_consumidor_omite_sin_destino_si_el_correo_falta(monkeypatch: pytest.MonkeyPatch) -> None:
    # Se fuerza que la revisión previa deje pasar la fila (no debería, pero es lo que cubría el assert)
    monkeypatch.setattr(avisos_pedido, "motivo_omision_pedido", lambda **_: None)
    usuario_id = uuid.uuid4()
    repo = _RepoSinCorreo(usuario_id)
    correo = _CorreoQueNoDebeLlamarse()
    reloj = SimpleNamespace(ahora=lambda: datetime(2026, 11, 18, 15, tzinfo=UTC))
    consumidor = avisos_pedido.ConsumidorAvisoPedido(
        tipo=PEDIDO_ENTREGADO,
        unidad=Any,  # type: ignore[arg-type]
        correo=correo,
        push=Any,  # type: ignore[arg-type]
        reloj=reloj,  # type: ignore[arg-type]
        origen_web="https://matu.example",
        push_permitido=lambda _u: True,
    )
    fila = NotificacionLeida(
        id=uuid.uuid4(), usuario_id=usuario_id, canal=Canal.CORREO, estado=EstadoNotificacion.PENDIENTE, codigo=None
    )

    d = consumidor._intentar(repo, fila)  # type: ignore[arg-type]

    assert (d.estado, d.codigo, d.reintentar) == (EstadoNotificacion.OMITIDA, CodigoAviso.SIN_DESTINO, False)
    assert repo.actualizadas == [(fila.id, EstadoNotificacion.OMITIDA, CodigoAviso.SIN_DESTINO, None)]
    assert correo.envios == []
