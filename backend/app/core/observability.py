"""Small, allowlisted request events: no bodies, identities or raw URL values."""

import json
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("uvicorn.error")


async def request_event(request: Request, call_next):
    request_id = uuid4().hex
    started = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        # Raw exception messages/tracebacks can include SQL params or private text.
        response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "requestId": request_id},
        )
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Request-ID"] = request_id
    route = request.scope.get("route")
    event = {
        "event": "http_request",
        "requestId": request_id,
        "method": request.method
        if request.method
        in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
        else "OTHER",
        "route": getattr(route, "path", "unmatched"),
        "status": response.status_code,
        "durationMs": round((perf_counter() - started) * 1000, 2),
    }
    logger.log(
        logging.ERROR if response.status_code >= 500 else logging.INFO,
        json.dumps(event, separators=(",", ":")),
    )
    return response
