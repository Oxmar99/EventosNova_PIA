from fastapi import FastAPI

app = FastAPI(
    title="Eventos Nova API",
    description="Sistema de gestión de propuestas, eventos y proveedores.",
    version="0.1.0",
)


@app.get("/health", tags=["Estado"])
def health_check():
    return {
        "status": "ok",
        "application": "Eventos Nova",
    }