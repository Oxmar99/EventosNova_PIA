class ErrorDeDominio(Exception):
    """Error causado por incumplir una regla del negocio."""


class ImporteInvalido(ErrorDeDominio):
    """El importe no cumple las condiciones permitidas."""

class PropuestaInvalida(ErrorDeDominio):
    """La propuesta o sus servicios contienen datos inválidos."""

class TransicionInvalida(ErrorDeDominio):
    """La acción no está permitida en el estado actual."""

class ContratoInvalido(ErrorDeDominio):
    """El contrato no cumple las condiciones del negocio."""


class PagoInvalido(ErrorDeDominio):
    """El pago no cumple las condiciones del negocio."""


class OperacionNoAutorizada(ErrorDeDominio):
    """El responsable no tiene permiso para realizar la operación."""