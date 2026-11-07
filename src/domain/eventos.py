from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from src.domain.events import EventoDeDominio
from src.domain.exceptions import (
    ContratoInvalido,
    OperacionNoAutorizada,
    PagoInvalido,
    TransicionInvalida,
)
from src.domain.propuestas import EstadoPropuesta, Propuesta
from src.domain.specifications import (
    PUEDE_CONFIRMARSE,
    PUEDE_RECIBIR_ANTICIPO,
    REQUIERE_ANTICIPO,
)
from src.domain.value_objects import Dinero


class EstadoEvento(str, Enum):
    SOLICITADO = "SOLICITADO"
    CONFIRMADO = "CONFIRMADO"


@dataclass(frozen=True)
class Contrato:
    referencia: str
    propuesta_id: str
    version: int
    total: Dinero


@dataclass(frozen=True)
class Pago:
    monto: Dinero
    responsable: str

@dataclass(frozen=True)
class AjusteDeCambio:
    cambio_id: str
    incremento: Dinero
    cargo: Dinero
    version: int

class Evento:
    def __init__(self, evento_id: str):
        if not isinstance(evento_id, str) or not evento_id.strip():
            raise ContratoInvalido("El evento requiere un identificador.")

        self._id = evento_id
        self._estado = EstadoEvento.SOLICITADO
        self._contrato = None
        self._pagos = []
        self._ajustes = []
        self._eventos = []

    @property
    def id(self):
        return self._id

    @property
    def estado(self):
        return self._estado

    @property
    def contrato(self):
        return self._contrato

    @property
    def pagos(self):
        return tuple(self._pagos)

    @property
    def eventos(self):
        return tuple(self._eventos)

    @property
    def total_pagado(self):
        total = sum(
            (pago.monto.monto for pago in self._pagos),
            start=Decimal("0.00"),
        )
        return Dinero(total)

    @property
    def requiere_anticipo(self):
        return REQUIERE_ANTICIPO.cumple(self)

    def registrar_contrato_firmado(
        self,
        propuesta: Propuesta,
        referencia: str,
    ):
        if self._contrato is not None:
            raise ContratoInvalido("El evento ya tiene un contrato.")

        if propuesta.evento_id != self._id:
            raise ContratoInvalido(
                "La propuesta pertenece a otro evento."
            )

        if propuesta.estado != EstadoPropuesta.ACEPTADA:
            raise ContratoInvalido(
                "La propuesta debe estar aceptada."
            )

        if not isinstance(referencia, str) or not referencia.strip():
            raise ContratoInvalido(
                "Se requiere la referencia del contrato firmado."
            )

        version = propuesta.version_vigente

        if version.total.monto <= 0:
            raise ContratoInvalido(
                "El total del contrato debe ser mayor que cero."
            )

        self._contrato = Contrato(
            referencia=referencia.strip(),
            propuesta_id=propuesta.id,
            version=version.numero,
            total=version.total,
        )
        self._registrar_evento("ContratoFirmado")

    def registrar_anticipo(
        self,
        monto: Dinero,
        responsable: str,
        rol: str,
    ):
        if rol != "ADMINISTRACION":
            raise OperacionNoAutorizada(
                "Solo Administración puede registrar anticipos."
            )

        if not isinstance(responsable, str) or not responsable.strip():
            raise PagoInvalido("Se requiere identificar al responsable.")

        if self._contrato is None:
            raise ContratoInvalido(
                "Debe existir un contrato firmado antes del anticipo."
            )

        if not PUEDE_RECIBIR_ANTICIPO.cumple(self):
            raise TransicionInvalida(
                "El estado actual no permite registrar anticipos."
            )

        if not isinstance(monto, Dinero) or monto.monto <= 0:
            raise PagoInvalido("El pago debe ser mayor que cero.")

        self._pagos.append(
            Pago(monto=monto, responsable=responsable.strip())
        )
        self._registrar_evento("AnticipoRegistrado")

        if PUEDE_CONFIRMARSE.cumple(self):
            self._estado = EstadoEvento.CONFIRMADO
            self._registrar_evento("EventoConfirmado")

    def _registrar_evento(self, tipo):
        self._eventos.append(
            EventoDeDominio(
                tipo=tipo,
                agregado_id=self._id,
                version=self._contrato.version,
            )
        )

    @property
    def ajustes(self):
        return tuple(self._ajustes)

    @property
    def total_actual(self):
        if self._contrato is None:
            return Dinero("0")

        adicionales = sum(
            (
                ajuste.incremento.monto + ajuste.cargo.monto
                for ajuste in self._ajustes
            ),
            start=Decimal("0.00"),
        )

        return Dinero(self._contrato.total.monto + adicionales)

    @property
    def saldo(self):
        # Decimal permite representar también un saldo a favor.
        return self.total_actual.monto - self.total_pagado.monto

    def validar_ajuste(self, cambio):
        if self._estado != EstadoEvento.CONFIRMADO:
            raise TransicionInvalida(
                "Solo se aplican cambios a eventos confirmados."
            )

        if self._contrato is None:
            raise ContratoInvalido("El evento no tiene contrato.")

        if (
            cambio.evento_id != self._id
            or cambio.propuesta_id != self._contrato.propuesta_id
        ):
            raise ContratoInvalido(
                "El cambio no corresponde al contrato de este evento."
            )

        if cambio.estado.value != "LISTO_PARA_APLICAR":
            raise TransicionInvalida(
                "El cambio todavía no está autorizado para aplicarse."
            )

        if any(
            ajuste.cambio_id == cambio.id
            for ajuste in self._ajustes
        ):
            raise TransicionInvalida("El cambio ya fue aplicado.")

    def registrar_ajuste(self, cambio):
        self.validar_ajuste(cambio)

        self._ajustes.append(
            AjusteDeCambio(
                cambio_id=cambio.id,
                incremento=cambio.evaluacion.incremento,
                cargo=cambio.evaluacion.cargo,
                version=cambio.version_propuesta.numero,
            )
        )

        self._eventos.append(
            EventoDeDominio(
                tipo="CambioAplicado",
                agregado_id=self._id,
                version=cambio.version_propuesta.numero,
            )
        )