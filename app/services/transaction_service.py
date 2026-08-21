from sqlalchemy.orm import Session

from app.db.models import TransactionDB
from app.schemas.transaction import Transaction


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