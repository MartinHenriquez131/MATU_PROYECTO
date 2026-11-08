"""Casos de uso de «Compré» y «Me quedan N» (MATU-51, RF-10 y RF-11, decisiones 136 a 143).

La autorización para ``consumo`` (leída con FOR SHARE), el rol y la persona ya los verificó la API
(api/dependencias.py, ``ParaEscribir``). Los dos son condicionales, como el PATCH y «Ya lo
resolví» (decisiones 41 y 80): exigen If-Match con el ETag del perfil.

- «Compré» reutiliza ``reponer()`` y ``declarar_reposicion`` de MATU-37 (decisión 79), sin otra fórmula:
  suma lo comprado a lo que MATU estima que queda hoy, anota una reposicion declarada con ``ocurrida_en`` =
  hoy según el Reloj, deja ``resuelta`` la alerta abierta de la fecha anterior y descarta las demás que
  dejan de corresponder. Nunca crea una fila en alerta_quiebre.
- «Me quedan N» reutiliza ``aplicar_cambios`` (``recontar``): no anota una reposicion y descarta las
  alertas abiertas que dejan de corresponder.

La auditoría lleva solo actor, identificador y request_id. Nada de este archivo escribe en los logs.
Ninguna de las dos crea un pedido ni publica un evento (decisión C de Jorge, ADR-002).
"""

import uuid
from datetime import date, datetime

from app.modules.consumption.application.alertas import InsumoAvisado, _auditar, _avisado
from app.modules.consumption.application.perfiles import (
    PerfilInactivo,
    PerfilNoEncontrado,
    PeticionConsumo,
    VersionDesactualizada,
)
from app.modules.consumption.application.ports import (
    AlertaLeida,
    InsumoEnVentana,
    PerfilLeido,
    RepositorioAlertas,
    RepositorioPerfiles,
)
from app.modules.consumption.domain.alerta import (
    AlertaAbierta,
    EstadoAlerta,
    cantidad_comprada,
    dejan_de_corresponder,
    reponer,
)
from app.modules.consumption.domain.perfil import Perfil, coincide, exigir_if_match, hoy_en_chile, recontar
from app.shared.auditoria import AccionAuditoria, EntidadAuditoria
from app.shared.puertos import RegistroAuditoria, Reloj


def _vigente(
    peticion: PeticionConsumo, perfil_id: uuid.UUID, if_match: str | None, perfiles: RepositorioPerfiles
) -> PerfilLeido | VersionDesactualizada:
    """404 (perfil), 428 (FaltaVersion), 409 (PerfilInactivo) y 412, en ese orden, sin escribir nada."""
    leido = perfiles.obtener(peticion.persona_id, perfil_id, para_escribir=True)
    if leido is None:
        raise PerfilNoEncontrado()
    valor = exigir_if_match(if_match)
    if not leido.perfil.activo:
        raise PerfilInactivo()
    if not coincide(valor, leido.perfil.version):
        return VersionDesactualizada(actual=leido)
    return leido


def _descartar(
    peticion: PeticionConsumo,
    nuevo: Perfil,
    abiertas: list[AlertaLeida],
    hoy: date,
    ahora: datetime,
    alertas: RepositorioAlertas,
    auditoria: RegistroAuditoria,
) -> None:
    """Las alertas abiertas que con la fecha nueva dejan de corresponder pasan a descartada."""
    candidatas = tuple(AlertaAbierta(id=a.id, fecha_prevista=a.fecha_prevista) for a in abiertas)
    for alerta_id in dejan_de_corresponder(nuevo, candidatas, hoy):
        alertas.cerrar(alerta_id, EstadoAlerta.DESCARTADA, ahora)
        _auditar(auditoria, peticion, AccionAuditoria.ALERTA_DESCARTAR, EntidadAuditoria.ALERTA_QUIEBRE, alerta_id)


def _recalculado(
    peticion: PeticionConsumo,
    perfil_id: uuid.UUID,
    hoy: date,
    perfiles: RepositorioPerfiles,
    alertas: RepositorioAlertas,
) -> InsumoAvisado:
    """El perfil recién escrito, con avisando y alerta_id para su fecha nueva (decisión 140)."""
    nuevo = perfiles.obtener(peticion.persona_id, perfil_id)
    if nuevo is None:  # pragma: no cover - recién escrito en la misma transacción
        raise PerfilNoEncontrado()
    alerta = alertas.de_la_fecha(perfil_id, nuevo.perfil.fecha_quiebre_estimada)
    return _avisado(InsumoEnVentana(leido=nuevo, alerta=alerta), hoy)


def comprar(
    peticion: PeticionConsumo,
    perfil_id: uuid.UUID,
    envases: int | None,
    cantidad: int | None,
    if_match: str | None,
    reloj: Reloj,
    perfiles: RepositorioPerfiles,
    alertas: RepositorioAlertas,
    auditoria: RegistroAuditoria,
) -> InsumoAvisado | VersionDesactualizada:
    """«Compré» (decisiones 137 y 138). Orden: 404, 428, 409 perfil-inactivo, 412 y después los 422 que dependen
    del perfil: EnvasesOCantidad, SinUnidadesPorEnvase, StockMaximo y CoberturaMaxima del dominio. Si algo
    falla, no se escribe nada."""
    vigente = _vigente(peticion, perfil_id, if_match, perfiles)
    if isinstance(vigente, VersionDesactualizada):
        return vigente
    perfil = vigente.perfil
    ahora = reloj.ahora()
    hoy = hoy_en_chile(ahora)
    unidades = cantidad_comprada(perfil, envases=envases, cantidad=cantidad)
    repuesto = reponer(perfil, unidades, hoy, peticion.usuario_id)

    abiertas = alertas.abiertas_del_perfil(perfil.id)
    perfiles.actualizar(repuesto)
    reposicion_id = uuid.uuid4()
    alertas.declarar_reposicion(reposicion_id, perfil.id, unidades, hoy, peticion.usuario_id)
    _auditar(auditoria, peticion, AccionAuditoria.REPOSICION_DECLARAR, EntidadAuditoria.REPOSICION, reposicion_id)

    # La alerta abierta de la fecha anterior queda resuelta: la compra la responde. Si ya estaba cerrada
    # (por ejemplo «No avisar esta vez»), no está entre las abiertas y no hay 409 (condición 10)
    resueltas = [a for a in abiertas if a.fecha_prevista == perfil.fecha_quiebre_estimada]
    for alerta in resueltas:
        alertas.cerrar(alerta.id, EstadoAlerta.RESUELTA, ahora)
        _auditar(auditoria, peticion, AccionAuditoria.ALERTA_RESOLVER, EntidadAuditoria.ALERTA_QUIEBRE, alerta.id)
    otras = [a for a in abiertas if a.fecha_prevista != perfil.fecha_quiebre_estimada]
    _descartar(peticion, repuesto, otras, hoy, ahora, alertas, auditoria)
    return _recalculado(peticion, perfil.id, hoy, perfiles, alertas)


def anotar_lo_que_queda(
    peticion: PeticionConsumo,
    perfil_id: uuid.UUID,
    stock_unidades: int,
    if_match: str | None,
    reloj: Reloj,
    perfiles: RepositorioPerfiles,
    alertas: RepositorioAlertas,
    auditoria: RegistroAuditoria,
) -> InsumoAvisado | VersionDesactualizada:
    """«Me quedan N» (decisión 139). Orden: 404, 428, 409 perfil-inactivo, 412 y 422 (CoberturaMaxima). No
    anota una reposicion."""
    vigente = _vigente(peticion, perfil_id, if_match, perfiles)
    if isinstance(vigente, VersionDesactualizada):
        return vigente
    perfil = vigente.perfil
    ahora = reloj.ahora()
    hoy = hoy_en_chile(ahora)
    nuevo = recontar(perfil, stock_unidades, hoy, peticion.usuario_id)

    abiertas = alertas.abiertas_del_perfil(perfil.id)
    perfiles.actualizar(nuevo)
    _auditar(auditoria, peticion, AccionAuditoria.CONSUMO_EDITAR, EntidadAuditoria.PERFIL_CONSUMO, perfil.id)
    _descartar(peticion, nuevo, abiertas, hoy, ahora, alertas, auditoria)
    return _recalculado(peticion, perfil.id, hoy, perfiles, alertas)
