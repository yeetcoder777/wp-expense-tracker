import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.api.webhook import router as webhook_router
from app.api import budgets, imports, recurring, reports, transactions
from app.db.database import Base, engine
import app.db.models
from app.services.recurring_service import recurring_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.extraction_provider == "gliner2":
        from app.services.local_extraction_service import load_local_model

        try:
            await asyncio.to_thread(load_local_model)
        except (ImportError, OSError, ValueError, RuntimeError):
            if not settings.gliner2_fallback_to_groq:
                raise
            logging.getLogger("uvicorn.error").exception("Local extractor unavailable; Groq fallback enabled")
    Base.metadata.create_all(bind=engine)
    worker = asyncio.create_task(recurring_worker(), name="recurring-payment-worker")
    try:
        yield
    finally:
        worker.cancel()
        with suppress(asyncio.CancelledError):
            await worker


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)

logger = logging.getLogger("uvicorn.error")


@app.middleware("http")
async def log_webhook_requests(request, call_next):
    if request.url.path.startswith("/webhook"):
        logger.info("Webhook arrived: %s %s", request.method, request.url.path)
        response = await call_next(request)
        logger.info("Webhook completed: HTTP %s", response.status_code)
        return response
    return await call_next(request)


app.include_router(
    webhook_router,
    prefix="/webhook",
)

app.include_router(transactions.router)
app.include_router(budgets.router)
app.include_router(reports.router)
app.include_router(recurring.router)
app.include_router(imports.router)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "environment": settings.environment,
    }


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="dashboard")
