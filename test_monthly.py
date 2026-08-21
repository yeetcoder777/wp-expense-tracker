from app.db.database import SessionLocal
from app.services.transaction_service import get_this_month_expenses

db = SessionLocal()

try:
    user_id = "whatsapp:+918879985555"

    total = get_this_month_expenses(
        db=db,
        user_id=user_id,
    )

    print(f"This month's expenses: ₹{total:.2f}")

finally:
    db.close()
