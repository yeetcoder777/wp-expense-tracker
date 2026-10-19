import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.api.webhook import router as webhook_router
from app.api import auth, budgets, imports, recurring, reports, transactions
from app.services.database_setup_service import prepare_database
from app.services.recurring_service import recurring_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.environment.lower() == "production":
        if settings.dashboard_auth_mode != "whatsapp":
            raise RuntimeError("Production dashboards require WhatsApp account authentication")
        if settings.dashboard_cookie_secure is False:
            raise RuntimeError("Production dashboard cookies must use HTTPS")
        if not settings.twilio_auth_token:
            raise RuntimeError("Production requires Twilio signature validation")
    await asyncio.to_thread(prepare_database)
    if settings.extraction_provider == "gliner2":
        from app.services.local_extraction_service import load_local_model

        try:
            await asyncio.to_thread(load_local_model)
        except (ImportError, OSError, ValueError, RuntimeError):
            if not settings.gliner2_fallback_to_groq:
                raise
            logging.getLogger("uvicorn.error").exception("Local extractor unavailable; Groq fallback enabled")
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
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        account_id = getattr(request.state, "dashboard_account_id", None)
        if account_id:
            response.headers["X-Ledger-Account"] = account_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path not in {"/docs", "/redoc", "/docs/oauth2-redirect"}:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
            "base-uri 'self'; form-action 'self'"
        )
    return response


app.include_router(
    webhook_router,
    prefix="/webhook",
)

app.include_router(auth.router)
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


# A built React frontend is served from the same origin as the authenticated API.
# Source-only Python setups retain the original dashboard until React is built.
frontend_directory = Path(__file__).resolve().parents[2] / "frontend"
frontend_dist = frontend_directory / "dist"
dashboard_directory = (
    frontend_dist if (frontend_dist / "index.html").is_file()
    else frontend_directory / "legacy"
)
app.mount("/", StaticFiles(directory=dashboard_directory, html=True), name="dashboard")
