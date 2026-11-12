"""El bloque ``grupos`` de «Tus datos» (MATU-54, decisiones 358 y 401): los grupos de los que la cuenta es miembro
activo, con su nombre, el rol, cuándo se unió y, si es pagador, el permiso de ver la ficha; y las membresías retiradas,
con el rol, cuándo se unió y cuándo salió, **sin el nombre del grupo** (grupo_mis_grupos no lo deja leer). Sin ids ni
las demás personas.

Corre con solo app.usuario_id: membresia_propia y grupo_mis_grupos deciden qué se ve. Lo registra app/main.py.
"""

from typing import Any

from sqlalchemy import text

from app.modules.iam.infrastructure.copia_cuenta import ContextoCopiaCuenta
from app.shared.copia_datos import en_chile, en_chile_o_nada

_GRUPOS = text(
    "SELECT g.nombre, m.rol, m.unido_en, m.puede_ver_plan FROM membresia m JOIN grupo_familiar g ON g.id = m.grupo_id"
    " WHERE m.usuario_id = app_usuario() AND m.estado = 'activa' ORDER BY m.unido_en, m.id"
)


# F2 del cierre del analista (decisión 401): membresia_propia deja leer las propias retiradas; el grupo ya no se ve
_RETIRADAS = text(
    "SELECT rol, unido_en, retirado_en FROM membresia WHERE usuario_id = app_usuario() AND estado = 'retirada'"
    " ORDER BY retirado_en DESC NULLS LAST, id"
)


def grupos(ctx: ContextoCopiaCuenta) -> dict[str, Any]:
    activos = [
        {
            "nombre": f.nombre,
            "rol": f.rol,
            "unido_en": en_chile(f.unido_en),
            "puede_ver_ficha": bool(f.puede_ver_plan) if f.rol == "pagador" else None,
        }
        for f in ctx.sesion.execute(_GRUPOS).all()
    ]
    retirados = [
        {"rol": f.rol, "unido_en": en_chile(f.unido_en), "retirado_en": en_chile_o_nada(f.retirado_en)}
        for f in ctx.sesion.execute(_RETIRADAS).all()
    ]
    return {"grupos": activos, "grupos_que_dejaste": retirados}
