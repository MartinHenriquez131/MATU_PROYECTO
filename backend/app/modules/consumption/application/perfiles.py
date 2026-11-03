"""Casos de uso del perfil de consumo (MATU-36, RF-10 y RF-11).

La autorización para ``consumo``, el rol y la persona ya los verificó la API antes de llegar aquí
(api/dependencias.py): sin autorización vigente no se lee ni se escribe nada del consumo.

Cada escritura registra su acción en la auditoría (consumo.crear, consumo.editar, consumo.desactivar,
consumo.activar y consumo.eliminar) con solo identificadores: sin nombre_libre, sin cantidades y sin
IP. Las lecturas no se auditan (decisión 52). Un desactivar o activar que no cambia nada no se audita.
"""

import uuid
from dataclasses import dataclass
from datetime import date

from app.modules.consumption.application.ports import Pagina, PerfilLeido, RepositorioPerfiles
from app.modules.consumption.domain.perfil import (
    CambiosPerfil,
    NombreLibreConProducto,
    Perfil,
    UnidadConsumo,
    aplicar_cambios,
    coincide,
    con_activo,
    exigir_if_match,
    hoy_en_chile,
    nuevo_perfil,
)
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.puertos import RegistroAuditoria, Reloj


@dataclass(frozen=True)
class PeticionConsumo:
    grupo_id: uuid.UUID
    usuario_id: uuid.UUID
    persona_id: uuid.UUID
    request_id: str | None = None


class PerfilNoEncontrado(Exception):
    """El perfil no existe o no es de la persona del path. La API responde 404."""


class ProductoNoAdmitido(Exception):
    """El producto no existe, está inactivo o requiere receta (ADR-022). 422."""


class UnidadDistinta(Exception):
    """La unidad no es la del producto. 422."""


class PerfilDuplicado(Exception):
    """La persona ya sigue ese producto en un perfil activo. 409."""


class PerfilInactivo(Exception):
    """El perfil está desactivado y no se edita. 409."""


@dataclass(frozen=True)
class VersionDesactualizada:
    """El If-Match no coincide: se devuelve el perfil actual para el 412."""

    actual: PerfilLeido


@dataclass(frozen=True)
class DatosPerfil:
    producto_id: uuid.UUID | None
    nombre_libre: str | None
    unidad: UnidadConsumo | None
    tasa_unidades: int
    tasa_dias: int
    stock_unidades: int
    dias_aviso: int


def _auditar(
    auditoria: RegistroAuditoria, peticion: PeticionConsumo, accion: AccionAuditoria, perfil_id: uuid.UUID
) -> None:
    auditoria.registrar(
        EntradaAuditoria(
            grupo_id=peticion.grupo_id,
            actor_tipo=ActorTipo.USUARIO,
            actor_ref=peticion.usuario_id,
            accion=accion,
            entidad=EntidadAuditoria.PERFIL_CONSUMO,
            entidad_id=perfil_id,
            request_id=peticion.request_id,
        )
    )


def listar(
    peticion: PeticionConsumo,
    activo: bool | None,
    despues_de: tuple[date, uuid.UUID] | None,
    limite: int,
    repositorio: RepositorioPerfiles,
) -> Pagina:
    return repositorio.listar(peticion.persona_id, activo, despues_de, limite)


def ver(peticion: PeticionConsumo, perfil_id: uuid.UUID, repositorio: RepositorioPerfiles) -> PerfilLeido:
    leido = repositorio.obtener(peticion.persona_id, perfil_id)
    if leido is None:
        raise PerfilNoEncontrado()
    return leido


def crear(
    peticion: PeticionConsumo,
    datos: DatosPerfil,
    reloj: Reloj,
    repositorio: RepositorioPerfiles,
    auditoria: RegistroAuditoria,
) -> PerfilLeido:
    """Crea el perfil con stock_medido_en = hoy (Reloj, America/Santiago) y la fecha estimada.

    Orden: producto (422), unidad (422), cobertura (422, CoberturaMaxima del dominio) y duplicado (409).
    """
    unidad = datos.unidad or UnidadConsumo.UNIDAD
    producto = None
    if datos.producto_id is not None:
        producto = repositorio.producto_admitido(datos.producto_id)
        if producto is None:
            raise ProductoNoAdmitido()
        if datos.unidad is not None and datos.unidad is not producto.unidad:
            raise UnidadDistinta()
        unidad = producto.unidad
    perfil = nuevo_perfil(
        perfil_id=uuid.uuid4(),
        persona_cuidada_id=peticion.persona_id,
        producto_id=datos.producto_id,
        nombre_libre=datos.nombre_libre,
        unidad=unidad,
        tasa_unidades=datos.tasa_unidades,
        tasa_dias=datos.tasa_dias,
        stock_unidades=datos.stock_unidades,
        dias_aviso=datos.dias_aviso,
        hoy=hoy_en_chile(reloj.ahora()),
        autor=peticion.usuario_id,
    )
    if datos.producto_id is not None and repositorio.hay_activo_del_producto(
        peticion.persona_id, datos.producto_id, salvo=None
    ):
        raise PerfilDuplicado()
    repositorio.insertar(peticion.grupo_id, perfil)
    _auditar(auditoria, peticion, AccionAuditoria.CONSUMO_CREAR, perfil.id)
    return _leer_guardado(repositorio, peticion, perfil.id)


def _leer_guardado(repositorio: RepositorioPerfiles, peticion: PeticionConsumo, perfil_id: uuid.UUID) -> PerfilLeido:
    leido = repositorio.obtener(peticion.persona_id, perfil_id)
    if leido is None:  # pragma: no cover - recién escrito en la misma transacción
        raise PerfilNoEncontrado()
    return leido


def editar(
    peticion: PeticionConsumo,
    perfil_id: uuid.UUID,
    cambios: CambiosPerfil,
    if_match: str | None,
    reloj: Reloj,
    repositorio: RepositorioPerfiles,
    auditoria: RegistroAuditoria,
) -> PerfilLeido | VersionDesactualizada:
    """PATCH condicional. Orden: 404 (perfil), 422 (nombre_libre en un perfil de producto), 428,
    409 (inactivo), 412 y 422 (cobertura, con los valores ya combinados). Lanza FaltaVersion,
    NombreLibreConProducto y CoberturaMaxima del dominio."""
    leido = repositorio.obtener(peticion.persona_id, perfil_id, para_escribir=True)
    if leido is None:
        raise PerfilNoEncontrado()
    actual = leido.perfil
    if cambios.nombre_libre is not None and actual.producto_id is not None:
        raise NombreLibreConProducto("nombre_libre solo se edita en un perfil sin producto")
    valor = exigir_if_match(if_match)
    if not actual.activo:
        raise PerfilInactivo()
    if not coincide(valor, actual.version):
        return VersionDesactualizada(actual=leido)
    nuevo = aplicar_cambios(actual, cambios, hoy_en_chile(reloj.ahora()), peticion.usuario_id)
    repositorio.actualizar(nuevo)
    _auditar(auditoria, peticion, AccionAuditoria.CONSUMO_EDITAR, perfil_id)
    return _leer_guardado(repositorio, peticion, perfil_id)


def desactivar(
    peticion: PeticionConsumo,
    perfil_id: uuid.UUID,
    reloj: Reloj,
    repositorio: RepositorioPerfiles,
    auditoria: RegistroAuditoria,
) -> PerfilLeido:
    """Archiva (decisión 46): activo = false y las alertas abiertas pasan a descartada. Idempotente."""
    leido = repositorio.obtener(peticion.persona_id, perfil_id, para_escribir=True)
    if leido is None:
        raise PerfilNoEncontrado()
    nuevo = con_activo(leido.perfil, False, peticion.usuario_id)
    if nuevo is leido.perfil:
        return leido
    repositorio.actualizar(nuevo)
    repositorio.descartar_alertas_abiertas(perfil_id, reloj.ahora())
    _auditar(auditoria, peticion, AccionAuditoria.CONSUMO_DESACTIVAR, perfil_id)
    return _leer_guardado(repositorio, peticion, perfil_id)


def activar(
    peticion: PeticionConsumo,
    perfil_id: uuid.UUID,
    repositorio: RepositorioPerfiles,
    auditoria: RegistroAuditoria,
) -> PerfilLeido:
    """Vuelve a seguir un perfil desactivado (decisión 68). Idempotente. Conserva el stock y la fecha
    estimada que tenía: la pantalla invita a anotar cuánto queda. Si la persona ya sigue el mismo
    producto en otro perfil activo, PerfilDuplicado (409)."""
    leido = repositorio.obtener(peticion.persona_id, perfil_id, para_escribir=True)
    if leido is None:
        raise PerfilNoEncontrado()
    perfil: Perfil = leido.perfil
    nuevo = con_activo(perfil, True, peticion.usuario_id)
    if nuevo is perfil:
        return leido
    if perfil.producto_id is not None and repositorio.hay_activo_del_producto(
        peticion.persona_id, perfil.producto_id, salvo=perfil.id
    ):
        raise PerfilDuplicado()
    repositorio.actualizar(nuevo)
    _auditar(auditoria, peticion, AccionAuditoria.CONSUMO_ACTIVAR, perfil_id)
    return _leer_guardado(repositorio, peticion, perfil_id)


def eliminar(
    peticion: PeticionConsumo,
    perfil_id: uuid.UUID,
    repositorio: RepositorioPerfiles,
    auditoria: RegistroAuditoria,
) -> None:
    """Borra el perfil en el acto (decisión 69), activo o no. Sus reposiciones y alertas caen con él."""
    leido = repositorio.obtener(peticion.persona_id, perfil_id, para_escribir=True)
    if leido is None:
        raise PerfilNoEncontrado()
    repositorio.eliminar(perfil_id)
    _auditar(auditoria, peticion, AccionAuditoria.CONSUMO_ELIMINAR, perfil_id)
