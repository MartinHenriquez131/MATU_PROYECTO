"""MATU-36 · Casos de uso del perfil de consumo con un repositorio en memoria (RF-10, RF-11). Sin base.

Cubren el orden del PATCH (404, 422, 428, 409, 412), la idempotencia de desactivar y activar, el
borrado y lo que va a la auditoría: solo identificadores, nunca nombre_libre ni cantidades.
"""

import dataclasses
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from app.modules.consumption.application import perfiles
from app.modules.consumption.application.conservacion import conservar
from app.modules.consumption.application.perfiles import (
    DatosPerfil,
    PerfilDuplicado,
    PerfilInactivo,
    PerfilNoEncontrado,
    PeticionConsumo,
    ProductoNoAdmitido,
    UnidadDistinta,
    VersionDesactualizada,
)
from app.modules.consumption.application.ports import Pagina, PerfilLeido, ProductoAdmitido
from app.modules.consumption.domain.perfil import (
    CambiosPerfil,
    CoberturaMaxima,
    FaltaVersion,
    NombreLibreConProducto,
    Perfil,
    UnidadConsumo,
)
from app.shared.auditoria import AccionAuditoria, EntidadAuditoria
from tests.dobles.registro_auditoria_en_memoria import RegistroAuditoriaEnMemoria
from tests.dobles.reloj_fijo import RelojFijo

GRUPO = uuid.UUID("00000000-0000-4000-8000-00000000000a")
PERSONA = uuid.UUID("00000000-0000-4000-8000-0000000001a0")
CARMEN = uuid.UUID("00000000-0000-4000-8000-0000000000a1")
PEDRO = uuid.UUID("00000000-0000-4000-8000-0000000000a2")
PRODUCTO = uuid.UUID("00000000-0000-4000-8000-000000000f01")
RECETA = uuid.UUID("00000000-0000-4000-8000-000000000f02")
NOMBRES = {CARMEN: "Carmen", PEDRO: "Pedro"}
# 15:00 UTC del 31-10 es 12:00 en Santiago: hoy es el 31-10
AHORA = datetime(2026, 10, 31, 15, 0, tzinfo=UTC)


class RepositorioEnMemoria:
    def __init__(self) -> None:
        self.perfiles: dict[uuid.UUID, Perfil] = {}
        self.alertas_descartadas: list[uuid.UUID] = []
        self.productos = {
            PRODUCTO: ProductoAdmitido(id=PRODUCTO, nombre="Pañal", presentacion="x30", unidad=UnidadConsumo.UNIDAD)
        }

    def _leido(self, perfil: Perfil) -> PerfilLeido:
        producto = None if perfil.producto_id is None else self.productos[perfil.producto_id]
        nombre = None if perfil.actualizado_por is None else NOMBRES.get(perfil.actualizado_por)
        return PerfilLeido(perfil=perfil, producto=producto, actualizado_por_nombre=nombre)

    def listar(self, persona_id, activo, despues_de, limite):  # type: ignore[no-untyped-def]
        filas = sorted(
            (p for p in self.perfiles.values() if p.persona_cuidada_id == persona_id and activo in (None, p.activo)),
            key=lambda p: (p.fecha_quiebre_estimada, p.id),
        )
        if despues_de is not None:
            filas = [p for p in filas if (p.fecha_quiebre_estimada, p.id) > despues_de]
        pagina = filas[:limite]
        siguiente = (pagina[-1].fecha_quiebre_estimada, pagina[-1].id) if len(filas) > limite else None
        return Pagina(items=[self._leido(p) for p in pagina], siguiente=siguiente)

    def obtener(self, persona_id, perfil_id, *, para_escribir=False):  # type: ignore[no-untyped-def]
        perfil = self.perfiles.get(perfil_id)
        if perfil is None or perfil.persona_cuidada_id != persona_id:
            return None
        return self._leido(perfil)

    def producto_admitido(self, producto_id):  # type: ignore[no-untyped-def]
        return self.productos.get(producto_id)

    def hay_activo_del_producto(self, persona_id, producto_id, salvo):  # type: ignore[no-untyped-def]
        return any(
            p.persona_cuidada_id == persona_id and p.producto_id == producto_id and p.activo and p.id != salvo
            for p in self.perfiles.values()
        )

    def insertar(self, grupo_id, perfil):  # type: ignore[no-untyped-def]
        self.perfiles[perfil.id] = perfil

    def actualizar(self, perfil):  # type: ignore[no-untyped-def]
        assert self.perfiles[perfil.id].version == perfil.version - 1
        self.perfiles[perfil.id] = perfil

    def descartar_alertas_abiertas(self, perfil_id, ahora):  # type: ignore[no-untyped-def]
        self.alertas_descartadas.append(perfil_id)

    def eliminar(self, perfil_id):  # type: ignore[no-untyped-def]
        del self.perfiles[perfil_id]


@pytest.fixture
def repo() -> RepositorioEnMemoria:
    return RepositorioEnMemoria()


@pytest.fixture
def auditoria() -> RegistroAuditoriaEnMemoria:
    return RegistroAuditoriaEnMemoria()


@pytest.fixture
def reloj() -> RelojFijo:
    return RelojFijo(AHORA)


def _peticion(usuario: uuid.UUID = CARMEN) -> PeticionConsumo:
    return PeticionConsumo(grupo_id=GRUPO, usuario_id=usuario, persona_id=PERSONA, request_id="r-1")


def _datos(**cambios: object) -> DatosPerfil:
    base = DatosPerfil(
        producto_id=None, nombre_libre="Pañal adulto M", unidad=None, tasa_unidades=4, tasa_dias=1,
        stock_unidades=24, dias_aviso=7,
    )
    return dataclasses.replace(base, **cambios)  # type: ignore[arg-type]


def _crear(repo, reloj, auditoria, **cambios):  # type: ignore[no-untyped-def]
    return perfiles.crear(_peticion(), _datos(**cambios), reloj, repo, auditoria)


@pytest.mark.rf("RF-11")
def test_crear_calcula_la_fecha_con_hoy_del_reloj(repo, reloj, auditoria) -> None:  # type: ignore[no-untyped-def]
    creado = _crear(repo, reloj, auditoria)
    assert creado.perfil.stock_medido_en == date(2026, 10, 31)
    assert creado.perfil.fecha_quiebre_estimada == date(2026, 11, 6)
    assert creado.perfil.unidad is UnidadConsumo.UNIDAD and creado.perfil.version == 1
    [entrada] = auditoria.entradas
    assert entrada.accion is AccionAuditoria.CONSUMO_CREAR
    assert entrada.entidad is EntidadAuditoria.PERFIL_CONSUMO and entrada.entidad_id == creado.perfil.id
    # Solo identificadores: ni el nombre ni las cantidades
    assert "Pañal" not in repr(entrada) and entrada.motivo is None and entrada.detalle() is None


@pytest.mark.rf("RF-10")
def test_crear_con_producto_usa_su_unidad_y_rechaza_receta_unidad_y_duplicado(repo, reloj, auditoria) -> None:  # type: ignore[no-untyped-def]
    creado = _crear(repo, reloj, auditoria, producto_id=PRODUCTO, nombre_libre=None)
    assert creado.producto is not None and creado.perfil.unidad is UnidadConsumo.UNIDAD
    with pytest.raises(ProductoNoAdmitido):
        _crear(repo, reloj, auditoria, producto_id=RECETA, nombre_libre=None)
    with pytest.raises(UnidadDistinta):
        _crear(repo, reloj, auditoria, producto_id=PRODUCTO, nombre_libre=None, unidad=UnidadConsumo.ML)
    with pytest.raises(PerfilDuplicado):
        _crear(repo, reloj, auditoria, producto_id=PRODUCTO, nombre_libre=None)
    with pytest.raises(CoberturaMaxima):
        _crear(repo, reloj, auditoria, stock_unidades=100_000, tasa_unidades=1, tasa_dias=90)
    assert len(auditoria.entradas) == 1


@pytest.mark.rf("RF-10")
def test_editar_con_if_match_actual_reancla_y_audita(repo, reloj, auditoria) -> None:  # type: ignore[no-untyped-def]
    creado = _crear(repo, reloj, auditoria)
    reloj.avanzar(timedelta(days=2))
    editado = perfiles.editar(
        _peticion(PEDRO), creado.perfil.id, CambiosPerfil(stock_unidades=20), '"v1"', reloj, repo, auditoria
    )
    assert isinstance(editado, PerfilLeido)
    assert editado.perfil.version == 2 and editado.perfil.stock_medido_en == date(2026, 11, 2)
    assert editado.perfil.fecha_quiebre_estimada == date(2026, 11, 7)
    assert editado.actualizado_por_nombre == "Pedro"
    assert auditoria.entradas[-1].accion is AccionAuditoria.CONSUMO_EDITAR


@pytest.mark.rf("RF-10")
def test_editar_con_if_match_viejo_devuelve_el_actual_con_quien_guardo(repo, reloj, auditoria) -> None:  # type: ignore[no-untyped-def]
    creado = _crear(repo, reloj, auditoria)
    cambios = CambiosPerfil(stock_unidades=18)
    perfiles.editar(_peticion(PEDRO), creado.perfil.id, cambios, '"v1"', reloj, repo, auditoria)
    conflicto = perfiles.editar(
        _peticion(), creado.perfil.id, CambiosPerfil(stock_unidades=20), '"v1"', reloj, repo, auditoria
    )
    assert isinstance(conflicto, VersionDesactualizada)
    assert conflicto.actual.perfil.version == 2 and conflicto.actual.perfil.stock_unidades == 18
    assert conflicto.actual.actualizado_por_nombre == "Pedro"
    # El 412 no escribe ni audita
    assert [e.accion for e in auditoria.entradas] == [AccionAuditoria.CONSUMO_CREAR, AccionAuditoria.CONSUMO_EDITAR]


@pytest.mark.rf("RF-10")
@pytest.mark.parametrize("if_match", [None, "", "*"])
def test_editar_sin_if_match_es_428(repo, reloj, auditoria, if_match) -> None:  # type: ignore[no-untyped-def]
    creado = _crear(repo, reloj, auditoria)
    with pytest.raises(FaltaVersion):
        perfiles.editar(_peticion(), creado.perfil.id, CambiosPerfil(dias_aviso=3), if_match, reloj, repo, auditoria)


@pytest.mark.rf("RF-10")
def test_orden_del_patch_404_422_428_409_412(repo, reloj, auditoria) -> None:  # type: ignore[no-untyped-def]
    de_producto = _crear(repo, reloj, auditoria, producto_id=PRODUCTO, nombre_libre=None)
    libre = _crear(repo, reloj, auditoria)
    with pytest.raises(PerfilNoEncontrado):
        perfiles.editar(_peticion(), uuid.uuid4(), CambiosPerfil(dias_aviso=1), None, reloj, repo, auditoria)
    # 422 antes que 428
    with pytest.raises(NombreLibreConProducto):
        perfiles.editar(
            _peticion(), de_producto.perfil.id, CambiosPerfil(nombre_libre="X"), None, reloj, repo, auditoria
        )
    perfiles.desactivar(_peticion(), libre.perfil.id, reloj, repo, auditoria)
    # 428 antes que 409, y 409 antes que 412 (con un If-Match viejo o actual)
    with pytest.raises(FaltaVersion):
        perfiles.editar(_peticion(), libre.perfil.id, CambiosPerfil(dias_aviso=1), "*", reloj, repo, auditoria)
    for valor in ('"v1"', '"v2"'):
        with pytest.raises(PerfilInactivo):
            perfiles.editar(_peticion(), libre.perfil.id, CambiosPerfil(dias_aviso=1), valor, reloj, repo, auditoria)


@pytest.mark.rf("RF-10")
def test_desactivar_y_activar_son_idempotentes_y_se_auditan_una_vez(repo, reloj, auditoria) -> None:  # type: ignore[no-untyped-def]
    creado = _crear(repo, reloj, auditoria)
    uno = perfiles.desactivar(_peticion(), creado.perfil.id, reloj, repo, auditoria)
    dos = perfiles.desactivar(_peticion(), creado.perfil.id, reloj, repo, auditoria)
    assert not uno.perfil.activo and uno.perfil.version == 2 and dos.perfil.version == 2
    assert repo.alertas_descartadas == [creado.perfil.id]
    activo = perfiles.activar(_peticion(), creado.perfil.id, repo, auditoria)
    perfiles.activar(_peticion(), creado.perfil.id, repo, auditoria)
    assert activo.perfil.activo and activo.perfil.version == 3
    assert activo.perfil.fecha_quiebre_estimada == creado.perfil.fecha_quiebre_estimada
    assert [e.accion for e in auditoria.entradas] == [
        AccionAuditoria.CONSUMO_CREAR, AccionAuditoria.CONSUMO_DESACTIVAR, AccionAuditoria.CONSUMO_ACTIVAR,
    ]


@pytest.mark.rf("RF-10")
def test_activar_un_producto_que_ya_se_sigue_es_409(repo, reloj, auditoria) -> None:  # type: ignore[no-untyped-def]
    viejo = _crear(repo, reloj, auditoria, producto_id=PRODUCTO, nombre_libre=None)
    perfiles.desactivar(_peticion(), viejo.perfil.id, reloj, repo, auditoria)
    _crear(repo, reloj, auditoria, producto_id=PRODUCTO, nombre_libre=None)
    with pytest.raises(PerfilDuplicado):
        perfiles.activar(_peticion(), viejo.perfil.id, repo, auditoria)


@pytest.mark.rf("RF-10")
def test_eliminar_borra_y_audita(repo, reloj, auditoria) -> None:  # type: ignore[no-untyped-def]
    creado = _crear(repo, reloj, auditoria)
    perfiles.eliminar(_peticion(), creado.perfil.id, repo, auditoria)
    assert creado.perfil.id not in repo.perfiles
    assert auditoria.entradas[-1].accion is AccionAuditoria.CONSUMO_ELIMINAR
    with pytest.raises(PerfilNoEncontrado):
        perfiles.eliminar(_peticion(), creado.perfil.id, repo, auditoria)


@pytest.mark.rf("RF-11")
def test_listar_ordena_por_fecha_y_pagina(repo, reloj, auditoria) -> None:  # type: ignore[no-untyped-def]
    for stock in (40, 8, 24):
        _crear(repo, reloj, auditoria, stock_unidades=stock)
    pagina = perfiles.listar(_peticion(), True, None, 2, repo)
    assert [i.perfil.stock_unidades for i in pagina.items] == [8, 24]
    resto = perfiles.listar(_peticion(), True, pagina.siguiente, 2, repo)
    assert [i.perfil.stock_unidades for i in resto.items] == [40] and resto.siguiente is None


@pytest.mark.rf("RF-10")
def test_conservacion_usa_el_limite_de_90_dias_del_reloj(reloj) -> None:  # type: ignore[no-untyped-def]
    llamadas: list[tuple[datetime, datetime]] = []

    class Unidad:
        def conservar(self, limite: datetime, ahora: datetime) -> int:
            llamadas.append((limite, ahora))
            return 3

    assert conservar(unidad=Unidad(), reloj=reloj).perfiles_borrados == 3
    assert llamadas == [(AHORA - timedelta(days=90), AHORA)]
