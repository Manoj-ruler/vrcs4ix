from fastapi import APIRouter, Request

from app import __version__
from app.schemas.analysis import Health

router = APIRouter()


@router.get("/api/health", response_model=Health)
async def health(request: Request) -> Health:
    """Liveness only: never triggers an upstream download."""
    return Health(status="ok", version=__version__, data_loaded=request.app.state.analysis.is_loaded)
