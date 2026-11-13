"""Esquemas de «Datos de {nombre_pila}» (MATU-54, contrato docs/api/propuestos/mis-datos.openapi.yaml).

Todos con ``extra="forbid"`` (C5): un campo que un bloque devuelva de más hace fallar la respuesta, y nunca sale. Sin
ids, sin teléfonos, sin correos, sin referencia_documento, sin evidencia en bruto (C4). Instantes con el desfase de
Chile (decisión 349), como texto ya formateado por app/shared/copia_datos.py.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.shared.copia_datos import AVISO_COPIA

Instante = str
Dia = str
Pesos = int
Seccion = Literal["quien_es", "preferencias", "alimentacion", "movilidad", "comunicacion", "remedios"]
Campo = Literal["rutina", "manejo_situaciones", "red_apoyo"]
EstadoBloque = Literal["disponible", "retirada", "en_pausa", "borrada", "sin_autorizar"]


class _Cerrado(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PersonaNombrada(_Cerrado):
    nombre: str | None
    activo: bool


class DireccionCopia(_Cerrado):
    etiqueta: str
    calle: str
    numero: str
    depto: str | None
    comuna: str
    region: str
    referencia: str | None


class DatosPersonaCopia(_Cerrado):
    nombre: str
    nombre_pila: str
    nivel_apoyo: Literal["autovalente_con_supervision", "apoyo_parcial", "apoyo_total"]
    direccion: DireccionCopia | None
    alta_en: Instante


class TextoMostrado(_Cerrado):
    identificador: str
    version: str
    huella: str | None


class AutorizacionCopia(_Cerrado):
    finalidad: Literal["plan_cuidado", "consumo", "despacho"]
    estado: Literal["vigente", "revision_vencida", "retirada", "reemplazada"]
    calidad_otorgante: Literal["titular", "representante_legal", "cuidador_de_hecho"]
    version_politica: str
    declaracion: TextoMostrado | None
    aviso: TextoMostrado | None
    registrada_por: PersonaNombrada
    otorgada_en: Instante
    revision_vence_en: Instante | None
    retirada_en: Instante | None
    hay_documento_representante: bool


class CampoCopia(_Cerrado):
    campo: Campo
    texto: str | None
    escrito_por: PersonaNombrada | None
    actualizado_en: Instante | None


class SeccionCopia(_Cerrado):
    seccion: Seccion
    texto: str
    escrito_por: PersonaNombrada | None
    creada_en: Instante
    actualizado_en: Instante


class FichaCopia(_Cerrado):
    estado: EstadoBloque
    borrado_el: Dia | None
    completitud: Literal[0, 33, 67, 100] | None
    campos: list[CampoCopia] | None
    secciones: list[SeccionCopia] | None


class AperturaCopia(_Cerrado):
    tipo: Literal["presentacion", "apertura", "pin_incorrecto", "bloqueo"]
    ocurrido_en: Instante
    secciones: list[Seccion] | None


class EnlaceRelevoCopia(_Cerrado):
    nombre_relevo: str
    motivo: Literal["salgo_unas_horas", "fin_de_semana_fuera", "turno_de_noche", "otro"]
    campos: list[Campo]
    secciones: list[Seccion]
    estado: Literal["vigente", "vencido", "revocado", "bloqueado"]
    creado_en: Instante
    vence_en: Instante
    cortado_en: Instante | None
    compartido_por: str
    usos: int = Field(ge=0)
    ultimo_uso_en: Instante | None
    aperturas: list[AperturaCopia]


Unidad = Literal["unidad", "sobre", "ml", "g"]


class InsumoCopia(_Cerrado):
    nombre: str
    del_catalogo: bool
    unidad: Unidad
    usa_unidades: int
    cada_dias: int
    quedaban_unidades: int
    quedaban_el: Dia
    se_acaba_el: Dia
    dias_aviso: int
    unidades_por_envase: int | None
    se_sigue: bool
    agregado_en: Instante
    actualizado_en: Instante
    actualizado_por: PersonaNombrada | None


class CompraCopia(_Cerrado):
    insumo: str
    unidad: Unidad
    unidades: int
    el: Dia
    origen: Literal["declarada", "pedido_matu"]
    anotada_en: Instante
    anotada_por: PersonaNombrada | None


class AvisoInsumoCopia(_Cerrado):
    insumo: str
    fecha_prevista: Dia
    estado: Literal["pendiente", "notificada", "resuelta", "descartada"]
    creado_en: Instante
    notificado_en: Instante | None
    cerrado_en: Instante | None


class InsumosCopia(_Cerrado):
    estado: EstadoBloque
    borrado_el: Dia | None
    lista: list[InsumoCopia] | None
    compras: list[CompraCopia] | None
    avisos: list[AvisoInsumoCopia] | None


EstadoPedido = Literal[
    "borrador", "total_confirmado", "vencido", "pagado", "enviado_a_comercio", "preparando", "listo_retiro",
    "asignado", "sin_repartidor", "retirado", "en_ruta", "entregado", "no_entregado", "reprogramado", "cerrado",
    "cancelado", "cancelado_con_devolucion",
]


class LineaPedidoCopia(_Cerrado):
    producto: str
    presentacion: str
    comercio: str
    cantidad: int
    precio_unitario: Pesos
    subtotal: Pesos
    si_falta: Literal["otro_comercio", "quitar"]
    # MATU-63: lo que marcó el comercio y cuántos faltaron (D-63-8)
    estado: Literal["pendiente", "sin_stock", "preparada", "faltante", "devuelta", "eliminada"]
    unidades_faltantes: int


class EntregaCopia(_Cerrado):
    calle: str
    numero: str
    depto: str | None
    comuna: str
    region: str
    referencia: str | None


class DevolucionCopia(_Cerrado):
    motivo: Literal["pago_tardio", "producto_no_entregado", "cancelacion", "retracto"]
    producto: str | None
    monto: Pesos
    estado: Literal["en_curso", "hecha"]
    solicitada_en: Instante
    hecha_en: Instante | None


class PagoPedidoCopia(_Cerrado):
    estado: Literal["sin_intento", "pendiente", "aprobado", "no_aprobado", "devuelto_parcial", "anulado"]
    pagado_en: Instante | None
    pagado_por: PersonaNombrada | None
    cobrado: Pesos
    devuelto: Pesos
    devoluciones: list[DevolucionCopia]
    pago_de_prueba: bool


class ParteCopia(_Cerrado):
    """MATU-63: la parte de cada comercio, sin su referencia ni nada del encargado."""

    comercio: str
    estado: Literal["enviada", "preparando", "lista", "retirada", "cancelada"]
    enviado_en: Instante | None
    lista_en: Instante | None
    retirada_en: Instante | None
    cancelada_en: Instante | None
    motivo_cancelacion: Literal["producto_faltante", "familia_cancela"] | None


class LineaRetractoCopia(_Cerrado):
    producto: str
    cantidad: int


class RetractoCopia(_Cerrado):
    """MATU-63 (R3): el retracto pedido, con sus productos y cómo se resolvió."""

    estado: Literal["solicitado", "devuelto", "rechazado"]
    solicitado_en: Instante
    plazo_hasta: Instante
    incluye_envio: bool
    resuelto_en: Instante | None
    lineas: list[LineaRetractoCopia]


class PedidoCopia(_Cerrado):
    referencia: str | None
    estado: EstadoPedido
    creado_en: Instante
    total_confirmado_en: Instante | None
    lineas: list[LineaPedidoCopia]
    subtotal_productos: Pesos
    costo_envio: Pesos
    total: Pesos | None
    entrega: EntregaCopia | None
    pago: PagoPedidoCopia | None
    precios_de_ejemplo: bool
    # MATU-63
    entregado_en: Instante | None
    partes: list[ParteCopia]
    retractos: list[RetractoCopia]


TipoHecho = Literal[
    "abrio_la_ficha", "edito_la_ficha", "quito_una_seccion", "ficha_borrada", "dio_una_autorizacion",
    "retiro_una_autorizacion", "compartio_la_ficha", "corto_un_enlace", "agrego_un_insumo", "edito_un_insumo",
    "dejo_de_seguir_un_insumo", "volvio_a_seguir_un_insumo", "quito_un_insumo", "anoto_una_compra", "aviso_de_insumo",
    "descarto_un_aviso", "resolvio_un_aviso", "cambio_la_direccion", "creo_un_pedido", "confirmo_un_pedido",
    "cancelo_un_pedido", "cambio_que_hacer_si_falta", "inicio_un_pago", "pago_aprobado", "pago_anulado",
    "pidio_una_copia",
    # MATU-63
    "devolucion_a_la_tarjeta", "pidio_un_retracto", "codigo_de_retiro_generado", "pedido_en_camino", "pedido_entregado",
    "pedido_no_entregado", "retracto_resuelto",
]


class QuienCopia(_Cerrado):
    tipo: Literal["persona", "matu"]
    nombre: str | None
    activo: bool | None


class HechoCopia(_Cerrado):
    tipo: TipoHecho
    ocurrido_en: Instante
    quien: QuienCopia
    campo: Campo | None
    seccion: Seccion | None
    # F1 (decisión 384): a qué autorización o a qué pedido se refiere
    finalidad: Literal["plan_cuidado", "consumo", "despacho"] | None
    referencia: str | None


class HistorialCopia(_Cerrado):
    alcance: Literal["todo", "lo_tuyo"]
    hechos: list[HechoCopia]
    hay_hechos_sin_asociar: bool


class CopiaDatosPersona(_Cerrado):
    """Respuesta de GET /v1/personas-cuidadas/{persona_id}/datos (MATU-54, decisión 350)."""

    formato: Literal["matu-datos/1"]
    tipo: Literal["persona_cuidada"]
    generado_en: Instante
    aviso: Literal[AVISO_COPIA]  # type: ignore[valid-type]
    persona: DatosPersonaCopia
    autorizaciones: list[AutorizacionCopia]
    ficha: FichaCopia
    enlaces_relevo: list[EnlaceRelevoCopia]
    insumos: InsumosCopia
    pedidos: list[PedidoCopia] | None
    historial: HistorialCopia
