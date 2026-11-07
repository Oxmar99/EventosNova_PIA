from datetime import date

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database import Base


class FechaEventoRow(Base):
    __tablename__ = "fechas_evento"

    evento_id: Mapped[str] = mapped_column(
        ForeignKey("eventos.id"),
        primary_key=True,
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    registrado_por: Mapped[str] = mapped_column(String(200), nullable=False)


class SqlAlchemyRepositorioDeFechas:
    def __init__(self, session):
        self.session = session

    def obtener(self, evento_id):
        fila = self.session.get(FechaEventoRow, evento_id)
        return fila.fecha if fila is not None else None

    def agregar(self, evento_id, fecha, responsable):
        self.session.add(
            FechaEventoRow(
                evento_id=evento_id,
                fecha=fecha,
                registrado_por=responsable,
            )
        )