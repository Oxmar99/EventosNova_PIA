from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from src.api.security import exigir_administracion
from src.infrastructure.evento_repository import (
    SqlAlchemyRepositorioDeEventos,
)
from src.infrastructure.fecha_evento_repository import (
    SqlAlchemyRepositorioDeFechas,
)
from src.infrastructure.unit_of_work import SqlAlchemyUnitOfWork


router = APIRouter(
    prefix="/eventos",
    tags=["Eventos"],
    dependencies=[Depends(exigir_administracion)],
)


class FechaEntrada(BaseModel):
    fecha: date


class FechaSalida(BaseModel):
    evento_id: str
    fecha: date


@router.put("/{evento_id}/fecha", response_model=FechaSalida)
def registrar_fecha(
    evento_id: str,
    datos: FechaEntrada,
    request: Request,
    responsable: str = Depends(exigir_administracion),
):
    fabrica = request.app.state.fabrica_sesiones

    try:
        with SqlAlchemyUnitOfWork(fabrica) as uow:
            eventos = SqlAlchemyRepositorioDeEventos(uow.session)
            fechas = SqlAlchemyRepositorioDeFechas(uow.session)

            if eventos.obtener(evento_id) is None:
                raise HTTPException(404, "El evento no existe.")

            existente = fechas.obtener(evento_id)

            if existente is not None and existente != datos.fecha:
                raise HTTPException(
                    409,
                    "La fecha ya está registrada. "
                    "La reprogramación requiere un proceso específico.",
                )

            if existente is None:
                fechas.agregar(evento_id, datos.fecha, responsable)

            uow.commit()

    except IntegrityError as error:
        raise HTTPException(
            409,
            "La fecha fue registrada por otra operación. Consulta su valor.",
        ) from error

    return FechaSalida(evento_id=evento_id, fecha=datos.fecha)


@router.get("/{evento_id}/fecha", response_model=FechaSalida)
def consultar_fecha(evento_id: str, request: Request):
    fabrica = request.app.state.fabrica_sesiones

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        eventos = SqlAlchemyRepositorioDeEventos(uow.session)
        fechas = SqlAlchemyRepositorioDeFechas(uow.session)

        if eventos.obtener(evento_id) is None:
            raise HTTPException(404, "El evento no existe.")

        fecha = fechas.obtener(evento_id)

        if fecha is None:
            raise HTTPException(404, "El evento no tiene fecha registrada.")

        return FechaSalida(evento_id=evento_id, fecha=fecha)