from sqlalchemy import func

from app.db.database import SessionLocal
from app.db.models import TransactionDB


db = SessionLocal()

try:
    user_id = "whatsapp:+918879985555"

    result = (
        db.query(
            func.sum(TransactionDB.amount)
        )
        .filter(
            TransactionDB.user_id == user_id,
            TransactionDB.transaction_type == "expense",
        )
        .scalar()
    )

    print("SUM RESULT:", result)
    print("TYPE:", type(result))

finally:
    db.close()
