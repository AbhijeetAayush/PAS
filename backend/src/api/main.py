from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.container import get_container
from api.routes import router, worker
from domain.models import AppError


def create_app() -> FastAPI:
    settings = get_container().settings
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    app = FastAPI(title="Voter rolls", docs_url=None, redoc_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins(),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(router)
    app.include_router(worker)

    @app.exception_handler(AppError)
    async def app_error(_request, exc: AppError) -> JSONResponse:
        return JSONResponse({"detail": exc.message}, status_code=exc.status_code)

    @app.exception_handler(RuntimeError)
    async def runtime_error(_request, exc: RuntimeError) -> JSONResponse:
        logging.getLogger(__name__).error("runtime error: %s", exc)
        return JSONResponse({"detail": str(exc)}, status_code=503)

    return app
