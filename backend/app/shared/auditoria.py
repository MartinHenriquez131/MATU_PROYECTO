"""Tipos de la auditoría transversal (MATU-14, RF-08).

Toda lectura y escritura de la ficha, y cada acción sensible sobre el consentimiento y el acceso de
relevo, deja una fila en ``auditoria``. Este archivo define QUÉ se puede registrar, con catálogos
cerrados. El puerto que lo registra es ``RegistroAuditoria`` (app/shared/puertos.py), y su adaptador
SQL es ``RegistroAuditoriaSql`` (app/shared/auditoria_sql.py).

Reglas que fijan los tipos, y no la disciplina de quien los usa:

- Acción, motivo, actor y entidad son enumerados. Un str libre no pasa: el motivo queda en la
  auditoría 3 años y un texto libre podría guardar un dato de salud que no se puede borrar
  (modelo de datos, acceso_relevo, decisión 16).
- La entrada lleva solo identificadores. Nada derivado del contenido de la ficha: ni texto, ni
  ETag, ni versión, ni hash, ni largo.
- No hay campo de IP ni de user agent: la IP no se guarda (decisión 27 del contrato de MATU-09).
- grupo_id es obligatorio, salvo en las acciones de la cuenta (ACCIONES_DE_CUENTA, MATU-38): la
  sesión y los dispositivos no pertenecen a una familia. RLS (auditoria_insertar, auditoria_relevo)
  acepta una entrada en el grupo del contexto o sin grupo.
- detalle solo admite dos datos tipados (MATU-38): la huella del email de un inicio fallido y la
  cantidad de sesiones revocadas al sacar un dispositivo. Nunca el email, la IP, un token ni texto.
- El momento no viaja en la entrada: lo pone el adaptador con el puerto Reloj.

Solo biblioteca estándar: se importa desde domain/ y application/ de cualquier módulo.
"""

import re
import uuid
from dataclasses import dataclass
from enum import StrEnum


class AccionAuditoria(StrEnum):
    """Las acciones que se registran. Agregar una exige cambiar este catálogo y su prueba."""

    PLAN_LEER = "plan.leer"
    PLAN_EDITAR = "plan.editar"
    CONSENTIMIENTO_OTORGAR = "consentimiento.otorgar"
    CONSENTIMIENTO_REVOCAR = "consentimiento.revocar"
    RELEVO_COMPARTIR = "relevo.compartir"
    RELEVO_REVOCAR = "relevo.revocar"
    RELEVO_PRESENTAR = "relevo.presentar"
    RELEVO_CANJE = "relevo.canje"
    RELEVO_PIN_INCORRECTO = "relevo.pin_incorrecto"
    RELEVO_BLOQUEO = "relevo.bloqueo"
    RELEVO_ABRIR = "relevo.abrir"
    # MATU-38: la sesión y los dispositivos. La renovación del refresh no se audita
    SESION_INICIAR = "sesion.iniciar"
    SESION_INICIO_FALLIDO = "sesion.inicio_fallido"
    SESION_REUTILIZACION_DETECTADA = "sesion.reutilizacion_detectada"
    SESION_CERRAR = "sesion.cerrar"
    DISPOSITIVO_SACAR = "dispositivo.sacar"
    DISPOSITIVO_PUSH_REGISTRAR = "dispositivo.push_registrar"
    DISPOSITIVO_PUSH_BORRAR = "dispositivo.push_borrar"


# Las acciones de la cuenta, que no pertenecen a una familia: van sin grupo_id (MATU-38)
ACCIONES_DE_CUENTA = frozenset(
    {
        AccionAuditoria.SESION_INICIAR,
        AccionAuditoria.SESION_INICIO_FALLIDO,
        AccionAuditoria.SESION_REUTILIZACION_DETECTADA,
        AccionAuditoria.SESION_CERRAR,
        AccionAuditoria.DISPOSITIVO_SACAR,
        AccionAuditoria.DISPOSITIVO_PUSH_REGISTRAR,
        AccionAuditoria.DISPOSITIVO_PUSH_BORRAR,
    }
)


class MotivoAuditoria(StrEnum):
    """Por qué se comparte la ficha. Enumerado sin texto libre (decisión 16 del contrato de MATU-09)."""

    SALGO_UNAS_HORAS = "salgo_unas_horas"
    FIN_DE_SEMANA_FUERA = "fin_de_semana_fuera"
    TURNO_DE_NOCHE = "turno_de_noche"
    OTRO = "otro"


class ActorTipo(StrEnum):
    """Quién actúa. El CHECK de la base admite más (comercio, repartidor, operacion, sistema): se
    agregan aquí cuando una historia los necesite."""

    USUARIO = "usuario"
    RELEVO = "relevo"
    # MATU-38: un inicio de sesión fallido no tiene un usuario conocido (actor_ref vacío)
    SISTEMA = "sistema"


class EntidadAuditoria(StrEnum):
    """Sobre qué se actúa: el nombre de la tabla de la fila que identifica entidad_id."""

    PLAN_CUIDADO = "plan_cuidado"
    PLAN_SECCION = "plan_seccion"
    CONSENTIMIENTO = "consentimiento"
    ACCESO_RELEVO = "acceso_relevo"
    # MATU-38
    USUARIO = "usuario"
    DISPOSITIVO = "dispositivo"


_HUELLA = re.compile(r"[0-9a-f]{64}")


def _exigir(nombre: str, valor: object, tipo: type) -> None:
    # isinstance y no igualdad: "plan.leer" == AccionAuditoria.PLAN_LEER, pero un str suelto no pasa
    if not isinstance(valor, tipo):
        raise TypeError(f"{nombre} debe ser {tipo.__name__}, no {type(valor).__name__}")


@dataclass(frozen=True, slots=True)
class EntradaAuditoria:
    """Una fila de auditoría, antes de registrarse. Inmutable.

    - ``grupo_id``: la familia dueña de lo que se tocó. Obligatorio.
    - ``actor_tipo`` y ``actor_ref``: quién actuó, tomado del contexto autenticado, nunca del cuerpo
      de la petición. Con USUARIO, el usuario_id de la sesión de grupo. Con RELEVO, el id del
      acceso de relevo canjeado (el relevo no es usuario).
    - ``accion``, ``entidad`` y ``entidad_id``: qué se hizo y sobre qué fila. entidad_id puede faltar
      cuando la fila aún no existe o no aplica.
    - ``motivo``: solo con catálogo, por ejemplo al compartir la ficha.
    - ``request_id``: el de la petición, para cruzar con los logs.
    - ``huella_email``: solo en sesion.inicio_fallido, la huella HMAC-SHA-256 del email en hex (64).
    - ``sesiones_revocadas``: solo en dispositivo.sacar, un entero de 0 en adelante.

    grupo_id puede faltar solo en ACCIONES_DE_CUENTA, y actor_ref solo con el actor SISTEMA.

    Lanza TypeError si un campo no es del tipo declarado (un str libre en vez del enumerado, o
    un grupo_id ausente).
    """

    grupo_id: uuid.UUID | None
    actor_tipo: ActorTipo
    actor_ref: uuid.UUID | None
    accion: AccionAuditoria
    entidad: EntidadAuditoria
    entidad_id: uuid.UUID | None = None
    motivo: MotivoAuditoria | None = None
    request_id: str | None = None
    huella_email: str | None = None
    sesiones_revocadas: int | None = None

    def __post_init__(self) -> None:
        _exigir("accion", self.accion, AccionAuditoria)
        _exigir("actor_tipo", self.actor_tipo, ActorTipo)
        if self.grupo_id is not None or self.accion not in ACCIONES_DE_CUENTA:
            _exigir("grupo_id", self.grupo_id, uuid.UUID)
        if self.actor_ref is not None or self.actor_tipo is not ActorTipo.SISTEMA:
            _exigir("actor_ref", self.actor_ref, uuid.UUID)
        _exigir("entidad", self.entidad, EntidadAuditoria)
        if self.entidad_id is not None:
            _exigir("entidad_id", self.entidad_id, uuid.UUID)
        if self.motivo is not None:
            _exigir("motivo", self.motivo, MotivoAuditoria)
        if self.request_id is not None:
            _exigir("request_id", self.request_id, str)
        if self.huella_email is not None:
            _exigir("huella_email", self.huella_email, str)
            if self.accion is not AccionAuditoria.SESION_INICIO_FALLIDO or not _HUELLA.fullmatch(self.huella_email):
                raise TypeError("huella_email solo va en sesion.inicio_fallido, como 64 caracteres hex")
        if self.sesiones_revocadas is not None:
            if isinstance(self.sesiones_revocadas, bool) or not isinstance(self.sesiones_revocadas, int):
                raise TypeError("sesiones_revocadas debe ser int")
            if self.accion is not AccionAuditoria.DISPOSITIVO_SACAR or self.sesiones_revocadas < 0:
                raise TypeError("sesiones_revocadas solo va en dispositivo.sacar, como entero no negativo")

    def detalle(self) -> dict[str, object] | None:
        """El contenido de la columna auditoria.detalle, o None si la entrada no lleva detalle."""
        datos: dict[str, object] = {}
        if self.huella_email is not None:
            datos["huella_email"] = self.huella_email
        if self.sesiones_revocadas is not None:
            datos["sesiones_revocadas"] = self.sesiones_revocadas
        return datos or None
