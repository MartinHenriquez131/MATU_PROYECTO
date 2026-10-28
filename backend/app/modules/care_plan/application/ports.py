"""Puertos del módulo care_plan (ADR-021).

CustodiaClaves es el primer nivel del sobre-cifrado de la ficha (arquitectura 11.4, ADR-014
y ADR-016): la clave maestra (KEK) vive fuera del servidor de aplicación y solo se usa para
envolver y desenvolver la clave de datos (DEK) de cada persona cuidada. La DEK envuelta y la
versión de KEK que la envolvió se guardan en clave_datos (dek_cifrada_con_kek, kek_version).

Implementaciones: CustodiaEnMemoria (tests/dobles). El adaptador real llega cuando se decida
el proveedor de custodia (ADR-019).

CifradorSecciones es el segundo nivel (MATU-11): cifra cada sección de la ficha con AES-256-GCM y
la DEK de la persona. RepositorioClaves guarda y lee la fila de clave_datos.
"""

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from app.modules.care_plan.domain.cifrado import ClaveGuardada, SeccionCifrada


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
