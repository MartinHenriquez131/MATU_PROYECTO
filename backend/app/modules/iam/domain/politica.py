"""La política de privacidad vigente y su aceptación al crear la cuenta (MATU-75, decisiones D1 y D2).

Reglas puras, sin I/O ni reloj:

- El texto que se muestra es exactamente el que entra en la huella: SHA-256 del texto en UTF-8 con saltos LF, tal
  como está publicado. La API no reemplaza nada: el correo de contacto, su proveedor y su país vienen escritos en el
  texto desde docs/legal/politica-privacidad.md.
- Si el texto todavía trae un marcador ({correo_privacidad} o cualquier {algo}, [PROVEEDOR…] o [PAÍS]), la política
  no se publica. Nunca se muestra ni se acepta un texto con marcadores.
- Al crear la cuenta, el cliente envía la huella que mostró, y el servidor estampa la versión y la huella vigentes. Si
  la huella mostrada no es la vigente (hubo un despliegue mientras la persona leía), la cuenta no se crea.
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime

# Marcadores que impiden publicar: {minúsculas_y_guiones_bajos}, como {correo_privacidad}, y los de la fuente que
# Jorge completa a mano, [PROVEEDOR DEL CORREO] y [PAÍS]
_MARCADORES = re.compile(r"\{[a-z_]+\}|\[PROVEEDOR|\[PAÍS\]")
FORMA_HUELLA = re.compile(r"^[0-9a-f]{64}$")


class PoliticaNoDisponible(Exception):
    """No hay una política que servir: falta la versión o la fecha, la versión no tiene texto, o el texto todavía
    tiene un marcador.

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


def tiene_marcadores(texto: str) -> bool:
    return _MARCADORES.search(texto) is not None


def armar_politica(*, version: str, actualizada_en: date, texto: str, correo: str | None) -> PoliticaVigente:
    """La política que se sirve: el texto tal cual, su huella y el correo de contacto aparte.

    Lanza PoliticaNoDisponible si el texto todavía tiene un marcador.
    """
    texto = normalizar_saltos(texto)
    if tiene_marcadores(texto):
        raise PoliticaNoDisponible("el texto todavía tiene un marcador sin completar")
    return PoliticaVigente(
        version=version, actualizada_en=actualizada_en, huella=huella_de(texto), texto=texto, correo_contacto=correo
    )


def aceptar(politica: PoliticaVigente, huella_mostrada: str, ahora: datetime) -> AceptacionPolitica:
    """La aceptación que se guarda con la cuenta. Lanza PoliticaCambio si la huella mostrada no es la vigente."""
    if huella_mostrada != politica.huella:
        raise PoliticaCambio()
    return AceptacionPolitica(version=politica.version, huella=politica.huella, aceptada_en=ahora)
