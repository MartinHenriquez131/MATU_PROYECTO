"""MATU-75 · Genera el texto de la política que sirve GET /v1/politica desde docs/legal/politica-privacidad.md.

La fuente es la política del repositorio MATU (docs/legal/politica-privacidad.md). Este script la convierte en el
texto para la persona, siempre igual: la misma entrada da el mismo archivo, byte a byte.

Uso, desde backend/ y con el entorno virtual activo:

    python scripts/generar_politica.py <ruta a politica-privacidad.md> 0.11

Escribe app/modules/iam/politica/politica-<versión>.md e imprime su huella (SHA-256 del archivo en UTF-8 con saltos
LF). Esa huella va en PUBLICADAS de app/modules/iam/infrastructure/textos_politica.py: si el archivo cambia y la
tabla no, la API no sirve la política y tests/modules/iam/test_politica.py falla. Una versión ya publicada no se
regenera: un texto nuevo es una versión nueva (POLITICA_VERSION y una fila nueva en PUBLICADAS).

Qué hace, en este orden (decisión de Jorge D2, MATU-75):

1. Quita los comentarios HTML <!-- … -->. Desde la 0.11, la fuente guarda ahí sus notas internas, sus PENDIENTE y
   las citas de ADR.
2. Toma desde «## En un minuto» hasta el final. Lo de arriba es el encabezado interno (versión, estado, aprobaciones
   y notas por historia) y no se muestra.
3. Quita las citas internas «> ADR-…» y la línea en blanco que las sigue (fuentes anteriores a la 0.11).
4. Quita las referencias internas entre paréntesis: los que nombran una historia (MATU-nn), un ADR (ADR-nnn) o una
   aprobación de Jorge, por ejemplo «(MATU-41)», «(ADR-029)» o «(aprobado por Jorge el 28-10, MATU-14)». También las
   frases «Las aprobó Jorge el dd-mm.».
5. Quita las frases que muestran un identificador interno entre comillas invertidas (`declaracion_titular`,
   `aviso_cuidador_de_hecho`) o una huella SHA-256: son del sistema, no de la persona.
6. El correo de contacto, su proveedor y su país vienen escritos en la fuente desde la 0.11 (cuidaconmatu@gmail.com,
   Gmail de Google LLC, Estados Unidos). La API no reemplaza nada: sirve el texto tal cual (decisión 174).
   Si la fuente todavía trae un marcador ({correo_privacidad}, «[PROVEEDOR DEL CORREO]» o «[PAÍS]»), el archivo se
   escribe igual y el script avisa: con ese texto la API no publica la política y responde 503. «[PENDIENTE: correo
   de contacto]» pasa a {correo_privacidad}, con el mismo efecto. Cada otro «[PENDIENTE…]» pasa a «Todavía no lo
   definimos.» (D6).
7. Deja un solo espacio entre palabras, quita los espacios al final de cada línea, deja una sola línea en blanco
   seguida y un solo salto al final.
8. Comprueba que no queden «MATU-», «ADR-», «[PENDIENTE», «POLITICA_VERSION», «aprobado por Jorge», comillas
   invertidas, «declaracion_», un comentario HTML, otro marcador entre corchetes en mayúsculas («[ALGO]», salvo los
   del punto 6) ni una huella de 64 caracteres hexadecimales. Si algo queda, no escribe nada y sale con 1, con las
   líneas que fallan.

Avisa, sin fallar, de cada «Todavía no lo definimos.» que queda dentro de una frase («escribe a Todavía no lo
definimos.»): esa frase se corrige en la fuente, docs/legal/politica-privacidad.md, y se vuelve a generar.
"""

import hashlib
import re
import sys
from pathlib import Path

INICIO = "## En un minuto"
MARCADOR_CORREO = "{correo_privacidad}"
# Los marcadores que la fuente puede traer mientras Jorge no los completa. Pasan al archivo, y la API no lo publica
MARCADORES_PENDIENTES = (MARCADOR_CORREO, "[PROVEEDOR DEL CORREO]", "[PAÍS]")
PENDIENTE = "Todavía no lo definimos."
CARPETA = Path(__file__).resolve().parents[1] / "app" / "modules" / "iam" / "politica"

_COMENTARIO = re.compile(r"<!--.*?-->", re.DOTALL)
_CITA_INTERNA = re.compile(r"^> ADR-[^\n]*\n(?:\n)?", re.MULTILINE)
_PARENTESIS_INTERNO = re.compile(r" ?\((?=[^()]*(?:MATU-\d|ADR-\d|Jorge))[^()]*\)")
_APROBACION = re.compile(r" ?(?:La|Las|Lo|Los) aprobó Jorge el \d{2}-\d{2}\.")
_CORREO = re.compile(r"\[PENDIENTE: correo de contacto\]")
_PENDIENTE = re.compile(r"\[PENDIENTE[^\]]*\]")
_CORCHETES_MAYUSCULAS = re.compile(r"\[[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ :]*\]")
_PROHIBIDOS = (
    "MATU-", "ADR-", "[PENDIENTE", "POLITICA_VERSION", "aprobado por Jorge", "aprobó Jorge", "`", "declaracion_",
    "<!--", "-->",
)
_HUELLA_64 = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])")
# Fin de frase: punto o dos puntos, espacios y una mayúscula (o una marca) que empieza la siguiente
_FIN_DE_FRASE = re.compile(r"(?<=[.:])\s+(?=[A-ZÁÉÍÓÚÑ¿¡«*])")
_PENDIENTE_EN_FRASE = re.compile(r"[a-záéíóúñ,] Todavía no lo definimos")


def _es_interna(frase: str) -> bool:
    return "`" in frase or _HUELLA_64.search(frase) is not None


def _sin_frases_internas(linea: str) -> str:
    """La línea sin las frases que muestran un identificador o una huella. Las demás líneas no se tocan."""
    if not _es_interna(linea):
        return linea
    return " ".join(f for f in _FIN_DE_FRASE.split(linea) if not _es_interna(f))


def frases_rotas(texto: str) -> list[str]:
    """Las líneas donde «Todavía no lo definimos.» quedó dentro de una frase."""
    return [linea for linea in texto.split("\n") if _PENDIENTE_EN_FRASE.search(linea)]


def _falla(linea: str) -> bool:
    for marcador in MARCADORES_PENDIENTES:
        linea = linea.replace(marcador, "")
    return (
        any(p in linea for p in _PROHIBIDOS)
        or _HUELLA_64.search(linea) is not None
        or _CORCHETES_MAYUSCULAS.search(linea) is not None
    )


def convertir(fuente: str) -> str:
    """El texto para la persona a partir del .md de docs. Lanza ValueError si queda algo interno."""
    texto = fuente.replace("\r\n", "\n").replace("\r", "\n")
    texto = _COMENTARIO.sub("", texto)
    inicio = texto.find(INICIO)
    if inicio < 0:
        raise ValueError(f"la fuente no tiene la sección «{INICIO}»")
    texto = texto[inicio:]
    texto = _CITA_INTERNA.sub("", texto)
    texto = _PARENTESIS_INTERNO.sub("", texto)
    texto = _APROBACION.sub("", texto)
    texto = "\n".join(_sin_frases_internas(linea) for linea in texto.split("\n"))
    texto = _CORREO.sub(MARCADOR_CORREO, texto)
    texto = _PENDIENTE.sub(PENDIENTE, texto)
    # «… dentro de [PENDIENTE: plazo].» deja dos puntos seguidos
    texto = texto.replace(PENDIENTE + ".", PENDIENTE)
    # Un comentario quitado a mitad de línea deja dos espacios seguidos: queda uno. La sangría no se toca
    lineas = [re.sub(r"(?<=\S) {2,}", " ", linea).rstrip() for linea in texto.split("\n")]
    texto = re.sub(r"\n{3,}", "\n\n", "\n".join(lineas)).strip("\n") + "\n"

    fallas = [linea for linea in texto.split("\n") if _falla(linea)]
    if fallas:
        raise ValueError("quedan referencias internas:\n" + "\n".join(fallas))
    return texto


def huella(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not re.fullmatch(r"[0-9]+\.[0-9]+", argv[1]):
        print("Uso: python scripts/generar_politica.py <politica-privacidad.md> <versión MAYOR.MENOR>", file=sys.stderr)
        return 2
    fuente, version = Path(argv[0]), argv[1]
    try:
        texto = convertir(fuente.read_text(encoding="utf-8"))
    except ValueError as error:
        print(f"No se generó el texto: {error}", file=sys.stderr)
        return 1
    destino = CARPETA / f"politica-{version}.md"
    destino.write_bytes(texto.encode("utf-8"))
    print(f"{destino.name}: {huella(texto)}")
    pendientes = [m for m in MARCADORES_PENDIENTES if m in texto]
    if pendientes:
        print(f"Aviso: el texto todavía tiene {', '.join(pendientes)}. La API no lo publica (503) hasta completarlos.")
    rotas = frases_rotas(texto)
    if rotas:
        print(f"Aviso: {len(rotas)} líneas con «{PENDIENTE}» dentro de una frase. Corrígelas en la fuente:")
        for linea in rotas:
            print(f"  {linea[:160]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
