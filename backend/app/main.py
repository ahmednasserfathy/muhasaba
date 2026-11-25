from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import get_session
from app.core.observability import request_event
from app.modules.auth.router import router as auth_router
from app.modules.catalog.router import router as catalog_router
from app.modules.editorial.router import router as editorial_router
from app.modules.fasting.router import router as fasting_router
from app.modules.journal.router import router as journal_router
from app.modules.personal.router import router as personal_router
from app.modules.reports.router import router as reports_router

app = FastAPI(title="Muhasaba", version="0.1.0")
app.include_router(catalog_router)
app.include_router(auth_router)
app.include_router(journal_router)
app.include_router(fasting_router)
app.include_router(reports_router)
app.include_router(personal_router)
app.include_router(editorial_router)


@app.middleware("http")
async def private_account_responses(request: Request, call_next):
    response = await call_next(request)
    if (
        request.url.path.startswith("/api/v1/auth/")
        or request.url.path == "/api/v1/me"
        or request.url.path.startswith("/api/v1/me/")
        or request.url.path.startswith("/api/v1/admin/")
        or request.url.path.startswith("/api/v1/days")
        or request.url.path.startswith("/api/v1/fasting")
        or request.url.path.startswith("/api/v1/reports")
    ):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    return response


app.middleware("http")(request_event)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    if request.url.path.startswith(("/api/v1/auth/", "/api/v1/me/", "/api/v1/admin/")):
        # Never echo submitted passwords/tokens in validation responses.
        errors = [
            {key: error[key] for key in ("loc", "msg", "type")}
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": errors})
    return await request_validation_exception_handler(request, exc)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Process liveness only; database readiness is checked separately."""
    return HealthResponse()


@app.get(
    "/ready",
    response_model=HealthResponse,
    responses={503: {"description": "Database unavailable"}},
)
def ready(db=Depends(get_session)) -> HealthResponse:
    """Database connectivity only; migration and content checks are release gates."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(503, "Database unavailable") from None
    return HealthResponse()
