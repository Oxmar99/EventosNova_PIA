from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from src.domain.exceptions import ImporteInvalido


@dataclass(frozen=True)
class Dinero:
    monto: Decimal
    moneda: str = "MXN"

    def __post_init__(self):
        if self.moneda != "MXN":
            raise ImporteInvalido("Solo se permiten importes en MXN.")

        # Evitamos recibir números float con imprecisión binaria.
        if isinstance(self.monto, (float, bool)):
            raise ImporteInvalido(
                "Usa texto o Decimal para representar dinero."
            )

        try:
            valor = Decimal(self.monto)

            if not valor.is_finite() or valor < 0:
                raise ImporteInvalido(
                    "El importe debe ser finito y no negativo."
                )

            valor = valor.quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
        except (InvalidOperation, TypeError, ValueError) as error:
            raise ImporteInvalido("El importe no es válido.") from error

        object.__setattr__(self, "monto", valor)