from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.domain.cambios import (
    CambioInvalido,
    EstadoCambio,
    SolicitudDeCambio,
)
from src.domain.exceptions import (
    OperacionNoAutorizada,
    TransicionInvalida,
)
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
def propuesta():
    propuesta = Propuesta(
        evento_id="EVE-O001",
        lineas=lineas("1000"),
    )
    propuesta.enviar()
    propuesta.aceptar()
    return propuesta


def solicitar(propuesta, dias=14, nuevo_total="1200"):
    return SolicitudDeCambio(
        propuesta=propuesta,
        nuevas_lineas=lineas(nuevo_total),
        fecha_evento=FECHA_EVENTO,
        fecha_solicitud=FECHA_EVENTO - timedelta(days=dias),
        solicitante="cliente-001",
        motivo="Agregar servicios",
    )


def test_cambio_tardio_calcula_cargo_sobre_incremento(propuesta):
    cambio = solicitar(propuesta)

    assert cambio.estado == EstadoCambio.PENDIENTE_AUTORIZACION
    assert cambio.evaluacion.incremento.monto == Decimal("200.00")
    assert cambio.evaluacion.cargo.monto == Decimal("30.00")
    assert cambio.evaluacion.importe_adicional.monto == Decimal("230.00")


def test_cambio_a_15_dias_no_requiere_autorizacion(propuesta):
    cambio = solicitar(propuesta, dias=15)

    assert cambio.estado == EstadoCambio.LISTO_PARA_APLICAR
    assert cambio.evaluacion.cargo.monto == Decimal("0.00")
    assert cambio.autorizado_por is None


def test_solicitar_no_modifica_historial_original(propuesta):
    versiones_antes = propuesta.versiones
    eventos_antes = propuesta.eventos

    cambio = solicitar(propuesta)

    assert propuesta.versiones == versiones_antes
    assert propuesta.eventos == eventos_antes
    assert propuesta.version_vigente.total.monto == Decimal("1000.00")
    assert cambio.version_propuesta.total.monto == Decimal("1200.00")
    assert cambio.version_propuesta.numero == 2


def test_administracion_autoriza_y_registra_responsable(propuesta):
    cambio = solicitar(propuesta)
    fecha = FECHA_EVENTO - timedelta(days=13)

    cambio.autorizar("admin-001", "ADMINISTRACION", fecha)

    assert cambio.estado == EstadoCambio.LISTO_PARA_APLICAR
    assert cambio.autorizado_por == "admin-001"
    assert cambio.fecha_autorizacion == fecha
    assert cambio.eventos[-1].tipo == "CambioAutorizado"

    # Autorizar no equivale a aplicar el cambio.
    assert propuesta.version_vigente.numero == 1


def test_cliente_no_puede_autorizar(propuesta):
    cambio = solicitar(propuesta)
    eventos_antes = cambio.eventos

    with pytest.raises(OperacionNoAutorizada):
        cambio.autorizar(
            "cliente-001",
            "CLIENTE",
            FECHA_EVENTO - timedelta(days=13),
        )

    assert cambio.estado == EstadoCambio.PENDIENTE_AUTORIZACION
    assert cambio.autorizado_por is None
    assert cambio.eventos == eventos_antes


def test_no_autoriza_dos_veces(propuesta):
    cambio = solicitar(propuesta)
    fecha = FECHA_EVENTO - timedelta(days=13)
    cambio.autorizar("admin-001", "ADMINISTRACION", fecha)
    eventos_antes = cambio.eventos

    with pytest.raises(TransicionInvalida):
        cambio.autorizar("admin-001", "ADMINISTRACION", fecha)

    assert cambio.eventos == eventos_antes


def test_rechaza_reduccion_de_precio_no_soportada(propuesta):
    with pytest.raises(CambioInvalido):
        solicitar(propuesta, nuevo_total="900")


def test_rechaza_cambio_sobre_propuesta_no_aceptada():
    borrador = Propuesta(
        evento_id="EVE-O001",
        lineas=lineas("1000"),
    )

    with pytest.raises(TransicionInvalida):
        solicitar(borrador)