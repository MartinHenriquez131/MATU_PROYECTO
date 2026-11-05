"""MATU-41 · El consumidor de QuiebreProximo y el publicador del outbox contra PostgreSQL (RF-39).

Corren como matu_app: el publicador con app.rol = 'operacion' (funciones outbox_*) y el consumidor con
app.rol = 'sistema' y el grupo del evento. Los enviadores son dobles en memoria. Solo datos sintéticos.
"""

import json
import logging
from datetime import timedelta

import pytest

from app.core.db import fabrica_sesiones
from app.modules.consumption.events import QUIEBRE_PROXIMO
from app.modules.notifications.domain.aviso import ResultadoEnvio
from app.shared.outbox import Hecho, Posponer, Reintentar, publicar_pendientes
from app.shared.outbox_sql import AlmacenOutboxSql
from tests.base_datos import requiere_base
from tests.modules.notifications.conftest import EntornoAvisos, ejecutar, filas

pytestmark = [requiere_base, pytest.mark.rf("RF-39")]

TOKEN = "https://fcm.googleapis.com/fcm/send/token-sintetico-{}"


def _token(n: int) -> str:
    return TOKEN.format(n)


def test_un_evento_produce_los_avisos_esperados(entorno_avisos: EntornoAvisos) -> None:
    e = entorno_avisos
    familia = e.familia()
    admin, cuidador = familia.admin, familia.miembros["cuidador"].usuario
    pagador, observador = familia.miembros["pagador"].usuario, familia.miembros["observador"].usuario
    e.dispositivo(admin, _token(1))
    e.dispositivo(admin)  # sin push_token: no cuenta
    avisado = e.avisar(familia)

    assert isinstance(e.consumir(avisado), Hecho)

    # Admin y cuidador por defecto; el pagador y el observador no tienen filas
    assert e.avisos(familia) == {
        (admin.id, "correo"): ("enviada", None),
        (admin.id, "push"): ("enviada", None),
        (cuidador.id, "correo"): ("enviada", None),
        (cuidador.id, "push"): ("omitida", "sin_destino"),
    }
    assert {x.destino for x in e.correo.enviados} == {admin.email, cuidador.email}
    assert [x.push_token for x in e.push.enviados] == [_token(1)]
    assert pagador.id not in {x.usuario_id for x in e.correo.enviados}
    assert observador.id not in {x.usuario_id for x in e.correo.enviados}
    assert e.estado_alerta(avisado) == ("notificada", True)
    assert filas("SELECT consumidor FROM evento_consumido WHERE evento_id = %s", avisado.evento.id) == [
        ("notifications.quiebre_proximo",)
    ]
    # Ninguna columna de la fila lleva el destino ni el texto
    [(fila,)] = filas("SELECT to_jsonb(n) FROM notificacion n WHERE usuario_id = %s AND canal = 'correo'", admin.id)
    assert admin.email not in json.dumps(fila) and "insumo" not in json.dumps(fila)


def test_un_reintento_del_mismo_evento_no_duplica(entorno_avisos: EntornoAvisos) -> None:
    e = entorno_avisos
    familia = e.familia()
    avisado = e.avisar(familia)
    assert isinstance(e.consumir(avisado), Hecho)
    enviados = len(e.correo.enviados)

    # Al menos una vez: el publicador se cayó antes de marcarlo publicado y el evento vuelve
    assert isinstance(e.consumir(avisado), Hecho)

    assert len(e.correo.enviados) == enviados == 2
    assert len(filas("SELECT 1 FROM notificacion WHERE grupo_id = %s", familia.grupo.id)) == 4


def test_si_el_push_falla_el_correo_sale_igual_y_el_reintento_no_reenvia_el_correo(
    entorno_avisos: EntornoAvisos,
) -> None:
    e = entorno_avisos
    familia = e.familia()
    e.dispositivo(familia.admin, _token(2))
    e.push.respuesta = ResultadoEnvio.NO_DISPONIBLE
    avisado = e.avisar(familia)

    assert isinstance(e.consumir(avisado), Reintentar)
    avisos = e.avisos(familia)
    assert avisos[(familia.admin.id, "correo")] == ("enviada", None)
    assert avisos[(familia.admin.id, "push")] == ("fallida", "proveedor_no_disponible")
    assert e.estado_alerta(avisado) == ("notificada", True)  # al menos un envío llegó
    assert filas("SELECT 1 FROM evento_consumido WHERE evento_id = %s", avisado.evento.id) == []

    e.push.respuesta = ResultadoEnvio.ENVIADO
    e.reloj.avanzar(timedelta(seconds=1))
    assert isinstance(e.consumir(avisado), Hecho)
    assert e.avisos(familia)[(familia.admin.id, "push")] == ("enviada", None)
    assert [x.usuario_id for x in e.correo.enviados].count(familia.admin.id) == 1
    assert len(e.push.enviados) == 2


def test_autorizacion_retirada_entre_la_creacion_y_el_envio_no_envia(entorno_avisos: EntornoAvisos) -> None:
    e = entorno_avisos
    familia = e.familia()
    avisado = e.avisar(familia)
    ejecutar(
        "UPDATE consentimiento SET revocado_en = %s WHERE persona_cuidada_id = %s AND finalidad = 'consumo'",
        e.reloj.ahora(), familia.persona.id,
    )

    assert isinstance(e.consumir(avisado), Hecho)

    assert set(e.avisos(familia).values()) == {("omitida", "sin_autorizacion")}
    assert e.correo.enviados == [] and e.push.enviados == []
    assert e.estado_alerta(avisado) == ("pendiente", False)


def test_revision_de_12_meses_vencida_no_envia(entorno_avisos: EntornoAvisos) -> None:
    e = entorno_avisos
    # Otorgada por un cuidador de hecho hace 12 meses menos una hora: vigente al crear el evento
    otorgado = e.reloj.ahora().replace(year=e.reloj.ahora().year - 1) + timedelta(hours=1)
    familia = e.familia(calidad="cuidador_de_hecho", otorgado_en=otorgado)
    avisado = e.avisar(familia)
    e.reloj.avanzar(timedelta(hours=2))  # 11:00 en Santiago: la revisión ya venció

    assert isinstance(e.consumir(avisado), Hecho)

    assert set(e.avisos(familia).values()) == {("omitida", "sin_autorizacion")}
    assert e.correo.enviados == []


def test_alerta_cerrada_no_envia(entorno_avisos: EntornoAvisos) -> None:
    e = entorno_avisos
    familia = e.familia()
    avisado = e.avisar(familia)
    ejecutar("UPDATE alerta_quiebre SET estado = 'resuelta', cerrada_en = now() WHERE id = %s", avisado.alerta_id)

    assert isinstance(e.consumir(avisado), Hecho)

    assert set(e.avisos(familia).values()) == {("omitida", "alerta_cerrada")}
    assert e.correo.enviados == []


def test_perfil_borrado_no_envia(entorno_avisos: EntornoAvisos) -> None:
    e = entorno_avisos
    familia = e.familia()
    avisado = e.avisar(familia)
    ejecutar("DELETE FROM perfil_consumo WHERE id = %s", avisado.perfil_id)  # la alerta cae en cascada

    assert isinstance(e.consumir(avisado), Hecho)
    assert set(e.avisos(familia).values()) == {("omitida", "alerta_cerrada")}


def test_miembro_retirado_no_recibe(entorno_avisos: EntornoAvisos) -> None:
    e = entorno_avisos
    familia = e.familia()
    cuidador = familia.miembros["cuidador"]
    e.correo.respuestas = [ResultadoEnvio.NO_DISPONIBLE, ResultadoEnvio.NO_DISPONIBLE]
    avisado = e.avisar(familia)
    assert isinstance(e.consumir(avisado), Reintentar)

    # Se retira entre un intento y el siguiente
    ejecutar("UPDATE membresia SET estado = 'retirada' WHERE id = %s", cuidador.membresia.id)
    e.reloj.avanzar(timedelta(seconds=1))
    assert isinstance(e.consumir(avisado), Hecho)

    avisos = e.avisos(familia)
    assert avisos[(cuidador.usuario.id, "correo")] == ("omitida", "miembro_inactivo")
    assert avisos[(familia.admin.id, "correo")] == ("enviada", None)
    assert [x.usuario_id for x in e.correo.enviados].count(cuidador.usuario.id) == 1  # solo el intento fallido


def test_miembro_retirado_antes_del_evento_no_tiene_filas(entorno_avisos: EntornoAvisos) -> None:
    e = entorno_avisos
    familia = e.familia()
    cuidador = familia.miembros["cuidador"]
    ejecutar("UPDATE membresia SET estado = 'retirada' WHERE id = %s", cuidador.membresia.id)
    ejecutar("UPDATE usuario SET estado = 'bloqueado' WHERE id = %s", familia.admin.id)
    avisado = e.avisar(familia)

    assert isinstance(e.consumir(avisado), Hecho)
    assert e.avisos(familia) == {}
    assert e.correo.enviados == []


def test_pagador_sin_opt_in_no_recibe_y_con_opt_in_si(entorno_avisos: EntornoAvisos) -> None:
    e = entorno_avisos
    familia = e.familia()
    pagador, observador = familia.miembros["pagador"].usuario, familia.miembros["observador"].usuario
    e.preferencia(pagador, "correo", True)
    e.dispositivo(observador, _token(3))
    e.preferencia(observador, "push", True)
    avisado = e.avisar(familia)

    assert isinstance(e.consumir(avisado), Hecho)

    avisos = e.avisos(familia)
    assert avisos[(pagador.id, "correo")] == ("enviada", None)
    assert avisos[(observador.id, "push")] == ("enviada", None)
    # Los canales que no activaron no tienen fila: nunca se busca otro canal
    assert (pagador.id, "push") not in avisos and (observador.id, "correo") not in avisos


def test_admin_con_el_correo_desactivado_no_recibe_correo(entorno_avisos: EntornoAvisos) -> None:
    e = entorno_avisos
    familia = e.familia()
    e.preferencia(familia.admin, "correo", False)
    e.dispositivo(familia.admin, _token(4))
    avisado = e.avisar(familia)

    assert isinstance(e.consumir(avisado), Hecho)

    avisos = e.avisos(familia)
    assert (familia.admin.id, "correo") not in avisos  # el canal apagado no tiene fila
    assert avisos[(familia.admin.id, "push")] == ("enviada", None)
    assert familia.admin.id not in {x.usuario_id for x in e.correo.enviados}


class _RepositorioQueVigila:
    """Envuelve el repositorio real y anota a quién se le leyó el destino."""

    def __init__(self, real: object, leidos: list[tuple[str, object]]) -> None:
        self._real = real
        self._leidos = leidos

    def __getattr__(self, nombre: str) -> object:
        return getattr(self._real, nombre)

    def correo(self, usuario_id: object) -> object:
        self._leidos.append(("correo", usuario_id))
        return self._real.correo(usuario_id)  # type: ignore[attr-defined]

    def destinos_push(self, usuario_id: object) -> object:
        self._leidos.append(("push", usuario_id))
        return self._real.destinos_push(usuario_id)  # type: ignore[attr-defined]


def test_apagar_el_correo_despues_de_creada_la_fila_omite_sin_leer_el_email(entorno_avisos: EntornoAvisos) -> None:
    from contextlib import contextmanager

    from app.modules.notifications.infrastructure.repositorio_avisos import UnidadAvisosSQL

    e = entorno_avisos
    familia = e.familia()
    e.correo.respuestas = [ResultadoEnvio.NO_DISPONIBLE, ResultadoEnvio.NO_DISPONIBLE]
    avisado = e.avisar(familia)
    assert isinstance(e.consumir(avisado), Reintentar)
    # Entre un intento y el siguiente, el admin apaga el correo
    e.preferencia(familia.admin, "correo", False)

    leidos: list[tuple[str, object]] = []
    real = UnidadAvisosSQL(fabrica_sesiones())

    class UnidadQueVigila:
        @contextmanager
        def abrir(self, grupo_id):  # type: ignore[no-untyped-def]
            with real.abrir(grupo_id) as repo:
                yield _RepositorioQueVigila(repo, leidos)

    consumidor = e.consumidor()
    consumidor._unidad = UnidadQueVigila()  # type: ignore[assignment]
    e.reloj.avanzar(timedelta(seconds=1))
    assert isinstance(consumidor.consumir(avisado.evento), Hecho)

    assert e.avisos(familia)[(familia.admin.id, "correo")] == ("omitida", "sin_destino")
    assert ("correo", familia.admin.id) not in leidos
    assert ("correo", familia.miembros["cuidador"].usuario.id) in leidos


def test_push_410_deja_el_push_token_en_null(entorno_avisos: EntornoAvisos) -> None:
    e = entorno_avisos
    familia = e.familia()
    vencido = e.dispositivo(familia.admin, _token(5))
    vigente = e.dispositivo(familia.miembros["cuidador"].usuario, _token(6))
    e.push.por_token = {_token(5): ResultadoEnvio.EXPIRADO}
    avisado = e.avisar(familia)

    assert isinstance(e.consumir(avisado), Hecho)

    avisos = e.avisos(familia)
    assert avisos[(familia.admin.id, "push")] == ("fallida", "push_expirado")
    assert avisos[(familia.admin.id, "correo")] == ("enviada", None)
    assert filas("SELECT push_token FROM dispositivo WHERE id = %s", vencido) == [(None,)]
    assert filas("SELECT push_token FROM dispositivo WHERE id = %s", vigente) == [(_token(6),)]


def test_no_se_envia_antes_de_las_0900_de_chile(entorno_avisos: EntornoAvisos) -> None:
    e = entorno_avisos
    # El trabajo diario de las 04:00 en Santiago (07:00 UTC con horario de verano)
    e.reloj = type(e.reloj)(e.reloj.ahora().replace(hour=7))
    familia = e.familia()
    avisado = e.avisar(familia)
    almacen = AlmacenOutboxSql(fabrica_sesiones())
    consumidores = {QUIEBRE_PROXIMO: [e.consumidor()]}

    assert isinstance(e.consumir(avisado), Posponer)
    resultado = publicar_pendientes(almacen, consumidores, e.reloj, grupo_id=familia.grupo.id)

    assert resultado.pospuestos == 1 and e.correo.enviados == [] and e.avisos(familia) == {}
    [(disponible, intentos)] = filas("SELECT disponible_en, intentos FROM evento_outbox WHERE id = %s",
                                     avisado.evento.id)
    assert (disponible, intentos) == (e.reloj.ahora().replace(hour=12), 0)

    e.reloj.avanzar(timedelta(hours=4, minutes=59))  # 08:59
    assert publicar_pendientes(almacen, consumidores, e.reloj, grupo_id=familia.grupo.id).publicados == 0
    e.reloj.avanzar(timedelta(minutes=1))  # 09:00
    assert publicar_pendientes(almacen, consumidores, e.reloj, grupo_id=familia.grupo.id).publicados == 1
    assert len(e.correo.enviados) == 2
    assert filas("SELECT publicado_en IS NOT NULL FROM evento_outbox WHERE id = %s", avisado.evento.id) == [(True,)]


def test_el_publicador_reintenta_con_backoff_contra_la_base(entorno_avisos: EntornoAvisos) -> None:
    e = entorno_avisos
    familia = e.familia()
    e.correo.respuestas = [ResultadoEnvio.NO_DISPONIBLE] * 2
    avisado = e.avisar(familia)
    almacen = AlmacenOutboxSql(fabrica_sesiones())

    resultado = publicar_pendientes(almacen, {QUIEBRE_PROXIMO: [e.consumidor()]}, e.reloj, grupo_id=familia.grupo.id)

    assert resultado.reintentos == 1
    [(disponible, intentos, publicado)] = filas(
        "SELECT disponible_en, intentos, publicado_en FROM evento_outbox WHERE id = %s", avisado.evento.id
    )
    assert (disponible, intentos, publicado) == (e.reloj.ahora() + timedelta(seconds=1), 1, None)


def test_los_logs_no_llevan_email_token_ni_texto(
    entorno_avisos: EntornoAvisos, caplog: pytest.LogCaptureFixture
) -> None:
    e = entorno_avisos
    familia = e.familia()
    e.dispositivo(familia.admin, _token(7))
    e.push.por_token = {_token(7): ResultadoEnvio.EXPIRADO}
    avisado = e.avisar(familia)

    with caplog.at_level(logging.DEBUG):
        e.consumir(avisado)

    prohibidos = [familia.admin.email, familia.miembros["cuidador"].usuario.email, _token(7), "insumo", "Abrir MATU"]
    lineas = [str(r.__dict__) for r in caplog.records] + [caplog.text]
    for texto in prohibidos:
        assert all(texto not in linea for linea in lineas), texto
    avisos = [r for r in caplog.records if r.name == "matu.notifications.avisos"]
    assert {r.__dict__["canal"] for r in avisos} == {"correo", "push"}
    assert {"notificacion_id", "evento_id", "estado", "codigo"} <= set(avisos[0].__dict__)
    # Ni el repr del consumidor ni el de lo enviado muestran el destino
    assert familia.admin.email not in repr(e.correo.enviados) and _token(7) not in repr(e.push.enviados)
    assert repr(e.consumidor()) == "ConsumidorQuiebreProximo()"
