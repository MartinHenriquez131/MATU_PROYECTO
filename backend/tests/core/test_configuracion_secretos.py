"""MATU-79 · El repr y el str de la configuración no muestran ningún secreto ni cadena de conexión.

Una traza, un log de arranque o un print(config) en una sesión de depuración imprime el repr de Configuracion. Los
secretos van como SecretStr (se ven como '**********'). Las tres cadenas de conexión a la base, REDIS_URL,
WEBPAY_CODIGO_COMERCIO y PUSH_CUENTAS_PERMITIDAS llevaban repr=False desde el 18-11, que no los sacaba de model_dump:
ahora las cinco primeras son SecretStr y la lista de cuentas va con exclude=True. Todos los valores son sintéticos y se
generan al correr la prueba: ninguno queda escrito en el repositorio.

Trazan a RNF-08 (arquitectura 2.2, «fuera de los registros», que sale de la sección 11.6, donde están los secretos).
"""

import base64
import secrets
import uuid
from collections.abc import Callable

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Configuracion
from app.core.vapid import generar_clave_privada

# Campos que guardan un secreto, una cadena de conexión o un dato que identifica una cuenta. Una variable nueva con
# uno de estos trozos en el nombre tiene que ser SecretStr o llevar repr=False (última prueba)
TROZOS_SENSIBLES = ("url", "clave", "pepper", "kek_entorno", "llave", "secreto", "comercio", "cuentas")

# La deuda de MATU-79: los campos que pasaron de repr=False a SecretStr
MIGRADOS_A_SECRETSTR = (
    "database_url",
    "scheduler_database_url",
    "publisher_database_url",
    "redis_url",
    "webpay_codigo_comercio",
)
# Y todos los que no pueden salir en ningún volcado: los anteriores y la lista de cuentas del piloto de push
FUERA_DE_LOS_VOLCADOS = (*MIGRADOS_A_SECRETSTR, "push_cuentas_permitidas")

pytestmark = pytest.mark.rf("RNF-08")


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
    assert config.database_url.get_secret_value() == valores["database_url"]
    assert config.kek_entorno is not None and config.kek_entorno.get_secret_value() == valores["kek_entorno"]
    assert config.push_cuentas_permitidas == frozenset({uuid.UUID(valores["push_cuentas_permitidas"])})
    for texto in (repr(config), str(config)):
        for campo, valor in valores.items():
            for trozo in _a_la_vista(valor):
                assert trozo not in texto, f"{campo} aparece en el repr o el str de la configuración"


@pytest.mark.parametrize("volcado", ["repr", "str", "model_dump", "model_dump_json"])
def test_los_campos_migrados_no_salen_en_ningun_volcado(monkeypatch: pytest.MonkeyPatch, volcado: str) -> None:
    """Con repr=False el repr y el str ya los ocultaban, pero model_dump los entregaba en claro: esta prueba falla
    con la versión del 18-11 en model_dump y model_dump_json."""
    valores = _valores_sinteticos()
    for campo in FUERA_DE_LOS_VOLCADOS:
        monkeypatch.setenv(campo.upper(), valores[campo])
    monkeypatch.setenv("PASARELA_PAGO", "integracion")
    config = Configuracion()

    volcados: dict[str, Callable[[Configuracion], str]] = {
        "repr": repr,
        "str": str,
        "model_dump": lambda c: str(c.model_dump()),
        "model_dump_json": lambda c: c.model_dump_json(),
    }
    texto = volcados[volcado](config)

    for campo in FUERA_DE_LOS_VOLCADOS:
        for trozo in _a_la_vista(valores[campo]):
            assert trozo not in texto, f"{campo} aparece en {volcado}"


def test_los_campos_migrados_son_secretstr() -> None:
    for campo in MIGRADOS_A_SECRETSTR:
        anotacion = Configuracion.model_fields[campo].annotation
        tipos = getattr(anotacion, "__args__", (anotacion,))
        assert SecretStr in tipos, f"{campo} no es SecretStr"


def test_la_lista_de_cuentas_de_push_no_se_vuelca(monkeypatch: pytest.MonkeyPatch) -> None:
    # exclude=True la saca de model_dump y model_dump_json; repr=False, del repr. app/core/push_piloto.py la lee igual
    campo = Configuracion.model_fields["push_cuentas_permitidas"]
    assert campo.exclude is True and campo.repr is False
    cuenta = uuid.uuid4()
    monkeypatch.setenv("PUSH_CUENTAS_PERMITIDAS", str(cuenta))
    config = Configuracion()
    assert config.push_cuentas_permitidas == frozenset({cuenta})
    assert "push_cuentas_permitidas" not in config.model_dump()
    assert "push_cuentas_permitidas" not in config.model_dump_json()


def test_los_usos_leen_el_valor_con_get_secret_value(monkeypatch: pytest.MonkeyPatch) -> None:
    # SecretStr no cambia el valor: el motor de la API, las tareas, Redis y la pasarela lo piden con .get_secret_value()
    valores = _valores_sinteticos()
    for campo in MIGRADOS_A_SECRETSTR:
        monkeypatch.setenv(campo.upper(), valores[campo])
    config = Configuracion()
    assert config.database_url.get_secret_value() == valores["database_url"]
    assert config.scheduler_database_url.get_secret_value() == valores["scheduler_database_url"]
    assert config.publisher_database_url.get_secret_value() == valores["publisher_database_url"]
    assert config.redis_url.get_secret_value() == valores["redis_url"]
    assert config.webpay_codigo_comercio is not None
    assert config.webpay_codigo_comercio.get_secret_value() == valores["webpay_codigo_comercio"]


def test_sin_variables_quedan_los_valores_por_omision(monkeypatch: pytest.MonkeyPatch) -> None:
    # El CI define DATABASE_URL, y la fixture _sin_env la deja a propósito: la prueba borra todas las que compara
    for campo in (*MIGRADOS_A_SECRETSTR, "webpay_llave", "pasarela_pago"):
        monkeypatch.delenv(campo.upper(), raising=False)
    config = Configuracion(_env_file=None)  # type: ignore[call-arg]
    assert config.database_url.get_secret_value() == ""
    assert config.scheduler_database_url.get_secret_value() == ""
    assert config.publisher_database_url.get_secret_value() == ""
    assert config.redis_url.get_secret_value() == "redis://127.0.0.1:6379/0"
    assert config.webpay_codigo_comercio is None


@pytest.mark.parametrize("valor", ["12345", "1234567890123", "12345a", " 123456"])
def test_un_codigo_de_comercio_mal_formado_no_carga_ni_se_repite(monkeypatch: pytest.MonkeyPatch, valor: str) -> None:
    # pydantic no aplica pattern a un SecretStr: el formato lo revisa un validador con un mensaje fijo
    monkeypatch.setenv("WEBPAY_CODIGO_COMERCIO", valor)
    with pytest.raises(ValidationError) as error:
        Configuracion()
    mensaje = str(error.value)
    assert "WEBPAY_CODIGO_COMERCIO" in mensaje and valor.strip() not in mensaje


def test_un_codigo_de_comercio_vacio_cuenta_como_ausente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBPAY_CODIGO_COMERCIO", "")
    assert Configuracion().webpay_codigo_comercio is None


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
