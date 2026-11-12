"""El bloque ``grupos`` de «Tus datos» (MATU-54, decisión 358): los grupos de los que la cuenta es miembro activo, con
su nombre, el rol, cuándo se unió y, si es pagador, el permiso de ver la ficha. Sin ids ni las demás personas.

Corre con solo app.usuario_id: membresia_propia y grupo_mis_grupos deciden qué se ve. Lo registra app/main.py.
"""

from typing import Any

from sqlalchemy import text

from app.modules.iam.infrastructure.copia_cuenta import ContextoCopiaCuenta
from app.shared.copia_datos import en_chile

_GRUPOS = text(
    "SELECT g.nombre, m.rol, m.unido_en, m.puede_ver_plan FROM membresia m JOIN grupo_familiar g ON g.id = m.grupo_id"
    " WHERE m.usuario_id = app_usuario() AND m.estado = 'activa' ORDER BY m.unido_en, m.id"
)


def grupos(ctx: ContextoCopiaCuenta) -> list[dict[str, Any]]:
    return [
        {
            "nombre": f.nombre,
            "rol": f.rol,
            "unido_en": en_chile(f.unido_en),
            "puede_ver_ficha": bool(f.puede_ver_plan) if f.rol == "pagador" else None,
        }
        for f in ctx.sesion.execute(_GRUPOS).all()
    ]
