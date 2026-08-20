from fastapi import FastAPI

from app.config import settings
from app.api.webhook import router as webhook_router


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
)


app.include_router(
    webhook_router,
    prefix="/webhook",
)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "environment": settings.environment,
    }