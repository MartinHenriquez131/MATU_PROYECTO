"""El efecto del retiro de ``plan_cuidado`` (MATU-44, decisiones 124, 128 y 130).

Lo registra app.main en care_circle (infrastructure/efectos_retiro.py). Corre en la transacción de la
petición de retiro o de autorización, con su sesión y su registro de auditoría:

- aplicar: corta los accesos de relevo de la persona (cortar_por_retiro), cada uno con relevo.revocar.
- antes_de_otorgar: al volver a autorizar la ficha.
  - Si el retiro anterior cumplió 90 días y la tarea no destruyó todavía la clave, la destruye y registra
    clave.destruir con actor sistema y sin detalle (decisión 128).
  - Si la persona quedó con la clave destruida, descarta las secciones cifradas con ella y deja el plan en
    0 de 3: la ficha empieza en blanco y la próxima escritura crea una clave nueva (P8, decisión 130). Lo
    borrado nunca vuelve a leerse.
- borrar (MATU-72, decisión 150): al borrar a la persona, en este orden y con el instante del borrado:
  1. corta los accesos con la misma regla del retiro (cortar_por_retiro, FOR UPDATE OF a) y deja sin el nombre
     de pila de la persona todos los accesos de su plan. En la misma sentencia vacía el teléfono del relevo y fija
     telefono_borrado_en con el instante del borrado (MATU-46, D-46-3 a): no espera los 30 días. Un teléfono que la
     tarea ya vació conserva su instante;
  2. destruye la clave vigente, con clave.destruir y actor el usuario, en una sentencia;
  3. después, en otra sentencia, borra todas las filas de plan_seccion de la persona y deja el plan en 0 de 3
     (C6). En READ COMMITTED cada sentencia toma una foto nueva: una sección que se confirmó mientras el UPDATE
     de la clave esperaba su bloqueo también se borra. En una sola sentencia (como plan_destruir_claves) quedaría.

No lee ni escribe texto de la ficha. Nada se registra en los logs.
"""

import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.care_circle.domain.borrado import NOMBRE_BORRADO
from app.modules.care_plan.application.relevo import cortar_por_retiro
from app.modules.care_plan.domain.cifrado import EstadoClave, estado_clave
from app.modules.care_plan.infrastructure.repositorio_accesos import RepositorioAccesosSQL
from app.modules.care_plan.infrastructure.repositorio_claves import RepositorioClavesSQL
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.puertos import RegistroAuditoria

# Las secciones de la clave destruida no se pueden leer nunca más: se descartan con el plan en blanco
_DESCARTAR_SECCIONES = text(
    "DELETE FROM plan_seccion s USING plan_cuidado p"
    " WHERE s.plan_id = p.id AND p.persona_cuidada_id = :persona_id AND p.grupo_id = :grupo_id"
)
_PLAN_EN_BLANCO = text(
    "UPDATE plan_cuidado SET completitud_pct = 0, actualizado_en = :ahora"
    " WHERE persona_cuidada_id = :persona_id AND grupo_id = :grupo_id"
)
# MATU-72 (D5): los accesos se conservan (D4), sin el nombre de pila de la persona. MATU-46 (D-46-3 a): y sin el
# teléfono del relevo, desde ese instante. Solo los accesos del plan de esta persona, nunca los de otra del grupo
_ACCESOS_SIN_NOMBRE_NI_TELEFONO = text(
    "UPDATE acceso_relevo a SET nombre_pila_persona = :fijo, otorgado_a_telefono = NULL,"
    " telefono_borrado_en = COALESCE(a.telefono_borrado_en, :ahora) FROM plan_cuidado p"
    " WHERE a.plan_id = p.id AND p.persona_cuidada_id = :persona_id AND p.grupo_id = :grupo_id"
    " AND a.grupo_id = :grupo_id"
    " AND (a.nombre_pila_persona IS DISTINCT FROM :fijo OR a.otorgado_a_telefono IS NOT NULL)"
)


class EfectoRetiroFicha:
    def __init__(self, sesion: Session, grupo_id: uuid.UUID, registro: RegistroAuditoria) -> None:
        self._sesion = sesion
        self._grupo_id = grupo_id
        self._registro = registro
        self._accesos = RepositorioAccesosSQL(sesion, grupo_id, registro)
        self._claves = RepositorioClavesSQL(sesion)

    def aplicar(self, persona_id: uuid.UUID, ahora: datetime, usuario_id: uuid.UUID, request_id: str | None) -> int:
        return cortar_por_retiro(persona_id, ahora, usuario_id, request_id, self._accesos)

    def antes_de_otorgar(
        self, persona_id: uuid.UUID, ahora: datetime, request_id: str | None, plazo_cumplido: bool
    ) -> None:
        if plazo_cumplido:
            self._destruir(persona_id, ahora, request_id)
        if estado_clave(self._claves.obtener(persona_id)) is EstadoClave.DESTRUIDA:
            parametros = {"persona_id": persona_id, "grupo_id": self._grupo_id, "ahora": ahora}
            self._sesion.execute(_DESCARTAR_SECCIONES, parametros)
            self._sesion.execute(_PLAN_EN_BLANCO, parametros)

    def borrar(self, persona_id: uuid.UUID, ahora: datetime, usuario_id: uuid.UUID, request_id: str | None) -> int:
        cortados = cortar_por_retiro(persona_id, ahora, usuario_id, request_id, self._accesos)
        parametros = {"persona_id": persona_id, "grupo_id": self._grupo_id, "ahora": ahora}
        self._sesion.execute(_ACCESOS_SIN_NOMBRE_NI_TELEFONO, {**parametros, "fijo": NOMBRE_BORRADO})
        # C6: la clave en una sentencia y las secciones en otra, después
        self._destruir(persona_id, ahora, request_id, usuario_id)
        self._sesion.execute(_DESCARTAR_SECCIONES, parametros)
        self._sesion.execute(_PLAN_EN_BLANCO, parametros)
        return cortados

    def _destruir(
        self, persona_id: uuid.UUID, ahora: datetime, request_id: str | None, usuario_id: uuid.UUID | None = None
    ) -> None:
        """Destruye la clave vigente y registra clave.destruir: actor sistema al autorizar tarde (decisión 128),
        actor el usuario en el borrado (MATU-72)."""
        clave_id = self._claves.destruir(persona_id, ahora)
        if clave_id is None:
            return
        self._registro.registrar(
            EntradaAuditoria(
                grupo_id=self._grupo_id,
                actor_tipo=ActorTipo.SISTEMA if usuario_id is None else ActorTipo.USUARIO,
                actor_ref=usuario_id,
                accion=AccionAuditoria.CLAVE_DESTRUIR,
                entidad=EntidadAuditoria.CLAVE_DATOS,
                entidad_id=clave_id,
                request_id=request_id,
                persona_cuidada_id=persona_id,
            )
        )
