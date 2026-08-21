from app.db.database import SessionLocal
from app.services.transaction_service import get_total_expenses


db = SessionLocal()

try:
    total = get_total_expenses(
        db=db,
        user_id="whatsapp:+918879985555",
    )

    print(f"Total expenses: ₹{total}")

finally:
    db.close()
