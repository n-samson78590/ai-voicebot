from fastapi import APIRouter

from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.ivr import router as ivr_router
from backend.app.api.routes.tickets import router as tickets_router
from backend.app.api.routes.webhooks import router as webhooks_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(tickets_router)
api_router.include_router(ivr_router)
api_router.include_router(webhooks_router)
