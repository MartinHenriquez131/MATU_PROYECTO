"""Puertos del módulo iam (ADR-021)."""

import uuid
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.modules.iam.domain.demora import ContadorFallos
from app.modules.iam.domain.dispositivo import LimitesConservacion
from app.modules.iam.domain.politica import AceptacionPolitica
from app.modules.iam.domain.recuperacion import Canal, CodigoGuardado, EnviosRecientes
from app.modules.iam.domain.refresh import EstadoRefresh
from app.shared.puertos import RegistroAuditoria


class HasherContrasenas(Protocol):
    """Hash de contraseñas con Argon2id (arquitectura, sección 11.6).

    Implementación: HasherArgon2id (infrastructure/hasher_argon2.py).
    """

    def hashear(self, contrasena: str) -> str:
        """Devuelve el hash en formato PHC ($argon2id$...), con su sal y sus parámetros."""
        ...

    def verificar(self, hash_guardado: str, contrasena: str) -> bool:
        """True si la contraseña corresponde al hash. Nunca lanza por una contraseña incorrecta."""
        ...


@dataclass(frozen=True)
class NuevoUsuario:
    id: uuid.UUID
    nombre: str
    email: str
    password_hash: str
    email_hash: bytes
    # Celular en E.164 (+569XXXXXXXX), ya validado por la API
    telefono: str
    # MATU-75: la política que aceptó al crear la cuenta. Se guarda en la misma transacción que la cuenta
    aceptacion: AceptacionPolitica


@dataclass(frozen=True)
class CredencialGuardada:
    """Lo que el login necesita de una cuenta: su id, el hash de su contraseña y su estado."""

    usuario_id: uuid.UUID
    password_hash: str
    estado: str


class RepositorioUsuarios(Protocol):
    """Persistencia de usuario e indice_credencial.

    Implementación: RepositorioUsuariosSQL (infrastructure/repositorio_usuarios.py).
    """

    def crear(self, usuario: NuevoUsuario) -> None:
        """Guarda el usuario, su fila de indice_credencial y su aceptación de la política (MATU-75) en una sola
        transacción.

        Lanza EmailYaRegistrado si el email ya tiene una cuenta. En ese caso no queda nada guardado.
        """
        ...

    def buscar_credencial(self, email_hash: bytes) -> CredencialGuardada | None:
        """Resuelve el usuario por indice_credencial y lee su hash y su estado.

        Primero busca en indice_credencial (sin RLS) y después fija app.usuario_id para leer la
        fila de usuario, que la política usuario_propio_leer solo muestra a su dueño. None si el email
        no tiene cuenta.
        """
        ...


@dataclass(frozen=True)
class ClaimsAcceso:
    """Los claims de un access token ya verificado. Los instantes van con zona horaria UTC."""

    sub: uuid.UUID
    iat: datetime
    exp: datetime
    # Id del dispositivo (MATU-38, decisión 48). None en un token anterior a MATU-38
    did: uuid.UUID | None = None


class EmisorTokens(Protocol):
    """Firma y lectura de los access tokens (JWT HS256).

    Implementación: EmisorJWT (infrastructure/tokens_jwt.py).
    """

    def emitir(
        self, usuario_id: uuid.UUID, emitido_en: datetime, expira_en: datetime, dispositivo_id: uuid.UUID | None = None
    ) -> str:
        """Devuelve el token firmado con sub, iat y exp, y did si llega el dispositivo (MATU-38)."""
        ...

    def leer(self, token: str) -> ClaimsAcceso:
        """Verifica firma, algoritmo y formato, y devuelve los claims.

        No decide el vencimiento: eso lo hace validar_acceso con el Reloj. Lanza TokenInvalido
        si la firma, el algoritmo o el formato fallan.
        """
        ...


# --- MATU-38: demora progresiva de la entrada (decisión 49) ------------------------------------


class ContadoresNoDisponibles(Exception):
    """El almacén de contadores (Redis) no respondió. La entrada responde 503 y falla cerrada."""


class ContadoresEntrada(Protocol):
    """Contadores de fallos de la entrada, por huella (nunca la IP ni el email en claro).

    Solo guardan: cuántos fallos y cuándo fue el último. La espera la decide el dominio (demora.py).
    Implementaciones: ContadoresEntradaRedis (infrastructure/contadores_redis.py) y
    ContadoresEnMemoria (tests/dobles). Cada método lanza ContadoresNoDisponibles si no puede.
    """

    def leer(self, huella: str) -> ContadorFallos:
        """Los fallos de la huella en la ventana vigente, o SIN_FALLOS."""
        ...

    def sumar_fallo(self, huella: str, ahora: datetime) -> None:
        """Suma un fallo y fija el último en ahora. La ventana vence a la hora del primer fallo."""
        ...

    def borrar(self, huella: str) -> None:
        """Borra el contador de la huella (un inicio correcto borra el del email)."""
        ...


# --- MATU-38: sesiones y dispositivos ---------------------------------------------------------


@dataclass(frozen=True)
class RefreshIndexado:
    """Lo que indice_token dice de un refresh, antes de tener contexto: de quién es y qué sesión."""

    usuario_id: uuid.UUID
    sesion_id: uuid.UUID


@dataclass(frozen=True)
class SesionGuardada:
    id: uuid.UUID
    familia_id: uuid.UUID
    dispositivo_id: uuid.UUID
    estado: EstadoRefresh


@dataclass(frozen=True)
class NuevoRefresh:
    id: uuid.UUID
    usuario_id: uuid.UUID
    dispositivo_id: uuid.UUID
    familia_id: uuid.UUID
    token_hash: bytes
    emitido_en: datetime
    expira_en: datetime


@dataclass(frozen=True)
class DispositivoGuardado:
    """Un dispositivo propio, sin push_token: nunca se lee para mostrarlo."""

    id: uuid.UUID
    plataforma: str
    nombre: str
    creado_en: datetime
    ultimo_uso_en: datetime | None
    revocado: bool


class RepositorioSesiones(Protocol):
    """sesion_refresh, indice_token (tipo refresh) y dispositivo, dentro de una transacción con
    app.usuario_id fijado: RLS (sesion_propia, dispositivo_propio) acota todo al usuario.

    Implementación: RepositorioSesionesSql (infrastructure/repositorio_sesiones.py).
    """

    def sesion_para_actualizar(self, sesion_id: uuid.UUID) -> SesionGuardada | None:
        """La sesión con su dispositivo y el estado de la cuenta, bloqueada (FOR UPDATE)."""
        ...

    def crear_refresh(self, nuevo: NuevoRefresh) -> None:
        """Inserta el token en sesion_refresh y su entrada en indice_token (tipo refresh)."""
        ...

    def marcar_usado(self, sesion_id: uuid.UUID, ahora: datetime) -> None: ...

    def revocar_familia(self, familia_id: uuid.UUID, motivo: str, ahora: datetime) -> int:
        """Revoca los tokens no revocados de la familia. Devuelve cuántos revocó."""
        ...

    def crear_dispositivo(self, usuario_id: uuid.UUID, nombre: str, ahora: datetime) -> uuid.UUID:
        """Crea un dispositivo web con creado_en y ultimo_uso_en = ahora."""
        ...

    def tocar_dispositivo(self, dispositivo_id: uuid.UUID, ahora: datetime) -> None:
        """Fija ultimo_uso_en = ahora."""
        ...

    def dispositivo_para_actualizar(self, dispositivo_id: uuid.UUID) -> DispositivoGuardado | None:
        """El dispositivo propio, bloqueado. None si no existe o es de otro usuario (RLS)."""
        ...

    def revocar_dispositivo(self, dispositivo_id: uuid.UUID, ahora: datetime) -> None:
        """Fija revocado_en (si no lo tenía) y pone push_token = NULL."""
        ...

    def revocar_sesiones_de_dispositivo(self, dispositivo_id: uuid.UUID, motivo: str, ahora: datetime) -> int:
        """Revoca los tokens no revocados del dispositivo. Devuelve cuántas familias (sesiones) cerró."""
        ...

    def revocar_todas(self, motivo: str, ahora: datetime) -> int:
        """MATU-57: revoca todos los tokens no revocados del usuario en contexto. Devuelve cuántas
        familias (sesiones) cerró."""
        ...

    def listar_dispositivos(self) -> list[DispositivoGuardado]:
        """Los dispositivos propios no revocados."""
        ...

    def guardar_push(self, dispositivo_id: uuid.UUID, push_token: str | None) -> bool:
        """Escribe push_token en el dispositivo propio no revocado. False si no hay tal dispositivo."""
        ...


# --- MATU-57: la cuenta, los códigos y su envío ----------------------------------------------------


@dataclass(frozen=True)
class DatosCuenta:
    """Lo que la recuperación y el perfil leen de la cuenta propia. Nunca se registra."""

    id: uuid.UUID
    nombre: str
    email: str
    telefono: str | None
    estado: str
    celular_verificado_en: datetime | None
    celular_canal: str

    def __repr__(self) -> str:
        return f"DatosCuenta(id={self.id})"


class RepositorioCuenta(Protocol):
    """La fila de usuario del contexto (RLS usuario_propio_leer y usuario_propio_editar).

    Implementación: RepositorioCuentaSql."""

    def datos(self) -> DatosCuenta | None: ...

    def cambiar_contrasena(self, password_hash: str, ahora: datetime) -> None: ...

    def marcar_celular_verificado(self, ahora: datetime, canal: str) -> None: ...

    def ultima_aceptacion(self) -> AceptacionPolitica | None:
        """MATU-75: la última aceptación de la política de la cuenta del contexto (RLS aceptacion_propia_leer).
        None si la cuenta no tiene registro."""
        ...


class EnviadorCodigos(Protocol):
    """Envía un mensaje a un celular o a un correo (decisión 82).

    En el semestre la única implementación es EnviadorSimulado (infrastructure/enviador_simulado.py):
    no envía nada. El destino y el mensaje nunca van a un log de la aplicación.
    """

    def enviar(self, canal: Canal, destino: str, mensaje: str) -> None: ...


class AlmacenCodigos(Protocol):
    """Los códigos vigentes, por clave (la huella del usuario y el propósito). Solo la huella del código.

    Implementaciones: AlmacenCodigosRedis (infrastructure/recuperacion_redis.py) y AlmacenCodigosEnMemoria
    (tests/dobles). Cada método lanza ContadoresNoDisponibles si el almacén no responde.
    """

    def guardar(self, clave: str, codigo: CodigoGuardado) -> None:
        """Guarda el código y reemplaza al anterior con sus intentos. Vence en codigo.expira_en."""
        ...

    def leer(self, clave: str) -> CodigoGuardado | None: ...

    def sumar_intento(self, clave: str) -> int:
        """Suma un intento al código vigente y devuelve cuántos van. 0 si no hay código."""
        ...

    def consumir(self, clave: str) -> bool:
        """Borra el código. True solo para quien lo borró: un segundo uso concurrente recibe False."""
        ...


class ContadoresEnvio(Protocol):
    """Envíos por huella (cuenta, destino o IP), con ventanas fijas de una hora y de un día."""

    def leer(self, huella: str) -> EnviosRecientes: ...

    def sumar(self, huella: str, ahora: datetime) -> None: ...


class TransaccionIam(Protocol):
    """Una transacción: el repositorio de sesiones y la auditoría comparten la misma sesión."""

    @property
    def sesiones(self) -> RepositorioSesiones: ...

    @property
    def cuenta(self) -> RepositorioCuenta: ...

    @property
    def auditoria(self) -> RegistroAuditoria: ...


class UnidadIam(Protocol):
    """Abre las transacciones de la sesión y de los dispositivos.

    Implementación: UnidadIamSql (infrastructure/repositorio_sesiones.py).
    """

    def resolver_refresh(self, token_hash: bytes) -> RefreshIndexado | None:
        """Busca el hash en indice_token (tipo refresh, sin RLS), sin contexto de usuario."""
        ...

    def transaccion(self, usuario_id: uuid.UUID | None) -> AbstractContextManager[TransaccionIam]:
        """Una transacción con app.usuario_id fijado (o sin usuario). Commit al salir sin error."""
        ...

    def conservar(self, limites: LimitesConservacion) -> tuple[int, int]:
        """Con app.rol = 'operacion', llama a iam_conservar. Devuelve (sesiones, dispositivos) borrados."""
        ...
