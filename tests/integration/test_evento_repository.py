from decimal import Decimal

import pytest

from src.domain.eventos import EstadoEvento, Evento
from src.domain.propuestas import LineaDeServicio, Propuesta
from src.domain.value_objects import Dinero
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


@pytest.fixture
def fabrica(tmp_path):
    archivo = (tmp_path / "eventos.db").as_posix()
    motor = crear_motor(f"sqlite:///{archivo}")
    Base.metadata.create_all(motor)

    try:
        yield crear_fabrica_sesiones(motor)
    finally:
        motor.dispose()


def preparar_evento_con_contrato(fabrica):
    propuesta = Propuesta(
        evento_id="EVE-O001",
        lineas=(
            LineaDeServicio(
                recurso_id="EVE-P001",
                descripcion="Paquete de evento",
                precio_unitario=Dinero("1000"),
                cantidad=1,
            ),
        ),
    )
    propuesta.enviar()
    propuesta.aceptar()

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        propuestas = SqlAlchemyRepositorioDePropuestas(uow.session)
        propuestas.agregar(propuesta)

        # Guarda la propuesta antes de insertar el contrato que la referencia.
        uow.session.flush()

        evento = Evento("EVE-O001")
        evento.registrar_contrato_firmado(propuesta, "CON-001")

        eventos = SqlAlchemyRepositorioDeEventos(uow.session)
        eventos.agregar(evento)
        uow.commit()

    return evento.id


def registrar_pago(evento, monto):
    evento.registrar_anticipo(
        Dinero(monto),
        responsable="admin-001",
        rol="ADMINISTRACION",
    )


def test_recupera_contrato_y_estado(fabrica):
    evento_id = preparar_evento_con_contrato(fabrica)

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        repo = SqlAlchemyRepositorioDeEventos(uow.session)
        evento = repo.obtener(evento_id)

    assert evento.estado == EstadoEvento.SOLICITADO
    assert evento.contrato.referencia == "CON-001"
    assert evento.contrato.total.monto == Decimal("1000.00")
    assert evento.pagos == ()
    assert evento.eventos == ()


def test_acumula_pagos_entre_transacciones(fabrica):
    evento_id = preparar_evento_con_contrato(fabrica)

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        repo = SqlAlchemyRepositorioDeEventos(uow.session)
        evento = repo.obtener(evento_id)
        registrar_pago(evento, "299.99")
        repo.guardar(evento)
        uow.commit()

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        repo = SqlAlchemyRepositorioDeEventos(uow.session)
        evento = repo.obtener(evento_id)

        assert evento.estado == EstadoEvento.SOLICITADO
        assert evento.total_pagado.monto == Decimal("299.99")

        registrar_pago(evento, "0.01")
        repo.guardar(evento)
        uow.commit()

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        repo = SqlAlchemyRepositorioDeEventos(uow.session)
        evento = repo.obtener(evento_id)

    assert evento.estado == EstadoEvento.CONFIRMADO
    assert evento.total_pagado.monto == Decimal("300.00")
    assert len(evento.pagos) == 2


def test_rollback_descarta_pago_y_confirmacion(fabrica):
    evento_id = preparar_evento_con_contrato(fabrica)

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        repo = SqlAlchemyRepositorioDeEventos(uow.session)
        evento = repo.obtener(evento_id)
        registrar_pago(evento, "300")
        repo.guardar(evento)

        # Ejecuta las escrituras, pero sale sin commit.
        uow.session.flush()

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        repo = SqlAlchemyRepositorioDeEventos(uow.session)
        evento = repo.obtener(evento_id)

    assert evento.estado == EstadoEvento.SOLICITADO
    assert evento.total_pagado.monto == Decimal("0.00")
    assert evento.pagos == ()