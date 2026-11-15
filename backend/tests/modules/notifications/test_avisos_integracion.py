"""MATU-41 · El consumidor de QuiebreProximo y el publicador del outbox contra PostgreSQL (RF-39).

El publicador corre como matu_publisher (desde la 0022, MATU-74) con app.rol = 'operacion' (funciones outbox_*), y
el consumidor como matu_app con app.rol = 'sistema' y el grupo del evento. Los enviadores son dobles en memoria.
Solo datos sintéticos.
"""

import json
import logging
import threading
from datetime import timedelta
from typing import Any

import pytest

from app.core.db import fabrica_sesiones
from app.modules.consumption.events import QUIEBRE_PROXIMO
from app.modules.notifications.application.avisos import ConsumidorQuiebreProximo
from app.modules.notifications.application.ports import EnvioCorreo
from app.modules.notifications.domain.aviso import ResultadoEnvio
from app.modules.notifications.infrastructure.repositorio_avisos import UnidadAvisosSQL
from app.shared.outbox import Hecho, Posponer, Reintentar, ResultadoPublicacion, publicar_pendientes
from app.shared.outbox_sql import AlmacenOutboxSql
from tests.base_datos import fabrica_publisher, requiere_base
from tests.dobles.enviadores_en_memoria import EnviadorCorreoEnMemoria, EnviadorPushEnMemoria
from tests.dobles.reloj_fijo import RelojFijo
from tests.modules.notifications.conftest import ORIGEN, EntornoAvisos, ejecutar, filas

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
        "UPDATE consentimiento SET revocado_en = %s, revocacion_motivo = 'retiro'"
        " WHERE persona_cuidada_id = %s AND finalidad = 'consumo'",
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
    almacen = AlmacenOutboxSql(fabrica_publisher())
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
    almacen = AlmacenOutboxSql(fabrica_publisher())

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


def test_retiro_por_el_caso_de_uso_omite_el_aviso_pendiente(entorno_avisos: EntornoAvisos) -> None:
    """MATU-44 (condición 10): el retiro real descarta la alerta y el aviso pendiente queda omitido."""
    from app.core.db import fabrica_sesiones, sesion_tenant
    from app.modules.care_circle.application.retiro import SolicitudRetiro, retirar_autorizacion
    from app.modules.care_circle.infrastructure.efectos_retiro import efectos_de, registrar_efecto
    from app.modules.care_circle.infrastructure.repositorio_retiros import RepositorioRetirosSQL
    from app.modules.consumption.infrastructure.efecto_retiro import EfectoRetiroConsumo
    from app.shared.auditoria_sql import RegistroAuditoriaSql

    registrar_efecto("consumo", EfectoRetiroConsumo)
    e = entorno_avisos
    familia = e.familia()
    avisado = e.avisar(familia)
    grupo = familia.grupo.id
    with sesion_tenant(fabrica_sesiones(), usuario_id=familia.admin.id, grupo_id=grupo) as sesion:
        registro = RegistroAuditoriaSql(sesion, e.reloj)
        retirar_autorizacion(
            SolicitudRetiro(
                usuario_id=familia.admin.id, rol="admin", persona_id=familia.persona.id, finalidad="consumo"
            ),
            e.reloj, RepositorioRetirosSQL(sesion, grupo, registro), efectos_de(sesion, grupo, registro),
        )

    assert isinstance(e.consumir(avisado), Hecho)

    assert set(e.avisos(familia).values()) == {("omitida", "sin_autorizacion")}
    assert e.correo.enviados == [] and e.push.enviados == []
    assert e.estado_alerta(avisado)[0] == "descartada"


# --- MATU-74, hallazgo H3 y condición C15: avisos cada 5 minutos sin enviar dos veces ----------------------------


class _CorreoQueEspera:
    """Un enviador de correo cuyo primer envío no termina hasta que la prueba lo suelta."""

    def __init__(self) -> None:
        self.entro = threading.Event()
        self.seguir = threading.Event()
        self.enviados: list[EnvioCorreo] = []

    def enviar(self, envio: EnvioCorreo) -> ResultadoEnvio:
        self.enviados.append(envio)
        if len(self.enviados) == 1:
            self.entro.set()
            assert self.seguir.wait(timeout=30)
        return ResultadoEnvio.ENVIADO


def test_dos_corridas_que_se_cruzan_no_envian_dos_veces(entorno_avisos: EntornoAvisos) -> None:
    """La primera corrida toma el evento y se queda en su primer envío. La segunda, 6 minutos después según su Reloj
    (pasó el arriendo de 5 minutos del outbox), vuelve a tomar el mismo evento y espera el bloqueo de la fila. Al
    terminar, cada notificación se envió una sola vez y hay una sola fila enviada por persona y canal."""
    e = entorno_avisos
    familia = e.familia()
    e.dispositivo(familia.admin, _token(7))
    avisado = e.avisar(familia)
    lento, rapido = _CorreoQueEspera(), EnviadorCorreoEnMemoria()
    push_lento, push_rapido = EnviadorPushEnMemoria(), EnviadorPushEnMemoria()
    almacen = AlmacenOutboxSql(fabrica_publisher())
    resultados: dict[str, ResultadoPublicacion] = {}

    def corrida(nombre: str, correo: Any, push: Any, reloj: RelojFijo) -> None:
        consumidor = ConsumidorQuiebreProximo(
            unidad=UnidadAvisosSQL(fabrica_sesiones()),
            correo=correo,
            push=push,
            reloj=reloj,
            origen_web=ORIGEN,
            push_permitido=lambda _usuario_id: True,
        )
        resultados[nombre] = publicar_pendientes(
            almacen, {QUIEBRE_PROXIMO: [consumidor]}, reloj, grupo_id=familia.grupo.id
        )

    primera = threading.Thread(target=corrida, args=("primera", lento, push_lento, RelojFijo(e.reloj.ahora())))
    primera.start()
    assert lento.entro.wait(timeout=30)
    seis_minutos = RelojFijo(e.reloj.ahora() + timedelta(minutes=6))
    segunda = threading.Thread(target=corrida, args=("segunda", rapido, push_rapido, seis_minutos))
    segunda.start()
    segunda.join(timeout=2)
    se_cruzaron = segunda.is_alive()  # tomó el evento y espera el FOR UPDATE de la fila que envía la primera
    lento.seguir.set()
    primera.join(timeout=30)
    segunda.join(timeout=30)

    assert se_cruzaron and not primera.is_alive() and not segunda.is_alive()
    assert set(resultados) == {"primera", "segunda"}
    envios = [x.notificacion_id for x in [*lento.enviados, *rapido.enviados]]
    envios += [x.notificacion_id for x in [*push_lento.enviados, *push_rapido.enviados]]
    assert len(envios) == len(set(envios)) == 3  # correo del admin y del cuidador, y el push del admin
    enviadas = filas("SELECT usuario_id, canal, count(*) FROM notificacion WHERE grupo_id = %s AND estado = 'enviada'"
                     " GROUP BY usuario_id, canal", familia.grupo.id)
    cuidador = familia.miembros["cuidador"].usuario
    assert sorted((u, c, n) for u, c, n in enviadas) == sorted(
        [(familia.admin.id, "correo", 1), (familia.admin.id, "push", 1), (cuidador.id, "correo", 1)]
    )
    assert filas("SELECT publicado_en IS NOT NULL FROM evento_outbox WHERE id = %s", avisado.evento.id) == [(True,)]
