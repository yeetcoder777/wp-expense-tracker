from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.auth import require_dashboard_user
from app.db.database import get_db
from app.db.models import Budget, BudgetAlert, TransactionDB
from app.schemas.features import BudgetCreate
from app.services.budget_service import monthly_bounds
from app.services.date_service import get_today

router = APIRouter(prefix="/api/budgets", tags=["budgets"])


def _serialize_budget(db: Session, budget: Budget, day: date) -> dict:
    start, end = monthly_bounds(day)
    query = db.query(func.coalesce(func.sum(TransactionDB.amount), 0)).filter(
        TransactionDB.user_id == budget.user_id,
        TransactionDB.transaction_type == "expense",
        TransactionDB.currency == budget.currency,
        TransactionDB.transaction_date >= start,
        TransactionDB.transaction_date <= end,
    )
    if budget.category != "all":
        query = query.filter(TransactionDB.category == budget.category)
    result = query.scalar()
    spent = result if isinstance(result, Decimal) else Decimal(str(result))
    percent = (spent / budget.amount * 100) if budget.amount else 0
    return {
        "id": budget.id,
        "category": budget.category,
        "amount": budget.amount,
        "currency": budget.currency,
        "spent": spent,
        "remaining": max(budget.amount - spent, 0),
        "percent_used": min(percent, 100),
        "period_start": monthly_bounds(day)[0],
    }


@router.get("")
def list_budgets(
    user_id: str = Depends(require_dashboard_user),
    db: Session = Depends(get_db),
):
    budgets = db.query(Budget).filter(Budget.user_id == user_id).order_by(Budget.category).all()
    today = get_today()
    return [_serialize_budget(db, budget, today) for budget in budgets]


@router.post("")
def save_budget(
    payload: BudgetCreate,
    user_id: str = Depends(require_dashboard_user),
    db: Session = Depends(get_db),
):
    budget = db.query(Budget).filter(
        Budget.user_id == user_id,
        Budget.category == payload.category,
        Budget.currency == payload.currency.upper(),
    ).first()
    if budget is None:
        budget = Budget(
            user_id=user_id,
            category=payload.category,
            amount=payload.amount,
            currency=payload.currency.upper(),
        )
        db.add(budget)
    else:
        db.query(BudgetAlert).filter(BudgetAlert.budget_id == budget.id).delete()
        budget.amount = payload.amount
    db.commit()
    db.refresh(budget)
    return _serialize_budget(db, budget, get_today())


@router.delete("/{budget_id}")
def delete_budget(
    budget_id: int,
    user_id: str = Depends(require_dashboard_user),
    db: Session = Depends(get_db),
):
    budget = db.query(Budget).filter(Budget.id == budget_id, Budget.user_id == user_id).first()
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    db.query(BudgetAlert).filter(BudgetAlert.budget_id == budget.id).delete()
    db.delete(budget)
    db.commit()
    return {"deleted": True, "id": budget_id}
