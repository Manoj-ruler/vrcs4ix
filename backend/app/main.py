import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.routes import analysis, health
from app.clients.elexon import ElexonError
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.services.analysis import AnalysisService, DataUnavailableError

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, service: AnalysisService | None = None) -> FastAPI:
    configure_logging()
    settings = settings or get_settings()
    app = FastAPI(title="Wind Forecast Accuracy API", version=__version__)
    app.state.analysis = service or AnalysisService(settings)

    app.add_middleware(
        CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["GET"], allow_headers=["*"],
    )

    @app.exception_handler(ElexonError)
    async def upstream_error(_: Request, exc: ElexonError) -> JSONResponse:
        logger.error("upstream_unavailable error=%s", exc)
        return JSONResponse(status_code=502, content={
            "detail": "The Elexon data service could not be reached. Please retry shortly.", "code": "upstream_unavailable",
        })

    @app.exception_handler(DataUnavailableError)
    async def data_unavailable(_: Request, exc: DataUnavailableError) -> JSONResponse:
        logger.error("data_unavailable error=%s", exc)
        return JSONResponse(status_code=503, content={"detail": str(exc), "code": "data_unavailable"})

    @app.exception_handler(Exception)
    async def unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error")
        return JSONResponse(status_code=500, content={"detail": "Internal server error", "code": "internal_error"})

    app.include_router(health.router)
    app.include_router(analysis.router)
    return app


app = create_app()
