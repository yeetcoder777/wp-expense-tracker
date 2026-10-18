import re
from decimal import Decimal, InvalidOperation

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Budget, BudgetAlert, TransactionDB
from app.services.budget_service import monthly_bounds
from app.services.date_service import get_today

_AMOUNT = re.compile(r"(?P<symbol>₹|\$|€|£)?\s*(?P<amount>[\d,]+(?:\.\d{1,2})?)\s*(?P<currency>[A-Za-z]{3})?\s*$")
_SET_BUDGET = re.compile(
    r"^(?:set|create|update)\s+(?:a\s+)?(?:my\s+)?(?P<subject>.+?)\s+budget\s+(?:to|at|of)\s+(?P<value>.+)$",
    re.IGNORECASE,
)
_SIMPLE_BUDGET = re.compile(
    r"^(?:set|create|update)\s+(?:my\s+)?budget\s+(?:to|at|of)\s+(?P<value>.+)$",
    re.IGNORECASE,
)
_BUDGET_CATEGORIES = {
    "food", "transport", "shopping", "bills", "entertainment",
    "health", "education", "other", "overall", "all",
}


def _amount(value: str) -> tuple[Decimal, str] | None:
    match = _AMOUNT.match(value.strip())
    if not match:
        return None
    try:
        amount = Decimal(match.group("amount").replace(",", ""))
    except InvalidOperation:
        return None
    currency = match.group("currency") or {
        "₹": "INR", "$": "USD", "€": "EUR", "£": "GBP",
    }.get(match.group("symbol"), "INR")
    return amount, currency.upper()


def _spent(db: Session, user_id: str, category: str, currency: str) -> Decimal:
    start, end = monthly_bounds(get_today())
    query = db.query(func.coalesce(func.sum(TransactionDB.amount), 0)).filter(
        TransactionDB.user_id == user_id,
        TransactionDB.transaction_type == "expense",
        TransactionDB.currency == currency,
        TransactionDB.transaction_date >= start,
        TransactionDB.transaction_date <= end,
    )
    if category != "all":
        query = query.filter(TransactionDB.category == category)
    value = query.scalar()
    return value if isinstance(value, Decimal) else Decimal(str(value))


def handle_budget_command(db: Session, user_id: str, message: str) -> str | None:
    text = message.strip().rstrip("?.!")
    normalized = text.lower()

    if normalized in {"my budgets", "show my budgets", "list budgets"}:
        budgets = db.query(Budget).filter(Budget.user_id == user_id).order_by(Budget.category).all()
        if not budgets:
            return "You don't have any budgets yet. Try 'Set my food budget to ₹8,000'."
        lines = ["Monthly budgets:"]
        for budget in budgets:
            spent = _spent(db, user_id, budget.category, budget.currency)
            lines.append(
                f"{budget.category.capitalize()}: {budget.currency} {spent:.2f} "
                f"of {budget.amount:.2f}"
            )
        return "\n".join(lines)

    set_match = _SET_BUDGET.match(text)
    simple_match = _SIMPLE_BUDGET.match(text)
    if set_match or simple_match:
        subject = set_match.group("subject").lower().strip() if set_match else "all"
        value = set_match.group("value") if set_match else simple_match.group("value")
        subject = re.sub(r"^(?:for\s+)?(?:my\s+)?", "", subject)
        subject = re.sub(r"^(?:monthly\s+)?", "", subject)
        if subject.startswith("budget for "):
            subject = subject[len("budget for "):]
        category = "all" if subject in {"all", "overall", "total", "monthly"} else subject
        parsed = _amount(value)
        if category not in _BUDGET_CATEGORIES and category not in {"all"}:
            return "Tell me a category, for example 'Set my food budget to ₹8,000'."
        if parsed is None or parsed[0] <= 0:
            return "Enter a positive budget amount, such as 'Set my food budget to ₹8,000'."
        amount, currency = parsed
        existing = db.query(Budget).filter(
            Budget.user_id == user_id,
            Budget.category == ("all" if category in {"overall", "all"} else category),
            Budget.currency == currency,
        ).first()
        if existing:
            db.query(BudgetAlert).filter(BudgetAlert.budget_id == existing.id).delete()
            existing.amount = amount
        else:
            db.add(Budget(
                user_id=user_id,
                category="all" if category in {"overall", "all"} else category,
                amount=amount,
                currency=currency,
            ))
        db.commit()
        label = "overall" if category in {"overall", "all"} else category
        return f"Monthly {label} budget set to {currency} {amount:.2f}."

    remaining_match = re.search(r"(?:left|remaining)\s+in\s+(?:my\s+)?(?P<category>[a-z ]+?)\s+budget", normalized)
    if remaining_match:
        category = remaining_match.group("category").strip()
        budget = db.query(Budget).filter(
            Budget.user_id == user_id,
            Budget.category == category,
        ).first()
        if not budget:
            return f"I couldn't find a {category} budget."
        spent = _spent(db, user_id, category, budget.currency)
        remaining = budget.amount - spent
        if remaining < 0:
            return f"Your {category} budget is over by {budget.currency} {abs(remaining):.2f}."
        return f"You have {budget.currency} {remaining:.2f} left in your {category} budget this month."

    if "budget" in normalized and any(word in normalized for word in ("set", "create", "update")):
        return "Try 'Set my food budget to ₹8,000' or 'Set my overall budget to ₹20,000'."
    return None
