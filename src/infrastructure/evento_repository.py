from decimal import Decimal

from src.domain.eventos import Contrato, EstadoEvento, Evento, Pago
from src.domain.value_objects import Dinero
from src.infrastructure.evento_models import EventoRow, PagoRow

# Registra también la tabla referenciada por el contrato.
from src.infrastructure.models import PropuestaRow

from sqlalchemy import select

from src.domain.eventos import AjusteDeCambio
from src.infrastructure.ajuste_models import AjusteCambioRow


class SqlAlchemyRepositorioDeEventos:
    def __init__(self, session):
        self.session = session
        self._cargados = {}

    def agregar(self, evento: Evento):
        fila = EventoRow(
            id=evento.id,
            estado=evento.estado.value,
        )
        self._copiar_contrato(evento, fila)

        for pago in evento.pagos:
            fila.pagos.append(self._crear_pago(pago))

        self.session.add(fila)
        self._cargados[evento.id] = (evento, fila)

    def obtener(self, evento_id: str):
        if evento_id in self._cargados:
            return self._cargados[evento_id][0]

        fila = self.session.get(EventoRow, evento_id)

        if fila is None:
            return None

        evento = Evento(fila.id)
        evento._estado = EstadoEvento(fila.estado)

        if fila.contrato_referencia is not None:
            evento._contrato = Contrato(
                referencia=fila.contrato_referencia,
                propuesta_id=fila.contrato_propuesta_id,
                version=fila.contrato_version,
                total=Dinero(
                    Decimal(fila.contrato_total_centavos) / Decimal("100")
                ),
            )

        evento._pagos = [
            Pago(
                monto=Dinero(
                    Decimal(pago.monto_centavos) / Decimal("100")
                ),
                responsable=pago.responsable,
            )
            for pago in fila.pagos
        ]

        # Leer datos existentes no genera nuevos eventos de dominio.
        evento._eventos = []

        ajustes_guardados = self.session.scalars(
            select(AjusteCambioRow)
            .where(AjusteCambioRow.evento_id == evento.id)
            .order_by(AjusteCambioRow.version)
        ).all()

        evento._ajustes = [
            AjusteDeCambio(
                cambio_id=ajuste.cambio_id,
                incremento=Dinero(
                    Decimal(ajuste.incremento_centavos) / Decimal("100")
                ),
                cargo=Dinero(
                    Decimal(ajuste.cargo_centavos) / Decimal("100")
                ),
                version=ajuste.version,
            )
            for ajuste in ajustes_guardados
        ]

        self._cargados[evento.id] = (evento, fila)
        return evento

    def guardar(self, evento: Evento):
        registro = self._cargados.get(evento.id)

        if registro is None or registro[0] is not evento:
            raise ValueError(
                "Primero recupera el evento con este repositorio."
            )

        fila = registro[1]
        cantidad_guardada = len(fila.pagos)

        if len(evento.pagos) < cantidad_guardada:
            raise ValueError("No se permite eliminar pagos registrados.")

        # Los pagos existentes son inmutables.
        for pago, guardado in zip(evento.pagos, fila.pagos):
            if (
                int(pago.monto.monto * 100) != guardado.monto_centavos
                or pago.responsable != guardado.responsable
            ):
                raise ValueError(
                    "No se permite modificar pagos registrados."
                )

        fila.estado = evento.estado.value
        self._copiar_contrato(evento, fila)

        for pago in evento.pagos[cantidad_guardada:]:
            fila.pagos.append(self._crear_pago(pago))

        self._guardar_ajustes(evento)

        # Fuerza una actualización de la raíz incluso si solo hubo pagos.
        fila.revision += 1

    @staticmethod
    def _crear_pago(pago):
        return PagoRow(
            monto_centavos=int(pago.monto.monto * 100),
            responsable=pago.responsable,
        )

    @staticmethod
    def _copiar_contrato(evento, fila):
        if evento.contrato is None:
            return

        fila.contrato_referencia = evento.contrato.referencia
        fila.contrato_propuesta_id = evento.contrato.propuesta_id
        fila.contrato_version = evento.contrato.version
        fila.contrato_total_centavos = int(
            evento.contrato.total.monto * 100
        )

    def _guardar_ajustes(self, evento):
        guardados = {
            ajuste.cambio_id: ajuste
            for ajuste in self.session.scalars(
                select(AjusteCambioRow).where(
                    AjusteCambioRow.evento_id == evento.id
                )
            ).all()
        }

        # Incluye ajustes agregados a la sesión aún no enviados a la DB.
        for pendiente in self.session.new:
            if (
                isinstance(pendiente, AjusteCambioRow)
                and pendiente.evento_id == evento.id
            ):
                guardados[pendiente.cambio_id] = pendiente

        actuales = {ajuste.cambio_id for ajuste in evento.ajustes}

        if not set(guardados).issubset(actuales):
            raise ValueError("No se permite eliminar ajustes aplicados.")

        for ajuste in evento.ajustes:
            incremento = int(ajuste.incremento.monto * 100)
            cargo = int(ajuste.cargo.monto * 100)
            anterior = guardados.get(ajuste.cambio_id)

            if anterior is not None:
                if (
                    anterior.incremento_centavos != incremento
                    or anterior.cargo_centavos != cargo
                    or anterior.version != ajuste.version
                ):
                    raise ValueError(
                        "No se permite modificar un ajuste aplicado."
                    )
                continue

            fila_ajuste = AjusteCambioRow(
                cambio_id=ajuste.cambio_id,
                evento_id=evento.id,
                incremento_centavos=incremento,
                cargo_centavos=cargo,
                version=ajuste.version,
            )
            self.session.add(fila_ajuste)
            guardados[ajuste.cambio_id] = fila_ajuste