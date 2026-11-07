from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
import src.api.proveedor_routes as rutas


CABECERAS = {"X-Admin-Key": "clave-ficticia-proveedores"}


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    archivo = (tmp_path / "proveedores.db").as_posix()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{archivo}")
    monkeypatch.setenv("ADMIN_API_KEY", CABECERAS["X-Admin-Key"])

    reloj = {
        "ahora": datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
    }
    monkeypatch.setattr(rutas, "ahora_utc", lambda: reloj["ahora"])

    with TestClient(app) as cliente:
        yield cliente, reloj


def preparar_evento(cliente, confirmar=True):
    respuesta = cliente.post(
        "/eventos",
        json={"evento_id": "EVE-O001"},
        headers=CABECERAS,
    )
    assert respuesta.status_code == 201, respuesta.text

    if not confirmar:
        return

    respuesta = cliente.post(
        "/propuestas",
        json={
            "evento_id": "EVE-O001",
            "lineas": [{
                "recurso_id": "EVE-P001",
                "descripcion": "Paquete",
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


def solicitar(cliente):
    return cliente.post(
        "/solicitudes-proveedor",
        json={
            "evento_id": "EVE-O001",
            "proveedor_id": "PROV-001",
            "servicio": "Alimentos",
        },
        headers=CABECERAS,
    )


def actuar(cliente, solicitud_id, accion):
    return cliente.post(
        f"/solicitudes-proveedor/{solicitud_id}/acciones",
        json={"accion": accion},
        headers=CABECERAS,
    )


def test_bloquea_evento_sin_confirmar(entorno):
    cliente, _ = entorno
    preparar_evento(cliente, confirmar=False)

    respuesta = solicitar(cliente)

    assert respuesta.status_code == 409


def test_crea_confirma_y_consulta_solicitud(entorno):
    cliente, _ = entorno
    preparar_evento(cliente)

    respuesta = solicitar(cliente)
    assert respuesta.status_code == 201, respuesta.text
    solicitud_id = respuesta.json()["id"]
    assert respuesta.json()["estado"] == "PENDIENTE"

    respuesta = actuar(cliente, solicitud_id, "confirmar")
    assert respuesta.status_code == 200, respuesta.text

    consulta = cliente.get(
        f"/solicitudes-proveedor/{solicitud_id}",
        headers=CABECERAS,
    )
    assert consulta.status_code == 200
    assert consulta.json()["estado"] == "CONFIRMADA"

    assert actuar(cliente, solicitud_id, "confirmar").status_code == 409


def test_rechaza_solicitud(entorno):
    cliente, _ = entorno
    preparar_evento(cliente)
    solicitud_id = solicitar(cliente).json()["id"]

    respuesta = actuar(cliente, solicitud_id, "rechazar")

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "RECHAZADA"


def test_expira_a_las_48_horas(entorno):
    cliente, reloj = entorno
    preparar_evento(cliente)
    solicitud_id = solicitar(cliente).json()["id"]

    reloj["ahora"] += timedelta(hours=48)

    assert actuar(cliente, solicitud_id, "confirmar").status_code == 409

    respuesta = actuar(cliente, solicitud_id, "expirar")
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "EXPIRADA"

    consulta = cliente.get(
        f"/solicitudes-proveedor/{solicitud_id}",
        headers=CABECERAS,
    )
    assert consulta.json()["estado"] == "EXPIRADA"


def test_no_expira_antes_del_limite(entorno):
    cliente, _ = entorno
    preparar_evento(cliente)
    solicitud_id = solicitar(cliente).json()["id"]

    respuesta = actuar(cliente, solicitud_id, "expirar")

    assert respuesta.status_code == 409

    consulta = cliente.get(
        f"/solicitudes-proveedor/{solicitud_id}",
        headers=CABECERAS,
    )
    assert consulta.json()["estado"] == "PENDIENTE"


def test_solicitud_inexistente(entorno):
    cliente, _ = entorno

    respuesta = cliente.get(
        "/solicitudes-proveedor/no-existe",
        headers=CABECERAS,
    )

    assert respuesta.status_code == 404