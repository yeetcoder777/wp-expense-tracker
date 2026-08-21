from app.db.database import SessionLocal
from app.services.transaction_service import get_transactions


db = SessionLocal()

try:
    transactions = get_transactions(
        db=db,
        user_id="whatsapp:+918879985555",
    )

    for transaction in transactions:
        print(
            transaction.id,
            transaction.amount,
            transaction.person,
            transaction.purpose,
            transaction.category,
            transaction.created_at,
        )

finally:
    db.close()
