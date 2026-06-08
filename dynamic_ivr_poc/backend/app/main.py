from fastapi import FastAPI

from backend.app.api.router import api_router
from backend.app.db.base import Base
from backend.app.db.session import engine
from backend.app.models import CallAttempt, CallResponse  # noqa: F401


def create_application() -> FastAPI:
    application = FastAPI(title="Dynamic IVR POC API")
    application.include_router(api_router)
    return application


Base.metadata.create_all(bind=engine)
app = create_application()
