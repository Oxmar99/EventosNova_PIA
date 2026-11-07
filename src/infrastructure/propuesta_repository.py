from decimal import Decimal

from src.domain.propuestas import (
    EstadoPropuesta,
    LineaDeServicio,
    Propuesta,
    VersionDePropuesta,
)
from src.domain.value_objects import Dinero
from src.infrastructure.models import LineaRow, PropuestaRow, VersionRow


class SqlAlchemyRepositorioDePropuestas:
    def __init__(self, session):
        self.session = session

    def agregar(self, propuesta: Propuesta) -> None:
        fila = PropuestaRow(
            id=propuesta.id,
            evento_id=propuesta.evento_id,
            estado=propuesta.estado.value,
        )

        for version in propuesta.versiones:
            fila_version = VersionRow(numero=version.numero)

            for posicion, linea in enumerate(version.lineas):
                fila_version.lineas.append(
                    LineaRow(
                        posicion=posicion,
                        recurso_id=linea.recurso_id,
                        descripcion=linea.descripcion,
                        precio_centavos=int(
                            linea.precio_unitario.monto * 100
                        ),
                        cantidad=linea.cantidad,
                    )
                )

            fila.versiones.append(fila_version)

        self.session.add(fila)

    def obtener(self, propuesta_id: str) -> Propuesta | None:
        fila = self.session.get(PropuestaRow, propuesta_id)

        if fila is None:
            return None

        versiones = []

        for fila_version in fila.versiones:
            lineas = tuple(
                LineaDeServicio(
                    recurso_id=linea.recurso_id,
                    descripcion=linea.descripcion,
                    precio_unitario=Dinero(
                        Decimal(linea.precio_centavos) / Decimal("100")
                    ),
                    cantidad=linea.cantidad,
                )
                for linea in fila_version.lineas
            )

            versiones.append(
                VersionDePropuesta(
                    numero=fila_version.numero,
                    lineas=lineas,
                )
            )

        # Reconstruimos un objeto existente sin ejecutar su creación.
        propuesta = Propuesta.__new__(Propuesta)
        propuesta._id = fila.id
        propuesta._evento_id = fila.evento_id
        propuesta._estado = EstadoPropuesta(fila.estado)
        propuesta._versiones = versiones
        propuesta._eventos = []

        return propuesta

    def guardar_estado(self, propuesta: Propuesta) -> None:
        fila = self.session.get(PropuestaRow, propuesta.id)

        if fila is None:
            raise LookupError("La propuesta no existe.")

        fila.estado = propuesta.estado.value

    def guardar_versiones(self, propuesta: Propuesta) -> None:
        fila = self.session.get(PropuestaRow, propuesta.id)

        if fila is None:
            raise LookupError("La propuesta no existe.")

        existentes = {
            version.numero: version
            for version in fila.versiones
        }

        numeros_actuales = {
            version.numero for version in propuesta.versiones
        }

        if not set(existentes).issubset(numeros_actuales):
            raise ValueError("No se permite eliminar versiones.")

        for version in propuesta.versiones:
            anterior = existentes.get(version.numero)

            if anterior is not None:
                contenido_guardado = [
                    (
                        linea.recurso_id,
                        linea.descripcion,
                        linea.precio_centavos,
                        linea.cantidad,
                    )
                    for linea in anterior.lineas
                ]

                contenido_actual = [
                    (
                        linea.recurso_id,
                        linea.descripcion,
                        int(linea.precio_unitario.monto * 100),
                        linea.cantidad,
                    )
                    for linea in version.lineas
                ]

                if contenido_guardado != contenido_actual:
                    raise ValueError(
                        "Las versiones existentes son inmutables."
                    )
                continue

            nueva = VersionRow(numero=version.numero)

            for posicion, linea in enumerate(version.lineas):
                nueva.lineas.append(
                    LineaRow(
                        posicion=posicion,
                        recurso_id=linea.recurso_id,
                        descripcion=linea.descripcion,
                        precio_centavos=int(
                            linea.precio_unitario.monto * 100
                        ),
                        cantidad=linea.cantidad,
                    )
                )

            fila.versiones.append(nueva)
            existentes[version.numero] = nueva

        fila.estado = propuesta.estado.value