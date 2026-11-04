"""MATU-37 · Casos de uso de alertas y trabajo diario con repositorios en memoria (RF-12). Sin base.

Cubren: sin autorización vigente no se materializa ni se avisa; el evento lleva solo identificadores;
una corrida doble no duplica; «Ya lo resolví» sin alerta previa la crea ya descartada; con cantidad
todavía no; y la auditoría lleva solo identificadores.
"""

import dataclasses
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from app.modules.care_circle.domain.personas import AutorizacionGuardada
from app.modules.consumption.application import alertas
from app.modules.consumption.application.alertas import AlertaNoEncontrada
from app.modules.consumption.application.conservacion import conservar_quiebres
from app.modules.consumption.application.perfiles import (
    PerfilInactivo,
    PerfilNoEncontrado,
    PeticionConsumo,
    VersionDesactualizada,
)
from app.modules.consumption.application.ports import (
    AlertaLeida,
    InsumoDelTrabajo,
    InsumoEnVentana,
    PaginaAlertas,
    PerfilLeido,
)
from app.modules.consumption.application.trabajo_diario import recalcular_quiebres
from app.modules.consumption.domain.alerta import AlertaCerrada, EstadoAlerta
from app.modules.consumption.domain.perfil import FaltaVersion, Perfil, UnidadConsumo
from app.modules.consumption.events import QuiebreProximo
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria
from tests.dobles.registro_auditoria_en_memoria import RegistroAuditoriaEnMemoria
from tests.dobles.reloj_fijo import RelojFijo

pytestmark = pytest.mark.rf("RF-12")

GRUPO = uuid.UUID("00000000-0000-4000-8000-00000000000a")
PERSONA = uuid.UUID("00000000-0000-4000-8000-0000000001a0")
CARMEN = uuid.UUID("00000000-0000-4000-8000-0000000000a1")
# 15:00 UTC es 12:00 en Santiago: hoy es el 03-11
AHORA = datetime(2026, 11, 3, 15, 0, tzinfo=UTC)
HOY = date(2026, 11, 3)


# --- Trabajo diario -------------------------------------------------------------------------------------


class QuiebresEnMemoria:
    def __init__(self, insumos: list[InsumoDelTrabajo], abiertas: list[AlertaLeida] | None = None) -> None:
        self._insumos = insumos
        self._abiertas = abiertas or []
        self.claves: set[tuple[uuid.UUID, date]] = {
            (i.perfil_id, i.fecha_quiebre_estimada) for i in insumos if i.hay_alerta_de_la_fecha
        }
        self.materializadas: list[uuid.UUID] = []
        self.descartadas: list[uuid.UUID] = []
        self.eventos: list[QuiebreProximo] = []

    def insumos(self) -> list[InsumoDelTrabajo]:
        return self._insumos

    def abiertas(self) -> list[AlertaLeida]:
        return self._abiertas

    def materializar(self, alerta_id: uuid.UUID, perfil_id: uuid.UUID, fecha: date, ahora: datetime) -> bool:
        if (perfil_id, fecha) in self.claves:
            return False
        self.claves.add((perfil_id, fecha))
        self.materializadas.append(alerta_id)
        return True

    def descartar(self, alerta_id: uuid.UUID, ahora: datetime) -> None:
        self.descartadas.append(alerta_id)

    def publicar(self, evento: QuiebreProximo, ahora: datetime) -> None:
        self.eventos.append(evento)


def _insumo(autorizacion: AutorizacionGuardada | None, dias: int = 3) -> InsumoDelTrabajo:
    return InsumoDelTrabajo(
        perfil_id=uuid.uuid4(),
        persona_cuidada_id=PERSONA,
        fecha_quiebre_estimada=HOY + timedelta(days=dias),
        dias_aviso=7,
        autorizacion=autorizacion,
        hay_alerta_de_la_fecha=False,
    )


TITULAR = AutorizacionGuardada(calidad_otorgante="titular", revision_vence_en=None)
REVISION_VENCIDA = AutorizacionGuardada(calidad_otorgante="cuidador_de_hecho", revision_vence_en=AHORA)


def test_materializa_publica_solo_identificadores_y_audita_como_sistema() -> None:
    insumo = _insumo(TITULAR)
    repo = QuiebresEnMemoria([insumo])
    auditoria = RegistroAuditoriaEnMemoria()
    resultado = recalcular_quiebres(GRUPO, repo, auditoria, RelojFijo(AHORA))
    assert resultado.materializadas == 1
    [evento] = repo.eventos
    assert evento.payload() == {
        "alerta_id": str(repo.materializadas[0]),
        "perfil_id": str(insumo.perfil_id),
        "persona_cuidada_id": str(PERSONA),
    }
    [entrada] = auditoria.entradas
    assert (entrada.accion, entrada.actor_tipo, entrada.actor_ref) == (
        AccionAuditoria.ALERTA_MATERIALIZAR,
        ActorTipo.SISTEMA,
        None,
    )
    assert entrada.entidad is EntidadAuditoria.ALERTA_QUIEBRE and entrada.detalle() is None


@pytest.mark.parametrize("autorizacion", [None, REVISION_VENCIDA], ids=["sin-consentimiento", "revision-vencida"])
def test_sin_autorizacion_vigente_no_materializa_ni_avisa(autorizacion: AutorizacionGuardada | None) -> None:
    repo = QuiebresEnMemoria([_insumo(autorizacion)])
    auditoria = RegistroAuditoriaEnMemoria()
    resultado = recalcular_quiebres(GRUPO, repo, auditoria, RelojFijo(AHORA))
    assert (resultado.materializadas, repo.eventos, auditoria.entradas) == (0, [], ())


def test_una_corrida_doble_no_duplica() -> None:
    repo = QuiebresEnMemoria([_insumo(TITULAR)])
    reloj = RelojFijo(AHORA)
    recalcular_quiebres(GRUPO, repo, RegistroAuditoriaEnMemoria(), reloj)
    segunda = recalcular_quiebres(GRUPO, repo, RegistroAuditoriaEnMemoria(), reloj)
    assert segunda.materializadas == 0 and len(repo.eventos) == 1


def test_fuera_de_la_ventana_no_materializa() -> None:
    repo = QuiebresEnMemoria([_insumo(TITULAR, dias=8)])
    assert recalcular_quiebres(GRUPO, repo, RegistroAuditoriaEnMemoria(), RelojFijo(AHORA)).materializadas == 0


def test_descarta_la_alerta_de_una_fecha_vieja() -> None:
    insumo = _insumo(TITULAR)
    vieja = AlertaLeida(uuid.uuid4(), insumo.perfil_id, HOY, EstadoAlerta.PENDIENTE, AHORA, None, None)
    repo = QuiebresEnMemoria([insumo], [vieja])
    auditoria = RegistroAuditoriaEnMemoria()
    resultado = recalcular_quiebres(GRUPO, repo, auditoria, RelojFijo(AHORA))
    assert (resultado.descartadas, resultado.materializadas, repo.descartadas) == (1, 1, [vieja.id])
    assert [e.accion for e in auditoria.entradas] == [
        AccionAuditoria.ALERTA_DESCARTAR,
        AccionAuditoria.ALERTA_MATERIALIZAR,
    ]


class ConservacionEnMemoria:
    def __init__(self) -> None:
        self.llamada: tuple[datetime, datetime, datetime] | None = None

    def conservar(self, limite_alertas: datetime, limite_eventos: datetime, ahora: datetime) -> tuple[int, int, int]:
        self.llamada = (limite_alertas, limite_eventos, ahora)
        return (2, 3, 4)


def test_conservacion_con_90_y_30_dias() -> None:
    unidad = ConservacionEnMemoria()
    resultado = conservar_quiebres(unidad=unidad, reloj=RelojFijo(AHORA))
    assert unidad.llamada == (AHORA - timedelta(days=90), AHORA - timedelta(days=30), AHORA)
    assert (resultado.alertas_borradas, resultado.eventos_borrados, resultado.notificaciones_borradas) == (2, 3, 4)


# --- Descartar y «Ya lo resolví» -----------------------------------------------------------------------


def _perfil(activo: bool = True) -> PerfilLeido:
    return PerfilLeido(
        perfil=Perfil(
            id=uuid.uuid4(),
            persona_cuidada_id=PERSONA,
            producto_id=None,
            nombre_libre="Pañal adulto M",
            unidad=UnidadConsumo.UNIDAD,
            tasa_unidades=4,
            tasa_dias=1,
            stock_unidades=12,
            stock_medido_en=HOY,
            dias_aviso=7,
            fecha_quiebre_estimada=HOY + timedelta(days=3),
            activo=activo,
            version=1,
            actualizado_por=CARMEN,
        ),
        producto=None,
        actualizado_por_nombre="Carmen",
    )


class PerfilesEnMemoria:
    def __init__(self, leido: PerfilLeido | None) -> None:
        self.leido = leido

    def obtener(
        self, persona_id: uuid.UUID, perfil_id: uuid.UUID, *, para_escribir: bool = False
    ) -> PerfilLeido | None:
        return self.leido if self.leido is not None and self.leido.perfil.id == perfil_id else None

    def actualizar(self, perfil: Perfil) -> None:
        assert self.leido is not None and perfil.version == self.leido.perfil.version + 1
        self.leido = dataclasses.replace(self.leido, perfil=perfil)


class AlertasEnMemoria:
    def __init__(self) -> None:
        self.filas: dict[uuid.UUID, AlertaLeida] = {}
        self.reposiciones: list[tuple[uuid.UUID, uuid.UUID, int, date, uuid.UUID]] = []

    def agregar(self, perfil_id: uuid.UUID, fecha: date, estado: EstadoAlerta) -> AlertaLeida:
        a = AlertaLeida(uuid.uuid4(), perfil_id, fecha, estado, AHORA, None, None)
        self.filas[a.id] = a
        return a

    def en_ventana(self, persona_id: uuid.UUID, hoy: date) -> list[InsumoEnVentana]:
        raise NotImplementedError

    def listar(
        self, persona_id: uuid.UUID, estados: frozenset[EstadoAlerta], despues_de: object, limite: int
    ) -> PaginaAlertas:
        raise NotImplementedError

    def obtener(self, persona_id: uuid.UUID, alerta_id: uuid.UUID) -> AlertaLeida | None:
        return self.filas.get(alerta_id)

    def declarar_reposicion(
        self, reposicion_id: uuid.UUID, perfil_id: uuid.UUID, cantidad: int, ocurrida_en: date, usuario_id: uuid.UUID
    ) -> None:
        self.reposiciones.append((reposicion_id, perfil_id, cantidad, ocurrida_en, usuario_id))

    def de_la_fecha(self, perfil_id: uuid.UUID, fecha: date) -> AlertaLeida | None:
        return next((a for a in self.filas.values() if (a.perfil_id, a.fecha_prevista) == (perfil_id, fecha)), None)

    def cerrar(self, alerta_id: uuid.UUID, estado: EstadoAlerta, ahora: datetime) -> AlertaLeida:
        a = self.filas[alerta_id]
        nueva = AlertaLeida(a.id, a.perfil_id, a.fecha_prevista, estado, a.creada_en, a.notificada_en, ahora)
        self.filas[a.id] = nueva
        return nueva

    def insertar_cerrada(
        self, alerta_id: uuid.UUID, perfil_id: uuid.UUID, fecha: date, estado: EstadoAlerta, ahora: datetime
    ) -> AlertaLeida:
        a = AlertaLeida(alerta_id, perfil_id, fecha, estado, ahora, None, ahora)
        self.filas[a.id] = a
        return a


PETICION = PeticionConsumo(grupo_id=GRUPO, usuario_id=CARMEN, persona_id=PERSONA, request_id="r-1")


def _resolver(leido: PerfilLeido | None, repo: AlertasEnMemoria, cantidad: int | None = None, perfil_id=None):  # type: ignore[no-untyped-def]
    auditoria = RegistroAuditoriaEnMemoria()
    objetivo = perfil_id or (leido.perfil.id if leido else uuid.uuid4())
    resultado = alertas.resolver(
        PETICION,
        objetivo,
        cantidad,
        '"v1"',
        RelojFijo(AHORA),
        PerfilesEnMemoria(leido),  # type: ignore[arg-type]
        repo,
        auditoria,
    )
    return resultado, auditoria


def test_resolver_sin_alerta_previa_la_crea_descartada() -> None:
    leido = _perfil()
    repo = AlertasEnMemoria()
    resultado, auditoria = _resolver(leido, repo)
    [alerta] = repo.filas.values()
    assert alerta.estado is EstadoAlerta.DESCARTADA and alerta.fecha_prevista == leido.perfil.fecha_quiebre_estimada
    assert resultado.avisando is False and resultado.alerta_id == alerta.id
    [entrada] = auditoria.entradas
    assert (entrada.accion, entrada.entidad_id, entrada.actor_ref) == (
        AccionAuditoria.ALERTA_DESCARTAR,
        alerta.id,
        CARMEN,
    )


def test_resolver_cierra_la_alerta_abierta_de_la_fecha() -> None:
    leido = _perfil()
    repo = AlertasEnMemoria()
    abierta = repo.agregar(leido.perfil.id, leido.perfil.fecha_quiebre_estimada, EstadoAlerta.NOTIFICADA)
    resultado, _ = _resolver(leido, repo)
    assert repo.filas[abierta.id].estado is EstadoAlerta.DESCARTADA and resultado.alerta_id == abierta.id


def test_resolver_dos_veces_es_409() -> None:
    leido = _perfil()
    repo = AlertasEnMemoria()
    _resolver(leido, repo)
    with pytest.raises(AlertaCerrada):
        _resolver(leido, repo)


def _resolver_con(leido: PerfilLeido, repo: AlertasEnMemoria, cantidad: int | None, if_match: str | None = '"v1"'):  # type: ignore[no-untyped-def]
    perfiles = PerfilesEnMemoria(leido)
    auditoria = RegistroAuditoriaEnMemoria()
    resultado = alertas.resolver(
        PETICION,
        leido.perfil.id,
        cantidad,
        if_match,
        RelojFijo(AHORA),
        perfiles,  # type: ignore[arg-type]
        repo,
        auditoria,
    )
    return resultado, perfiles, auditoria


def _anotado_hace(dias: int) -> PerfilLeido:
    leido = _perfil()
    return dataclasses.replace(
        leido, perfil=dataclasses.replace(leido.perfil, stock_medido_en=HOY - timedelta(days=dias))
    )


def test_resolver_con_cantidad_suma_al_stock_estimado_de_hoy_y_resuelve() -> None:
    # Anotado hace 1 día: 12 - 4 = 8 quedan hoy; + 30 = 38, alcanza 9 días (piso de 38/4)
    leido = _anotado_hace(1)
    repo = AlertasEnMemoria()
    abierta = repo.agregar(leido.perfil.id, leido.perfil.fecha_quiebre_estimada, EstadoAlerta.PENDIENTE)
    resultado, perfiles, auditoria = _resolver_con(leido, repo, 30)
    nuevo = perfiles.leido.perfil
    assert (nuevo.stock_unidades, nuevo.stock_medido_en, nuevo.version) == (38, HOY, 2)
    assert nuevo.fecha_quiebre_estimada == HOY + timedelta(days=9)
    assert repo.filas[abierta.id].estado is EstadoAlerta.RESUELTA and repo.filas[abierta.id].cerrada_en == AHORA
    [(rep_id, perfil_id, cantidad, ocurrida, usuario)] = repo.reposiciones
    assert (perfil_id, cantidad, ocurrida, usuario) == (leido.perfil.id, 30, HOY, CARMEN)
    assert resultado.leido.perfil == nuevo and resultado.avisando is False and resultado.alerta_id is None
    assert [(e.accion, e.entidad_id) for e in auditoria.entradas] == [
        (AccionAuditoria.REPOSICION_DECLARAR, rep_id),
        (AccionAuditoria.ALERTA_RESOLVER, abierta.id),
    ]
    assert all(e.detalle() is None for e in auditoria.entradas)


def test_resolver_con_cantidad_sin_alerta_previa_la_crea_resuelta() -> None:
    leido = _perfil()
    repo = AlertasEnMemoria()
    _resolver_con(leido, repo, 5)
    [alerta] = repo.filas.values()
    assert alerta.estado is EstadoAlerta.RESUELTA and alerta.fecha_prevista == leido.perfil.fecha_quiebre_estimada


def test_resolver_con_cantidad_y_stock_estimado_negativo_parte_de_cero() -> None:
    # Anotado hace 10 días: 12 - 40 es negativo, queda 0; + 30 = 30
    _, perfiles, _ = _resolver_con(_anotado_hace(10), AlertasEnMemoria(), 30)
    assert perfiles.leido is not None and perfiles.leido.perfil.stock_unidades == 30


def test_resolver_con_cantidad_sobre_alerta_cerrada_es_409_y_no_suma() -> None:
    leido = _perfil()
    repo = AlertasEnMemoria()
    repo.agregar(leido.perfil.id, leido.perfil.fecha_quiebre_estimada, EstadoAlerta.DESCARTADA)
    with pytest.raises(AlertaCerrada):
        _resolver_con(leido, repo, 30)
    assert repo.reposiciones == []


def test_resolver_perfil_ajeno_o_inactivo() -> None:
    with pytest.raises(PerfilNoEncontrado):
        _resolver(None, AlertasEnMemoria())
    with pytest.raises(PerfilInactivo):
        _resolver(_perfil(activo=False), AlertasEnMemoria())


def test_descartar_alerta_ajena_o_cerrada() -> None:
    repo = AlertasEnMemoria()
    auditoria = RegistroAuditoriaEnMemoria()
    with pytest.raises(AlertaNoEncontrada):
        alertas.descartar(PETICION, uuid.uuid4(), RelojFijo(AHORA), repo, auditoria)
    cerrada = repo.agregar(uuid.uuid4(), HOY, EstadoAlerta.RESUELTA)
    with pytest.raises(AlertaCerrada):
        alertas.descartar(PETICION, cerrada.id, RelojFijo(AHORA), repo, auditoria)
    abierta = repo.agregar(uuid.uuid4(), HOY, EstadoAlerta.PENDIENTE)
    resultado = alertas.descartar(PETICION, abierta.id, RelojFijo(AHORA), repo, auditoria)
    assert resultado.estado is EstadoAlerta.DESCARTADA and resultado.cerrada_en == AHORA
    assert [e.accion for e in auditoria.entradas] == [AccionAuditoria.ALERTA_DESCARTAR]


# --- Decisión 80: «Ya lo resolví» es condicional ------------------------------------------------------


@pytest.mark.parametrize("if_match", [None, "", "*"])
def test_resolver_sin_if_match_es_428_y_no_toca_nada(if_match: str | None) -> None:
    repo = AlertasEnMemoria()
    with pytest.raises(FaltaVersion):
        _resolver_con(_perfil(), repo, 30, if_match)
    assert repo.filas == {} and repo.reposiciones == []


@pytest.mark.parametrize("cantidad", [30, None])
def test_resolver_con_version_vieja_es_412_y_no_suma_ni_cierra(cantidad: int | None) -> None:
    leido = _perfil()
    repo = AlertasEnMemoria()
    resultado, perfiles, auditoria = _resolver_con(leido, repo, cantidad, '"v7"')
    assert isinstance(resultado, VersionDesactualizada) and resultado.actual == leido
    assert repo.filas == {} and repo.reposiciones == [] and auditoria.entradas == ()
    assert perfiles.leido == leido


def test_dos_resolver_seguidos_con_el_mismo_etag_suman_una_sola_vez() -> None:
    leido = _perfil()
    repo = AlertasEnMemoria()
    primero, perfiles, _ = _resolver_con(leido, repo, 5)
    assert not isinstance(primero, VersionDesactualizada)
    segundo = alertas.resolver(
        PETICION,
        leido.perfil.id,
        5,
        '"v1"',
        RelojFijo(AHORA),
        perfiles,  # type: ignore[arg-type]
        repo,
        RegistroAuditoriaEnMemoria(),
    )
    assert isinstance(segundo, VersionDesactualizada) and len(repo.reposiciones) == 1
