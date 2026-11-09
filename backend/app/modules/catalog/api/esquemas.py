"""Esquemas de GET /v1/catalogo (MATU-59, decisión 160 de docs/api/README.md).

Del comercio solo viajan comercio_id y nombre_fantasia (condición 3): nunca razon_social, rut, direccion, comuna
ni telefono. Del stock, solo disponible (decisión 161). Sin grupo, persona ni nada de quien mira.
"""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OfertaCatalogo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    oferta_id: uuid.UUID
    comercio_id: uuid.UUID
    nombre_fantasia: str = Field(
        description="El nombre del comercio que se muestra. La pantalla agrega «(comercio ficticio)»"
    )
    precio: int = Field(gt=0, description="Precio exacto en pesos enteros, con IVA. Nunca neto (ADR-027)")
    disponible: bool = Field(
        description="Si el comercio tiene el producto. No promete disponibilidad: se confirma antes de pagar"
    )


class ProductoCatalogo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    nombre: str
    presentacion: str = Field(description="Cómo viene, por ejemplo «Paquete de 30 unidades». No repite el nombre (N3)")
    unidad: Literal["unidad", "sobre", "ml", "g"]
    unidades_por_envase: int = Field(gt=0)
    retracto_pierde_al_abrir: bool = Field(
        description="true si el derecho a retracto no aplica al abrir el sello (higiene y uso personal, D2)"
    )
    comercios: list[OfertaCatalogo] = Field(
        description="Cada comercio con su precio y si hay stock, por nombre_fantasia y comercio_id, nunca por precio"
    )


class CategoriaCatalogo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    nombre: str
    orden: int = Field(description="El orden de la categoría; la lista ya viene en este orden")
    productos: list[ProductoCatalogo]


class Catalogo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    precios_de_ejemplo: bool = Field(
        description=(
            "true mientras MATU no tenga convenio con comercios (adaptador simulado): la pantalla rotula los precios"
        )
    )
    categorias: list[CategoriaCatalogo]
