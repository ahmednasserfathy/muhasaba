from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from app.modules.catalog.router import router as catalog_router

app = FastAPI(title="Muhasaba", version="0.1.0")
app.include_router(catalog_router)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Process liveness only; database readiness is checked separately."""
    return HealthResponse()
