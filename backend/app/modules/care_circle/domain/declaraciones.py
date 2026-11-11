"""Las declaraciones de la autorización de pedidos (MATU-61, D1 y P13 aprobada con C7).

``declaracion_pedidos_<calidad>`` lleva su huella: la SHA-256 de la plantilla que la pantalla mostró, en UTF-8 y
con ``{nombre_pila}`` sin reemplazar. POST …/consentimientos con ``finalidad: despacho`` exige
``huella_declaracion`` y la compara con la de esta tabla: otra huella responde 422 ``declaracion_no_vigente``.

**Textos provisionales del backend.** Siguen la redacción propuesta por el analista (revisión previa de MATU-61,
sección 4) y la forma de las de consumo (política, sección 5). Los textos definitivos los publica el analista en la
política 0.12 (D11): si cambian, cambia la huella, y esta tabla y la pantalla se actualizan en el mismo PR. Ningún
texto lleva un término clínico (docs/lenguaje.md).

Regla pura, sin I/O.
"""

import hashlib
import re

from app.modules.care_circle.domain.personas import CalidadOtorgante

FORMA_HUELLA = re.compile(r"^[0-9a-f]{64}$")

_CUERPO = (
    "a guardar los pedidos de insumos para {nombre_pila}, con los productos, la dirección de entrega, el teléfono"
    " de contacto y el pago, para preparar, entregar y responder por cada pedido, según la política de privacidad"
    " vigente."
)

DECLARACIONES_PEDIDOS: dict[CalidadOtorgante, str] = {
    CalidadOtorgante.TITULAR: (
        "Declaro que {nombre_pila} me dijo hoy, en persona, que autoriza a MATU "
        + _CUERPO
        + " Yo solo registro su decisión."
    ),
    CalidadOtorgante.REPRESENTANTE_LEGAL: (
        "Declaro que soy representante legal de {nombre_pila} y que la referencia que indico corresponde al"
        " documento que lo acredita. Como su representante, autorizo a MATU " + _CUERPO
    ),
    CalidadOtorgante.CUIDADOR_DE_HECHO: (
        "Declaro que cuido a {nombre_pila} y que no soy su representante legal. Autorizo a MATU "
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
