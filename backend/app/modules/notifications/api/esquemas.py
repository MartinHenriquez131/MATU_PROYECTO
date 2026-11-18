"""Esquemas de GET y PUT /v1/yo/avisos (MATU-41, decisión 111; MATU-76, C3). Contrato: docs/api/openapi.json.

El cuerpo del PUT trae los dos canales del insumo, como booleanos estrictos ("true", 1 o null responden 422), y
extra="forbid": otro campo (por ejemplo sms o usuario_id) responde 422. El 422 nunca repite el valor. Desde MATU-76 trae
además ``pedido``, opcional: sin él, la preferencia de los avisos del pedido no cambia.
"""

from pydantic import BaseModel, ConfigDict, Field, StrictBool

_PUSH = "Avisos por notificación, en los dispositivos donde se activó (PUT /v1/dispositivos/actual/push)"


class PreferenciaPedidoVista(BaseModel):
    """Si la persona recibe los avisos de sus pedidos, por canal (MATU-76). Es de la persona y vale para todos sus
    grupos. Sin preferencia guardada, activa por los dos canales, sea cual sea su rol. Solo le llegan a quien pagó el
    pedido."""

    model_config = ConfigDict(extra="forbid")

    correo: StrictBool = Field(
        description=(
            "Avisos del pedido por correo. Apagarlo apaga solo el de «Entregado» y «No entregado»: el correo de una"
            " devolución o cancelación llega siempre, porque es sobre el dinero de quien pagó (D-76-3)"
        )
    )
    push: StrictBool = Field(description=_PUSH + ". Todos los avisos del pedido por push siguen esta preferencia")


class PreferenciaAvisosVista(BaseModel):
    """Lo que devuelven GET y PUT: ``correo`` y ``push`` son los avisos de un insumo que se está acabando (sin
    preferencia guardada, lo que corresponde a sus roles: activo si es admin o cuidador en algún grupo), y ``pedido``
    los avisos de sus pedidos (MATU-76)."""

    model_config = ConfigDict(extra="forbid")

    correo: StrictBool = Field(description="Avisos de un insumo por correo")
    push: StrictBool = Field(description=_PUSH)
    pedido: PreferenciaPedidoVista


class SolicitudPreferenciaAvisos(BaseModel):
    """El cuerpo del PUT. ``pedido`` es opcional: sin él, la preferencia de los avisos del pedido no cambia."""

    model_config = ConfigDict(extra="forbid")

    correo: StrictBool = Field(description="Avisos de un insumo por correo")
    push: StrictBool = Field(description=_PUSH)
    pedido: PreferenciaPedidoVista | None = Field(
        default=None, description="Los avisos de los pedidos. Sin él, no cambian (MATU-76)"
    )
