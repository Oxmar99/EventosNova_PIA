from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from src.api.schemas import (
    LineaSalida,
    PropuestaEntrada,
    PropuestaSalida,
)
from src.application.propuesta_service import (
    PropuestaNoEncontrada,
    PropuestaService,
)
from src.domain.exceptions import (
    ErrorDeDominio,
    OperacionNoAutorizada,
    TransicionInvalida,
)
from src.domain.propuestas import LineaDeServicio
from src.domain.value_objects import Dinero
from src.infrastructure.database import (
    Base,
    crear_fabrica_sesiones,
    crear_motor,
)
from src.infrastructure.propuesta_repository import (
    SqlAlchemyRepositorioDePropuestas,
)
from src.infrastructure.unit_of_work import SqlAlchemyUnitOfWork

from src.infrastructure.evento_models import EventoRow, PagoRow

from src.api.evento_routes import router as eventos_router
from src.application.evento_service import EventoNoEncontrado

from src.api.proveedor_routes import router as proveedores_router

from src.api.cambio_routes import router as cambios_router
from src.application.cambio_service import CambioNoEncontrado
from sqlalchemy.orm.exc import StaleDataError

@asynccontextmanager
async def lifespan(app):
    motor = crear_motor()

    try:
        Base.metadata.create_all(motor)
        app.state.fabrica_sesiones = crear_fabrica_sesiones(motor)
        yield
    finally:
        motor.dispose()


app = FastAPI(
    title="Eventos Nova API",
    description="Gestión de propuestas, eventos y proveedores.",
    version="0.2.0",
    lifespan=lifespan,
)


def obtener_servicio(request: Request):
    fabrica = request.app.state.fabrica_sesiones

    return PropuestaService(
        crear_uow=lambda: SqlAlchemyUnitOfWork(fabrica),
        crear_repositorio=SqlAlchemyRepositorioDePropuestas,
    )


def convertir_salida(propuesta):
    version = propuesta.version_vigente

    return PropuestaSalida(
        id=propuesta.id,
        evento_id=propuesta.evento_id,
        estado=propuesta.estado.value,
        version=version.etiqueta,
        total=str(version.total.monto),
        lineas=[
            LineaSalida(
                recurso_id=linea.recurso_id,
                descripcion=linea.descripcion,
                precio_unitario=str(linea.precio_unitario.monto),
                cantidad=linea.cantidad,
                subtotal=str(linea.subtotal.monto),
            )
            for linea in version.lineas
        ],
    )


@app.exception_handler(PropuestaNoEncontrada)
async def propuesta_no_encontrada(request, error):
    return JSONResponse(
        status_code=404,
        content={"detail": str(error)},
    )


@app.exception_handler(ErrorDeDominio)
async def error_de_dominio(request, error):
    if isinstance(error, OperacionNoAutorizada):
        codigo = 403
    elif isinstance(error, TransicionInvalida):
        codigo = 409
    else:
        codigo = 422

    return JSONResponse(
        status_code=codigo,
        content={"detail": str(error)},
    )


@app.get("/health", tags=["Estado"])
def health_check():
    return {"status": "ok", "application": "Eventos Nova"}


@app.post(
    "/propuestas",
    response_model=PropuestaSalida,
    status_code=201,
    tags=["Propuestas"],
)
def crear_propuesta(
    datos: PropuestaEntrada,
    servicio: PropuestaService = Depends(obtener_servicio),
):
    lineas = tuple(
        LineaDeServicio(
            recurso_id=linea.recurso_id,
            descripcion=linea.descripcion,
            precio_unitario=Dinero(linea.precio_unitario),
            cantidad=linea.cantidad,
        )
        for linea in datos.lineas
    )

    propuesta = servicio.crear(datos.evento_id, lineas)
    return convertir_salida(propuesta)


@app.get(
    "/propuestas/{propuesta_id}",
    response_model=PropuestaSalida,
    tags=["Propuestas"],
    responses={404: {"description": "Propuesta inexistente"}},
)
def consultar_propuesta(
    propuesta_id: str,
    servicio: PropuestaService = Depends(obtener_servicio),
):
    return convertir_salida(servicio.consultar(propuesta_id))


@app.post(
    "/propuestas/{propuesta_id}/enviar",
    response_model=PropuestaSalida,
    tags=["Propuestas"],
    responses={
        404: {"description": "Propuesta inexistente"},
        409: {"description": "Transición no permitida"},
    },
)
def enviar_propuesta(
    propuesta_id: str,
    servicio: PropuestaService = Depends(obtener_servicio),
):
    return convertir_salida(servicio.enviar(propuesta_id))


@app.post(
    "/propuestas/{propuesta_id}/aceptar",
    response_model=PropuestaSalida,
    tags=["Propuestas"],
    responses={
        404: {"description": "Propuesta inexistente"},
        409: {"description": "Transición no permitida"},
    },
)
def aceptar_propuesta(
    propuesta_id: str,
    servicio: PropuestaService = Depends(obtener_servicio),
):
    return convertir_salida(servicio.aceptar(propuesta_id))

@app.exception_handler(EventoNoEncontrado)
async def evento_no_encontrado(request, error):
    return JSONResponse(
        status_code=404,
        content={"detail": str(error)},
    )


app.include_router(eventos_router)

app.include_router(proveedores_router)

@app.exception_handler(CambioNoEncontrado)
async def cambio_no_encontrado(request, error):
    return JSONResponse(
        status_code=404,
        content={"detail": str(error)},
    )


@app.exception_handler(StaleDataError)
async def conflicto_de_actualizacion(request, error):
    return JSONResponse(
        status_code=409,
        content={
            "detail": (
                "Otro proceso modificó los datos. "
                "Consulta su estado actual antes de reintentar."
            )
        },
    )


app.include_router(cambios_router)