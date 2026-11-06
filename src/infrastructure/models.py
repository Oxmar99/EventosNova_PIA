from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database import Base


class PropuestaRow(Base):
    __tablename__ = "propuestas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    evento_id: Mapped[str] = mapped_column(String(100), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)

    versiones: Mapped[list["VersionRow"]] = relationship(
        back_populates="propuesta",
        cascade="all, delete-orphan",
        order_by="VersionRow.numero",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint(
            "estado IN ('BORRADOR', 'ENVIADA', 'ACEPTADA')",
            name="ck_propuesta_estado",
        ),
    )


class VersionRow(Base):
    __tablename__ = "versiones_propuesta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    propuesta_id: Mapped[str] = mapped_column(
        ForeignKey("propuestas.id"),
        nullable=False,
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False)

    propuesta: Mapped["PropuestaRow"] = relationship(
        back_populates="versiones"
    )
    lineas: Mapped[list["LineaRow"]] = relationship(
        back_populates="version",
        cascade="all, delete-orphan",
        order_by="LineaRow.posicion",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint(
            "propuesta_id",
            "numero",
            name="uq_propuesta_version",
        ),
        CheckConstraint("numero > 0", name="ck_version_positiva"),
    )


class LineaRow(Base):
    __tablename__ = "lineas_propuesta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_id: Mapped[int] = mapped_column(
        ForeignKey("versiones_propuesta.id"),
        nullable=False,
    )
    posicion: Mapped[int] = mapped_column(Integer, nullable=False)
    recurso_id: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str] = mapped_column(String(500), nullable=False)
    precio_centavos: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)

    version: Mapped["VersionRow"] = relationship(
        back_populates="lineas"
    )

    __table_args__ = (
        UniqueConstraint(
            "version_id",
            "posicion",
            name="uq_version_posicion",
        ),
        CheckConstraint("cantidad > 0", name="ck_cantidad_positiva"),
        CheckConstraint(
            "precio_centavos >= 0",
            name="ck_precio_no_negativo",
        ),
    )