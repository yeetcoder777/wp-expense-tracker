from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Budget, BudgetAlert, TransactionDB
from app.services.date_service import get_today


def monthly_bounds(day: date) -> tuple[date, date]:
    start = day.replace(day=1)
    if day.month == 12:
        next_month = date(day.year + 1, 1, 1)
    else:
        next_month = date(day.year, day.month + 1, 1)
    return start, date.fromordinal(next_month.toordinal() - 1)


def evaluate_budget_alerts(
    db: Session,
    user_id: str,
    transaction: TransactionDB,
) -> list[str]:
    if transaction.transaction_type != "expense" or transaction.transaction_date is None:
        return []

    period_start, period_end = monthly_bounds(transaction.transaction_date)
    current_period_start, _ = monthly_bounds(get_today())
    if period_start != current_period_start:
        return []
    budgets = (
        db.query(Budget)
        .filter(
            Budget.user_id == user_id,
            Budget.currency == transaction.currency,
            or_(Budget.category == "all", Budget.category == transaction.category),
        )
        .all()
    )

    messages: list[str] = []
    for budget in budgets:
        spent = db.query(
            func.coalesce(func.sum(TransactionDB.amount), 0)
        ).filter(
            TransactionDB.user_id == user_id,
            TransactionDB.transaction_type == "expense",
            TransactionDB.currency == budget.currency,
            TransactionDB.transaction_date >= period_start,
            TransactionDB.transaction_date <= period_end,
        )
        if budget.category != "all":
            spent = spent.filter(TransactionDB.category == budget.category)
        total = spent.scalar()
        total = total if isinstance(total, Decimal) else Decimal(str(total))
        ratio = total / budget.amount if budget.amount else Decimal("0")

        for threshold in (80, 100):
            if ratio * 100 < threshold:
                continue
            already_sent = db.query(BudgetAlert.id).filter(
                BudgetAlert.budget_id == budget.id,
                BudgetAlert.period_start == period_start,
                BudgetAlert.threshold == threshold,
            ).first()
            if already_sent:
                continue

            try:
                with db.begin_nested():
                    db.add(BudgetAlert(
                        budget_id=budget.id,
                        period_start=period_start,
                        threshold=threshold,
                    ))
                    db.flush()
            except IntegrityError:
                continue
            label = "overall spending" if budget.category == "all" else budget.category
            messages.append(
                f"{label.capitalize()} budget: {threshold}% reached "
                f"({transaction.currency} {total:.2f} of {budget.amount:.2f})."
            )

    if messages:
        db.commit()
    return messages
