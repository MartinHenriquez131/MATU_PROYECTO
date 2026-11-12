"""Los enlaces de relevo que cada persona compartió en el grupo (MATU-42, C13, C19, decisión 305).

Implementa EnlacesDeRelevo de care_circle; app.main lo registra con registrar_enlaces. Corre en la transacción de la
petición de sacar, salir o cambiar el rol, con su sesión y su registro de auditoría:

- vigentes_por_persona: cuántos accesos no cortados y no vencidos compartió cada usuario (acceso_relevo.otorgado_por).
  acceso_familia_leer (0020) los muestra solo a quien ve el plan; para los demás la cuenta queda en 0.
- cortar_de: los corta con revocado_en en el acceso y en indice_token y relevo.revocar por acceso, como el corte de
  MATU-20 (RepositorioAccesosSQL.revocar). acceso_familia_cortar exige que quien actúa sea admin o cuidador: por eso
  se corta antes de degradar o retirar la membresía.

No lee texto de la ficha ni datos del relevo. Nada va a los logs.
"""

import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.care_plan.infrastructure.repositorio_accesos import RepositorioAccesosSQL
from app.shared.puertos import RegistroAuditoria

_VIGENTES = text(
    "SELECT otorgado_por, count(*) AS n FROM acceso_relevo"
    " WHERE grupo_id = :grupo_id AND revocado_en IS NULL AND expira_en > :ahora GROUP BY otorgado_por"
)

# En un orden fijo y bloqueados: dos cortes a la vez no fijan dos instantes distintos
_DE_LA_PERSONA = text(
    "SELECT id FROM acceso_relevo WHERE grupo_id = :grupo_id AND otorgado_por = :usuario_id"
    " AND revocado_en IS NULL AND expira_en > :ahora ORDER BY id FOR UPDATE"
)


class EnlacesOtorgados:
    def __init__(self, sesion: Session, grupo_id: uuid.UUID, registro: RegistroAuditoria) -> None:
        self._sesion = sesion
        self._grupo_id = grupo_id
        self._accesos = RepositorioAccesosSQL(sesion, grupo_id, registro)

    def vigentes_por_persona(self, ahora: datetime) -> dict[uuid.UUID, int]:
        filas = self._sesion.execute(_VIGENTES, {"grupo_id": self._grupo_id, "ahora": ahora}).all()
        return {f.otorgado_por: int(f.n) for f in filas}

    def cortar_de(self, otorgado_por: uuid.UUID, ahora: datetime, actor_id: uuid.UUID, request_id: str | None) -> int:
        ids = self._sesion.execute(
            _DE_LA_PERSONA, {"grupo_id": self._grupo_id, "usuario_id": otorgado_por, "ahora": ahora}
        ).scalars().all()
        for acceso_id in ids:
            self._accesos.revocar(acceso_id, ahora, actor_id, request_id)
        return len(ids)
