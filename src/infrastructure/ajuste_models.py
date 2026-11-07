from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database import Base


class AjusteCambioRow(Base):
    __tablename__ = "ajustes_cambio"

    cambio_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    evento_id: Mapped[str] = mapped_column(
        ForeignKey("eventos.id"),
        nullable=False,
    )
    incremento_centavos: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    cargo_centavos: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)