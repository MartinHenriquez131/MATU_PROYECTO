"""El bloque ``insumos`` de la copia de los datos de la persona (MATU-54; decisiones 354 y 386).

Solo con la autorización de insumos vigente trae la lista, las compras anotadas y los avisos de insumos (D-54-5 a). En
los demás estados, solo el estado y, si está retirada, el día en que se borra lo anotado. Es la primera lectura de las
compras (registro de tratamientos, entrada 5): las declaradas se borran a los 90 días (0017), así que son las de los
últimos 90 días. Se registra desde app/main.py en el registro de care_circle.

Columnas nombradas, sin SELECT * (C6). Sin ids, sin etag, sin pedido_ref.
"""

from typing import Any

from sqlalchemy import text

from app.modules.care_circle.infrastructure.copia_datos import ContextoCopia, estado_bloque, persona_nombrada
from app.shared.copia_datos import en_chile, en_chile_o_nada

_NOMBRE = "COALESCE(pr.nombre, p.nombre_libre)"

_LISTA = text(
    f"SELECT {_NOMBRE} AS nombre, (p.producto_id IS NOT NULL) AS del_catalogo, p.unidad, p.tasa_unidades,"
    " p.tasa_dias, p.stock_unidades, p.stock_medido_en, p.fecha_quiebre_estimada, p.dias_aviso,"
    " p.unidades_por_envase, p.activo, p.creado_en, p.actualizado_en,"
    " u.nombre AS autor_nombre, (u.id IS NOT NULL) AS autor_activo, (p.actualizado_por IS NOT NULL) AS con_autor"
    " FROM perfil_consumo p LEFT JOIN producto pr ON pr.id = p.producto_id"
    " LEFT JOIN usuario u ON u.id = p.actualizado_por AND u.eliminado_en IS NULL"
    " WHERE p.persona_cuidada_id = :persona_id AND p.grupo_id = :grupo_id"
    " ORDER BY p.creado_en, p.id"
)

_COMPRAS = text(
    f"SELECT {_NOMBRE} AS insumo, p.unidad, r.cantidad_unidades, r.ocurrida_en, r.origen, r.registrada_en,"
    " u.nombre AS autor_nombre, (u.id IS NOT NULL) AS autor_activo, (r.registrada_por IS NOT NULL) AS con_autor"
    " FROM reposicion r JOIN perfil_consumo p ON p.id = r.perfil_id"
    " LEFT JOIN producto pr ON pr.id = p.producto_id"
    " LEFT JOIN usuario u ON u.id = r.registrada_por AND u.eliminado_en IS NULL"
    " WHERE p.persona_cuidada_id = :persona_id AND p.grupo_id = :grupo_id"
    " ORDER BY r.registrada_en DESC, r.id DESC"
)

_AVISOS = text(
    f"SELECT {_NOMBRE} AS insumo, q.fecha_prevista, q.estado, q.creada_en, q.notificada_en, q.cerrada_en"
    " FROM alerta_quiebre q JOIN perfil_consumo p ON p.id = q.perfil_id"
    " LEFT JOIN producto pr ON pr.id = p.producto_id"
    " WHERE p.persona_cuidada_id = :persona_id AND p.grupo_id = :grupo_id"
    " ORDER BY q.creada_en DESC, q.id DESC"
)


def _autor(f: Any) -> dict[str, Any] | None:
    return persona_nombrada(f.autor_nombre, f.autor_activo) if f.con_autor else None


def insumos(ctx: ContextoCopia) -> dict[str, Any]:
    estado, borrado_el = estado_bloque(ctx.estado_insumos)
    if estado != "disponible":
        return {"estado": estado, "borrado_el": borrado_el, "lista": None, "compras": None, "avisos": None}
    parametros = {"persona_id": ctx.persona_id, "grupo_id": ctx.grupo_id}
    lista = [
        {
            "nombre": f.nombre,
            "del_catalogo": bool(f.del_catalogo),
            "unidad": f.unidad,
            "usa_unidades": int(f.tasa_unidades),
            "cada_dias": int(f.tasa_dias),
            "quedaban_unidades": int(f.stock_unidades),
            "quedaban_el": f.stock_medido_en.isoformat(),
            "se_acaba_el": f.fecha_quiebre_estimada.isoformat(),
            "dias_aviso": int(f.dias_aviso),
            "unidades_por_envase": f.unidades_por_envase,
            "se_sigue": bool(f.activo),
            "agregado_en": en_chile(f.creado_en),
            "actualizado_en": en_chile(f.actualizado_en),
            "actualizado_por": _autor(f),
        }
        for f in ctx.sesion.execute(_LISTA, parametros).all()
    ]
    compras = [
        {
            "insumo": f.insumo,
            # F5 (decisión 386): la unidad del insumo, para leer la cantidad
            "unidad": f.unidad,
            "unidades": int(f.cantidad_unidades),
            "el": f.ocurrida_en.isoformat(),
            "origen": f.origen,
            "anotada_en": en_chile(f.registrada_en),
            "anotada_por": _autor(f),
        }
        for f in ctx.sesion.execute(_COMPRAS, parametros).all()
    ]
    avisos = [
        {
            "insumo": f.insumo,
            "fecha_prevista": f.fecha_prevista.isoformat(),
            "estado": f.estado,
            "creado_en": en_chile(f.creada_en),
            "notificado_en": en_chile_o_nada(f.notificada_en),
            "cerrado_en": en_chile_o_nada(f.cerrada_en),
        }
        for f in ctx.sesion.execute(_AVISOS, parametros).all()
    ]
    return {"estado": estado, "borrado_el": None, "lista": lista, "compras": compras, "avisos": avisos}
