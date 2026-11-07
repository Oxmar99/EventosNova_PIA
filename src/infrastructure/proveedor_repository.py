from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.proveedores import EstadoSolicitud, SolicitudDeProveedor
from src.infrastructure.database import Base


class SolicitudProveedorRow(Base):
    __tablename__ = "solicitudes_proveedor"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    evento_id: Mapped[str] = mapped_column(
        ForeignKey("eventos.id"),
        nullable=False,
    )
    proveedor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    servicio: Mapped[str] = mapped_column(String(500), nullable=False)
    enviada_en: Mapped[str] = mapped_column(String(50), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)
    revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    __mapper_args__ = {"version_id_col": revision}


class SqlAlchemyRepositorioDeSolicitudes:
    def __init__(self, session):
        self.session = session
        self._cargadas = {}

    def agregar(self, solicitud):
        fila = SolicitudProveedorRow(
            id=solicitud.id,
            evento_id=solicitud.evento_id,
            proveedor_id=solicitud.proveedor_id,
            servicio=solicitud.servicio,
            enviada_en=solicitud.enviada_en.isoformat(),
            estado=solicitud.estado.value,
        )

        self.session.add(fila)
        self._cargadas[solicitud.id] = (solicitud, fila)

    def obtener(self, solicitud_id):
        if solicitud_id in self._cargadas:
            return self._cargadas[solicitud_id][0]

        fila = self.session.get(SolicitudProveedorRow, solicitud_id)

        if fila is None:
            return None

        solicitud = SolicitudDeProveedor(
            evento_id=fila.evento_id,
            proveedor_id=fila.proveedor_id,
            servicio=fila.servicio,
            enviada_en=datetime.fromisoformat(fila.enviada_en),
        )
        solicitud._id = fila.id
        solicitud._estado = EstadoSolicitud(fila.estado)

        # La lectura no debe anunciar nuevamente el envío.
        solicitud._eventos = []

        self._cargadas[solicitud.id] = (solicitud, fila)
        return solicitud

    def guardar(self, solicitud):
        registro = self._cargadas.get(solicitud.id)

        if registro is None or registro[0] is not solicitud:
            raise ValueError(
                "Primero recupera la solicitud con este repositorio."
            )

        fila = registro[1]
        fila.estado = solicitud.estado.value