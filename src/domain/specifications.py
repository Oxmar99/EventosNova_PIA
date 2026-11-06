from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


class Specification(ABC):
    @abstractmethod
    def cumple(self, candidato) -> bool:
        pass

    def __and__(self, otra):
        return AndSpecification(self, otra)

    def __or__(self, otra):
        return OrSpecification(self, otra)

    def __invert__(self):
        return NotSpecification(self)


@dataclass(frozen=True)
class AndSpecification(Specification):
    izquierda: Specification
    derecha: Specification

    def cumple(self, candidato):
        return (
            self.izquierda.cumple(candidato)
            and self.derecha.cumple(candidato)
        )


@dataclass(frozen=True)
class OrSpecification(Specification):
    izquierda: Specification
    derecha: Specification

    def cumple(self, candidato):
        return (
            self.izquierda.cumple(candidato)
            or self.derecha.cumple(candidato)
        )


@dataclass(frozen=True)
class NotSpecification(Specification):
    regla: Specification

    def cumple(self, candidato):
        return not self.regla.cumple(candidato)


class TieneContratoSpecification(Specification):
    def cumple(self, candidato):
        return candidato.contrato is not None


class AnticipoSuficienteSpecification(Specification):
    def cumple(self, candidato):
        if candidato.contrato is None:
            return False

        minimo = candidato.contrato.total.monto * Decimal("0.30")
        return candidato.total_pagado.monto >= minimo


@dataclass(frozen=True)
class EstadoEsSpecification(Specification):
    estado: str

    def cumple(self, candidato):
        return candidato.estado.value == self.estado


PUEDE_RECIBIR_ANTICIPO = (
    EstadoEsSpecification("SOLICITADO")
    | EstadoEsSpecification("CONFIRMADO")
)

PUEDE_CONFIRMARSE = (
    TieneContratoSpecification()
    & AnticipoSuficienteSpecification()
    & EstadoEsSpecification("SOLICITADO")
)

REQUIERE_ANTICIPO = ~AnticipoSuficienteSpecification()