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

from enum import Enum
from uuid import uuid4

from src.domain.events import EventoDeDominio
from src.domain.exceptions import (
    OperacionNoAutorizada,
    TransicionInvalida,
)
from src.domain.propuestas import (
    EstadoPropuesta,
    Propuesta,
    VersionDePropuesta,
)


class EstadoCambio(str, Enum):
    PENDIENTE_AUTORIZACION = "PENDIENTE_AUTORIZACION"
    LISTO_PARA_APLICAR = "LISTO_PARA_APLICAR"
    APLICADO = "APLICADO"


class SolicitudDeCambio:
    def __init__(
        self,
        propuesta: Propuesta,
        nuevas_lineas: tuple,
        fecha_evento: date,
        fecha_solicitud: date,
        solicitante: str,
        motivo: str,
    ):
        if propuesta.estado != EstadoPropuesta.ACEPTADA:
            raise TransicionInvalida(
                "Solo se solicitan cambios sobre una propuesta aceptada."
            )

        for valor in (solicitante, motivo):
            if not isinstance(valor, str) or not valor.strip():
                raise CambioInvalido(
                    "El solicitante y el motivo son obligatorios."
                )

        anterior = propuesta.version_vigente
        nueva = VersionDePropuesta(
            numero=anterior.numero + 1,
            lineas=nuevas_lineas,
        )

        diferencia = nueva.total.monto - anterior.total.monto

        if diferencia < 0:
            raise CambioInvalido(
                "Las reducciones de precio requieren una política "
                "todavía no implementada."
            )

        evaluacion = PoliticaDeCambios().evaluar(
            fecha_evento=fecha_evento,
            fecha_solicitud=fecha_solicitud,
            incremento=Dinero(diferencia),
        )

        self._id = str(uuid4())
        self._evento_id = propuesta.evento_id
        self._propuesta_id = propuesta.id
        self._version_anterior = anterior
        self._version_propuesta = nueva
        self._fecha_evento = fecha_evento
        self._fecha_solicitud = fecha_solicitud
        self._solicitante = solicitante.strip()
        self._motivo = motivo.strip()
        self._evaluacion = evaluacion
        self._autorizado_por = None
        self._fecha_autorizacion = None

        self._estado = (
            EstadoCambio.PENDIENTE_AUTORIZACION
            if evaluacion.requiere_autorizacion
            else EstadoCambio.LISTO_PARA_APLICAR
        )

        self._eventos = [
            EventoDeDominio(
                tipo=(
                    "CambioPendienteDeAutorizacion"
                    if evaluacion.requiere_autorizacion
                    else "CambioEvaluado"
                ),
                agregado_id=self._evento_id,
                version=anterior.numero,
            )
        ]

    @property
    def id(self):
        return self._id

    @property
    def evento_id(self):
        return self._evento_id

    @property
    def propuesta_id(self):
        return self._propuesta_id

    @property
    def version_anterior(self):
        return self._version_anterior

    @property
    def version_propuesta(self):
        return self._version_propuesta

    @property
    def fecha_evento(self):
        return self._fecha_evento

    @property
    def fecha_solicitud(self):
        return self._fecha_solicitud

    @property
    def solicitante(self):
        return self._solicitante

    @property
    def motivo(self):
        return self._motivo

    @property
    def evaluacion(self):
        return self._evaluacion

    @property
    def estado(self):
        return self._estado

    @property
    def autorizado_por(self):
        return self._autorizado_por

    @property
    def fecha_autorizacion(self):
        return self._fecha_autorizacion

    @property
    def eventos(self):
        return tuple(self._eventos)

    def autorizar(self, responsable: str, rol: str, fecha: date):
        if rol != "ADMINISTRACION":
            raise OperacionNoAutorizada(
                "Solo Administración puede autorizar cambios tardíos."
            )

        if self._estado != EstadoCambio.PENDIENTE_AUTORIZACION:
            raise TransicionInvalida(
                "El cambio no está pendiente de autorización."
            )

        if not isinstance(responsable, str) or not responsable.strip():
            raise CambioInvalido("El responsable es obligatorio.")

        if type(fecha) is not date or not (
            self._fecha_solicitud <= fecha <= self._fecha_evento
        ):
            raise CambioInvalido(
                "La autorización debe ocurrir entre la solicitud "
                "y la fecha del evento."
            )

        self._autorizado_por = responsable.strip()
        self._fecha_autorizacion = fecha
        self._estado = EstadoCambio.LISTO_PARA_APLICAR

        self._eventos.append(
            EventoDeDominio(
                tipo="CambioAutorizado",
                agregado_id=self._evento_id,
                version=self._version_anterior.numero,
            )
        )

    def marcar_aplicado(self):
        if self._estado != EstadoCambio.LISTO_PARA_APLICAR:
            raise TransicionInvalida(
                "El cambio no está listo para aplicarse."
            )

        self._estado = EstadoCambio.APLICADO

class AplicadorDeCambios:
    """Coordina las validaciones de los objetos del dominio."""

    def aplicar(self, cambio, evento, propuesta):
        if (
            cambio.propuesta_id != propuesta.id
            or cambio.evento_id != evento.id
        ):
            raise CambioInvalido(
                "El cambio no corresponde a estos objetos."
            )

        # Comprobamos todas las condiciones antes de modificar objetos.
        evento.validar_ajuste(cambio)
        propuesta.validar_nueva_version(
            cambio.version_anterior,
            cambio.version_propuesta,
        )

        propuesta.incorporar_version(
            cambio.version_anterior,
            cambio.version_propuesta,
        )
        evento.registrar_ajuste(cambio)
        cambio.marcar_aplicado()