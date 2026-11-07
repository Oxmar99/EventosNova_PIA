import pytest
from fastapi.testclient import TestClient

from src.api.main import app


CLAVE_PRUEBA = "clave-ficticia-solo-para-tests"
CABECERAS = {"X-Admin-Key": CLAVE_PRUEBA}


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    archivo = (tmp_path / "api_eventos.db").as_posix()

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{archivo}")
    monkeypatch.setenv("ADMIN_API_KEY", CLAVE_PRUEBA)
    monkeypatch.setenv("ADMIN_USER", "admin-pruebas")

    with TestClient(app) as client:
        yield client


def crear_evento(cliente, evento_id="EVE-O001"):
    respuesta = cliente.post(
        "/eventos",
        json={"evento_id": evento_id},
        headers=CABECERAS,
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["id"]


def crear_propuesta(cliente, evento_id="EVE-O001", aceptar=True):
    respuesta = cliente.post(
        "/propuestas",
        json={
            "evento_id": evento_id,
            "lineas": [
                {
                    "recurso_id": "EVE-P001",
                    "descripcion": "Paquete de evento",
                    "precio_unitario": "1000.00",
                    "cantidad": 1,
                }
            ],
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    propuesta_id = respuesta.json()["id"]

    if aceptar:
        respuesta = cliente.post(
            f"/propuestas/{propuesta_id}/enviar"
        )
        assert respuesta.status_code == 200, respuesta.text

        respuesta = cliente.post(
            f"/propuestas/{propuesta_id}/aceptar"
        )
        assert respuesta.status_code == 200, respuesta.text

    return propuesta_id


def registrar_contrato(cliente, evento_id, propuesta_id):
    return cliente.post(
        f"/eventos/{evento_id}/contrato",
        json={
            "propuesta_id": propuesta_id,
            "referencia": "CON-PRUEBA",
        },
        headers=CABECERAS,
    )


@pytest.mark.parametrize(
    "cabeceras",
    [{}, {"X-Admin-Key": "clave-incorrecta"}],
)
def test_rechaza_acceso_sin_clave_valida(cliente, cabeceras):
    respuesta = cliente.post(
        "/eventos",
        json={"evento_id": "EVE-O001"},
        headers=cabeceras,
    )

    assert respuesta.status_code == 401

    # La petición rechazada no debe crear el evento.
    consulta = cliente.get(
        "/eventos/EVE-O001",
        headers=CABECERAS,
    )
    assert consulta.status_code == 404


def test_informa_si_falta_configurar_clave(cliente, monkeypatch):
    monkeypatch.delenv("ADMIN_API_KEY")

    respuesta = cliente.get(
        "/eventos/EVE-O001",
        headers=CABECERAS,
    )

    assert respuesta.status_code == 503


def test_recorrido_completo_hasta_confirmacion(cliente):
    evento_id = crear_evento(cliente)
    propuesta_id = crear_propuesta(cliente)

    respuesta = registrar_contrato(
        cliente, evento_id, propuesta_id
    )
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["contrato"]["total"] == "1000.00"
    assert respuesta.json()["estado"] == "SOLICITADO"

    respuesta = cliente.post(
        f"/eventos/{evento_id}/anticipos",
        json={"monto": "299.99"},
        headers=CABECERAS,
    )
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado"] == "SOLICITADO"

    respuesta = cliente.post(
        f"/eventos/{evento_id}/anticipos",
        json={"monto": "0.01"},
        headers=CABECERAS,
    )
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado"] == "CONFIRMADO"

    consulta = cliente.get(
        f"/eventos/{evento_id}",
        headers=CABECERAS,
    )
    assert consulta.status_code == 200
    resultado = consulta.json()

    assert resultado["total_pagado"] == "300.00"
    assert resultado["cantidad_pagos"] == 2
    assert resultado["requiere_anticipo"] is False
    assert resultado["estado"] == "CONFIRMADO"


def test_no_registra_pago_sin_contrato(cliente):
    evento_id = crear_evento(cliente)

    respuesta = cliente.post(
        f"/eventos/{evento_id}/anticipos",
        json={"monto": "300"},
        headers=CABECERAS,
    )
    assert respuesta.status_code == 422

    consulta = cliente.get(
        f"/eventos/{evento_id}",
        headers=CABECERAS,
    )
    resultado = consulta.json()

    assert resultado["total_pagado"] == "0.00"
    assert resultado["cantidad_pagos"] == 0
    assert resultado["estado"] == "SOLICITADO"


def test_no_contrata_propuesta_sin_aceptar(cliente):
    evento_id = crear_evento(cliente)
    propuesta_id = crear_propuesta(cliente, aceptar=False)

    respuesta = registrar_contrato(
        cliente, evento_id, propuesta_id
    )
    assert respuesta.status_code == 422

    consulta = cliente.get(
        f"/eventos/{evento_id}",
        headers=CABECERAS,
    )
    assert consulta.json()["contrato"] is None


def test_no_contrata_propuesta_de_otro_evento(cliente):
    evento_id = crear_evento(cliente)
    crear_evento(cliente, "EVE-O002")
    propuesta_id = crear_propuesta(cliente, "EVE-O002")

    respuesta = registrar_contrato(
        cliente, evento_id, propuesta_id
    )
    assert respuesta.status_code == 422

    consulta = cliente.get(
        f"/eventos/{evento_id}",
        headers=CABECERAS,
    )
    assert consulta.json()["contrato"] is None


def test_evento_inexistente_devuelve_404(cliente):
    respuesta = cliente.get(
        "/eventos/no-existe",
        headers=CABECERAS,
    )

    assert respuesta.status_code == 404
    assert respuesta.json()["detail"] == "El evento no existe."


def test_no_crea_evento_duplicado(cliente):
    crear_evento(cliente)

    respuesta = cliente.post(
        "/eventos",
        json={"evento_id": "EVE-O001"},
        headers=CABECERAS,
    )

    assert respuesta.status_code == 409