from src.application.evento_service import EventoNoEncontrado
from src.application.propuesta_service import PropuestaNoEncontrada
from src.domain.cambios import (
    AplicadorDeCambios,
    CambioInvalido,
    EstadoCambio,
    SolicitudDeCambio,
)
from src.domain.eventos import EstadoEvento
from src.domain.exceptions import TransicionInvalida


class CambioNoEncontrado(Exception):
    pass


class CambioService:
    def __init__(
        self,
        crear_uow,
        crear_eventos,
        crear_propuestas,
        crear_cambios,
        fecha_actual,
    ):
        self.crear_uow = crear_uow
        self.crear_eventos = crear_eventos
        self.crear_propuestas = crear_propuestas
        self.crear_cambios = crear_cambios
        self.fecha_actual = fecha_actual

    def solicitar(
        self,
        evento_id,
        propuesta_id,
        nuevas_lineas,
        fecha_evento,
        solicitante,
        motivo,
    ):
        with self.crear_uow() as uow:
            eventos = self.crear_eventos(uow.session)
            propuestas = self.crear_propuestas(uow.session)
            cambios = self.crear_cambios(uow.session)

            evento, propuesta = self._obtener_contexto(
                eventos,
                propuestas,
                evento_id,
                propuesta_id,
            )

            cambio = SolicitudDeCambio(
                propuesta=propuesta,
                nuevas_lineas=nuevas_lineas,
                fecha_evento=fecha_evento,
                fecha_solicitud=self.fecha_actual(),
                solicitante=solicitante,
                motivo=motivo,
            )
            cambios.agregar(cambio)

            if cambio.estado == EstadoCambio.LISTO_PARA_APLICAR:
                self._aplicar(
                    cambio, evento, propuesta, eventos, propuestas
                )
                cambios.guardar(cambio)

            uow.commit()

        return cambio

    def consultar(self, cambio_id):
        with self.crear_uow() as uow:
            cambios = self.crear_cambios(uow.session)
            return self._obtener_cambio(cambios, cambio_id)

    def autorizar_y_aplicar(self, cambio_id, responsable):
        with self.crear_uow() as uow:
            eventos = self.crear_eventos(uow.session)
            propuestas = self.crear_propuestas(uow.session)
            cambios = self.crear_cambios(uow.session)

            cambio = self._obtener_cambio(cambios, cambio_id)

            evento, propuesta = self._obtener_contexto(
                eventos,
                propuestas,
                cambio.evento_id,
                cambio.propuesta_id,
            )

            cambio.autorizar(
                responsable=responsable,
                rol="ADMINISTRACION",
                fecha=self.fecha_actual(),
            )

            self._aplicar(
                cambio, evento, propuesta, eventos, propuestas
            )
            cambios.guardar(cambio)
            uow.commit()

        return cambio

    @staticmethod
    def _obtener_contexto(
        eventos, propuestas, evento_id, propuesta_id
    ):
        evento = eventos.obtener(evento_id)

        if evento is None:
            raise EventoNoEncontrado("El evento no existe.")

        propuesta = propuestas.obtener(propuesta_id)

        if propuesta is None:
            raise PropuestaNoEncontrada("La propuesta no existe.")

        if evento.estado != EstadoEvento.CONFIRMADO:
            raise TransicionInvalida(
                "El evento debe estar confirmado para solicitar cambios."
            )

        if (
            evento.contrato is None
            or evento.contrato.propuesta_id != propuesta.id
            or propuesta.evento_id != evento.id
        ):
            raise CambioInvalido(
                "La propuesta no corresponde al contrato del evento."
            )

        return evento, propuesta

    @staticmethod
    def _obtener_cambio(repo, cambio_id):
        cambio = repo.obtener(cambio_id)

        if cambio is None:
            raise CambioNoEncontrado("La solicitud de cambio no existe.")

        return cambio

    @staticmethod
    def _aplicar(cambio, evento, propuesta, eventos, propuestas):
        AplicadorDeCambios().aplicar(cambio, evento, propuesta)
        propuestas.guardar_versiones(propuesta)
        eventos.guardar(evento)