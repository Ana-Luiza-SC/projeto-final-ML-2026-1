from __future__ import annotations

from fastapi import FastAPI

from app.routers.disciplines import router as disciplines_router

app = FastAPI(
    title="EstudaUnB API",
    version="0.1.0",
    description="Backend inicial do MVP EstudaUnB.",
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(disciplines_router)
