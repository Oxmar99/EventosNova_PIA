from datetime import date

from sqlalchemy import ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.cambios import (
    EstadoCambio,
    EvaluacionDeCambio,
    SolicitudDeCambio,
)
from src.domain.propuestas import LineaDeServicio, VersionDePropuesta
from src.domain.value_objects import Dinero
from src.infrastructure.database import Base

# Registran las tablas referenciadas.
from src.infrastructure.evento_models import EventoRow
from src.infrastructure.models import PropuestaRow


class SolicitudCambioRow(Base):
    __tablename__ = "solicitudes_cambio"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    evento_id: Mapped[str] = mapped_column(
        ForeignKey("eventos.id"),
        nullable=False,
    )
    propuesta_id: Mapped[str] = mapped_column(
        ForeignKey("propuestas.id"),
        nullable=False,
    )
    estado: Mapped[str] = mapped_column(String(30), nullable=False)
    datos: Mapped[dict] = mapped_column(JSON, nullable=False)
    revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    __mapper_args__ = {"version_id_col": revision}


def version_a_datos(version):
    return {
        "numero": version.numero,
        "lineas": [
            {
                "recurso_id": linea.recurso_id,
                "descripcion": linea.descripcion,
                "precio": str(linea.precio_unitario.monto),
                "cantidad": linea.cantidad,
            }
            for linea in version.lineas
        ],
    }


def version_desde_datos(datos):
    return VersionDePropuesta(
        numero=datos["numero"],
        lineas=tuple(
            LineaDeServicio(
                recurso_id=linea["recurso_id"],
                descripcion=linea["descripcion"],
                precio_unitario=Dinero(linea["precio"]),
                cantidad=linea["cantidad"],
            )
            for linea in datos["lineas"]
        ),
    )


def cambio_a_datos(cambio):
    return {
        "version_anterior": version_a_datos(cambio.version_anterior),
        "version_propuesta": version_a_datos(cambio.version_propuesta),
        "fecha_evento": cambio.fecha_evento.isoformat(),
        "fecha_solicitud": cambio.fecha_solicitud.isoformat(),
        "solicitante": cambio.solicitante,
        "motivo": cambio.motivo,
        "dias_anticipacion": cambio.evaluacion.dias_de_anticipacion,
        "requiere_autorizacion": cambio.evaluacion.requiere_autorizacion,
        "incremento": str(cambio.evaluacion.incremento.monto),
        "cargo": str(cambio.evaluacion.cargo.monto),
        "autorizado_por": cambio.autorizado_por,
        "fecha_autorizacion": (
            cambio.fecha_autorizacion.isoformat()
            if cambio.fecha_autorizacion is not None
            else None
        ),
    }


class SqlAlchemyRepositorioDeCambios:
    def __init__(self, session):
        self.session = session
        self._cargados = {}

    def agregar(self, cambio):
        fila = SolicitudCambioRow(
            id=cambio.id,
            evento_id=cambio.evento_id,
            propuesta_id=cambio.propuesta_id,
            estado=cambio.estado.value,
            datos=cambio_a_datos(cambio),
        )
        self.session.add(fila)
        self._cargados[cambio.id] = (cambio, fila)

    def obtener(self, cambio_id):
        if cambio_id in self._cargados:
            return self._cargados[cambio_id][0]

        fila = self.session.get(SolicitudCambioRow, cambio_id)

        if fila is None:
            return None

        datos = fila.datos

        # Recupera el registro sin crear otra solicitud ni recalcular cargos.
        cambio = SolicitudDeCambio.__new__(SolicitudDeCambio)
        cambio._id = fila.id
        cambio._evento_id = fila.evento_id
        cambio._propuesta_id = fila.propuesta_id
        cambio._estado = EstadoCambio(fila.estado)

        cambio._version_anterior = version_desde_datos(
            datos["version_anterior"]
        )
        cambio._version_propuesta = version_desde_datos(
            datos["version_propuesta"]
        )
        cambio._fecha_evento = date.fromisoformat(datos["fecha_evento"])
        cambio._fecha_solicitud = date.fromisoformat(
            datos["fecha_solicitud"]
        )
        cambio._solicitante = datos["solicitante"]
        cambio._motivo = datos["motivo"]

        cambio._evaluacion = EvaluacionDeCambio(
            dias_de_anticipacion=datos["dias_anticipacion"],
            requiere_autorizacion=datos["requiere_autorizacion"],
            incremento=Dinero(datos["incremento"]),
            cargo=Dinero(datos["cargo"]),
        )

        cambio._autorizado_por = datos["autorizado_por"]
        cambio._fecha_autorizacion = (
            date.fromisoformat(datos["fecha_autorizacion"])
            if datos["fecha_autorizacion"] is not None
            else None
        )
        cambio._eventos = []

        self._cargados[cambio.id] = (cambio, fila)
        return cambio

    def guardar(self, cambio):
        registro = self._cargados.get(cambio.id)

        if registro is None or registro[0] is not cambio:
            raise ValueError(
                "Primero recupera el cambio con este repositorio."
            )

        fila = registro[1]
        fila.estado = cambio.estado.value

        # Reemplazamos el diccionario para que SQLAlchemy detecte el cambio.
        fila.datos = cambio_a_datos(cambio)