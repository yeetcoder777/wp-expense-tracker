from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.auth import require_dashboard_user
from app.db.database import get_db
from app.services.date_service import get_today
from app.services.report_service import compare_months, get_report

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/monthly")
def monthly_report(
    year: int | None = Query(default=None, ge=2000, le=2200),
    month: int | None = Query(default=None, ge=1, le=12),
    currency: str = "INR",
    user_id: str = Depends(require_dashboard_user),
    db: Session = Depends(get_db),
):
    current = get_today()
    selected_year = year or current.year
    selected_month = month or current.month
    return compare_months(db, user_id, selected_year, selected_month, currency.upper())


@router.get("/range")
def custom_report(
    start_date: date,
    end_date: date,
    currency: str = "INR",
    user_id: str = Depends(require_dashboard_user),
    db: Session = Depends(get_db),
):
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date")
    return get_report(db, user_id, start_date, end_date, currency.upper())
