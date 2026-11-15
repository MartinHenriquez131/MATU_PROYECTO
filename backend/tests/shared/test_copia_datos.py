"""MATU-54 · Reglas de la copia de los datos, sin base (Ley 21.719, acceso y portabilidad; decisiones 343, 349 a 359).

El formato, el aviso fijo, los instantes con el desfase de Chile, el nombre del archivo sin nombres de nadie, el estado
de cada bloque según la autorización, los hechos del historial y el resultado de los avisos simulados.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.care_circle.domain.retiro import EstadoDeAutorizacion, EstadoVista
from app.modules.care_circle.infrastructure.copia_datos import (
    TIPO_HECHO,
    alcance_del_historial,
    estado_bloque,
    estado_de_fila,
    hecho,
    persona_nombrada,
)
from app.modules.iam.domain.ingresos import TIPO_POR_ACCION, TIPOS_SIN_DISPOSITIVO, TipoEventoCuenta
from app.modules.notifications.infrastructure.copia_avisos import resultado
from app.shared.auditoria import ACCIONES_DE_PERSONA, AccionAuditoria
from app.shared.copia_datos import (
    ARCHIVO_CUENTA,
    ARCHIVO_PERSONA,
    AVISO_COPIA,
    FORMATO,
    LIMITE_COPIAS,
    content_disposition,
    en_chile,
    nombre_archivo,
)

pytestmark = [pytest.mark.rf("RF-08"), pytest.mark.rf("Ley-21.719")]

# 02:30 UTC del 12-11 es el 11-11 a las 23:30 en Chile (verano, -03:00)
MADRUGADA_UTC = datetime(2026, 11, 12, 2, 30, tzinfo=UTC)


def test_formato_y_aviso_fijo() -> None:
    assert FORMATO == "matu-datos/1"
    # P14 del diseñador: dice dónde queda el archivo sin suponer un teléfono
    assert AVISO_COPIA.startswith("Esta es una copia de los datos que MATU guarda")
    assert "No es la ficha para un relevo" in AVISO_COPIA
    assert "en tu teléfono" not in AVISO_COPIA and "queda donde lo descargaste" in AVISO_COPIA


def test_los_instantes_van_con_el_desfase_de_chile() -> None:
    assert en_chile(MADRUGADA_UTC) == "2026-11-11T23:30:00-03:00"
    # En invierno, -04:00
    assert en_chile(datetime(2026, 7, 1, 12, 0, 0, 999, tzinfo=UTC)) == "2026-07-01T08:00:00-04:00"
    with pytest.raises(ValueError):
        en_chile(datetime(2026, 11, 12, 2, 30))


def test_el_nombre_del_archivo_es_generico_y_con_el_dia_de_chile() -> None:
    assert nombre_archivo(ARCHIVO_PERSONA, MADRUGADA_UTC) == "matu-datos-2026-11-11.json"
    assert nombre_archivo(ARCHIVO_CUENTA, MADRUGADA_UTC) == "matu-cuenta-2026-11-11.json"
    assert content_disposition(ARCHIVO_PERSONA, MADRUGADA_UTC) == 'inline; filename="matu-datos-2026-11-11.json"'
    with pytest.raises(ValueError):
        nombre_archivo("Elena", MADRUGADA_UTC)


def test_el_limite_es_de_diez_copias_por_hora() -> None:
    assert (LIMITE_COPIAS.prefijo, LIMITE_COPIAS.maximo, LIMITE_COPIAS.ventana_segundos) == ("copia-datos", 10, 3600)


@pytest.mark.parametrize(
    ("estado", "esperado"),
    [
        (EstadoVista.VIGENTE, ("disponible", None)),
        (EstadoVista.REVISION_VENCIDA, ("en_pausa", None)),
        (EstadoVista.BORRADA, ("borrada", None)),
        (EstadoVista.SIN_AUTORIZAR, ("sin_autorizar", None)),
    ],
)
def test_estado_de_un_bloque(estado: EstadoVista, esperado: tuple[str, None]) -> None:
    assert estado_bloque(EstadoDeAutorizacion("plan_cuidado", estado, None, None, False)) == esperado


def test_retirada_dice_el_dia_en_que_se_borra() -> None:
    retirada = EstadoDeAutorizacion(
        "plan_cuidado", EstadoVista.RETIRADA, None, MADRUGADA_UTC + timedelta(days=90), False
    )
    assert estado_bloque(retirada) == ("retirada", "2027-02-09")


def test_estado_de_cada_autorizacion() -> None:
    ahora = MADRUGADA_UTC
    assert estado_de_fila(None, None, "titular", None, ahora) == "vigente"
    assert estado_de_fila(None, None, "cuidador_de_hecho", ahora, ahora) == "revision_vencida"
    assert estado_de_fila(ahora, "retiro", "titular", None, ahora) == "retirada"
    assert estado_de_fila(ahora, "renovacion", "titular", None, ahora) == "reemplazada"


def test_una_persona_que_ya_no_esta_va_sin_nombre() -> None:
    assert persona_nombrada("Carmen Soto", True) == {"nombre": "Carmen Soto", "activo": True}
    assert persona_nombrada("Carmen Soto", False) == {"nombre": None, "activo": False}


def test_el_historial_es_una_lista_cerrada_sin_lo_del_relevo_ni_el_borrado() -> None:
    assert set(TIPO_HECHO) <= ACCIONES_DE_PERSONA
    fuera = ACCIONES_DE_PERSONA - set(TIPO_HECHO)
    assert fuera == {
        AccionAuditoria.RELEVO_PRESENTAR, AccionAuditoria.RELEVO_CANJE, AccionAuditoria.RELEVO_PIN_INCORRECTO,
        AccionAuditoria.RELEVO_BLOQUEO, AccionAuditoria.RELEVO_ABRIR, AccionAuditoria.PERSONA_BORRAR,
    }
    assert len(set(TIPO_HECHO.values())) == len(TIPO_HECHO) == 33
    assert alcance_del_historial("admin") == "todo" and alcance_del_historial("cuidador") == "lo_tuyo"


def test_un_hecho_dice_a_que_se_refiere_sin_el_contenido() -> None:
    editado = hecho("plan.editar", MADRUGADA_UTC, "usuario", "Carmen", True, None, "rutina", None, None)
    assert editado == {
        "tipo": "edito_la_ficha", "ocurrido_en": "2026-11-11T23:30:00-03:00",
        "quien": {"tipo": "persona", "nombre": "Carmen", "activo": True},
        "campo": "rutina", "seccion": None, "finalidad": None, "referencia": None,
    }
    complementaria = hecho("plan.editar", MADRUGADA_UTC, "usuario", "Carmen", True, "remedios", "remedios", None, None)
    assert (complementaria or {})["campo"] is None and (complementaria or {})["seccion"] == "remedios"
    # F1: la finalidad de la autorización y la referencia del pedido, nada más
    retiro = hecho("consentimiento.revocar", MADRUGADA_UTC, "usuario", None, False, None, None, "consumo", None)
    assert retiro is not None and retiro["finalidad"] == "consumo" and retiro["quien"]["nombre"] is None
    pago = hecho("pago.aprobar", MADRUGADA_UTC, "sistema", None, False, None, None, None, "4821")
    assert pago is not None and pago["referencia"] == "4821" and pago["quien"] == {
        "tipo": "matu", "nombre": None, "activo": None}
    assert hecho("relevo.abrir", MADRUGADA_UTC, "relevo", None, False, None, None, None, None) is None
    assert hecho("sesion.iniciar", MADRUGADA_UTC, "usuario", "Carmen", True, None, None, None, None) is None


def test_un_aviso_simulado_no_sale_como_enviado() -> None:
    assert resultado("enviada", True) == "en_el_piloto_no_salio"
    assert resultado("enviada", False) == "salio"
    assert resultado("fallida", True) == resultado("omitida", True) == "no_salio"
    assert resultado("pendiente", True) == "pendiente"


@pytest.mark.rf("RF-37")
def test_donde_entraste_suma_solo_la_copia_de_la_cuenta() -> None:
    """C-2 y C-3 (decisión 376): «Pediste una copia de tus datos»; la copia de una persona no entra."""
    assert TIPO_POR_ACCION[AccionAuditoria.CUENTA_DATOS_DESCARGAR] is TipoEventoCuenta.PEDISTE_UNA_COPIA
    assert AccionAuditoria.PERSONA_DATOS_DESCARGAR not in TIPO_POR_ACCION
    assert TipoEventoCuenta.PEDISTE_UNA_COPIA in TIPOS_SIN_DISPOSITIVO


def test_un_id_sintetico_no_es_un_nombre_de_archivo() -> None:
    # Ningún nombre de archivo lleva un id o un nombre: solo el prefijo y el día
    nombre = nombre_archivo(ARCHIVO_PERSONA, MADRUGADA_UTC)
    assert str(uuid.UUID(int=1)) not in nombre and nombre.count("-") == 4
