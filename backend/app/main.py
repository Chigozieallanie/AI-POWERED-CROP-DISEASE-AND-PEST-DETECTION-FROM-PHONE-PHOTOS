import time
from collections.abc import Awaitable, Callable

from fastapi import Depends, FastAPI, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.admin import install_admin
from app.config import get_settings
from app.db import SessionLocal, get_db
from app.errors import install_error_handlers
from app.inference import ModelRegistry
from app.models import UsageEvent
from app.routers import mobile, partner
from app.security import IpRateLimiter

UPLOAD_PATHS = ("/v1/diagnose", "/app/v1/contributions")


def _record_usage(tenant_id: int, endpoint: str, status: int, latency_ms: int) -> None:
    with SessionLocal() as db:
        db.add(
            UsageEvent(tenant_id=tenant_id, endpoint=endpoint, status=status, latency_ms=latency_ms)
        )
        db.commit()


def create_app(registry: ModelRegistry | None = None) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Crop Disease and Pest API", version="1.0.0")
    app.state.models = registry or ModelRegistry.from_directory(settings.model_dir)
    app.state.app_limiter = IpRateLimiter(settings.app_rate_limit_per_minute)
    install_error_handlers(app)

    @app.middleware("http")
    async def guard_and_meter(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        length = request.headers.get("content-length", "")
        if (
            request.url.path in UPLOAD_PATHS
            and length.isdigit()
            and int(length) > settings.max_request_bytes
        ):
            return JSONResponse(
                {"error": {"code": "too_large", "message": "The upload is too large."}}, 413
            )

        started = time.perf_counter()
        response = await call_next(request)
        tenant_id = getattr(request.state, "tenant_id", None)
        route = request.scope.get("route")
        if tenant_id is not None and route is not None:
            # The route template is logged, so query values such as coordinates never are.
            await run_in_threadpool(
                _record_usage,
                tenant_id,
                route.path,
                response.status_code,
                int((time.perf_counter() - started) * 1000),
            )
        return response

    app.include_router(partner.router)
    app.include_router(mobile.router)

    @app.get("/healthz", tags=["Operations"])
    def healthz(request: Request, db: Session = Depends(get_db)) -> dict:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "models": sorted(request.app.state.models.models)}

    install_admin(app, settings)
    return app
