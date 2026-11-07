from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from src.api.security import exigir_administracion
from src.application.evento_service import EventoService
from src.domain.value_objects import Dinero
from src.infrastructure.evento_repository import (
    SqlAlchemyRepositorioDeEventos,
)
from src.infrastructure.propuesta_repository import (
    SqlAlchemyRepositorioDePropuestas,
)
from src.infrastructure.unit_of_work import SqlAlchemyUnitOfWork


router = APIRouter(
    prefix="/eventos",
    tags=["Eventos"],
    dependencies=[Depends(exigir_administracion)],
)


class EventoEntrada(BaseModel):
    evento_id: str = Field(min_length=1, max_length=100)


class ContratoEntrada(BaseModel):
    propuesta_id: str = Field(min_length=1, max_length=36)
    referencia: str = Field(min_length=1, max_length=200)


class AnticipoEntrada(BaseModel):
    monto: Decimal = Field(
        gt=0,
        max_digits=14,
        decimal_places=2,
    )


class ContratoSalida(BaseModel):
    referencia: str
    propuesta_id: str
    version: int
    total: str


class EventoSalida(BaseModel):
    id: str
    estado: str
    contrato: ContratoSalida | None
    total_pagado: str
    cantidad_pagos: int
    requiere_anticipo: bool
    total_actual: str
    saldo: str


def obtener_servicio(request: Request):
    fabrica = request.app.state.fabrica_sesiones

    return EventoService(
        crear_uow=lambda: SqlAlchemyUnitOfWork(fabrica),
        crear_repositorio_eventos=SqlAlchemyRepositorioDeEventos,
        crear_repositorio_propuestas=SqlAlchemyRepositorioDePropuestas,
    )


def convertir_salida(evento):
    contrato = None

    if evento.contrato is not None:
        contrato = ContratoSalida(
            referencia=evento.contrato.referencia,
            propuesta_id=evento.contrato.propuesta_id,
            version=evento.contrato.version,
            total=str(evento.contrato.total.monto),
        )

    return EventoSalida(
        id=evento.id,
        estado=evento.estado.value,
        contrato=contrato,
        total_pagado=str(evento.total_pagado.monto),
        cantidad_pagos=len(evento.pagos),
        requiere_anticipo=evento.requiere_anticipo,
        total_actual=str(evento.total_actual.monto),
        saldo=str(evento.saldo),
    )


@router.post("", response_model=EventoSalida, status_code=201)
def crear_evento(
    datos: EventoEntrada,
    servicio: EventoService = Depends(obtener_servicio),
):
    return convertir_salida(servicio.crear(datos.evento_id))


@router.get("/{evento_id}", response_model=EventoSalida)
def consultar_evento(
    evento_id: str,
    servicio: EventoService = Depends(obtener_servicio),
):
    return convertir_salida(servicio.consultar(evento_id))


@router.post("/{evento_id}/contrato", response_model=EventoSalida)
def registrar_contrato(
    evento_id: str,
    datos: ContratoEntrada,
    servicio: EventoService = Depends(obtener_servicio),
):
    evento = servicio.registrar_contrato(
        evento_id,
        datos.propuesta_id,
        datos.referencia,
    )
    return convertir_salida(evento)


@router.post("/{evento_id}/anticipos", response_model=EventoSalida)
def registrar_anticipo(
    evento_id: str,
    datos: AnticipoEntrada,
    responsable: str = Depends(exigir_administracion),
    servicio: EventoService = Depends(obtener_servicio),
):
    evento = servicio.registrar_anticipo(
        evento_id,
        Dinero(datos.monto),
        responsable,
    )
    return convertir_salida(evento)