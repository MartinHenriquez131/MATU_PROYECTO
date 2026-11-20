"""Adaptador SQL de NotasDelPedido (MATU-128): «Lo que pasó con tu pedido» para quien lo pagó, por pedido_lo_que_paso.

Lee en la transacción de la petición (sesion_de_grupo), como matu_app. Quien pagó no lee incidencia ni clave_notas con
un SELECT directo (incidencia_familia y clave_notas_familia_leer exigen app_escribe_plan()): la función SECURITY
DEFINER de la 0036 exige que haya pagado ese pedido y esté activo en el grupo, y devuelve columnas fijas, sin quién lo
anotó ni a quién se asignó, más la clave de las notas de ese pedido. El id de la incidencia sirve solo para el AAD.

Falla cerrada como la copia de los datos (decisión de Jorge del 17-11): sin nada anotado no abre nada, ni pide la KEK
(E4); con algo que descifrar y sin la KEK, con otra KEK o con una clave que no se ve, NotasNoDisponibles (503). Con la
clave destruida, la nota sale como no disponible. Ningún texto ni DEK va a un log, un error o un repr.
"""

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.backoffice.application.pedidos_familia import CosaAnotada
from app.shared.notas_operacion import CustodiaNotas, descifrar_nota
from app.shared.notas_operacion_sql import abrir_clave

_LO_QUE_PASO = text(
    "SELECT id, tipo, estado, creada_en, resuelta_en, descripcion, resolucion, nota_dek_cifrada, nota_kek_version,"
    " resolucion_dek_cifrada, resolucion_kek_version FROM pedido_lo_que_paso(:pedido)"
)


def _bytes(valor: Any) -> bytes | None:
    return None if valor is None else bytes(valor)


class NotasDelPedidoSQL:
    def __init__(self, sesion: Session, custodia: CustodiaNotas | None) -> None:
        self._sesion = sesion
        self._custodia = custodia

    def __repr__(self) -> str:
        return "NotasDelPedidoSQL()"

    def del_pedido(self, pedido_id: uuid.UUID) -> list[CosaAnotada]:
        cosas: list[CosaAnotada] = []
        for f in self._sesion.execute(_LO_QUE_PASO, {"pedido": pedido_id}).all():
            dek = abrir_clave(self._custodia, _bytes(f.nota_dek_cifrada), f.nota_kek_version)
            nota = descifrar_nota(dek, f.id, "descripcion", bytes(f.descripcion))
            resolucion = None
            if f.resolucion is not None:
                dek_resolucion = abrir_clave(self._custodia, _bytes(f.resolucion_dek_cifrada),
                                             f.resolucion_kek_version)
                resolucion = descifrar_nota(dek_resolucion, f.id, "resolucion", bytes(f.resolucion))
            # Como «Datos de» (copia_pagos.py): si una de las dos no se lee, ninguna sale
            disponible = nota is not None and (f.resolucion is None or resolucion is not None)
            cosas.append(
                CosaAnotada(
                    tipo=f.tipo,
                    estado=f.estado,
                    anotado_en=f.creada_en,
                    resuelto_en=f.resuelta_en,
                    nota=nota if disponible else None,
                    resolucion=resolucion if disponible else None,
                    nota_disponible=disponible,
                )
            )
        return cosas
