"""Casos de uso de MATU-57 (RF-37): recuperar el acceso con un código, y verificar el celular.

Reglas de privacidad que valen para todo el archivo:
- El código, el celular, el email, sus huellas y la IP nunca van a la auditoría, a un log, a un error
  ni a un evento. Solo el EnviadorCodigos recibe el destino y el mensaje.
- solicitar_recuperacion corre después de responder (la ruta lo deja en segundo plano): la respuesta
  es la misma exista o no la cuenta, y los contadores del email y de la IP se cuentan antes de leer
  la base, para que el límite tampoco dependa de que exista.
"""

import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime

from app.modules.iam.application.ports import (
    AlmacenCodigos,
    ContadoresEntrada,
    ContadoresEnvio,
    DatosCuenta,
    EnviadorCodigos,
    HasherContrasenas,
    RepositorioUsuarios,
    UnidadIam,
)
from app.modules.iam.application.sesiones import DemoraActiva
from app.modules.iam.domain.credenciales import indice_email, normalizar_email
from app.modules.iam.domain.demora import UMBRAL_EMAIL, huella, retry_after, segundos_restantes
from app.modules.iam.domain.recuperacion import (
    MAX_INTENTOS,
    MENSAJE_AVISO,
    PREFIJO_RECUPERAR_CELULAR,
    PREFIJO_RECUPERAR_EMAIL,
    PREFIJO_RECUPERAR_IP,
    PREFIJO_VERIFICAR_CELULAR,
    PREFIJO_VERIFICAR_EMAIL,
    PREFIJO_VERIFICAR_IP,
    Canal,
    CodigoGuardado,
    CodigoInvalido,
    Proposito,
    canal_del_aviso,
    canal_del_codigo,
    clave_codigo,
    codigo_nuevo,
    codigo_sirve,
    es_codigo,
    espera_destino,
    espera_ip,
    huella_codigo,
    mensaje_codigo,
)
from app.modules.iam.domain.refresh import MOTIVO_CAMBIO_CLAVE
from app.modules.iam.domain.sesion import puede_iniciar_sesion
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.puertos import Reloj

log = logging.getLogger("matu.iam")

# Prefijo de la huella de la cuenta para los envíos al celular (además del destino)
PREFIJO_CELULAR_CUENTA = "celular-cuenta"


class SinCelular(Exception):
    """La cuenta no tiene celular."""


class CelularYaVerificado(Exception):
    """El celular de la cuenta ya está verificado."""


class EnvioEnEspera(Exception):
    """Hay que esperar para pedir otro código (60 s, 3 por hora o 10 al día)."""

    def __init__(self, segundos: int) -> None:
        super().__init__("envio en espera")
        self.segundos = segundos


@dataclass(frozen=True)
class Peppers:
    """Las llaves que usa MATU-57. Nunca se registran."""

    email: bytes
    limites: bytes
    recuperacion: bytes

    def __repr__(self) -> str:
        return "Peppers()"


def _codigo_aleatorio() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def _celular_verificado(datos: DatosCuenta) -> bool:
    return datos.telefono is not None and datos.celular_verificado_en is not None


def _destino(datos: DatosCuenta, canal: Canal) -> str:
    if canal is Canal.SMS:
        assert datos.telefono is not None
        return datos.telefono
    return datos.email


def _huella_valor(pepper: bytes, clave: str, proposito: Proposito, telefono: str | None, codigo: str) -> str:
    # El código del celular queda ligado al número al que se envió: si cambia, el código ya no calza
    ligado = f"{clave}:{telefono}" if proposito is Proposito.CELULAR else clave
    return huella_codigo(pepper, ligado, codigo)


def _enviar(enviador: EnviadorCodigos, canal: Canal, destino: str, mensaje: str) -> None:
    try:
        enviador.enviar(canal, destino, mensaje)
    except Exception:
        # Sin el destino, el mensaje ni la excepción, que podría traerlos
        log.error("no se pudo enviar un mensaje", extra={"evento": "recuperacion.envio_fallido", "canal": canal.value})


def _usuario_activo(email: str, pepper: bytes, repositorio: RepositorioUsuarios) -> uuid.UUID | None:
    credencial = repositorio.buscar_credencial(indice_email(pepper, normalizar_email(email)))
    if credencial is None or not puede_iniciar_sesion(credencial.estado):
        return None
    return credencial.usuario_id


def solicitar_recuperacion(
    *,
    email: str,
    solo_correo: bool,
    ip: str,
    peppers: Peppers,
    repositorio: RepositorioUsuarios,
    unidad: UnidadIam,
    almacen: AlmacenCodigos,
    envios: ContadoresEnvio,
    enviador: EnviadorCodigos,
    reloj: Reloj,
    request_id: str | None = None,
) -> None:
    """Pide un código de recuperación (decisiones 81 a 85). Nunca lanza por la cuenta ni por el límite:
    la ruta ya respondió 202. Puede lanzar ContadoresNoDisponibles si Redis no responde.

    - Límites (antes de leer la base): IP (20 por hora, 50 al día) y email (60 s, 3 por hora, 10 al
      día). Si se alcanzan, no envía nada.
    - Cuenta inexistente o no activa: no envía nada ni audita.
    - Celular verificado y sin solo_correo: al celular, si su destino no está en el límite; si lo está,
      al correo. Si no, al correo.
    - Guarda la huella del código nuevo (el anterior deja de servir), audita y envía.
    """
    ahora = reloj.ahora()
    huella_ip = huella(peppers.limites, PREFIJO_RECUPERAR_IP, ip)
    huella_email = huella(peppers.limites, PREFIJO_RECUPERAR_EMAIL, normalizar_email(email))
    if espera_ip(envios.leer(huella_ip), ahora) > 0 or espera_destino(envios.leer(huella_email), ahora) > 0:
        log.info("recuperacion: limite de envios alcanzado", extra={"evento": "recuperacion.limite"})
        return
    envios.sumar(huella_ip, ahora)
    envios.sumar(huella_email, ahora)

    usuario_id = _usuario_activo(email, peppers.email, repositorio)
    if usuario_id is None:
        return
    with unidad.transaccion(usuario_id) as tx:
        datos = tx.cuenta.datos()
    if datos is None:
        return

    canal = canal_del_codigo(_celular_verificado(datos), solo_correo)
    if canal is Canal.SMS:
        assert datos.telefono is not None
        huella_celular = huella(peppers.limites, PREFIJO_RECUPERAR_CELULAR, datos.telefono)
        if espera_destino(envios.leer(huella_celular), ahora) > 0:
            canal = Canal.CORREO
        else:
            envios.sumar(huella_celular, ahora)

    codigo = _codigo_aleatorio()
    clave = clave_codigo(peppers.recuperacion, Proposito.RECUPERAR, str(usuario_id))
    almacen.guardar(
        clave, codigo_nuevo(_huella_valor(peppers.recuperacion, clave, Proposito.RECUPERAR, None, codigo), canal, ahora)
    )
    with unidad.transaccion(usuario_id) as tx:
        tx.auditoria.registrar(
            EntradaAuditoria(
                grupo_id=None,
                actor_tipo=ActorTipo.SISTEMA,
                actor_ref=None,
                accion=AccionAuditoria.CUENTA_RECUPERAR_SOLICITAR,
                entidad=EntidadAuditoria.USUARIO,
                entidad_id=usuario_id,
                request_id=request_id,
            )
        )
    _enviar(enviador, canal, _destino(datos, canal), mensaje_codigo(codigo))


def _comprobar(
    *,
    almacen: AlmacenCodigos,
    clave: str,
    huella_presentada: str,
    ahora: datetime,
) -> CodigoGuardado:
    """Suma el intento, decide y consume. Lanza CodigoInvalido sin decir por qué."""
    guardado = almacen.leer(clave)
    intentos = almacen.sumar_intento(clave) if guardado is not None else 0
    if not codigo_sirve(guardado, huella_presentada, intentos, ahora):
        if guardado is not None and (intentos >= MAX_INTENTOS or ahora >= guardado.expira_en):
            # Agotado o vencido: se quema, y pedir otro es la única salida
            almacen.consumir(clave)
        raise CodigoInvalido()
    assert guardado is not None
    if not almacen.consumir(clave):
        # Otro uso del mismo código llegó primero: un solo uso
        raise CodigoInvalido()
    return guardado


def cambiar_contrasena_con_codigo(
    *,
    email: str,
    codigo: str,
    contrasena_nueva: str,
    ip: str,
    peppers: Peppers,
    hasher: HasherContrasenas,
    repositorio: RepositorioUsuarios,
    unidad: UnidadIam,
    almacen: AlmacenCodigos,
    contadores: ContadoresEntrada,
    enviador: EnviadorCodigos,
    reloj: Reloj,
    request_id: str | None = None,
) -> int:
    """Cambia la contraseña con un código (decisiones 85 y 86). Devuelve cuántas sesiones revocó.

    Orden: demora de la verificación (DemoraActiva), código (CodigoInvalido, el mismo para incorrecto,
    vencido, usado, agotado o sin cuenta; suma un fallo a la IP y al email y audita
    cuenta.recuperar_verificar_fallido), y el cambio: contraseña nueva, todas las sesiones revocadas
    ('cambio_clave'), cuenta.contrasena_cambiar con sesiones_revocadas, los códigos pendientes
    invalidados y el aviso por el otro canal. No emite tokens: la persona vuelve a entrar.
    """
    huella_ip = huella(peppers.limites, PREFIJO_VERIFICAR_IP, ip)
    huella_email = huella(peppers.limites, PREFIJO_VERIFICAR_EMAIL, normalizar_email(email))
    espera = retry_after(contadores.leer(huella_ip), contadores.leer(huella_email), reloj.ahora())
    if espera > 0:
        raise DemoraActiva(espera)

    ahora = reloj.ahora()
    usuario_id = _usuario_activo(email, peppers.email, repositorio)

    def fallar() -> CodigoInvalido:
        contadores.sumar_fallo(huella_ip, ahora)
        contadores.sumar_fallo(huella_email, ahora)
        with unidad.transaccion(usuario_id) as tx:
            tx.auditoria.registrar(
                EntradaAuditoria(
                    grupo_id=None,
                    actor_tipo=ActorTipo.SISTEMA,
                    actor_ref=None,
                    accion=AccionAuditoria.CUENTA_RECUPERAR_VERIFICAR_FALLIDO,
                    entidad=EntidadAuditoria.USUARIO,
                    entidad_id=usuario_id,
                    request_id=request_id,
                )
            )
        return CodigoInvalido()

    if usuario_id is None or not es_codigo(codigo):
        raise fallar()
    clave = clave_codigo(peppers.recuperacion, Proposito.RECUPERAR, str(usuario_id))
    try:
        guardado = _comprobar(
            almacen=almacen,
            clave=clave,
            huella_presentada=_huella_valor(peppers.recuperacion, clave, Proposito.RECUPERAR, None, codigo),
            ahora=ahora,
        )
    except CodigoInvalido:
        raise fallar() from None

    password_hash = hasher.hashear(contrasena_nueva)
    with unidad.transaccion(usuario_id) as tx:
        datos = tx.cuenta.datos()
        tx.cuenta.cambiar_contrasena(password_hash, ahora)
        revocadas = tx.sesiones.revocar_todas(MOTIVO_CAMBIO_CLAVE, ahora)
        tx.auditoria.registrar(
            EntradaAuditoria(
                grupo_id=None,
                actor_tipo=ActorTipo.USUARIO,
                actor_ref=usuario_id,
                accion=AccionAuditoria.CUENTA_CONTRASENA_CAMBIAR,
                entidad=EntidadAuditoria.USUARIO,
                entidad_id=usuario_id,
                sesiones_revocadas=revocadas,
                request_id=request_id,
            )
        )
    # Los demás códigos pendientes de la persona dejan de servir
    almacen.consumir(clave_codigo(peppers.recuperacion, Proposito.CELULAR, str(usuario_id)))
    contadores.borrar(huella_email)
    if datos is not None:
        canal = canal_del_aviso(guardado.canal, _celular_verificado(datos))
        _enviar(enviador, canal, _destino(datos, canal), MENSAJE_AVISO)
    return revocadas


def leer_cuenta(*, usuario_id: uuid.UUID, unidad: UnidadIam) -> DatosCuenta:
    with unidad.transaccion(usuario_id) as tx:
        datos = tx.cuenta.datos()
    if datos is None:
        raise LookupError("la cuenta del token no existe")
    return datos


def pedir_codigo_celular(
    *,
    usuario_id: uuid.UUID,
    peppers: Peppers,
    unidad: UnidadIam,
    almacen: AlmacenCodigos,
    envios: ContadoresEnvio,
    enviador: EnviadorCodigos,
    reloj: Reloj,
    request_id: str | None = None,
) -> None:
    """Envía un código al celular de la cuenta para verificarlo (decisión 87).

    Lanza SinCelular, CelularYaVerificado o EnvioEnEspera (60 s, 3 por hora y 10 al día, por cuenta y
    por número).
    """
    ahora = reloj.ahora()
    datos = leer_cuenta(usuario_id=usuario_id, unidad=unidad)
    if datos.telefono is None:
        raise SinCelular()
    if datos.celular_verificado_en is not None:
        raise CelularYaVerificado()
    huella_cuenta = huella(peppers.limites, PREFIJO_CELULAR_CUENTA, str(usuario_id))
    huella_celular = huella(peppers.limites, PREFIJO_RECUPERAR_CELULAR, datos.telefono)
    espera = max(espera_destino(envios.leer(huella_cuenta), ahora), espera_destino(envios.leer(huella_celular), ahora))
    if espera > 0:
        raise EnvioEnEspera(espera)
    envios.sumar(huella_cuenta, ahora)
    envios.sumar(huella_celular, ahora)

    codigo = _codigo_aleatorio()
    clave = clave_codigo(peppers.recuperacion, Proposito.CELULAR, str(usuario_id))
    almacen.guardar(
        clave,
        codigo_nuevo(
            _huella_valor(peppers.recuperacion, clave, Proposito.CELULAR, datos.telefono, codigo), Canal.SMS, ahora
        ),
    )
    with unidad.transaccion(usuario_id) as tx:
        tx.auditoria.registrar(
            EntradaAuditoria(
                grupo_id=None,
                actor_tipo=ActorTipo.USUARIO,
                actor_ref=usuario_id,
                accion=AccionAuditoria.CUENTA_CELULAR_SOLICITAR,
                entidad=EntidadAuditoria.USUARIO,
                entidad_id=usuario_id,
                request_id=request_id,
            )
        )
    _enviar(enviador, Canal.SMS, datos.telefono, mensaje_codigo(codigo))


def verificar_celular(
    *,
    usuario_id: uuid.UUID,
    codigo: str,
    canal_preferido: str,
    peppers: Peppers,
    unidad: UnidadIam,
    almacen: AlmacenCodigos,
    contadores: ContadoresEntrada,
    reloj: Reloj,
    request_id: str | None = None,
) -> None:
    """Confirma el celular con su código. Lanza DemoraActiva o CodigoInvalido (que audita el fallo)."""
    huella_usuario = huella(peppers.limites, PREFIJO_VERIFICAR_CELULAR, str(usuario_id))
    ahora = reloj.ahora()
    espera = segundos_restantes(contadores.leer(huella_usuario), UMBRAL_EMAIL, ahora)
    if espera > 0:
        raise DemoraActiva(espera)

    def fallar() -> CodigoInvalido:
        contadores.sumar_fallo(huella_usuario, ahora)
        with unidad.transaccion(usuario_id) as tx:
            tx.auditoria.registrar(
                EntradaAuditoria(
                    grupo_id=None,
                    actor_tipo=ActorTipo.USUARIO,
                    actor_ref=usuario_id,
                    accion=AccionAuditoria.CUENTA_CELULAR_VERIFICAR_FALLIDO,
                    entidad=EntidadAuditoria.USUARIO,
                    entidad_id=usuario_id,
                    request_id=request_id,
                )
            )
        return CodigoInvalido()

    datos = leer_cuenta(usuario_id=usuario_id, unidad=unidad)
    if datos.telefono is None or not es_codigo(codigo):
        raise fallar()
    clave = clave_codigo(peppers.recuperacion, Proposito.CELULAR, str(usuario_id))
    try:
        _comprobar(
            almacen=almacen,
            clave=clave,
            huella_presentada=_huella_valor(peppers.recuperacion, clave, Proposito.CELULAR, datos.telefono, codigo),
            ahora=ahora,
        )
    except CodigoInvalido:
        raise fallar() from None
    with unidad.transaccion(usuario_id) as tx:
        tx.cuenta.marcar_celular_verificado(ahora, canal_preferido)
        tx.auditoria.registrar(
            EntradaAuditoria(
                grupo_id=None,
                actor_tipo=ActorTipo.USUARIO,
                actor_ref=usuario_id,
                accion=AccionAuditoria.CUENTA_CELULAR_VERIFICAR,
                entidad=EntidadAuditoria.USUARIO,
                entidad_id=usuario_id,
                request_id=request_id,
            )
        )
    contadores.borrar(huella_usuario)
