from src.application.propuesta_service import PropuestaNoEncontrada
from src.domain.eventos import Evento
from src.domain.exceptions import TransicionInvalida


class EventoNoEncontrado(Exception):
    pass


class EventoService:
    def __init__(
        self,
        crear_uow,
        crear_repositorio_eventos,
        crear_repositorio_propuestas,
    ):
        self.crear_uow = crear_uow
        self.crear_eventos = crear_repositorio_eventos
        self.crear_propuestas = crear_repositorio_propuestas

    def crear(self, evento_id):
        with self.crear_uow() as uow:
            repo = self.crear_eventos(uow.session)

            if repo.obtener(evento_id) is not None:
                raise TransicionInvalida(
                    "Ya existe un evento con ese identificador."
                )

            evento = Evento(evento_id)
            repo.agregar(evento)
            uow.commit()

        return evento

    def consultar(self, evento_id):
        with self.crear_uow() as uow:
            repo = self.crear_eventos(uow.session)
            return self._obtener(repo, evento_id)

    def registrar_contrato(self, evento_id, propuesta_id, referencia):
        with self.crear_uow() as uow:
            eventos = self.crear_eventos(uow.session)
            propuestas = self.crear_propuestas(uow.session)

            evento = self._obtener(eventos, evento_id)
            propuesta = propuestas.obtener(propuesta_id)

            if propuesta is None:
                raise PropuestaNoEncontrada("La propuesta no existe.")

            evento.registrar_contrato_firmado(propuesta, referencia)
            eventos.guardar(evento)
            uow.commit()

        return evento

    def registrar_anticipo(self, evento_id, monto, responsable):
        with self.crear_uow() as uow:
            repo = self.crear_eventos(uow.session)
            evento = self._obtener(repo, evento_id)

            evento.registrar_anticipo(
                monto=monto,
                responsable=responsable,
                rol="ADMINISTRACION",
            )

            repo.guardar(evento)
            uow.commit()

        return evento

    @staticmethod
    def _obtener(repo, evento_id):
        evento = repo.obtener(evento_id)

        if evento is None:
            raise EventoNoEncontrado("El evento no existe.")

        return evento