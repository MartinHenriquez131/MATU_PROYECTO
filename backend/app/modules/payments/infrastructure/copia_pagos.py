"""Los bloques de la capa 3 en la copia de los datos (MATU-54; D-54-14 a D-54-16, decisiones 355, 360, 371 y 379).

- ``pedidos`` de «Datos de {nombre_pila}»: los pedidos de la persona con sus líneas, la dirección copiada **sin el
  teléfono de contacto**, y el pago: estado, cuándo, quién pagó (nombre), lo cobrado, lo devuelto y las devoluciones.
  Nunca el token, la orden de compra, la sesión, el código de autorización ni datos de la tarjeta.
- ``pagos`` de «Tus datos»: los pagos de esta cuenta (tipo de tarjeta, últimos 4 dígitos y cuotas) y las condiciones
  que aceptó, por grupo, sin el nombre de la persona ni los productos (decisión 379).

Vive en payments porque lee el pago con sus repositorios, y payments puede importar ordering y care_circle. app/main.py
los registra solo si el paquete está (la capa 3 se puede quitar: D-54-15 a). Corren como matu_app con la RLS de hoy.
"""

import uuid
from typing import Any

from sqlalchemy import text

from app.core.config import obtener_configuracion
from app.modules.care_circle.infrastructure.copia_datos import ContextoCopia, persona_nombrada
from app.modules.iam.infrastructure.copia_cuenta import ContextoCopiaCuenta
from app.modules.ordering.domain.pedido import REGLA_POR_OMISION
from app.modules.payments.application.lectura import ESTADO_PAGO
from app.modules.payments.domain.venta import EstadoVenta
from app.modules.payments.infrastructure.pasarela import pasarela_desde
from app.modules.payments.infrastructure.repositorio_pagos import RepositorioPagosSQL
from app.shared.copia_datos import en_chile, en_chile_o_nada

_PEDIDOS = text(
    "SELECT p.id, p.referencia, p.estado, p.creado_en, p.total_confirmado_en, p.total_vence_en, p.subtotal_productos,"
    " p.costo_envio, p.total, p.pagado_en"
    " FROM pedido p WHERE p.persona_cuidada_id = :persona_id AND p.grupo_id = :grupo_id"
    " ORDER BY p.creado_en DESC, p.id DESC"
)
_LINEAS = text(
    "SELECT pr.nombre, pr.presentacion, c.nombre_fantasia, c.ficticio, l.cantidad, l.precio_unitario, r.accion"
    " FROM pedido_linea l JOIN producto pr ON pr.id = l.producto_id"
    " JOIN oferta o ON o.id = l.oferta_id JOIN comercio c ON c.id = o.comercio_id"
    " LEFT JOIN regla_sustitucion r ON r.pedido_id = l.pedido_id AND r.producto_id = l.producto_id"
    " WHERE l.pedido_id = :pedido_id ORDER BY l.creado_en, l.id"
)
# Sin telefono_contacto ni telefono_origen (D-54-14)
_ENTREGA = text(
    "SELECT calle, numero, depto, comuna, region, referencia FROM pedido_entrega WHERE pedido_id = :pedido_id"
)
_NOMBRE = text("SELECT nombre FROM usuario WHERE id = :id AND eliminado_en IS NULL")


def _pago_de_prueba() -> bool:
    """Sin pasarela configurada no se movió dinero (D-62-7); con la de integración, tampoco."""
    pasarela = pasarela_desde(obtener_configuracion())
    return True if pasarela is None else pasarela.pago_de_prueba


def _pago(ctx: ContextoCopia, pagos: RepositorioPagosSQL, pedido_id: uuid.UUID, pagado_en: Any) -> Any:
    cargo = pagos.cargo_de(pedido_id)
    if cargo is None:
        return None
    ventas = pagos.ventas(cargo.id)
    pagadora = next(
        (v for v in ventas if v.estado is EstadoVenta.APROBADA and not v.anulada_por_pago_tardio), None
    )
    pagado_por = None
    if pagadora is not None:
        nombre = ctx.sesion.execute(_NOMBRE, {"id": pagadora.usuario_id}).scalar_one_or_none()
        pagado_por = persona_nombrada(nombre, nombre is not None)
    lineas = {x.id: x for x in pagos.lineas_pagadas(pedido_id)}
    devoluciones = [
        {
            "motivo": a.motivo.value,
            "producto": None if a.pedido_linea_id is None or a.pedido_linea_id not in lineas
            else lineas[a.pedido_linea_id].nombre,
            "monto": a.monto,
            "estado": "hecha" if a.hecha else "en_curso",
            "solicitada_en": en_chile(a.solicitada_en),
            "hecha_en": en_chile_o_nada(a.hecha_en),
        }
        for a in sorted(pagos.anulaciones(cargo.id), key=lambda x: (x.solicitada_en, str(x.id)))
    ]
    return {
        "estado": ESTADO_PAGO[cargo.estado],
        "pagado_en": en_chile_o_nada(pagado_en),
        "pagado_por": pagado_por,
        "cobrado": cargo.monto_cobrado,
        "devuelto": cargo.monto_devuelto,
        "devoluciones": devoluciones,
        "pago_de_prueba": _pago_de_prueba(),
    }


def pedidos(ctx: ContextoCopia) -> list[dict[str, Any]]:
    """El bloque ``pedidos``. Va también con la autorización de pedidos retirada o la capa 3 apagada (D-54-15 a)."""
    pagos = RepositorioPagosSQL(ctx.sesion, ctx.grupo_id)
    resultado = []
    for p in ctx.sesion.execute(_PEDIDOS, {"persona_id": ctx.persona_id, "grupo_id": ctx.grupo_id}).all():
        filas = ctx.sesion.execute(_LINEAS, {"pedido_id": p.id}).all()
        entrega = ctx.sesion.execute(_ENTREGA, {"pedido_id": p.id}).first()
        estado = p.estado
        # El vencimiento se decide al leer, según el Reloj, como en el pedido (MATU-61)
        if estado == "total_confirmado" and p.total_vence_en is not None and p.total_vence_en <= ctx.ahora:
            estado = "vencido"
        resultado.append(
            {
                "referencia": p.referencia,
                "estado": estado,
                "creado_en": en_chile(p.creado_en),
                "total_confirmado_en": en_chile_o_nada(p.total_confirmado_en),
                "lineas": [
                    {
                        "producto": f.nombre,
                        "presentacion": f.presentacion,
                        "comercio": f.nombre_fantasia,
                        "cantidad": int(f.cantidad),
                        "precio_unitario": int(f.precio_unitario),
                        "subtotal": int(f.precio_unitario) * int(f.cantidad),
                        "si_falta": f.accion or REGLA_POR_OMISION.value,
                    }
                    for f in filas
                ],
                "subtotal_productos": int(p.subtotal_productos),
                "costo_envio": int(p.costo_envio),
                "total": None if p.total_confirmado_en is None else int(p.total),
                "entrega": None
                if entrega is None
                else {
                    "calle": entrega.calle,
                    "numero": entrega.numero,
                    "depto": entrega.depto,
                    "comuna": entrega.comuna,
                    "region": entrega.region,
                    "referencia": entrega.referencia,
                },
                "pago": _pago(ctx, pagos, p.id, p.pagado_en),
                "precios_de_ejemplo": any(bool(f.ficticio) for f in filas),
            }
        )
    return resultado


# --- «Tus datos» --------------------------------------------------------------------------------------------------

_MIS_GRUPOS = text(
    "SELECT g.id, g.nombre FROM membresia m JOIN grupo_familiar g ON g.id = m.grupo_id"
    " WHERE m.usuario_id = app_usuario() AND m.estado = 'activa' ORDER BY m.unido_en, m.id"
)
_FIJAR_GRUPO = text("SELECT set_config('app.grupo_id', :grupo_id, true)")
# Lo cobrado es lo que se aprobó en la tarjeta; lo devuelto, las anulaciones aprobadas de esa venta
_MIS_PAGOS = text(
    "SELECT pe.referencia, t.cerrada_en, t.creado_en, t.monto, t.tipo_tarjeta, t.ultimos4, t.cuotas,"
    " t.codigo_autorizacion,"
    " (SELECT COALESCE(sum(a.monto), 0) FROM transaccion_pasarela a WHERE a.venta_id = t.id"
    "  AND a.tipo = 'anulacion' AND a.estado = 'aprobada') AS devuelto"
    " FROM transaccion_pasarela t JOIN participacion pa ON pa.id = t.participacion_id"
    " JOIN cargo c ON c.id = t.cargo_id JOIN pedido pe ON pe.id = c.pedido_id"
    " WHERE t.tipo = 'venta' AND t.estado = 'aprobada' AND pa.usuario_id = app_usuario()"
    " AND pe.grupo_id = :grupo_id"
    " ORDER BY COALESCE(t.cerrada_en, t.creado_en) DESC, t.id DESC"
)
_MIS_CONDICIONES = text(
    "SELECT pe.referencia, pe.condiciones_version, pe.condiciones_huella, pe.condiciones_aceptadas_en FROM pedido pe"
    " WHERE pe.grupo_id = :grupo_id AND pe.condiciones_aceptadas_por = app_usuario()"
    " ORDER BY pe.condiciones_aceptadas_en DESC, pe.id DESC"
)


def pagos_de_la_cuenta(ctx: ContextoCopiaCuenta) -> dict[str, Any]:
    """Los pagos y las condiciones de esta cuenta, grupo por grupo, con las políticas de hoy y sin una nueva
    (decisión 371): dentro de la transacción se fija cada grupo del que es miembro activo y al final se limpia.
    Quien salió de un grupo no ve aquí lo de ese grupo (CL-68): lo pide por correo."""
    pagos: list[dict[str, Any]] = []
    condiciones: list[dict[str, Any]] = []
    prueba = _pago_de_prueba()
    grupos = ctx.sesion.execute(_MIS_GRUPOS).all()
    try:
        for g in grupos:
            ctx.sesion.execute(_FIJAR_GRUPO, {"grupo_id": str(g.id)})
            for f in ctx.sesion.execute(_MIS_PAGOS, {"grupo_id": g.id}).all():
                tarjeta = None
                if f.tipo_tarjeta is not None and f.ultimos4 is not None:
                    tarjeta = {"tipo": f.tipo_tarjeta, "ultimos4": f.ultimos4, "cuotas": int(f.cuotas or 0)}
                pagos.append(
                    {
                        "grupo": g.nombre,
                        "referencia": f.referencia,
                        "pagado_en": en_chile(f.cerrada_en or f.creado_en),
                        "cobrado": int(f.monto),
                        "devuelto": int(f.devuelto),
                        "tarjeta": tarjeta,
                        # F3 (decisión 402): el de su propio pago, como en su comprobante. Nunca en «Datos de»
                        "codigo_autorizacion": f.codigo_autorizacion,
                        "pago_de_prueba": prueba,
                    }
                )
            for f in ctx.sesion.execute(_MIS_CONDICIONES, {"grupo_id": g.id}).all():
                condiciones.append(
                    {
                        "grupo": g.nombre,
                        "referencia": f.referencia,
                        "version": f.condiciones_version,
                        "huella": f.condiciones_huella,
                        "aceptadas_en": en_chile(f.condiciones_aceptadas_en),
                    }
                )
    finally:
        ctx.sesion.execute(_FIJAR_GRUPO, {"grupo_id": ""})
    return {"pagos": pagos, "condiciones_aceptadas": condiciones}
