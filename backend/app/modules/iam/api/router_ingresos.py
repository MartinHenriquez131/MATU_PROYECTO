"""«Dónde entraste» (MATU-55, RF-37): GET /v1/yo/ingresos, los últimos ingresos de la propia cuenta.

- Solo de la persona autenticada: no recibe un usuario, una fecha ni una página (C2), y X-Grupo-Id se ignora. La
  transacción fija solo app.usuario_id, y la RLS auditoria_cuenta_propia (0025) decide qué filas se ven (C1).
- No se audita (C10). Orden: 401 y 200.
- Cache-Control: no-store lo pone el middleware de /v1/yo/ (app/main.py); aquí se repite.
- Logs: la línea de la petición lleva la ruta, el estado y el usuario. Nunca los eventos ni los nombres de los
  dispositivos (decisión 270).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response

from app.modules.iam.api.dependencias import UsuarioActual, obtener_reloj, usuario_actual
from app.modules.iam.api.esquemas import DispositivoEventoVista, EventoCuentaVista, UltimosIngresosVista
from app.modules.iam.api.sesion_web import PROBLEMA, UnidadDep
from app.modules.iam.application.sesiones import ver_ingresos
from app.shared.puertos import Reloj

router = APIRouter()

_NO_STORE = {"Cache-Control": {"description": "no-store", "schema": {"type": "string"}}}
_Respuestas = dict[int | str, dict[str, Any]]
_401: _Respuestas = {401: {"description": "no-autenticado o token-invalido", **PROBLEMA}}


@router.get(
    "/yo/ingresos",
    response_model=UltimosIngresosVista,
    tags=["cuenta"],
    operation_id="verIngresosPropios",
    description=(
        "Los eventos de la propia cuenta de los últimos 90 días, hasta 20, del más reciente al más antiguo (MATU-55,"
        " decisiones 254 y 255): entrar, salir, cerrar MATU en un dispositivo, la salida por seguridad, el cambio de"
        " contraseña, el celular confirmado, el pedido de un código de recuperación y los cambios de los avisos. Nunca"
        " los fallidos. Sin parámetros: un parámetro de consulta desconocido se ignora. `hay_mas` dice si hay más de"
        " 20. No se audita. Orden: 401 y 200."
    ),
    responses={200: {"headers": _NO_STORE}, **_401},
)
def ver_ingresos_propios(
    respuesta: Response,
    usuario: Annotated[UsuarioActual, Depends(usuario_actual)],
    unidad: UnidadDep,
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
) -> UltimosIngresosVista:
    ingresos = ver_ingresos(
        usuario_id=usuario.id, dispositivo_actual=usuario.dispositivo_id, unidad=unidad, reloj=reloj
    )
    respuesta.headers["Cache-Control"] = "no-store"
    return UltimosIngresosVista(
        eventos=[
            EventoCuentaVista(
                tipo=evento.tipo.value,  # type: ignore[arg-type]
                ocurrido_en=evento.ocurrido_en,
                dispositivo=None
                if evento.dispositivo is None
                else DispositivoEventoVista(
                    nombre=evento.dispositivo.nombre,
                    clase=evento.dispositivo.clase.value,  # type: ignore[arg-type]
                    actual=evento.dispositivo.actual,
                ),
            )
            for evento in ingresos.eventos
        ],
        hay_mas=ingresos.hay_mas,
    )
