from src.application.evento_service import EventoNoEncontrado
from src.domain.eventos import EstadoEvento
from src.domain.exceptions import TransicionInvalida
from src.domain.proveedores import SolicitudDeProveedor


class SolicitudNoEncontrada(Exception):
    pass


class ProveedorService:
    def __init__(
        self,
        crear_uow,
        crear_eventos,
        crear_solicitudes,
        reloj,
    ):
        self.crear_uow = crear_uow
        self.crear_eventos = crear_eventos
        self.crear_solicitudes = crear_solicitudes
        self.reloj = reloj

    def solicitar(self, evento_id, proveedor_id, servicio):
        with self.crear_uow() as uow:
            eventos = self.crear_eventos(uow.session)
            solicitudes = self.crear_solicitudes(uow.session)

            evento = eventos.obtener(evento_id)

            if evento is None:
                raise EventoNoEncontrado("El evento no existe.")

            if evento.estado != EstadoEvento.CONFIRMADO:
                raise TransicionInvalida(
                    "Solo un evento confirmado puede solicitar proveedores."
                )

            solicitud = SolicitudDeProveedor(
                evento_id=evento_id,
                proveedor_id=proveedor_id,
                servicio=servicio,
                enviada_en=self.reloj(),
            )

            solicitudes.agregar(solicitud)
            uow.commit()

        return solicitud

    def consultar(self, solicitud_id):
        with self.crear_uow() as uow:
            repo = self.crear_solicitudes(uow.session)
            return self._obtener(repo, solicitud_id)

    def ejecutar(self, solicitud_id, accion):
        if accion not in {"confirmar", "rechazar", "expirar"}:
            raise TransicionInvalida("Acción no permitida.")

        with self.crear_uow() as uow:
            repo = self.crear_solicitudes(uow.session)
            solicitud = self._obtener(repo, solicitud_id)

            getattr(solicitud, accion)(self.reloj())

            repo.guardar(solicitud)
            uow.commit()

        return solicitud

    @staticmethod
    def _obtener(repo, solicitud_id):
        solicitud = repo.obtener(solicitud_id)

        if solicitud is None:
            raise SolicitudNoEncontrada("La solicitud no existe.")

        return solicitud