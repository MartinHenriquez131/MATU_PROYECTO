"""MATU-30 y MATU-64 · La semilla de demostración (infra/semillas/demo.py).

MATU-30: dos familias, sus cuentas inician sesión en la API, es idempotente y no corre en producción.
MATU-64: los cuatro roles, un celular y un correo por cuenta, la ficha completa y cifrada, los insumos con una alerta
abierta, el relevo de ejemplo que abre la ficha con su PIN, --restablecer y nada que parezca un dato real.

Las pruebas con base siembran familias con emails y nombres de grupo únicos y un catálogo copiado con nombres y RUT
únicos, para no chocar con una semilla de verdad en la base local, y los borran al terminar (la fábrica y la fixture
``catalogo``, como superusuario). La auditoría se queda: es de solo inserción y solo lleva identificadores. La KEK y
los peppers son de cada prueba, nunca los del .env.
"""

import base64
import importlib.util
import io
import re
import secrets
import subprocess
import sys
import uuid
from collections.abc import Iterator
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import psycopg
import pytest
from argon2 import PasswordHasher, Type
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import obtener_configuracion
from app.core.db import fabrica_sesiones, sesion_tenant
from app.main import crear_app
from app.modules.care_plan.api.dependencias import obtener_custodia, obtener_pepper_pin
from app.modules.care_plan.api.router_relevo_publico import obtener_sesiones_relevo
from app.modules.care_plan.application.ficha import PeticionFicha, leer_ficha
from app.modules.care_plan.domain.cifrado import ErrorCifrado
from app.modules.care_plan.domain.ficha import CampoFicha, normalizar_texto
from app.modules.care_plan.infrastructure.auditoria_ficha import AuditoriaFichaRegistro
from app.modules.care_plan.infrastructure.cifrador_aes_gcm import CifradorAesGcm
from app.modules.care_plan.infrastructure.custodia_kek_entorno import CustodiaKekEntorno
from app.modules.care_plan.infrastructure.repositorio_claves import RepositorioClavesSQL
from app.modules.care_plan.infrastructure.repositorio_ficha import RepositorioFichaSQL
from app.modules.consumption.application.alertas import por_acabarse
from app.modules.consumption.application.perfiles import PeticionConsumo
from app.modules.consumption.infrastructure.repositorio_alertas import RepositorioAlertasSQL
from app.modules.iam.api.dependencias import obtener_clave_jwt
from app.modules.iam.api.router import obtener_pepper_email
from app.modules.iam.infrastructure.hasher_argon2 import HasherArgon2id
from app.shared.auditoria_sql import RegistroAuditoriaSql
from app.shared.reloj_sistema import RelojSistema
from tests.base_datos import DSN, requiere_base
from tests.dobles.contador_ventana_en_memoria import limite_ip_en_memoria
from tests.dobles.contadores_en_memoria import demora_en_memoria
from tests.dobles.sesiones_relevo_en_memoria import SesionesRelevoEnMemoria
from tests.fabricas import Fabrica
from tests.rut_ficticio import rut_ficticio
from tests.textos import aparece_como_dato

RAIZ = Path(__file__).resolve().parents[2]
RUTA_SEMILLA = RAIZ / "infra" / "semillas" / "demo.py"

pytestmark = pytest.mark.rf("MATU-30")
MATU_64 = pytest.mark.rf("MATU-64")

# PIN conocido de las pruebas, como SEMILLA_PIN en la demo
PIN = "4821"


def _cargar_semilla() -> ModuleType:
    spec = importlib.util.spec_from_file_location("semilla_demo", RUTA_SEMILLA)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    # Registrado antes de ejecutarlo: dataclasses busca el módulo de cada clase en sys.modules
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


demo = _cargar_semilla()
CATALOGO = demo.cargar_catalogo_demo().CATALOGO


def _familias_unicas() -> tuple[Any, ...]:
    """Las familias de la semilla con emails y nombres de grupo únicos para esta prueba."""
    sufijo = uuid.uuid4().hex[:8]

    def unica(cuenta: Any) -> Any:
        local, dominio = cuenta.email.split("@")
        return replace(cuenta, email=f"{local}.{sufijo}@{dominio}")

    return tuple(
        replace(f, grupo=f"{f.grupo} {sufijo}", admin=unica(f.admin), miembros=tuple(unica(m) for m in f.miembros))
        for f in demo.FAMILIAS
    )


def _catalogo_unico() -> Any:
    """El catálogo de la semilla con nombres y RUT únicos (como test_semilla_catalogo.py)."""
    sufijo = uuid.uuid4().hex[:6]
    digitos = str(int(sufijo, 16) % 10**6).zfill(6)
    return replace(
        CATALOGO,
        categorias=tuple(replace(c, nombre=f"{c.nombre} {sufijo}") for c in CATALOGO.categorias),
        productos=tuple(
            replace(p, nombre=f"{p.nombre} {sufijo}", categoria=f"{p.categoria} {sufijo}") for p in CATALOGO.productos
        ),
        comercios=tuple(
            replace(c, nombre_fantasia=f"{c.nombre_fantasia} {sufijo}", rut=rut_ficticio(f"6{i}{digitos}"))
            for i, c in enumerate(CATALOGO.comercios)
        ),
    )


@pytest.fixture
def catalogo() -> Iterator[dict[str, uuid.UUID]]:
    """Los ids de los productos de una copia única del catálogo. Al terminar borra la copia y los insumos que la
    usan (sus alertas caen por ON DELETE CASCADE)."""
    sembrado = demo.cargar_catalogo_demo().sembrar_catalogo(fabrica_sesiones(), _catalogo_unico())
    yield sembrado.productos
    productos = list(sembrado.productos.values())
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute("DELETE FROM perfil_consumo WHERE producto_id = ANY(%s)", (productos,))
        cx.execute("DELETE FROM oferta WHERE id = ANY(%s)", (list(sembrado.ofertas.values()),))
        cx.execute("DELETE FROM producto WHERE id = ANY(%s)", (productos,))
        cx.execute("DELETE FROM comercio WHERE id = ANY(%s)", (list(sembrado.comercios.values()),))
        cx.execute("DELETE FROM categoria_cuidado WHERE id = ANY(%s)", (list(sembrado.categorias.values()),))


@pytest.fixture
def pepper() -> bytes:
    return secrets.token_bytes(32)


@pytest.fixture
def pepper_pin() -> bytes:
    return secrets.token_bytes(32)


@pytest.fixture
def custodia() -> CustodiaKekEntorno:
    # El adaptador real de la custodia, con una KEK de esta prueba: nunca la del .env
    return CustodiaKekEntorno(
        SecretStr(base64.b64encode(secrets.token_bytes(32)).decode()), kek_version=1, entorno="pruebas"
    )


@pytest.fixture
def sembradora(pepper: bytes, pepper_pin: bytes, custodia: CustodiaKekEntorno) -> Any:
    # Argon2id real con el costo mínimo: la API verifica con los parámetros guardados en el hash
    rapido = HasherArgon2id(PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1, type=Type.ID))
    # El reloj del sistema: las políticas RLS del relevo usan now() de la base
    return demo.Sembradora(
        fabrica=fabrica_sesiones(),
        pepper=pepper,
        version_politica="0.9",
        reloj=RelojSistema(),
        hasher=rapido,
        custodia=custodia,
        pepper_pin=pepper_pin,
        pin_relevo=PIN,
    )


def _anotar(fabrica: Fabrica, familias: list[Any]) -> None:
    for familia in familias:
        if familia.grupo_id not in fabrica.ids("grupo_familiar"):
            fabrica.anotar("grupo_familiar", familia.grupo_id)
        for usuario_id in familia.usuarios:
            if usuario_id not in fabrica.ids("usuario"):
                fabrica.anotar("usuario", usuario_id)


def _sembrar(fabrica: Fabrica, sembradora: Any, familias: Any, productos: Any, contrasena: str | None = None) -> Any:
    sembrado = demo.sembrar(sembradora, contrasena or f"clave-{secrets.token_hex(8)}", productos, familias)
    _anotar(fabrica, sembrado.familias)
    return sembrado


def _filas(sql: str, *parametros: Any) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchall()


def _estado(grupos: list[uuid.UUID]) -> dict[str, Any]:
    """Lo que la app ve de los grupos: personas activas, autorizaciones vigentes, ficha, insumos, alertas abiertas
    y relevos vigentes. Sin ids, para comparar dos siembras."""
    activas = "persona_cuidada_id IN (SELECT id FROM persona_cuidada WHERE eliminado_en IS NULL)"
    return {
        "membresias": _filas(
            "SELECT u.nombre, m.rol, m.puede_ver_plan FROM membresia m JOIN usuario u ON u.id = m.usuario_id"
            " WHERE m.grupo_id = ANY(%s::uuid[]) AND m.estado = 'activa' ORDER BY 1",
            grupos,
        ),
        "personas": _filas(
            "SELECT nombre FROM persona_cuidada WHERE grupo_id = ANY(%s::uuid[]) AND eliminado_en IS NULL ORDER BY 1",
            grupos,
        ),
        "autorizaciones": _filas(
            f"SELECT finalidad, count(*) FROM consentimiento WHERE grupo_id = ANY(%s::uuid[]) AND revocado_en IS NULL"
            f" AND {activas} GROUP BY 1 ORDER BY 1",
            grupos,
        ),
        "secciones": _filas(
            "SELECT s.tipo, s.version FROM plan_seccion s JOIN plan_cuidado p ON p.id = s.plan_id"
            f" WHERE p.grupo_id = ANY(%s::uuid[]) AND p.{activas} ORDER BY 1, 2",
            grupos,
        ),
        "insumos": _filas(
            "SELECT pr.unidades_por_envase, pc.stock_unidades, pc.dias_aviso, pc.activo FROM perfil_consumo pc"
            f" JOIN producto pr ON pr.id = pc.producto_id WHERE pc.grupo_id = ANY(%s::uuid[]) AND pc.{activas}"
            " ORDER BY 1, 2",
            grupos,
        ),
        "alertas": _filas(
            "SELECT a.estado, count(*) FROM alerta_quiebre a JOIN perfil_consumo p ON p.id = a.perfil_id"
            f" WHERE p.grupo_id = ANY(%s::uuid[]) AND p.{activas} GROUP BY 1",
            grupos,
        ),
        "relevos": _filas(
            "SELECT a.otorgado_a_nombre, a.secciones_permitidas FROM acceso_relevo a JOIN plan_cuidado p"
            " ON p.id = a.plan_id WHERE a.grupo_id = ANY(%s::uuid[]) AND a.revocado_en IS NULL"
            f" AND a.expira_en > now() AND p.{activas}",
            grupos,
        ),
    }


# --- Los datos, sin base ------------------------------------------------------------------------------------


def _cuentas() -> list[Any]:
    return [c for f in demo.FAMILIAS for c in (f.admin, *f.miembros)]


@MATU_64
def test_ninguna_cuenta_comparte_celular_ni_correo() -> None:
    cuentas = _cuentas()
    correos = [c.email.lower() for c in cuentas]
    celulares = [c.telefono for c in cuentas]
    relevos = [f.relevo.telefono for f in demo.FAMILIAS if f.relevo is not None]

    assert len(set(correos)) == len(correos)
    assert len(set(celulares)) == len(celulares)
    # El celular del relevo de ejemplo tampoco es el de una cuenta
    assert not set(relevos) & set(celulares)


@MATU_64
def test_los_cuatro_roles_en_una_familia() -> None:
    soto = demo.FAMILIAS[0]
    assert {c.rol for c in (soto.admin, *soto.miembros)} == {"admin", "cuidador", "pagador", "observador"}
    assert len(demo.FAMILIAS) == 2


# lenguaje.md, sección 3 (prohibidos) y lo que se evita en la ficha
PROHIBIDOS = (
    "diagnóstico", "diagnostico", "conducta", "incidente", "deterioro", "incontinencia", "paciente", "postrad",
    "demencia", "alzheimer", "crisis", "episodio", "descompensación", "adulto mayor",
)
# La serie +56 9 0000 00xx de las cuentas y +56 9 0000 01xx del relevo: no se asignan a nadie
CELULAR_DE_PRUEBA = re.compile(r"^\+5690000(00|01)\d{2}$")


def _textos_de_la_ficha() -> list[str]:
    return [t for f in demo.FAMILIAS for t in (*f.ficha.campos.values(), *f.ficha.secciones.values())]


@MATU_64
def test_nada_parece_un_dato_real() -> None:
    for cuenta in _cuentas():
        assert cuenta.email.split("@")[1] in {"example.com", "example.org"}, cuenta.email
        assert CELULAR_DE_PRUEBA.match(cuenta.telefono), cuenta.nombre
    for familia in demo.FAMILIAS:
        # MATU no pide RUT ni documento de la persona: la semilla tampoco
        assert familia.persona.referencia_documento is None
        if familia.relevo is not None:
            assert CELULAR_DE_PRUEBA.match(familia.relevo.telefono)
    for texto in _textos_de_la_ficha():
        bajo = texto.lower()
        assert not any(p in bajo for p in PROHIBIDOS), texto[:30]
        # Los teléfonos que la ficha nombra son de la misma serie de prueba
        for numero in re.findall(r"\+56 ?9 ?\d{4} ?\d{4}", texto):
            assert CELULAR_DE_PRUEBA.match(numero.replace(" ", "")), numero
        # Ni RUT ni correos dentro de la ficha
        assert not re.search(r"\d{1,2}\.?\d{3}\.?\d{3}-[\dkK]", texto)
        assert "@" not in texto


@MATU_64
def test_la_ficha_trae_los_tres_campos_y_secciones() -> None:
    for familia in demo.FAMILIAS:
        assert set(familia.ficha.campos) == set(CampoFicha)
        assert all(t.strip() for t in familia.ficha.campos.values())
        assert familia.ficha.secciones
        if familia.relevo is not None:
            # Solo se comparten secciones que la ficha trae (si no, compartir responde 422)
            assert set(familia.relevo.secciones) <= set(familia.ficha.secciones)


@MATU_64
def test_cada_familia_tiene_un_insumo_que_se_acaba_pronto_y_otro_que_no() -> None:
    productos = {p.clave for p in CATALOGO.productos}
    for familia in demo.FAMILIAS:
        assert {i.producto for i in familia.insumos} <= productos
        assert any(i.se_acaba_pronto() for i in familia.insumos)
        assert not all(i.se_acaba_pronto() for i in familia.insumos)


@MATU_64
def test_el_pin_de_la_semilla_son_4_digitos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(demo.VARIABLE_PIN, raising=False)
    assert demo._pin() is None
    monkeypatch.setenv(demo.VARIABLE_PIN, "0137")
    assert demo._pin() == "0137"
    for invalido in ("123", "12345", "12a4"):
        monkeypatch.setenv(demo.VARIABLE_PIN, invalido)
        with pytest.raises(SystemExit):
            demo._pin()
    # El generador de la semilla usa ese PIN y un token aleatorio de 32 bytes
    generador = demo.GeneradorCredencialesDemo("0137")
    assert generador.pin() == "0137" and "0137" not in repr(generador)
    assert len(generador.token()) == 32 and generador.token() != generador.token()


@MATU_64
def test_el_enlace_y_el_pin_van_a_un_archivo_que_git_ignora(tmp_path: Path) -> None:
    entregado = SimpleNamespace(token="t" * 43, pin="0137")
    relevo = demo.RelevoSembrado(
        acceso_id=uuid.uuid4(), grupo="Familia Soto", nombre_relevo="Rosa",
        expira_en=RelojSistema().ahora() + timedelta(days=7), entregado=entregado,
    )
    archivo = tmp_path / "salida" / "relevo-demo.txt"

    enlace = demo.guardar_relevo(relevo, "https://demo.example.org", archivo)

    assert enlace == "https://demo.example.org/r#" + "t" * 43
    contenido = archivo.read_text(encoding="utf-8")
    assert f"enlace: {enlace}" in contenido and "pin: 0137" in contenido
    # El archivo de verdad está en una carpeta que git ignora
    ignorado = subprocess.run(
        ["git", "check-ignore", "-q", str(demo.ARCHIVO_RELEVO)], cwd=RAIZ, check=False, capture_output=True
    )
    assert ignorado.returncode == 0
    # El repr del relevo sembrado no lleva el token ni el PIN
    assert "0137" not in repr(relevo) and "t" * 43 not in repr(relevo)


# --- En la base ----------------------------------------------------------------------------------------------


@requiere_base
def test_crea_dos_familias_con_los_cuatro_roles(
    fabrica: Fabrica, sembradora: Any, pepper: bytes, catalogo: dict[str, uuid.UUID]
) -> None:
    contrasena = f"clave-{secrets.token_hex(8)}"

    sembrado = _sembrar(fabrica, sembradora, _familias_unicas(), catalogo, contrasena)

    assert len(sembrado.familias) == 2 and all(c.creada for c in sembrado.cuentas)
    soto, riquelme = (f.grupo_id for f in sembrado.familias)
    membresias = _filas(
        "SELECT g.id, u.nombre, m.rol, m.puede_ver_plan, m.invitado_por IS NOT NULL FROM membresia m"
        " JOIN grupo_familiar g ON g.id = m.grupo_id JOIN usuario u ON u.id = m.usuario_id"
        " WHERE g.id = ANY(%s::uuid[]) ORDER BY u.nombre",
        [soto, riquelme],
    )
    assert sorted(membresias) == sorted(
        [
            (soto, "Carmen Fuentes", "admin", False, False),
            (soto, "Luisa Contreras", "cuidador", False, True),
            (soto, "Rodrigo Soto", "pagador", True, True),
            (soto, "Javiera Soto", "observador", False, True),
            (riquelme, "Patricia Riquelme", "admin", False, False),
            (riquelme, "Tomás Riquelme", "observador", False, True),
        ]
    )
    consentimientos = _filas(
        "SELECT p.grupo_id, p.nombre, c.finalidad, c.calidad_otorgante, c.version_politica, c.otorgado_en,"
        " c.revision_vence_en FROM persona_cuidada p JOIN consentimiento c ON c.persona_cuidada_id = p.id"
        " WHERE p.grupo_id = ANY(%s::uuid[]) AND c.revocado_en IS NULL",
        [soto, riquelme],
    )
    por_grupo: dict[uuid.UUID, dict[str, tuple[Any, ...]]] = {}
    for fila in consentimientos:
        por_grupo.setdefault(fila[0], {})[fila[2]] = fila
    assert set(por_grupo[soto]) == set(por_grupo[riquelme]) == {"plan_cuidado", "consumo"}
    for finalidad in ("plan_cuidado", "consumo"):
        maria, hernan = por_grupo[soto][finalidad], por_grupo[riquelme][finalidad]
        assert maria[1] == "María Soto" and maria[3:5] == ("cuidador_de_hecho", "0.9")
        assert maria[6] - maria[5] >= timedelta(days=365)
        assert hernan[1] == "Hernán Riquelme" and hernan[3:5] == ("titular", "0.9")
        assert hernan[6] is None

    # Cada cuenta con su celular, y las cuentas sirven para iniciar sesión en la API con el mismo pepper
    celulares = _filas(
        "SELECT telefono FROM usuario WHERE id = ANY(%s::uuid[])", [u for f in sembrado.familias for u in f.usuarios]
    )
    assert len({c[0] for c in celulares}) == 6
    app = crear_app(stream_logs=io.StringIO())
    app.dependency_overrides[obtener_pepper_email] = lambda: pepper
    demora_en_memoria(app)
    app.dependency_overrides[obtener_clave_jwt] = lambda: secrets.token_hex(32).encode()
    with TestClient(app, raise_server_exceptions=False) as cliente:
        for nombre in ("Rodrigo Soto", "Luisa Contreras"):
            cuenta = next(c for c in sembrado.cuentas if c.nombre == nombre)
            sesion = cliente.post("/v1/sesiones", json={"email": cuenta.email, "contrasena": contrasena})
            assert sesion.status_code == 200, nombre


@requiere_base
@MATU_64
def test_es_idempotente(fabrica: Fabrica, sembradora: Any, catalogo: dict[str, uuid.UUID]) -> None:
    familias = _familias_unicas()

    primera = _sembrar(fabrica, sembradora, familias, catalogo)
    grupos = [f.grupo_id for f in primera.familias]
    antes = _estado(grupos)
    auditoria = _filas("SELECT count(*) FROM auditoria WHERE grupo_id = ANY(%s::uuid[])", grupos)
    segunda = _sembrar(fabrica, sembradora, familias, catalogo)

    assert [f.grupo_id for f in segunda.familias] == grupos
    assert [f.usuarios for f in segunda.familias] == [f.usuarios for f in primera.familias]
    assert [f.persona_id for f in segunda.familias] == [f.persona_id for f in primera.familias]
    assert not any(c.creada for c in segunda.cuentas)
    assert not any(f.persona_creada or f.campos_escritos or f.secciones_escritas or f.insumos_creados
                   for f in segunda.familias)
    assert segunda.alertas_creadas == 0
    # El relevo de ejemplo es el mismo, y su PIN no se vuelve a entregar
    assert segunda.familias[0].relevo.acceso_id == primera.familias[0].relevo.acceso_id
    assert segunda.familias[0].relevo.entregado is None
    assert _estado(grupos) == antes
    # Ni una lectura ni una escritura más en la auditoría: la segunda corrida no toca nada
    assert _filas("SELECT count(*) FROM auditoria WHERE grupo_id = ANY(%s::uuid[])", grupos) == auditoria
    assert len(antes["membresias"]) == 6 and len(antes["personas"]) == 2
    assert antes["autorizaciones"] == [("consumo", 2), ("plan_cuidado", 2)]
    assert len(antes["secciones"]) == 11 and len(antes["insumos"]) == 5 and len(antes["relevos"]) == 1


@requiere_base
@MATU_64
def test_corrige_el_celular_compartido_de_una_semilla_anterior(
    fabrica: Fabrica, sembradora: Any, catalogo: dict[str, uuid.UUID]
) -> None:
    familias = _familias_unicas()
    primera = _sembrar(fabrica, sembradora, familias, catalogo)
    usuarios = [u for f in primera.familias for u in f.usuarios]
    # Como dejaba la semilla de MATU-30: todas con el mismo celular, verificado
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute("UPDATE usuario SET telefono = '+56900000000' WHERE id = ANY(%s::uuid[])", (usuarios,))
        cx.execute("UPDATE usuario SET celular_verificado_en = now() WHERE id = ANY(%s::uuid[])", (usuarios,))

    _sembrar(fabrica, sembradora, familias, catalogo)

    filas = _filas("SELECT telefono, celular_verificado_en FROM usuario WHERE id = ANY(%s::uuid[])", usuarios)
    assert len({f[0] for f in filas}) == 6
    # El trigger de la 0012 deja sin verificar el celular que cambió
    assert all(f[1] is None for f in filas)


@requiere_base
@MATU_64
def test_la_ficha_queda_cifrada_y_descifra_con_su_clave(
    fabrica: Fabrica, sembradora: Any, catalogo: dict[str, uuid.UUID], custodia: CustodiaKekEntorno
) -> None:
    familias = _familias_unicas()
    sembrado = _sembrar(fabrica, sembradora, familias, catalogo)

    for familia, demo_familia in zip(sembrado.familias, familias, strict=True):
        esperados = {c.value: normalizar_texto(t) for c, t in demo_familia.ficha.campos.items()}
        esperados |= {s.value: normalizar_texto(t) for s, t in demo_familia.ficha.secciones.items()}
        # En la base, como superusuario: solo bytes cifrados con su nonce y su tag, nunca el texto
        guardadas = _filas(
            "SELECT s.tipo, s.contenido_cifrado, s.nonce, s.tag_auth FROM plan_seccion s"
            " JOIN plan_cuidado p ON p.id = s.plan_id WHERE p.persona_cuidada_id = %s",
            familia.persona_id,
        )
        assert {g[0] for g in guardadas} == set(esperados)
        for tipo, contenido, nonce, tag in guardadas:
            assert len(nonce) == 12 and len(tag) == 16
            texto = esperados[tipo].encode("utf-8")
            assert texto not in bytes(contenido) and texto[:12] not in bytes(contenido)
        assert _filas("SELECT count(*) FROM clave_datos WHERE persona_cuidada_id = %s", familia.persona_id) == [(1,)]

        # Con la custodia de la semilla, la ficha se lee completa por el caso de uso de la API
        admin = familia.usuarios[0]
        peticion = PeticionFicha(grupo_id=familia.grupo_id, usuario_id=admin, persona_cuidada_id=familia.persona_id)
        reloj = RelojSistema()
        with sesion_tenant(fabrica_sesiones(), usuario_id=admin, grupo_id=familia.grupo_id) as sesion:
            ficha = leer_ficha(
                peticion,
                RepositorioFichaSQL(sesion, familia.grupo_id),
                CifradorAesGcm(custodia, RepositorioClavesSQL(sesion)),
                AuditoriaFichaRegistro(sesion, RegistroAuditoriaSql(sesion, reloj)),
                reloj,
            )
        leidos = {c.value: e.texto for c, e in ficha.campos.items()} | {
            s.value: e.texto for s, e in ficha.secciones.items()
        }
        assert leidos == esperados
        assert ficha.completitud == 100

        # Con otra KEK no se abre: la clave de la persona está envuelta con la de la custodia
        otra = CustodiaKekEntorno(
            SecretStr(base64.b64encode(secrets.token_bytes(32)).decode()), kek_version=1, entorno="pruebas"
        )
        with pytest.raises(ErrorCifrado), sesion_tenant(
            fabrica_sesiones(), usuario_id=admin, grupo_id=familia.grupo_id
        ) as sesion:
            leer_ficha(
                peticion,
                RepositorioFichaSQL(sesion, familia.grupo_id),
                CifradorAesGcm(otra, RepositorioClavesSQL(sesion)),
                AuditoriaFichaRegistro(sesion, RegistroAuditoriaSql(sesion, reloj)),
                reloj,
            )


@requiere_base
@MATU_64
def test_hay_una_alerta_abierta_y_se_ve_en_se_acaba_pronto(
    fabrica: Fabrica, sembradora: Any, catalogo: dict[str, uuid.UUID]
) -> None:
    familias = _familias_unicas()
    sembrado = _sembrar(fabrica, sembradora, familias, catalogo)

    assert sembrado.alertas_creadas == 2
    for familia, demo_familia in zip(sembrado.familias, familias, strict=True):
        pronto = {catalogo[i.producto] for i in demo_familia.insumos if i.se_acaba_pronto()}
        abiertas = _filas(
            "SELECT p.producto_id FROM alerta_quiebre a JOIN perfil_consumo p ON p.id = a.perfil_id"
            " WHERE p.persona_cuidada_id = %s AND a.estado = 'pendiente'"
            " AND a.fecha_prevista = p.fecha_quiebre_estimada",
            familia.persona_id,
        )
        assert {a[0] for a in abiertas} == pronto and len(abiertas) == 1
        # Con su evento en el outbox, como el trabajo de las 04:00
        assert _filas(
            "SELECT count(*) FROM evento_outbox WHERE grupo_id = %s AND tipo = 'QuiebreProximo'", familia.grupo_id
        ) == [(1,)]
        # «Se acaban pronto», como la lee la app (decisión 53), con «Te estamos avisando»
        admin = familia.usuarios[0]
        with sesion_tenant(fabrica_sesiones(), usuario_id=admin, grupo_id=familia.grupo_id) as sesion:
            avisados = por_acabarse(
                PeticionConsumo(grupo_id=familia.grupo_id, usuario_id=admin, persona_id=familia.persona_id),
                RelojSistema(),
                RepositorioAlertasSQL(sesion, familia.grupo_id),
            )
        assert {a.leido.perfil.producto_id for a in avisados if a.avisando} == pronto
        assert all(a.alerta_id is not None for a in avisados if a.avisando)


class _Relevo:
    """La API con las rutas públicas del relevo, con la custodia y el pepper de la semilla. Las sesiones de relevo
    y el límite por IP van en memoria, sin Redis. El cliente es https: la cookie del relevo es Secure."""

    def __init__(self, custodia: CustodiaKekEntorno, pepper_pin: bytes) -> None:
        self.logs = io.StringIO()
        reloj = RelojSistema()
        self.app = crear_app(stream_logs=self.logs)
        self.app.dependency_overrides[obtener_custodia] = lambda: custodia
        self.app.dependency_overrides[obtener_pepper_pin] = lambda: pepper_pin
        sesiones = SesionesRelevoEnMemoria(reloj)
        self.app.dependency_overrides[obtener_sesiones_relevo] = lambda: sesiones
        limite_ip_en_memoria(self.app, reloj)

    def cliente(self) -> TestClient:
        return TestClient(self.app, base_url="https://testserver", raise_server_exceptions=False)


@requiere_base
@MATU_64
def test_el_relevo_de_ejemplo_abre_la_ficha_con_su_pin(
    fabrica: Fabrica,
    sembradora: Any,
    catalogo: dict[str, uuid.UUID],
    custodia: CustodiaKekEntorno,
    pepper_pin: bytes,
) -> None:
    familias = _familias_unicas()
    entregados: list[Any] = []
    sembradora.al_crear_relevo = entregados.append
    sembrado = _sembrar(fabrica, sembradora, familias, catalogo)
    relevo = sembrado.familias[0].relevo
    assert relevo is not None and relevo.entregado is not None
    # main lo recibe apenas se confirma, para guardarlo aunque la corrida se detenga después
    assert entregados == [relevo]
    token, pin = relevo.entregado.token, relevo.entregado.pin
    assert pin == PIN
    # Vale 7 días, dentro del máximo de 30
    assert timedelta(days=6) < relevo.expira_en - RelojSistema().ahora() <= timedelta(days=7)

    api = _Relevo(custodia, pepper_pin)
    with api.cliente() as cliente:
        presentacion = cliente.post("/v1/relevo/presentacion", json={"token": token})
        assert presentacion.json() == {"nombre_pila_comparte": "Carmen", "nombre_pila": "María"}
        otro_pin = "0000" if pin != "0000" else "1111"
        assert cliente.post("/v1/relevo/canje", json={"token": token, "pin": otro_pin}).status_code == 401
        canje = cliente.post("/v1/relevo/canje", json={"token": token, "pin": pin})
        assert canje.status_code == 204, canje.text
        ficha = cliente.get("/v1/relevo/ficha")

    assert ficha.status_code == 200, ficha.text
    cuerpo = ficha.json()
    soto = familias[0]
    assert cuerpo["campos"] == {c.value: {"texto": normalizar_texto(t)} for c, t in soto.ficha.campos.items()}
    assert [s["tipo"] for s in cuerpo["secciones"]] == [s.value for s in soto.relevo.secciones]
    assert cuerpo["secciones"][0]["texto"] == normalizar_texto(soto.ficha.secciones[soto.relevo.secciones[0]])
    # Lo que no se compartió no llega, ni el nombre completo
    assert soto.ficha.secciones[next(iter(set(soto.ficha.secciones) - set(soto.relevo.secciones)))] not in ficha.text
    assert "María Soto" not in ficha.text
    # Ni el token ni el PIN quedan en los logs de la API
    logs = api.logs.getvalue()
    assert token not in logs and not aparece_como_dato(pin, logs)


@requiere_base
@MATU_64
def test_restablecer_deja_todo_como_recien_sembrado(
    fabrica: Fabrica,
    sembradora: Any,
    catalogo: dict[str, uuid.UUID],
    custodia: CustodiaKekEntorno,
    pepper_pin: bytes,
) -> None:
    familias = _familias_unicas()
    primera = _sembrar(fabrica, sembradora, familias, catalogo)
    grupos = [f.grupo_id for f in primera.familias]
    recien_sembrado = _estado(grupos)
    viejo = primera.familias[0]
    # Lo que deja una demo: el enlace cortado, una alerta resuelta, un insumo menos y un campo editado
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute("UPDATE acceso_relevo SET revocado_en = now() WHERE id = %s", (viejo.relevo.acceso_id,))
        cx.execute(
            "UPDATE alerta_quiebre SET estado = 'resuelta', cerrada_en = now() WHERE perfil_id IN"
            " (SELECT id FROM perfil_consumo WHERE grupo_id = %s)",
            (viejo.grupo_id,),
        )
        cx.execute(
            "DELETE FROM perfil_consumo WHERE id = (SELECT id FROM perfil_consumo WHERE grupo_id = %s"
            " AND fecha_quiebre_estimada > current_date + 10 LIMIT 1)",
            (grupos[1],),
        )
        cx.execute(
            "UPDATE plan_seccion SET version = version + 1 WHERE tipo = 'rutina' AND plan_id IN"
            " (SELECT id FROM plan_cuidado WHERE grupo_id = %s)",
            (viejo.grupo_id,),
        )
    assert _estado(grupos) != recien_sembrado

    borradas = demo.restablecer(sembradora, familias)
    segunda = _sembrar(fabrica, sembradora, familias, catalogo)

    assert borradas == 2
    assert [f.grupo_id for f in segunda.familias] == grupos
    assert [f.usuarios for f in segunda.familias] == [f.usuarios for f in primera.familias]
    assert not any(c.creada for c in segunda.cuentas)
    assert all(f.persona_creada for f in segunda.familias)
    assert _estado(grupos) == recien_sembrado
    # Las personas de antes quedaron borradas como pide MATU-72, con su clave destruida y sus enlaces cortados
    for antes in primera.familias:
        assert _filas(
            "SELECT datos_borrados_en IS NOT NULL FROM persona_cuidada WHERE id = %s", antes.persona_id
        ) == [(True,)]
        assert _filas(
            "SELECT count(*) FROM acceso_relevo a JOIN plan_cuidado p ON p.id = a.plan_id"
            " WHERE p.persona_cuidada_id = %s AND a.revocado_en IS NULL",
            antes.persona_id,
        ) == [(0,)]
    # El relevo nuevo abre la ficha nueva con el mismo PIN conocido; el viejo ya no sirve
    nuevo = segunda.familias[0].relevo
    assert nuevo is not None and nuevo.entregado is not None and nuevo.acceso_id != viejo.relevo.acceso_id
    with _Relevo(custodia, pepper_pin).cliente() as cliente:
        viejo_canje = cliente.post("/v1/relevo/canje", json={"token": viejo.relevo.entregado.token, "pin": PIN})
        assert viejo_canje.status_code == 410
        nuevo_canje = cliente.post("/v1/relevo/canje", json={"token": nuevo.entregado.token, "pin": PIN})
        assert nuevo_canje.status_code == 204
        assert cliente.get("/v1/relevo/ficha").status_code == 200


@requiere_base
@MATU_64
def test_restablecer_sin_semilla_no_borra_nada(sembradora: Any) -> None:
    assert demo.restablecer(sembradora, _familias_unicas()) == 0


@pytest.mark.usefixtures("configuracion_sin_env")
def test_no_corre_en_produccion(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("ENTORNO", "produccion")
    monkeypatch.setenv("POLITICA_VERSION", "0.9")
    obtener_configuracion.cache_clear()
    try:
        assert demo.main() == 2
        assert demo.main(["--restablecer"]) == 2
    finally:
        obtener_configuracion.cache_clear()
    assert "produccion" in capsys.readouterr().err


# --- Solo como matu_app ---------------------------------------------------------------------------------

# Sin contraseña en la URL: basta para comprobar que el mensaje no la muestra
URL_SINTETICA = "postgresql+psycopg://dueno_sintetico@127.0.0.1:1/base_sintetica"


class _SesionFalsa:
    def __init__(self, resultado: str | Exception) -> None:
        self.resultado = resultado

    def __enter__(self) -> "_SesionFalsa":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, sentencia: Any) -> "_SesionFalsa":
        assert str(sentencia) == "SELECT current_user"
        if isinstance(self.resultado, Exception):
            raise self.resultado
        return self

    def scalar_one(self) -> str:
        assert isinstance(self.resultado, str)
        return self.resultado


@pytest.fixture
def entorno_local(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    """Configuración local completa y sintética, con DATABASE_URL apuntando a nada. Sin el archivo .env: lo que
    la prueba quita del entorno no vuelve desde el archivo."""
    from app.core import config

    monkeypatch.setitem(config.Configuracion.model_config, "env_file", None)
    monkeypatch.setenv("ENTORNO", "local")
    monkeypatch.setenv("POLITICA_VERSION", "0.9")
    monkeypatch.setenv("PEPPER_EMAIL", secrets.token_hex(32))
    monkeypatch.setenv("JWT_CLAVE", secrets.token_hex(32))
    monkeypatch.setenv("PEPPER_PIN", secrets.token_hex(32))
    monkeypatch.setenv("CUSTODIA_KEK", "entorno_sintetico")
    monkeypatch.setenv("KEK_ENTORNO", base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.setenv("DATABASE_URL", URL_SINTETICA)
    monkeypatch.setattr(demo, "ARCHIVO_RELEVO", tmp_path / "relevo-demo.txt")
    monkeypatch.setattr(demo, "ARCHIVO_CONTRASENA", tmp_path / "contrasena-demo.txt")
    monkeypatch.delenv(demo.VARIABLE_CONTRASENA, raising=False)
    monkeypatch.delenv(demo.VARIABLE_PIN, raising=False)
    obtener_configuracion.cache_clear()
    yield
    obtener_configuracion.cache_clear()


def _con_rol(monkeypatch: pytest.MonkeyPatch, resultado: str | Exception) -> list[str]:
    """Hace que la semilla vea ``resultado`` al preguntar current_user, y anota si llegó a sembrar."""
    sembro: list[str] = []
    monkeypatch.setattr(demo, "fabrica_sesiones", lambda: lambda: _SesionFalsa(resultado))

    def sembrar(*_: Any, **__: Any) -> Any:
        sembro.append("sembro")
        return demo.SemillaSembrada(familias=[], cuentas=[])

    monkeypatch.setattr(demo, "sembrar", sembrar)

    def restablecer(*_: Any, **__: Any) -> int:
        sembro.append("restablecer")
        return 0

    monkeypatch.setattr(demo, "restablecer", restablecer)

    def sembrar_catalogo(*_: Any, **__: Any) -> Any:
        sembro.append("catalogo")
        return SimpleNamespace(productos={}, ofertas={}, comercios={})

    # MATU-59: el catálogo se siembra antes de las familias, con la misma conexión ya verificada
    monkeypatch.setattr(demo, "sembrar_catalogo_demo", sembrar_catalogo)
    return sembro


@pytest.mark.parametrize("rol", ["postgres", "matu_owner", "MATU_APP"])
def test_se_niega_si_no_esta_conectada_como_matu_app(
    entorno_local: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], rol: str
) -> None:
    sembro = _con_rol(monkeypatch, rol)

    assert demo.main(["--restablecer"]) == 2

    salida = capsys.readouterr()
    assert sembro == []
    assert "matu_app" in salida.err
    for fragmento in (URL_SINTETICA, "dueno_sintetico", "127.0.0.1", "base_sintetica"):
        assert fragmento not in salida.err + salida.out


def test_si_no_se_conecta_sale_con_1_sin_mostrar_la_url(
    entorno_local: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from sqlalchemy.exc import OperationalError

    sembro = _con_rol(monkeypatch, OperationalError("SELECT current_user", {}, Exception(URL_SINTETICA)))

    assert demo.main() == 1

    salida = capsys.readouterr()
    assert sembro == []
    assert "DATABASE_URL" in salida.err
    assert URL_SINTETICA not in salida.err + salida.out


def test_como_matu_app_siembra(entorno_local: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    sembro = _con_rol(monkeypatch, "matu_app")

    assert demo.main([]) == 0
    assert sembro == ["catalogo", "sembro"]


@MATU_64
def test_restablecer_borra_antes_de_sembrar(entorno_local: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    sembro = _con_rol(monkeypatch, "matu_app")
    demo.ARCHIVO_RELEVO.write_text("enlace viejo", encoding="utf-8")

    assert demo.main(["--restablecer"]) == 0

    assert sembro == ["restablecer", "catalogo", "sembro"]
    # El enlace y el PIN del relevo anterior ya no sirven: el archivo se borra
    assert not demo.ARCHIVO_RELEVO.exists()


@MATU_64
@pytest.mark.parametrize("falta", ["CUSTODIA_KEK", "PEPPER_PIN"])
def test_sin_custodia_ni_pepper_pin_no_siembra(
    entorno_local: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], falta: str
) -> None:
    monkeypatch.delenv(falta)
    if falta == "CUSTODIA_KEK":
        monkeypatch.delenv("KEK_ENTORNO")
    obtener_configuracion.cache_clear()
    sembro = _con_rol(monkeypatch, "matu_app")

    assert demo.main() == 2

    assert sembro == []
    assert falta in capsys.readouterr().err


# --- Las credenciales nunca salen sin --mostrar-credenciales (regla de Jorge del 08-11) --------------------------

TOKEN_FALSO = "Tk" + "x9" * 20 + "Q"  # 43 caracteres, como un token base64url
PIN_FALSO = "7319"


def _sembrar_con_credenciales(monkeypatch: pytest.MonkeyPatch, falla: Exception | None = None) -> list[str]:
    """La semilla crea dos cuentas con la contraseña aleatoria y el relevo de ejemplo y, si ``falla``, se detiene
    justo después, como lo haría con la segunda familia."""
    sembro = _con_rol(monkeypatch, "matu_app")

    def sembrar(sembradora: Any, contrasena: str, productos: Any, *_: Any, **__: Any) -> Any:
        sembradora.cuentas_creadas += 2
        relevo = demo.RelevoSembrado(
            acceso_id=uuid.uuid4(), grupo="Familia Soto", nombre_relevo="Rosa",
            expira_en=RelojSistema().ahora() + timedelta(days=7),
            entregado=SimpleNamespace(token=TOKEN_FALSO, pin=PIN_FALSO),
        )
        sembradora.al_crear_relevo(relevo)
        if falla is not None:
            raise falla
        familia = demo.FamiliaSembrada(
            grupo_id=uuid.uuid4(), usuarios=(), persona_id=uuid.uuid4(), persona_creada=True, relevo=relevo
        )
        return demo.SemillaSembrada(familias=[familia], cuentas=[])

    monkeypatch.setattr(demo, "sembrar", sembrar)
    return sembro


def _contrasena_guardada() -> str:
    linea = next(x for x in demo.ARCHIVO_CONTRASENA.read_text(encoding="utf-8").splitlines() if x.startswith("contr"))
    return linea.split(": ", 1)[1]


def _credenciales_en(salida: str) -> list[str]:
    """Cuáles de las tres credenciales aparecen en la salida."""
    encontradas = []
    if TOKEN_FALSO in salida:
        encontradas.append("token")
    if aparece_como_dato(PIN_FALSO, salida):
        encontradas.append("pin")
    if _contrasena_guardada() in salida:
        encontradas.append("contrasena")
    return encontradas


def _archivos_completos() -> None:
    relevo = demo.ARCHIVO_RELEVO.read_text(encoding="utf-8")
    assert TOKEN_FALSO in relevo and f"pin: {PIN_FALSO}" in relevo
    assert len(_contrasena_guardada()) >= 10


@MATU_64
def test_sin_la_opcion_la_salida_no_trae_credenciales(
    entorno_local: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _sembrar_con_credenciales(monkeypatch)

    assert demo.main([]) == 0

    capturada = capsys.readouterr()
    salida = capturada.out + capturada.err
    _archivos_completos()
    assert _credenciales_en(salida) == []
    # Solo dice dónde quedaron
    assert str(demo.ARCHIVO_RELEVO) in salida and str(demo.ARCHIVO_CONTRASENA) in salida


@MATU_64
def test_con_la_opcion_la_salida_trae_las_credenciales(
    entorno_local: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _sembrar_con_credenciales(monkeypatch)

    assert demo.main(["--mostrar-credenciales"]) == 0

    capturada = capsys.readouterr()
    _archivos_completos()
    assert _credenciales_en(capturada.out + capturada.err) == ["token", "pin", "contrasena"]


@MATU_64
@pytest.mark.parametrize("falla", ["semilla", "base"])
def test_si_se_detiene_a_la_mitad_tampoco_salen(
    entorno_local: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], falla: str
) -> None:
    from sqlalchemy.exc import OperationalError

    # El error de la base trae el token en su texto: la semilla no lo muestra
    error = (
        demo.SemillaInconsistente("Un miembro de la semilla ya está en el grupo con otro rol")
        if falla == "semilla"
        else OperationalError("INSERT", {"token": TOKEN_FALSO}, Exception(TOKEN_FALSO))
    )
    _sembrar_con_credenciales(monkeypatch, error)

    assert demo.main([]) == 1

    capturada = capsys.readouterr()
    salida = capturada.out + capturada.err
    # El enlace, el PIN y la contraseña quedaron guardados, y la salida dice dónde, sin mostrarlos
    _archivos_completos()
    assert _credenciales_en(salida) == []
    assert str(demo.ARCHIVO_RELEVO) in salida and str(demo.ARCHIVO_CONTRASENA) in salida


@MATU_64
def test_los_archivos_de_credenciales_son_solo_del_dueno(tmp_path: Path) -> None:
    archivo = tmp_path / "salida" / "contrasena-demo.txt"
    demo.guardar_contrasena("clave-sintetica-123", 3, archivo)
    assert "contrasena: clave-sintetica-123" in archivo.read_text(encoding="utf-8")
    if sys.platform != "win32":
        assert archivo.stat().st_mode & 0o077 == 0
    # Las dos van a la carpeta que git ignora
    for ruta in (demo.ARCHIVO_RELEVO, demo.ARCHIVO_CONTRASENA):
        ignorado = subprocess.run(["git", "check-ignore", "-q", str(ruta)], cwd=RAIZ, check=False)
        assert ignorado.returncode == 0, ruta.name


@requiere_base
def test_la_conexion_de_la_api_entra_como_matu_app() -> None:
    assert demo.rol_de_la_conexion(fabrica_sesiones()) == "matu_app"
