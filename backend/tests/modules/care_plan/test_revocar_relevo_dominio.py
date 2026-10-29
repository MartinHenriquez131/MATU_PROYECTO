"""MATU-20 · Reglas puras de revocar un acceso de relevo (RF-07), sin base de datos."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.care_plan.application.relevo import AccesoNoEncontrado, PeticionRevocar, revocar
from app.modules.care_plan.domain.relevo import VidaAcceso, debe_revocar, puede_revocar
from tests.dobles.reloj_fijo import RelojFijo

pytestmark = pytest.mark.rf("RF-07")

AHORA = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)


def _vida(expira_en: datetime = AHORA + timedelta(hours=1), revocado_en: datetime | None = None,
          intentos: int = 0) -> VidaAcceso:
    return VidaAcceso(expira_en=expira_en, revocado_en=revocado_en, pin_intentos_fallidos=intentos)


@pytest.mark.parametrize(("rol", "puede"), [
    ("admin", True), ("cuidador", True), ("pagador", False), ("observador", False), ("otro", False),
])
def test_revocan_admin_y_cuidador(rol: str, puede: bool) -> None:
    assert puede_revocar(rol) is puede


def test_vigente_se_revoca() -> None:
    assert debe_revocar(_vida(), AHORA)


def test_bloqueado_se_revoca() -> None:
    assert debe_revocar(_vida(intentos=5), AHORA)


def test_ya_revocado_no_se_vuelve_a_revocar() -> None:
    assert not debe_revocar(_vida(revocado_en=AHORA - timedelta(minutes=5)), AHORA)


def test_vencido_no_se_revoca_desde_el_instante_exacto() -> None:
    assert not debe_revocar(_vida(expira_en=AHORA), AHORA)
    assert debe_revocar(_vida(expira_en=AHORA + timedelta(microseconds=1)), AHORA)


class _AccesosEspia:
    def __init__(self, vida: VidaAcceso | None) -> None:
        self.vida = vida
        self.revocados: list[tuple[uuid.UUID, datetime]] = []

    def vida_para_revocar(self, acceso_id: uuid.UUID) -> VidaAcceso | None:
        return self.vida

    def revocar(self, acceso_id: uuid.UUID, ahora: datetime, usuario_id: uuid.UUID, request_id: str | None) -> None:
        self.revocados.append((acceso_id, ahora))


def _peticion() -> PeticionRevocar:
    return PeticionRevocar(grupo_id=uuid.uuid4(), usuario_id=uuid.uuid4(), acceso_id=uuid.uuid4(), request_id="r")


def test_caso_de_uso_revoca_con_el_instante_del_reloj() -> None:
    accesos = _AccesosEspia(_vida())
    peticion = _peticion()
    assert revocar(peticion, accesos, RelojFijo(AHORA)) is True  # type: ignore[arg-type]
    assert accesos.revocados == [(peticion.acceso_id, AHORA)]


@pytest.mark.parametrize("vida", [_vida(revocado_en=AHORA - timedelta(hours=1)), _vida(expira_en=AHORA)])
def test_caso_de_uso_idempotente_no_escribe(vida: VidaAcceso) -> None:
    accesos = _AccesosEspia(vida)
    assert revocar(_peticion(), accesos, RelojFijo(AHORA)) is False  # type: ignore[arg-type]
    assert accesos.revocados == []


def test_caso_de_uso_sin_acceso() -> None:
    with pytest.raises(AccesoNoEncontrado):
        revocar(_peticion(), _AccesosEspia(None), RelojFijo(AHORA))  # type: ignore[arg-type]
