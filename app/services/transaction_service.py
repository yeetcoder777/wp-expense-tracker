from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from datetime import date

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

    start_of_day = datetime.combine(
        datetime.now().date(),
        time.min,
    )

    result = (
        db.query(func.coalesce(func.sum(TransactionDB.amount), 0))
        .filter(
            TransactionDB.user_id == user_id,
            TransactionDB.transaction_type == "expense",
            TransactionDB.created_at >= start_of_day,
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