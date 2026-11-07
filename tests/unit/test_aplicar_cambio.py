from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.domain.cambios import (
    AplicadorDeCambios,
    EstadoCambio,
    SolicitudDeCambio,
)
from src.domain.eventos import Evento
from src.domain.exceptions import TransicionInvalida
from src.domain.propuestas import LineaDeServicio, Propuesta
from src.domain.value_objects import Dinero


FECHA_EVENTO = date(2026, 12, 20)


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
def negocio():
    propuesta = Propuesta(
        evento_id="EVE-O001",
        lineas=lineas("1000"),
    )
    propuesta.enviar()
    propuesta.aceptar()

    evento = Evento("EVE-O001")
    evento.registrar_contrato_firmado(propuesta, "CON-001")
    evento.registrar_anticipo(
        Dinero("300"),
        responsable="admin-001",
        rol="ADMINISTRACION",
    )

    return evento, propuesta


def crear_cambio(propuesta, dias=14, precio="1200"):
    return SolicitudDeCambio(
        propuesta=propuesta,
        nuevas_lineas=lineas(precio),
        fecha_evento=FECHA_EVENTO,
        fecha_solicitud=FECHA_EVENTO - timedelta(days=dias),
        solicitante="cliente-001",
        motivo="Ampliación de servicios",
    )


def autorizar(cambio):
    cambio.autorizar(
        "admin-001",
        "ADMINISTRACION",
        FECHA_EVENTO - timedelta(days=13),
    )


def test_aplica_cambio_autorizado_y_conserva_contrato(negocio):
    evento, propuesta = negocio
    contrato_original = evento.contrato
    version_original = propuesta.version_vigente

    cambio = crear_cambio(propuesta)
    autorizar(cambio)

    AplicadorDeCambios().aplicar(cambio, evento, propuesta)

    assert cambio.estado == EstadoCambio.APLICADO
    assert evento.contrato == contrato_original
    assert propuesta.versiones[0] == version_original
    assert len(propuesta.versiones) == 2
    assert propuesta.version_vigente.total.monto == Decimal("1200.00")
    assert evento.total_actual.monto == Decimal("1230.00")
    assert evento.saldo == Decimal("930.00")
    assert len(evento.ajustes) == 1
    assert evento.eventos[-1].tipo == "CambioAplicado"


def test_no_aplica_cambio_pendiente_de_autorizacion(negocio):
    evento, propuesta = negocio
    cambio = crear_cambio(propuesta)
    eventos_antes = evento.eventos
    propuesta_eventos_antes = propuesta.eventos

    with pytest.raises(TransicionInvalida):
        AplicadorDeCambios().aplicar(cambio, evento, propuesta)

    assert len(propuesta.versiones) == 1
    assert evento.ajustes == ()
    assert evento.total_actual.monto == Decimal("1000.00")
    assert evento.eventos == eventos_antes
    assert propuesta.eventos == propuesta_eventos_antes


def test_no_aplica_dos_veces_el_mismo_cambio(negocio):
    evento, propuesta = negocio
    cambio = crear_cambio(propuesta)
    autorizar(cambio)
    aplicador = AplicadorDeCambios()
    aplicador.aplicar(cambio, evento, propuesta)

    with pytest.raises(TransicionInvalida):
        aplicador.aplicar(cambio, evento, propuesta)

    assert len(evento.ajustes) == 1
    assert len(propuesta.versiones) == 2
    assert evento.total_actual.monto == Decimal("1230.00")


def test_aplica_cambio_a_tiempo_sin_cargo(negocio):
    evento, propuesta = negocio
    cambio = crear_cambio(propuesta, dias=15)

    AplicadorDeCambios().aplicar(cambio, evento, propuesta)

    assert cambio.estado == EstadoCambio.APLICADO
    assert evento.total_actual.monto == Decimal("1200.00")
    assert evento.ajustes[0].cargo.monto == Decimal("0.00")


def test_rechaza_cambio_basado_en_version_anterior(negocio):
    evento, propuesta = negocio

    primero = crear_cambio(propuesta, dias=15, precio="1200")
    segundo = crear_cambio(propuesta, dias=15, precio="1300")

    aplicador = AplicadorDeCambios()
    aplicador.aplicar(primero, evento, propuesta)
    eventos_antes = evento.eventos

    with pytest.raises(TransicionInvalida):
        aplicador.aplicar(segundo, evento, propuesta)

    assert segundo.estado == EstadoCambio.LISTO_PARA_APLICAR
    assert len(propuesta.versiones) == 2
    assert len(evento.ajustes) == 1
    assert evento.total_actual.monto == Decimal("1200.00")
    assert evento.eventos == eventos_antes