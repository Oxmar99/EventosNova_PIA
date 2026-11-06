from decimal import Decimal

from pydantic import BaseModel, Field


class LineaEntrada(BaseModel):
    recurso_id: str = Field(min_length=1, max_length=100)
    descripcion: str = Field(min_length=1, max_length=500)
    precio_unitario: Decimal = Field(
        ge=0,
        max_digits=14,
        decimal_places=2,
    )
    cantidad: int = Field(strict=True, gt=0, le=1_000_000)


class PropuestaEntrada(BaseModel):
    evento_id: str = Field(min_length=1, max_length=100)
    lineas: list[LineaEntrada] = Field(min_length=1)


class LineaSalida(BaseModel):
    recurso_id: str
    descripcion: str
    precio_unitario: str
    cantidad: int
    subtotal: str


class PropuestaSalida(BaseModel):
    id: str
    evento_id: str
    estado: str
    version: str
    total: str
    lineas: list[LineaSalida]