"""MATU-79 · El repr y el str de la configuración no muestran ningún secreto ni cadena de conexión.

Una traza, un log de arranque o un print(config) en una sesión de depuración imprime el repr de Configuracion. Los
secretos van como SecretStr (se ven como '**********') y las cadenas de conexión, que siguen siendo str, con repr=False.
Todos los valores son sintéticos y se generan al correr la prueba: ninguno queda escrito en el repositorio.
"""

import base64
import secrets
import uuid

import pytest
from pydantic import SecretStr

from app.core.config import Configuracion
from app.core.vapid import generar_clave_privada

# Campos que guardan un secreto, una cadena de conexión o un dato que identifica una cuenta. Una variable nueva con
# uno de estos trozos en el nombre tiene que ser SecretStr o llevar repr=False (última prueba)
TROZOS_SENSIBLES = ("url", "clave", "pepper", "kek_entorno", "llave", "secreto", "comercio", "cuentas")


@pytest.fixture(autouse=True)
def _sin_env(configuracion_sin_env: None) -> None:
    """Solo las variables que fija cada prueba, sin el .env del equipo."""


def _secreto() -> str:
    return secrets.token_urlsafe(48)


def _url(esquema: str, usuario: str, destino: str) -> str:
    # Usuario y contraseña se unen al correr: el archivo no tiene ninguna URL con credenciales (detect-secrets)
    return f"{esquema}://" + ":".join((usuario, _secreto())) + f"@{destino}"


def _valores_sinteticos() -> dict[str, str]:
    base = "db.invalid:5432/matu_pruebas"
    return {
        "database_url": _url("postgresql+psycopg", "matu_app", base),
        "scheduler_database_url": _url("postgresql+psycopg", "matu_scheduler", base),
        "publisher_database_url": _url("postgresql+psycopg", "matu_publisher", base),
        "redis_url": _url("redis", "default", "redis.invalid:6379/0"),
        "pepper_email": _secreto(),
        "jwt_clave": _secreto(),
        "kek_entorno": base64.b64encode(secrets.token_bytes(32)).decode(),
        "pepper_pin": _secreto(),
        "pepper_limites": _secreto(),
        "pepper_recuperacion": _secreto(),
        "webpay_codigo_comercio": str(secrets.randbelow(9 * 10**11) + 10**11),
        "webpay_llave": _secreto(),
        "vapid_clave_privada": generar_clave_privada(),
        "codigo_retiro_secreto": _secreto(),
        "push_cuentas_permitidas": str(uuid.uuid4()),
    }


def _a_la_vista(valor: str) -> list[str]:
    """El valor y sus trozos con sentido: la contraseña de una URL puede aparecer sola, sin el resto."""
    trozos = [valor]
    if "://" in valor and "@" in valor:
        trozos.append(valor.split("://", 1)[1].split("@", 1)[0].split(":", 1)[1])
    return trozos


def test_el_repr_y_el_str_no_muestran_ningun_valor(monkeypatch: pytest.MonkeyPatch) -> None:
    valores = _valores_sinteticos()
    for campo, valor in valores.items():
        monkeypatch.setenv(campo.upper(), valor)
    monkeypatch.setenv("CUSTODIA_KEK", "entorno_sintetico")

    config = Configuracion()

    # Los valores sí se cargaron: si no, la prueba pasaría sin probar nada
    assert config.database_url == valores["database_url"]
    assert config.kek_entorno is not None and config.kek_entorno.get_secret_value() == valores["kek_entorno"]
    assert config.push_cuentas_permitidas == frozenset({uuid.UUID(valores["push_cuentas_permitidas"])})
    for texto in (repr(config), str(config)):
        for campo, valor in valores.items():
            for trozo in _a_la_vista(valor):
                assert trozo not in texto, f"{campo} aparece en el repr o el str de la configuración"


def test_los_usos_siguen_leyendo_la_cadena_de_conexion(monkeypatch: pytest.MonkeyPatch) -> None:
    # repr=False no cambia el valor: el motor de la API y las tareas lo leen igual que antes
    valores = _valores_sinteticos()
    monkeypatch.setenv("DATABASE_URL", valores["database_url"])
    monkeypatch.setenv("REDIS_URL", valores["redis_url"])
    config = Configuracion()
    assert isinstance(config.database_url, str) and config.database_url == valores["database_url"]
    assert config.redis_url == valores["redis_url"]


def test_todo_campo_sensible_es_secreto_o_no_sale_en_el_repr() -> None:
    expuestos = []
    for nombre, campo in Configuracion.model_fields.items():
        if not any(trozo in nombre for trozo in TROZOS_SENSIBLES):
            continue
        tipos = getattr(campo.annotation, "__args__", (campo.annotation,))
        es_secreto = SecretStr in tipos
        if not es_secreto and campo.repr:
            expuestos.append(nombre)
    assert expuestos == [], f"campos sensibles a la vista en el repr: {expuestos}"
