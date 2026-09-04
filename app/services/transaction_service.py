from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from datetime import date, datetime, time

from app.db.models import TransactionDB
from app.schemas.transaction import Transaction

IST = ZoneInfo("Asia/Kolkata")

def save_transaction(
    db: Session,
    user_id: str,
    transaction: Transaction,
) -> TransactionDB:

    db_transaction = TransactionDB(
        user_id=user_id,
        transaction_type=transaction.transaction_type,
        amount=transaction.amount,
        currency=transaction.currency,
        person=transaction.person,
        purpose=transaction.purpose,
        category=transaction.category,
        transaction_date=transaction.transaction_date,
    )

    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)

    return db_transaction


def get_transactions(
    db: Session,
    user_id: str,
    limit: int = 10,
) -> list[TransactionDB]:

    return (
        db.query(TransactionDB)
        .filter(TransactionDB.user_id == user_id)
        .order_by(TransactionDB.created_at.desc())
        .limit(limit)
        .all()
    )
    
def get_total_expenses(
    db: Session,
    user_id: str,
) -> Decimal:

    result = (
        db.query(func.coalesce(func.sum(TransactionDB.amount), 0))
        .filter(
            TransactionDB.user_id == user_id,
            TransactionDB.transaction_type == "expense",
        )
        .scalar()
    )

    return Decimal(result)

def get_today_expenses(
    db: Session,
    user_id: str,
) -> Decimal:
    today = datetime.now(IST).date()

    result = (
        db.query(func.coalesce(func.sum(TransactionDB.amount), 0))
        .filter(
            TransactionDB.user_id == user_id,
            TransactionDB.transaction_type == "expense",
            TransactionDB.transaction_date == today,
        )
        .scalar()
    )

    return (
        result
        if isinstance(result, Decimal)
        else Decimal(str(result))
    )
    
def get_this_month_expenses(
    db: Session,
    user_id: str,
) -> Decimal:

    now_ist = datetime.now(IST)

    start_of_month = now_ist.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    result = (
        db.query(func.coalesce(func.sum(TransactionDB.amount), 0))
        .filter(
            TransactionDB.user_id == user_id,
            TransactionDB.transaction_type == "expense",
            TransactionDB.created_at >= start_of_month,
        )
        .scalar()
    )

    return (
        result
        if isinstance(result, Decimal)
        else Decimal(str(result))
    )

def get_transactions_by_date(
    db: Session,
    user_id: str,
    transaction_date: date,
    limit: int = 20,
) -> list[TransactionDB]:
    return (
        db.query(TransactionDB)
        .filter(
            TransactionDB.user_id == user_id,
            TransactionDB.transaction_type == "expense",
            TransactionDB.transaction_date == transaction_date,
        )
        .order_by(TransactionDB.created_at.desc())
        .limit(limit)
        .all()
    )
    
def get_expenses_between(
    db: Session,
    user_id: str,
    start_date: date,
    end_date: date,
) -> list[TransactionDB]:

    return (
        db.query(TransactionDB)
        .filter(
            TransactionDB.user_id == user_id,
            TransactionDB.transaction_type == "expense",
            TransactionDB.transaction_date >= start_date,
            TransactionDB.transaction_date <= end_date,
        )
        .order_by(TransactionDB.transaction_date.desc())
        .all()
    )
    
def get_total_income(
    db: Session,
    user_id: str,
) -> Decimal:

    result = (
        db.query(func.coalesce(func.sum(TransactionDB.amount), 0))
        .filter(
            TransactionDB.user_id == user_id,
            TransactionDB.transaction_type == "income",
        )
        .scalar()
    )

    return Decimal(result)

def get_today_income(db, user_id):
    today = datetime.now(IST).date()

    result = (
        db.query(
            func.coalesce(
                func.sum(TransactionDB.amount),
                0
            )
        )
        .filter(
            TransactionDB.user_id == user_id,
            TransactionDB.transaction_type == "income",
            TransactionDB.transaction_date == today,
        )
        .scalar()
    )

    return (
        result
        if isinstance(result, Decimal)
        else Decimal(str(result))
    )


def get_income_between(
    db,
    user_id,
    start_date,
    end_date,
):
    return (
        db.query(TransactionDB)
        .filter(
            TransactionDB.user_id == user_id,
            TransactionDB.transaction_type == "income",
            TransactionDB.transaction_date >= start_date,
            TransactionDB.transaction_date <= end_date,
        )
        .order_by(TransactionDB.transaction_date.desc())
        .all()
    )
    
def get_category_expenses(db, user_id, category):
    result = (
        db.query(func.coalesce(func.sum(TransactionDB.amount), 0))
        .filter(
            TransactionDB.user_id == user_id,
            TransactionDB.transaction_type == "expense",
            TransactionDB.category == category,
        )
        .scalar()
    )

    return result if isinstance(result, Decimal) else Decimal(str(result))

def get_category_expenses_between(
    db,
    user_id,
    category,
    start_date,
    end_date,
):
    result = (
        db.query(func.coalesce(func.sum(TransactionDB.amount), 0))
        .filter(
            TransactionDB.user_id == user_id,
            TransactionDB.transaction_type == "expense",
            TransactionDB.category == category,
            TransactionDB.transaction_date >= start_date,
            TransactionDB.transaction_date <= end_date,
        )
        .scalar()
    )

    return result if isinstance(result, Decimal) else Decimal(str(result))

def get_category_transactions(
    db,
    user_id,
    category,
    start_date=None,
    end_date=None,
):
    query = (
        db.query(TransactionDB)
        .filter(
            TransactionDB.user_id == user_id,
            TransactionDB.transaction_type == "expense",
            TransactionDB.category == category,
        )
    )

    if start_date is not None:
        query = query.filter(TransactionDB.transaction_date >= start_date)

    if end_date is not None:
        query = query.filter(TransactionDB.transaction_date <= end_date)

    return query.order_by(
        TransactionDB.transaction_date.desc(),
        TransactionDB.created_at.desc(),
    ).all()
    
def get_monthly_summary(db, user_id, start_date, end_date):
    expense_transactions = get_expenses_between(
        db=db,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
    )

    income_transactions = get_income_between(
        db=db,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
    )

    expenses = sum(
        transaction.amount
        for transaction in expense_transactions
    )

    income = sum(
        transaction.amount
        for transaction in income_transactions
    )

    category_rows = (
        db.query(
            TransactionDB.category,
            func.coalesce(func.sum(TransactionDB.amount), 0),
        )
        .filter(
            TransactionDB.user_id == user_id,
            TransactionDB.transaction_type == "expense",
            TransactionDB.transaction_date >= start_date,
            TransactionDB.transaction_date <= end_date,
        )
        .group_by(TransactionDB.category)
        .order_by(
            func.sum(TransactionDB.amount).desc()
        )
        .all()
    )

    categories = [
        {
            "category": category or "other",
            "amount": (
                amount
                if isinstance(amount, Decimal)
                else Decimal(str(amount))
            ),
        }
        for category, amount in category_rows
    ]

    return {
        "expenses": expenses,
        "income": income,
        "balance": income - expenses,
        "categories": categories,
    }