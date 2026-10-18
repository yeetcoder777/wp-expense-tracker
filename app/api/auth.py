import hmac

from fastapi import Header, HTTPException

from app.config import settings


def require_dashboard_user(authorization: str | None = Header(default=None)) -> str:
    if not settings.dashboard_api_token or not settings.dashboard_user_id:
        raise HTTPException(
            status_code=503,
            detail="Configure DASHBOARD_API_TOKEN and DASHBOARD_USER_ID to enable the dashboard API.",
        )

    expected = f"Bearer {settings.dashboard_api_token}"
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Invalid dashboard token")
    return settings.dashboard_user_id
