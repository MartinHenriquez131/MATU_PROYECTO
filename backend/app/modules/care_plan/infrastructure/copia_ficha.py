"""Los bloques de care_plan en la copia de los datos de la persona: la ficha y los enlaces de relevo con sus aperturas
(MATU-54; decisiones 352, 353 y 382).

- La ficha se descifra **solo** con la autorización de la ficha vigente según el Reloj (C28), con el mismo
  CifradorSecciones de la ficha. En los demás estados no se lee nada del plan: ni el texto, ni cuántos campos hay, ni
  quién los escribió (D-54-5 a). Si la clave ya se destruyó, la ficha sale ``borrada``.
- Los enlaces nunca traen el teléfono del relevo, el token, el PIN ni sus huellas (D-54-4 a). Las aperturas salen de
  la auditoría (relevo.presentar, .abrir, .pin_incorrecto y .bloqueo), como en «Quién abrió la ficha» (MATU-45).

Columnas nombradas, sin SELECT * (C6). Nada de esto va a un log.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import text

from app.modules.care_circle.infrastructure.copia_datos import ContextoCopia, estado_bloque, persona_nombrada
from app.modules.care_plan.application.ports import CifradorSecciones
from app.modules.care_plan.domain.cifrado import EstadoClave, SeccionCifrada, estado_clave
from app.modules.care_plan.domain.ficha import CAMPOS_FICHA, completitud, texto_visible
from app.modules.care_plan.domain.relevo import INTENTOS_PIN_MAXIMOS
from app.modules.care_plan.domain.secciones import SECCIONES_COMPLEMENTARIAS
from app.modules.care_plan.infrastructure.repositorio_claves import RepositorioClavesSQL
from app.shared.copia_datos import en_chile, en_chile_o_nada

_PLAN = text("SELECT id FROM plan_cuidado WHERE persona_cuidada_id = :persona_id AND grupo_id = :grupo_id")

_SECCIONES = text(
    "SELECT s.tipo, s.contenido_cifrado, s.nonce, s.tag_auth, s.kek_version, s.actualizado_en, s.creado_en,"
    " u.nombre AS autor_nombre, (u.id IS NOT NULL) AS autor_activo, (s.actualizado_por IS NOT NULL) AS con_autor"
    " FROM plan_seccion s LEFT JOIN usuario u ON u.id = s.actualizado_por AND u.eliminado_en IS NULL"
    " WHERE s.plan_id = :plan_id"
)

_ESTADO_ACCESO = (
    "CASE WHEN a.revocado_en IS NOT NULL THEN 'revocado'"
    " WHEN a.expira_en <= :ahora THEN 'vencido'"
    f" WHEN a.pin_intentos_fallidos >= {INTENTOS_PIN_MAXIMOS} THEN 'bloqueado'"
    " ELSE 'vigente' END"
)

# Sin el teléfono del relevo (D-54-4 a), el token, el PIN ni sus intentos
_ENLACES = text(
    "SELECT a.id, a.otorgado_a_nombre, a.motivo, a.secciones_permitidas, a.creado_en, a.expira_en, a.revocado_en,"
    f" a.nombre_pila_comparte, a.usos, a.ultimo_uso_en, {_ESTADO_ACCESO} AS estado"
    " FROM acceso_relevo a JOIN plan_cuidado p ON p.id = a.plan_id"
    " WHERE p.persona_cuidada_id = :persona_id AND a.grupo_id = :grupo_id"
    " ORDER BY a.creado_en DESC, a.id DESC"
)

TIPO_APERTURA = {
    "relevo.presentar": "presentacion",
    "relevo.abrir": "apertura",
    "relevo.pin_incorrecto": "pin_incorrecto",
    "relevo.bloqueo": "bloqueo",
}

_APERTURAS = text(
    "SELECT a.actor_ref AS acceso_id, a.accion, a.ocurrido_en, a.detalle -> 'secciones' AS secciones"
    " FROM auditoria a JOIN acceso_relevo r ON r.id = a.actor_ref JOIN plan_cuidado p ON p.id = r.plan_id"
    " WHERE p.persona_cuidada_id = :persona_id AND a.grupo_id = :grupo_id AND r.grupo_id = :grupo_id"
    " AND a.actor_tipo = 'relevo'"
    " AND a.accion IN ('relevo.presentar', 'relevo.abrir', 'relevo.pin_incorrecto', 'relevo.bloqueo')"
    " ORDER BY a.ocurrido_en DESC, a.id DESC"
)

_COMPLEMENTARIAS = {s.value for s in SECCIONES_COMPLEMENTARIAS}
_ORDEN_COMPLEMENTARIAS = [s.value for s in SECCIONES_COMPLEMENTARIAS]


class SinCustodia(RuntimeError):
    """Hay texto de una ficha vigente que descifrar y la custodia no está configurada: la ruta responde 503 sin
    entregar nada (decisión 32). Mensaje fijo."""


def _cifrada(f: Any) -> SeccionCifrada:
    return SeccionCifrada(
        contenido_cifrado=bytes(f.contenido_cifrado), nonce=bytes(f.nonce), tag_auth=bytes(f.tag_auth),
        kek_version=f.kek_version,
    )


def _autor(f: Any) -> dict[str, Any] | None:
    return persona_nombrada(f.autor_nombre, f.autor_activo) if f.con_autor else None


def ficha(ctx: ContextoCopia, cifrador: CifradorSecciones | None) -> dict[str, Any]:
    """El bloque ``ficha``. ``cifrador`` es None si la custodia no está configurada: si hay algo que descifrar, lanza
    SinCustodia y la ruta responde 503 (decisión 32). Los errores del cifrado suben a la ruta, sin el texto."""
    estado, borrado_el = estado_bloque(ctx.estado_ficha)
    vacio = {"estado": estado, "borrado_el": borrado_el, "completitud": None, "campos": None, "secciones": None}
    if estado != "disponible":
        return vacio
    if estado_clave(RepositorioClavesSQL(ctx.sesion).obtener(ctx.persona_id)) is EstadoClave.DESTRUIDA:
        return {**vacio, "estado": "borrada"}
    campos: dict[str, dict[str, Any]] = {
        c.value: {"campo": c.value, "texto": None, "escrito_por": None, "actualizado_en": None} for c in CAMPOS_FICHA
    }
    secciones: dict[str, dict[str, Any]] = {}
    plan_id = ctx.sesion.execute(_PLAN, {"persona_id": ctx.persona_id, "grupo_id": ctx.grupo_id}).scalar_one_or_none()
    if plan_id is not None:
        for f in ctx.sesion.execute(_SECCIONES, {"plan_id": plan_id}).all():
            if cifrador is None:
                raise SinCustodia("la ficha vigente necesita la custodia")
            texto = cifrador.descifrar(
                persona_cuidada_id=ctx.persona_id, plan_id=plan_id, tipo=f.tipo, seccion=_cifrada(f)
            )
            if f.tipo in campos:
                campos[f.tipo] = {
                    "campo": f.tipo,
                    "texto": texto_visible(texto),
                    "escrito_por": _autor(f),
                    "actualizado_en": en_chile(f.actualizado_en),
                }
            elif f.tipo in _COMPLEMENTARIAS:
                secciones[f.tipo] = {
                    "seccion": f.tipo,
                    "texto": texto,
                    "escrito_por": _autor(f),
                    "creada_en": en_chile(f.creado_en),
                    "actualizado_en": en_chile(f.actualizado_en),
                }
    lista_campos = [campos[c.value] for c in CAMPOS_FICHA]
    return {
        "estado": estado,
        "borrado_el": None,
        "completitud": completitud(sum(1 for c in lista_campos if c["texto"])),
        "campos": lista_campos,
        "secciones": [secciones[s] for s in _ORDEN_COMPLEMENTARIAS if s in secciones],
    }


def _secciones_vistas(valor: Any) -> list[str]:
    if not isinstance(valor, list):
        return []
    return [s for s in valor if isinstance(s, str) and s in _COMPLEMENTARIAS]


def enlaces_relevo(ctx: ContextoCopia, ahora: datetime) -> list[dict[str, Any]]:
    """Todos los enlaces de la ficha, también vencidos y cortados, con sus aperturas. Van aunque la ficha esté
    retirada: dicen a quién se comunicaron los datos (decisión 353)."""
    parametros = {"persona_id": ctx.persona_id, "grupo_id": ctx.grupo_id, "ahora": ahora}
    aperturas: dict[Any, list[dict[str, Any]]] = {}
    for f in ctx.sesion.execute(_APERTURAS, parametros).all():
        tipo = TIPO_APERTURA[f.accion]
        aperturas.setdefault(f.acceso_id, []).append(
            {
                "tipo": tipo,
                "ocurrido_en": en_chile(f.ocurrido_en),
                "secciones": _secciones_vistas(f.secciones) if tipo == "apertura" else None,
            }
        )
    enlaces = []
    for f in ctx.sesion.execute(_ENLACES, parametros).all():
        permitidas = list(f.secciones_permitidas)
        enlaces.append(
            {
                "nombre_relevo": f.otorgado_a_nombre,
                "motivo": f.motivo,
                "campos": [c.value for c in CAMPOS_FICHA if c.value in permitidas],
                "secciones": [s for s in _ORDEN_COMPLEMENTARIAS if s in permitidas],
                "estado": f.estado,
                "creado_en": en_chile(f.creado_en),
                "vence_en": en_chile(f.expira_en),
                "cortado_en": en_chile_o_nada(f.revocado_en),
                "compartido_por": f.nombre_pila_comparte,
                "usos": int(f.usos),
                "ultimo_uso_en": en_chile_o_nada(f.ultimo_uso_en),
                "aperturas": aperturas.get(f.id, []),
            }
        )
    return enlaces
