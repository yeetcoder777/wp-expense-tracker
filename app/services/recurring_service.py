import asyncio
import logging
from calendar import monthrange
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import RecurringExecution, RecurringPayment
from app.schemas.transaction import Transaction
from app.services.budget_service import evaluate_budget_alerts
from app.services.notification_service import send_whatsapp_message
from app.services.date_service import get_today
from app.services.transaction_service import save_transaction

logger = logging.getLogger(__name__)


def advance_date(
    day: date,
    interval: str,
    anchor_day: int | None = None,
    anchor_month: int | None = None,
) -> date:
    if interval == "weekly":
        return day + timedelta(days=7)
    if interval == "monthly":
        year = day.year + (day.month == 12)
        month = 1 if day.month == 12 else day.month + 1
        requested_day = anchor_day or day.day
        return date(year, month, min(requested_day, monthrange(year, month)[1]))
    if interval == "yearly":
        month = anchor_month or day.month
        requested_day = anchor_day or day.day
        try:
            return date(day.year + 1, month, requested_day)
        except ValueError:
            return date(day.year + 1, month, monthrange(day.year + 1, month)[1])
    raise ValueError(f"Unsupported recurring interval: {interval}")


def process_recurring_payments(
    db: Session,
    today: date,
) -> None:
    schedules = db.query(RecurringPayment).filter(RecurringPayment.is_active.is_(True)).all()
    for schedule_id in [item.id for item in schedules]:
        schedule = db.query(RecurringPayment).filter(
            RecurringPayment.id == schedule_id,
            RecurringPayment.is_active.is_(True),
        ).with_for_update(skip_locked=True).first()
        if schedule is None:
            continue
        due_date = schedule.next_run_date
        reminder_date = due_date - timedelta(days=schedule.reminder_days)

        if today < reminder_date:
            db.rollback()
            continue

        if today < due_date:
            if schedule.last_reminded_for == due_date:
                db.rollback()
                continue
            message = (
                f"Reminder: {schedule.name} ({schedule.currency} "
                f"{schedule.amount:.2f}) is due on {due_date.isoformat()}."
            )
            if send_whatsapp_message(schedule.user_id, message):
                schedule.last_reminded_for = due_date
                db.commit()
            else:
                db.rollback()
            continue

        if not schedule.auto_record:
            if schedule.last_reminded_for != due_date:
                message = (
                    f"{schedule.name} ({schedule.currency} {schedule.amount:.2f}) "
                    f"is due today. Reply when you have paid it."
                )
                if not send_whatsapp_message(schedule.user_id, message):
                    db.rollback()
                    continue
                schedule.last_reminded_for = due_date

        execution = db.query(RecurringExecution).filter(
            RecurringExecution.recurring_payment_id == schedule.id,
            RecurringExecution.scheduled_date == due_date,
        ).first()
        if execution is None:
            transaction_id = None
            if schedule.auto_record:
                transaction = Transaction(
                    transaction_type=schedule.transaction_type,
                    amount=schedule.amount,
                    currency=schedule.currency,
                    person=schedule.person,
                    purpose=schedule.purpose or schedule.name,
                    category=schedule.category,
                    transaction_date=due_date,
                )
                saved = save_transaction(
                    db,
                    schedule.user_id,
                    transaction,
                    commit=False,
                )
                transaction_id = saved.id
            db.add(RecurringExecution(
                recurring_payment_id=schedule.id,
                scheduled_date=due_date,
                transaction_id=transaction_id,
            ))

        next_date = advance_date(
            due_date,
            schedule.interval,
            schedule.anchor_day,
            schedule.anchor_month,
        )
        while next_date <= today:
            next_date = advance_date(
                next_date,
                schedule.interval,
                schedule.anchor_day,
                schedule.anchor_month,
            )
        schedule.next_run_date = next_date
        schedule.last_reminded_for = None
        db.commit()

        if schedule.auto_record:
            try:
                added = db.query(RecurringExecution).filter(
                    RecurringExecution.recurring_payment_id == schedule.id,
                    RecurringExecution.scheduled_date == due_date,
                ).first()
                if added and added.transaction_id:
                    from app.db.models import TransactionDB

                    saved_transaction = db.query(TransactionDB).filter(
                        TransactionDB.id == added.transaction_id
                    ).first()
                    if saved_transaction:
                        alerts = evaluate_budget_alerts(db, schedule.user_id, saved_transaction)
                        if alerts:
                            send_whatsapp_message(schedule.user_id, "\n".join(alerts))
            except Exception:
                logger.exception("Could not evaluate recurring transaction budget alerts")
            send_whatsapp_message(
                schedule.user_id,
                f"Recorded recurring {schedule.transaction_type}: "
                f"{schedule.currency} {schedule.amount:.2f} for {schedule.name}.",
            )


def process_recurring_payments_once(today: date | None = None) -> None:
    db = SessionLocal()
    try:
        process_recurring_payments(db, today or get_today())
    finally:
        db.close()


async def recurring_worker() -> None:
    while True:
        try:
            await asyncio.to_thread(process_recurring_payments_once)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Recurring payment worker failed")
        await asyncio.sleep(60)
