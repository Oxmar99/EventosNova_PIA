from typing import Protocol

from src.domain.propuestas import Propuesta


class RepositorioDePropuestas(Protocol):
    def agregar(self, propuesta: Propuesta) -> None:
        ...

    def obtener(self, propuesta_id: str) -> Propuesta | None:
        ...

    def guardar_estado(self, propuesta: Propuesta) -> None:
        ...