from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from src.domain.cambios import CambioInvalido, PoliticaDeCambios
from src.domain.value_objects import Dinero


FECHA_EVENTO = date(2026, 12, 20)


@pytest.mark.parametrize(
    "dias, autorizacion, cargo",
    [
        (16, False, "0.00"),
        (15, False, "0.00"),
        (14, True, "150.00"),
        (0, True, "150.00"),
    ],
)
def test_limite_de_dias(dias, autorizacion, cargo):
    resultado = PoliticaDeCambios().evaluar(
        fecha_evento=FECHA_EVENTO,
        fecha_solicitud=FECHA_EVENTO - timedelta(days=dias),
        incremento=Dinero("1000"),
    )

    assert resultado.dias_de_anticipacion == dias
    assert resultado.requiere_autorizacion is autorizacion
    assert resultado.cargo.monto == Decimal(cargo)


def test_calcula_importe_adicional_con_cargo():
    resultado = PoliticaDeCambios().evaluar(
        fecha_evento=FECHA_EVENTO,
        fecha_solicitud=FECHA_EVENTO - timedelta(days=10),
        incremento=Dinero("1000"),
    )

    assert resultado.importe_adicional.monto == Decimal("1150.00")


def test_cambio_a_tiempo_conserva_incremento_sin_penalizacion():
    resultado = PoliticaDeCambios().evaluar(
        fecha_evento=FECHA_EVENTO,
        fecha_solicitud=FECHA_EVENTO - timedelta(days=15),
        incremento=Dinero("1000"),
    )

    assert resultado.importe_adicional.monto == Decimal("1000.00")
    assert resultado.cargo.monto == Decimal("0.00")


def test_cambio_tardio_sin_incremento_requiere_autorizacion():
    resultado = PoliticaDeCambios().evaluar(
        fecha_evento=FECHA_EVENTO,
        fecha_solicitud=FECHA_EVENTO - timedelta(days=5),
        incremento=Dinero("0"),
    )

    assert resultado.requiere_autorizacion is True
    assert resultado.cargo.monto == Decimal("0.00")


def test_redondea_cargo_a_centavos():
    resultado = PoliticaDeCambios().evaluar(
        fecha_evento=FECHA_EVENTO,
        fecha_solicitud=FECHA_EVENTO - timedelta(days=5),
        incremento=Dinero("10.10"),
    )

    assert resultado.cargo.monto == Decimal("1.52")
    assert resultado.importe_adicional.monto == Decimal("11.62")


def test_rechaza_solicitud_posterior_al_evento():
    with pytest.raises(CambioInvalido):
        PoliticaDeCambios().evaluar(
            fecha_evento=FECHA_EVENTO,
            fecha_solicitud=FECHA_EVENTO + timedelta(days=1),
            incremento=Dinero("1000"),
        )


def test_rechaza_datetime_para_evitar_ambiguedad_de_horas():
    with pytest.raises(CambioInvalido):
        PoliticaDeCambios().evaluar(
            fecha_evento=FECHA_EVENTO,
            fecha_solicitud=datetime(2026, 12, 1, 12, 0),
            incremento=Dinero("1000"),
        )


def test_exige_incremento_como_dinero():
    with pytest.raises(CambioInvalido):
        PoliticaDeCambios().evaluar(
            fecha_evento=FECHA_EVENTO,
            fecha_solicitud=date(2026, 12, 1),
            incremento="1000",
        )