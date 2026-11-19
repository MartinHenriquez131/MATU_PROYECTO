"""MATU-80 · La preparación de la carga de k6 (infra/carga/preparar_carga.py): sus datos, sus guardas y la siembra.

Los datos y las guardas, sin base. La siembra, contra PostgreSQL como matu_app, con cuentas, nombres y RUT únicos por
prueba (para no chocar con una preparación de verdad en la base local), que se borran al terminar. Solo datos
sintéticos.
"""

import base64
import importlib.util
import secrets
import sys
import uuid
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import psycopg
import pytest
from argon2 import PasswordHasher, Type
from pydantic import SecretStr

from app.core.db import fabrica_sesiones
from app.modules.care_plan.infrastructure.custodia_kek_entorno import CustodiaKekEntorno
from app.modules.iam.infrastructure.hasher_argon2 import HasherArgon2id
from app.shared.reloj_sistema import RelojSistema
from tests.base_datos import DSN, requiere_base
from tests.fabricas import Fabrica
from tests.politica import POLITICA_PRUEBAS, VERSION_PRUEBAS
from tests.rut_ficticio import modulo_11, rut_ficticio

pytestmark = [pytest.mark.rf("RF-25")]

RUTA = Path(__file__).resolve().parents[2] / "infra" / "carga" / "preparar_carga.py"


def _cargar() -> ModuleType:
    spec = importlib.util.spec_from_file_location("preparar_carga", RUTA)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


carga = _cargar()


# --- Los datos y las guardas, sin base ------------------------------------------------------------------------


def test_cincuenta_familias_sinteticas_listas_para_pedir() -> None:
    familias = carga.familias_de_carga(50)

    assert len(familias) == 50
    emails = [f.admin.email for f in familias]
    assert len(set(emails)) == 50 and all(e.endswith("@example.com") for e in emails)
    assert emails[0] == "carga01@example.com" and emails[-1] == "carga50@example.com"
    celulares = [f.admin.telefono for f in familias]
    assert len(set(celulares)) == 50 and all(c.startswith("+56900000") for c in celulares)
    for f in familias:
        assert f.admin.rol == "admin" and f.miembros == ()
        assert f.persona.calidad.value == "titular" and f.persona.direccion is not None
        assert f.autoriza_pedidos is True
        assert f.insumos == () and dict(f.ficha.campos) == {} and f.relevo is None


@pytest.mark.parametrize("cuentas", [0, 100])
def test_el_numero_de_cuentas_tiene_tope(cuentas: int) -> None:
    with pytest.raises(ValueError):
        carga.familias_de_carga(cuentas)


def test_el_comercio_de_carga_es_ficticio_y_su_stock_cabe_en_el_tope() -> None:
    catalogo = carga.catalogo_de_carga()

    [comercio] = catalogo.comercios
    numero, dv = comercio.rut.replace(".", "").split("-")
    assert dv != modulo_11(numero)  # no pasa el módulo 11: no es el RUT de nadie
    assert comercio.nombre_fantasia == carga.COMERCIO_CARGA
    [oferta] = catalogo.ofertas
    assert 0 < oferta.stock <= 9999  # CHECK oferta_stock_tope (0029)
    # El mismo pañal de la demo: el id del producto sale de su nombre y presentación
    [panal] = catalogo.productos
    [de_la_demo] = [p for p in carga.catalogo_demo.CATALOGO.productos if p.clave == "panal"]
    assert carga.catalogo_demo.id_producto(panal) == carga.catalogo_demo.id_producto(de_la_demo)


@pytest.mark.parametrize(
    ("entorno", "pasarela", "corre"),
    [
        ("local", "falsa", True),
        ("pruebas", "falsa", True),
        ("staging", "falsa", False),
        ("staging", "integracion", False),
        ("produccion", "produccion", False),
        ("local", "integracion", False),
        ("local", None, False),
    ],
)
def test_solo_corre_en_local_con_la_pasarela_falsa(entorno: str, pasarela: str | None, corre: bool) -> None:
    assert (carga.motivo_para_no_correr(entorno, pasarela) is None) is corre


def test_sin_contrasena_no_corre(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv(carga.demo.VARIABLE_CONTRASENA, raising=False)

    assert carga.main(["--cuentas", "2"]) == 2
    assert carga.demo.VARIABLE_CONTRASENA in capsys.readouterr().err


# --- La guarda de la base local (hallazgo P2 de la revisión del 17-11) ------------------------------------------
# URLs sintéticas: hosts inventados y la contraseña «secreta-sintetica». Nunca la URL de un .env.

CLAVE = "secreta-sintetica"
REMOTAS = [
    f"postgresql+psycopg://matu_app:{CLAVE}@monorail.proxy.rlwy.net:41234/railway",
    f"postgresql+psycopg://matu_app:{CLAVE}@postgres.railway.internal:5432/matu",
    f"postgresql+psycopg://matu_app:{CLAVE}@db.example.com/matu",
    f"postgresql+psycopg://matu_app:{CLAVE}@10.0.0.5/matu",
    f"postgresql+psycopg://matu_app:{CLAVE}@localhost.example.com/matu",
    # El parámetro host manda sobre el de la URL en libpq: localhost por fuera y Railway por dentro
    f"postgresql+psycopg://matu_app:{CLAVE}@localhost/matu?host=monorail.proxy.rlwy.net",
    f"postgresql+psycopg://matu_app:{CLAVE}@localhost/matu?hostaddr=203.0.113.7",
    f"postgresql+psycopg://matu_app:{CLAVE}@localhost,db.example.com/matu",
    f"postgresql+psycopg://matu_app:{CLAVE}@localhost/matu?service=railway",
    "esto no es una url",
]
LOCALES = [
    f"postgresql+psycopg://matu_app:{CLAVE}@localhost:5432/matu_wt61",
    f"postgresql+psycopg://matu_app:{CLAVE}@127.0.0.1:5432/matu_wt61",
    f"postgresql+psycopg://matu_app:{CLAVE}@LOCALHOST/matu_wt61",
    f"postgresql+psycopg://matu_app:{CLAVE}@[::1]:5432/matu_wt61",
    f"postgresql+psycopg://matu_app:{CLAVE}@/matu_wt61?host=/var/run/postgresql",
    f"postgresql+psycopg://matu_app:{CLAVE}@/matu_wt61",
]


@pytest.mark.parametrize("url", REMOTAS)
def test_una_base_remota_se_rechaza(url: str) -> None:
    assert carga.motivo_por_la_base(url, {}) == carga.BASE_NO_LOCAL


@pytest.mark.parametrize("url", LOCALES)
def test_una_base_local_se_acepta(url: str) -> None:
    assert carga.motivo_por_la_base(url, {}) is None


@pytest.mark.parametrize(
    "entorno_os",
    [{"PGHOST": "monorail.proxy.rlwy.net"}, {"PGHOSTADDR": "203.0.113.7"}, {"PGSERVICE": "railway"}],
)
def test_sin_host_en_la_url_manda_el_entorno_de_libpq(entorno_os: dict[str, str]) -> None:
    assert carga.motivo_por_la_base(f"postgresql+psycopg://matu_app:{CLAVE}@/matu", entorno_os) is not None


def test_sin_database_url_no_corre() -> None:
    assert carga.motivo_por_la_base("", {}) is not None


@pytest.mark.parametrize("url", REMOTAS)
def test_el_motivo_no_muestra_la_url(url: str) -> None:
    motivo = carga.motivo_por_la_base(url, {})

    assert motivo is not None
    for pedazo in (url, CLAVE, "matu_app", "rlwy", "railway", "example.com", "203.0.113", "10.0.0.5"):
        assert pedazo not in motivo


def test_con_entorno_local_y_base_de_railway_se_detiene_antes_de_conectar(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """El caso del hallazgo: ENTORNO=local y PASARELA_PAGO=falsa, pero DATABASE_URL de Railway."""
    url = REMOTAS[0]
    configuracion = SimpleNamespace(
        entorno="local",
        pasarela_pago="falsa",
        database_url=SecretStr(url),
        pepper_email=SecretStr("p" * 32),
        pepper_pin=SecretStr("q" * 32),
        capa3_habilitada=True,
    )
    monkeypatch.setenv(carga.demo.VARIABLE_CONTRASENA, "clave-sintetica-de-carga")
    for variable in ("PGHOST", "PGHOSTADDR", "PGSERVICE"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr(carga, "obtener_configuracion", lambda: configuracion)

    def _no_conecta() -> Any:
        raise AssertionError("la preparación intentó conectar a una base remota")

    monkeypatch.setattr(carga, "fabrica_sesiones", _no_conecta)
    monkeypatch.setattr(carga.demo, "_custodia", _no_conecta)

    assert carga.main(["--cuentas", "2"]) == 2
    salida = capsys.readouterr()
    assert salida.err.strip() == carga.BASE_NO_LOCAL
    for pedazo in (url, CLAVE, "rlwy", "41234"):
        assert pedazo not in salida.err and pedazo not in salida.out


# --- La siembra, contra la base ---------------------------------------------------------------------------------


def _unicas(cuentas: int) -> tuple[list[Any], Any]:
    """Las familias y el catálogo de carga con correos, nombres y RUT únicos de esta prueba."""
    s = secrets.token_hex(4)
    familias = [
        replace(f, grupo=f"{f.grupo} {s}", admin=replace(f.admin, email=f"carga.{s}.{i}@example.com"))
        for i, f in enumerate(carga.familias_de_carga(cuentas))
    ]
    catalogo = carga.catalogo_de_carga()
    [categoria], [producto], [comercio] = catalogo.categorias, catalogo.productos, catalogo.comercios
    unico = replace(
        catalogo,
        categorias=(replace(categoria, nombre=f"{categoria.nombre} {s}"),),
        productos=(replace(producto, nombre=f"{producto.nombre} {s}", categoria=f"{categoria.nombre} {s}"),),
        comercios=(replace(comercio, rut=rut_ficticio(f"7{secrets.randbelow(10**7):07d}")),),
    )
    return familias, unico


@pytest.fixture
def sembradora() -> Any:
    rapido = HasherArgon2id(PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1, type=Type.ID))
    custodia = CustodiaKekEntorno(
        SecretStr(base64.b64encode(secrets.token_bytes(32)).decode()), kek_version=1, entorno="pruebas"
    )
    return carga.demo.Sembradora(
        fabrica=fabrica_sesiones(),
        pepper=secrets.token_bytes(32),
        version_politica=VERSION_PRUEBAS,
        reloj=RelojSistema(),
        hasher=rapido,
        custodia=custodia,
        pepper_pin=secrets.token_bytes(32),
        politica=POLITICA_PRUEBAS,
    )


@pytest.fixture
def limpieza() -> Iterator[tuple[Fabrica, list[Any]]]:
    fabrica = Fabrica()
    catalogos: list[Any] = []
    yield fabrica, catalogos
    fabrica.limpiar()
    with psycopg.connect(DSN, autocommit=True) as cx:
        for c in catalogos:
            cx.execute("DELETE FROM oferta WHERE id = ANY(%s)", (list(c.ofertas.values()),))
            cx.execute("DELETE FROM producto WHERE id = ANY(%s)", (list(c.productos.values()),))
            cx.execute("DELETE FROM comercio WHERE id = ANY(%s)", (list(c.comercios.values()),))
            cx.execute("DELETE FROM categoria_cuidado WHERE id = ANY(%s)", (list(c.categorias.values()),))


def _anotar(fabrica: Fabrica, semilla: Any) -> None:
    for familia in semilla.familias:
        if familia.grupo_id not in fabrica.ids("grupo_familiar"):
            for usuario_id in familia.usuarios:
                fabrica.anotar("usuario", usuario_id)
            fabrica.anotar("grupo_familiar", familia.grupo_id)


@requiere_base
def test_prepara_las_familias_y_el_stock_y_es_idempotente(sembradora: Any, limpieza: tuple[Fabrica, list[Any]]) -> None:
    fabrica, catalogos = limpieza
    familias, catalogo = _unicas(2)
    contrasena = f"clave-{uuid.uuid4().hex[:16]}"

    sembrado, semilla = carga.preparar(sembradora, contrasena, familias, catalogo)
    catalogos.append(sembrado)
    _anotar(fabrica, semilla)

    assert [c.creada for c in semilla.cuentas] == [True, True]
    with psycopg.connect(DSN) as cx:
        for familia in semilla.familias:
            [(direccion,)] = cx.execute(
                "SELECT direccion_entrega_id FROM persona_cuidada WHERE grupo_id = %s", (familia.grupo_id,)
            ).fetchall()
            assert direccion is not None
            finalidades = {
                f
                for (f,) in cx.execute(
                    "SELECT finalidad FROM consentimiento WHERE grupo_id = %s AND revocado_en IS NULL",
                    (familia.grupo_id,),
                ).fetchall()
            }
            assert {"consumo", "despacho"} <= finalidades
        [oferta_id] = sembrado.ofertas.values()
        assert cx.execute("SELECT stock, disponible FROM oferta WHERE id = %s", (oferta_id,)).fetchone() == (
            carga.STOCK_CARGA,
            True,
        )

    # Una corrida después de la carga: el stock vuelve al tope y las cuentas no se crean otra vez
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute("UPDATE oferta SET stock = 3 WHERE id = %s", (oferta_id,))
    otra, de_nuevo = carga.preparar(sembradora, contrasena, familias, catalogo)
    assert otra == sembrado
    assert [c.creada for c in de_nuevo.cuentas] == [False, False]
    with psycopg.connect(DSN) as cx:
        assert cx.execute("SELECT stock FROM oferta WHERE id = %s", (oferta_id,)).fetchone() == (carga.STOCK_CARGA,)
