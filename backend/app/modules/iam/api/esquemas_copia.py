"""Esquemas de «Tus datos» (MATU-54, contrato docs/api/propuestos/mis-datos.openapi.yaml).

Todos con ``extra="forbid"`` (C5). Nada de una persona cuidada, ningún id, ni el push_token, la contraseña, el secreto
del doble factor, la huella del correo, los hashes de sesión, el token, la orden ni el código de autorización.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.shared.copia_datos import AVISO_COPIA

Instante = str


class _Cerrado(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CuentaCopia(_Cerrado):
    nombre: str
    correo: str
    celular: str | None
    celular_confirmado: bool
    canal_codigos: Literal["sms", "whatsapp"]
    creada_en: Instante


class PoliticaCopia(_Cerrado):
    version: str
    huella: str
    aceptada_en: Instante


class GrupoCopia(_Cerrado):
    nombre: str
    rol: Literal["admin", "cuidador", "pagador", "observador"]
    unido_en: Instante
    puede_ver_ficha: bool | None


class GrupoQueDejasteCopia(_Cerrado):
    """F2 del cierre del analista (decisión 401): una membresía retirada, sin el nombre del grupo, que ya no se puede
    leer. La pantalla la muestra como «Un grupo del que saliste»."""

    rol: Literal["admin", "cuidador", "pagador", "observador"]
    unido_en: Instante
    retirado_en: Instante | None


Clase = Literal["telefono", "computador", "otro"]


class DispositivoCopia(_Cerrado):
    nombre: str
    clase: Clase
    creado_en: Instante
    ultimo_uso_en: Instante | None
    cerrado_en: Instante | None
    avisos_activos: bool


class PreferenciaAvisosCopia(_Cerrado):
    correo: bool
    push: bool


class DispositivoDelEventoCopia(_Cerrado):
    nombre: str
    clase: Clase


class EventoCuentaCopia(_Cerrado):
    tipo: Literal[
        "entraste", "saliste", "cerraste_en_dispositivo", "salida_por_seguridad", "contrasena_cambiada",
        "celular_confirmado", "codigo_recuperacion_pedido", "avisos_cambiados", "avisos_activados",
        "avisos_desactivados", "pediste_una_copia",
    ]
    ocurrido_en: Instante
    dispositivo: DispositivoDelEventoCopia | None


class AvisoEnviadoCopia(_Cerrado):
    creado_en: Instante
    enviado_en: Instante | None
    canal: Literal["correo", "push", "sms"]
    resultado: Literal["salio", "no_salio", "pendiente", "en_el_piloto_no_salio"]


class TarjetaCopia(_Cerrado):
    tipo: Literal["credito", "debito", "prepago"]
    ultimos4: str
    cuotas: int


class PagoCuentaCopia(_Cerrado):
    grupo: str
    referencia: str | None
    pagado_en: Instante
    cobrado: int
    devuelto: int
    tarjeta: TarjetaCopia | None
    # F3 del cierre del analista (decisión 402): solo en «Tus datos» de quien pagó, que ya lo ve en su comprobante
    codigo_autorizacion: str | None
    pago_de_prueba: bool


class CondicionesCopia(_Cerrado):
    grupo: str
    referencia: str | None
    version: str
    huella: str
    aceptadas_en: Instante


class CopiaDatosCuenta(_Cerrado):
    """Respuesta de GET /v1/yo/datos (MATU-54, decisiones 358 a 360)."""

    formato: Literal["matu-datos/1"]
    tipo: Literal["cuenta"]
    generado_en: Instante
    aviso: Literal[AVISO_COPIA]  # type: ignore[valid-type]
    cuenta: CuentaCopia
    politica: PoliticaCopia | None
    grupos: list[GrupoCopia]
    grupos_que_dejaste: list[GrupoQueDejasteCopia]
    dispositivos: list[DispositivoCopia]
    preferencia_avisos: PreferenciaAvisosCopia
    eventos: list[EventoCuentaCopia]
    avisos_enviados: list[AvisoEnviadoCopia]
    envio_simulado: bool
    pagos: list[PagoCuentaCopia] | None
    condiciones_aceptadas: list[CondicionesCopia] | None
