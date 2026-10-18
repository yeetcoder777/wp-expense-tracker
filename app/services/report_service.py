from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import TransactionDB


def get_report(
    db: Session,
    user_id: str,
    start_date: date,
    end_date: date,
    currency: str = "INR",
) -> dict:
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date")

    def total(transaction_type: str) -> Decimal:
        value = db.query(
            func.coalesce(func.sum(TransactionDB.amount), 0)
        ).filter(
            TransactionDB.user_id == user_id,
            TransactionDB.currency == currency,
            TransactionDB.transaction_type == transaction_type,
            TransactionDB.transaction_date >= start_date,
            TransactionDB.transaction_date <= end_date,
        ).scalar()
        return value if isinstance(value, Decimal) else Decimal(str(value))

    expenses = total("expense")
    income = total("income")
    categories = db.query(
        TransactionDB.category,
        func.sum(TransactionDB.amount).label("amount"),
    ).filter(
        TransactionDB.user_id == user_id,
        TransactionDB.currency == currency,
        TransactionDB.transaction_type == "expense",
        TransactionDB.transaction_date >= start_date,
        TransactionDB.transaction_date <= end_date,
    ).group_by(TransactionDB.category).order_by(func.sum(TransactionDB.amount).desc()).all()

    largest = db.query(TransactionDB).filter(
        TransactionDB.user_id == user_id,
        TransactionDB.currency == currency,
        TransactionDB.transaction_type == "expense",
        TransactionDB.transaction_date >= start_date,
        TransactionDB.transaction_date <= end_date,
    ).order_by(TransactionDB.amount.desc()).limit(5).all()

    net = income - expenses
    savings_rate = (net / income * 100) if income else Decimal("0")
    return {
        "start_date": start_date,
        "end_date": end_date,
        "currency": currency,
        "income": income,
        "expenses": expenses,
        "net": net,
        "savings_rate": savings_rate.quantize(Decimal("0.01")),
        "categories": [
            {"category": category or "other", "amount": amount}
            for category, amount in categories
        ],
        "largest_expenses": [
            {
                "id": item.id,
                "transaction_type": item.transaction_type,
                "amount": item.amount,
                "currency": item.currency,
                "person": item.person,
                "purpose": item.purpose,
                "category": item.category,
                "transaction_date": item.transaction_date,
            }
            for item in largest
        ],
    }


def compare_months(
    db: Session,
    user_id: str,
    year: int,
    month: int,
    currency: str = "INR",
) -> dict:
    start = date(year, month, 1)
    if month == 1:
        previous_year, previous_month = year - 1, 12
    else:
        previous_year, previous_month = year, month - 1
    previous_start = date(previous_year, previous_month, 1)
    previous_end = date(previous_year, previous_month + 1, 1) - timedelta(days=1) if previous_month < 12 else date(previous_year, 12, 31)
    current_end = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)

    current = get_report(db, user_id, start, current_end, currency)
    previous = get_report(db, user_id, previous_start, previous_end, currency)
    change = current["expenses"] - previous["expenses"]
    change_percent = change / previous["expenses"] * 100 if previous["expenses"] else None
    return {
        "current": current,
        "previous": previous,
        "expense_change": change,
        "expense_change_percent": change_percent,
    }
