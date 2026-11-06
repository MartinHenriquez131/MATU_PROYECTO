"""Esquemas de GET y PUT /v1/yo/avisos (MATU-41, decisión 111). Contrato: docs/api/openapi.json.

El cuerpo del PUT trae los dos canales, como booleanos estrictos ("true", 1 o null responden 422), y
extra="forbid": otro campo (por ejemplo sms o usuario_id) responde 422. El 422 nunca repite el valor.
"""

from pydantic import BaseModel, ConfigDict, Field, StrictBool


class PreferenciaAvisosVista(BaseModel):
    """Si la persona recibe los avisos de un insumo que se está acabando, por canal. Sin preferencia
    guardada, lo que corresponde a sus roles: activo si es admin o cuidador en algún grupo."""

    model_config = ConfigDict(extra="forbid")

    correo: StrictBool = Field(description="Avisos por correo")
    push: StrictBool = Field(
        description="Avisos por notificación, en los dispositivos donde se activó (PUT /v1/dispositivos/actual/push)"
    )
