"""Las declaraciones de la autorización de pedidos (MATU-61, D1 y P13 aprobada con C7).

``declaracion_pedidos_<calidad>`` lleva su huella: la SHA-256 del texto exacto que la pantalla mostró, en UTF-8.
POST …/consentimientos con ``finalidad: despacho`` exige ``huella_declaracion`` y la compara con la de esta tabla:
otra huella responde 422 ``declaracion_no_vigente``.

Los textos son los de la política de privacidad, sección 5, «La autorización para los pedidos», aprobados por Jorge el
11-11 (docs/legal/politica-privacidad.md del repositorio MATU). Se copian sin cambiar una palabra: cambiarlos es
publicar una versión nueva de la política, y cambia la huella. La pantalla muestra el mismo texto.

Regla pura, sin I/O.
"""

import hashlib
import re

from app.modules.care_circle.domain.personas import CalidadOtorgante

FORMA_HUELLA = re.compile(r"^[0-9a-f]{64}$")

_CUERPO = (
    "a guardar los pedidos de sus insumos, con los productos, la dirección de entrega, el teléfono de contacto y lo"
    " que se pagó, para preparar, entregar y responder por cada pedido, y a enviar al comercio que lo prepara solo"
    " los productos y las cantidades, según la política de privacidad vigente."
)

DECLARACIONES_PEDIDOS: dict[CalidadOtorgante, str] = {
    CalidadOtorgante.TITULAR: (
        "Declaro que la persona que cuido me dijo hoy, en persona, que autoriza a MATU "
        + _CUERPO
        + " Yo solo registro su decisión."
    ),
    CalidadOtorgante.REPRESENTANTE_LEGAL: (
        "Declaro que soy representante legal de la persona que cuido y que la referencia que indico corresponde al"
        " documento que lo acredita. Como su representante, autorizo a MATU " + _CUERPO
    ),
    CalidadOtorgante.CUIDADOR_DE_HECHO: (
        "Declaro que cuido a esta persona y que no soy su representante legal. Autorizo a MATU "
        + _CUERPO
        + " Leí el aviso sobre el límite de esta autorización."
    ),
}


def huella(texto: str) -> str:
    """SHA-256 en hexadecimal minúscula del texto en UTF-8."""
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def huella_declaracion_pedidos(calidad: CalidadOtorgante) -> str:
    """La huella vigente de ``declaracion_pedidos_<calidad>``."""
    return huella(DECLARACIONES_PEDIDOS[calidad])
