from app.db.database import SessionLocal
from app.schemas.transaction import Transaction
from app.services.transaction_service import save_transaction


db = SessionLocal()

try:
    transaction = Transaction(
        transaction_type="expense",
        amount=50,
        currency="INR",
        person="Siddhesh",
        purpose="Lunch",
    )

    saved = save_transaction(
        db=db,
        user_id="whatsapp:+918879985555",
        transaction=transaction,
    )

    print("Transaction saved successfully!")
    print("ID:", saved.id)

finally:
    db.close()