"""MATU-11 · CifradorAesGcm con RepositorioClavesSQL, contra PostgreSQL como matu_app.

La familia, la persona y el plan los siembran las fábricas (superusuario). El cifrado y la escritura
de las secciones corren como matu_app dentro de sesion_tenant, con el contexto del admin del grupo:
RLS acota clave_datos y plan_seccion al grupo. Lo que quedó en la base se revisa como superusuario.

Las secciones se insertan aquí con SQL: el repositorio de secciones y su endpoint llegan con MATU-12.

Trazan a ADR-014 y ADR-016 (no hay un RF): sin marca rf. Solo textos sintéticos.
"""

import secrets
import threading
import uuid
from collections.abc import Iterator
from contextlib import AbstractContextManager
from typing import Any

import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import obtener_configuracion
from app.core.db import sesion_tenant
from app.modules.care_plan.domain.cifrado import ClaveDestruida, SeccionCifrada
from app.modules.care_plan.infrastructure.cifrador_aes_gcm import CifradorAesGcm
from app.modules.care_plan.infrastructure.repositorio_claves import RepositorioClavesSQL
from tests.base_datos import DSN, requiere_base
from tests.dobles.custodia_en_memoria import CustodiaEnMemoria
from tests.fabricas import Fabrica
from tests.fabricas.fabrica import FamiliaCreada

pytestmark = requiere_base

_INSERTAR_SECCION = text(
    "INSERT INTO plan_seccion (plan_id, tipo, contenido_cifrado, nonce, tag_auth, kek_version)"
    " VALUES (:plan_id, :tipo, :contenido, :nonce, :tag, :kek_version)"
)
_LEER_SECCION = text(
    "SELECT contenido_cifrado, nonce, tag_auth, kek_version FROM plan_seccion WHERE plan_id = :plan_id AND tipo = :tipo"
)


def _texto() -> str:
    return f"Almuerza a las 13 y duerme siesta hasta las 15 · marca {secrets.token_hex(6)}"


@pytest.fixture
def sesiones() -> Iterator[sessionmaker[Session]]:
    """Sesiones como matu_app (DATABASE_URL), con dos conexiones para las pruebas de concurrencia."""
    url = obtener_configuracion().database_url
    assert url
    engine = create_engine(url, pool_size=2, max_overflow=0)
    try:
        yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    finally:
        engine.dispose()


@pytest.fixture
def familia(fabrica: Fabrica) -> FamiliaCreada:
    """Un grupo con su admin, una persona con consentimiento y su plan, sin secciones ni clave."""
    return fabrica.familia(miembros=(), con_ficha=True)


def _como_admin(sesiones: sessionmaker[Session], familia: FamiliaCreada) -> AbstractContextManager[Session]:
    """La transacción de una petición del admin del grupo: matu_app con app.usuario_id y app.grupo_id."""
    return sesion_tenant(sesiones, usuario_id=familia.admin.id, grupo_id=familia.grupo.id)


def _plan(familia: FamiliaCreada) -> uuid.UUID:
    assert familia.ficha is not None
    return familia.ficha.plan_id


def _escribir(
    sesion: Session, custodia: CustodiaEnMemoria, familia: FamiliaCreada, tipo: str, texto: str
) -> SeccionCifrada:
    """Lo que hará el PUT de MATU-12: cifrar y guardar la sección en la misma transacción."""
    cifrador = CifradorAesGcm(custodia, RepositorioClavesSQL(sesion))
    seccion = cifrador.cifrar(
        grupo_id=familia.grupo.id, persona_cuidada_id=familia.persona.id, plan_id=_plan(familia), tipo=tipo, texto=texto
    )
    sesion.execute(
        _INSERTAR_SECCION,
        {
            "plan_id": _plan(familia),
            "tipo": tipo,
            "contenido": seccion.contenido_cifrado,
            "nonce": seccion.nonce,
            "tag": seccion.tag_auth,
            "kek_version": seccion.kek_version,
        },
    )
    return seccion


def _leer(sesion: Session, custodia: CustodiaEnMemoria, familia: FamiliaCreada, tipo: str) -> str:
    contenido, nonce, tag, kek_version = sesion.execute(_LEER_SECCION, {"plan_id": _plan(familia), "tipo": tipo}).one()
    seccion = SeccionCifrada(bytes(contenido), bytes(nonce), bytes(tag), kek_version)
    cifrador = CifradorAesGcm(custodia, RepositorioClavesSQL(sesion))
    return cifrador.descifrar(persona_cuidada_id=familia.persona.id, plan_id=_plan(familia), tipo=tipo, seccion=seccion)


def _claves_de(persona_id: uuid.UUID) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute(
            "SELECT dek_cifrada_con_kek, kek_version, destruida_en FROM clave_datos WHERE persona_cuidada_id = %s",
            (persona_id,),
        ).fetchall()


def _secciones_de(plan_id: uuid.UUID) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute(
            "SELECT tipo, contenido_cifrado, kek_version FROM plan_seccion WHERE plan_id = %s ORDER BY tipo", (plan_id,)
        ).fetchall()


def _destruir(persona_id: uuid.UUID) -> None:
    """El borrado criptográfico, como superusuario: la aplicación todavía no tiene cómo hacerlo."""
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute(
            "UPDATE clave_datos SET dek_cifrada_con_kek = NULL, destruida_en = now() WHERE persona_cuidada_id = %s",
            (persona_id,),
        )


def test_escribir_y_leer_la_ficha_como_matu_app(
    sesiones: sessionmaker[Session], custodia: CustodiaEnMemoria, familia: FamiliaCreada
) -> None:
    # Dada una persona sin clave de datos
    assert _claves_de(familia.persona.id) == []
    textos = {"rutina": _texto(), "manejo_situaciones": _texto(), "red_apoyo": _texto()}

    # Cuando su admin escribe las tres secciones en una transacción
    with _como_admin(sesiones, familia) as sesion:
        for tipo, texto in textos.items():
            _escribir(sesion, custodia, familia, tipo, texto)

    # Entonces queda una sola clave, vigente y con su kek_version, y las secciones van cifradas
    [(dek_cifrada, kek_version, destruida_en)] = _claves_de(familia.persona.id)
    assert dek_cifrada is not None and destruida_en is None and kek_version == 1
    guardadas = _secciones_de(_plan(familia))
    assert [g[0] for g in guardadas] == sorted(textos)
    for tipo, contenido, kek_seccion in guardadas:
        assert textos[tipo].encode("utf-8") not in bytes(contenido)
        assert kek_seccion == kek_version

    # Y en otra transacción se leen de vuelta
    with _como_admin(sesiones, familia) as sesion:
        assert {tipo: _leer(sesion, custodia, familia, tipo) for tipo in textos} == textos


def test_la_clave_y_la_primera_seccion_van_en_la_misma_transaccion(
    sesiones: sessionmaker[Session], custodia: CustodiaEnMemoria, familia: FamiliaCreada
) -> None:
    # Cuando la primera escritura crea la clave y la transacción falla después
    with pytest.raises(RuntimeError), _como_admin(sesiones, familia) as sesion:
        _escribir(sesion, custodia, familia, "rutina", _texto())
        raise RuntimeError("falla después de escribir")

    # Entonces no queda ni la clave ni la sección
    assert _claves_de(familia.persona.id) == []
    assert _secciones_de(_plan(familia)) == []


def test_escribir_con_clave_destruida_falla_y_no_crea_otra(
    sesiones: sessionmaker[Session], custodia: CustodiaEnMemoria, familia: FamiliaCreada
) -> None:
    # Dada una ficha escrita y la clave de la persona destruida
    with _como_admin(sesiones, familia) as sesion:
        _escribir(sesion, custodia, familia, "rutina", _texto())
    _destruir(familia.persona.id)

    # Cuando se intenta escribir y leer
    with pytest.raises(ClaveDestruida), _como_admin(sesiones, familia) as sesion:
        _escribir(sesion, custodia, familia, "red_apoyo", _texto())
    with pytest.raises(ClaveDestruida), _como_admin(sesiones, familia) as sesion:
        _leer(sesion, custodia, familia, "rutina")

    # Entonces falla con el error de dominio, y sigue la misma fila, destruida, sin una nueva
    [(dek_cifrada, _, destruida_en)] = _claves_de(familia.persona.id)
    assert dek_cifrada is None and destruida_en is not None
    assert [g[0] for g in _secciones_de(_plan(familia))] == ["rutina"]


def test_dos_primeras_escrituras_concurrentes_dejan_una_sola_dek(
    sesiones: sessionmaker[Session], custodia: CustodiaEnMemoria, familia: FamiliaCreada
) -> None:
    # Dadas dos transacciones que escriben a la vez la primera sección de la misma persona
    texto_a, texto_b = _texto(), _texto()
    resultado_b: dict[str, Any] = {}

    def escribir_b() -> None:
        try:
            with _como_admin(sesiones, familia) as sesion:
                _escribir(sesion, custodia, familia, "red_apoyo", texto_b)
        except Exception as error:  # se revisa en el hilo principal
            resultado_b["error"] = error

    with _como_admin(sesiones, familia) as sesion_a:
        # A crea la clave y no confirma todavía
        _escribir(sesion_a, custodia, familia, "rutina", texto_a)
        # B lee "no existe" e intenta crear la suya: el UNIQUE la deja esperando a A
        hilo = threading.Thread(target=escribir_b)
        hilo.start()
        hilo.join(timeout=1.0)
        assert hilo.is_alive(), "B debía quedar esperando la transacción de A"
    # Al confirmar A, B sigue con la clave de A
    hilo.join(timeout=10.0)
    assert not hilo.is_alive()

    # Entonces no hubo error, quedó una sola DEK, y las dos secciones se leen con ella
    assert "error" not in resultado_b, repr(resultado_b.get("error"))
    assert len(_claves_de(familia.persona.id)) == 1
    with _como_admin(sesiones, familia) as sesion:
        assert _leer(sesion, custodia, familia, "rutina") == texto_a
        assert _leer(sesion, custodia, familia, "red_apoyo") == texto_b


def test_otro_grupo_no_alcanza_la_clave(
    sesiones: sessionmaker[Session], custodia: CustodiaEnMemoria, fabrica: Fabrica, familia: FamiliaCreada
) -> None:
    # Dada la ficha de una familia escrita, y el admin de otra familia
    with _como_admin(sesiones, familia) as sesion:
        _escribir(sesion, custodia, familia, "rutina", _texto())
    otra = fabrica.familia(miembros=())

    # Cuando el otro admin, en el contexto de su grupo, busca la clave de esa persona
    with sesion_tenant(sesiones, usuario_id=otra.admin.id, grupo_id=otra.grupo.id) as sesion:
        clave = RepositorioClavesSQL(sesion).obtener(familia.persona.id)

    # Entonces RLS no la muestra
    assert clave is None
