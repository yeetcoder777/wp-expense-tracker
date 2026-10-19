"""Dashboard session endpoints and the common financial API identity dependency."""

import hmac
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import get_db
from app.schemas.dashboard_auth import AccountRead, LoginChallengeRead, LoginComplete, LoginStart
from app.services import dashboard_auth_service as auth

router = APIRouter(prefix="/api/auth", tags=["dashboard accounts"])


def require_browser_request(request: Request) -> None:
    # A custom header blocks cross-site HTML form submission; no permissive CORS
    # is enabled. Also reject foreign origins when the browser supplies Origin.
    if request.headers.get("X-Ledger-Request") != "1":
        raise HTTPException(status_code=403, detail="Invalid dashboard request")
    origin = request.headers.get("Origin")
    expected = urlsplit(settings.dashboard_public_url or str(request.base_url))
    if origin and origin.rstrip("/") != f"{expected.scheme}://{expected.netloc}":
        raise HTTPException(status_code=403, detail="Dashboard request origin does not match")


def _account_read(account) -> AccountRead:
    return AccountRead(account_id=account.id, whatsapp_number=account.whatsapp_user_id.removeprefix("whatsapp:"))


def require_dashboard_user(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> str:
    if settings.dashboard_auth_mode == "legacy":
        # Explicit compatibility mode for old local tooling, never public hosting.
        if settings.environment.lower() == "production":
            raise HTTPException(status_code=503, detail="Legacy dashboard tokens are disabled in production")
        expected = "Bearer " + (settings.dashboard_api_token or "")
        if (not settings.dashboard_api_token or not settings.dashboard_user_id
                or not authorization or not hmac.compare_digest(authorization, expected)):
            raise HTTPException(status_code=401, detail="Invalid dashboard token")
        return settings.dashboard_user_id
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        require_browser_request(request)
    try:
        account = auth.session_account(db, request.cookies.get(auth.COOKIE_NAME))
        request.state.dashboard_account_id = account.id
        return account.whatsapp_user_id
    except auth.DashboardAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/me", response_model=AccountRead)
def current_account(request: Request, db: Session = Depends(get_db)):
    try:
        return _account_read(auth.session_account(db, request.cookies.get(auth.COOKIE_NAME)))
    except auth.DashboardAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/login/start", response_model=LoginChallengeRead)
def begin_login(payload: LoginStart, request: Request, db: Session = Depends(get_db)):
    require_browser_request(request)
    try:
        return auth.start_login(db, payload.phone, request.client.host if request.client else "unknown")
    except auth.DashboardAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/login/complete")
def finish_login(payload: LoginComplete, request: Request, response: Response, db: Session = Depends(get_db)):
    require_browser_request(request)
    try:
        result = auth.complete_login(db, payload.request_id, payload.poll_secret)
    except auth.DashboardAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    if result is None:
        response.status_code = 202
        return {"status": "pending"}
    token, account = result
    secure = settings.dashboard_cookie_secure
    if secure is None:
        secure = settings.environment.lower() == "production"
    response.set_cookie(
        auth.COOKIE_NAME, token, max_age=settings.dashboard_session_hours * 3600,
        httponly=True, secure=secure, samesite="strict", path="/",
    )
    return {"status": "authenticated", "account": _account_read(account).model_dump()}


@router.post("/logout", status_code=204)
def logout(request: Request, db: Session = Depends(get_db)):
    require_browser_request(request)
    auth.revoke_session(db, request.cookies.get(auth.COOKIE_NAME))
    response = Response(status_code=204)
    response.delete_cookie(auth.COOKIE_NAME, path="/", samesite="strict")
    return response
