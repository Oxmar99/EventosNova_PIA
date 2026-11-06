from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from src.domain.exceptions import PropuestaInvalida
from src.domain.propuestas import LineaDeServicio, VersionDePropuesta
from src.domain.value_objects import Dinero


def crear_linea(cantidad=2):
    return LineaDeServicio(
        recurso_id="EVE-P001",
        descripcion="Servicio de alimentos",
        precio_unitario=Dinero("150.25"),
        cantidad=cantidad,
    )


def test_calcula_subtotal():
    assert crear_linea().subtotal.monto == Decimal("300.50")


@pytest.mark.parametrize("cantidad", [0, -1, 1.5, True])
def test_rechaza_cantidades_invalidas(cantidad):
    with pytest.raises(PropuestaInvalida):
        crear_linea(cantidad)


def test_calcula_total_de_varios_servicios():
    alimentos = crear_linea()
    mobiliario = LineaDeServicio(
        recurso_id="EVE-P002",
        descripcion="Mobiliario",
        precio_unitario=Dinero("200.00"),
        cantidad=3,
    )

    version = VersionDePropuesta(
        numero=1,
        lineas=(alimentos, mobiliario),
    )

    assert version.total.monto == Decimal("900.50")
    assert version.etiqueta == "V1.0"


def test_rechaza_propuesta_vacia():
    with pytest.raises(PropuestaInvalida):
        VersionDePropuesta(numero=1, lineas=())


def test_conserva_la_version_anterior():
    anterior = VersionDePropuesta(numero=1, lineas=(crear_linea(2),))
    nueva = VersionDePropuesta(numero=2, lineas=(crear_linea(3),))

    assert anterior.total.monto == Decimal("300.50")
    assert nueva.total.monto == Decimal("450.75")
    assert nueva.etiqueta == "V1.1"


def test_no_permite_reemplazar_lineas_de_una_version():
    version = VersionDePropuesta(numero=1, lineas=(crear_linea(),))

    with pytest.raises(FrozenInstanceError):
        version.lineas = ()