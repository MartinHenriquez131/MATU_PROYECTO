"""Puertos del módulo care_plan (ADR-021).

CustodiaClaves es el primer nivel del sobre-cifrado de la ficha (arquitectura 11.4, ADR-014
y ADR-016): la clave maestra (KEK) vive fuera del servidor de aplicación y solo se usa para
envolver y desenvolver la clave de datos (DEK) de cada persona cuidada. La DEK envuelta y la
versión de KEK que la envolvió se guardan en clave_datos (dek_cifrada_con_kek, kek_version).

Implementaciones: CustodiaEnMemoria (tests/dobles) y CustodiaKekEntorno
(infrastructure/custodia_kek_entorno.py), que lee la KEK de la configuración: solo para el semestre y
datos sintéticos (decisión D-A de Jorge del 28-10, desvío explícito del ADR-016). El adaptador de
producción llega cuando se decida el proveedor de custodia (ADR-019).

CifradorSecciones es el segundo nivel (MATU-11): cifra cada sección de la ficha con AES-256-GCM y
la DEK de la persona. RepositorioClaves guarda y lee la fila de clave_datos.

RepositorioFicha y AuditoriaFicha son de la ficha de relevo (MATU-12): la persistencia del plan y de
sus secciones cifradas, y el punto de enganche de la auditoría plan.leer y plan.editar (MATU-14).
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.modules.care_plan.domain.cifrado import ClaveGuardada, SeccionCifrada
from app.modules.care_plan.domain.ficha import Autor


@dataclass(frozen=True)
class DekEnvuelta:
    """Una DEK cifrada con la KEK, tal como se guarda en clave_datos. La DEK envuelta no sale
    en el repr, igual que en ClaveGuardada."""

    dek_cifrada: bytes = field(repr=False)
    kek_version: int


class KekNoDisponible(Exception):
    """La versión de KEK pedida no existe o fue destruida.

    Nunca se responde generando una clave de reemplazo: eso rompería el borrado criptográfico.
    """


class DekCifradaInvalida(Exception):
    """La DEK cifrada no corresponde a la versión de KEK indicada, o fue alterada."""


class CustodiaClaves(Protocol):
    """Custodia de la clave maestra. La KEK nunca sale de la custodia: solo envuelve y desenvuelve."""

    def envolver(self, dek: bytes) -> DekEnvuelta:
        """Cifra la DEK con la versión vigente de la KEK y devuelve la DEK cifrada con esa versión.

        Lanza KekNoDisponible si no hay una KEK vigente.
        """
        ...

    def desenvolver(self, dek_cifrada: bytes, kek_version: int) -> bytes:
        """Descifra la DEK con la versión de KEK con que fue envuelta.

        Lanza KekNoDisponible si esa versión no existe o fue destruida, y DekCifradaInvalida
        si la DEK cifrada no corresponde a esa versión.
        """
        ...


class RepositorioClaves(Protocol):
    """Persistencia de clave_datos, dentro de la transacción de la petición (sesion_tenant).

    Trabaja con la misma sesión con que se escriben las secciones: crear la DEK y escribir la
    primera sección quedan en una sola transacción. RLS acota cada consulta al grupo en contexto
    o al acceso de relevo vigente.

    No hay método para destruir ni para borrar la clave: quién puede destruirla se decide más
    adelante, y matu_app no tiene DELETE sobre clave_datos (migración 0003).

    Implementación: RepositorioClavesSQL (infrastructure/repositorio_claves.py).
    """

    def obtener(self, persona_cuidada_id: uuid.UUID, *, para_escribir: bool = False) -> ClaveGuardada | None:
        """La clave de la persona, vigente o destruida, o None si todavía no existe.

        Con ``para_escribir`` bloquea la fila en modo compartido hasta el fin de la transacción:
        una destrucción concurrente espera a que termine la escritura.
        """
        ...

    def crear(self, grupo_id: uuid.UUID, persona_cuidada_id: uuid.UUID, envuelta: DekEnvuelta) -> bool:
        """Guarda la DEK envuelta como la clave de la persona, si la persona todavía no tiene una.

        Devuelve False si ya existía una fila para la persona (vigente o destruida), por ejemplo
        porque otra transacción la creó primero: entonces no escribe nada. Se apoya en el UNIQUE
        de persona_cuidada_id, así que dos primeras escrituras concurrentes dejan una sola DEK.
        """
        ...


class CifradorSecciones(Protocol):
    """Cifra y descifra las secciones de la ficha con la DEK de la persona (MATU-11, ADR-014).

    El texto en claro y la DEK viven solo durante la llamada: no se guardan, no se registran en
    los logs y no aparecen en los errores.

    Errores (todos de app.modules.care_plan.domain.cifrado, con mensaje fijo):
    - ClaveDestruida: la clave de la persona fue destruida. Al escribir y al leer.
    - ClaveInexistente: se pidió leer y la persona nunca tuvo clave.
    - ClaveNoDisponible: la custodia no pudo envolver o desenvolver la DEK.
    - SeccionIlegible: el texto cifrado fue alterado o se movió a otra sección o a otro plan.
    - TipoSeccionInvalido: el tipo no es uno de los de plan_seccion.

    Implementación: CifradorAesGcm (infrastructure/cifrador_aes_gcm.py).
    """

    def cifrar(
        self, *, grupo_id: uuid.UUID, persona_cuidada_id: uuid.UUID, plan_id: uuid.UUID, tipo: str, texto: str
    ) -> SeccionCifrada:
        """Cifra el texto de la sección ``tipo`` del plan, con un nonce nuevo.

        Si la persona no tiene clave, la crea en la misma transacción (primera escritura).
        """
        ...

    def descifrar(
        self, *, persona_cuidada_id: uuid.UUID, plan_id: uuid.UUID, tipo: str, seccion: SeccionCifrada
    ) -> str:
        """Descifra la sección ``tipo`` del plan. Nunca crea una clave."""
        ...


# --- Ficha de relevo (MATU-12, RF-02) -------------------------------------------------------------


@dataclass(frozen=True)
class PlanGuardado:
    id: uuid.UUID


@dataclass(frozen=True)
class SeccionGuardada:
    """Una sección de la ficha tal como está en plan_seccion: cifrada, nunca en claro."""

    tipo: str
    cifrada: SeccionCifrada
    version: int
    # None si la cuenta de quien la escribió ya no existe o no es visible para el grupo
    actualizado_por: Autor | None
    actualizado_en: datetime


class RepositorioFicha(Protocol):
    """Persistencia de plan_cuidado y de las secciones de la ficha, en la transacción de la petición.

    Trabaja con la sesión del contexto de grupo (sesion_de_grupo): RLS acota plan_cuidado y
    plan_seccion al grupo, y solo para quien puede ver el plan. Nunca recibe ni devuelve texto en
    claro: solo SeccionCifrada.

    Implementación: RepositorioFichaSQL (infrastructure/repositorio_ficha.py).
    """

    def obtener_plan(self, persona_cuidada_id: uuid.UUID) -> PlanGuardado | None:
        """El plan de la persona, o None si nadie ha escrito su ficha todavía. Leer no lo crea."""
        ...

    def crear_plan(
        self, plan_id: uuid.UUID, grupo_id: uuid.UUID, persona_cuidada_id: uuid.UUID, usuario_id: uuid.UUID,
        ahora: datetime,
    ) -> bool:
        """Crea el plan con modo 'ficha_relevo', si la persona todavía no tiene uno.

        Devuelve False si ya existía (otra transacción lo creó primero): entonces no escribe nada.
        """
        ...

    def secciones(self, plan_id: uuid.UUID) -> list[SeccionGuardada]:
        """Las secciones de la ficha del plan (solo los tres tipos de la ficha), con su autor."""
        ...

    def version_para_escribir(self, plan_id: uuid.UUID, tipo: str) -> int | None:
        """La versión de la sección, bloqueada hasta el fin de la transacción, o None si no existe."""
        ...

    def insertar_seccion(
        self, plan_id: uuid.UUID, tipo: str, cifrada: SeccionCifrada, usuario_id: uuid.UUID, ahora: datetime
    ) -> bool:
        """Crea la sección con versión 1. False si ya existía (otra transacción la creó primero)."""
        ...

    def actualizar_seccion(
        self, plan_id: uuid.UUID, tipo: str, cifrada: SeccionCifrada, version: int, usuario_id: uuid.UUID,
        ahora: datetime,
    ) -> None:
        """Reemplaza el contenido cifrado de la sección y la deja en ``version``."""
        ...

    def campos_con_texto(self, plan_id: uuid.UUID) -> int:
        """Cuántas secciones de la ficha tienen texto, sin descifrarlas.

        AES-GCM conserva el largo: un campo vaciado se guarda cifrado con largo 0. Así la completitud
        se calcula sin abrir los otros campos.
        """
        ...

    def actualizar_plan(self, plan_id: uuid.UUID, completitud_pct: int, usuario_id: uuid.UUID, ahora: datetime) -> None:
        """Guarda la completitud, quién escribió y cuándo."""
        ...

    def autor(self, usuario_id: uuid.UUID) -> Autor | None:
        """El id y el nombre del usuario, nunca su email."""
        ...


@dataclass(frozen=True)
class EventoFicha:
    """Lo que la auditoría de MATU-14 necesita de una lectura o una escritura de la ficha.

    Solo identificadores: nunca el texto, el ETag ni el nombre de nadie.
    """

    grupo_id: uuid.UUID
    usuario_id: uuid.UUID
    persona_cuidada_id: uuid.UUID
    # None si se leyó una ficha que nadie ha escrito: todavía no hay plan
    plan_id: uuid.UUID | None
    # El campo escrito, o None en una lectura de la ficha completa
    campo: str | None
    request_id: str | None
    ocurrido_en: datetime


class AuditoriaFicha(Protocol):
    """Punto de enganche de la auditoría de la ficha (MATU-14): plan.leer y plan.editar.

    Los casos de uso lo llaman dentro de la transacción de la petición, después de leer o escribir y
    antes de responder: si la auditoría falla, la petición falla y la escritura se deshace. Nunca se
    llama cuando la petición se rechaza antes (401, 404, 403 o 422).

    Implementación de MATU-12: AuditoriaFichaPendiente (infrastructure/auditoria_ficha.py), que no
    escribe nada. MATU-14 la reemplaza por la que inserta en auditoria, sin tocar los casos de uso.
    """

    def registrar_lectura(self, evento: EventoFicha) -> None: ...

    def registrar_edicion(self, evento: EventoFicha) -> None: ...


# --- Acceso de relevo (MATU-18, RF-05) ------------------------------------------------------------------


class GeneradorCredencialesRelevo(Protocol):
    """El token (32 bytes aleatorios, 256 bits) y el PIN de 4 dígitos de un acceso nuevo.

    Implementación: GeneradorSecrets (infrastructure/credenciales_relevo.py), con el módulo secrets.
    """

    def token(self) -> bytes: ...

    def pin(self) -> str: ...


class HuellasRelevo(Protocol):
    """Lo único que se guarda del token y del PIN (contrato, notas para implementar).

    - El token: su SHA-256. 256 bits aleatorios no se recuperan por fuerza bruta.
    - El PIN: un HMAC-SHA-256 con pepper (PEPPER_PIN), ligado al acceso. 10.000 valores sí se
      recuperan con un hash simple: el pepper vive fuera de la base.

    Implementación: HuellasHmac (infrastructure/credenciales_relevo.py).
    """

    def huella_token(self, token: bytes) -> bytes: ...

    def huella_pin(self, acceso_id: uuid.UUID, pin: str) -> str: ...


@dataclass(frozen=True)
class AccesoNuevo:
    """La fila de acceso_relevo y de indice_token, sin el token ni el PIN en claro."""

    id: uuid.UUID
    grupo_id: uuid.UUID
    plan_id: uuid.UUID
    otorgado_por: uuid.UUID
    nombre_relevo: str
    telefono_relevo: str = field(repr=False)
    nombre_pila_persona: str
    nombre_pila_comparte: str
    campos: tuple[str, ...]
    motivo: str
    token_hash: bytes = field(repr=False)
    pin_hash: str = field(repr=False)
    creado_en: datetime
    expira_en: datetime
    request_id: str | None


@dataclass(frozen=True)
class AccesoListado:
    id: uuid.UUID
    nombre_relevo: str
    telefono_relevo: str | None = field(repr=False)
    campos: tuple[str, ...]
    motivo: str
    creado_en: datetime
    expira_en: datetime
    revocado_en: datetime | None
    pin_intentos_fallidos: int
    usos: int
    ultimo_uso_en: datetime | None
    otorgado_por: Autor | None


@dataclass(frozen=True)
class Posicion:
    """Dónde sigue la página siguiente: la lista va por (creado_en, id) descendente."""

    creado_en: datetime
    id: uuid.UUID


class RepositorioAccesos(Protocol):
    """Persistencia de acceso_relevo e indice_token, en la transacción de la petición.

    Trabaja con la sesión del contexto de grupo: la política acceso_familia acota acceso_relevo al
    grupo y a quien puede ver el plan. Nunca recibe el token ni el PIN en claro.

    Implementación: RepositorioAccesosSQL (infrastructure/repositorio_accesos.py).
    """

    def nombre_pila_persona(self, persona_cuidada_id: uuid.UUID) -> str | None: ...

    def nombre_usuario(self, usuario_id: uuid.UUID) -> str | None: ...

    def crear(self, acceso: AccesoNuevo) -> None:
        """Inserta el acceso, su fila de indice_token y la auditoría relevo.compartir."""
        ...

    def listar(
        self, plan_id: uuid.UUID, ahora: datetime, estado: str | None, despues_de: Posicion | None, limite: int
    ) -> list[AccesoListado]:
        """Hasta ``limite`` accesos del plan, del más nuevo al más antiguo, con ``estado`` si se pide."""
        ...
