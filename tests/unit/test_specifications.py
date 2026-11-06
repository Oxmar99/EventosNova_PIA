from types import SimpleNamespace

import pytest

from src.domain.specifications import (
    AnticipoSuficienteSpecification,
    PUEDE_CONFIRMARSE,
    PUEDE_RECIBIR_ANTICIPO,
    REQUIERE_ANTICIPO,
    TieneContratoSpecification,
)
from src.domain.value_objects import Dinero


def candidato(pagado="0", estado="SOLICITADO", con_contrato=True):
    contrato = (
        SimpleNamespace(total=Dinero("1000"))
        if con_contrato
        else None
    )

    return SimpleNamespace(
        contrato=contrato,
        total_pagado=Dinero(pagado),
        estado=SimpleNamespace(value=estado),
    )


def test_detecta_ausencia_de_contrato():
    evento = candidato(con_contrato=False)

    assert not TieneContratoSpecification().cumple(evento)
    assert not AnticipoSuficienteSpecification().cumple(evento)
    assert not PUEDE_CONFIRMARSE.cumple(evento)


@pytest.mark.parametrize(
    "pagado, esperado",
    [
        ("299.99", False),
        ("300.00", True),
        ("300.01", True),
    ],
)
def test_umbral_del_anticipo(pagado, esperado):
    regla = AnticipoSuficienteSpecification()

    assert regla.cumple(candidato(pagado=pagado)) is esperado


@pytest.mark.parametrize(
    "estado, esperado",
    [
        ("SOLICITADO", True),
        ("CONFIRMADO", True),
        ("CERRADO", False),
    ],
)
def test_or_de_estados_para_recibir_anticipo(estado, esperado):
    assert (
        PUEDE_RECIBIR_ANTICIPO.cumple(candidato(estado=estado))
        is esperado
    )


def test_and_exige_estado_solicitado_para_confirmar():
    assert PUEDE_CONFIRMARSE.cumple(candidato(pagado="300"))

    assert not PUEDE_CONFIRMARSE.cumple(
        candidato(pagado="300", estado="CONFIRMADO")
    )


def test_not_detecta_anticipo_pendiente():
    assert REQUIERE_ANTICIPO.cumple(candidato(pagado="299.99"))
    assert not REQUIERE_ANTICIPO.cumple(candidato(pagado="300"))