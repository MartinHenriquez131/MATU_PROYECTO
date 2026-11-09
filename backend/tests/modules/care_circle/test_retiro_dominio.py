"""MATU-44 · Reglas del retiro y del estado de las autorizaciones, y el caso de uso con dobles. Sin base."""

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.care_circle.application.retiro import (
    AutorizacionNoEncontrada,
    EfectoNoDisponible,
    RolSinPermisoRetiro,
    SolicitudRetiro,
    antes_de_otorgar,
    estado_autorizaciones,
    retirar_autorizacion,
)
from app.modules.care_circle.domain import retiro as dominio
from app.modules.care_circle.domain.retiro import (
    AutorizacionRegistrada,
    EstadoVista,
    YaRetirada,
    borrado_desde,
    estado_de,
    exigir_retirable,
    finalidad_de,
    plazo_cumplido,
    puede_retirar,
)
from tests.dobles.reloj_fijo import RelojFijo

pytestmark = pytest.mark.rf("RF-02")

AHORA = datetime(2026, 11, 6, 15, 0, tzinfo=UTC)


def _autorizacion(
    finalidad: str = "plan_cuidado",
    calidad: str = "titular",
    revision: datetime | None = None,
    revocado: datetime | None = None,
) -> AutorizacionRegistrada:
    return AutorizacionRegistrada(
        id=uuid.uuid4(), finalidad=finalidad, calidad_otorgante=calidad, otorgado_en=AHORA - timedelta(days=200),
        revision_vence_en=revision, revocado_en=revocado,
    )


@pytest.mark.parametrize(("rol", "puede"), [("admin", True), ("cuidador", True), ("pagador", False),
                                            ("observador", False), ("desconocido", False)])
def test_retiran_admin_y_cuidador(rol: str, puede: bool) -> None:
    assert puede_retirar(rol) is puede


def test_finalidades_del_path() -> None:
    assert finalidad_de("plan_cuidado") == "plan_cuidado" and finalidad_de("consumo") == "consumo"
    for otra in ("despacho", "comunicaciones", "", "PLAN_CUIDADO"):
        assert finalidad_de(otra) is None


def test_ya_retirada() -> None:
    with pytest.raises(YaRetirada):
        exigir_retirable(_autorizacion(revocado=AHORA - timedelta(days=1)), AHORA)


def test_con_la_revision_vencida_se_retira() -> None:
    """Condición 3 del analista (P6 pendiente de Jorge): la regla está encendida."""
    assert dominio.RETIRO_CON_REVISION_VENCIDA is True
    exigir_retirable(_autorizacion(calidad="cuidador_de_hecho", revision=AHORA - timedelta(seconds=1)), AHORA)


def test_con_la_regla_p6_apagada_no_se_retira_vencida(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dominio, "RETIRO_CON_REVISION_VENCIDA", False)
    with pytest.raises(dominio.RetiroNoPermitido):
        exigir_retirable(_autorizacion(calidad="cuidador_de_hecho", revision=AHORA), AHORA)


def test_plazo_de_90_dias_desde_el_instante_exacto() -> None:
    retiro = AHORA - timedelta(days=90)
    assert borrado_desde(retiro) == AHORA
    assert plazo_cumplido(retiro, AHORA)
    assert not plazo_cumplido(retiro, AHORA - timedelta(seconds=1))
    assert not plazo_cumplido(None, AHORA)


def test_estado_sin_autorizar() -> None:
    estado = estado_de("consumo", None, None, AHORA)
    assert (estado.estado, estado.autorizacion, estado.borrado_en, estado.borrada) == (
        EstadoVista.SIN_AUTORIZAR, None, None, False)


def test_estado_vigente_y_por_renovar() -> None:
    assert estado_de("plan_cuidado", _autorizacion(), None, AHORA).estado is EstadoVista.VIGENTE
    vencida = _autorizacion(calidad="cuidador_de_hecho", revision=AHORA)
    assert estado_de("plan_cuidado", vencida, None, AHORA).estado is EstadoVista.REVISION_VENCIDA


def test_estado_retirada_y_borrada_segun_el_reloj() -> None:
    retiro = AHORA - timedelta(days=89)
    retirada = estado_de("consumo", _autorizacion("consumo", revocado=retiro), None, AHORA)
    assert (retirada.estado, retirada.borrado_en, retirada.borrada) == (
        EstadoVista.RETIRADA, retiro + timedelta(days=90), False)
    borrada = estado_de("consumo", _autorizacion("consumo", revocado=retiro), None, AHORA + timedelta(days=1))
    assert (borrada.estado, borrada.borrada) == (EstadoVista.BORRADA, True)


def test_autorizada_de_nuevo_despues_del_dia_90_dice_que_lo_anterior_se_borro() -> None:
    """P8: la ficha empieza en blanco. La vista lo dice con borrada y borrado_en, sin leer la ficha."""
    retiro = _autorizacion(revocado=AHORA - timedelta(days=100))
    nueva = replace(_autorizacion(), otorgado_en=AHORA - timedelta(days=5))
    vigente = estado_de("plan_cuidado", nueva, retiro, AHORA)
    assert (vigente.estado, vigente.borrado_en, vigente.borrada) == (
        EstadoVista.VIGENTE, retiro.revocado_en + timedelta(days=90), True)  # type: ignore[operator]


def test_autorizada_de_nuevo_antes_del_dia_90_no_se_borro_nada() -> None:
    retiro = _autorizacion(revocado=AHORA - timedelta(days=30))
    nueva = replace(_autorizacion(), otorgado_en=AHORA - timedelta(days=5))
    vigente = estado_de("plan_cuidado", nueva, retiro, AHORA)
    assert (vigente.estado, vigente.borrado_en, vigente.borrada) == (EstadoVista.VIGENTE, None, False)


# --- Caso de uso, con dobles -----------------------------------------------------------------------------


class Repo:
    def __init__(self, filas: dict[str, list[AutorizacionRegistrada]]) -> None:
        self.filas = filas
        self.retiradas: list[tuple[uuid.UUID, datetime]] = []
        self.motivos: list[str] = []

    def bloquear_vigente(self, persona_id: uuid.UUID, finalidad: str) -> AutorizacionRegistrada | None:
        return next((a for a in self.filas.get(finalidad, []) if a.revocado_en is None), None)

    def ultima(self, persona_id: uuid.UUID, finalidad: str) -> AutorizacionRegistrada | None:
        filas = self.filas.get(finalidad, [])
        vigente = self.bloquear_vigente(persona_id, finalidad)
        if vigente is not None:
            return vigente
        revocadas = sorted((a for a in filas if a.revocado_en), key=lambda a: a.revocado_en or AHORA)
        return revocadas[-1] if revocadas else None

    def retiro_anterior(self, persona_id: uuid.UUID, finalidad: str,
                        antes_de: datetime) -> AutorizacionRegistrada | None:
        revocadas = [a for a in self.filas.get(finalidad, []) if a.revocado_en and a.revocado_en <= antes_de]
        return max(revocadas, key=lambda a: a.revocado_en or AHORA) if revocadas else None

    def retirar(self, consentimiento_id: uuid.UUID, ahora: datetime, usuario_id: uuid.UUID,
                request_id: str | None, motivo: str = "retiro") -> None:
        self.retiradas.append((consentimiento_id, ahora))
        self.motivos.append(motivo)


class Efecto:
    def __init__(self, cortados: int = 0, falla: bool = False) -> None:
        self.cortados = cortados
        self.falla = falla
        self.aplicados: list[datetime] = []
        self.preparados: list[tuple[datetime, bool]] = []
        self.borrados: list[datetime] = []

    def aplicar(self, persona_id: uuid.UUID, ahora: datetime, usuario_id: uuid.UUID, request_id: str | None) -> int:
        if self.falla:
            raise RuntimeError("falla sintética")
        self.aplicados.append(ahora)
        return self.cortados

    def antes_de_otorgar(
        self, persona_id: uuid.UUID, ahora: datetime, request_id: str | None, plazo_cumplido: bool
    ) -> None:
        self.preparados.append((ahora, plazo_cumplido))

    def borrar(self, persona_id: uuid.UUID, ahora: datetime, usuario_id: uuid.UUID, request_id: str | None) -> int:
        if self.falla:
            raise RuntimeError("falla sintética")
        self.borrados.append(ahora)
        return self.cortados


def _solicitud(rol: str = "cuidador", finalidad: str = "plan_cuidado") -> SolicitudRetiro:
    return SolicitudRetiro(usuario_id=uuid.uuid4(), rol=rol, persona_id=uuid.uuid4(), finalidad=finalidad)


def test_retirar_fija_el_instante_del_reloj_y_aplica_el_efecto() -> None:
    vigente = _autorizacion()
    repo, efecto = Repo({"plan_cuidado": [vigente]}), Efecto(cortados=3)
    resultado = retirar_autorizacion(_solicitud(), RelojFijo(AHORA), repo, {"plan_cuidado": efecto})
    assert repo.retiradas == [(vigente.id, AHORA)] and efecto.aplicados == [AHORA]
    assert resultado.enlaces_cortados == 3
    assert resultado.estado.estado is EstadoVista.RETIRADA
    assert resultado.estado.autorizacion == replace(vigente, revocado_en=AHORA)
    assert resultado.estado.borrado_en == AHORA + timedelta(days=90)


@pytest.mark.parametrize("rol", ["pagador", "observador"])
def test_pagador_y_observador_no_retiran(rol: str) -> None:
    repo = Repo({"plan_cuidado": [_autorizacion()]})
    with pytest.raises(RolSinPermisoRetiro):
        retirar_autorizacion(_solicitud(rol), RelojFijo(AHORA), repo, {"plan_cuidado": Efecto()})
    assert repo.retiradas == []


def test_nunca_autorizada_404_y_ya_retirada_409() -> None:
    with pytest.raises(AutorizacionNoEncontrada):
        retirar_autorizacion(_solicitud(finalidad="consumo"), RelojFijo(AHORA), Repo({}), {"consumo": Efecto()})
    repo = Repo({"consumo": [_autorizacion("consumo", revocado=AHORA - timedelta(days=1))]})
    with pytest.raises(YaRetirada):
        retirar_autorizacion(_solicitud(finalidad="consumo"), RelojFijo(AHORA), repo, {"consumo": Efecto()})
    assert repo.retiradas == []


def test_sin_efecto_registrado_no_retira() -> None:
    repo = Repo({"plan_cuidado": [_autorizacion()]})
    with pytest.raises(EfectoNoDisponible):
        retirar_autorizacion(_solicitud(), RelojFijo(AHORA), repo, {})
    assert repo.retiradas == []


def test_si_el_efecto_falla_la_excepcion_sigue() -> None:
    """La transacción de la petición deshace la revocación: el caso de uso no se traga el error."""
    repo = Repo({"plan_cuidado": [_autorizacion()]})
    with pytest.raises(RuntimeError):
        retirar_autorizacion(_solicitud(), RelojFijo(AHORA), repo, {"plan_cuidado": Efecto(falla=True)})


def test_estado_trae_las_dos_finalidades_en_orden() -> None:
    repo = Repo({"plan_cuidado": [_autorizacion()]})
    estados = estado_autorizaciones(uuid.uuid4(), RelojFijo(AHORA), repo)
    assert [(e.finalidad, e.estado) for e in estados] == [
        ("plan_cuidado", EstadoVista.VIGENTE), ("consumo", EstadoVista.SIN_AUTORIZAR)]


@pytest.mark.parametrize(("dias", "borra"), [(89, False), (90, True)])
def test_antes_de_otorgar_avisa_el_plazo_cumplido_solo_desde_el_dia_90(dias: int, borra: bool) -> None:
    efecto = Efecto()
    repo = Repo({"consumo": [_autorizacion("consumo", revocado=AHORA - timedelta(days=dias))]})
    antes_de_otorgar(uuid.uuid4(), "consumo", AHORA, None, repo, {"consumo": efecto})
    assert efecto.preparados == [(AHORA, borra)]


def test_antes_de_otorgar_sin_retiro_no_hace_nada() -> None:
    efecto = Efecto()
    antes_de_otorgar(uuid.uuid4(), "plan_cuidado", AHORA, None, Repo({}), {"plan_cuidado": efecto})
    antes_de_otorgar(uuid.uuid4(), "plan_cuidado", AHORA, None, Repo({"plan_cuidado": [_autorizacion()]}),
                     {"plan_cuidado": efecto})
    assert efecto.preparados == []
