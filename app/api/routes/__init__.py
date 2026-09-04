"""API Router registration and aggregation."""

from fastapi import APIRouter

from app.api.routes.agent import router as agent_router
from app.api.routes.auth import router as auth_router
from app.api.routes.documents import router as documents_router
from app.api.routes.dossiers import router as dossiers_router
from app.api.routes.events import router as events_router
from app.api.routes.health import router as health_router
from app.api.routes.search import router as search_router
from app.api.routes.settings import router as settings_router
from app.api.routes.sync import router as sync_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(documents_router)
api_router.include_router(dossiers_router)
api_router.include_router(events_router)
api_router.include_router(search_router)
api_router.include_router(sync_router)
api_router.include_router(auth_router)
api_router.include_router(settings_router)
api_router.include_router(agent_router)

__all__ = ["api_router"]


