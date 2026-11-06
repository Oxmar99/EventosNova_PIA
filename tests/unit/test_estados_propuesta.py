import pytest

from src.domain.exceptions import TransicionInvalida
from src.domain.propuestas import (
    EstadoPropuesta,
    LineaDeServicio,
    Propuesta,
)
from src.domain.value_objects import Dinero


@pytest.fixture
def propuesta():
    linea = LineaDeServicio(
        recurso_id="EVE-P001",
        descripcion="Servicio de alimentos",
        precio_unitario=Dinero("150.25"),
        cantidad=2,
    )
    return Propuesta(evento_id="EVE-O001", lineas=(linea,))


def test_propuesta_inicia_en_borrador(propuesta):
    assert propuesta.estado == EstadoPropuesta.BORRADOR
    assert propuesta.version_vigente.etiqueta == "V1.0"
    assert len(propuesta.eventos) == 1

    evento = propuesta.eventos[0]
    assert evento.tipo == "PropuestaGenerada"
    assert evento.agregado_id == propuesta.id
    assert evento.version == 1


def test_enviar_propuesta(propuesta):
    propuesta.enviar()

    assert propuesta.estado == EstadoPropuesta.ENVIADA
    assert propuesta.eventos[-1].tipo == "PropuestaEnviada"


def test_aceptar_propuesta_enviada(propuesta):
    propuesta.enviar()
    propuesta.aceptar()

    assert propuesta.estado == EstadoPropuesta.ACEPTADA
    assert [evento.tipo for evento in propuesta.eventos] == [
        "PropuestaGenerada",
        "PropuestaEnviada",
        "PropuestaAceptada",
    ]


def test_no_acepta_directamente_desde_borrador(propuesta):
    eventos_antes = propuesta.eventos

    with pytest.raises(TransicionInvalida):
        propuesta.aceptar()

    assert propuesta.estado == EstadoPropuesta.BORRADOR
    assert propuesta.eventos == eventos_antes


def test_no_acepta_dos_veces(propuesta):
    propuesta.enviar()
    propuesta.aceptar()
    eventos_antes = propuesta.eventos

    with pytest.raises(TransicionInvalida):
        propuesta.aceptar()

    assert propuesta.estado == EstadoPropuesta.ACEPTADA
    assert propuesta.eventos == eventos_antes


def test_no_envia_dos_veces(propuesta):
    propuesta.enviar()
    eventos_antes = propuesta.eventos

    with pytest.raises(TransicionInvalida):
        propuesta.enviar()

    assert propuesta.estado == EstadoPropuesta.ENVIADA
    assert propuesta.eventos == eventos_antes