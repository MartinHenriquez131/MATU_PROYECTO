"""MATU-41 · Reglas puras de los avisos: destinatarios, revisión antes de enviar, desenlace, hora y textos.

Sin base (RF-39). La hora de envío se prueba con instantes fijos, nunca con el reloj del sistema.
"""

from datetime import UTC, datetime

import pytest

from app.modules.notifications.domain.aviso import (
    CANALES,
    Canal,
    CodigoAviso,
    EstadoNotificacion,
    ResultadoEnvio,
    Revision,
    canal_activo,
    canales_activos,
    canales_por_guardar,
    desenlace,
    es_destinatario,
    motivo_omision,
    por_intentar,
)
from app.modules.notifications.domain.horario import disponible_desde
from app.modules.notifications.domain.mensaje import (
    ASUNTO,
    CUERPO,
    PIE,
    correo_quiebre,
    enlace_app,
)

pytestmark = pytest.mark.rf("RF-39")

ORIGEN = "https://matu.example"


# --- Destinatarios y canales -----------------------------------------------------------------------------


def test_el_correo_es_el_primer_canal() -> None:
    assert CANALES == (Canal.CORREO, Canal.PUSH)


@pytest.mark.parametrize(
    ("por_defecto", "preferencia", "activo"),
    [(True, None, True), (False, None, False), (True, False, False), (False, True, True)],
)
def test_la_preferencia_manda_y_sin_ella_el_rol(por_defecto: bool, preferencia: bool | None, activo: bool) -> None:
    assert canal_activo(por_defecto=por_defecto, preferencia=preferencia) is activo


def test_pagador_sin_preferencia_no_es_destinatario_y_con_un_canal_si() -> None:
    assert not es_destinatario(por_defecto=False, preferencias={})
    assert es_destinatario(por_defecto=False, preferencias={Canal.PUSH: True})


def test_admin_con_los_dos_canales_apagados_no_es_destinatario() -> None:
    assert es_destinatario(por_defecto=True, preferencias={Canal.CORREO: False})
    assert not es_destinatario(por_defecto=True, preferencias={Canal.CORREO: False, Canal.PUSH: False})


# --- Revisión antes de cada envío ---------------------------------------------------------------------------

TODO_BIEN = {"autorizado": True, "alerta_abierta": True, "miembro_activo": True, "canal_activo": True,
             "con_destino": True}


@pytest.mark.parametrize(
    ("falla", "codigo"),
    [
        ({"autorizado": False, "alerta_abierta": False, "miembro_activo": False}, CodigoAviso.SIN_AUTORIZACION),
        ({"alerta_abierta": False, "miembro_activo": False}, CodigoAviso.ALERTA_CERRADA),
        ({"miembro_activo": False, "canal_activo": False}, CodigoAviso.MIEMBRO_INACTIVO),
        ({"canal_activo": False}, CodigoAviso.SIN_DESTINO),
        ({"con_destino": False}, CodigoAviso.SIN_DESTINO),
        ({}, None),
    ],
)
def test_motivo_de_omision_en_orden(falla: dict[str, bool], codigo: CodigoAviso | None) -> None:
    assert motivo_omision(Revision(**{**TODO_BIEN, **falla})) is codigo


# --- Desenlace del envío -----------------------------------------------------------------------------------

E, R, N, X = ResultadoEnvio.ENVIADO, ResultadoEnvio.RECHAZADO, ResultadoEnvio.NO_DISPONIBLE, ResultadoEnvio.EXPIRADO


@pytest.mark.parametrize(
    ("resultados", "estado", "codigo", "reintentar"),
    [
        ([E], EstadoNotificacion.ENVIADA, None, False),
        ([X, E], EstadoNotificacion.ENVIADA, None, False),  # un dispositivo vencido y otro que llegó
        ([N, E], EstadoNotificacion.ENVIADA, None, False),  # ya llegó: reintentar duplicaría
        ([N], EstadoNotificacion.FALLIDA, CodigoAviso.PROVEEDOR_NO_DISPONIBLE, True),
        ([R, N], EstadoNotificacion.FALLIDA, CodigoAviso.PROVEEDOR_NO_DISPONIBLE, True),
        ([R], EstadoNotificacion.FALLIDA, CodigoAviso.PROVEEDOR_RECHAZO, False),
        ([X, R], EstadoNotificacion.FALLIDA, CodigoAviso.PROVEEDOR_RECHAZO, False),
        ([X, X], EstadoNotificacion.FALLIDA, CodigoAviso.PUSH_EXPIRADO, False),
        ([], EstadoNotificacion.OMITIDA, CodigoAviso.SIN_DESTINO, False),
    ],
)
def test_desenlace(
    resultados: list[ResultadoEnvio], estado: EstadoNotificacion, codigo: CodigoAviso | None, reintentar: bool
) -> None:
    d = desenlace(resultados)
    assert (d.estado, d.codigo, d.reintentar) == (estado, codigo, reintentar)


@pytest.mark.parametrize(
    ("estado", "codigo", "esperado"),
    [
        (EstadoNotificacion.PENDIENTE, None, True),
        (EstadoNotificacion.FALLIDA, CodigoAviso.PROVEEDOR_NO_DISPONIBLE, True),
        (EstadoNotificacion.ENVIADA, None, False),  # un reintento nunca reenvía
        (EstadoNotificacion.FALLIDA, CodigoAviso.PUSH_EXPIRADO, False),
        (EstadoNotificacion.FALLIDA, CodigoAviso.PROVEEDOR_RECHAZO, False),
        (EstadoNotificacion.OMITIDA, CodigoAviso.SIN_AUTORIZACION, False),
    ],
)
def test_que_filas_se_intentan(estado: EstadoNotificacion, codigo: CodigoAviso | None, esperado: bool) -> None:
    assert por_intentar(estado, codigo) is esperado


def test_los_codigos_son_los_de_la_lista_cerrada() -> None:
    assert {c.value for c in CodigoAviso} == {
        "sin_autorizacion", "alerta_cerrada", "miembro_inactivo", "sin_destino", "push_expirado",
        "proveedor_rechazo", "proveedor_no_disponible",
    }


# --- Hora de envío (decisión 109) ---------------------------------------------------------------------------


def test_el_trabajo_de_las_0400_queda_disponible_a_las_0900_del_mismo_dia() -> None:
    # 20-10-2026: Chile en horario de verano (UTC-3). 04:00 en Santiago = 07:00 UTC
    cuatro = datetime(2026, 10, 20, 7, 0, tzinfo=UTC)
    assert disponible_desde(cuatro) == datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def test_en_invierno_las_0900_son_las_1300_utc() -> None:
    # 20-06-2026: UTC-4
    assert disponible_desde(datetime(2026, 6, 20, 8, 0, tzinfo=UTC)) == datetime(2026, 6, 20, 13, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "instante",
    [
        datetime(2026, 10, 20, 12, 0, tzinfo=UTC),  # 09:00 en punto
        datetime(2026, 10, 20, 18, 30, tzinfo=UTC),
        datetime(2026, 10, 21, 2, 59, tzinfo=UTC),  # 23:59 del 20 en Santiago
    ],
)
def test_desde_las_0900_se_envia_al_momento(instante: datetime) -> None:
    assert disponible_desde(instante) is None


def test_un_minuto_antes_de_las_0900_espera() -> None:
    assert disponible_desde(datetime(2026, 10, 20, 11, 59, tzinfo=UTC)) == datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def test_pasada_la_medianoche_espera_las_0900_de_ese_dia() -> None:
    # 00:30 del 21 en Santiago (03:30 UTC del 21)
    assert disponible_desde(datetime(2026, 10, 21, 3, 30, tzinfo=UTC)) == datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def test_sin_zona_horaria_falla() -> None:
    with pytest.raises(ValueError):
        disponible_desde(datetime(2026, 10, 20, 7, 0))


# --- Textos (decisión 113, lenguaje.md sección 20) ------------------------------------------------------------


def test_textos_del_correo_aprobados() -> None:
    correo = correo_quiebre(ORIGEN)
    assert correo.remitente == "MATU"
    assert correo.asunto == ASUNTO == "MATU: un insumo se está acabando"
    assert correo.cuerpo == CUERPO == "Un insumo se está acabando. Abre la app para ver cuál."
    assert correo.texto_enlace == "Abrir MATU"
    assert correo.pie == PIE == (
        "Te llega este correo porque eres parte de un grupo de cuidado en MATU. Para dejar de recibir estos"
        " avisos por correo, entra a MATU y desactívalos en Tu cuenta."
    )


def test_el_enlace_es_la_raiz_de_la_app_sin_identificadores() -> None:
    assert correo_quiebre(ORIGEN).enlace == "https://matu.example/"
    for malo in ("http://matu.example", "https://matu.example/r", "https://matu.example?x=1", "https://a#b"):
        with pytest.raises(ValueError):
            enlace_app(malo)


def test_el_push_no_lleva_contenido() -> None:
    # Decisión 50: el push va sin contenido y el envío no tiene campo para un texto
    from dataclasses import fields

    from app.modules.notifications.application.ports import EnvioPush

    assert {f.name for f in fields(EnvioPush)} == {"notificacion_id", "usuario_id", "plantilla", "push_token"}


def test_el_correo_no_lleva_imagenes_ni_seguimiento() -> None:
    html = correo_quiebre(ORIGEN).html()
    assert "<img" not in html and "src=" not in html and "<link" not in html and "style" not in html
    assert html.count("href=") == 1 and 'href="https://matu.example/"' in html
    assert "Abrir MATU" in correo_quiebre(ORIGEN).texto_plano()


def test_el_repr_de_los_mensajes_no_muestra_el_texto() -> None:
    assert "insumo" not in repr(correo_quiebre(ORIGEN)) and "matu.example" not in repr(correo_quiebre(ORIGEN))


# --- Lo que guarda el PUT /v1/yo/avisos (decisión 111) --------------------------------------------------------

C, P = Canal.CORREO, Canal.PUSH


@pytest.mark.parametrize(
    ("pedidos", "guardadas", "por_defecto", "esperado"),
    [
        # Admin en A y observador en B, sin filas: apaga solo el push; el correo queda sin elegir
        ({C: True, P: False}, {}, True, {P: False}),
        # Observador sin filas que activa el correo
        ({C: True, P: False}, {}, False, {C: True}),
        # Sin cambios respecto del GET: no se guarda nada
        ({C: True, P: True}, {}, True, {}),
        ({C: False, P: False}, {}, False, {}),
        # Un canal que ya tenía fila se actualiza aunque coincida con el rol
        ({C: True, P: True}, {C: False}, True, {C: True}),
    ],
)
def test_el_put_guarda_solo_el_canal_que_cambia(
    pedidos: dict[Canal, bool], guardadas: dict[Canal, bool], por_defecto: bool, esperado: dict[Canal, bool]
) -> None:
    assert canales_por_guardar(pedidos=pedidos, guardadas=guardadas, por_defecto=por_defecto) == esperado


def test_canales_activos_correo_primero_y_sin_los_apagados() -> None:
    assert canales_activos(por_defecto=True, preferencias={}) == (C, P)
    assert canales_activos(por_defecto=True, preferencias={C: False}) == (P,)
    assert canales_activos(por_defecto=False, preferencias={P: True}) == (P,)
    assert canales_activos(por_defecto=False, preferencias={}) == ()
