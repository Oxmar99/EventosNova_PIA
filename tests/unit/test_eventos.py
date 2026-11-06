from decimal import Decimal

import pytest

from src.domain.eventos import EstadoEvento, Evento
from src.domain.exceptions import (
    ContratoInvalido,
    OperacionNoAutorizada,
    PagoInvalido,
)
from src.domain.propuestas import LineaDeServicio, Propuesta
from src.domain.value_objects import Dinero


def crear_propuesta(evento_id="EVE-O001", aceptada=True):
    linea = LineaDeServicio(
        recurso_id="EVE-P001",
        descripcion="Paquete de evento",
        precio_unitario=Dinero("1000.00"),
        cantidad=1,
    )
    propuesta = Propuesta(evento_id=evento_id, lineas=(linea,))

    if aceptada:
        propuesta.enviar()
        propuesta.aceptar()

    return propuesta


@pytest.fixture
def evento():
    evento = Evento("EVE-O001")
    evento.registrar_contrato_firmado(
        crear_propuesta(),
        referencia="CON-001",
    )
    return evento


def pagar(evento, monto):
    evento.registrar_anticipo(
        Dinero(monto),
        responsable="admin-001",
        rol="ADMINISTRACION",
    )


def test_registra_contrato_sin_confirmar_evento(evento):
    assert evento.contrato.total.monto == Decimal("1000.00")
    assert evento.estado == EstadoEvento.SOLICITADO
    assert evento.eventos[-1].tipo == "ContratoFirmado"


def test_rechaza_contrato_con_propuesta_no_aceptada():
    evento = Evento("EVE-O001")

    with pytest.raises(ContratoInvalido):
        evento.registrar_contrato_firmado(
            crear_propuesta(aceptada=False),
            "CON-001",
        )

    assert evento.contrato is None
    assert evento.eventos == ()


def test_rechaza_propuesta_de_otro_evento():
    evento = Evento("EVE-O002")

    with pytest.raises(ContratoInvalido):
        evento.registrar_contrato_firmado(
            crear_propuesta(),
            "CON-001",
        )

    assert evento.contrato is None


def test_no_permite_anticipo_sin_contrato():
    evento = Evento("EVE-O001")

    with pytest.raises(ContratoInvalido):
        pagar(evento, "300")

    assert evento.pagos == ()
    assert evento.eventos == ()


def test_solo_administracion_registra_anticipos(evento):
    eventos_antes = evento.eventos

    with pytest.raises(OperacionNoAutorizada):
        evento.registrar_anticipo(
            Dinero("300"),
            responsable="cliente-001",
            rol="CLIENTE",
        )

    assert evento.pagos == ()
    assert evento.eventos == eventos_antes


def test_rechaza_pago_cero(evento):
    eventos_antes = evento.eventos

    with pytest.raises(PagoInvalido):
        pagar(evento, "0")

    assert evento.pagos == ()
    assert evento.eventos == eventos_antes


def test_confirma_al_acumular_exactamente_el_30_por_ciento(evento):
    pagar(evento, "299.99")

    assert evento.estado == EstadoEvento.SOLICITADO

    pagar(evento, "0.01")

    assert evento.total_pagado.monto == Decimal("300.00")
    assert evento.estado == EstadoEvento.CONFIRMADO
    assert evento.eventos[-1].tipo == "EventoConfirmado"


def test_pagos_posteriores_no_duplican_confirmacion(evento):
    pagar(evento, "350")
    pagar(evento, "100")

    confirmaciones = [
        evento_dominio
        for evento_dominio in evento.eventos
        if evento_dominio.tipo == "EventoConfirmado"
    ]

    assert evento.total_pagado.monto == Decimal("450.00")
    assert evento.estado == EstadoEvento.CONFIRMADO
    assert len(confirmaciones) == 1