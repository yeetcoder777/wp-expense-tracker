import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.auth import require_dashboard_user
from app.db.database import get_db
from app.db.models import TransactionDB
from app.schemas.features import TransactionRead, TransactionUpdate
from app.services.budget_service import evaluate_budget_alerts
from app.services.notification_service import send_whatsapp_message
from app.services.transaction_service import delete_user_transaction, get_user_transaction

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def _safe_csv_text(value: str | None) -> str:
    text = value or ""
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


@router.get("/currencies")
def list_currencies(
    user_id: str = Depends(require_dashboard_user),
    db: Session = Depends(get_db),
):
    values = db.query(TransactionDB.currency).filter(
        TransactionDB.user_id == user_id
    ).distinct().order_by(TransactionDB.currency).all()
    currencies = [value[0] for value in values if value[0]]
    return sorted(set(currencies or ["INR"]))


@router.get("", response_model=list[TransactionRead])
def list_transactions(
    start_date: date | None = None,
    end_date: date | None = None,
    category: str | None = None,
    transaction_type: str | None = Query(default=None, pattern="^(expense|income)$"),
    currency: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user_id: str = Depends(require_dashboard_user),
    db: Session = Depends(get_db),
):
    query = db.query(TransactionDB).filter(TransactionDB.user_id == user_id)
    if start_date:
        query = query.filter(TransactionDB.transaction_date >= start_date)
    if end_date:
        query = query.filter(TransactionDB.transaction_date <= end_date)
    if category:
        query = query.filter(TransactionDB.category == category.strip().lower())
    if transaction_type:
        query = query.filter(TransactionDB.transaction_type == transaction_type)
    if currency:
        query = query.filter(TransactionDB.currency == currency.upper())
    return query.order_by(
        TransactionDB.transaction_date.desc(),
        TransactionDB.created_at.desc(),
    ).offset(offset).limit(limit).all()


@router.post("/undo", response_model=TransactionRead)
def undo_last_transaction(
    user_id: str = Depends(require_dashboard_user),
    db: Session = Depends(get_db),
):
    transaction = delete_user_transaction(db, user_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="No transaction to undo")
    return transaction


@router.get("/{transaction_id}", response_model=TransactionRead)
def get_transaction(
    transaction_id: int,
    user_id: str = Depends(require_dashboard_user),
    db: Session = Depends(get_db),
):
    transaction = get_user_transaction(db, user_id, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@router.patch("/{transaction_id}", response_model=TransactionRead)
def update_transaction(
    transaction_id: int,
    changes: TransactionUpdate,
    user_id: str = Depends(require_dashboard_user),
    db: Session = Depends(get_db),
):
    transaction = get_user_transaction(db, user_id, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    values = changes.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=400, detail="No transaction changes supplied")
    if any(values.get(field) is None for field in ("amount", "transaction_type", "currency", "category") if field in values):
        raise HTTPException(status_code=422, detail="Amount, type, currency, and category cannot be null")
    for field, value in values.items():
        if isinstance(value, str):
            value = value.strip()
            if field == "currency":
                if not value:
                    raise HTTPException(status_code=422, detail="Currency cannot be empty")
                value = value.upper()
            elif field == "category":
                if not value:
                    raise HTTPException(status_code=422, detail="Category cannot be empty")
                value = value.lower()
        setattr(transaction, field, value)
    db.commit()
    db.refresh(transaction)
    alerts = evaluate_budget_alerts(db, user_id, transaction)
    if alerts:
        send_whatsapp_message(user_id, "\n".join(alerts))
    return transaction


@router.delete("/{transaction_id}", response_model=TransactionRead)
def remove_transaction(
    transaction_id: int,
    user_id: str = Depends(require_dashboard_user),
    db: Session = Depends(get_db),
):
    transaction = delete_user_transaction(db, user_id, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@router.get("/export/csv")
def export_transactions_csv(
    start_date: date | None = None,
    end_date: date | None = None,
    currency: str | None = None,
    user_id: str = Depends(require_dashboard_user),
    db: Session = Depends(get_db),
):
    query = db.query(TransactionDB).filter(TransactionDB.user_id == user_id)
    if start_date:
        query = query.filter(TransactionDB.transaction_date >= start_date)
    if end_date:
        query = query.filter(TransactionDB.transaction_date <= end_date)
    if currency:
        query = query.filter(TransactionDB.currency == currency.upper())

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(("id", "date", "type", "amount", "currency", "category", "purpose", "person"))
    for item in query.order_by(TransactionDB.transaction_date, TransactionDB.id).all():
        writer.writerow((
            item.id,
            item.transaction_date.isoformat() if item.transaction_date else "",
            item.transaction_type,
            item.amount,
            _safe_csv_text(item.currency),
            _safe_csv_text(item.category),
            _safe_csv_text(item.purpose),
            _safe_csv_text(item.person),
        ))
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=transactions.csv"},
    )
