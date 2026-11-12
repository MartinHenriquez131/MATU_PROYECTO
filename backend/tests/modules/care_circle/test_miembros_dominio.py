"""MATU-42 · Reglas puras de quiénes forman el grupo (RF-38, decisiones 302 a 307). Sin base."""

import pytest

from app.modules.care_circle.domain.miembros import (
    ROLES,
    FaltaVersion,
    NoPuedeSalir,
    PermisoSoloPagador,
    RolYPermiso,
    aplicar_cambio,
    deja_de_compartir,
    deja_de_ser_admin,
    deja_sin_admin,
    etag,
    no_puede_salir,
    permiso_visible,
    ve_enlaces,
    version_de_if_match,
)
from app.shared.auditoria import ROLES_AUDITABLES

pytestmark = pytest.mark.rf("RF-38")


def test_los_roles_son_los_de_la_auditoria() -> None:
    assert set(ROLES) == ROLES_AUDITABLES


def test_etag_y_su_lectura() -> None:
    assert etag(3) == '"v3"'
    assert version_de_if_match('"v3"') == 3
    assert version_de_if_match(' W/"v12" ') == 12


@pytest.mark.parametrize("valor", [None, "", "  ", "*"])
def test_sin_if_match_es_falta_version(valor: str | None) -> None:
    with pytest.raises(FaltaVersion):
        version_de_if_match(valor)


@pytest.mark.parametrize("valor", ['"3"', "v3", '"vx"', '"v"', "abc"])
def test_un_if_match_con_otra_forma_no_coincide_con_ninguna_version(valor: str) -> None:
    assert version_de_if_match(valor) is None


@pytest.mark.parametrize(
    ("actual", "rol", "permiso", "esperado"),
    [
        # El permiso se da solo al pagador
        (RolYPermiso("pagador", False), None, True, RolYPermiso("pagador", True)),
        (RolYPermiso("pagador", True), None, False, RolYPermiso("pagador", False)),
        # Seguir en pagador sin pedirlo: no cambia
        (RolYPermiso("pagador", True), "pagador", None, RolYPermiso("pagador", True)),
        # Al dejar de ser pagador vuelve a false (C18)
        (RolYPermiso("pagador", True), "cuidador", None, RolYPermiso("cuidador", False)),
        # Al pasar a pagador queda en false salvo que se pida true
        (RolYPermiso("cuidador", False), "pagador", None, RolYPermiso("pagador", False)),
        (RolYPermiso("cuidador", False), "pagador", True, RolYPermiso("pagador", True)),
        (RolYPermiso("admin", False), "observador", None, RolYPermiso("observador", False)),
    ],
)
def test_aplicar_cambio(actual: RolYPermiso, rol: str | None, permiso: bool | None, esperado: RolYPermiso) -> None:
    assert aplicar_cambio(actual, rol, permiso) == esperado


@pytest.mark.parametrize(("actual", "rol"), [(RolYPermiso("cuidador", False), None), (RolYPermiso("pagador", True),
                                                                                     "observador")])
def test_el_permiso_con_un_rol_que_no_es_pagador_es_422(actual: RolYPermiso, rol: str | None) -> None:
    with pytest.raises(PermisoSoloPagador) as error:
        aplicar_cambio(actual, rol, True)
    assert "True" not in str(error.value)


@pytest.mark.parametrize(
    ("antes", "despues", "corta"),
    [
        ("admin", "pagador", True),
        ("admin", "observador", True),
        ("cuidador", "pagador", True),
        ("cuidador", "observador", True),
        ("cuidador", None, True),
        ("admin", None, True),
        ("admin", "cuidador", False),
        ("cuidador", "admin", False),
        ("pagador", "observador", False),
        ("pagador", None, False),
        ("observador", "cuidador", False),
    ],
)
def test_se_cortan_los_enlaces_al_dejar_de_compartir(antes: str, despues: str | None, corta: bool) -> None:
    assert deja_de_compartir(antes, despues) is corta


def test_quien_deja_de_administrar() -> None:
    assert deja_de_ser_admin("admin", "cuidador") and deja_de_ser_admin("admin", None)
    assert not deja_de_ser_admin("admin", "admin") and not deja_de_ser_admin("cuidador", None)


def test_el_grupo_nunca_queda_sin_admin() -> None:
    assert deja_sin_admin("admin", "cuidador", admins_activos=1)
    assert not deja_sin_admin("admin", "cuidador", admins_activos=2)
    assert not deja_sin_admin("cuidador", "observador", admins_activos=1)


@pytest.mark.parametrize(
    ("rol", "admins", "miembros", "esperado"),
    [
        ("admin", 1, 1, NoPuedeSalir.UNICA_PERSONA),
        ("admin", 1, 3, NoPuedeSalir.ULTIMO_ADMIN),
        ("admin", 2, 3, None),
        ("cuidador", 1, 3, None),
        ("observador", 1, 2, None),
    ],
)
def test_quien_no_puede_salir(rol: str, admins: int, miembros: int, esperado: NoPuedeSalir | None) -> None:
    assert no_puede_salir(rol, admins, miembros) is esperado


def test_el_permiso_solo_se_ve_en_el_pagador() -> None:
    assert permiso_visible("pagador", True) is True and permiso_visible("pagador", False) is False
    assert permiso_visible("admin", False) is None and permiso_visible("observador", False) is None


def test_los_enlaces_los_ve_quien_administra_y_cada_cual_en_su_fila() -> None:
    assert ve_enlaces(True, False) and ve_enlaces(False, True) and not ve_enlaces(False, False)
