class SqlAlchemyUnitOfWork:
    def __init__(self, fabrica_sesiones):
        self._fabrica_sesiones = fabrica_sesiones
        self.session = None

    def __enter__(self):
        self.session = self._fabrica_sesiones()
        return self

    def commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()

    def __exit__(self, tipo_error, error, traceback):
        try:
            # Descarta cualquier trabajo que no se haya confirmado.
            self.rollback()
        finally:
            self.session.close()

        # Permite que el error llegue a la capa que llamó la operación.
        return False