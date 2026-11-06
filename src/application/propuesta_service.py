from src.domain.propuestas import Propuesta


class PropuestaNoEncontrada(Exception):
    pass


class PropuestaService:
    def __init__(self, crear_uow, crear_repositorio):
        self.crear_uow = crear_uow
        self.crear_repositorio = crear_repositorio

    def crear(self, evento_id, lineas):
        propuesta = Propuesta(evento_id=evento_id, lineas=lineas)

        with self.crear_uow() as uow:
            repo = self.crear_repositorio(uow.session)
            repo.agregar(propuesta)
            uow.commit()

        return propuesta

    def consultar(self, propuesta_id):
        with self.crear_uow() as uow:
            repo = self.crear_repositorio(uow.session)
            propuesta = repo.obtener(propuesta_id)

            if propuesta is None:
                raise PropuestaNoEncontrada("La propuesta no existe.")

            return propuesta

    def enviar(self, propuesta_id):
        return self._cambiar_estado(propuesta_id, "enviar")

    def aceptar(self, propuesta_id):
        return self._cambiar_estado(propuesta_id, "aceptar")

    def _cambiar_estado(self, propuesta_id, accion):
        with self.crear_uow() as uow:
            repo = self.crear_repositorio(uow.session)
            propuesta = repo.obtener(propuesta_id)

            if propuesta is None:
                raise PropuestaNoEncontrada("La propuesta no existe.")

            if accion == "enviar":
                propuesta.enviar()
            else:
                propuesta.aceptar()

            repo.guardar_estado(propuesta)
            uow.commit()

        return propuesta