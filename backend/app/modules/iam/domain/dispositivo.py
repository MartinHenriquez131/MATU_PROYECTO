"""Reglas puras de los dispositivos (MATU-38; decisiones 47, 50 y 59).

Sin I/O ni reloj del sistema.

- El nombre de un dispositivo es grueso: navegador y sistema de una lista cerrada, o "Navegador web".
  El agente de usuario no se guarda.
- El endpoint de push es https, sin credenciales ni puerto, y su host está en una lista cerrada de
  servicios de Web Push: si no, MATU podría terminar enviando peticiones a cualquier dirección.
- Conservación: una sesión se borra 30 días después de vencer o de revocarse; un dispositivo, 90 días
  después de su último uso, si no tiene sesiones vigentes.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlsplit

PLATAFORMA_WEB = "web"
NOMBRE_GENERICO = "Navegador web"
LARGO_MAXIMO_NOMBRE = 60

# El orden importa: Edge y Opera dicen también "Chrome", y Chrome dice también "Safari"
_NAVEGADORES = (
    ("Edg/", "Edge"),
    ("EdgA/", "Edge"),
    ("EdgiOS/", "Edge"),
    ("OPR/", "Opera"),
    ("SamsungBrowser/", "Samsung Internet"),
    ("Firefox/", "Firefox"),
    ("FxiOS/", "Firefox"),
    ("CriOS/", "Chrome"),
    ("Chrome/", "Chrome"),
    ("Safari/", "Safari"),
)
_SISTEMAS = (
    ("Android", "Android"),
    ("iPhone", "iPhone"),
    ("iPad", "iPad"),
    ("Windows", "Windows"),
    ("CrOS", "ChromeOS"),
    ("Macintosh", "Mac"),
    ("Linux", "Linux"),
)


def nombre_dispositivo(agente_usuario: str | None) -> str:
    """"Chrome en Android", "Safari en iPhone", … o "Navegador web" si no reconoce ambos."""
    if not agente_usuario:
        return NOMBRE_GENERICO
    navegador = next((nombre for marca, nombre in _NAVEGADORES if marca in agente_usuario), None)
    sistema = next((nombre for marca, nombre in _SISTEMAS if marca in agente_usuario), None)
    if navegador is None or sistema is None:
        return NOMBRE_GENERICO
    return f"{navegador} en {sistema}"[:LARGO_MAXIMO_NOMBRE]


# Servicios de Web Push admitidos (decisión 50). Un host exacto, o un sufijo que empieza con punto
HOSTS_PUSH_EXACTOS = frozenset({"fcm.googleapis.com", "updates.push.services.mozilla.com"})
SUFIJOS_PUSH = (".push.apple.com", ".notify.windows.com")
LARGO_MAXIMO_PUSH = 1024


def push_admitido(endpoint: str) -> bool:
    """True si el endpoint es https, sin usuario, contraseña ni puerto, con un host de la lista."""
    if len(endpoint) > LARGO_MAXIMO_PUSH or any(c.isspace() for c in endpoint):
        return False
    try:
        partes = urlsplit(endpoint)
        puerto = partes.port
    except ValueError:
        return False
    if partes.scheme != "https" or partes.username is not None or partes.password is not None:
        return False
    if puerto is not None or "@" in partes.netloc:
        return False
    host = (partes.hostname or "").lower()
    if not host or host != partes.netloc.lower():
        return False
    return host in HOSTS_PUSH_EXACTOS or any(host.endswith(s) and len(host) > len(s) for s in SUFIJOS_PUSH)


# --- Conservación (decisión 59) ---------------------------------------------------------------

CONSERVACION_SESION = timedelta(days=30)
CONSERVACION_DISPOSITIVO = timedelta(days=90)


@dataclass(frozen=True)
class LimitesConservacion:
    """Antes de limite_sesion se borran las sesiones vencidas o revocadas; antes de
    limite_dispositivo, los dispositivos sin uso y sin sesiones vigentes en ahora."""

    ahora: datetime
    limite_sesion: datetime
    limite_dispositivo: datetime


def limites_conservacion(ahora: datetime) -> LimitesConservacion:
    if ahora.tzinfo is None or ahora.utcoffset() is None:
        raise ValueError("El instante debe tener zona horaria")
    return LimitesConservacion(
        ahora=ahora,
        limite_sesion=ahora - CONSERVACION_SESION,
        limite_dispositivo=ahora - CONSERVACION_DISPOSITIVO,
    )


def sesion_se_borra(expira_en: datetime, revocado_en: datetime | None, limites: LimitesConservacion) -> bool:
    """La misma regla que aplica iam_conservar (migración 0008): venció o se revocó hace 30 días o más."""
    return expira_en <= limites.limite_sesion or (revocado_en is not None and revocado_en <= limites.limite_sesion)


def dispositivo_se_borra(
    ultimo_uso_en: datetime | None, creado_en: datetime, tiene_sesion_vigente: bool, limites: LimitesConservacion
) -> bool:
    """Sin uso hace 90 días o más (o, si nunca se usó, creado hace 90 días o más) y sin sesión vigente."""
    referencia = ultimo_uso_en if ultimo_uso_en is not None else creado_en
    return referencia <= limites.limite_dispositivo and not tiene_sesion_vigente
