"""Caso de uso de la lista de insumos (MATU-60, RF-15, ADR-031).

La autorización para ``consumo``, el rol y la persona ya los verificó la API (api/dependencias.py,
``consumo_para_leer``): sin autorización vigente no se lee nada del consumo.

- Lee el Reloj una sola vez: la ``fecha`` de la lista y los ``dias_restantes`` de cada línea son del mismo
  «hoy» en America/Santiago (decisión 118).
- Lee lo mismo que «Se acaban pronto» (``RepositorioAlertas.en_ventana``): perfiles activos en su ventana,
  con la alerta de su fecha estimada actual y el producto. Las reglas de qué entra, cuánto y en qué orden
  son del dominio (domain/lista.py).
- Es una lectura pura: no crea ni cierra alertas, no se audita (decisión 52) y no publica eventos. Nunca
  escribe el nombre de un insumo en un log ni en un error.
- No lee el catálogo: el nombre de un producto llega con el perfil, y el envase sale solo del perfil
  (decisión 121).
"""

from dataclasses import dataclass
from datetime import date

from app.modules.consumption.application.perfiles import PeticionConsumo
from app.modules.consumption.application.ports import PerfilLeido, RepositorioAlertas
from app.modules.consumption.domain.lista import InsumoCandidato, LineaLista, armar_lista
from app.modules.consumption.domain.perfil import hoy_en_chile
from app.shared.puertos import Reloj


@dataclass(frozen=True)
class ListaDeInsumos:
    fecha: date
    lineas: list[LineaLista]


class PerfilSinNombre(RuntimeError):
    """Un perfil sin producto visible ni nombre_libre. No ocurre con el CHECK de la 0009. Mensaje fijo."""


def _nombre(leido: PerfilLeido) -> str:
    if leido.producto is not None:
        return leido.producto.nombre
    if leido.perfil.nombre_libre is not None:
        return leido.perfil.nombre_libre
    raise PerfilSinNombre("el perfil no tiene nombre")  # pragma: no cover - lo impide perfil_consumo_producto


def lista_de_insumos(peticion: PeticionConsumo, reloj: Reloj, repositorio: RepositorioAlertas) -> ListaDeInsumos:
    hoy = hoy_en_chile(reloj.ahora())
    candidatos = [
        InsumoCandidato(
            perfil=i.leido.perfil,
            nombre=_nombre(i.leido),
            estado_de_la_fecha=None if i.alerta is None else i.alerta.estado,
        )
        for i in repositorio.en_ventana(peticion.persona_id, hoy)
    ]
    return ListaDeInsumos(fecha=hoy, lineas=armar_lista(candidatos, hoy))
