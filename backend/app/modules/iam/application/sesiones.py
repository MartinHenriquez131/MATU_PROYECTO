"""Casos de uso de MATU-38 (RF-37): entrar con demora progresiva, renovar con rotación, cerrar,
y los dispositivos.

El refresh solo existe aquí y en la cookie: nunca se registra, ni se audita, ni sale en un error. A la
base llega su SHA-256. La renovación no se audita (decisión de MATU-38); la reutilización sí, y deja
además un evento de seguridad en el log con el id de la familia.
"""

import logging
import secrets
import uuid
from dataclasses import dataclass

from app.modules.iam.application.ports import (
    ContadoresEntrada,
    DispositivoGuardado,
    EmisorTokens,
    HasherContrasenas,
    NuevoRefresh,
    RepositorioUsuarios,
    UnidadIam,
)
from app.modules.iam.application.sesion import emitir_acceso, verificar_credenciales
from app.modules.iam.domain.credenciales import normalizar_email
from app.modules.iam.domain.demora import PREFIJO_EMAIL, PREFIJO_IP, huella, retry_after
from app.modules.iam.domain.dispositivo import limites_conservacion, nombre_dispositivo
from app.modules.iam.domain.refresh import (
    BYTES_REFRESH,
    MOTIVO_DISPOSITIVO,
    MOTIVO_LOGOUT,
    MOTIVO_REUTILIZACION,
    Veredicto,
    evaluar_renovacion,
    huella_refresh,
    sigue_vigente,
    tiene_forma_de_refresh,
    vencimiento_refresh,
)
from app.modules.iam.domain.sesion import CredencialesInvalidas
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.puertos import Reloj

log = logging.getLogger("matu.iam")


class DemoraActiva(Exception):
    """La huella de la IP o la del email están en espera. Nunca dice cuál."""

    def __init__(self, segundos: int) -> None:
        super().__init__("demora activa")
        self.segundos = segundos


class SesionRechazada(Exception):
    """El refresh no sirve: falta, es desconocido, venció, fue revocado o se reutilizó. Un solo caso."""


class DispositivoNoEncontrado(Exception):
    """No existe, es de otro usuario, ya fue revocado (push) o el token no trae did."""


@dataclass(frozen=True)
class SesionAbierta:
    usuario_id: uuid.UUID
    dispositivo_id: uuid.UUID
    access_token: str
    duracion_segundos: int
    # Solo para la cookie. Nunca en un log, un error ni la auditoría
    refresh: str

    def __repr__(self) -> str:
        return f"SesionAbierta(usuario_id={self.usuario_id}, dispositivo_id={self.dispositivo_id})"


def _nuevo_refresh() -> str:
    return secrets.token_urlsafe(BYTES_REFRESH)


def _resolver(refresh: str | None, unidad: UnidadIam) -> tuple[uuid.UUID, uuid.UUID] | None:
    if not tiene_forma_de_refresh(refresh):
        return None
    assert refresh is not None
    indexado = unidad.resolver_refresh(huella_refresh(refresh))
    if indexado is None:
        return None
    return indexado.usuario_id, indexado.sesion_id


def entrar(
    *,
    email: str,
    contrasena: str,
    ip: str,
    agente_usuario: str | None,
    refresh_presentado: str | None,
    pepper: bytes,
    pepper_limites: bytes,
    hasher: HasherContrasenas,
    repositorio: RepositorioUsuarios,
    contadores: ContadoresEntrada,
    unidad: UnidadIam,
    emisor: EmisorTokens,
    reloj: Reloj,
    request_id: str | None = None,
) -> SesionAbierta:
    """POST /v1/sesiones (MATU-05a con el cambio de MATU-38).

    Orden: demora (DemoraActiva, sin correr Argon2), credenciales (CredencialesInvalidas, suma un fallo
    a las dos huellas y audita sesion.inicio_fallido con la huella del email), y la sesión: borra el
    contador del email, reutiliza el dispositivo de la cookie si es del mismo usuario y sigue vigente
    (revocando la familia anterior) o crea uno, crea la familia y audita sesion.iniciar.

    Lanza ContadoresNoDisponibles si Redis no responde: la entrada falla cerrada.
    """
    huella_ip = huella(pepper_limites, PREFIJO_IP, ip)
    huella_email = huella(pepper_limites, PREFIJO_EMAIL, normalizar_email(email))

    espera = retry_after(contadores.leer(huella_ip), contadores.leer(huella_email), reloj.ahora())
    if espera > 0:
        raise DemoraActiva(espera)

    try:
        usuario_id = verificar_credenciales(
            email=email, contrasena=contrasena, pepper=pepper, hasher=hasher, repositorio=repositorio
        )
    except CredencialesInvalidas:
        ahora = reloj.ahora()
        contadores.sumar_fallo(huella_ip, ahora)
        contadores.sumar_fallo(huella_email, ahora)
        with unidad.transaccion(None) as tx:
            tx.auditoria.registrar(
                EntradaAuditoria(
                    grupo_id=None,
                    actor_tipo=ActorTipo.SISTEMA,
                    actor_ref=None,
                    accion=AccionAuditoria.SESION_INICIO_FALLIDO,
                    entidad=EntidadAuditoria.USUARIO,
                    huella_email=huella_email,
                    request_id=request_id,
                )
            )
        raise

    # Un 200 borra el contador del email, nunca el de la IP. Antes de crear nada: si Redis falla, 503
    contadores.borrar(huella_email)

    anterior = _resolver(refresh_presentado, unidad)
    ahora = reloj.ahora()
    refresh = _nuevo_refresh()
    with unidad.transaccion(usuario_id) as tx:
        dispositivo_id: uuid.UUID | None = None
        if anterior is not None and anterior[0] == usuario_id:
            guardada = tx.sesiones.sesion_para_actualizar(anterior[1])
            if guardada is not None and sigue_vigente(guardada.estado, ahora):
                # Una sola sesión viva por dispositivo: la anterior se cierra
                tx.sesiones.revocar_familia(guardada.familia_id, MOTIVO_LOGOUT, ahora)
                dispositivo_id = guardada.dispositivo_id
                tx.sesiones.tocar_dispositivo(dispositivo_id, ahora)
        if dispositivo_id is None:
            dispositivo_id = tx.sesiones.crear_dispositivo(usuario_id, nombre_dispositivo(agente_usuario), ahora)
        tx.sesiones.crear_refresh(
            NuevoRefresh(
                id=uuid.uuid4(),
                usuario_id=usuario_id,
                dispositivo_id=dispositivo_id,
                familia_id=uuid.uuid4(),
                token_hash=huella_refresh(refresh),
                emitido_en=ahora,
                expira_en=vencimiento_refresh(ahora),
            )
        )
        tx.auditoria.registrar(
            EntradaAuditoria(
                grupo_id=None,
                actor_tipo=ActorTipo.USUARIO,
                actor_ref=usuario_id,
                accion=AccionAuditoria.SESION_INICIAR,
                entidad=EntidadAuditoria.DISPOSITIVO,
                entidad_id=dispositivo_id,
                request_id=request_id,
            )
        )
    acceso = emitir_acceso(usuario_id, emisor, reloj, dispositivo_id)
    return SesionAbierta(
        usuario_id=usuario_id,
        dispositivo_id=dispositivo_id,
        access_token=acceso.access_token,
        duracion_segundos=acceso.duracion_segundos,
        refresh=refresh,
    )


def renovar(
    *, refresh_presentado: str | None, unidad: UnidadIam, emisor: EmisorTokens, reloj: Reloj, request_id: str | None
) -> SesionAbierta:
    """POST /v1/sesiones/renovar: rota el refresh con detección de reutilización.

    Lanza SesionRechazada, siempre igual, en todo caso de fallo. Si el token ya se había usado, antes
    revoca toda la familia ('reutilizacion'), lo audita y lo registra en el log, y lo confirma.
    No audita la renovación correcta.
    """
    resuelto = _resolver(refresh_presentado, unidad)
    if resuelto is None:
        raise SesionRechazada()
    usuario_id, sesion_id = resuelto

    ahora = reloj.ahora()
    refresh = _nuevo_refresh()
    veredicto = Veredicto.RECHAZADO
    with unidad.transaccion(usuario_id) as tx:
        guardada = tx.sesiones.sesion_para_actualizar(sesion_id)
        if guardada is not None:
            veredicto = evaluar_renovacion(guardada.estado, ahora)
        if guardada is not None and veredicto is Veredicto.REUTILIZACION:
            tx.sesiones.revocar_familia(guardada.familia_id, MOTIVO_REUTILIZACION, ahora)
            tx.auditoria.registrar(
                EntradaAuditoria(
                    grupo_id=None,
                    actor_tipo=ActorTipo.USUARIO,
                    actor_ref=usuario_id,
                    accion=AccionAuditoria.SESION_REUTILIZACION_DETECTADA,
                    entidad=EntidadAuditoria.DISPOSITIVO,
                    entidad_id=guardada.dispositivo_id,
                    request_id=request_id,
                )
            )
            log.warning(
                "reutilizacion de refresh: familia revocada",
                extra={"evento": "seguridad.reutilizacion_refresh", "familia_id": str(guardada.familia_id),
                       "usuario_id": str(usuario_id)},
            )
        elif guardada is not None and veredicto is Veredicto.VIGENTE:
            tx.sesiones.marcar_usado(guardada.id, ahora)
            tx.sesiones.crear_refresh(
                NuevoRefresh(
                    id=uuid.uuid4(),
                    usuario_id=usuario_id,
                    dispositivo_id=guardada.dispositivo_id,
                    familia_id=guardada.familia_id,
                    token_hash=huella_refresh(refresh),
                    emitido_en=ahora,
                    expira_en=vencimiento_refresh(ahora),
                )
            )
            tx.sesiones.tocar_dispositivo(guardada.dispositivo_id, ahora)
    if guardada is None or veredicto is not Veredicto.VIGENTE:
        raise SesionRechazada()

    acceso = emitir_acceso(usuario_id, emisor, reloj, guardada.dispositivo_id)
    return SesionAbierta(
        usuario_id=usuario_id,
        dispositivo_id=guardada.dispositivo_id,
        access_token=acceso.access_token,
        duracion_segundos=acceso.duracion_segundos,
        refresh=refresh,
    )


def cerrar(*, refresh_presentado: str | None, unidad: UnidadIam, reloj: Reloj, request_id: str | None) -> None:
    """POST /v1/sesiones/cerrar: idempotente. Revoca la familia ('logout') y el dispositivo, y borra su
    push_token (decisión 47). Sin cookie, o con una desconocida o ya cerrada, no hace nada."""
    resuelto = _resolver(refresh_presentado, unidad)
    if resuelto is None:
        return
    usuario_id, sesion_id = resuelto
    ahora = reloj.ahora()
    with unidad.transaccion(usuario_id) as tx:
        guardada = tx.sesiones.sesion_para_actualizar(sesion_id)
        if guardada is None:
            return
        revocados = tx.sesiones.revocar_familia(guardada.familia_id, MOTIVO_LOGOUT, ahora)
        dispositivo = tx.sesiones.dispositivo_para_actualizar(guardada.dispositivo_id)
        dispositivo_abierto = dispositivo is not None and not dispositivo.revocado
        if dispositivo_abierto:
            tx.sesiones.revocar_sesiones_de_dispositivo(guardada.dispositivo_id, MOTIVO_LOGOUT, ahora)
            tx.sesiones.revocar_dispositivo(guardada.dispositivo_id, ahora)
        if revocados or dispositivo_abierto:
            tx.auditoria.registrar(
                EntradaAuditoria(
                    grupo_id=None,
                    actor_tipo=ActorTipo.USUARIO,
                    actor_ref=usuario_id,
                    accion=AccionAuditoria.SESION_CERRAR,
                    entidad=EntidadAuditoria.DISPOSITIVO,
                    entidad_id=guardada.dispositivo_id,
                    request_id=request_id,
                )
            )


def listar_dispositivos(*, usuario_id: uuid.UUID, unidad: UnidadIam) -> list[DispositivoGuardado]:
    """Los dispositivos propios no revocados."""
    with unidad.transaccion(usuario_id) as tx:
        return tx.sesiones.listar_dispositivos()


def sacar_dispositivo(
    *, usuario_id: uuid.UUID, dispositivo_id: uuid.UUID, unidad: UnidadIam, reloj: Reloj, request_id: str | None
) -> None:
    """DELETE /v1/dispositivos/{id}: revoca sus sesiones ('dispositivo'), el dispositivo y su push_token.

    Lanza DispositivoNoEncontrado si no es del usuario. Uno ya revocado no cambia nada (idempotente).
    """
    ahora = reloj.ahora()
    with unidad.transaccion(usuario_id) as tx:
        dispositivo = tx.sesiones.dispositivo_para_actualizar(dispositivo_id)
        if dispositivo is None:
            raise DispositivoNoEncontrado()
        if dispositivo.revocado:
            return
        cerradas = tx.sesiones.revocar_sesiones_de_dispositivo(dispositivo_id, MOTIVO_DISPOSITIVO, ahora)
        tx.sesiones.revocar_dispositivo(dispositivo_id, ahora)
        tx.auditoria.registrar(
            EntradaAuditoria(
                grupo_id=None,
                actor_tipo=ActorTipo.USUARIO,
                actor_ref=usuario_id,
                accion=AccionAuditoria.DISPOSITIVO_SACAR,
                entidad=EntidadAuditoria.DISPOSITIVO,
                entidad_id=dispositivo_id,
                sesiones_revocadas=cerradas,
                request_id=request_id,
            )
        )


def guardar_push(
    *,
    usuario_id: uuid.UUID,
    dispositivo_id: uuid.UUID | None,
    push_token: str | None,
    unidad: UnidadIam,
    request_id: str | None,
) -> None:
    """PUT (con push_token) o DELETE (con None) de /v1/dispositivos/actual/push.

    Lanza DispositivoNoEncontrado si el access token no trae did, o si el dispositivo está revocado.
    El push_token ya llega validado (lista cerrada de hosts) y nunca se audita.
    """
    if dispositivo_id is None:
        raise DispositivoNoEncontrado()
    with unidad.transaccion(usuario_id) as tx:
        if not tx.sesiones.guardar_push(dispositivo_id, push_token):
            raise DispositivoNoEncontrado()
        tx.auditoria.registrar(
            EntradaAuditoria(
                grupo_id=None,
                actor_tipo=ActorTipo.USUARIO,
                actor_ref=usuario_id,
                accion=(
                    AccionAuditoria.DISPOSITIVO_PUSH_BORRAR
                    if push_token is None
                    else AccionAuditoria.DISPOSITIVO_PUSH_REGISTRAR
                ),
                entidad=EntidadAuditoria.DISPOSITIVO,
                entidad_id=dispositivo_id,
                request_id=request_id,
            )
        )


@dataclass(frozen=True)
class ResultadoConservacion:
    sesiones_borradas: int
    dispositivos_borrados: int


def conservar(*, unidad: UnidadIam, reloj: Reloj) -> ResultadoConservacion:
    """Decisión 59: borra las sesiones 30 días después de vencer o de revocarse, y los dispositivos
    90 días después de su último uso que no tengan sesiones vigentes. Los límites salen del Reloj."""
    sesiones, dispositivos = unidad.conservar(limites_conservacion(reloj.ahora()))
    return ResultadoConservacion(sesiones_borradas=sesiones, dispositivos_borrados=dispositivos)
