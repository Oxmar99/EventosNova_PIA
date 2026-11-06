from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from src.domain.exceptions import ErrorDeDominio
from src.domain.value_objects import Dinero


class CambioInvalido(ErrorDeDominio):
    """Los datos del cambio no permiten evaluar la política."""


@dataclass(frozen=True)
class EvaluacionDeCambio:
    dias_de_anticipacion: int
    requiere_autorizacion: bool
    incremento: Dinero
    cargo: Dinero

    @property
    def importe_adicional(self) -> Dinero:
        return Dinero(self.incremento.monto + self.cargo.monto)


class PoliticaDeCambios:
    DIAS_LIMITE = 15
    PORCENTAJE_URGENCIA = Decimal("0.15")

    def evaluar(
        self,
        fecha_evento: date,
        fecha_solicitud: date,
        incremento: Dinero,
    ) -> EvaluacionDeCambio:
        # Se usan fechas de calendario, no horas transcurridas.
        if (
            type(fecha_evento) is not date
            or type(fecha_solicitud) is not date
        ):
            raise CambioInvalido(
                "Se requieren fechas de calendario para evaluar el cambio."
            )

        if not isinstance(incremento, Dinero):
            raise CambioInvalido(
                "El incremento debe representarse con Dinero."
            )

        dias = (fecha_evento - fecha_solicitud).days

        if dias < 0:
            raise CambioInvalido(
                "Esta política no admite cambios posteriores al evento."
            )

        es_tardio = dias < self.DIAS_LIMITE

        cargo = (
            Dinero(incremento.monto * self.PORCENTAJE_URGENCIA)
            if es_tardio
            else Dinero("0")
        )

        return EvaluacionDeCambio(
            dias_de_anticipacion=dias,
            requiere_autorizacion=es_tardio,
            incremento=incremento,
            cargo=cargo,
        )