"""MATU-19 · Reglas y casos de uso de abrir la ficha como relevo, sin base ni Redis (RF-06).

Los puertos son dobles: un acceso en memoria, RegistroAuditoriaEnMemoria, SesionesRelevoEnMemoria y
RelojFijo. Solo datos sintéticos.
"""

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.care_plan.application.canje_relevo import (
    AccesoBloqueadoAhora,
    PinIncorrecto,
    PinNoVerificable,
    RelevoBloqueado,
    RelevoNoDisponible,
    SesionCreada,
    TipoNoDisponible,
    canjear,
    presentar,
    verificar_indice,
)
from app.modules.care_plan.application.ficha_relevo import leer_ficha_relevo
from app.modules.care_plan.application.ports import AccesoDelRelevo, EntradaIndice
from app.modules.care_plan.domain.cifrado import SeccionCifrada
from app.modules.care_plan.domain.relevo import (
    MAX_AGE_SESION,
    campos_para_relevo,
    intento_fallido,
    segundos_de_sesion,
)
from app.modules.care_plan.infrastructure.credenciales_relevo import HuellasHmac
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria
from tests.dobles.registro_auditoria_en_memoria import RegistroAuditoriaEnMemoria
from tests.dobles.reloj_fijo import RelojFijo
from tests.dobles.sesiones_relevo_en_memoria import SesionesRelevoEnMemoria

pytestmark = pytest.mark.rf("RF-06")

AHORA = datetime(2026, 10, 30, 18, 0, tzinfo=UTC)
PEPPER = b"p" * 32
HUELLAS = HuellasHmac(PEPPER)


class AccesoEnMemoria:
    def __init__(self, acceso: AccesoDelRelevo | None, vigente: bool = True) -> None:
        self.acceso = acceso
        self.vigente = vigente
        self.usos: list[datetime] = []

    def leer(self) -> AccesoDelRelevo | None:
        return self.acceso

    def autorizacion_vigente(self, ahora: datetime) -> bool:
        return self.vigente

    def fijar_intentos(self, intentos: int) -> None:
        assert self.acceso is not None
        self.acceso = replace(self.acceso, pin_intentos_fallidos=intentos)

    def registrar_uso(self, ahora: datetime) -> None:
        self.usos.append(ahora)


def _acceso(intentos: int = 0, expira_en: datetime = AHORA + timedelta(days=1), **cambios: object) -> AccesoDelRelevo:
    acceso_id = uuid.uuid4()
    base = AccesoDelRelevo(
        id=acceso_id, grupo_id=uuid.uuid4(), plan_id=uuid.uuid4(), campos=("rutina", "manejo_situaciones"),
        nombre_pila_persona="María", nombre_pila_comparte="Carmen",
        pin_hash=HUELLAS.huella_pin(acceso_id, "4821"), pin_intentos_fallidos=intentos, expira_en=expira_en,
    )
    return replace(base, **cambios)  # type: ignore[arg-type]


@pytest.fixture
def reloj() -> RelojFijo:
    return RelojFijo(AHORA)


# --- Reglas puras ------------------------------------------------------------------------------------


def test_max_age_es_el_menor_entre_12_horas_y_lo_que_queda() -> None:
    assert segundos_de_sesion(AHORA + timedelta(days=3), AHORA) == MAX_AGE_SESION == 43_200
    assert segundos_de_sesion(AHORA + timedelta(hours=2, seconds=30), AHORA) == 7_230
    assert segundos_de_sesion(AHORA, AHORA) == 0
    assert segundos_de_sesion(AHORA - timedelta(hours=1), AHORA) == 0


def test_quinto_intento_bloquea() -> None:
    assert intento_fallido(0) == intento_fallido(0).__class__(intentos=1, bloqueado=False, restantes=4)
    assert intento_fallido(3).restantes == 1 and not intento_fallido(3).bloqueado
    assert intento_fallido(4).bloqueado and intento_fallido(4).intentos == 5
    assert intento_fallido(5).intentos == 5  # nunca pasa de 5 (CHECK de la base)


def test_solo_campos_habilitados_y_vacio_es_null() -> None:
    textos = {"rutina": "08:00 Desayuno", "manejo_situaciones": "", "red_apoyo": "Hija: Carmen"}
    assert campos_para_relevo(("manejo_situaciones", "rutina"), textos) == {
        "rutina": "08:00 Desayuno",
        "manejo_situaciones": None,
    }
    assert campos_para_relevo(("red_apoyo",), {}) == {"red_apoyo": None}


@pytest.mark.parametrize(
    ("entrada", "tipo"),
    [
        (None, TipoNoDisponible.NO_DISPONIBLE),
        (EntradaIndice(uuid.uuid4(), AHORA + timedelta(hours=1), AHORA), TipoNoDisponible.REVOCADO),
        (EntradaIndice(uuid.uuid4(), AHORA, None), TipoNoDisponible.VENCIDO),
        # Revocado manda sobre vencido, igual que estado_acceso
        (EntradaIndice(uuid.uuid4(), AHORA - timedelta(days=1), AHORA), TipoNoDisponible.REVOCADO),
    ],
)
def test_indice_decide_revocado_vencido_o_no_disponible(entrada: EntradaIndice | None, tipo: TipoNoDisponible) -> None:
    with pytest.raises(RelevoNoDisponible) as error:
        verificar_indice(entrada, AHORA)
    assert error.value.tipo is tipo


def test_indice_vigente_devuelve_el_acceso() -> None:
    entrada = EntradaIndice(uuid.uuid4(), AHORA + timedelta(seconds=1), None)
    assert verificar_indice(entrada, AHORA) == entrada.acceso_id


# --- Presentación ------------------------------------------------------------------------------------


def test_presentar_da_los_dos_nombres_y_audita(reloj: RelojFijo) -> None:
    acceso = _acceso()
    registro = RegistroAuditoriaEnMemoria()
    vista = presentar(AccesoEnMemoria(acceso), registro, reloj, "rid")
    assert (vista.nombre_pila_comparte, vista.nombre_pila) == ("Carmen", "María")
    [entrada] = registro.entradas
    assert entrada.accion is AccionAuditoria.RELEVO_PRESENTAR
    assert (entrada.actor_tipo, entrada.actor_ref, entrada.grupo_id) == (ActorTipo.RELEVO, acceso.id, acceso.grupo_id)
    assert entrada.motivo is None


@pytest.mark.parametrize(
    ("repo", "error"),
    [
        (AccesoEnMemoria(None), RelevoNoDisponible),                      # C5: RLS no lo muestra
        (AccesoEnMemoria(_acceso(intentos=5)), RelevoBloqueado),
        (AccesoEnMemoria(_acceso(), vigente=False), RelevoNoDisponible),  # decisión 33
    ],
)
def test_presentar_rechaza_sin_auditar(reloj: RelojFijo, repo: AccesoEnMemoria, error: type[Exception]) -> None:
    registro = RegistroAuditoriaEnMemoria()
    with pytest.raises(error):
        presentar(repo, registro, reloj, None)
    assert registro.entradas == ()


def test_bloqueo_se_evalua_antes_que_la_autorizacion(reloj: RelojFijo) -> None:
    with pytest.raises(RelevoBloqueado):
        presentar(AccesoEnMemoria(_acceso(intentos=5), vigente=False), RegistroAuditoriaEnMemoria(), reloj, None)


def test_relevo_pausado_no_dice_el_motivo(reloj: RelojFijo) -> None:
    with pytest.raises(RelevoNoDisponible) as error:
        presentar(AccesoEnMemoria(_acceso(), vigente=False), RegistroAuditoriaEnMemoria(), reloj, None)
    assert error.value.tipo is TipoNoDisponible.PAUSADO


# --- Canje -------------------------------------------------------------------------------------------


def test_canje_correcto_crea_sesion_y_reinicia_el_contador(reloj: RelojFijo) -> None:
    repo = AccesoEnMemoria(_acceso(intentos=2, expira_en=AHORA + timedelta(hours=3)))
    registro, sesiones = RegistroAuditoriaEnMemoria(), SesionesRelevoEnMemoria(reloj)
    resultado = canjear("4821", repo, HUELLAS, registro, sesiones, reloj, None)
    assert isinstance(resultado, SesionCreada)
    assert resultado.max_age == 3 * 3600 and sesiones.ttls == [3 * 3600]
    assert len(resultado.sesion_id) >= 43  # 256 bits en base64url
    assert resultado.sesion_id not in repr(resultado)
    assert repo.acceso is not None and repo.acceso.pin_intentos_fallidos == 0
    assert sesiones.acceso_de(resultado.sesion_id) == repo.acceso.id
    # Redis guarda la huella del id, nunca el id
    assert resultado.sesion_id not in sesiones.guardadas
    assert [e.accion for e in registro.entradas] == [AccionAuditoria.RELEVO_CANJE]


def test_pin_incorrecto_cuenta_y_audita_sin_crear_sesion(reloj: RelojFijo) -> None:
    repo = AccesoEnMemoria(_acceso())
    registro, sesiones = RegistroAuditoriaEnMemoria(), SesionesRelevoEnMemoria(reloj)
    resultado = canjear("0000", repo, HUELLAS, registro, sesiones, reloj, None)
    assert resultado == PinIncorrecto(restantes=4)
    assert repo.acceso is not None and repo.acceso.pin_intentos_fallidos == 1
    assert [e.accion for e in registro.entradas] == [AccionAuditoria.RELEVO_PIN_INCORRECTO]
    assert sesiones.guardadas == {}


def test_quinto_pin_incorrecto_bloquea_y_audita_el_bloqueo(reloj: RelojFijo) -> None:
    repo = AccesoEnMemoria(_acceso(intentos=4))
    registro = RegistroAuditoriaEnMemoria()
    resultado = canjear("0000", repo, HUELLAS, registro, SesionesRelevoEnMemoria(reloj), reloj, None)
    assert isinstance(resultado, AccesoBloqueadoAhora)
    assert [e.accion for e in registro.entradas] == [AccionAuditoria.RELEVO_PIN_INCORRECTO, AccionAuditoria.RELEVO_BLOQUEO]
    # Bloqueado, ni el PIN correcto abre
    with pytest.raises(RelevoBloqueado):
        canjear("4821", repo, HUELLAS, registro, SesionesRelevoEnMemoria(reloj), reloj, None)


def test_canje_pausado_no_cuenta_intento(reloj: RelojFijo) -> None:
    repo = AccesoEnMemoria(_acceso(), vigente=False)
    with pytest.raises(RelevoNoDisponible):
        canjear("0000", repo, HUELLAS, RegistroAuditoriaEnMemoria(), SesionesRelevoEnMemoria(reloj), reloj, None)
    assert repo.acceso is not None and repo.acceso.pin_intentos_fallidos == 0


def test_canje_sin_pepper_falla_cerrado(reloj: RelojFijo) -> None:
    with pytest.raises(PinNoVerificable):
        canjear("4821", AccesoEnMemoria(_acceso()), None, RegistroAuditoriaEnMemoria(),
                SesionesRelevoEnMemoria(reloj), reloj, None)


# --- Ficha -------------------------------------------------------------------------------------------


class SeccionesEnMemoria:
    def __init__(self, persona: uuid.UUID, tipos: list[str]) -> None:
        self.persona = persona
        self.tipos = tipos

    def persona_del_plan(self, plan_id: uuid.UUID) -> uuid.UUID | None:
        return self.persona

    def secciones(self, plan_id: uuid.UUID) -> list[tuple[str, SeccionCifrada]]:
        return [(t, SeccionCifrada(contenido_cifrado=t.encode(), nonce=b"0" * 12, tag_auth=b"0" * 16, kek_version=1))
                for t in self.tipos]


class CifradorTexto:
    """Doble: 'descifra' devolviendo un texto sintético por tipo; red_apoyo vacío."""

    def cifrar(self, **_: object) -> SeccionCifrada:
        raise AssertionError("el relevo nunca cifra")

    def descifrar(self, *, persona_cuidada_id: uuid.UUID, plan_id: uuid.UUID, tipo: str,
                  seccion: SeccionCifrada) -> str:
        return "" if tipo == "manejo_situaciones" else f"texto de {tipo}"


def test_ficha_del_relevo_solo_campos_habilitados_y_auditada(reloj: RelojFijo) -> None:
    acceso = _acceso()
    repo = AccesoEnMemoria(acceso)
    registro = RegistroAuditoriaEnMemoria()
    secciones = SeccionesEnMemoria(uuid.uuid4(), ["rutina", "manejo_situaciones", "red_apoyo"])
    ficha = leer_ficha_relevo(repo, secciones, CifradorTexto(), registro, reloj, "rid")
    assert ficha.campos == {"rutina": "texto de rutina", "manejo_situaciones": None}
    assert (ficha.nombre_pila, ficha.nombre_pila_comparte, ficha.vence_en) == ("María", "Carmen", acceso.expira_en)
    [entrada] = registro.entradas
    assert (entrada.accion, entrada.entidad, entrada.entidad_id) == (
        AccionAuditoria.RELEVO_ABRIR, EntidadAuditoria.PLAN_CUIDADO, acceso.plan_id)
    assert repo.usos == [AHORA]


def test_ficha_sin_auditoria_no_devuelve_texto(reloj: RelojFijo) -> None:
    registro = RegistroAuditoriaEnMemoria()
    registro.fallar_con(RuntimeError("la base rechazó la fila"))
    repo = AccesoEnMemoria(_acceso())
    with pytest.raises(RuntimeError):
        leer_ficha_relevo(repo, SeccionesEnMemoria(uuid.uuid4(), ["rutina"]), CifradorTexto(), registro, reloj, None)
    assert repo.usos == []


def test_ficha_bloqueada_despues_del_canje(reloj: RelojFijo) -> None:
    with pytest.raises(RelevoBloqueado):
        leer_ficha_relevo(AccesoEnMemoria(_acceso(intentos=5)), SeccionesEnMemoria(uuid.uuid4(), []),
                          CifradorTexto(), RegistroAuditoriaEnMemoria(), reloj, None)
