from app.db.database import SessionLocal
from app.db.models import TransactionDB


db = SessionLocal()

try:
    transactions = db.query(TransactionDB).all()

    print(f"Total rows: {len(transactions)}")
    print()

    for t in transactions:
        print(
            f"id={t.id} | "
            f"user_id={t.user_id} | "
            f"type={t.transaction_type} | "
            f"amount={t.amount} | "
            f"person={t.person} | "
            f"purpose={t.purpose}"
        )

finally:
    db.close()
