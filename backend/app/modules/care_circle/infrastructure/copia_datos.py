"""La copia de los datos de la persona cuidada: su contexto, el registro de bloques y los bloques de care_circle
(MATU-54, Ley 21.719, acceso y portabilidad; decisiones 350, 351, 356 y 367).

La ruta vive en care_plan (``router_copia.py``), porque la ficha se descifra con la custodia que inyecta care_plan.
Los bloques de otros módulos se registran aquí desde ``app/main.py``, como los efectos del retiro (decisión 124):
care_circle no importa care_plan, consumption ni la capa 3, y ellos sí pueden importar care_circle.

- ``insumos`` (consumption) es obligatorio: sin él, la ruta falla cerrada (500).
- ``pedidos`` (payments) es opcional: con la capa 3 quitada no se registra y la copia trae ``pedidos: null``
  (D-54-15 a).

Cada bloque devuelve datos planos (dict, list) que la ruta valida con esquemas ``extra="forbid"``: un campo de más
hace fallar la respuesta, nunca sale (C5). Las consultas nombran sus columnas, sin ``SELECT *`` (C6), y corren como
matu_app con la RLS de siempre (D-54-6 a): el cuidador ve en el historial solo lo suyo.
"""

import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY, TEXT
from sqlalchemy.orm import Session

from app.modules.care_circle.domain.retiro import EstadoDeAutorizacion, EstadoVista
from app.shared.auditoria import AccionAuditoria
from app.shared.copia_datos import dia_en_chile, en_chile, en_chile_o_nada


@dataclass(frozen=True)
class ContextoCopia:
    """Lo que un bloque necesita: la transacción de la copia (REPEATABLE READ, con el contexto del grupo), la persona,
    quién pide, su rol, el instante del Reloj y el estado de las autorizaciones de la ficha y de los insumos."""

    sesion: Session
    grupo_id: uuid.UUID
    persona_id: uuid.UUID
    usuario_id: uuid.UUID
    rol: str
    ahora: datetime
    estado_ficha: EstadoDeAutorizacion
    estado_insumos: EstadoDeAutorizacion

    def __repr__(self) -> str:
        return f"ContextoCopia(rol={self.rol!r})"


FuenteBloque = Callable[[ContextoCopia], Any]

BLOQUE_INSUMOS = "insumos"
BLOQUE_PEDIDOS = "pedidos"
BLOQUES_OBLIGATORIOS = frozenset({BLOQUE_INSUMOS})
BLOQUES_CONOCIDOS = frozenset({BLOQUE_INSUMOS, BLOQUE_PEDIDOS})

_BLOQUES: dict[str, FuenteBloque] = {}


class BloqueFaltante(RuntimeError):
    """Falta un bloque obligatorio: la copia falla cerrada en vez de salir incompleta. Mensaje fijo."""


def registrar_bloque(nombre: str, fuente: FuenteBloque) -> None:
    """Lo llama app/main.py al arrancar. Registrar dos veces el mismo nombre lo reemplaza."""
    if nombre not in BLOQUES_CONOCIDOS:
        raise ValueError("bloque de copia desconocido")
    _BLOQUES[nombre] = fuente


def quitar_bloque(nombre: str) -> None:
    """Solo para las pruebas: simula la capa 3 quitada."""
    _BLOQUES.pop(nombre, None)


def bloque(nombre: str) -> FuenteBloque | None:
    fuente = _BLOQUES.get(nombre)
    if fuente is None and nombre in BLOQUES_OBLIGATORIOS:
        raise BloqueFaltante("falta un bloque obligatorio de la copia")
    return fuente


# --- Estado de un bloque (D-54-5 a, decisión 352) -----------------------------------------------------------------

ESTADO_BLOQUE: dict[EstadoVista, str] = {
    EstadoVista.VIGENTE: "disponible",
    EstadoVista.REVISION_VENCIDA: "en_pausa",
    EstadoVista.RETIRADA: "retirada",
    EstadoVista.BORRADA: "borrada",
    EstadoVista.SIN_AUTORIZAR: "sin_autorizar",
}


def estado_bloque(estado: EstadoDeAutorizacion) -> tuple[str, str | None]:
    """El estado del bloque y, si está retirada, el día en que se borra lo guardado (hora de Chile)."""
    nombre = ESTADO_BLOQUE[estado.estado]
    borrado_el = None
    if estado.estado is EstadoVista.RETIRADA and estado.borrado_en is not None:
        borrado_el = dia_en_chile(estado.borrado_en).isoformat()
    return nombre, borrado_el


def persona_nombrada(nombre: str | None, activo: bool) -> dict[str, Any]:
    """Una persona del grupo por su nombre, sin id (D-54-4 a). Quien ya no está llega sin nombre (D-42-10 a)."""
    return {"nombre": nombre if activo else None, "activo": bool(activo)}


# --- La persona ---------------------------------------------------------------------------------------------------

_PERSONA = text(
    "SELECT p.nombre, p.nombre_pila, p.nivel_apoyo, p.creado_en, p.eliminado_en, p.datos_borrados_en,"
    " d.id AS direccion_id, d.etiqueta, d.calle, d.numero, d.depto, d.comuna, d.region, d.referencia"
    " FROM persona_cuidada p LEFT JOIN direccion d ON d.id = p.direccion_entrega_id"
    " WHERE p.id = :persona_id AND p.grupo_id = :grupo_id"
)


@dataclass(frozen=True)
class PersonaDeLaCopia:
    datos: dict[str, Any]

    def __repr__(self) -> str:
        return "PersonaDeLaCopia()"


def persona_de_la_copia(sesion: Session, grupo_id: uuid.UUID, persona_id: uuid.UUID) -> PersonaDeLaCopia | None:
    """La persona, o None si no es del grupo, se eliminó o sus datos se borraron (la ruta responde 404, C1)."""
    f = sesion.execute(_PERSONA, {"persona_id": persona_id, "grupo_id": grupo_id}).first()
    if f is None or f.eliminado_en is not None or f.datos_borrados_en is not None:
        return None
    direccion = None
    if f.direccion_id is not None:
        direccion = {
            "etiqueta": f.etiqueta,
            "calle": f.calle,
            "numero": f.numero,
            "depto": f.depto,
            "comuna": f.comuna,
            "region": f.region,
            "referencia": f.referencia,
        }
    return PersonaDeLaCopia(
        datos={
            "nombre": f.nombre,
            "nombre_pila": f.nombre_pila,
            "nivel_apoyo": f.nivel_apoyo,
            "direccion": direccion,
            "alta_en": en_chile(f.creado_en),
        }
    )


# --- Autorizaciones (decisión 351) ----------------------------------------------------------------------------

_AUTORIZACIONES = text(
    "SELECT c.finalidad, c.calidad_otorgante, c.version_politica, c.evidencia -> 'declaracion' AS declaracion,"
    " c.evidencia -> 'aviso' AS aviso, (c.referencia_documento IS NOT NULL) AS hay_documento,"
    " c.otorgado_en, c.revision_vence_en, c.revocado_en, c.revocacion_motivo,"
    " u.nombre AS autor_nombre, (u.id IS NOT NULL) AS autor_activo"
    " FROM consentimiento c LEFT JOIN usuario u ON u.id = c.usuario_id AND u.eliminado_en IS NULL"
    " WHERE c.persona_cuidada_id = :persona_id AND c.grupo_id = :grupo_id"
    " AND c.finalidad IN ('plan_cuidado', 'consumo', 'despacho')"
    " ORDER BY c.otorgado_en DESC, c.id DESC"
)


def _texto_mostrado(valor: Any) -> dict[str, Any] | None:
    """El identificador, la versión y la huella de lo que se mostró, leídos de la evidencia. Nunca la evidencia en
    bruto (C4)."""
    if not isinstance(valor, dict) or not isinstance(valor.get("id"), str):
        return None
    huella = valor.get("sha256")
    return {
        "identificador": valor["id"],
        "version": str(valor.get("version", "")),
        "huella": huella if isinstance(huella, str) else None,
    }


def estado_de_fila(
    revocado_en: datetime | None,
    motivo: str | None,
    calidad: str,
    revision_vence_en: datetime | None,
    ahora: datetime,
) -> str:
    """vigente, revision_vencida, retirada o reemplazada (renovada: la vigente es otra fila)."""
    if revocado_en is not None:
        return "reemplazada" if motivo == "renovacion" else "retirada"
    if calidad == "cuidador_de_hecho" and revision_vence_en is not None and revision_vence_en <= ahora:
        return "revision_vencida"
    return "vigente"


def autorizaciones(ctx: ContextoCopia) -> list[dict[str, Any]]:
    filas = ctx.sesion.execute(_AUTORIZACIONES, {"persona_id": ctx.persona_id, "grupo_id": ctx.grupo_id}).all()
    return [
        {
            "finalidad": f.finalidad,
            "estado": estado_de_fila(
                f.revocado_en, f.revocacion_motivo, f.calidad_otorgante, f.revision_vence_en, ctx.ahora
            ),
            "calidad_otorgante": f.calidad_otorgante,
            "version_politica": f.version_politica,
            "declaracion": _texto_mostrado(f.declaracion),
            "aviso": _texto_mostrado(f.aviso),
            "registrada_por": persona_nombrada(f.autor_nombre, f.autor_activo),
            "otorgada_en": en_chile(f.otorgado_en),
            "revision_vence_en": en_chile_o_nada(f.revision_vence_en),
            "retirada_en": en_chile_o_nada(f.revocado_en),
            "hay_documento_representante": bool(f.hay_documento),
        }
        for f in filas
    ]


# --- Historial (decisiones 356, 357, 383 y 384) -------------------------------------------------------------------

# La lista cerrada: acción de auditoría -> tipo de la API. Lo del relevo (salvo compartir y cortar) va en las
# aperturas de cada enlace; persona.borrar nunca se ve (una persona borrada da 404)
TIPO_HECHO: dict[AccionAuditoria, str] = {
    AccionAuditoria.PLAN_LEER: "abrio_la_ficha",
    AccionAuditoria.PLAN_EDITAR: "edito_la_ficha",
    AccionAuditoria.PLAN_QUITAR_SECCION: "quito_una_seccion",
    AccionAuditoria.CLAVE_DESTRUIR: "ficha_borrada",
    AccionAuditoria.CONSENTIMIENTO_OTORGAR: "dio_una_autorizacion",
    AccionAuditoria.CONSENTIMIENTO_REVOCAR: "retiro_una_autorizacion",
    AccionAuditoria.RELEVO_COMPARTIR: "compartio_la_ficha",
    AccionAuditoria.RELEVO_REVOCAR: "corto_un_enlace",
    AccionAuditoria.CONSUMO_CREAR: "agrego_un_insumo",
    AccionAuditoria.CONSUMO_EDITAR: "edito_un_insumo",
    AccionAuditoria.CONSUMO_DESACTIVAR: "dejo_de_seguir_un_insumo",
    AccionAuditoria.CONSUMO_ACTIVAR: "volvio_a_seguir_un_insumo",
    AccionAuditoria.CONSUMO_ELIMINAR: "quito_un_insumo",
    AccionAuditoria.REPOSICION_DECLARAR: "anoto_una_compra",
    AccionAuditoria.ALERTA_MATERIALIZAR: "aviso_de_insumo",
    AccionAuditoria.ALERTA_DESCARTAR: "descarto_un_aviso",
    AccionAuditoria.ALERTA_RESOLVER: "resolvio_un_aviso",
    AccionAuditoria.DIRECCION_CAMBIAR: "cambio_la_direccion",
    AccionAuditoria.PEDIDO_CREAR: "creo_un_pedido",
    AccionAuditoria.PEDIDO_CONFIRMAR: "confirmo_un_pedido",
    AccionAuditoria.PEDIDO_CANCELAR: "cancelo_un_pedido",
    AccionAuditoria.PEDIDO_REGLA_FALTANTE: "cambio_que_hacer_si_falta",
    AccionAuditoria.PAGO_INICIAR: "inicio_un_pago",
    AccionAuditoria.PAGO_APROBAR: "pago_aprobado",
    AccionAuditoria.PAGO_ANULAR: "pago_anulado",
    AccionAuditoria.PERSONA_DATOS_DESCARGAR: "pidio_una_copia",
    # MATU-63: el despacho, la devolución y el retracto, con la referencia del pedido y sin el código ni el comercio
    AccionAuditoria.PAGO_DEVOLVER: "devolucion_a_la_tarjeta",
    AccionAuditoria.PEDIDO_RETRACTO_SOLICITAR: "pidio_un_retracto",
    AccionAuditoria.CODIGO_RETIRO_GENERAR: "codigo_de_retiro_generado",
    AccionAuditoria.DESPACHO_EN_CAMINO: "pedido_en_camino",
    AccionAuditoria.DESPACHO_ENTREGAR: "pedido_entregado",
    AccionAuditoria.DESPACHO_NO_ENTREGADO: "pedido_no_entregado",
    AccionAuditoria.RETRACTO_RESOLVER: "retracto_resuelto",
}

CAMPOS_BASE = frozenset({"rutina", "manejo_situaciones", "red_apoyo"})

# La persona de una fila anterior a la 0028 (sin persona_cuidada_id), por su entidad mientras exista (decisión 356)
_PERSONA_POR_ENTIDAD = (
    "CASE a.entidad"
    " WHEN 'persona_cuidada' THEN a.entidad_id"
    " WHEN 'plan_cuidado' THEN (SELECT x.persona_cuidada_id FROM plan_cuidado x WHERE x.id = a.entidad_id)"
    " WHEN 'plan_seccion' THEN (SELECT x.persona_cuidada_id FROM plan_seccion s JOIN plan_cuidado x"
    "  ON x.id = s.plan_id WHERE s.id = a.entidad_id)"
    " WHEN 'acceso_relevo' THEN (SELECT x.persona_cuidada_id FROM acceso_relevo r JOIN plan_cuidado x"
    "  ON x.id = r.plan_id WHERE r.id = a.entidad_id)"
    " WHEN 'consentimiento' THEN (SELECT x.persona_cuidada_id FROM consentimiento x WHERE x.id = a.entidad_id)"
    " WHEN 'perfil_consumo' THEN (SELECT x.persona_cuidada_id FROM perfil_consumo x WHERE x.id = a.entidad_id)"
    " WHEN 'alerta_quiebre' THEN (SELECT x.persona_cuidada_id FROM alerta_quiebre q JOIN perfil_consumo x"
    "  ON x.id = q.perfil_id WHERE q.id = a.entidad_id)"
    " WHEN 'reposicion' THEN (SELECT x.persona_cuidada_id FROM reposicion q JOIN perfil_consumo x"
    "  ON x.id = q.perfil_id WHERE q.id = a.entidad_id)"
    " WHEN 'clave_datos' THEN (SELECT x.persona_cuidada_id FROM clave_datos x WHERE x.id = a.entidad_id)"
    " WHEN 'direccion' THEN (SELECT x.id FROM persona_cuidada x WHERE x.direccion_entrega_id = a.entidad_id LIMIT 1)"
    " WHEN 'pedido' THEN (SELECT x.persona_cuidada_id FROM pedido x WHERE x.id = a.entidad_id)"
    " WHEN 'cargo' THEN (SELECT x.persona_cuidada_id FROM cargo c JOIN pedido x ON x.id = c.pedido_id"
    "  WHERE c.id = a.entidad_id)"
    " WHEN 'retracto' THEN (SELECT x.persona_cuidada_id FROM retracto r JOIN pedido x ON x.id = r.pedido_id"
    "  WHERE r.id = a.entidad_id)"
    " WHEN 'pedido_comercio' THEN (SELECT x.persona_cuidada_id FROM pedido_comercio pc JOIN pedido x"
    "  ON x.id = pc.pedido_id WHERE pc.id = a.entidad_id)"
    " END"
)

_DE_LA_PERSONA = (
    f"COALESCE(a.persona_cuidada_id, {_PERSONA_POR_ENTIDAD},"
    " CASE WHEN CAST(:unica AS boolean) THEN CAST(:persona_id AS uuid) END)"
)

_HISTORIAL = text(
    "SELECT a.accion, a.ocurrido_en, a.actor_tipo, a.detalle ->> 'seccion' AS seccion,"
    " u.nombre AS actor_nombre, (u.id IS NOT NULL) AS actor_activo,"
    " CASE WHEN a.entidad = 'plan_seccion' THEN"
    "  (SELECT s.tipo FROM plan_seccion s WHERE s.id = a.entidad_id) END AS tipo_seccion,"
    " CASE WHEN a.entidad = 'consentimiento' THEN"
    "  (SELECT c.finalidad FROM consentimiento c WHERE c.id = a.entidad_id) END AS finalidad,"
    " CASE a.entidad WHEN 'pedido' THEN (SELECT x.referencia FROM pedido x WHERE x.id = a.entidad_id)"
    "  WHEN 'cargo' THEN (SELECT x.referencia FROM cargo c JOIN pedido x ON x.id = c.pedido_id"
    "  WHERE c.id = a.entidad_id)"
    "  WHEN 'retracto' THEN (SELECT x.referencia FROM retracto r JOIN pedido x ON x.id = r.pedido_id"
    "  WHERE r.id = a.entidad_id)"
    "  WHEN 'pedido_comercio' THEN (SELECT x.referencia FROM pedido_comercio pc JOIN pedido x ON x.id = pc.pedido_id"
    "  WHERE pc.id = a.entidad_id) END AS referencia"
    " FROM auditoria a"
    " LEFT JOIN usuario u ON a.actor_tipo = 'usuario' AND u.id = a.actor_ref AND u.eliminado_en IS NULL"
    " WHERE a.grupo_id = :grupo_id AND a.accion = ANY(:acciones)"
    f" AND {_DE_LA_PERSONA} = :persona_id"
    " ORDER BY a.ocurrido_en DESC, a.id DESC"
).bindparams(bindparam("acciones", type_=ARRAY(TEXT)))

# Filas anteriores a la 0028 que no se pueden asociar a ninguna persona (su entidad ya no existe)
_SIN_ASOCIAR = text(
    "SELECT EXISTS (SELECT 1 FROM auditoria a WHERE a.grupo_id = :grupo_id AND a.accion = ANY(:acciones)"
    f" AND a.persona_cuidada_id IS NULL AND {_DE_LA_PERSONA} IS NULL)"
).bindparams(bindparam("acciones", type_=ARRAY(TEXT)))

_PERSONAS_DEL_GRUPO = text("SELECT count(*) FROM persona_cuidada WHERE grupo_id = :grupo_id")


def alcance_del_historial(rol: str) -> str:
    """Lo que el rol lee por RLS (D-54-6 a): el admin todo; el cuidador lo suyo (C13)."""
    return "todo" if rol == "admin" else "lo_tuyo"


def _quien(actor_tipo: str, nombre: str | None, activo: bool) -> dict[str, Any]:
    if actor_tipo == "usuario":
        return {"tipo": "persona", "nombre": nombre if activo else None, "activo": bool(activo)}
    return {"tipo": "matu", "nombre": None, "activo": None}


def hecho(
    accion: str,
    ocurrido_en: datetime,
    actor_tipo: str,
    actor_nombre: str | None,
    actor_activo: bool,
    seccion: str | None,
    tipo_seccion: str | None,
    finalidad: str | None,
    referencia: str | None,
) -> dict[str, Any] | None:
    """Un hecho del historial, o None si la acción no está en la lista cerrada."""
    try:
        tipo = TIPO_HECHO[AccionAuditoria(accion)]
    except (ValueError, KeyError):
        return None
    campo = None
    if tipo == "edito_la_ficha" and seccion is None and tipo_seccion in CAMPOS_BASE:
        campo = tipo_seccion
    return {
        "tipo": tipo,
        "ocurrido_en": en_chile(ocurrido_en),
        "quien": _quien(actor_tipo, actor_nombre, actor_activo),
        "campo": campo,
        "seccion": seccion if tipo in ("edito_la_ficha", "quito_una_seccion") else None,
        # F1 (decisión 384): a qué autorización o a qué pedido se refiere, nada que identifique a una persona
        "finalidad": finalidad if tipo in ("dio_una_autorizacion", "retiro_una_autorizacion") else None,
        "referencia": referencia
        if accion.startswith(("pedido.", "pago.", "despacho.", "codigo_retiro.", "retracto."))
        else None,
    }


def _acciones(acciones: Iterable[AccionAuditoria]) -> list[str]:
    return sorted(a.value for a in acciones)


def historial(ctx: ContextoCopia) -> dict[str, Any]:
    unica = int(ctx.sesion.execute(_PERSONAS_DEL_GRUPO, {"grupo_id": ctx.grupo_id}).scalar_one()) == 1
    parametros = {
        "grupo_id": ctx.grupo_id,
        "persona_id": ctx.persona_id,
        "acciones": _acciones(TIPO_HECHO),
        "unica": unica,
    }
    filas = ctx.sesion.execute(_HISTORIAL, parametros).all()
    hechos = [
        h
        for f in filas
        if (
            h := hecho(
                f.accion, f.ocurrido_en, f.actor_tipo, f.actor_nombre, f.actor_activo, f.seccion, f.tipo_seccion,
                f.finalidad, f.referencia,
            )
        )
        is not None
    ]
    sin_asociar = bool(ctx.sesion.execute(_SIN_ASOCIAR, parametros).scalar_one())
    return {"alcance": alcance_del_historial(ctx.rol), "hechos": hechos, "hay_hechos_sin_asociar": sin_asociar}
