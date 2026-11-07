import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from src.api.schemas import LineaEntrada
from src.api.security import exigir_administracion
from src.application.cambio_service import CambioService
from src.domain.propuestas import LineaDeServicio
from src.domain.value_objects import Dinero
from src.infrastructure.cambio_repository import (
    SqlAlchemyRepositorioDeCambios,
)
from src.infrastructure.evento_repository import (
    SqlAlchemyRepositorioDeEventos,
)
from src.infrastructure.propuesta_repository import (
    SqlAlchemyRepositorioDePropuestas,
)
from src.infrastructure.unit_of_work import SqlAlchemyUnitOfWork

from src.infrastructure.fecha_evento_repository import (
    SqlAlchemyRepositorioDeFechas,
)


router = APIRouter(
    prefix="/cambios",
    tags=["Cambios"],
    dependencies=[Depends(exigir_administracion)],
)


class CambioEntrada(BaseModel):
    model_config = {"extra": "forbid"}

    evento_id: str = Field(min_length=1, max_length=100)
    propuesta_id: str = Field(min_length=1, max_length=36)
    motivo: str = Field(min_length=1, max_length=1000)
    nuevas_lineas: list[LineaEntrada] = Field(min_length=1)


class CambioSalida(BaseModel):
    id: str
    evento_id: str
    propuesta_id: str
    estado: str
    fecha_evento: date
    fecha_solicitud: date
    solicitante: str
    motivo: str
    version_anterior: str
    version_propuesta: str
    total_anterior: str
    total_propuesto: str
    incremento: str
    cargo: str
    importe_adicional: str
    requiere_autorizacion: bool
    autorizado_por: str | None
    fecha_autorizacion: date | None


def hoy_negocio():
    zona = ZoneInfo(
        os.getenv("APP_TIMEZONE", "America/Monterrey")
    )
    return datetime.now(zona).date()


def obtener_servicio(request: Request):
    fabrica = request.app.state.fabrica_sesiones

    return CambioService(
        crear_uow=lambda: SqlAlchemyUnitOfWork(fabrica),
        crear_eventos=SqlAlchemyRepositorioDeEventos,
        crear_propuestas=SqlAlchemyRepositorioDePropuestas,
        crear_cambios=SqlAlchemyRepositorioDeCambios,
        fecha_actual=hoy_negocio,
        crear_fechas=SqlAlchemyRepositorioDeFechas,
    )


def convertir_salida(cambio):
    return CambioSalida(
        id=cambio.id,
        evento_id=cambio.evento_id,
        propuesta_id=cambio.propuesta_id,
        estado=cambio.estado.value,
        fecha_evento=cambio.fecha_evento,
        fecha_solicitud=cambio.fecha_solicitud,
        solicitante=cambio.solicitante,
        motivo=cambio.motivo,
        version_anterior=cambio.version_anterior.etiqueta,
        version_propuesta=cambio.version_propuesta.etiqueta,
        total_anterior=str(cambio.version_anterior.total.monto),
        total_propuesto=str(cambio.version_propuesta.total.monto),
        incremento=str(cambio.evaluacion.incremento.monto),
        cargo=str(cambio.evaluacion.cargo.monto),
        importe_adicional=str(
            cambio.evaluacion.importe_adicional.monto
        ),
        requiere_autorizacion=cambio.evaluacion.requiere_autorizacion,
        autorizado_por=cambio.autorizado_por,
        fecha_autorizacion=cambio.fecha_autorizacion,
    )


@router.post("", response_model=CambioSalida, status_code=201)
def solicitar_cambio(
    datos: CambioEntrada,
    responsable: str = Depends(exigir_administracion),
    servicio: CambioService = Depends(obtener_servicio),
):
    lineas = tuple(
        LineaDeServicio(
            recurso_id=linea.recurso_id,
            descripcion=linea.descripcion,
            precio_unitario=Dinero(linea.precio_unitario),
            cantidad=linea.cantidad,
        )
        for linea in datos.nuevas_lineas
    )

    cambio = servicio.solicitar(
        evento_id=datos.evento_id,
        propuesta_id=datos.propuesta_id,
        nuevas_lineas=lineas,
        solicitante=responsable,
        motivo=datos.motivo,
    )
    return convertir_salida(cambio)


@router.get("/{cambio_id}", response_model=CambioSalida)
def consultar_cambio(
    cambio_id: str,
    servicio: CambioService = Depends(obtener_servicio),
):
    return convertir_salida(servicio.consultar(cambio_id))


@router.post("/{cambio_id}/autorizar", response_model=CambioSalida)
def autorizar_cambio(
    cambio_id: str,
    responsable: str = Depends(exigir_administracion),
    servicio: CambioService = Depends(obtener_servicio),
):
    return convertir_salida(
        servicio.autorizar_y_aplicar(cambio_id, responsable)
    )