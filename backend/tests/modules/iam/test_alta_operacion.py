"""MATU-81 · El alta de una cuenta de operación por consola (C28 y C33), con matu_scheduler y app.rol = 'operacion'.

La URI otpauth sale una vez por la consola y nunca por el log; el alta pide el primer código antes de guardar; el
secreto queda cifrado con la KEK y el AAD de la cuenta; una cuenta que es de una familia o de un comercio no se da de
alta; repetir el alta cierra las sesiones abiertas. La KEK y el pepper son de la prueba."""

import base64
import io
import re
import secrets
import uuid
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from pydantic import SecretStr

from app import tareas
from app.core.config import obtener_configuracion
from app.modules.iam.domain.mfa import hotp, paso_de
from app.modules.iam.infrastructure.cifrador_mfa import cifrador_de
from tests.base_datos import DSN, fabrica_scheduler, requiere_base
from tests.dobles.reloj_fijo import RelojFijo
from tests.fabricas import Fabrica

pytestmark = [pytest.mark.rf("RF-37"), pytest.mark.rf("Ley-21.719"), requiere_base]


@pytest.fixture
def fabrica() -> Iterator[Fabrica]:
    """Con un pepper en texto, como el PEPPER_EMAIL del entorno."""
    sembradora = Fabrica(pepper=secrets.token_hex(32).encode())
    yield sembradora
    sembradora.limpiar()


@pytest.fixture
def config(fabrica: Fabrica) -> Any:
    return obtener_configuracion().model_copy(update={
        "pepper_email": SecretStr(fabrica.pepper.decode()),
        "custodia_kek": "entorno_sintetico",
        "kek_entorno": SecretStr(base64.b64encode(secrets.token_bytes(32)).decode()),
        "entorno": "pruebas",
    })


@pytest.fixture
def con_scheduler(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(tareas, "fabrica_de_rol", lambda url, rol: fabrica_scheduler())
    yield


def _respuestas(*valores: str) -> Any:
    pendientes = list(valores)
    return lambda _pregunta: pendientes.pop(0)


def _sql(sentencia: str, *parametros: Any) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sentencia, parametros).fetchall()


def test_el_alta_muestra_la_uri_una_vez_pide_el_codigo_y_guarda_el_secreto_cifrado(
    fabrica: Fabrica, config: Any, reloj_fijo: RelojFijo, con_scheduler: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    cuenta = fabrica.usuario()
    capturado: dict[str, bytes] = {}
    from app.modules.iam.infrastructure import tarea_alta_operacion

    original = tarea_alta_operacion.secrets.token_bytes

    def espiar(n: int) -> bytes:
        valor = original(n)
        if n == 20:  # el secreto; el nonce del cifrado son 12
            capturado["secreto"] = valor
        return valor

    monkeypatch.setattr(tarea_alta_operacion.secrets, "token_bytes", espiar)
    logs, consola = io.StringIO(), io.StringIO()
    preguntas = iter([cuenta.email.upper()])

    def preguntar(texto: str) -> str:
        if "Correo" in texto:
            return next(preguntas)
        return hotp(capturado["secreto"], paso_de(reloj_fijo.ahora()))

    assert tareas.operacion_alta(stream=logs, consola=consola, preguntar=preguntar, reloj=reloj_fijo,
                                 config=config) == 0
    [uri] = re.findall(r"otpauth://\S+", consola.getvalue())
    assert "otpauth" not in logs.getvalue() and cuenta.email not in logs.getvalue()
    assert str(cuenta.id) not in logs.getvalue() and '"resultado": "ok"' in logs.getvalue()
    [(es, cifrado)] = _sql("SELECT es_operacion, mfa_secreto_cifrado FROM usuario WHERE id = %s", cuenta.id)
    assert es is True and capturado["secreto"] not in bytes(cifrado)
    cifrador = cifrador_de(config)
    assert cifrador is not None and cifrador.descifrar(bytes(cifrado), cuenta.id) == capturado["secreto"]
    assert uri.count("secret=") == 1
    assert _sql("SELECT actor_tipo, grupo_id FROM auditoria WHERE accion = 'cuenta.mfa_alta' AND entidad_id = %s",
                cuenta.id) == [("sistema", None)]


def test_sin_el_primer_codigo_no_se_guarda_nada(
    fabrica: Fabrica, config: Any, reloj_fijo: RelojFijo, con_scheduler: None
) -> None:
    cuenta = fabrica.usuario()
    consola = io.StringIO()
    assert tareas.operacion_alta(stream=io.StringIO(), consola=consola,
                                 preguntar=_respuestas(cuenta.email, "000000", "000001", "000002"),
                                 reloj=reloj_fijo, config=config) == 1
    assert _sql("SELECT es_operacion, mfa_secreto_cifrado FROM usuario WHERE id = %s", cuenta.id) == [(False, None)]
    assert "No se guardó nada" in consola.getvalue()


def test_c33_una_cuenta_de_familia_no_se_da_de_alta_y_una_que_no_existe_tampoco(
    fabrica: Fabrica, config: Any, reloj_fijo: RelojFijo, con_scheduler: None
) -> None:
    familia = fabrica.familia()
    logs, consola = io.StringIO(), io.StringIO()
    assert tareas.operacion_alta(stream=logs, consola=consola, preguntar=_respuestas(familia.admin.email),
                                 reloj=reloj_fijo, config=config) == 1
    assert "miembro de una familia" in consola.getvalue() and '"tipo_error": "AltaRechazada"' in logs.getvalue()
    assert tareas.operacion_alta(stream=logs, consola=consola,
                                 preguntar=_respuestas(f"nadie.{uuid.uuid4().hex}@ejemplo.cl"), reloj=reloj_fijo,
                                 config=config) == 1
    assert "No hay una cuenta con ese correo" in consola.getvalue()
    assert familia.admin.email not in logs.getvalue()
    # Sin la KEK, falla nombrando la variable y sin preguntar
    sin_kek = config.model_copy(update={"custodia_kek": None, "kek_entorno": None})
    assert tareas.operacion_alta(stream=logs, consola=io.StringIO(), preguntar=_respuestas(), reloj=reloj_fijo,
                                 config=sin_kek) == 1
    assert '"falta": "KEK_ENTORNO"' in logs.getvalue()


def test_c33_la_base_separa_las_cuentas_de_operacion_de_las_familias_y_los_comercios(fabrica: Fabrica) -> None:
    familia = fabrica.familia()
    with psycopg.connect(DSN) as cx:
        with pytest.raises(psycopg.errors.CheckViolation), cx.transaction():
            cx.execute("UPDATE usuario SET es_operacion = true, mfa_secreto_cifrado = '\\x01' WHERE id = %s",
                       (familia.admin.id,))
        operador = fabrica.usuario()
        cx.execute("UPDATE usuario SET es_operacion = true, mfa_secreto_cifrado = '\\x01' WHERE id = %s",
                   (operador.id,))
        with pytest.raises(psycopg.errors.CheckViolation), cx.transaction():
            cx.execute("INSERT INTO membresia (grupo_id, usuario_id, rol) VALUES (%s, %s, 'cuidador')",
                       (familia.grupo.id, operador.id))
        cx.rollback()


def test_matu_app_no_da_de_alta_ni_lee_el_secreto_de_otra_cuenta() -> None:
    """C27 y C28: operacion_alta y operacion_buscar_cuenta son solo de matu_scheduler; iam_mfa_secreto entrega solo
    lo de la cuenta del contexto."""
    with psycopg.connect(DSN) as cx:
        cx.execute("SET ROLE matu_app")
        for llamada in ("SELECT operacion_alta(gen_random_uuid(), '\\x00')",
                        "SELECT * FROM operacion_buscar_cuenta('\\x00')"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), cx.transaction():
                cx.execute(llamada)
        cx.execute("SELECT set_config('app.usuario_id', %s, false)", (str(uuid.uuid4()),))
        assert cx.execute("SELECT iam_mfa_secreto(gen_random_uuid())").fetchone() == (None,)
        cx.rollback()


def test_main_lleva_operacion_alta_a_su_tarea_y_sin_scheduler_falla_nombrando_la_variable(
    monkeypatch: pytest.MonkeyPatch, config: Any
) -> None:
    llamadas: list[object] = []

    def doble(**argumentos: object) -> int:
        llamadas.append(argumentos)
        return 0

    monkeypatch.setattr(tareas, "operacion_alta", doble)
    assert tareas.main(["operacion-alta"]) == 0 and len(llamadas) == 1
    monkeypatch.undo()
    monkeypatch.setattr(tareas, "fabrica_de_rol", lambda url, rol: None)
    logs = io.StringIO()
    assert tareas.operacion_alta(stream=logs, consola=io.StringIO(), preguntar=_respuestas(), config=config) == 1
    assert '"falta": "SCHEDULER_DATABASE_URL"' in logs.getvalue()
