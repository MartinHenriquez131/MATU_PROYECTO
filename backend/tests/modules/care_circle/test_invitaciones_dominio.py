"""MATU-42 · Reglas puras de la invitación (RF-38, decisiones 294 a 301 y 308). Sin base."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.care_circle.application.invitaciones import Actor, NoEncontrado, crear_invitacion, texto_del_token
from app.modules.care_circle.domain.invitaciones import (
    VIGENCIA,
    Anulacion,
    EstadoInvitacion,
    VidaInvitacion,
    anulacion,
    codigo_valido,
    estado,
    expira_en,
    nombre_pila,
    tope_superado,
    url_invitacion,
)
from app.modules.care_circle.infrastructure.credenciales_invitacion import CredencialesInvitacionHmac, huella_de_texto
from tests.dobles.reloj_fijo import RelojFijo

pytestmark = pytest.mark.rf("RF-38")

AHORA = datetime(2026, 11, 12, 21, 30, tzinfo=UTC)


def _vida(**cambios: datetime | None) -> VidaInvitacion:
    datos: dict[str, datetime | None] = {
        "expira_en": AHORA + timedelta(days=1), "aceptada_en": None, "revocada_en": None, "bloqueada_en": None,
    }
    datos.update(cambios)
    return VidaInvitacion(**datos)  # type: ignore[arg-type]


def test_vence_a_los_7_dias_exactos() -> None:
    assert VIGENCIA == timedelta(days=7)
    assert expira_en(AHORA) == AHORA + timedelta(days=7)


@pytest.mark.parametrize(
    ("vida", "esperado"),
    [
        (_vida(), EstadoInvitacion.PENDIENTE),
        (_vida(bloqueada_en=AHORA), EstadoInvitacion.BLOQUEADA),
        (_vida(expira_en=AHORA), EstadoInvitacion.VENCIDA),
        (_vida(aceptada_en=AHORA, expira_en=AHORA), EstadoInvitacion.USADA),
        # Anulada gana a todo, como en el contrato: inexistente y anulada dan lo mismo (C28)
        (_vida(revocada_en=AHORA, aceptada_en=AHORA, bloqueada_en=AHORA), EstadoInvitacion.ANULADA),
        (_vida(bloqueada_en=AHORA, expira_en=AHORA - timedelta(seconds=1)), EstadoInvitacion.VENCIDA),
    ],
)
def test_estado_en_el_orden_del_contrato(vida: VidaInvitacion, esperado: EstadoInvitacion) -> None:
    assert estado(vida, AHORA) is esperado


@pytest.mark.parametrize(
    ("estado_actual", "esperado"),
    [
        (EstadoInvitacion.PENDIENTE, Anulacion.ANULAR),
        (EstadoInvitacion.BLOQUEADA, Anulacion.ANULAR),
        (EstadoInvitacion.ANULADA, Anulacion.YA_ANULADA),
        (EstadoInvitacion.USADA, Anulacion.CERRADA),
        (EstadoInvitacion.VENCIDA, Anulacion.CERRADA),
    ],
)
def test_que_hace_anular(estado_actual: EstadoInvitacion, esperado: Anulacion) -> None:
    assert anulacion(estado_actual) is esperado


def test_nombre_de_pila_y_url_con_el_token_en_el_fragmento() -> None:
    assert nombre_pila("Carmen Soto Pérez") == "Carmen"
    assert nombre_pila("   ") == ""
    assert url_invitacion("https://matu.example", "abc") == "https://matu.example/invitacion#abc"


@pytest.mark.parametrize(("codigo", "valido"), [("0000", True), ("4827", True), ("482", False), ("48a7", False),
                                                ("٤٨٢٧", False)])
def test_el_codigo_son_4_digitos_ascii(codigo: str, valido: bool) -> None:
    assert codigo_valido(codigo) is valido


def test_el_tope_es_20_en_24_horas() -> None:
    assert not tope_superado(20) and tope_superado(21)


def test_las_huellas_separan_dominio_e_invitacion() -> None:
    credenciales = CredencialesInvitacionHmac(b"p" * 32)
    a, b = uuid.uuid4(), uuid.uuid4()
    assert credenciales.huella_codigo(a, "1234") != credenciales.huella_codigo(b, "1234")
    assert len(credenciales.huella_codigo(a, "1234")) == 32
    assert "p" * 32 not in repr(credenciales)
    codigo = credenciales.codigo()
    assert codigo_valido(codigo)
    token = credenciales.token()
    assert len(token) == 32
    assert huella_de_texto(texto_del_token(token)) == credenciales.huella_token(token)
    assert huella_de_texto("no-es-un-token") is None


class _RepositorioMinimo:
    def __init__(self) -> None:
        self.creadas: list[object] = []

    def nombre_usuario(self, usuario_id: uuid.UUID) -> str | None:
        return "Carmen Soto"

    def crear(self, invitacion: object) -> None:
        self.creadas.append(invitacion)


def test_crear_solo_admin_y_con_7_dias() -> None:
    reloj = RelojFijo(AHORA)
    repositorio = _RepositorioMinimo()
    credenciales = CredencialesInvitacionHmac(b"p" * 32)
    cuidador = Actor(usuario_id=uuid.uuid4(), grupo_id=uuid.uuid4(), rol="cuidador")
    with pytest.raises(NoEncontrado):
        crear_invitacion("cuidador", cuidador, repositorio, credenciales, reloj)  # type: ignore[arg-type]
    admin = Actor(usuario_id=uuid.uuid4(), grupo_id=uuid.uuid4(), rol="admin")
    creada = crear_invitacion("pagador", admin, repositorio, credenciales, reloj)  # type: ignore[arg-type]
    assert creada.expira_en == AHORA + timedelta(days=7) and creada.rol == "pagador"
    [guardada] = repositorio.creadas
    assert guardada.nombre_pila_invita == "Carmen"  # type: ignore[attr-defined]
    # Nunca el token ni el código en claro: solo sus huellas
    assert creada.codigo.encode() not in guardada.codigo_hash  # type: ignore[attr-defined]
