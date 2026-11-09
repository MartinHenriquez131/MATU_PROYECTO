"""La política de privacidad vigente y su aceptación al crear la cuenta (MATU-75, decisiones D1 y D2).

Reglas puras, sin I/O ni reloj:

- El texto que se muestra es exactamente el que entra en la huella: SHA-256 del texto en UTF-8 con saltos LF,
  después de reemplazar sus marcadores ({correo_privacidad}, {proveedor_correo} y {pais_proveedor_correo}) con la
  configuración. Si el texto usa un marcador sin valor, o queda uno sin reemplazar, la política no se publica.
  Nunca se acepta un texto con marcadores.
- Al crear la cuenta, el servidor estampa la versión y la huella vigentes. Si el cliente envía la huella que mostró
  y no es la vigente (hubo un despliegue mientras la persona leía), la cuenta no se crea.
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime

MARCADOR_CORREO = "{correo_privacidad}"
MARCADOR_PROVEEDOR = "{proveedor_correo}"
MARCADOR_PAIS = "{pais_proveedor_correo}"
# Cualquier marcador {minúsculas_y_guiones_bajos} que quede en el texto final, también uno que este código no conoce
_MARCADOR = re.compile(r"\{[a-z_]+\}")
FORMA_HUELLA = re.compile(r"^[0-9a-f]{64}$")


class PoliticaNoDisponible(Exception):
    """No hay una política que servir: falta la versión, la fecha o el correo, o la versión no tiene texto.

    El motivo nombra lo que falta, nunca un valor de la configuración.
    """

    def __init__(self, motivo: str) -> None:
        super().__init__(motivo)
        self.motivo = motivo


class PoliticaCambio(Exception):
    """La huella que mostró el cliente no es la de la política vigente."""


@dataclass(frozen=True)
class PoliticaVigente:
    version: str
    actualizada_en: date
    huella: str
    texto: str
    # CORREO_PRIVACIDAD, o None si no está configurado. «Tu cuenta» lo usa para un mailto: y oculta el párrafo sin él
    correo_contacto: str | None = None

    def __repr__(self) -> str:
        return f"PoliticaVigente(version={self.version}, huella={self.huella[:12]})"


@dataclass(frozen=True)
class AceptacionPolitica:
    """Una fila de aceptacion_politica: qué versión aceptó la cuenta, con la huella del texto, y cuándo."""

    version: str
    huella: str
    aceptada_en: datetime


def normalizar_saltos(texto: str) -> str:
    return texto.replace("\r\n", "\n").replace("\r", "\n")


def huella_de(texto: str) -> str:
    """SHA-256 en hexadecimal del texto en UTF-8 con saltos LF."""
    return hashlib.sha256(normalizar_saltos(texto).encode("utf-8")).hexdigest()


def armar_politica(
    *,
    version: str,
    actualizada_en: date,
    plantilla: str,
    correo: str | None,
    proveedor_correo: str | None = None,
    pais_proveedor_correo: str | None = None,
) -> PoliticaVigente:
    """La política que se sirve, ya completa: la plantilla con sus marcadores reemplazados, y la huella de ese texto.

    Lanza PoliticaNoDisponible si el texto usa un marcador y falta su valor (el motivo nombra la variable), o si queda
    un marcador sin reemplazar. Un texto sin un marcador no necesita su valor.
    """
    texto = normalizar_saltos(plantilla)
    for marcador, valor, variable in (
        (MARCADOR_CORREO, correo, "CORREO_PRIVACIDAD"),
        (MARCADOR_PROVEEDOR, proveedor_correo, "PROVEEDOR_CORREO_PRIVACIDAD"),
        (MARCADOR_PAIS, pais_proveedor_correo, "PAIS_PROVEEDOR_CORREO"),
    ):
        if marcador in texto:
            if valor is None:
                raise PoliticaNoDisponible(f"falta {variable} y el texto lo usa")
            texto = texto.replace(marcador, valor)
    if _MARCADOR.search(texto):
        raise PoliticaNoDisponible("el texto tiene un marcador sin reemplazar")
    return PoliticaVigente(
        version=version, actualizada_en=actualizada_en, huella=huella_de(texto), texto=texto, correo_contacto=correo
    )


def aceptar(politica: PoliticaVigente, huella_mostrada: str | None, ahora: datetime) -> AceptacionPolitica:
    """La aceptación que se guarda con la cuenta. Lanza PoliticaCambio si la huella mostrada no es la vigente."""
    if huella_mostrada is not None and huella_mostrada != politica.huella:
        raise PoliticaCambio()
    return AceptacionPolitica(version=politica.version, huella=politica.huella, aceptada_en=ahora)
