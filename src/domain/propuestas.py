from dataclasses import dataclass
from decimal import Decimal

from src.domain.exceptions import PropuestaInvalida
from src.domain.value_objects import Dinero

from enum import Enum
from uuid import uuid4

from src.domain.events import EventoDeDominio
from src.domain.exceptions import TransicionInvalida


@dataclass(frozen=True)
class LineaDeServicio:
    recurso_id: str
    descripcion: str
    precio_unitario: Dinero
    cantidad: int

    def __post_init__(self):
        if not isinstance(self.recurso_id, str) or not self.recurso_id.strip():
            raise PropuestaInvalida("El recurso debe tener un identificador.")

        if not isinstance(self.descripcion, str) or not self.descripcion.strip():
            raise PropuestaInvalida("El servicio debe tener una descripción.")

        if not isinstance(self.precio_unitario, Dinero):
            raise PropuestaInvalida("El precio debe representarse con Dinero.")

        if type(self.cantidad) is not int or self.cantidad <= 0:
            raise PropuestaInvalida(
                "La cantidad debe ser un entero mayor que cero."
            )

    @property
    def subtotal(self) -> Dinero:
        return Dinero(self.precio_unitario.monto * self.cantidad)


@dataclass(frozen=True)
class VersionDePropuesta:
    numero: int
    lineas: tuple[LineaDeServicio, ...]

    def __post_init__(self):
        if type(self.numero) is not int or self.numero <= 0:
            raise PropuestaInvalida(
                "El número de versión debe ser un entero positivo."
            )

        # Exigimos una tupla para que la colección sea inmutable.
        if not isinstance(self.lineas, tuple) or not self.lineas:
            raise PropuestaInvalida(
                "La versión debe contener una tupla con al menos un servicio."
            )

        if not all(isinstance(linea, LineaDeServicio) for linea in self.lineas):
            raise PropuestaInvalida("Todas las líneas deben ser servicios válidos.")

    @property
    def total(self) -> Dinero:
        importe = sum(
            (linea.subtotal.monto for linea in self.lineas),
            start=Decimal("0.00"),
        )
        return Dinero(importe)

    @property
    def etiqueta(self) -> str:
        return f"V1.{self.numero - 1}"

class EstadoPropuesta(str, Enum):
    BORRADOR = "BORRADOR"
    ENVIADA = "ENVIADA"
    ACEPTADA = "ACEPTADA"


class Propuesta:
    def __init__(
        self,
        evento_id: str,
        lineas: tuple[LineaDeServicio, ...],
    ):
        if not isinstance(evento_id, str) or not evento_id.strip():
            raise PropuestaInvalida(
                "La propuesta debe estar asociada a un evento."
            )

        version_inicial = VersionDePropuesta(numero=1, lineas=lineas)

        self._id = str(uuid4())
        self._evento_id = evento_id
        self._estado = EstadoPropuesta.BORRADOR
        self._versiones = [version_inicial]
        self._eventos = []

        self._registrar_evento("PropuestaGenerada")

    @property
    def id(self) -> str:
        return self._id

    @property
    def evento_id(self) -> str:
        return self._evento_id

    @property
    def estado(self) -> EstadoPropuesta:
        return self._estado

    @property
    def versiones(self) -> tuple[VersionDePropuesta, ...]:
        return tuple(self._versiones)

    @property
    def version_vigente(self) -> VersionDePropuesta:
        return self._versiones[-1]

    @property
    def eventos(self) -> tuple[EventoDeDominio, ...]:
        return tuple(self._eventos)

    def enviar(self) -> None:
        if self._estado != EstadoPropuesta.BORRADOR:
            raise TransicionInvalida(
                "Solo se puede enviar una propuesta en borrador."
            )

        self._estado = EstadoPropuesta.ENVIADA
        self._registrar_evento("PropuestaEnviada")

    def aceptar(self) -> None:
        if self._estado != EstadoPropuesta.ENVIADA:
            raise TransicionInvalida(
                "Solo se puede aceptar una propuesta enviada."
            )

        self._estado = EstadoPropuesta.ACEPTADA
        self._registrar_evento("PropuestaAceptada")

    def _registrar_evento(self, tipo: str) -> None:
        self._eventos.append(
            EventoDeDominio(
                tipo=tipo,
                agregado_id=self._id,
                version=self.version_vigente.numero,
            )
        )