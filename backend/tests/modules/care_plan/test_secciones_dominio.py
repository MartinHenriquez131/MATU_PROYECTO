"""MATU-50 · Reglas puras de las secciones complementarias de la ficha (ADR-028, RF-03). Sin base.

Contrato: docs/api/propuestos/ficha-ampliada.openapi.yaml. Solo datos sintéticos.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import get_args

import pytest

from app.modules.care_plan.api.esquemas_relevo import SolicitudAccesoVista
from app.modules.care_plan.domain.aperturas import TipoApertura, secciones_de_apertura
from app.modules.care_plan.domain.cifrado import TIPOS_SECCION, datos_asociados
from app.modules.care_plan.domain.ficha import FaltaPrecondicion, PrecondicionInvalida, SiCoincide
from app.modules.care_plan.domain.secciones import (
    LARGO_MAXIMO_REMEDIOS,
    LARGO_MAXIMO_SECCION,
    SECCIONES_COMPLEMENTARIAS,
    SeccionComplementaria,
    SeccionNoAgregada,
    SeccionVisible,
    TextoSeccionInvalido,
    campos_del_acceso,
    largo_maximo,
    precondicion_para_quitar,
    seccion_de,
    secciones_a_compartir,
    secciones_del_acceso,
    secciones_para_relevo,
    secciones_permitidas,
    validar_texto_seccion,
)
from app.shared.auditoria import (
    SECCIONES_AUDITABLES,
    AccionAuditoria,
    ActorTipo,
    EntidadAuditoria,
    EntradaAuditoria,
)

pytestmark = pytest.mark.rf("RF-03")

S = SeccionComplementaria
BASE = ("rutina", "manejo_situaciones", "red_apoyo")
AHORA = datetime(2026, 11, 10, 14, 0, tzinfo=UTC)


# --- Las seis secciones ------------------------------------------------------------------------------


def test_las_seis_secciones_en_el_orden_de_adr_028() -> None:
    assert [s.value for s in SECCIONES_COMPLEMENTARIAS] == [
        "quien_es", "preferencias", "alimentacion", "movilidad", "comunicacion", "remedios"
    ]


@pytest.mark.parametrize("valor", [s.value for s in SeccionComplementaria])
def test_seccion_de_reconoce_las_seis(valor: str) -> None:
    assert seccion_de(valor) is SeccionComplementaria(valor)


@pytest.mark.parametrize(
    "valor", ["rutina", "manejo_situaciones", "red_apoyo", "horarios", "actividades", "", "REMEDIOS"]
)
def test_seccion_de_rechaza_campos_base_y_tipos_en_desuso(valor: str) -> None:
    assert seccion_de(valor) is None


def test_las_secciones_se_cifran_con_su_propio_aad() -> None:
    """Cada sección nueva es un tipo de plan_seccion, y su AAD es plan_id ‖ tipo como un campo base."""
    plan = uuid.UUID("00000000-0000-0000-0000-0000000050a0")
    assert {s.value for s in SECCIONES_COMPLEMENTARIAS} <= TIPOS_SECCION
    for s in SECCIONES_COMPLEMENTARIAS:
        assert datos_asociados(plan, s.value) == plan.bytes + s.value.encode()
    assert len({datos_asociados(plan, s.value) for s in SECCIONES_COMPLEMENTARIAS}) == 6


def test_el_detalle_de_auditoria_admite_exactamente_las_seis() -> None:
    """app/shared no importa care_plan: la lista se repite, y esta prueba las mantiene iguales."""
    assert {s.value for s in SECCIONES_COMPLEMENTARIAS} == SECCIONES_AUDITABLES


def test_el_esquema_de_compartir_usa_las_seis() -> None:
    anotacion = SolicitudAccesoVista.model_fields["secciones_adicionales"].annotation
    assert anotacion is not None
    [item] = get_args(anotacion)
    assert item is SeccionComplementaria


# --- Texto: vacío y máximo por sección ---------------------------------------------------------------


@pytest.mark.parametrize(("seccion", "maximo"), [(S.QUIEN_ES, 500), (S.COMUNICACION, 500), (S.REMEDIOS, 800)])
def test_largo_maximo_por_seccion(seccion: SeccionComplementaria, maximo: int) -> None:
    assert largo_maximo(seccion) == maximo
    assert validar_texto_seccion(seccion, "a" * maximo) == "a" * maximo
    with pytest.raises(TextoSeccionInvalido) as error:
        validar_texto_seccion(seccion, "a" * (maximo + 1))
    assert error.value.tipo == "largo_maximo"
    assert str(maximo) in error.value.mensaje


def test_constantes_del_contrato() -> None:
    assert (LARGO_MAXIMO_SECCION, LARGO_MAXIMO_REMEDIOS) == (500, 800)


@pytest.mark.parametrize("texto", ["", "   ", "\n\n", " \r\n\t "])
def test_vacio_o_solo_espacios_es_vacio(texto: str) -> None:
    with pytest.raises(TextoSeccionInvalido) as error:
        validar_texto_seccion(S.PREFERENCIAS, texto)
    assert error.value.tipo == "vacio"


def test_el_maximo_se_cuenta_despues_de_normalizar() -> None:
    """Espacios en los extremos y \\r\\n no cuentan de más, igual que un campo base."""
    texto = "  " + "a" * 249 + "\r\n" + "b" * 250 + "  "
    assert validar_texto_seccion(S.MOVILIDAD, texto) == "a" * 249 + "\n" + "b" * 250


def test_el_error_no_lleva_el_texto() -> None:
    marca = "Toma una pastilla sintética " + "x" * 800
    with pytest.raises(TextoSeccionInvalido) as error:
        validar_texto_seccion(S.REMEDIOS, marca)
    assert marca[:20] not in str(error.value) and marca[:20] not in error.value.mensaje
    assert marca[:20] not in repr(error.value.args)


def test_puntos_de_codigo_no_bytes() -> None:
    assert validar_texto_seccion(S.QUIEN_ES, "ñ" * 500) == "ñ" * 500


# --- Quitar exige If-Match ---------------------------------------------------------------------------


def test_quitar_con_if_match() -> None:
    assert precondicion_para_quitar('"v3"', None) == SiCoincide(3)
    assert precondicion_para_quitar('W/"v3"', None) == SiCoincide(None)  # nunca coincide: 412


@pytest.mark.parametrize("if_match", [None, "", " ", "*"])
def test_quitar_sin_if_match_o_con_asterisco_falta_la_precondicion(if_match: str | None) -> None:
    with pytest.raises(FaltaPrecondicion):
        precondicion_para_quitar(if_match, None)


@pytest.mark.parametrize("if_match", [None, '"v1"'])
def test_quitar_con_if_none_match_es_invalido(if_match: str | None) -> None:
    with pytest.raises(PrecondicionInvalida) as error:
        precondicion_para_quitar(if_match, "*")
    assert (error.value.cabecera, error.value.tipo) == ("If-None-Match", "precondicion_invalida")


# --- Compartir: los tres campos siempre, las secciones solo si se piden ---------------------------------


def test_sin_secciones_pedidas_van_solo_los_tres_campos() -> None:
    elegidas = secciones_a_compartir([], {"remedios", "quien_es"})
    assert elegidas == ()
    assert secciones_permitidas(elegidas) == BASE


def test_remedios_solo_va_si_se_pide() -> None:
    """ADR-028: remedios viene desmarcada por defecto. El servidor nunca la agrega por su cuenta."""
    agregadas = {s.value for s in SECCIONES_COMPLEMENTARIAS}
    assert S.REMEDIOS not in secciones_a_compartir([S.COMUNICACION], agregadas)
    assert secciones_a_compartir([S.REMEDIOS, S.COMUNICACION], agregadas) == (S.COMUNICACION, S.REMEDIOS)


def test_secciones_en_el_orden_de_adr_028_sin_importar_el_pedido() -> None:
    agregadas = {s.value for s in SECCIONES_COMPLEMENTARIAS}
    elegidas = secciones_a_compartir([S.REMEDIOS, S.QUIEN_ES, S.MOVILIDAD], agregadas)
    assert elegidas == (S.QUIEN_ES, S.MOVILIDAD, S.REMEDIOS)
    assert secciones_permitidas(elegidas) == (*BASE, "quien_es", "movilidad", "remedios")


@pytest.mark.parametrize("agregadas", [set(), {"comunicacion"}, {"rutina", "red_apoyo"}])
def test_pedir_una_seccion_no_agregada(agregadas: set[str]) -> None:
    with pytest.raises(SeccionNoAgregada):
        secciones_a_compartir([S.COMUNICACION, S.REMEDIOS], agregadas)


def test_campos_y_secciones_de_un_acceso() -> None:
    nuevo = (*BASE, "comunicacion", "remedios")
    assert campos_del_acceso(nuevo) == BASE
    assert secciones_del_acceso(nuevo) == (S.COMUNICACION, S.REMEDIOS)
    # Un acceso anterior a MATU-50, con un solo campo, no comparte ninguna sección
    assert campos_del_acceso(["red_apoyo"]) == ("red_apoyo",)
    assert secciones_del_acceso(["red_apoyo"]) == ()
    # horarios y actividades quedan en el CHECK pero no son secciones complementarias
    assert secciones_del_acceso(["rutina", "horarios", "actividades"]) == ()


# --- Lo que ve el relevo ----------------------------------------------------------------------------


def _visible(tipo: SeccionComplementaria, creado_en: datetime) -> SeccionVisible:
    return SeccionVisible(tipo=tipo, texto=f"texto sintético de {tipo.value}", creado_en=creado_en)


def test_el_relevo_ve_solo_las_compartidas_en_orden() -> None:
    antes = AHORA - timedelta(hours=1)
    visibles = [_visible(S.REMEDIOS, antes), _visible(S.QUIEN_ES, antes), _visible(S.PREFERENCIAS, antes)]
    mostradas = secciones_para_relevo((*BASE, "remedios", "quien_es"), AHORA, visibles)
    assert [s.tipo for s in mostradas] == [S.QUIEN_ES, S.REMEDIOS]  # preferencias no se compartió


def test_el_relevo_no_ve_una_seccion_agregada_despues_del_acceso() -> None:
    """Una sección quitada y vuelta a agregar es otra fila, con creado_en posterior al acceso."""
    visibles = [
        _visible(S.COMUNICACION, AHORA + timedelta(seconds=1)),
        _visible(S.REMEDIOS, AHORA),  # mismo instante: sí la ve
    ]
    mostradas = secciones_para_relevo((*BASE, "comunicacion", "remedios"), AHORA, visibles)
    assert [s.tipo for s in mostradas] == [S.REMEDIOS]


def test_un_acceso_anterior_a_matu_50_no_ve_secciones() -> None:
    visibles = [_visible(S.QUIEN_ES, AHORA - timedelta(days=1))]
    assert secciones_para_relevo(("rutina",), AHORA, visibles) == []


def test_el_texto_no_sale_en_el_repr() -> None:
    visible = _visible(S.REMEDIOS, AHORA)
    assert "texto sintético" not in repr(visible)
    assert "remedios" in repr(visible)


# --- Aperturas --------------------------------------------------------------------------------------


def test_solo_la_apertura_trae_secciones() -> None:
    assert secciones_de_apertura(TipoApertura.APERTURA, ["remedios", "quien_es"]) == (S.QUIEN_ES, S.REMEDIOS)
    assert secciones_de_apertura(TipoApertura.APERTURA, []) == ()
    for tipo in (TipoApertura.PRESENTACION, TipoApertura.PIN_INCORRECTO, TipoApertura.BLOQUEO):
        assert secciones_de_apertura(tipo, ["remedios"]) is None


def test_un_tipo_desconocido_en_el_detalle_se_ignora() -> None:
    assert secciones_de_apertura(TipoApertura.APERTURA, ["rutina", "otra cosa", "comunicacion"]) == (S.COMUNICACION,)


# --- Auditoría: el tipo de la sección, nunca el texto -----------------------------------------------


def _entrada(**cambios: object) -> EntradaAuditoria:
    campos: dict[str, object] = {
        "grupo_id": uuid.uuid4(),
        "actor_tipo": ActorTipo.USUARIO,
        "actor_ref": uuid.uuid4(),
        "accion": AccionAuditoria.PLAN_EDITAR,
        "entidad": EntidadAuditoria.PLAN_SECCION,
        "entidad_id": uuid.uuid4(),
        "persona_cuidada_id": uuid.uuid4(),
    }
    campos.update(cambios)
    return EntradaAuditoria(**campos)  # type: ignore[arg-type]


def test_editar_y_quitar_llevan_el_tipo() -> None:
    assert _entrada(seccion="remedios").detalle() == {"seccion": "remedios"}
    quitar = _entrada(accion=AccionAuditoria.PLAN_QUITAR_SECCION, seccion="quien_es")
    assert quitar.accion.value == "plan.quitar_seccion" and quitar.detalle() == {"seccion": "quien_es"}


def test_abrir_lleva_los_tipos_mostrados() -> None:
    abrir = _entrada(
        actor_tipo=ActorTipo.RELEVO, accion=AccionAuditoria.RELEVO_ABRIR, entidad=EntidadAuditoria.PLAN_CUIDADO,
        secciones=("comunicacion", "remedios"),
    )
    assert abrir.detalle() == {"secciones": ["comunicacion", "remedios"]}
    vacia = _entrada(
        actor_tipo=ActorTipo.RELEVO, accion=AccionAuditoria.RELEVO_ABRIR, entidad=EntidadAuditoria.PLAN_CUIDADO,
        secciones=(),
    )
    assert vacia.detalle() == {"secciones": []}


@pytest.mark.parametrize(
    "cambios",
    [
        pytest.param({"seccion": "Toma 1 pastilla"}, id="texto-libre"),
        pytest.param({"seccion": "rutina"}, id="campo-base"),
        pytest.param({"seccion": "remedios", "accion": AccionAuditoria.PLAN_LEER}, id="seccion-en-lectura"),
        pytest.param({"secciones": ("remedios",)}, id="secciones-en-editar"),
        pytest.param(
            {"secciones": ("remedios", "remedios"), "accion": AccionAuditoria.RELEVO_ABRIR,
             "actor_tipo": ActorTipo.RELEVO},
            id="secciones-repetidas",
        ),
        pytest.param(
            {"secciones": ("texto libre",), "accion": AccionAuditoria.RELEVO_ABRIR, "actor_tipo": ActorTipo.RELEVO},
            id="secciones-texto-libre",
        ),
        pytest.param(
            {"secciones": ["remedios"], "accion": AccionAuditoria.RELEVO_ABRIR, "actor_tipo": ActorTipo.RELEVO},
            id="secciones-no-tupla",
        ),
    ],
)
def test_detalle_fuera_de_lo_acotado_se_rechaza(cambios: dict[str, object]) -> None:
    with pytest.raises(TypeError):
        _entrada(**cambios)
