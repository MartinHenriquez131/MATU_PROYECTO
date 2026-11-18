"""Los textos del correo del aviso de quiebre (MATU-41, decisión 113, docs/lenguaje.md sección 20, aprobados
por Jorge el 04-11).

Se arman al enviar y nunca se guardan: ni en la base, ni en el registro simulado, ni en un log. No dicen
qué insumo ni de quién, no ofrecen comprar, y el enlace va a la raíz de la aplicación sin identificadores
ni token. El correo no lleva seguimiento ni imágenes remotas. Ni el ``repr`` del mensaje muestra el texto.

El push no tiene mensaje aquí: va sin contenido (decisión 50, RFC 8030 con VAPID) y su texto lo pone el service worker
de la aplicación web. Desde MATU-76 (D-76-1 a) es uno solo para todo: «MATU · Tienes una novedad. Abre la app para
verla.».

MATU-76 suma el correo del aviso del pedido (``correo_pedido``), con dos pies: el del aviso que se puede apagar y el del
aviso de dinero, que no se apaga (C7).
"""

import html
import re
from dataclasses import dataclass, field

REMITENTE = "MATU"
ASUNTO = "MATU: un insumo se está acabando"
CUERPO = "Un insumo se está acabando. Abre la app para ver cuál."
TEXTO_ENLACE = "Abrir MATU"
PIE = (
    "Te llega este correo porque eres parte de un grupo de cuidado en MATU. Para dejar de recibir estos avisos"
    " por correo, entra a MATU y desactívalos en Tu cuenta."
)

# MATU-76 (C6 y C7): el aviso del pedido. El mismo texto para todos los eventos, sin productos, montos, nombres,
# comercio, referencia ni código de retiro. Nunca «te devolvimos»: el evento se emite aunque la devolución falle (H3)
ASUNTO_PEDIDO = "MATU: hay una novedad en un pedido"
CUERPO_PEDIDO = "Hay una novedad en un pedido. Abre la app para verla."
PIE_PEDIDO = (
    "Te llega este correo porque pagaste un pedido en MATU. Para dejar de recibir estos avisos por correo, entra a MATU"
    " y desactívalos en Tu cuenta."
)
# El correo de dinero no se apaga (D-76-3): su pie nunca dice que se puede apagar. Texto del diseñador (sección 8)
PIE_PEDIDO_DINERO = (
    "Te llega este correo porque pagaste un pedido en MATU. Como es sobre tu dinero, te llega aunque hayas desactivado"
    " los avisos por correo."
)

# El origen https de la aplicación, sin ruta, query ni fragmento (como ORIGEN_WEB)
_ORIGEN = re.compile(r"^https://[^/#?\s]+$")


def enlace_app(origen_web: str) -> str:
    """La raíz de la aplicación: ``<origen>/``. Nunca lleva identificadores, token ni parámetros."""
    if not _ORIGEN.fullmatch(origen_web):
        raise ValueError("el origen de la aplicación debe ser https y sin ruta")
    return origen_web + "/"


@dataclass(frozen=True)
class MensajeCorreo:
    remitente: str = field(repr=False)
    asunto: str = field(repr=False)
    cuerpo: str = field(repr=False)
    texto_enlace: str = field(repr=False)
    enlace: str = field(repr=False)
    pie: str = field(repr=False)

    def texto_plano(self) -> str:
        return f"{self.cuerpo}\n\n{self.texto_enlace}: {self.enlace}\n\n{self.pie}\n"

    def html(self) -> str:
        """HTML mínimo, sin imágenes, sin estilos remotos y sin píxel ni enlaces de seguimiento."""
        e = html.escape
        return (
            '<!doctype html><html lang="es-CL"><body>'
            f"<p>{e(self.cuerpo)}</p>"
            f'<p><a href="{e(self.enlace, quote=True)}">{e(self.texto_enlace)}</a></p>'
            f"<p>{e(self.pie)}</p>"
            "</body></html>"
        )


def correo_quiebre(origen_web: str) -> MensajeCorreo:
    return MensajeCorreo(
        remitente=REMITENTE,
        asunto=ASUNTO,
        cuerpo=CUERPO,
        texto_enlace=TEXTO_ENLACE,
        enlace=enlace_app(origen_web),
        pie=PIE,
    )



def correo_pedido(origen_web: str, *, dinero: bool) -> MensajeCorreo:
    """El correo del aviso del pedido (MATU-76). ``dinero``: anulación, faltante o cancelación con devolución."""
    return MensajeCorreo(
        remitente=REMITENTE,
        asunto=ASUNTO_PEDIDO,
        cuerpo=CUERPO_PEDIDO,
        texto_enlace=TEXTO_ENLACE,
        enlace=enlace_app(origen_web),
        pie=PIE_PEDIDO_DINERO if dinero else PIE_PEDIDO,
    )
