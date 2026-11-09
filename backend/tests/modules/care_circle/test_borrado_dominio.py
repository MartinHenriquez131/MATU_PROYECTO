"""MATU-72 · Reglas del borrado de la persona y el caso de uso con dobles (decisiones 149 a 157). Sin base."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.care_circle.application.borrado import (
    RolSinPermisoBorrado,
    SolicitudBorrado,
    borrar_persona,
)
from app.modules.care_circle.application.retiro import EfectoNoDisponible, antes_de_otorgar
from app.modules.care_circle.domain.borrado import (
    NOMBRE_BORRADO,
    PersonaNoEncontrada,
    PersonaParaBorrar,
    YaBorrada,
    exigir_borrable,
    orden_de_bloqueo,
    puede_borrar,
)
from app.modules.care_circle.domain.retiro import (
    MOTIVO_BORRADO,
    AutorizacionRegistrada,
    EstadoVista,
    estado_de,
    fue_borrado,
    lo_guardado_ya_no_esta,
)
from tests.dobles.reloj_fijo import RelojFijo
from tests.modules.care_circle.test_retiro_dominio import Efecto
from tests.modules.care_circle.test_retiro_dominio import Repo as RepoRetiros

pytestmark = pytest.mark.rf("RF-01")

AHORA = datetime(2026, 11, 8, 15, 0, tzinfo=UTC)
PERSONA = uuid.UUID("00000000-0000-0000-0000-000000007201")


def _autorizacion(finalidad: str = "plan_cuidado", revocado: datetime | None = None,
                  motivo: str | None = None) -> AutorizacionRegistrada:
    return AutorizacionRegistrada(
        id=uuid.uuid4(), finalidad=finalidad, calidad_otorgante="titular", otorgado_en=AHORA - timedelta(days=30),
        revision_vence_en=None, revocado_en=revocado, revocacion_motivo=motivo,
    )


def _persona(eliminado: datetime | None = None, borrado: datetime | None = None) -> PersonaParaBorrar:
    return PersonaParaBorrar(id=PERSONA, eliminado_en=eliminado, datos_borrados_en=borrado, direccion_id=None)


# --- Reglas ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("rol", "borra"), [("admin", True), ("cuidador", True), ("pagador", False),
                                            ("observador", False), ("otro", False)])
def test_borran_admin_y_cuidador_como_en_el_retiro(rol: str, borra: bool) -> None:
    assert puede_borrar(rol) is borra


def test_exigir_borrable_404_409_y_la_persona() -> None:
    with pytest.raises(PersonaNoEncontrada):
        exigir_borrable(None)
    # C3: ya borrada es 409, aunque también tenga eliminado_en
    with pytest.raises(YaBorrada):
        exigir_borrable(_persona(eliminado=AHORA, borrado=AHORA))
    with pytest.raises(PersonaNoEncontrada):
        exigir_borrable(_persona(eliminado=AHORA))
    persona = _persona()
    assert exigir_borrable(persona) is persona


def test_orden_de_bloqueo_plan_consumo_y_las_demas_al_final() -> None:
    finalidades = ["despacho", "consumo", "plan_cuidado", "aviso"]
    assert sorted(finalidades, key=lambda f: (orden_de_bloqueo(f), f)) == ["plan_cuidado", "consumo", "aviso",
                                                                         "despacho"]


def test_el_nombre_fijo_no_dice_nada() -> None:
    assert NOMBRE_BORRADO == "borrada"


@pytest.mark.rf("RF-02")
def test_una_revocacion_por_borrado_esta_borrada_desde_ese_instante() -> None:
    """C10, decisión 154: sin esperar 90 días, y borrado_en es el mismo instante."""
    borrada = _autorizacion(revocado=AHORA, motivo=MOTIVO_BORRADO)
    assert fue_borrado(borrada) and lo_guardado_ya_no_esta(borrada, AHORA)
    estado = estado_de("plan_cuidado", borrada, None, AHORA)
    assert (estado.estado, estado.borrado_en, estado.borrada) == (EstadoVista.BORRADA, AHORA, True)
    # Un retiro sigue esperando sus 90 días
    retirada = _autorizacion(revocado=AHORA, motivo="retiro")
    assert not fue_borrado(retirada) and not lo_guardado_ya_no_esta(retirada, AHORA)
    assert estado_de("plan_cuidado", retirada, None, AHORA).estado is EstadoVista.RETIRADA
    assert lo_guardado_ya_no_esta(retirada, AHORA + timedelta(days=90))
    assert not lo_guardado_ya_no_esta(_autorizacion(), AHORA)


@pytest.mark.rf("RF-02")
def test_una_autorizacion_despues_de_un_borrado_dice_que_lo_de_antes_se_borro() -> None:
    anterior = _autorizacion(revocado=AHORA - timedelta(days=1), motivo=MOTIVO_BORRADO)
    nueva = _autorizacion()
    estado = estado_de("plan_cuidado", nueva, anterior, AHORA)
    assert (estado.estado, estado.borrada, estado.borrado_en) == (EstadoVista.VIGENTE, True, anterior.revocado_en)


@pytest.mark.rf("RF-02")
def test_volver_a_autorizar_tras_un_borrado_cuenta_como_plazo_cumplido() -> None:
    """C10: antes_de_otorgar reconoce el borrado aunque no pasaran 90 días: nunca vuelve lo escrito."""
    efecto = Efecto()
    repo = RepoRetiros({"plan_cuidado": [_autorizacion(revocado=AHORA - timedelta(days=1), motivo=MOTIVO_BORRADO)]})
    antes_de_otorgar(PERSONA, "plan_cuidado", AHORA, None, repo, {"plan_cuidado": efecto})
    assert efecto.preparados == [(AHORA, True)]


# --- Caso de uso, con dobles -----------------------------------------------------------------------------------


class RepoBorrado:
    def __init__(self, persona: PersonaParaBorrar | None, vigentes: list[AutorizacionRegistrada]) -> None:
        self.persona = persona
        self.vigentes = vigentes
        self.pasos: list[str] = []
        self.anonimizadas: list[tuple[uuid.UUID, datetime]] = []

    def bloquear_persona(self, persona_id: uuid.UUID) -> PersonaParaBorrar | None:
        self.pasos.append("persona")
        return self.persona

    def bloquear_vigentes(self, persona_id: uuid.UUID) -> list[AutorizacionRegistrada]:
        self.pasos.append("vigentes")
        return self.vigentes

    def anonimizar(self, persona: PersonaParaBorrar, ahora: datetime, usuario_id: uuid.UUID,
                   request_id: str | None) -> None:
        self.pasos.append("anonimizar")
        self.anonimizadas.append((persona.id, ahora))


class _RelojQueAvanza:
    def __init__(self) -> None:
        self.actual = AHORA

    def ahora(self) -> datetime:
        self.actual += timedelta(milliseconds=1)
        return self.actual


def _solicitud(rol: str = "cuidador") -> SolicitudBorrado:
    return SolicitudBorrado(usuario_id=uuid.uuid4(), rol=rol, persona_id=PERSONA)


def test_borrar_retira_con_motivo_borrado_aplica_los_efectos_y_cuenta() -> None:
    plan, consumo = _autorizacion(), _autorizacion("consumo")
    repo, retiros = RepoBorrado(_persona(), [plan, consumo]), RepoRetiros({})
    ficha, insumos = Efecto(cortados=3), Efecto()

    resultado = borrar_persona(_solicitud(), RelojFijo(AHORA), repo, retiros, {"consumo": insumos,
                                                                              "plan_cuidado": ficha})

    assert retiros.retiradas == [(plan.id, AHORA), (consumo.id, AHORA)]
    assert retiros.motivos == ["borrado", "borrado"]
    assert ficha.borrados == [AHORA] and insumos.borrados == [AHORA]
    assert repo.pasos == ["persona", "vigentes", "anonimizar"] and repo.anonimizadas == [(PERSONA, AHORA)]
    assert (resultado.persona_id, resultado.borrado_en, resultado.enlaces_cortados,
            resultado.autorizaciones_retiradas) == (PERSONA, AHORA, 3, 2)


def test_borrar_lee_el_reloj_una_sola_vez() -> None:
    reloj = _RelojQueAvanza()
    retiros = RepoRetiros({})
    resultado = borrar_persona(_solicitud(), reloj, RepoBorrado(_persona(), [_autorizacion()]), retiros,
                               {"plan_cuidado": Efecto(), "consumo": Efecto()})
    assert retiros.retiradas[0][1] == resultado.borrado_en == reloj.actual


def test_sin_autorizaciones_vigentes_igual_borra_todo() -> None:
    """Las ya retiradas conservan su motivo (D2): el repositorio no las devuelve y no se tocan."""
    ficha, insumos = Efecto(), Efecto()
    retiros = RepoRetiros({})
    resultado = borrar_persona(_solicitud("admin"), RelojFijo(AHORA), RepoBorrado(_persona(), []), retiros,
                               {"plan_cuidado": ficha, "consumo": insumos})
    assert retiros.retiradas == [] and resultado.autorizaciones_retiradas == 0
    assert ficha.borrados == [AHORA] and insumos.borrados == [AHORA]


@pytest.mark.parametrize("rol", ["pagador", "observador"])
def test_pagador_y_observador_no_borran_y_no_se_lee_nada(rol: str) -> None:
    repo = RepoBorrado(_persona(), [_autorizacion()])
    with pytest.raises(RolSinPermisoBorrado):
        borrar_persona(_solicitud(rol), RelojFijo(AHORA), repo, RepoRetiros({}),
                       {"plan_cuidado": Efecto(), "consumo": Efecto()})
    assert repo.pasos == []


@pytest.mark.parametrize(("persona", "error"), [
    (None, PersonaNoEncontrada),
    (_persona(eliminado=AHORA), PersonaNoEncontrada),
    (_persona(eliminado=AHORA, borrado=AHORA), YaBorrada),
])
def test_persona_ausente_o_ya_borrada_no_escribe_nada(persona: PersonaParaBorrar | None, error: type) -> None:
    repo, retiros, ficha = RepoBorrado(persona, [_autorizacion()]), RepoRetiros({}), Efecto()
    with pytest.raises(error):
        borrar_persona(_solicitud(), RelojFijo(AHORA), repo, retiros, {"plan_cuidado": ficha, "consumo": Efecto()})
    assert repo.pasos == ["persona"] and retiros.retiradas == [] and ficha.borrados == []


def test_sin_el_efecto_de_una_finalidad_no_se_borra_nada() -> None:
    """Falla cerrado: sin el efecto del consumo, sus perfiles quedarían guardados."""
    repo, retiros, ficha = RepoBorrado(_persona(), [_autorizacion()]), RepoRetiros({}), Efecto()
    with pytest.raises(EfectoNoDisponible):
        borrar_persona(_solicitud(), RelojFijo(AHORA), repo, retiros, {"plan_cuidado": ficha})
    assert retiros.retiradas == [] and ficha.borrados == [] and repo.anonimizadas == []


def test_si_falla_un_efecto_la_excepcion_sigue_y_no_se_anonimiza() -> None:
    """La transacción de la petición la deshace (C13, la prueba contra la base lo verifica)."""
    repo = RepoBorrado(_persona(), [_autorizacion()])
    with pytest.raises(RuntimeError):
        borrar_persona(_solicitud(), RelojFijo(AHORA), repo, RepoRetiros({}),
                       {"plan_cuidado": Efecto(falla=True), "consumo": Efecto()})
    assert repo.anonimizadas == []
