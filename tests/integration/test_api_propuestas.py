import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def datos():
    return {
        "evento_id": "EVE-O001",
        "lineas": [
            {
                "recurso_id": "EVE-P001",
                "descripcion": "Alimentos",
                "precio_unitario": "150.25",
                "cantidad": 2,
            },
            {
                "recurso_id": "EVE-P002",
                "descripcion": "Mobiliario",
                "precio_unitario": "200.00",
                "cantidad": 3,
            },
        ],
    }


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    archivo = (tmp_path / "api_pruebas.db").as_posix()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{archivo}")

    with TestClient(app) as client:
        yield client


def test_crea_y_consulta_propuesta(cliente, datos):
    respuesta = cliente.post("/propuestas", json=datos)

    assert respuesta.status_code == 201
    creada = respuesta.json()
    assert creada["estado"] == "BORRADOR"
    assert creada["version"] == "V1.0"
    assert creada["total"] == "900.50"

    consulta = cliente.get(f"/propuestas/{creada['id']}")

    assert consulta.status_code == 200
    assert consulta.json() == creada


def test_flujo_de_estados_y_rechazos(cliente, datos):
    respuesta = cliente.post("/propuestas", json=datos)
    assert respuesta.status_code == 201
    propuesta_id = respuesta.json()["id"]
    ruta = f"/propuestas/{propuesta_id}"

    # No se permite aceptar directamente desde borrador.
    respuesta = cliente.post(f"{ruta}/aceptar")
    assert respuesta.status_code == 409

    consulta = cliente.get(ruta)
    assert consulta.json()["estado"] == "BORRADOR"

    # Primero se envía y después se acepta.
    respuesta = cliente.post(f"{ruta}/enviar")
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "ENVIADA"

    respuesta = cliente.post(f"{ruta}/aceptar")
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "ACEPTADA"

    # La segunda aceptación se rechaza.
    respuesta = cliente.post(f"{ruta}/aceptar")
    assert respuesta.status_code == 409

    consulta = cliente.get(ruta)
    assert consulta.json()["estado"] == "ACEPTADA"
    assert consulta.json()["total"] == "900.50"


def test_propuesta_inexistente_devuelve_404(cliente):
    respuesta = cliente.get("/propuestas/no-existe")

    assert respuesta.status_code == 404
    assert respuesta.json()["detail"] == "La propuesta no existe."


def test_rechaza_propuesta_sin_lineas(cliente):
    respuesta = cliente.post(
        "/propuestas",
        json={"evento_id": "EVE-O001", "lineas": []},
    )

    assert respuesta.status_code == 422


def test_rechaza_precio_negativo(cliente, datos):
    datos["lineas"][0]["precio_unitario"] = "-1.00"

    respuesta = cliente.post("/propuestas", json=datos)

    assert respuesta.status_code == 422


def test_conserva_datos_tras_reiniciar_aplicacion(
    tmp_path,
    monkeypatch,
    datos,
):
    archivo = (tmp_path / "persistencia_api.db").as_posix()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{archivo}")

    # Primer arranque.
    with TestClient(app) as cliente:
        respuesta = cliente.post("/propuestas", json=datos)
        assert respuesta.status_code == 201
        propuesta_id = respuesta.json()["id"]

        respuesta = cliente.post(
            f"/propuestas/{propuesta_id}/enviar"
        )
        assert respuesta.status_code == 200

    # Segundo arranque, utilizando el mismo archivo de base de datos.
    with TestClient(app) as cliente:
        respuesta = cliente.get(f"/propuestas/{propuesta_id}")

        assert respuesta.status_code == 200
        assert respuesta.json()["estado"] == "ENVIADA"
        assert respuesta.json()["total"] == "900.50"