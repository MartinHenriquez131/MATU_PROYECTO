"""El efecto del retiro de ``consumo`` (MATU-44, decisiones 124 y 128). Lo registra app.main en care_circle.

Con la sesión de la petición: RLS de 0009 y 0011 deja cerrar alertas y borrar perfiles solo a admin y
cuidador, los mismos que retiran. No lee nombre_libre ni cantidades, y nada se registra en los logs.
"""

import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.consumption.application.retiro import descartar_por_retiro
from app.modules.consumption.domain.alerta import EstadoAlerta
from app.modules.consumption.infrastructure.repositorio_alertas import RepositorioAlertasSQL
from app.shared.puertos import RegistroAuditoria

_ABIERTAS = text(
    "SELECT a.id FROM alerta_quiebre a JOIN perfil_consumo p ON p.id = a.perfil_id"
    " WHERE p.grupo_id = :grupo_id AND p.persona_cuidada_id = :persona_id"
    " AND a.estado IN ('pendiente', 'notificada') ORDER BY a.id FOR UPDATE OF a"
)
_BORRAR_PERFILES = text("DELETE FROM perfil_consumo WHERE grupo_id = :grupo_id AND persona_cuidada_id = :persona_id")


class _ConsumoSQL:
    def __init__(self, sesion: Session, grupo_id: uuid.UUID) -> None:
        self._sesion = sesion
        self._grupo_id = grupo_id
        self._alertas = RepositorioAlertasSQL(sesion, grupo_id)

    def abiertas_de_la_persona(self, persona_id: uuid.UUID) -> list[uuid.UUID]:
        filas = self._sesion.execute(_ABIERTAS, {"grupo_id": self._grupo_id, "persona_id": persona_id}).all()
        return [f.id for f in filas]

    def cerrar(self, alerta_id: uuid.UUID, estado: EstadoAlerta, ahora: datetime) -> object:
        return self._alertas.cerrar(alerta_id, estado, ahora)

    def borrar_perfiles_de_la_persona(self, persona_id: uuid.UUID) -> int:
        resultado = self._sesion.execute(_BORRAR_PERFILES, {"grupo_id": self._grupo_id, "persona_id": persona_id})
        return int(getattr(resultado, "rowcount", 0))


class EfectoRetiroConsumo:
    def __init__(self, sesion: Session, grupo_id: uuid.UUID, registro: RegistroAuditoria) -> None:
        self._grupo_id = grupo_id
        self._registro = registro
        self._consumo = _ConsumoSQL(sesion, grupo_id)

    def aplicar(self, persona_id: uuid.UUID, ahora: datetime, usuario_id: uuid.UUID, request_id: str | None) -> int:
        descartar_por_retiro(self._grupo_id, persona_id, ahora, usuario_id, request_id, self._consumo, self._registro)
        return 0  # el retiro de consumo no corta enlaces

    def borrar_vencido(self, persona_id: uuid.UUID, ahora: datetime, request_id: str | None) -> None:
        self._consumo.borrar_perfiles_de_la_persona(persona_id)

    def destruido_en(self, persona_id: uuid.UUID) -> datetime | None:
        return None  # un perfil borrado no deja rastro: la vista usa el plazo
