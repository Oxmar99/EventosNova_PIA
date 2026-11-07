from datetime import date
from decimal import Decimal

import pytest

from src.domain.cambios import EstadoCambio, SolicitudDeCambio
from src.domain.eventos import Evento
from src.domain.propuestas import LineaDeServicio, Propuesta
from src.domain.value_objects import Dinero
from src.infrastructure.cambio_repository import (
    SqlAlchemyRepositorioDeCambios,
)
from src.infrastructure.database import (
    Base,
    crear_fabrica_sesiones,
    crear_motor,
)
from src.infrastructure.evento_repository import (
    SqlAlchemyRepositorioDeEventos,
)
from src.infrastructure.propuesta_repository import (
    SqlAlchemyRepositorioDePropuestas,
)
from src.infrastructure.unit_of_work import SqlAlchemyUnitOfWork


def lineas(precio):
    return (
        LineaDeServicio(
            recurso_id="EVE-P001",
            descripcion="Paquete del evento",
            precio_unitario=Dinero(precio),
            cantidad=1,
        ),
    )


@pytest.fixture
def escenario(tmp_path):
    archivo = (tmp_path / "solicitudes_cambio.db").as_posix()
    motor = crear_motor(f"sqlite:///{archivo}")
    Base.metadata.create_all(motor)
    fabrica = crear_fabrica_sesiones(motor)

    propuesta = Propuesta("EVE-O001", lineas("1000"))
    propuesta.enviar()
    propuesta.aceptar()

    evento = Evento("EVE-O001")
    evento.registrar_contrato_firmado(propuesta, "CON-001")
    evento.registrar_anticipo(
        Dinero("300"),
        "admin-001",
        "ADMINISTRACION",
    )

    cambio = SolicitudDeCambio(
        propuesta=propuesta,
        nuevas_lineas=lineas("1200"),
        fecha_evento=date(2026, 12, 20),
        fecha_solicitud=date(2026, 12, 6),
        solicitante="cliente-001",
        motivo="Agregar servicios",
    )

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        propuestas = SqlAlchemyRepositorioDePropuestas(uow.session)
        eventos = SqlAlchemyRepositorioDeEventos(uow.session)
        cambios = SqlAlchemyRepositorioDeCambios(uow.session)

        propuestas.agregar(propuesta)
        uow.session.flush()

        eventos.agregar(evento)
        uow.session.flush()

        cambios.agregar(cambio)
        uow.commit()

    try:
        yield fabrica, cambio.id
    finally:
        motor.dispose()


def test_recupera_solicitud_pendiente_completa(escenario):
    fabrica, cambio_id = escenario

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        repo = SqlAlchemyRepositorioDeCambios(uow.session)
        cambio = repo.obtener(cambio_id)

    assert cambio.id == cambio_id
    assert cambio.estado == EstadoCambio.PENDIENTE_AUTORIZACION
    assert cambio.solicitante == "cliente-001"
    assert cambio.motivo == "Agregar servicios"
    assert cambio.fecha_solicitud == date(2026, 12, 6)

    assert cambio.version_anterior.total.monto == Decimal("1000.00")
    assert cambio.version_propuesta.total.monto == Decimal("1200.00")
    assert cambio.evaluacion.incremento.monto == Decimal("200.00")
    assert cambio.evaluacion.cargo.monto == Decimal("30.00")

    assert cambio.autorizado_por is None
    assert cambio.eventos == ()


def test_autorizacion_persiste_entre_sesiones(escenario):
    fabrica, cambio_id = escenario

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        repo = SqlAlchemyRepositorioDeCambios(uow.session)
        cambio = repo.obtener(cambio_id)

        cambio.autorizar(
            "admin-001",
            "ADMINISTRACION",
            date(2026, 12, 7),
        )
        repo.guardar(cambio)
        uow.commit()

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        repo = SqlAlchemyRepositorioDeCambios(uow.session)
        recuperado = repo.obtener(cambio_id)

    assert recuperado.estado == EstadoCambio.LISTO_PARA_APLICAR
    assert recuperado.autorizado_por == "admin-001"
    assert recuperado.fecha_autorizacion == date(2026, 12, 7)
    assert recuperado.evaluacion.cargo.monto == Decimal("30.00")
    assert recuperado.eventos == ()


def test_rollback_descarta_autorizacion(escenario):
    fabrica, cambio_id = escenario

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        repo = SqlAlchemyRepositorioDeCambios(uow.session)
        cambio = repo.obtener(cambio_id)

        cambio.autorizar(
            "admin-001",
            "ADMINISTRACION",
            date(2026, 12, 7),
        )
        repo.guardar(cambio)
        uow.session.flush()
        # Sin commit: se deshace la autorización.

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        repo = SqlAlchemyRepositorioDeCambios(uow.session)
        recuperado = repo.obtener(cambio_id)

    assert recuperado.estado == EstadoCambio.PENDIENTE_AUTORIZACION
    assert recuperado.autorizado_por is None
    assert recuperado.fecha_autorizacion is None