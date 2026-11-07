from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
import src.api.cambio_routes as rutas


HOY = date(2026, 11, 6)
CABECERAS = {"X-Admin-Key": "clave-ficticia-cambios"}


@pytest.fixture
def escenario(tmp_path, monkeypatch):
    archivo = (tmp_path / "api_cambios.db").as_posix()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{archivo}")
    monkeypatch.setenv("ADMIN_API_KEY", CABECERAS["X-Admin-Key"])
    monkeypatch.setenv("ADMIN_USER", "admin-pruebas")
    monkeypatch.setattr(rutas, "hoy_negocio", lambda: HOY)

    with TestClient(app) as cliente:
        respuesta = cliente.post(
            "/eventos",
            json={"evento_id": "EVE-O001"},
            headers=CABECERAS,
        )
        assert respuesta.status_code == 201, respuesta.text

        respuesta = cliente.post(
            "/propuestas",
            json={
                "evento_id": "EVE-O001",
                "lineas": [{
                    "recurso_id": "EVE-P001",
                    "descripcion": "Paquete inicial",
                    "precio_unitario": "1000",
                    "cantidad": 1,
                }],
            },
        )
        assert respuesta.status_code == 201, respuesta.text
        propuesta_id = respuesta.json()["id"]

        for accion in ("enviar", "aceptar"):
            respuesta = cliente.post(
                f"/propuestas/{propuesta_id}/{accion}"
            )
            assert respuesta.status_code == 200, respuesta.text

        respuesta = cliente.post(
            "/eventos/EVE-O001/contrato",
            json={
                "propuesta_id": propuesta_id,
                "referencia": "CON-001",
            },
            headers=CABECERAS,
        )
        assert respuesta.status_code == 200, respuesta.text

        respuesta = cliente.post(
            "/eventos/EVE-O001/anticipos",
            json={"monto": "300"},
            headers=CABECERAS,
        )
        assert respuesta.status_code == 200, respuesta.text

        yield cliente, propuesta_id


def solicitar(cliente, propuesta_id, dias=14, precio="1200"):
    return cliente.post(
        "/cambios",
        json={
            "evento_id": "EVE-O001",
            "propuesta_id": propuesta_id,
            "fecha_evento": (HOY + timedelta(days=dias)).isoformat(),
            "motivo": "Ampliación de servicios",
            "nuevas_lineas": [{
                "recurso_id": "EVE-P001",
                "descripcion": "Paquete ampliado",
                "precio_unitario": precio,
                "cantidad": 1,
            }],
        },
        headers=CABECERAS,
    )


def consultar_evento(cliente):
    respuesta = cliente.get(
        "/eventos/EVE-O001",
        headers=CABECERAS,
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


@pytest.mark.parametrize("dias", [15, 16])
def test_cambio_a_tiempo_se_aplica_sin_cargo(escenario, dias):
    cliente, propuesta_id = escenario

    respuesta = solicitar(cliente, propuesta_id, dias=dias)

    assert respuesta.status_code == 201, respuesta.text
    cambio = respuesta.json()
    assert cambio["estado"] == "APLICADO"
    assert cambio["cargo"] == "0.00"
    assert cambio["autorizado_por"] is None

    propuesta = cliente.get(
        f"/propuestas/{propuesta_id}"
    ).json()
    assert propuesta["version"] == "V1.1"
    assert propuesta["total"] == "1200.00"

    evento = consultar_evento(cliente)
    assert evento["contrato"]["total"] == "1000.00"
    assert evento["total_actual"] == "1200.00"
    assert evento["saldo"] == "900.00"


def test_cambio_tardio_espera_autorizacion_y_se_aplica(escenario):
    cliente, propuesta_id = escenario

    respuesta = solicitar(cliente, propuesta_id)
    assert respuesta.status_code == 201, respuesta.text

    cambio = respuesta.json()
    cambio_id = cambio["id"]

    assert cambio["estado"] == "PENDIENTE_AUTORIZACION"
    assert cambio["incremento"] == "200.00"
    assert cambio["cargo"] == "30.00"

    # Solicitar no debe actualizar todavía la propuesta ni el total.
    assert consultar_evento(cliente)["total_actual"] == "1000.00"

    propuesta = cliente.get(
        f"/propuestas/{propuesta_id}"
    ).json()
    assert propuesta["version"] == "V1.0"

    respuesta = cliente.post(
        f"/cambios/{cambio_id}/autorizar",
        headers=CABECERAS,
    )
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado"] == "APLICADO"
    assert respuesta.json()["autorizado_por"] == "admin-pruebas"

    # Consultas nuevas comprueban lo que quedó persistido.
    consulta = cliente.get(
        f"/cambios/{cambio_id}",
        headers=CABECERAS,
    )
    assert consulta.status_code == 200
    assert consulta.json()["estado"] == "APLICADO"

    propuesta = cliente.get(
        f"/propuestas/{propuesta_id}"
    ).json()
    assert propuesta["version"] == "V1.1"

    evento = consultar_evento(cliente)
    assert evento["total_actual"] == "1230.00"
    assert evento["saldo"] == "930.00"

    # No se puede autorizar ni cobrar de nuevo el mismo cambio.
    respuesta = cliente.post(
        f"/cambios/{cambio_id}/autorizar",
        headers=CABECERAS,
    )
    assert respuesta.status_code == 409
    assert consultar_evento(cliente)["total_actual"] == "1230.00"


def test_version_desactualizada_revierte_autorizacion(escenario):
    cliente, propuesta_id = escenario

    respuesta = solicitar(cliente, propuesta_id, precio="1200")
    assert respuesta.status_code == 201
    primero_id = respuesta.json()["id"]

    respuesta = solicitar(cliente, propuesta_id, precio="1300")
    assert respuesta.status_code == 201
    segundo_id = respuesta.json()["id"]

    respuesta = cliente.post(
        f"/cambios/{primero_id}/autorizar",
        headers=CABECERAS,
    )
    assert respuesta.status_code == 200

    respuesta = cliente.post(
        f"/cambios/{segundo_id}/autorizar",
        headers=CABECERAS,
    )
    assert respuesta.status_code == 409

    # El fallo debe deshacer también la autorización del segundo.
    consulta = cliente.get(
        f"/cambios/{segundo_id}",
        headers=CABECERAS,
    )
    segundo = consulta.json()

    assert segundo["estado"] == "PENDIENTE_AUTORIZACION"
    assert segundo["autorizado_por"] is None
    assert segundo["fecha_autorizacion"] is None

    assert consultar_evento(cliente)["total_actual"] == "1230.00"

    propuesta = cliente.get(
        f"/propuestas/{propuesta_id}"
    ).json()
    assert propuesta["version"] == "V1.1"


def test_no_autoriza_sin_clave(escenario):
    cliente, propuesta_id = escenario
    respuesta = solicitar(cliente, propuesta_id)
    assert respuesta.status_code == 201
    cambio_id = respuesta.json()["id"]

    respuesta = cliente.post(f"/cambios/{cambio_id}/autorizar")

    assert respuesta.status_code == 401

    consulta = cliente.get(
        f"/cambios/{cambio_id}",
        headers=CABECERAS,
    )
    assert consulta.json()["estado"] == "PENDIENTE_AUTORIZACION"
    assert consultar_evento(cliente)["total_actual"] == "1000.00"


def test_cambio_inexistente_devuelve_404(escenario):
    cliente, _ = escenario

    respuesta = cliente.get(
        "/cambios/no-existe",
        headers=CABECERAS,
    )

    assert respuesta.status_code == 404