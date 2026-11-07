import os
from secrets import compare_digest

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader


clave_administracion = APIKeyHeader(
    name="X-Admin-Key",
    scheme_name="Administracion",
    auto_error=False,
)


def exigir_administracion(
    clave: str | None = Depends(clave_administracion),
):
    esperada = os.getenv("ADMIN_API_KEY")

    if not esperada:
        raise HTTPException(
            status_code=503,
            detail="La autenticación administrativa no está configurada.",
        )

    if clave is None or not compare_digest(
        clave.encode("utf-8"),
        esperada.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=401,
            detail="Clave administrativa inválida.",
        )

    return os.getenv("ADMIN_USER", "administracion")
