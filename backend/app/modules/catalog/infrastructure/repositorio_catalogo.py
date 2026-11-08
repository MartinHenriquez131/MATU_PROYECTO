"""La lectura SQL de las ofertas publicadas (MATU-59).

Corre en la sesión del usuario (sesion_de_usuario, solo app.usuario_id): las políticas de lectura de 0001 dejan
leer categoria_cuidado, producto y oferta a todos, y comercio solo si está activo. El filtro explícito de estado
repite esa regla para que no dependa de RLS. Del comercio se selecciona solo nombre_fantasia: razon_social, rut,
direccion, comuna y telefono nunca salen de la base por esta consulta.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.catalog.domain.catalogo import FilaOferta

_OFERTAS = text(
    """
    SELECT c.id AS categoria_id, c.nombre AS categoria_nombre, c.orden AS categoria_orden,
           p.id AS producto_id, p.nombre AS producto_nombre, p.presentacion, p.unidad, p.unidades_por_envase,
           p.retracto_pierde_al_abrir,
           o.id AS oferta_id, co.id AS comercio_id, co.nombre_fantasia, o.precio, o.stock
      FROM oferta o
      JOIN producto p ON p.id = o.producto_id
      JOIN categoria_cuidado c ON c.id = p.categoria_id
      JOIN comercio co ON co.id = o.comercio_id
     WHERE o.disponible AND p.activo AND c.activa AND co.estado = 'activo'
    """
)


class RepositorioCatalogoSQL:
    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def ofertas_publicadas(self) -> list[FilaOferta]:
        return [
            FilaOferta(
                categoria_id=fila.categoria_id,
                categoria_nombre=fila.categoria_nombre,
                categoria_orden=fila.categoria_orden,
                producto_id=fila.producto_id,
                producto_nombre=fila.producto_nombre,
                presentacion=fila.presentacion,
                unidad=fila.unidad,
                unidades_por_envase=fila.unidades_por_envase,
                retracto_pierde_al_abrir=fila.retracto_pierde_al_abrir,
                oferta_id=fila.oferta_id,
                comercio_id=fila.comercio_id,
                nombre_fantasia=fila.nombre_fantasia,
                precio=fila.precio,
                stock=fila.stock,
            )
            for fila in self._sesion.execute(_OFERTAS)
        ]
