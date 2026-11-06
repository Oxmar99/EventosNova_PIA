from datetime import datetime, timedelta
from enum import Enum
from uuid import uuid4

from src.domain.events import EventoDeDominio
from src.domain.exceptions import ErrorDeDominio, TransicionInvalida


class SolicitudInvalida(ErrorDeDominio):
    """Los datos o las fechas de la solicitud son inválidos."""


class EstadoSolicitud(str, Enum):
    PENDIENTE = "PENDIENTE"
    CONFIRMADA = "CONFIRMADA"
    RECHAZADA = "RECHAZADA"
    EXPIRADA = "EXPIRADA"


class SolicitudDeProveedor:
    def __init__(
        self,
        evento_id: str,
        proveedor_id: str,
        servicio: str,
        enviada_en: datetime,
    ):
        for valor in (evento_id, proveedor_id, servicio):
            if not isinstance(valor, str) or not valor.strip():
                raise SolicitudInvalida(
                    "Evento, proveedor y servicio son obligatorios."
                )

        self._validar_fecha(enviada_en)

        self._id = str(uuid4())
        self._evento_id = evento_id
        self._proveedor_id = proveedor_id
        self._servicio = servicio.strip()
        self._enviada_en = enviada_en
        self._vence_en = enviada_en + timedelta(hours=48)
        self._estado = EstadoSolicitud.PENDIENTE
        self._eventos = []

        self._registrar_evento(
            "SolicitudAProveedorEnviada",
            enviada_en,
        )

    @property
    def id(self):
        return self._id

    @property
    def evento_id(self):
        return self._evento_id

    @property
    def proveedor_id(self):
        return self._proveedor_id

    @property
    def servicio(self):
        return self._servicio

    @property
    def enviada_en(self):
        return self._enviada_en

    @property
    def vence_en(self):
        return self._vence_en

    @property
    def estado(self):
        return self._estado

    @property
    def eventos(self):
        return tuple(self._eventos)

    def confirmar(self, ahora: datetime):
        self._validar_respuesta(ahora)
        self._estado = EstadoSolicitud.CONFIRMADA
        self._registrar_evento("ProveedorConfirmo", ahora)

    def rechazar(self, ahora: datetime):
        self._validar_respuesta(ahora)
        self._estado = EstadoSolicitud.RECHAZADA
        self._registrar_evento("ProveedorRechazo", ahora)

    def expirar(self, ahora: datetime):
        self._validar_instante(ahora)
        self._exigir_pendiente()

        if ahora < self._vence_en:
            raise TransicionInvalida(
                "La solicitud todavía no ha vencido."
            )

        self._estado = EstadoSolicitud.EXPIRADA
        self._registrar_evento(
            "SolicitudDeProveedorExpirada",
            ahora,
        )

    def _validar_respuesta(self, ahora):
        self._validar_instante(ahora)
        self._exigir_pendiente()

        if ahora >= self._vence_en:
            raise TransicionInvalida(
                "El plazo de respuesta de 48 horas terminó."
            )

    def _exigir_pendiente(self):
        if self._estado != EstadoSolicitud.PENDIENTE:
            raise TransicionInvalida(
                "Solo se puede modificar una solicitud pendiente."
            )

    def _validar_instante(self, ahora):
        self._validar_fecha(ahora)

        if ahora < self._enviada_en:
            raise SolicitudInvalida(
                "La acción no puede ocurrir antes del envío."
            )

    @staticmethod
    def _validar_fecha(fecha):
        if (
            not isinstance(fecha, datetime)
            or fecha.tzinfo is None
            or fecha.utcoffset() is None
        ):
            raise SolicitudInvalida(
                "La fecha debe incluir zona horaria."
            )

    def _registrar_evento(self, tipo, ahora):
        self._eventos.append(
            EventoDeDominio(
                tipo=tipo,
                agregado_id=self._id,
                version=1,
                ocurrido_en=ahora,
            )
        )