"""MATU-80 · Prepara la base LOCAL para la prueba de carga de k6 (infra/carga/pedido.js). Datos sintéticos.

k6 no puede crear las cuentas por la API: POST /v1/usuarios admite 5 por hora por IP (MATU-25). Este script deja
listas, por los mismos casos de uso que la semilla de la demo (infra/semillas/demo.py, clase Sembradora), N
familias de carga:

- la cuenta ``cargaNN@example.com`` (dominio reservado), admin de su grupo «Familia Carga NN», con un celular
  sintético de la serie +56 9 0000 01xx;
- la persona cuidada, titular, con su dirección de entrega en «Calle de Prueba», y las autorizaciones para los
  insumos y para los pedidos (despacho). Sin ficha, sin insumos y sin relevo: la carga no los usa;
- un comercio ficticio propio, «Comercio de Carga», con el pañal del catálogo de la demo a precio de ejemplo y el
  stock al tope (9999, CHECK oferta_stock_tope de la 0029), para que los 50 usuarios paguen sin agotar el stock de
  la demo. Cada corrida lo vuelve a dejar al tope.

Es idempotente: una cuenta que ya existe conserva su contraseña. Escribe como matu_app (RLS igual que en la API),
nunca como dueño ni superusuario.

Solo corre con ENTORNO=local o pruebas y PASARELA_PAGO=falsa, los únicos donde la API admite la pasarela falsa
(ENTORNOS_PASARELA_FALSA): así nunca prepara una base de Railway (staging o matu-demo, que tienen ENTORNO=staging y
Webpay de integración). Además, DATABASE_URL (la única conexión que usa) tiene que apuntar a una base local:
localhost, 127.0.0.1, ::1 o un socket local. Un .env con ENTORNO=local que apunte a Railway se detiene antes de
conectar, sin mostrar la URL. La contraseña de las cuentas sale de SEMILLA_CONTRASENA, del lado de quien la corre; nunca
se imprime ni se escribe en un archivo. Desde la raíz del repositorio, con el entorno virtual de backend/ activo:

    python infra/carga/preparar_carga.py --cuentas 50
"""

import argparse
import importlib.util
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

RAIZ_INFRA = Path(__file__).resolve().parents[1]
# backend/ en la ruta de importación, como en la semilla de la demo
sys.path.insert(0, str(RAIZ_INFRA.parent / "backend"))

from pydantic import ValidationError  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.exc import ArgumentError, SQLAlchemyError  # noqa: E402

from app.core.config import ENTORNOS_PASARELA_FALSA, obtener_configuracion  # noqa: E402
from app.core.db import fabrica_sesiones  # noqa: E402
from app.modules.care_circle.application.ports import DatosDireccion  # noqa: E402
from app.modules.care_circle.domain.personas import CalidadOtorgante  # noqa: E402
from app.modules.care_plan.infrastructure.custodia_kek_entorno import CustodiaNoPermitida  # noqa: E402
from app.modules.iam.application.politica import politica_vigente  # noqa: E402
from app.modules.iam.domain.politica import PoliticaNoDisponible  # noqa: E402
from app.modules.iam.infrastructure.hasher_argon2 import HasherArgon2id  # noqa: E402
from app.modules.iam.infrastructure.textos_politica import texto_publicado  # noqa: E402
from app.shared.reloj_sistema import RelojSistema  # noqa: E402

CUENTAS_POR_OMISION = 50
CUENTAS_MAXIMO = 99
COMERCIO_CARGA = "Comercio de Carga"
STOCK_CARGA = 9999
PRECIO_CARGA = 12990


def _cargar(nombre: str, ruta: Path) -> ModuleType:
    """Un script hermano, por ruta: infra/ no es un paquete."""
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    # Registrado antes de ejecutarlo: dataclasses busca el módulo de cada clase en sys.modules
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


demo = _cargar("semilla_demo_para_carga", RAIZ_INFRA / "semillas" / "demo.py")
catalogo_demo = demo.cargar_catalogo_demo()


def email_de_carga(numero: int) -> str:
    return f"carga{numero:02d}@example.com"


def familias_de_carga(cuentas: int) -> list[Any]:
    """Las N familias de carga, numeradas desde 1, como FamiliaDemo de la semilla."""
    if not 1 <= cuentas <= CUENTAS_MAXIMO:
        raise ValueError(f"cuentas debe estar entre 1 y {CUENTAS_MAXIMO}")
    familias = []
    for n in range(1, cuentas + 1):
        persona = demo.PersonaDemo(
            nombre=f"Persona de Carga {n:02d}",
            nombre_pila="Carga",
            nivel_apoyo="apoyo_parcial",
            calidad=CalidadOtorgante.TITULAR,
            direccion=DatosDireccion(
                etiqueta="Casa",
                calle="Calle de Prueba",
                numero=str(900 + n),
                depto=None,
                comuna="Ñuñoa",
                region="Metropolitana",
                referencia=None,
            ),
        )
        familias.append(
            demo.FamiliaDemo(
                grupo=f"Familia Carga {n:02d}",
                admin=demo.CuentaDemo(f"Cuenta de Carga {n:02d}", email_de_carga(n), "admin", f"+5690000{100 + n:04d}"),
                miembros=(),
                persona=persona,
                ficha=demo.FichaDemo(campos={}),
                insumos=(),
                autoriza_pedidos=True,
            )
        )
    return familias


def catalogo_de_carga() -> Any:
    """El pañal de la demo (el mismo id) en un comercio ficticio propio, con el stock al tope."""
    c = catalogo_demo
    [panal] = [p for p in c.CATALOGO.productos if p.clave == "panal"]
    [categoria] = [x for x in c.CATALOGO.categorias if x.nombre == panal.categoria]
    # RUT con dígito verificador incorrecto a propósito: el de 77.777.709 es 2, no 3. No pasa el módulo 11
    comercio = c.ComercioSemilla(
        "carga", "Comercio de Carga (ficticio)", COMERCIO_CARGA, "77.777.709-3", "Calle de Prueba 900", "Ñuñoa", None
    )
    return c.CatalogoSemilla(
        categorias=(categoria,),
        productos=(panal,),
        comercios=(comercio,),
        ofertas=(c.OfertaSemilla("panal", "carga", PRECIO_CARGA, STOCK_CARGA),),
    )


def preparar(sembradora: Any, contrasena: str, familias: Sequence[Any], catalogo: Any) -> tuple[Any, Any]:
    """Siembra el catálogo de carga y las familias (familias_de_carga y catalogo_de_carga). Devuelve (catálogo
    sembrado, semilla sembrada)."""
    sembrado = catalogo_demo.sembrar_catalogo(sembradora.fabrica, catalogo)
    semilla = demo.sembrar(sembradora, contrasena, sembrado.productos, familias)
    return sembrado, semilla


def motivo_para_no_correr(entorno: str, pasarela_pago: str | None) -> str | None:
    """None si puede correr. Si no, el motivo, sin valores de la configuración."""
    if entorno not in ENTORNOS_PASARELA_FALSA:
        return (
            "La preparación de la carga solo corre con ENTORNO=local o pruebas: nunca sobre staging, la demo de"
            " Railway ni producción."
        )
    if pasarela_pago != "falsa":
        return "La carga paga con la pasarela falsa: pon PASARELA_PAGO=falsa en el .env local, nunca integracion."
    return None


BASE_NO_LOCAL = "La carga solo se prepara contra una base local."
HOSTS_LOCALES = frozenset({"localhost", "127.0.0.1", "::1"})


def _es_local(host: str) -> bool:
    """localhost, 127.0.0.1, ::1 o un socket local (un directorio, como /var/run/postgresql)."""
    host = host.strip().lower().removeprefix("[").removesuffix("]")
    return host in HOSTS_LOCALES or host.startswith("/")


def _valores(valor: str | tuple[str, ...] | None) -> list[str]:
    """Un parámetro de la URL o del entorno, que puede venir repetido o separado por comas (varios hosts)."""
    if valor is None:
        return []
    valores = (valor,) if isinstance(valor, str) else valor
    return [h for v in valores for h in v.split(",") if h.strip()]


def motivo_por_la_base(url: str, entorno_os: Mapping[str, str] | None = None) -> str | None:
    """None si la URL de conexión apunta a una base local. Si no, el motivo: un texto fijo, sin la URL, el host ni
    credenciales.

    Revisa lo que libpq usaría para conectar: el host de la URL, los parámetros host y hostaddr (que mandan sobre el
    host de la URL) y, si la URL no los trae, PGHOST y PGHOSTADDR. Un servicio (service o PGSERVICE) se rechaza: su
    host está en un archivo que el script no lee.
    """
    entorno_os = os.environ if entorno_os is None else entorno_os
    if not url:
        return "Falta DATABASE_URL en el .env. " + BASE_NO_LOCAL
    try:
        partes = make_url(url)
    except (ArgumentError, ValueError):
        return BASE_NO_LOCAL
    consulta = partes.query
    if "service" in consulta or entorno_os.get("PGSERVICE"):
        return BASE_NO_LOCAL
    hosts = _valores(consulta.get("host")) or _valores(partes.host) or _valores(entorno_os.get("PGHOST"))
    direcciones = _valores(consulta.get("hostaddr")) or _valores(entorno_os.get("PGHOSTADDR"))
    # Sin host en ninguna parte, libpq usa el socket local (o localhost en Windows)
    if not all(_es_local(h) for h in [*hosts, *direcciones]):
        return BASE_NO_LOCAL
    return None


def _argumentos(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepara la base local para la carga de k6 (datos sintéticos).")
    parser.add_argument("--cuentas", type=int, default=CUENTAS_POR_OMISION, help="cuántas familias, de 1 a 99")
    return parser.parse_args(argv)


def main(argv: Sequence[str] = ()) -> int:
    argumentos = _argumentos(argv)
    if not 1 <= argumentos.cuentas <= CUENTAS_MAXIMO:
        print(f"--cuentas debe estar entre 1 y {CUENTAS_MAXIMO}.", file=sys.stderr)
        return 2
    contrasena = os.environ.get(demo.VARIABLE_CONTRASENA, "")
    if not demo.LARGO_MINIMO_CONTRASENA <= len(contrasena) <= demo.LARGO_MAXIMO_CONTRASENA:
        print(
            f"Falta {demo.VARIABLE_CONTRASENA}, de {demo.LARGO_MINIMO_CONTRASENA} a {demo.LARGO_MAXIMO_CONTRASENA}"
            " caracteres: k6 entra con la misma (CARGA_CONTRASENA). Nunca se imprime.",
            file=sys.stderr,
        )
        return 2
    try:
        configuracion = obtener_configuracion()
    except ValidationError:
        # Sin el texto del error: pydantic incluye los valores que rechaza
        print("La configuración del .env no es válida: este mensaje no muestra sus valores.", file=sys.stderr)
        return 2
    motivo = motivo_para_no_correr(configuracion.entorno, configuracion.pasarela_pago)
    if motivo is not None:
        print(motivo, file=sys.stderr)
        return 2
    # Antes de conectar, y sin mostrar la URL: un .env con ENTORNO=local que apunte a Railway se detiene aquí
    motivo = motivo_por_la_base(configuracion.database_url)
    if motivo is not None:
        print(motivo, file=sys.stderr)
        return 2
    if configuracion.pepper_email is None or configuracion.pepper_pin is None:
        print("Faltan PEPPER_EMAIL o PEPPER_PIN en el .env, los mismos de la API.", file=sys.stderr)
        return 2
    if not configuracion.capa3_habilitada:
        print("La carga pide y paga: pon CAPA3_HABILITADA=true en el .env local.", file=sys.stderr)
        return 2
    try:
        custodia = demo._custodia()
    except CustodiaNoPermitida:
        custodia = None
    if custodia is None:
        print("Falta CUSTODIA_KEK=entorno_sintetico con KEK_ENTORNO en el .env, como la API.", file=sys.stderr)
        return 2
    assert configuracion.politica_version is not None  # la configuración la exige fuera de pruebas
    try:
        politica = politica_vigente(
            version=configuracion.politica_version,
            actualizada_en=configuracion.politica_actualizada_en,
            correo=configuracion.correo_privacidad,
            texto_de=texto_publicado,
        )
    except PoliticaNoDisponible as error:
        print(f"Las cuentas aceptan la política de privacidad, y no está disponible: {error.motivo}.", file=sys.stderr)
        return 2
    fabrica = fabrica_sesiones()
    try:
        rol = demo.rol_de_la_conexion(fabrica)
    except SQLAlchemyError:
        print("No se pudo conectar a la base con DATABASE_URL. Revisa que esté levantada y migrada.", file=sys.stderr)
        return 1
    if rol != demo.ROL_ESPERADO:
        print(f"Solo corre conectada como {demo.ROL_ESPERADO}: corrige DATABASE_URL en el .env.", file=sys.stderr)
        return 2
    sembradora = demo.Sembradora(
        fabrica=fabrica,
        pepper=configuracion.pepper_email.get_secret_value().encode("utf-8"),
        version_politica=configuracion.politica_version,
        reloj=RelojSistema(),
        hasher=HasherArgon2id(),
        custodia=custodia,
        pepper_pin=configuracion.pepper_pin.get_secret_value().encode("utf-8"),
        politica=politica,
    )
    try:
        catalogo, semilla = preparar(sembradora, contrasena, familias_de_carga(argumentos.cuentas), catalogo_de_carga())
    except demo.SemillaInconsistente as error:
        print(f"No se pudo preparar: {error}.", file=sys.stderr)
        return 1
    except SQLAlchemyError:
        print("La base rechazó una escritura. Revisa que esté migrada (alembic upgrade head).", file=sys.stderr)
        return 1
    creadas = sum(c.creada for c in semilla.cuentas)
    print(
        f"Carga lista (ENTORNO={configuracion.entorno}): {len(semilla.cuentas)} cuentas, de {email_de_carga(1)} a"
        f" {email_de_carga(argumentos.cuentas)} ({creadas} creadas ahora), cada una con su persona, su dirección y la"
        f" autorización de pedidos. «{COMERCIO_CARGA}» con {STOCK_CARGA} pañales ({len(catalogo.ofertas)} oferta)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
