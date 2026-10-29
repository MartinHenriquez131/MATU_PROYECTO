"""Auditoría de la ficha mientras llega MATU-14: el punto de enganche, sin registro todavía.

El contrato (docs/api/propuestos/ficha.openapi.yaml) promete que toda lectura registra plan.leer y
toda escritura plan.editar en auditoria. Eso es MATU-14 (Martín). MATU-12 deja el puerto
AuditoriaFicha (application/ports.py) cableado en la API y llamado por los casos de uso en la misma
transacción, con un EventoFicha que lleva solo identificadores.

TODO(MATU-14): reemplazar AuditoriaFichaPendiente por un adaptador que inserte en auditoria con la
sesión de la petición: actor_tipo 'usuario', actor_ref = usuario_id, accion 'plan.leer' o
'plan.editar', entidad 'plan_cuidado', entidad_id = plan_id, request_id y ocurrido_en. Basta con
cambiar obtener_auditoria_ficha en api/dependencias.py: los casos de uso no cambian.
"""

from app.modules.care_plan.application.ports import EventoFicha


class AuditoriaFichaPendiente:
    """No registra nada. Existe para que la API ya llame al puerto en el lugar correcto."""

    def registrar_lectura(self, evento: EventoFicha) -> None:
        return None

    def registrar_edicion(self, evento: EventoFicha) -> None:
        return None
