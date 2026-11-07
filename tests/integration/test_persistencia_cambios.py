from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from src.domain.cambios import AplicadorDeCambios, SolicitudDeCambio
from src.domain.eventos import Evento
from src.domain.propuestas import LineaDeServicio, Propuesta
from src.domain.value_objects import Dinero
from src.infrastructure.ajuste_models import AjusteCambioRow
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
    archivo = (tmp_path / "cambios.db").as_posix()
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

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        propuestas = SqlAlchemyRepositorioDePropuestas(uow.session)
        eventos = SqlAlchemyRepositorioDeEventos(uow.session)

        propuestas.agregar(propuesta)
        uow.session.flush()
        eventos.agregar(evento)
        uow.commit()

    try:
        yield fabrica, propuesta.id
    finally:
        motor.dispose()


def aplicar_y_guardar(uow, propuesta_id):
    propuestas = SqlAlchemyRepositorioDePropuestas(uow.session)
    eventos = SqlAlchemyRepositorioDeEventos(uow.session)

    propuesta = propuestas.obtener(propuesta_id)
    evento = eventos.obtener("EVE-O001")

    cambio = SolicitudDeCambio(
        propuesta=propuesta,
        nuevas_lineas=lineas("1200"),
        fecha_evento=date(2026, 12, 20),
        fecha_solicitud=date(2026, 12, 6),
        solicitante="cliente-001",
        motivo="Ampliar servicios",
    )
    cambio.autorizar(
        "admin-001",
        "ADMINISTRACION",
        date(2026, 12, 7),
    )

    AplicadorDeCambios().aplicar(cambio, evento, propuesta)

    propuestas.guardar_versiones(propuesta)
    eventos.guardar(evento)

    return propuestas, eventos, propuesta, evento


def test_commit_conserva_version_y_ajuste(escenario):
    fabrica, propuesta_id = escenario

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        aplicar_y_guardar(uow, propuesta_id)
        uow.commit()

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        propuesta = SqlAlchemyRepositorioDePropuestas(
            uow.session
        ).obtener(propuesta_id)
        evento = SqlAlchemyRepositorioDeEventos(
            uow.session
        ).obtener("EVE-O001")

    assert len(propuesta.versiones) == 2
    assert propuesta.versiones[0].total.monto == Decimal("1000.00")
    assert propuesta.version_vigente.total.monto == Decimal("1200.00")

    assert evento.contrato.total.monto == Decimal("1000.00")
    assert evento.total_actual.monto == Decimal("1230.00")
    assert evento.saldo == Decimal("930.00")
    assert len(evento.ajustes) == 1


def test_error_revierte_version_y_ajuste(escenario):
    fabrica, propuesta_id = escenario

    with pytest.raises(RuntimeError, match="Fallo simulado"):
        with SqlAlchemyUnitOfWork(fabrica) as uow:
            aplicar_y_guardar(uow, propuesta_id)
            uow.session.flush()

            raise RuntimeError("Fallo simulado")

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        propuesta = SqlAlchemyRepositorioDePropuestas(
            uow.session
        ).obtener(propuesta_id)
        evento = SqlAlchemyRepositorioDeEventos(
            uow.session
        ).obtener("EVE-O001")

        cantidad_ajustes = uow.session.scalar(
            select(func.count()).select_from(AjusteCambioRow)
        )

    assert len(propuesta.versiones) == 1
    assert propuesta.version_vigente.total.monto == Decimal("1000.00")
    assert evento.total_actual.monto == Decimal("1000.00")
    assert evento.ajustes == ()
    assert cantidad_ajustes == 0


def test_guardar_dos_veces_no_duplica_ajuste(escenario):
    fabrica, propuesta_id = escenario

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        propuestas, eventos, propuesta, evento = aplicar_y_guardar(
            uow, propuesta_id
        )

        propuestas.guardar_versiones(propuesta)
        eventos.guardar(evento)
        uow.commit()

    with SqlAlchemyUnitOfWork(fabrica) as uow:
        propuesta = SqlAlchemyRepositorioDePropuestas(
            uow.session
        ).obtener(propuesta_id)
        evento = SqlAlchemyRepositorioDeEventos(
            uow.session
        ).obtener("EVE-O001")

    assert len(propuesta.versiones) == 2
    assert len(evento.ajustes) == 1
    assert evento.total_actual.monto == Decimal("1230.00")