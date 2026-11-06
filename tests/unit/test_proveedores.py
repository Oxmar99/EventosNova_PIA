from datetime import datetime, timedelta, timezone

import pytest

from src.domain.exceptions import TransicionInvalida
from src.domain.proveedores import (
    EstadoSolicitud,
    SolicitudDeProveedor,
    SolicitudInvalida,
)


INICIO = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def solicitud():
    return SolicitudDeProveedor(
        evento_id="EVE-O001",
        proveedor_id="PROV-001",
        servicio="Servicio de alimentos",
        enviada_en=INICIO,
    )


def test_solicitud_inicia_pendiente(solicitud):
    assert solicitud.estado == EstadoSolicitud.PENDIENTE
    assert solicitud.vence_en == INICIO + timedelta(hours=48)
    assert solicitud.eventos[0].tipo == "SolicitudAProveedorEnviada"
    assert solicitud.eventos[0].ocurrido_en == INICIO


def test_confirma_antes_del_vencimiento(solicitud):
    ahora = solicitud.vence_en - timedelta(seconds=1)

    solicitud.confirmar(ahora)

    assert solicitud.estado == EstadoSolicitud.CONFIRMADA
    assert solicitud.eventos[-1].tipo == "ProveedorConfirmo"
    assert solicitud.eventos[-1].ocurrido_en == ahora


def test_rechaza_dentro_del_plazo(solicitud):
    solicitud.rechazar(INICIO + timedelta(hours=1))

    assert solicitud.estado == EstadoSolicitud.RECHAZADA
    assert solicitud.eventos[-1].tipo == "ProveedorRechazo"


@pytest.mark.parametrize("accion", ["confirmar", "rechazar"])
def test_no_responde_a_las_48_horas_exactas(solicitud, accion):
    eventos_antes = solicitud.eventos

    with pytest.raises(TransicionInvalida):
        getattr(solicitud, accion)(solicitud.vence_en)

    assert solicitud.estado == EstadoSolicitud.PENDIENTE
    assert solicitud.eventos == eventos_antes


def test_expira_a_las_48_horas_exactas(solicitud):
    solicitud.expirar(solicitud.vence_en)

    assert solicitud.estado == EstadoSolicitud.EXPIRADA
    assert solicitud.eventos[-1].tipo == "SolicitudDeProveedorExpirada"


def test_no_expira_antes_del_plazo(solicitud):
    eventos_antes = solicitud.eventos

    with pytest.raises(TransicionInvalida):
        solicitud.expirar(solicitud.vence_en - timedelta(seconds=1))

    assert solicitud.estado == EstadoSolicitud.PENDIENTE
    assert solicitud.eventos == eventos_antes


@pytest.mark.parametrize("accion", ["confirmar", "rechazar", "expirar"])
def test_solicitud_confirmada_no_se_modifica(solicitud, accion):
    solicitud.confirmar(INICIO + timedelta(hours=1))
    eventos_antes = solicitud.eventos

    with pytest.raises(TransicionInvalida):
        getattr(solicitud, accion)(solicitud.vence_en)

    assert solicitud.estado == EstadoSolicitud.CONFIRMADA
    assert solicitud.eventos == eventos_antes


def test_solicitud_expirada_no_se_confirma(solicitud):
    solicitud.expirar(solicitud.vence_en)
    eventos_antes = solicitud.eventos

    with pytest.raises(TransicionInvalida):
        solicitud.confirmar(solicitud.vence_en + timedelta(seconds=1))

    assert solicitud.estado == EstadoSolicitud.EXPIRADA
    assert solicitud.eventos == eventos_antes


def test_rechaza_fecha_sin_zona_horaria():
    with pytest.raises(SolicitudInvalida):
        SolicitudDeProveedor(
            evento_id="EVE-O001",
            proveedor_id="PROV-001",
            servicio="Alimentos",
            enviada_en=datetime(2026, 11, 6, 12, 0),
        )


def test_rechaza_accion_anterior_al_envio(solicitud):
    eventos_antes = solicitud.eventos

    with pytest.raises(SolicitudInvalida):
        solicitud.confirmar(INICIO - timedelta(seconds=1))

    assert solicitud.estado == EstadoSolicitud.PENDIENTE
    assert solicitud.eventos == eventos_antes