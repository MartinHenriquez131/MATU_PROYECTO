"""Los bloques de la capa 3 en la copia de los datos (MATU-54; D-54-14 a D-54-16, decisiones 355, 360, 371 y 379).

- ``pedidos`` de «Datos de {nombre_pila}»: los pedidos de la persona con sus líneas, la dirección copiada **sin el
  teléfono de contacto**, y el pago: estado, cuándo, quién pagó (nombre), lo cobrado, lo devuelto y las devoluciones.
  Nunca el token, la orden de compra, la sesión, el código de autorización ni datos de la tarjeta.
- ``pagos`` de «Tus datos»: los pagos de esta cuenta (tipo de tarjeta, últimos 4 dígitos y cuotas), sus retractos y
  las condiciones que aceptó, en todos sus grupos, también los que dejó (MATU-116, decisión 475), sin el nombre de la
  persona (decisión 379). Los lee con las funciones definer de la 0032, sin fijar app.grupo_id.

Vive en payments porque lee el pago con sus repositorios, y payments puede importar ordering y care_circle. app/main.py
los registra solo si el paquete está (la capa 3 se puede quitar: D-54-15 a). Corren como matu_app, con RLS.
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
from app.shared.notas_operacion import descifrar_nota
from app.shared.notas_operacion_sql import deks

_PEDIDOS = text(
    "SELECT p.id, p.referencia, p.estado, p.creado_en, p.total_confirmado_en, p.total_vence_en, p.subtotal_productos,"
    " p.costo_envio, p.total, p.pagado_en, p.entregado_en"
    " FROM pedido p WHERE p.persona_cuidada_id = :persona_id AND p.grupo_id = :grupo_id"
    " ORDER BY p.creado_en DESC, p.id DESC"
)
_LINEAS = text(
    "SELECT pr.nombre, pr.presentacion, c.nombre_fantasia, c.ficticio, l.cantidad, l.precio_unitario, r.accion,"
    " l.estado_linea, l.unidades_faltantes"
    " FROM pedido_linea l JOIN producto pr ON pr.id = l.producto_id"
    " JOIN oferta o ON o.id = l.oferta_id JOIN comercio c ON c.id = o.comercio_id"
    " LEFT JOIN regla_sustitucion r ON r.pedido_id = l.pedido_id AND r.producto_id = l.producto_id"
    " WHERE l.pedido_id = :pedido_id ORDER BY l.creado_en, l.id"
)
# Sin telefono_contacto ni telefono_origen (D-54-14)
_ENTREGA = text(
    "SELECT calle, numero, depto, comuna, region, referencia FROM pedido_entrega WHERE pedido_id = :pedido_id"
)
# MATU-63: las partes por comercio, sin su referencia, y los retractos con sus productos
_PARTES = text(
    "SELECT c.nombre_fantasia, pc.estado, pc.enviado_en, pc.lista_en, pc.retirada_en, pc.cancelada_en,"
    " pc.motivo_cancelacion FROM pedido_comercio pc JOIN comercio c ON c.id = pc.comercio_id"
    " WHERE pc.pedido_id = :pedido_id ORDER BY pc.creado_en, pc.id"
)
_RETRACTOS = text(
    "SELECT r.id, r.estado, r.solicitado_en, r.plazo_hasta, r.incluye_envio, r.resuelto_en,"
    " r.motivo_rechazo FROM retracto r"
    " WHERE r.pedido_id = :pedido_id ORDER BY r.solicitado_en, r.id"
)
_LINEAS_RETRACTO = text(
    "SELECT pr.nombre, rl.cantidad FROM retracto_linea rl JOIN pedido_linea l ON l.id = rl.pedido_linea_id"
    " JOIN producto pr ON pr.id = l.producto_id WHERE rl.retracto_id = :retracto_id ORDER BY pr.nombre, l.id"
)
_NOMBRE = text("SELECT nombre FROM usuario WHERE id = :id AND eliminado_en IS NULL")
# MATU-81 (D-81-4): lo que el equipo anotó del pedido (RLS incidencia_familia), sin quién lo anotó ni a quién se asignó.
# La nota y la resolución salen cifradas con la clave de cada una (decisión 471) y se descifran aquí
_LO_QUE_PASO = text(
    "SELECT id, tipo, estado, creada_en, resuelta_en, descripcion, clave_notas_id, resolucion, resolucion_clave_id"
    " FROM incidencia WHERE pedido_id = :pedido_id ORDER BY creada_en, id"
)


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


def _partes(ctx: ContextoCopia, pedido_id: uuid.UUID) -> list[dict[str, Any]]:
    return [
        {
            "comercio": f.nombre_fantasia,
            "estado": f.estado,
            "enviado_en": en_chile_o_nada(f.enviado_en),
            "lista_en": en_chile_o_nada(f.lista_en),
            "retirada_en": en_chile_o_nada(f.retirada_en),
            "cancelada_en": en_chile_o_nada(f.cancelada_en),
            "motivo_cancelacion": f.motivo_cancelacion,
        }
        for f in ctx.sesion.execute(_PARTES, {"pedido_id": pedido_id})
    ]


def _retractos(ctx: ContextoCopia, pedido_id: uuid.UUID) -> list[dict[str, Any]]:
    return [
        {
            "estado": r.estado,
            "solicitado_en": en_chile(r.solicitado_en),
            "plazo_hasta": en_chile(r.plazo_hasta),
            "incluye_envio": bool(r.incluye_envio),
            "resuelto_en": en_chile_o_nada(r.resuelto_en),
            # H2 del analista (MATU-81): por qué no se aceptó, si se rechazó
            "motivo_rechazo": r.motivo_rechazo,
            "lineas": [
                {"producto": f.nombre, "cantidad": int(f.cantidad)}
                for f in ctx.sesion.execute(_LINEAS_RETRACTO, {"retracto_id": r.id})
            ],
        }
        for r in ctx.sesion.execute(_RETRACTOS, {"pedido_id": pedido_id}).all()
    ]


def _lo_que_paso(ctx: ContextoCopia, pedido_id: uuid.UUID) -> list[dict[str, Any]]:
    """Lo que el equipo anotó, descifrado con la clave de las notas de la persona, que la familia del grupo lee
    (clave_notas_familia_leer). Con la clave destruida (el borrado de la persona), la nota sale como no disponible,
    sin error. Con la clave vigente y sin la KEK, NotasNoDisponibles: la ruta responde 503 (falla cerrada)."""
    filas = ctx.sesion.execute(_LO_QUE_PASO, {"pedido_id": pedido_id}).all()
    claves = deks(ctx.sesion, ctx.custodia_notas, [x for f in filas for x in (f.clave_notas_id, f.resolucion_clave_id)])
    pasos = []
    for i in filas:
        nota = descifrar_nota(claves.get(i.clave_notas_id), i.id, "descripcion", bytes(i.descripcion))
        resolucion = None
        if i.resolucion is not None:
            resolucion = descifrar_nota(claves.get(i.resolucion_clave_id), i.id, "resolucion", bytes(i.resolucion))
        disponible = nota is not None and (i.resolucion is None or resolucion is not None)
        pasos.append(
            {
                "tipo": i.tipo,
                "estado": i.estado,
                "anotado_en": en_chile(i.creada_en),
                "resuelto_en": en_chile_o_nada(i.resuelta_en),
                "nota": nota if disponible else None,
                "resolucion": resolucion if disponible else None,
                "nota_disponible": disponible,
            }
        )
    return pasos


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
                        "estado": f.estado_linea,
                        "unidades_faltantes": int(f.unidades_faltantes),
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
                "entregado_en": en_chile_o_nada(p.entregado_en),
                "partes": _partes(ctx, p.id),
                "retractos": _retractos(ctx, p.id),
                "lo_que_paso": _lo_que_paso(ctx, p.id),
            }
        )
    return resultado


# --- «Tus datos» --------------------------------------------------------------------------------------------------

# MATU-116 (J5, decisión 475): las funciones definer de la 0032 devuelven solo lo de la cuenta en contexto, en todos sus
# grupos, también los que dejó, sin grupo_id. Ya no se fija app.grupo_id (reemplaza las decisiones 360 y 371)
_MIS_PAGOS = text(
    "SELECT referencia, pagado_en, cobrado, devuelto, tipo_tarjeta, ultimos4, cuotas, codigo_autorizacion, grupo,"
    " sigue_en_el_grupo FROM cuenta_pagos()"
)
_MIS_RETRACTOS = text(
    "SELECT referencia, estado, solicitado_en, resuelto_en, motivo_rechazo, productos, grupo, sigue_en_el_grupo"
    " FROM cuenta_retractos()"
)
_MIS_CONDICIONES = text(
    "SELECT referencia, version, huella, aceptadas_en, grupo, sigue_en_el_grupo FROM cuenta_condiciones()"
)


def _grupo(f: Any) -> str | None:
    """C4: el nombre del grupo, solo si la membresía sigue activa; si no, null («Un grupo del que saliste»)."""
    return f.grupo if f.sigue_en_el_grupo else None


def pagos_de_la_cuenta(ctx: ContextoCopiaCuenta) -> dict[str, Any]:
    """Los pagos, los retractos y las condiciones de esta cuenta, en todos sus grupos, también de los que salió
    (MATU-116, J2 y J3). De un grupo del que salió: sin el nombre del grupo, y los retractos sin productos (C3 y C4)."""
    prueba = _pago_de_prueba()
    pagos = []
    for f in ctx.sesion.execute(_MIS_PAGOS).all():
        tarjeta = None
        if f.tipo_tarjeta is not None and f.ultimos4 is not None:
            tarjeta = {"tipo": f.tipo_tarjeta, "ultimos4": f.ultimos4, "cuotas": int(f.cuotas or 0)}
        pagos.append(
            {
                "grupo": _grupo(f),
                "sigue_en_el_grupo": bool(f.sigue_en_el_grupo),
                # C2: sin el pedido (se guarda 2 años y el pago 6), null: la pantalla dice «Pago del {fecha}»
                "referencia": f.referencia,
                "pagado_en": en_chile(f.pagado_en),
                "cobrado": int(f.cobrado),
                "devuelto": int(f.devuelto),
                "tarjeta": tarjeta,
                # F3 (decisión 402): el de su propio pago, como en su comprobante. Nunca en «Datos de»
                "codigo_autorizacion": f.codigo_autorizacion,
                "pago_de_prueba": prueba,
            }
        )
    retractos = [
        {
            "grupo": _grupo(r),
            "sigue_en_el_grupo": bool(r.sigue_en_el_grupo),
            "referencia": r.referencia,
            "estado": r.estado,
            "solicitado_en": en_chile(r.solicitado_en),
            "resuelto_en": en_chile_o_nada(r.resuelto_en),
            "motivo_rechazo": r.motivo_rechazo,
            # C3: de un grupo del que salió, null (T4: «Los productos los puedes pedir a {correo}.»)
            "productos": list(r.productos) if r.sigue_en_el_grupo and r.productos is not None else None,
        }
        for r in ctx.sesion.execute(_MIS_RETRACTOS).all()
    ]
    condiciones = [
        {
            "grupo": _grupo(f),
            "sigue_en_el_grupo": bool(f.sigue_en_el_grupo),
            "referencia": f.referencia,
            "version": f.version,
            "huella": f.huella,
            "aceptadas_en": en_chile(f.aceptadas_en),
        }
        for f in ctx.sesion.execute(_MIS_CONDICIONES).all()
    ]
    return {"pagos": pagos, "condiciones_aceptadas": condiciones, "retractos": retractos}
