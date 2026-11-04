"""Los textos del aviso de quiebre (MATU-41, decisión 113, docs/lenguaje.md sección 20, aprobados por Jorge
el 04-11).

Se arman al enviar y nunca se guardan: ni en la base, ni en el registro simulado, ni en un log. No dicen
qué insumo ni de quién, no ofrecen comprar, y el enlace va a la raíz de la aplicación sin identificadores
ni token. El correo no lleva seguimiento ni imágenes remotas. Ni el ``repr`` de los mensajes muestra el
texto.
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
TITULO_PUSH = "MATU"

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


@dataclass(frozen=True)
class MensajePush:
    titulo: str = field(repr=False)
    cuerpo: str = field(repr=False)
    enlace: str = field(repr=False)


def correo_quiebre(origen_web: str) -> MensajeCorreo:
    return MensajeCorreo(
        remitente=REMITENTE,
        asunto=ASUNTO,
        cuerpo=CUERPO,
        texto_enlace=TEXTO_ENLACE,
        enlace=enlace_app(origen_web),
        pie=PIE,
    )


def push_quiebre(origen_web: str) -> MensajePush:
    return MensajePush(titulo=TITULO_PUSH, cuerpo=CUERPO, enlace=enlace_app(origen_web))
