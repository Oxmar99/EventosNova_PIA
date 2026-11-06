import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, select

from src.infrastructure.database import (
    crear_fabrica_sesiones,
    crear_motor,
)
from src.infrastructure.unit_of_work import SqlAlchemyUnitOfWork


@pytest.fixture
def base_prueba(tmp_path):
    archivo = (tmp_path / "pruebas.db").as_posix()
    motor = crear_motor(f"sqlite:///{archivo}")

    metadata = MetaData()
    tabla = Table(
        "registro_prueba",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("descripcion", String(100), nullable=False),
    )
    metadata.create_all(motor)

    fabrica = crear_fabrica_sesiones(motor)

    try:
        yield fabrica, tabla
    finally:
        motor.dispose()


def test_commit_conserva_registro(base_prueba):
    fabrica, tabla = base_prueba

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        uow.session.execute(
            tabla.insert().values(id=1, descripcion="Registro confirmado")
        )
        uow.commit()

    with fabrica() as session:
        descripcion = session.execute(
            select(tabla.c.descripcion).where(tabla.c.id == 1)
        ).scalar_one()

    assert descripcion == "Registro confirmado"


def test_sin_commit_descarta_registro(base_prueba):
    fabrica, tabla = base_prueba

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        uow.session.execute(
            tabla.insert().values(id=1, descripcion="Sin confirmar")
        )

    with fabrica() as session:
        registros = session.execute(select(tabla)).all()

    assert registros == []


def test_error_descarta_toda_la_operacion(base_prueba):
    fabrica, tabla = base_prueba

    with pytest.raises(ValueError, match="Fallo simulado"):
        with SqlAlchemyUnitOfWork(fabrica) as uow:
            uow.session.execute(
                tabla.insert().values(id=1, descripcion="Primero")
            )
            uow.session.execute(
                tabla.insert().values(id=2, descripcion="Segundo")
            )

            raise ValueError("Fallo simulado")

    with fabrica() as session:
        registros = session.execute(select(tabla)).all()

    assert registros == []