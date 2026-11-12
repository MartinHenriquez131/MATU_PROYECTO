"""El bloque ``avisos`` de «Tus datos» (MATU-54; decisiones 359 y 373): la preferencia de avisos y los avisos que MATU
le generó a la cuenta, con la fecha, el canal y si salió. **Nunca** el texto, la plantilla, el destino, la persona ni el
error (C16).

En el semestre no hay un proveedor real de correo ni de push (decisión 112): todo aviso «enviado» es simulado, y sale
como ``en_el_piloto_no_salio`` (D-54-11 a, C17). La fila de notificacion no guarda si se simuló: cuando llegue el
envío real, esa historia agrega la marca por fila (decisión 373). Lo registra app/main.py.
"""

from typing import Any

from sqlalchemy import text

from app.modules.iam.infrastructure.copia_cuenta import ContextoCopiaCuenta
from app.modules.notifications.application.preferencias import leer_preferencia
from app.modules.notifications.infrastructure.repositorio_preferencias import RepositorioPreferenciasSQL
from app.shared.copia_datos import en_chile, en_chile_o_nada

# Decisión 112: no hay adaptador real de correo ni de push
ENVIO_AVISOS_SIMULADO = True

# notificacion_propia: solo las filas de la cuenta. Sin plantilla, destino, evento ni error
_AVISOS = text(
    "SELECT creada_en, enviada_en, canal, estado FROM notificacion WHERE usuario_id = app_usuario()"
    " ORDER BY creada_en DESC, id DESC"
)


def resultado(estado: str, simulado: bool) -> str:
    if estado == "enviada":
        return "en_el_piloto_no_salio" if simulado else "salio"
    if estado == "pendiente":
        return "pendiente"
    return "no_salio"


def avisos(ctx: ContextoCopiaCuenta) -> dict[str, Any]:
    preferencia = leer_preferencia(RepositorioPreferenciasSQL(ctx.sesion), ctx.usuario_id)
    enviados = [
        {
            "creado_en": en_chile(f.creada_en),
            "enviado_en": en_chile_o_nada(f.enviada_en),
            "canal": f.canal,
            "resultado": resultado(f.estado, ENVIO_AVISOS_SIMULADO),
        }
        for f in ctx.sesion.execute(_AVISOS).all()
    ]
    return {
        "preferencia_avisos": {"correo": preferencia.correo, "push": preferencia.push},
        "avisos_enviados": enviados,
        "envio_simulado": ENVIO_AVISOS_SIMULADO,
    }
