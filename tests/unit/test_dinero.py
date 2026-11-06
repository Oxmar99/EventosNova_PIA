from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from src.domain.exceptions import ImporteInvalido
from src.domain.value_objects import Dinero


def test_conserva_un_importe_valido():
    dinero = Dinero("1250.50")

    assert dinero.monto == Decimal("1250.50")
    assert dinero.moneda == "MXN"


def test_permite_saldo_cero():
    assert Dinero("0").monto == Decimal("0.00")


def test_redondea_a_centavos():
    assert Dinero("10.125").monto == Decimal("10.13")


@pytest.mark.parametrize(
    "valor",
    ["-1", "-0.001", "NaN", "Infinity", "texto", 0.1, True],
)
def test_rechaza_importes_invalidos(valor):
    with pytest.raises(ImporteInvalido):
        Dinero(valor)


def test_rechaza_otra_moneda():
    with pytest.raises(ImporteInvalido):
        Dinero("100", moneda="USD")


def test_el_importe_es_inmutable():
    dinero = Dinero("100")

    with pytest.raises(FrozenInstanceError):
        dinero.monto = Decimal("200")