"""MATU-11 · El adaptador CifradorAesGcm del puerto CifradorSecciones, sin base.

Usa la custodia de las fixtures (CustodiaEnMemoria) y el doble RepositorioClavesEnMemoria. Las
pruebas contra PostgreSQL (misma transacción, concurrencia, RLS) están en test_cifrado_integracion.py.

Trazan a ADR-014 y ADR-016 (no hay un RF): sin marca rf. Solo textos sintéticos.
"""

import logging
import secrets
import traceback
import uuid
from collections.abc import Callable
from dataclasses import replace

import pytest

from app.modules.care_plan.application.ports import CifradorSecciones, DekEnvuelta
from app.modules.care_plan.domain.cifrado import (
    LARGO_NONCE,
    LARGO_TAG,
    ClaveDestruida,
    ClaveGuardada,
    ClaveInexistente,
    ClaveNoDisponible,
    ErrorCifrado,
    SeccionCifrada,
    SeccionIlegible,
    TipoSeccionInvalido,
)
from app.modules.care_plan.infrastructure.cifrador_aes_gcm import CifradorAesGcm
from tests.dobles.custodia_en_memoria import CustodiaEnMemoria
from tests.dobles.repositorio_claves_en_memoria import RepositorioClavesEnMemoria

GRUPO = uuid.UUID("00000000-0000-0000-0000-0000000012a0")
PERSONA = uuid.UUID("00000000-0000-0000-0000-0000000012a1")
PLAN = uuid.UUID("00000000-0000-0000-0000-0000000012a2")
OTRO_PLAN = uuid.UUID("00000000-0000-0000-0000-0000000012b2")


def _texto() -> str:
    """Un texto sintético con una marca única, para buscarlo después en logs y errores."""
    return f"Toma desayuno a las 8 y sale a caminar con apoyo · marca {secrets.token_hex(6)}"


class CustodiaEspia(CustodiaEnMemoria):
    """La custodia de las pruebas, que además recuerda cada DEK en claro que envolvió y lo que
    devolvió, para buscarlas en los logs y en los errores."""

    def __init__(self) -> None:
        super().__init__()
        self.deks: list[bytes] = []
        self.envueltas: list[DekEnvuelta] = []

    def envolver(self, dek: bytes) -> DekEnvuelta:
        envuelta = super().envolver(dek)
        self.deks.append(dek)
        self.envueltas.append(envuelta)
        return envuelta


@pytest.fixture
def claves() -> RepositorioClavesEnMemoria:
    return RepositorioClavesEnMemoria()


@pytest.fixture
def cifrador(custodia: CustodiaEnMemoria, claves: RepositorioClavesEnMemoria) -> CifradorAesGcm:
    return CifradorAesGcm(custodia, claves)


def _cifrar(cifrador: CifradorSecciones, texto: str, *, plan: uuid.UUID = PLAN, tipo: str = "rutina") -> SeccionCifrada:
    return cifrador.cifrar(grupo_id=GRUPO, persona_cuidada_id=PERSONA, plan_id=plan, tipo=tipo, texto=texto)


def _descifrar(
    cifrador: CifradorSecciones, seccion: SeccionCifrada, *, plan: uuid.UUID = PLAN, tipo: str = "rutina"
) -> str:
    return cifrador.descifrar(persona_cuidada_id=PERSONA, plan_id=plan, tipo=tipo, seccion=seccion)


def _cambiar_un_byte(datos: bytes) -> bytes:
    return bytes([datos[0] ^ 0x01]) + datos[1:]


# --- Las pruebas que pide el backlog ----------------------------------------------------------------


def test_cifrar_descifrar_ida_y_vuelta(cifrador: CifradorAesGcm) -> None:
    # Dado un texto de cada sección de la ficha de relevo, con tildes y eñes
    textos = {
        "rutina": _texto(),
        "manejo_situaciones": "Si se inquieta, bajar la voz y ofrecerle agua. Música de su época.",
        "red_apoyo": "Hija: +56 9 0000 0000 · Vecina del 2.º piso, señora Ñuñoa",
    }

    # Cuando se cifra y se descifra cada uno
    cifradas = {tipo: _cifrar(cifrador, texto, tipo=tipo) for tipo, texto in textos.items()}
    leidas = {tipo: _descifrar(cifrador, seccion, tipo=tipo) for tipo, seccion in cifradas.items()}

    # Entonces vuelve el mismo texto, y lo guardado no lo contiene en claro
    assert leidas == textos
    for tipo, seccion in cifradas.items():
        assert textos[tipo].encode("utf-8") not in seccion.contenido_cifrado
        assert len(seccion.nonce) == LARGO_NONCE
        assert len(seccion.tag_auth) == LARGO_TAG


def test_texto_vacio_ida_y_vuelta(cifrador: CifradorAesGcm) -> None:
    assert _descifrar(cifrador, _cifrar(cifrador, "")) == ""


def test_nonces_distintos(cifrador: CifradorAesGcm) -> None:
    # Dado el mismo texto escrito muchas veces en la misma sección
    texto = _texto()

    # Cuando se cifra en cada escritura
    secciones = [_cifrar(cifrador, texto) for _ in range(200)]

    # Entonces cada escritura lleva un nonce nuevo de 12 bytes, y el texto cifrado cambia
    assert len({s.nonce for s in secciones}) == len(secciones)
    assert len({s.contenido_cifrado + s.tag_auth for s in secciones}) == len(secciones)
    assert all(len(s.nonce) == LARGO_NONCE for s in secciones)


ALTERACIONES: dict[str, Callable[[SeccionCifrada], SeccionCifrada]] = {
    "contenido_cifrado": lambda s: replace(s, contenido_cifrado=_cambiar_un_byte(s.contenido_cifrado)),
    "tag_auth": lambda s: replace(s, tag_auth=_cambiar_un_byte(s.tag_auth)),
    "nonce": lambda s: replace(s, nonce=_cambiar_un_byte(s.nonce)),
}


@pytest.mark.parametrize("campo", sorted(ALTERACIONES))
def test_texto_alterado_falla(cifrador: CifradorAesGcm, campo: str) -> None:
    # Dada una sección cifrada
    seccion = _cifrar(cifrador, _texto())

    # Cuando alguien con escritura en la base cambia un byte del contenido, del tag o del nonce
    alterada = ALTERACIONES[campo](seccion)

    # Entonces descifrar falla con el error de dominio, sin devolver texto
    with pytest.raises(SeccionIlegible):
        _descifrar(cifrador, alterada)


def test_texto_truncado_falla(cifrador: CifradorAesGcm) -> None:
    seccion = _cifrar(cifrador, _texto())

    with pytest.raises(SeccionIlegible):
        _descifrar(cifrador, replace(seccion, contenido_cifrado=seccion.contenido_cifrado[:-1]))


@pytest.mark.parametrize(
    ("plan", "tipo"),
    [
        pytest.param(PLAN, "manejo_situaciones", id="otra-seccion-del-mismo-plan"),
        pytest.param(PLAN, "red_apoyo", id="otra-seccion-red-apoyo"),
        pytest.param(OTRO_PLAN, "rutina", id="misma-seccion-de-otro-plan"),
        pytest.param(OTRO_PLAN, "red_apoyo", id="otra-seccion-de-otro-plan"),
    ],
)
def test_mover_cifrado_a_otra_seccion_falla(cifrador: CifradorAesGcm, plan: uuid.UUID, tipo: str) -> None:
    # Dada la sección rutina del plan, cifrada con la DEK de la persona
    seccion = _cifrar(cifrador, _texto(), plan=PLAN, tipo="rutina")

    # Cuando ese mismo texto cifrado se intenta leer como otra sección o como la de otro plan
    # (la misma persona y la misma DEK: solo cambia el AAD)
    with pytest.raises(SeccionIlegible):
        _descifrar(cifrador, seccion, plan=plan, tipo=tipo)

    # Entonces falla, y en su lugar original se sigue leyendo
    assert _descifrar(cifrador, seccion, plan=PLAN, tipo="rutina")


def test_escribir_con_clave_destruida_falla(custodia: CustodiaEnMemoria, claves: RepositorioClavesEnMemoria) -> None:
    # Dada una persona cuya clave se creó y después se destruyó (borrado criptográfico)
    cifrador = CifradorAesGcm(custodia, claves)
    _cifrar(cifrador, _texto())
    claves.destruir(PERSONA)

    # Cuando se intenta escribir de nuevo su ficha
    with pytest.raises(ClaveDestruida):
        _cifrar(cifrador, _texto())

    # Entonces no se creó una clave nueva: sigue la misma fila, destruida
    assert claves.creaciones == 1
    assert claves.filas[PERSONA].dek_cifrada is None


def test_dek_se_crea_en_primera_escritura(custodia: CustodiaEnMemoria, claves: RepositorioClavesEnMemoria) -> None:
    # Dada una persona sin clave de datos: leer distingue "no existe" de "destruida"
    cifrador = CifradorAesGcm(custodia, claves)
    assert claves.filas == {}
    with pytest.raises(ClaveInexistente):
        _descifrar(cifrador, SeccionCifrada(b"\xaa", b"\x00" * LARGO_NONCE, b"\x00" * LARGO_TAG, 1))
    assert claves.filas == {}  # leer nunca crea la clave

    # Cuando se escribe la primera sección
    primera = _cifrar(cifrador, _texto(), tipo="rutina")

    # Entonces la DEK queda creada, envuelta con la KEK vigente y con su kek_version
    fila = claves.filas[PERSONA]
    assert claves.creaciones == 1
    assert fila.grupo_id == GRUPO
    assert fila.dek_cifrada is not None
    assert fila.kek_version == custodia.version_vigente == primera.kek_version == 1

    # Y las escrituras siguientes, de cualquier sección, usan la misma DEK
    segunda = _cifrar(cifrador, _texto(), tipo="red_apoyo")
    assert claves.creaciones == 1
    assert claves.filas[PERSONA].dek_cifrada == fila.dek_cifrada
    assert _descifrar(cifrador, segunda, tipo="red_apoyo")


# --- Más casos del criterio de aceptación y de las condiciones del analista --------------------------


def test_leer_con_clave_destruida_falla(cifrador: CifradorAesGcm, claves: RepositorioClavesEnMemoria) -> None:
    # Dada una sección escrita y la clave de la persona destruida
    seccion = _cifrar(cifrador, _texto())
    claves.destruir(PERSONA)

    # Cuando se intenta leer, entonces falla con el error de dominio explícito, no con "sin clave"
    with pytest.raises(ClaveDestruida):
        _descifrar(cifrador, seccion)
    assert claves.creaciones == 1


def test_kek_version_queda_registrada(custodia: CustodiaEnMemoria, claves: RepositorioClavesEnMemoria) -> None:
    # Dada una custodia cuya KEK vigente es la versión 2
    custodia.rotar()
    cifrador = CifradorAesGcm(custodia, claves)

    # Cuando se escribe la primera sección
    seccion = _cifrar(cifrador, _texto())

    # Entonces clave_datos y la sección registran la versión 2
    assert claves.filas[PERSONA].kek_version == 2
    assert seccion.kek_version == 2


def test_clave_envuelta_con_kek_anterior_sigue_sirviendo(
    custodia: CustodiaEnMemoria, claves: RepositorioClavesEnMemoria
) -> None:
    # La rotación no se implementa (después del semestre), pero una KEK nueva no rompe lo escrito
    cifrador = CifradorAesGcm(custodia, claves)
    texto = _texto()
    antes = _cifrar(cifrador, texto)
    custodia.rotar()

    despues = _cifrar(cifrador, texto)

    assert _descifrar(cifrador, antes) == texto
    assert despues.kek_version == 1  # la DEK sigue envuelta con la versión 1
    assert claves.creaciones == 1


class LeeAntesDeLaOtra(RepositorioClavesEnMemoria):
    """Simula la carrera de dos primeras escrituras: la primera lectura de esta transacción no ve
    la fila (la otra todavía no la creaba), y crear() choca con la fila que la otra ya dejó."""

    def __init__(self, compartido: RepositorioClavesEnMemoria) -> None:
        super().__init__()
        self.compartido = compartido
        self.primera_lectura = True

    def obtener(self, persona_cuidada_id: uuid.UUID, *, para_escribir: bool = False) -> ClaveGuardada | None:
        if self.primera_lectura:
            self.primera_lectura = False
            return None
        return self.compartido.obtener(persona_cuidada_id, para_escribir=para_escribir)

    def crear(self, grupo_id: uuid.UUID, persona_cuidada_id: uuid.UUID, envuelta: DekEnvuelta) -> bool:
        return self.compartido.crear(grupo_id, persona_cuidada_id, envuelta)


def test_primera_escritura_concurrente_usa_la_clave_que_quedo(custodia: CustodiaEnMemoria) -> None:
    # Dada otra transacción que creó la clave de la persona mientras esta leía "no existe"
    compartido = RepositorioClavesEnMemoria()
    texto_ajeno = _texto()
    seccion_ajena = _cifrar(CifradorAesGcm(custodia, compartido), texto_ajeno)
    cifrador = CifradorAesGcm(custodia, LeeAntesDeLaOtra(compartido))

    # Cuando esta escritura intenta crear su clave y la fila ya existe
    texto = _texto()
    seccion = _cifrar(cifrador, texto)

    # Entonces queda una sola DEK, y las dos secciones se leen con ella
    assert compartido.creaciones == 1
    assert _descifrar(cifrador, seccion) == texto
    assert _descifrar(cifrador, seccion_ajena) == texto_ajeno


def test_primera_escritura_concurrente_con_clave_ya_destruida_falla(custodia: CustodiaEnMemoria) -> None:
    # Dada otra transacción que creó la clave y la destruyó mientras esta leía "no existe"
    compartido = RepositorioClavesEnMemoria()
    _cifrar(CifradorAesGcm(custodia, compartido), _texto())
    compartido.destruir(PERSONA)

    # Cuando esta escritura intenta crear su clave, entonces falla y no crea otra
    with pytest.raises(ClaveDestruida):
        _cifrar(CifradorAesGcm(custodia, LeeAntesDeLaOtra(compartido)), _texto())
    assert compartido.creaciones == 1
    assert compartido.filas[PERSONA].dek_cifrada is None


def test_sin_kek_vigente_no_se_crea_la_clave(custodia: CustodiaEnMemoria, claves: RepositorioClavesEnMemoria) -> None:
    custodia.destruir(1)

    with pytest.raises(ClaveNoDisponible):
        _cifrar(CifradorAesGcm(custodia, claves), _texto())
    assert claves.filas == {}


def test_kek_destruida_no_desenvuelve_y_no_se_crea_otra_clave(
    custodia: CustodiaEnMemoria, claves: RepositorioClavesEnMemoria
) -> None:
    # Dada una sección escrita con la DEK envuelta con la versión 1, y esa versión de la KEK destruida
    cifrador = CifradorAesGcm(custodia, claves)
    seccion = _cifrar(cifrador, _texto())
    custodia.rotar()
    custodia.destruir(1)

    # Entonces ni se lee ni se escribe, y la clave guardada no se reemplaza
    with pytest.raises(ClaveNoDisponible):
        _descifrar(cifrador, seccion)
    with pytest.raises(ClaveNoDisponible):
        _cifrar(cifrador, _texto())
    assert claves.creaciones == 1


def test_seccion_de_otra_persona_falla(custodia: CustodiaEnMemoria, claves: RepositorioClavesEnMemoria) -> None:
    # Cada persona tiene su DEK: una sección copiada a la ficha de otra persona no se lee
    cifrador = CifradorAesGcm(custodia, claves)
    otra_persona = uuid.UUID("00000000-0000-0000-0000-0000000012c1")
    seccion = _cifrar(cifrador, _texto())
    cifrador.cifrar(grupo_id=GRUPO, persona_cuidada_id=otra_persona, plan_id=OTRO_PLAN, tipo="rutina", texto="x")

    with pytest.raises(SeccionIlegible):
        cifrador.descifrar(persona_cuidada_id=otra_persona, plan_id=PLAN, tipo="rutina", seccion=seccion)


def test_tipo_desconocido_no_toca_la_clave(cifrador: CifradorAesGcm, claves: RepositorioClavesEnMemoria) -> None:
    with pytest.raises(TipoSeccionInvalido):
        _cifrar(cifrador, _texto(), tipo="notas_libres")
    assert claves.filas == {}


# --- Nada sensible en logs, errores ni repr (condiciones 1 y 5 del analista) -------------------------


def _errores_de_cada_camino(custodia: CustodiaEspia, texto: str) -> list[ErrorCifrado]:
    """Recorre los caminos de error del cifrador con el mismo texto y devuelve cada excepción."""
    claves = RepositorioClavesEnMemoria()
    cifrador = CifradorAesGcm(custodia, claves)
    seccion = _cifrar(cifrador, texto)
    intentos = [
        lambda: _descifrar(cifrador, replace(seccion, tag_auth=_cambiar_un_byte(seccion.tag_auth))),
        lambda: _descifrar(cifrador, seccion, tipo="red_apoyo"),
        lambda: _descifrar(cifrador, seccion, plan=OTRO_PLAN),
        lambda: _cifrar(cifrador, texto, tipo="notas_libres"),
    ]
    errores: list[ErrorCifrado] = []
    for intento in intentos:
        with pytest.raises(ErrorCifrado) as capturado:
            intento()
        errores.append(capturado.value)

    claves.destruir(PERSONA)
    for intento in (lambda: _cifrar(cifrador, texto), lambda: _descifrar(cifrador, seccion)):
        with pytest.raises(ClaveDestruida) as destruida:
            intento()
        errores.append(destruida.value)

    sin_kek = CustodiaEspia()
    sin_kek.destruir(1)
    with pytest.raises(ClaveNoDisponible) as no_disponible:
        _cifrar(CifradorAesGcm(sin_kek, RepositorioClavesEnMemoria()), texto)
    errores.append(no_disponible.value)
    return errores


def test_texto_ni_claves_en_logs_ni_en_errores(caplog: pytest.LogCaptureFixture) -> None:
    # Dada una custodia que recuerda las DEK que envolvió, y un texto con una marca única
    caplog.set_level(logging.DEBUG)
    custodia = CustodiaEspia()
    texto = _texto()

    # Cuando se recorren el camino feliz y todos los caminos de error, registrando cada error
    # como lo haría la API (con su traza)
    errores = _errores_de_cada_camino(custodia, texto)
    for error in errores:
        logging.getLogger("matu.prueba").error("falló el cifrado", exc_info=error)

    # Entonces ni el texto, ni la DEK en claro, ni la DEK envuelta aparecen en los logs, ni en el
    # mensaje, el repr, los argumentos o la traza de ninguna excepción
    assert custodia.deks and custodia.envueltas
    secretos: list[str] = [texto]
    for dek in custodia.deks:
        secretos += [dek.hex(), repr(dek)]
    for envuelta in custodia.envueltas:
        secretos += [envuelta.dek_cifrada.hex(), repr(envuelta.dek_cifrada)]
    marca = texto.rsplit(" ", 1)[-1]
    secretos.append(marca)

    registros = caplog.text + "".join(repr(r.__dict__) for r in caplog.records)
    for secreto in secretos:
        assert secreto not in registros
    for error in errores:
        vistas = str(error) + repr(error) + repr(error.args) + "".join(traceback.format_exception(error))
        for secreto in secretos:
            assert secreto not in vistas
        # Errores genéricos, sin una excepción original encadenada que pudiera llevar contenido
        assert error.__cause__ is None
        assert error.__context__ is None
        assert str(error) == type(error).mensaje
    # Algo se registró: la prueba no pasa en vacío
    assert any(r.name == "matu.care_plan.cifrado" for r in caplog.records)


def test_repr_del_cifrador_y_de_la_seccion_sin_texto_ni_claves() -> None:
    espia = CustodiaEspia()
    cifrador = CifradorAesGcm(espia, RepositorioClavesEnMemoria())
    texto = _texto()

    seccion = _cifrar(cifrador, texto)

    vistas = repr(cifrador) + repr(seccion) + str(seccion)
    for secreto in (texto, espia.deks[0].hex(), espia.envueltas[0].dek_cifrada.hex()):
        assert secreto not in vistas


def test_el_cifrador_no_guarda_la_dek_en_claro() -> None:
    # Condición 5: la DEK en claro vive solo durante la operación. Ni el cifrador ni lo que se
    # guarda en clave_datos la contienen
    espia = CustodiaEspia()
    claves = RepositorioClavesEnMemoria()
    cifrador = CifradorAesGcm(espia, claves)
    _cifrar(cifrador, _texto())
    dek = espia.deks[0]

    assert all(not isinstance(v, bytes) for v in vars(cifrador).values())
    guardada = claves.filas[PERSONA].dek_cifrada
    assert guardada is not None and dek not in guardada
