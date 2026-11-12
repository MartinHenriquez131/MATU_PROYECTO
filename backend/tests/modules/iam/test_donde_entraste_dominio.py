"""MATU-55 · Reglas puras de «Dónde entraste» y de la clave VAPID (RF-37, RF-39; decisiones 254 a 256 y 262).

Sin base de datos.
"""

import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Configuracion
from app.core.vapid import ClaveVapidInvalida, clave_publica, generar_clave_privada, validar_clave_privada
from app.modules.iam.domain.dispositivo import ClaseDispositivo, clase_dispositivo, nombre_dispositivo
from app.modules.iam.domain.ingresos import (
    ACCIONES_EXCLUIDAS,
    TIPO_POR_ACCION,
    TIPOS_SIN_DISPOSITIVO,
    TOPE_INGRESOS,
    FilaIngreso,
    TipoEventoCuenta,
    armar_ingresos,
    inicio_ventana,
)
from app.shared.auditoria import ACCIONES_DE_CUENTA

pytestmark = pytest.mark.rf("RF-37")

AHORA = datetime(2026, 11, 12, 13, 5, tzinfo=UTC)
TELEFONO = uuid.UUID("00000000-0000-0000-0000-0000000055d1")
OTRO = uuid.UUID("00000000-0000-0000-0000-0000000055d2")


def _fila(accion: str, *, minutos: int = 0, dispositivo: uuid.UUID | None = None,
          nombre: str | None = None) -> FilaIngreso:
    return FilaIngreso(accion=accion, ocurrido_en=AHORA - timedelta(minutes=minutos), dispositivo_id=dispositivo,
                       dispositivo_nombre=nombre)


# --- La lista cerrada (decisión 254) -------------------------------------------------------------------------------


def test_la_lista_cerrada_son_las_acciones_de_la_cuenta_menos_las_excluidas() -> None:
    assert set(TIPO_POR_ACCION) | ACCIONES_EXCLUIDAS == ACCIONES_DE_CUENTA
    assert not set(TIPO_POR_ACCION) & ACCIONES_EXCLUIDAS
    assert {t.value for t in TIPO_POR_ACCION.values()} == {t.value for t in TipoEventoCuenta}
    # Ningún tipo de la API es el nombre de una acción de auditoría
    assert not {t.value for t in TipoEventoCuenta} & {a.value for a in ACCIONES_DE_CUENTA}


def test_los_fallidos_y_el_pedido_del_codigo_del_celular_no_entran() -> None:
    filas = [_fila(a) for a in ("sesion.inicio_fallido", "cuenta.recuperar_verificar_fallido",
                                "cuenta.celular_verificar_fallido", "cuenta.celular_solicitar", "plan.leer",
                                "no.existe")]
    assert armar_ingresos(filas, dispositivo_actual=None).eventos == ()


# --- La forma de cada evento (decisión 256) ------------------------------------------------------------------------


def test_el_dispositivo_actual_y_los_eventos_de_la_cuenta_sin_dispositivo() -> None:
    filas = [
        _fila("sesion.iniciar", dispositivo=TELEFONO, nombre="Chrome en Android"),
        _fila("dispositivo.sacar", minutos=1, dispositivo=OTRO, nombre="Safari en iPhone"),
        _fila("cuenta.contrasena_cambiar", minutos=2, dispositivo=TELEFONO, nombre="Chrome en Android"),
        _fila("sesion.cerrar", minutos=3),  # el dispositivo ya no existe
    ]
    eventos = armar_ingresos(filas, dispositivo_actual=TELEFONO).eventos
    assert [e.tipo for e in eventos] == [TipoEventoCuenta.ENTRASTE, TipoEventoCuenta.CERRASTE_EN_DISPOSITIVO,
                                         TipoEventoCuenta.CONTRASENA_CAMBIADA, TipoEventoCuenta.SALISTE]
    assert eventos[0].dispositivo is not None and eventos[0].dispositivo.actual is True
    assert eventos[0].dispositivo.clase is ClaseDispositivo.TELEFONO
    assert eventos[1].dispositivo is not None and eventos[1].dispositivo.actual is False
    assert eventos[1].dispositivo.nombre == "Safari en iPhone"
    # Un evento de la cuenta nunca lleva dispositivo, aunque la fila lo traiga
    assert eventos[2].dispositivo is None and eventos[2].tipo in TIPOS_SIN_DISPOSITIVO
    assert eventos[3].dispositivo is None


def test_sin_did_nada_es_el_actual() -> None:
    [evento] = armar_ingresos([_fila("sesion.iniciar", dispositivo=TELEFONO, nombre="Chrome en Android")],
                              dispositivo_actual=None).eventos
    assert evento.dispositivo is not None and evento.dispositivo.actual is False


def test_el_instante_sale_en_utc() -> None:
    santiago = timezone(timedelta(hours=-3))
    fila = FilaIngreso(accion="sesion.iniciar", ocurrido_en=datetime(2026, 11, 12, 10, 5, tzinfo=santiago),
                       dispositivo_id=None, dispositivo_nombre=None)
    [evento] = armar_ingresos([fila], dispositivo_actual=None).eventos
    assert evento.ocurrido_en == AHORA and evento.ocurrido_en.tzinfo == UTC


def test_el_repr_no_lleva_los_nombres_de_los_dispositivos() -> None:
    resultado = armar_ingresos([_fila("sesion.iniciar", dispositivo=TELEFONO, nombre="Chrome en Android")],
                               dispositivo_actual=TELEFONO)
    assert "Chrome" not in repr(resultado) and "Chrome" not in repr(resultado.eventos)
    assert "Chrome" not in repr(_fila("sesion.iniciar", nombre="Chrome en Android"))


# --- Ventana y tope (decisión 255) ---------------------------------------------------------------------------------


def test_la_ventana_es_de_90_dias() -> None:
    assert inicio_ventana(AHORA) == AHORA - timedelta(days=90)
    with pytest.raises(ValueError):
        inicio_ventana(AHORA.replace(tzinfo=None))


@pytest.mark.parametrize(("cantidad", "hay_mas"), [(0, False), (20, False), (21, True)])
def test_el_tope_es_20_y_hay_mas_no_dice_cuantos(cantidad: int, hay_mas: bool) -> None:
    filas = [_fila("avisos.preferencia", minutos=i) for i in range(cantidad)]
    resultado = armar_ingresos(filas, dispositivo_actual=None)
    assert len(resultado.eventos) == min(cantidad, TOPE_INGRESOS) and resultado.hay_mas is hay_mas
    # Conserva el orden de las filas: del más reciente al más antiguo
    assert list(resultado.eventos) == sorted(resultado.eventos, key=lambda e: e.ocurrido_en, reverse=True)


# --- La clase del dispositivo (C7) ---------------------------------------------------------------------------------


@pytest.mark.parametrize(("nombre", "clase"), [
    ("Chrome en Android", ClaseDispositivo.TELEFONO),
    ("Safari en iPhone", ClaseDispositivo.TELEFONO),
    ("Firefox en Windows", ClaseDispositivo.COMPUTADOR),
    ("Safari en Mac", ClaseDispositivo.COMPUTADOR),
    ("Firefox en Linux", ClaseDispositivo.COMPUTADOR),
    ("Chrome en ChromeOS", ClaseDispositivo.COMPUTADOR),
    ("Safari en iPad", ClaseDispositivo.OTRO),
    ("Navegador web", ClaseDispositivo.OTRO),
    ("", ClaseDispositivo.OTRO),
])
def test_clase_desde_el_nombre(nombre: str, clase: ClaseDispositivo) -> None:
    assert clase_dispositivo(nombre) is clase


def test_clase_desde_el_agente_de_usuario() -> None:
    android = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/130.0 Mobile Safari/537.36"
    windows = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0"
    assert clase_dispositivo(nombre_dispositivo(android)) is ClaseDispositivo.TELEFONO
    assert clase_dispositivo(nombre_dispositivo(windows)) is ClaseDispositivo.COMPUTADOR
    assert clase_dispositivo(nombre_dispositivo(None)) is ClaseDispositivo.OTRO


# --- La clave VAPID (decisión 262) ---------------------------------------------------------------------------------


@pytest.mark.rf("RF-39")
def test_la_publica_se_deriva_de_la_privada() -> None:
    privada = generar_clave_privada()
    assert len(privada) == 43 and "=" not in privada
    publica = clave_publica(privada)
    assert len(publica) == 87 and publica.startswith("B")
    assert clave_publica(privada) == publica and clave_publica(generar_clave_privada()) != publica


@pytest.mark.rf("RF-39")
@pytest.mark.parametrize("valor", ["", "corta", "A" * 43 + "=", "A" * 43, "_" * 43, "!" * 43, "A" * 44, " " + "B" * 42])
def test_una_privada_invalida_se_rechaza_sin_repetirla(valor: str) -> None:
    with pytest.raises(ClaveVapidInvalida) as error:
        validar_clave_privada(valor)
    assert valor.strip() == "" or valor not in str(error.value)


@pytest.mark.rf("RF-39")
def test_la_configuracion_no_carga_con_una_privada_invalida_y_no_la_muestra() -> None:
    privada = generar_clave_privada()
    config = _configuracion(vapid_clave_privada=privada)
    assert privada not in repr(config) and privada not in str(config.model_dump())
    assert _configuracion(vapid_clave_privada="").vapid_clave_privada is None
    malo = "z" * 42 + "!"
    with pytest.raises(ValidationError) as error:
        _configuracion(vapid_clave_privada=malo)
    assert malo not in str(error.value)


def _configuracion(**valores: Any) -> Configuracion:
    return Configuracion(_env_file=None, entorno="pruebas", **valores)  # type: ignore[call-arg]


@pytest.mark.rf("RF-39")
def test_el_script_imprime_una_clave_valida_sin_escribir_archivos(tmp_path: Path) -> None:
    """Q7 (decisión 277): la clave solo sale por la salida estándar, en el formato de VAPID_CLAVE_PRIVADA."""
    script = Path(__file__).resolve().parents[3] / "scripts" / "generar_vapid.py"
    r = subprocess.run([sys.executable, str(script)], cwd=tmp_path, capture_output=True, text=True, check=True)
    [privada] = [linea.split("=", 1)[1] for linea in r.stdout.splitlines() if linea.startswith("VAPID_CLAVE_PRIVADA=")]
    validar_clave_privada(privada)
    assert clave_publica(privada) in r.stdout
    assert r.stderr == "" and list(tmp_path.iterdir()) == []
