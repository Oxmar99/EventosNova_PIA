import os

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def crear_motor(url=None):
    direccion = url or os.getenv(
        "DATABASE_URL",
        "sqlite:///./eventos_nova.db",
    )

    # Algunos proveedores entregan estas formas de URL.
    if direccion.startswith("postgres://"):
        direccion = direccion.replace(
            "postgres://", "postgresql+psycopg://", 1
        )
    elif direccion.startswith("postgresql://"):
        direccion = direccion.replace(
            "postgresql://", "postgresql+psycopg://", 1
        )

    es_sqlite = make_url(direccion).get_backend_name() == "sqlite"

    opciones = {"pool_pre_ping": True}

    if es_sqlite:
        opciones["connect_args"] = {"check_same_thread": False}

    motor = create_engine(direccion, **opciones)

    if es_sqlite:
        @event.listens_for(motor, "connect")
        def activar_claves_foraneas(conexion, registro):
            cursor = conexion.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return motor


def crear_fabrica_sesiones(motor):
    return sessionmaker(
        bind=motor,
        autoflush=False,
        expire_on_commit=False,
    )