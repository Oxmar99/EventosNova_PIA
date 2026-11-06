from decimal import Decimal

import pytest

from src.domain.propuestas import (
    EstadoPropuesta,
    LineaDeServicio,
    Propuesta,
)
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


@pytest.fixture
def fabrica(tmp_path):
    archivo = (tmp_path / "propuestas.db").as_posix()
    motor = crear_motor(f"sqlite:///{archivo}")
    Base.metadata.create_all(motor)

    try:
        yield crear_fabrica_sesiones(motor)
    finally:
        motor.dispose()


def crear_propuesta():
    return Propuesta(
        evento_id="EVE-O001",
        lineas=(
            LineaDeServicio(
                recurso_id="EVE-P001",
                descripcion="Alimentos",
                precio_unitario=Dinero("150.25"),
                cantidad=2,
            ),
            LineaDeServicio(
                recurso_id="EVE-P002",
                descripcion="Mobiliario",
                precio_unitario=Dinero("200"),
                cantidad=3,
            ),
        ),
    )


def test_guarda_y_recupera_propuesta_completa(fabrica):
    original = crear_propuesta()

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        repo = SqlAlchemyRepositorioDePropuestas(uow.session)
        repo.agregar(original)
        uow.commit()

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        repo = SqlAlchemyRepositorioDePropuestas(uow.session)
        recuperada = repo.obtener(original.id)

    assert recuperada.id == original.id
    assert recuperada.evento_id == "EVE-O001"
    assert recuperada.estado == EstadoPropuesta.BORRADOR
    assert recuperada.versiones == original.versiones
    assert recuperada.version_vigente.total.monto == Decimal("900.50")
    assert recuperada.eventos == ()


def test_persiste_transiciones_sin_perder_versiones(fabrica):
    original = crear_propuesta()

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        repo = SqlAlchemyRepositorioDePropuestas(uow.session)
        repo.agregar(original)
        uow.commit()

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        repo = SqlAlchemyRepositorioDePropuestas(uow.session)
        propuesta = repo.obtener(original.id)
        propuesta.enviar()
        repo.guardar_estado(propuesta)
        uow.commit()

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        repo = SqlAlchemyRepositorioDePropuestas(uow.session)
        propuesta = repo.obtener(original.id)
        assert propuesta.estado == EstadoPropuesta.ENVIADA
        propuesta.aceptar()
        repo.guardar_estado(propuesta)
        uow.commit()

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        repo = SqlAlchemyRepositorioDePropuestas(uow.session)
        recuperada = repo.obtener(original.id)

    assert recuperada.estado == EstadoPropuesta.ACEPTADA
    assert recuperada.versiones == original.versiones


def test_rollback_descarta_propuesta_y_sus_detalles(fabrica):
    original = crear_propuesta()

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        repo = SqlAlchemyRepositorioDePropuestas(uow.session)
        repo.agregar(original)

        # Envía los INSERT a la DB, pero no confirma la transacción.
        uow.session.flush()

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        repo = SqlAlchemyRepositorioDePropuestas(uow.session)
        assert repo.obtener(original.id) is None

        from sqlalchemy import func, select
        from src.infrastructure.models import LineaRow, VersionRow

        assert uow.session.scalar(
            select(func.count()).select_from(VersionRow)
        ) == 0
        assert uow.session.scalar(
            select(func.count()).select_from(LineaRow)
        ) == 0