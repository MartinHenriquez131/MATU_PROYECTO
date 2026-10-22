"""MATU-06 · Reglas puras del grupo familiar y caso de uso con un repositorio en memoria (RF-38)."""

import uuid

import pytest

from app.modules.care_circle.application.grupos import crear_grupo, listar_grupos
from app.modules.care_circle.application.ports import GrupoDelUsuario, NuevoGrupo
from app.modules.care_circle.domain.grupos import (
    LARGO_MAXIMO_NOMBRE,
    ROL_FUNDADOR,
    NombreGrupoInvalido,
    normalizar_nombre,
)


class RepositorioEnMemoria:
    def __init__(self) -> None:
        self.creados: list[NuevoGrupo] = []
        self.listados: list[uuid.UUID] = []

    def crear(self, grupo: NuevoGrupo) -> None:
        self.creados.append(grupo)

    def listar(self, usuario_id: uuid.UUID) -> list[GrupoDelUsuario]:
        self.listados.append(usuario_id)
        return [GrupoDelUsuario(id=g.id, nombre=g.nombre, rol=ROL_FUNDADOR) for g in self.creados]


# --- Dominio -------------------------------------------------------------------------------


@pytest.mark.rf("RF-38")
def test_nombre_sin_espacios_en_los_extremos() -> None:
    assert normalizar_nombre("  Familia Sintética  ") == "Familia Sintética"


@pytest.mark.rf("RF-38")
@pytest.mark.parametrize("nombre", ["F", "F" * LARGO_MAXIMO_NOMBRE, " " + "F" * LARGO_MAXIMO_NOMBRE + " "])
def test_nombre_de_1_a_80_caracteres(nombre: str) -> None:
    assert normalizar_nombre(nombre) == nombre.strip()


@pytest.mark.rf("RF-38")
@pytest.mark.parametrize("nombre", ["", "   ", "\t\n", "F" * (LARGO_MAXIMO_NOMBRE + 1)])
def test_nombre_fuera_de_largo_se_rechaza(nombre: str) -> None:
    with pytest.raises(NombreGrupoInvalido):
        normalizar_nombre(nombre)


@pytest.mark.rf("RF-38")
def test_error_de_nombre_no_lleva_el_nombre() -> None:
    nombre = "Familia Sintética " + "x" * LARGO_MAXIMO_NOMBRE

    with pytest.raises(NombreGrupoInvalido) as error:
        normalizar_nombre(nombre)

    assert "Familia" not in str(error.value)
    assert error.value.args == ("el nombre del grupo debe tener entre 1 y 80 caracteres",)


@pytest.mark.rf("RF-38")
def test_el_fundador_es_admin() -> None:
    assert ROL_FUNDADOR == "admin"


# --- Caso de uso ---------------------------------------------------------------------------


@pytest.mark.rf("RF-38")
def test_crear_grupo_genera_el_id_antes_de_guardar() -> None:
    repositorio = RepositorioEnMemoria()
    usuario = uuid.uuid4()

    creado = crear_grupo(usuario, "  Familia Sintética ", repositorio)

    # El repositorio recibe el id ya generado: no depende de un RETURNING de la base
    assert repositorio.creados == [NuevoGrupo(id=creado.id, nombre="Familia Sintética", creado_por=usuario)]
    assert creado.id.version == 4
    assert creado.nombre == "Familia Sintética"
    assert creado.rol == "admin"


@pytest.mark.rf("RF-38")
def test_crear_grupo_genera_ids_distintos() -> None:
    repositorio = RepositorioEnMemoria()
    usuario = uuid.uuid4()

    primero = crear_grupo(usuario, "Familia Uno", repositorio)
    segundo = crear_grupo(usuario, "Familia Dos", repositorio)

    assert primero.id != segundo.id


@pytest.mark.rf("RF-38")
def test_crear_grupo_con_nombre_invalido_no_guarda() -> None:
    repositorio = RepositorioEnMemoria()

    with pytest.raises(NombreGrupoInvalido):
        crear_grupo(uuid.uuid4(), "   ", repositorio)

    assert repositorio.creados == []


@pytest.mark.rf("RF-38")
def test_listar_grupos_pide_los_del_usuario() -> None:
    repositorio = RepositorioEnMemoria()
    usuario = uuid.uuid4()
    creado = crear_grupo(usuario, "Familia Sintética", repositorio)

    grupos = listar_grupos(usuario, repositorio)

    assert repositorio.listados == [usuario]
    assert grupos == [GrupoDelUsuario(id=creado.id, nombre="Familia Sintética", rol="admin")]
