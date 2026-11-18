"""«Tus pedidos» (MATU-92, RF-20 y RF-25; D-92-1 a D-92-2, C1 a C23 y C27): la lista de los pedidos pagados de una
persona, el seguimiento de un pedido y lo que se puede devolver.

Vive en backoffice porque junta el pedido y sus partes (ordering, fulfillment) con lo devuelto y el retracto
(payments). Todo se lee en la transacción de la petición (sesion_de_grupo), con RLS. No se audita (C23).

- Roles (C3, C5): admin, cuidador y pagador ven el pedido con sus montos; el observador, la fecha del pago, el estado
  para la familia, la fecha de entrega y los productos, sin ningún monto (D-92-1 a; MATU-113, decisión 472).
  Quien salió del grupo no llega aquí (sesion_de_grupo responde 404, C4).
- MATU-116 (J1, C5; decisión 475): el observador que pagó un pedido ve ese pedido como quien paga (``pagaste``), con
  el detalle y «Arrepentirme de la compra»; nunca cancelar (puede_cancelar en false, con su motivo). Quien pagó lo
  dice la base (pagados_por, con RLS de la 0032), nunca el cliente. Los pedidos que no pagó siguen con su fila de
  observador, y su detalle responde 404.
- Lo que el servidor decide (C7, C10): ``puede_cancelar`` y ``puede_arrepentirse``, con su motivo cuando no.
- Conservación (C27): un pedido que cumplió 2 años desde su cierre (regla de ``ordering/domain/seguimiento.py``) no
  aparece en ``listar`` y responde 404 en ``seguimiento`` y en ``para_devolver`` (GET …/retractos), es decir, solo en
  las rutas 1 a 3 de «Tus pedidos». Nada más lo filtra: GET …/pago, los POST de cancelar y arrepentirse y la copia de
  «Tus datos» (MATU-54) siguen mostrando lo guardado, porque esconderlo sin borrarlo le negaría a la persona el acceso
  a lo que MATU todavía tiene. Quitarlo de verdad es el borrado de MATU-89.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.modules.fulfillment.domain.despacho import EstadoParte, MotivoNoCancelar, motivo_no_cancelar
from app.modules.ordering.domain.estados import Estado
from app.modules.ordering.domain.seguimiento import (
    CanceladaPor,
    EstadoFamilia,
    cancelada_por,
    cierre_del_pedido,
    estado_para_la_familia,
    vencido,
)
from app.modules.payments.domain import retracto as reglas_retracto
from app.modules.payments.domain.retracto import MotivoNoArrepentirse, motivo_no_arrepentirse

ROLES_QUE_LEEN = frozenset({"admin", "cuidador", "pagador", "observador"})
ROLES_QUE_VEN_EL_PAGO = frozenset({"admin", "cuidador", "pagador"})
LIMITE_POR_OMISION = 20
LIMITE_MAXIMO = 100


class PedidoNoEncontrado(LookupError):
    """Otro grupo, inexistente, de una persona eliminada, sin pagar, vencido o un rol que no alcanza (404)."""


# --- Lo que se lee ------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CabeceraPedido:
    id: uuid.UUID
    referencia: str | None
    pagado_en: datetime
    estado: Estado
    entregado_en: datetime | None
    cancelado_en: datetime | None
    total: int
    costo_envio: int
    condiciones_version: str | None


@dataclass(frozen=True)
class LineaLeida:
    id: uuid.UUID
    pedido_id: uuid.UUID
    parte_id: uuid.UUID | None
    producto_id: uuid.UUID
    nombre: str
    presentacion: str
    unidad: str
    unidades_por_envase: int
    cantidad: int
    unidades_faltantes: int
    precio_unitario: int
    retracto_pierde_al_abrir: bool

    @property
    def entregadas(self) -> int:
        return self.cantidad - self.unidades_faltantes


@dataclass(frozen=True)
class ParteLeida:
    id: uuid.UUID
    pedido_id: uuid.UUID
    nombre_fantasia: str | None
    ficticio: bool
    estado: str
    motivo_cancelacion: str | None


class LecturaPedidos(Protocol):
    """Implementación: LecturaPedidosSQL (backoffice/infrastructure/lectura_pedidos.py)."""

    def persona_viva(self, persona_id: uuid.UUID) -> bool: ...

    def pagados_de(self, persona_id: uuid.UUID) -> list[CabeceraPedido]: ...

    def cabecera(self, pedido_id: uuid.UUID) -> CabeceraPedido | None:
        """El pedido pagado del grupo, de una persona no eliminada, o None."""
        ...

    def lineas(self, pedido_ids: Sequence[uuid.UUID]) -> list[LineaLeida]:
        """Las líneas pagadas (sin las que salieron al confirmar)."""
        ...

    def partes(self, pedido_ids: Sequence[uuid.UUID]) -> list[ParteLeida]: ...

    def devuelto(self, pedido_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
        """Lo devuelto con anulaciones hechas (cargo.monto_devuelto). Solo para quien ve el pago."""
        ...

    def pagados_por(self, pedido_ids: Sequence[uuid.UUID], usuario_id: uuid.UUID) -> set[uuid.UUID]:
        """Los pedidos que pagó esa cuenta (su participación cobró algo)."""
        ...

    def ya_pedidas(self, pedido_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int]]:
        """Por línea: lo pedido en todos los retractos y en los no rechazados."""
        ...

    def envio_pedido(self, pedido_id: uuid.UUID) -> bool:
        """Si un retracto no rechazado ya incluye el envío."""
        ...


# --- Lo que se entrega --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Acciones:
    motivo_cancelar: MotivoNoCancelar | None
    motivo_arrepentirse: MotivoNoArrepentirse | None
    plazo_hasta: datetime | None
    plazo_correo_hasta: datetime | None

    @property
    def puede_cancelar(self) -> bool:
        return self.motivo_cancelar is None

    @property
    def puede_arrepentirse(self) -> bool:
        return self.motivo_arrepentirse is None


@dataclass(frozen=True)
class Parte:
    nombre_fantasia: str | None
    ficticio: bool
    estado: str
    cancelada_por: CanceladaPor | None
    lineas: tuple[LineaLeida, ...]


@dataclass(frozen=True)
class PedidoDeLaFamilia:
    cabecera: CabeceraPedido
    estado: EstadoFamilia
    lineas: tuple[LineaLeida, ...]
    partes: tuple[Parte, ...]
    # Solo para quien ve el pago; None para el observador
    devuelto: int | None
    acciones: Acciones | None
    # MATU-116 (C5): el observador que pagó este pedido. Ve el pago y puede arrepentirse; nunca cancelar
    pagaste: bool = False

    @property
    def productos_borrados(self) -> bool:
        """C28: un pedido cuyos productos ya no se guardan muestra un texto, no una lista vacía."""
        return not self.lineas


@dataclass(frozen=True)
class Pagina:
    pedidos: tuple[PedidoDeLaFamilia, ...]
    siguiente: tuple[datetime, uuid.UUID] | None
    ve_el_pago: bool


@dataclass(frozen=True)
class LineaParaRetracto:
    linea: LineaLeida
    ya_pedidas: int

    @property
    def disponibles(self) -> int:
        return max(0, self.linea.entregadas - self.ya_pedidas)


@dataclass(frozen=True)
class DevolverDelPedido:
    pedido: PedidoDeLaFamilia
    lineas: tuple[LineaParaRetracto, ...]
    incluye_envio_si_todo: bool


# --- Reglas que se juntan ------------------------------------------------------------------------------------------


def _vigente(c: CabeceraPedido, ahora: datetime) -> bool:
    return not vencido(cierre_del_pedido(c.estado, c.entregado_en, c.cancelado_en, c.pagado_en), ahora)


def _acciones(
    c: CabeceraPedido,
    rol: str,
    pago: bool,
    partes: Sequence[ParteLeida],
    lineas: Sequence[LineaLeida],
    pedidas: dict[uuid.UUID, tuple[int, int]],
    ahora: datetime,
) -> Acciones:
    estados = [EstadoParte(p.estado) for p in partes]
    disponibles = sum(max(0, x.entregadas - pedidas.get(x.id, (0, 0))[0]) for x in lineas)
    entregado = c.entregado_en
    return Acciones(
        motivo_cancelar=motivo_no_cancelar(rol, c.estado.value, estados),
        motivo_arrepentirse=motivo_no_arrepentirse(
            entregado_en=entregado, ahora=ahora, administra=rol == "admin", pago=pago, disponibles=disponibles
        ),
        plazo_hasta=None if entregado is None else reglas_retracto.plazo_retracto(entregado),
        plazo_correo_hasta=None if entregado is None else reglas_retracto.plazo_por_correo(entregado),
    )


def _armar(
    cabeceras: Sequence[CabeceraPedido],
    lectura: LecturaPedidos,
    rol: str,
    usuario_id: uuid.UUID,
    ahora: datetime,
) -> list[PedidoDeLaFamilia]:
    ids = [c.id for c in cabeceras]
    if not ids:
        return []
    lineas = lectura.lineas(ids)
    partes = lectura.partes(ids)
    por_rol = rol in ROLES_QUE_VEN_EL_PAGO
    # C5: para el observador, solo los que pagó (RLS no le deja ver la participación de otro)
    pagados = lectura.pagados_por(ids, usuario_id)
    con_pago = ids if por_rol else [i for i in ids if i in pagados]
    devuelto = lectura.devuelto(con_pago) if con_pago else {}
    pedidas = lectura.ya_pedidas(con_pago) if con_pago else {}
    resultado: list[PedidoDeLaFamilia] = []
    for c in cabeceras:
        suyas = tuple(x for x in lineas if x.pedido_id == c.id)
        sus_partes = [p for p in partes if p.pedido_id == c.id]
        ve_pago = c.id in con_pago
        resultado.append(
            PedidoDeLaFamilia(
                cabecera=c,
                estado=estado_para_la_familia(c.estado),
                lineas=suyas,
                partes=tuple(
                    Parte(
                        nombre_fantasia=p.nombre_fantasia,
                        ficticio=p.ficticio,
                        estado=p.estado,
                        cancelada_por=cancelada_por(p.estado, p.motivo_cancelacion),
                        lineas=tuple(x for x in suyas if x.parte_id == p.id),
                    )
                    for p in sus_partes
                ),
                devuelto=devuelto.get(c.id, 0) if ve_pago else None,
                acciones=_acciones(c, rol, c.id in pagados, sus_partes, suyas, pedidas, ahora) if ve_pago else None,
                pagaste=ve_pago and not por_rol,
            )
        )
    return resultado


# --- Casos de uso -------------------------------------------------------------------------------------------------


def listar(
    lectura: LecturaPedidos,
    rol: str,
    usuario_id: uuid.UUID,
    persona_id: uuid.UUID,
    ahora: datetime,
    despues_de: tuple[datetime, uuid.UUID] | None = None,
    limite: int = LIMITE_POR_OMISION,
) -> Pagina:
    """Los pedidos pagados de la persona, del más reciente al más antiguo (pagado_en, id), sin los vencidos. No pide
    la autorización despacho (C1) ni puede_ver_plan (C2)."""
    if rol not in ROLES_QUE_LEEN or not lectura.persona_viva(persona_id):
        raise PedidoNoEncontrado()
    vigentes = sorted(
        (c for c in lectura.pagados_de(persona_id) if _vigente(c, ahora)),
        key=lambda c: (c.pagado_en, str(c.id)),
        reverse=True,
    )
    if despues_de is not None:
        corte = (despues_de[0], str(despues_de[1]))
        vigentes = [c for c in vigentes if (c.pagado_en, str(c.id)) < corte]
    pagina = vigentes[:limite]
    siguiente = (pagina[-1].pagado_en, pagina[-1].id) if len(vigentes) > limite else None
    return Pagina(tuple(_armar(pagina, lectura, rol, usuario_id, ahora)), siguiente, rol in ROLES_QUE_VEN_EL_PAGO)


def seguimiento(
    lectura: LecturaPedidos, rol: str, usuario_id: uuid.UUID, pedido_id: uuid.UUID, ahora: datetime
) -> PedidoDeLaFamilia:
    """El detalle de un pedido pagado: admin, cuidador y pagador, y el observador que lo pagó (MATU-116, C5). De un
    pedido que no pagó, el observador no tiene detalle (D-92-1 a): 404, nunca 403."""
    if rol not in ROLES_QUE_LEEN:
        raise PedidoNoEncontrado()
    c = lectura.cabecera(pedido_id)
    if c is None or not _vigente(c, ahora):
        raise PedidoNoEncontrado()
    if rol not in ROLES_QUE_VEN_EL_PAGO and c.id not in lectura.pagados_por([c.id], usuario_id):
        raise PedidoNoEncontrado()
    [pedido] = _armar([c], lectura, rol, usuario_id, ahora)
    return pedido


def para_devolver(
    lectura: LecturaPedidos, rol: str, usuario_id: uuid.UUID, pedido_id: uuid.UUID, ahora: datetime
) -> DevolverDelPedido:
    """GET …/retractos (ruta 3): lo entregado, lo ya pedido y lo disponible por línea, y si devolver todo lo que queda
    incluye el envío según las condiciones aceptadas (D-63-10). Solo un pedido entregado."""
    pedido = seguimiento(lectura, rol, usuario_id, pedido_id, ahora)
    if pedido.cabecera.entregado_en is None:
        raise PedidoNoEncontrado()
    pedidas = lectura.ya_pedidas([pedido_id])
    lineas = tuple(LineaParaRetracto(x, pedidas.get(x.id, (0, 0))[0]) for x in pedido.lineas)
    retractables = [
        reglas_retracto.LineaRetractable(
            id=str(x.linea.id),
            entregadas=x.linea.entregadas,
            precio_unitario=x.linea.precio_unitario,
            ya_pedidas=x.ya_pedidas,
            vigentes=pedidas.get(x.linea.id, (0, 0))[1],
        )
        for x in lineas
    ]
    todo = {str(x.linea.id): x.disponibles for x in lineas if x.disponibles > 0}
    incluye = bool(todo) and reglas_retracto.incluye_envio(
        pedido.cabecera.condiciones_version, retractables, todo, lectura.envio_pedido(pedido_id)
    )
    return DevolverDelPedido(pedido, lineas, incluye)
