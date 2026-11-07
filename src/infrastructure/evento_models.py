from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database import Base


class EventoRow(Base):
    __tablename__ = "eventos"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)

    contrato_referencia: Mapped[str | None] = mapped_column(String(200))
    contrato_propuesta_id: Mapped[str | None] = mapped_column(
        ForeignKey("propuestas.id")
    )
    contrato_version: Mapped[int | None] = mapped_column(Integer)
    contrato_total_centavos: Mapped[int | None] = mapped_column(BigInteger)

    revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    pagos: Mapped[list["PagoRow"]] = relationship(
        back_populates="evento",
        cascade="all, delete-orphan",
        order_by="PagoRow.id",
        lazy="selectin",
    )

    # Detecta actualizaciones concurrentes del mismo evento.
    __mapper_args__ = {"version_id_col": revision}


class PagoRow(Base):
    __tablename__ = "pagos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evento_id: Mapped[str] = mapped_column(
        ForeignKey("eventos.id"),
        nullable=False,
    )
    monto_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    responsable: Mapped[str] = mapped_column(String(200), nullable=False)

    evento: Mapped["EventoRow"] = relationship(back_populates="pagos")