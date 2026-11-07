from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.api.security import exigir_administracion
from src.application.proveedor_service import (
    ProveedorService,
    SolicitudNoEncontrada,
)
from src.infrastructure.evento_repository import (
    SqlAlchemyRepositorioDeEventos,
)
from src.infrastructure.proveedor_repository import (
    SqlAlchemyRepositorioDeSolicitudes,
)
from src.infrastructure.unit_of_work import SqlAlchemyUnitOfWork


router = APIRouter(
    prefix="/solicitudes-proveedor",
    tags=["Proveedores"],
    dependencies=[Depends(exigir_administracion)],
)


class SolicitudEntrada(BaseModel):
    evento_id: str = Field(min_length=1, max_length=100)
    proveedor_id: str = Field(min_length=1, max_length=100)
    servicio: str = Field(min_length=1, max_length=500)


class AccionEntrada(BaseModel):
    accion: Literal["confirmar", "rechazar", "expirar"]


class SolicitudSalida(BaseModel):
    id: str
    evento_id: str
    proveedor_id: str
    servicio: str
    estado: str
    enviada_en: datetime
    vence_en: datetime


def ahora_utc():
    return datetime.now(timezone.utc)


def obtener_servicio(request: Request):
    fabrica = request.app.state.fabrica_sesiones

    return ProveedorService(
        crear_uow=lambda: SqlAlchemyUnitOfWork(fabrica),
        crear_eventos=SqlAlchemyRepositorioDeEventos,
        crear_solicitudes=SqlAlchemyRepositorioDeSolicitudes,
        reloj=ahora_utc,
    )


def convertir_salida(solicitud):
    return SolicitudSalida(
        id=solicitud.id,
        evento_id=solicitud.evento_id,
        proveedor_id=solicitud.proveedor_id,
        servicio=solicitud.servicio,
        estado=solicitud.estado.value,
        enviada_en=solicitud.enviada_en,
        vence_en=solicitud.vence_en,
    )


@router.post("", response_model=SolicitudSalida, status_code=201)
def crear_solicitud(
    datos: SolicitudEntrada,
    servicio: ProveedorService = Depends(obtener_servicio),
):
    solicitud = servicio.solicitar(
        datos.evento_id,
        datos.proveedor_id,
        datos.servicio,
    )
    return convertir_salida(solicitud)


@router.get("/{solicitud_id}", response_model=SolicitudSalida)
def consultar_solicitud(
    solicitud_id: str,
    servicio: ProveedorService = Depends(obtener_servicio),
):
    try:
        return convertir_salida(servicio.consultar(solicitud_id))
    except SolicitudNoEncontrada as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/{solicitud_id}/acciones", response_model=SolicitudSalida)
def ejecutar_accion(
    solicitud_id: str,
    datos: AccionEntrada,
    servicio: ProveedorService = Depends(obtener_servicio),
):
    try:
        solicitud = servicio.ejecutar(solicitud_id, datos.accion)
        return convertir_salida(solicitud)
    except SolicitudNoEncontrada as error:
        raise HTTPException(status_code=404, detail=str(error)) from error