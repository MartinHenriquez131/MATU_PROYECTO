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
- grupo_id es obligatorio: toda entrada de este servicio pertenece a una familia, y RLS
  (auditoria_insertar, auditoria_relevo) solo la acepta en el grupo del contexto.
- El momento no viaja en la entrada: lo pone el adaptador con el puerto Reloj.

Solo biblioteca estándar: se importa desde domain/ y application/ de cualquier módulo.
"""

import uuid
from dataclasses import dataclass
from enum import StrEnum


class AccionAuditoria(StrEnum):
    """Las acciones que se registran. Agregar una exige cambiar este catálogo y su prueba."""

    PLAN_LEER = "plan.leer"
    PLAN_EDITAR = "plan.editar"
    CONSENTIMIENTO_OTORGAR = "consentimiento.otorgar"
    RELEVO_COMPARTIR = "relevo.compartir"
    RELEVO_REVOCAR = "relevo.revocar"
    RELEVO_PRESENTAR = "relevo.presentar"
    RELEVO_CANJE = "relevo.canje"
    RELEVO_PIN_INCORRECTO = "relevo.pin_incorrecto"
    RELEVO_BLOQUEO = "relevo.bloqueo"
    RELEVO_ABRIR = "relevo.abrir"


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


class EntidadAuditoria(StrEnum):
    """Sobre qué se actúa: el nombre de la tabla de la fila que identifica entidad_id."""

    PLAN_CUIDADO = "plan_cuidado"
    PLAN_SECCION = "plan_seccion"
    CONSENTIMIENTO = "consentimiento"
    ACCESO_RELEVO = "acceso_relevo"


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

    Lanza TypeError si un campo no es del tipo declarado (un str libre en vez del enumerado, o
    un grupo_id ausente).
    """

    grupo_id: uuid.UUID
    actor_tipo: ActorTipo
    actor_ref: uuid.UUID
    accion: AccionAuditoria
    entidad: EntidadAuditoria
    entidad_id: uuid.UUID | None = None
    motivo: MotivoAuditoria | None = None
    request_id: str | None = None

    def __post_init__(self) -> None:
        _exigir("grupo_id", self.grupo_id, uuid.UUID)
        _exigir("actor_tipo", self.actor_tipo, ActorTipo)
        _exigir("actor_ref", self.actor_ref, uuid.UUID)
        _exigir("accion", self.accion, AccionAuditoria)
        _exigir("entidad", self.entidad, EntidadAuditoria)
        if self.entidad_id is not None:
            _exigir("entidad_id", self.entidad_id, uuid.UUID)
        if self.motivo is not None:
            _exigir("motivo", self.motivo, MotivoAuditoria)
        if self.request_id is not None:
            _exigir("request_id", self.request_id, str)
