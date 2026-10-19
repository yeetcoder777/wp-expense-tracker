import re
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.db.models import TransactionDB
from app.services.conversation_service import clear_pending, get_pending
from app.services.budget_service import evaluate_budget_alerts
from app.services.transaction_service import delete_user_transaction, get_user_transaction

_EDIT_PATTERN = re.compile(
    r"^(?:edit|change|update)\s+(?:transaction\s+)?(?P<target>last|#?\d+)\s+"
    r"(?P<field>amount|date|category|purpose)\s+(?:to\s+)?(?P<value>.+)$",
    re.IGNORECASE,
)
_DELETE_PATTERN = re.compile(
    r"^(?:delete|remove)\s+(?:transaction\s+)?(?P<target>last|#?\d+)$",
    re.IGNORECASE,
)


def handle_transaction_command(db: Session, user_id: str, message: str) -> str | None:
    text = message.strip()
    normalized = text.lower().strip(" .!")

    if normalized in {"cancel", "cancel transaction", "discard", "stop", "never mind"}:
        had_pending = get_pending(db, user_id) is not None
        clear_pending(db, user_id)
        return "Cancelled the pending transaction." if had_pending else "There is no pending transaction to cancel."

    if normalized in {"undo", "undo last", "undo last transaction"}:
        removed = delete_user_transaction(db, user_id)
        if removed is None:
            return "There is no transaction to undo."
        return f"Undid transaction #{removed['id']} ({removed['currency']} {removed['amount']:.2f})."

    deletion = _DELETE_PATTERN.match(text)
    if deletion:
        target = deletion.group("target").lstrip("#").lower()
        removed = delete_user_transaction(
            db,
            user_id,
            None if target == "last" else int(target),
        )
        if removed is None:
            return "I couldn't find that transaction. Try 'recent transactions' to see IDs."
        return f"Deleted transaction #{removed['id']}."

    edit = _EDIT_PATTERN.match(text)
    if edit:
        target = edit.group("target").lstrip("#").lower()
        transaction = (
            db.query(TransactionDB)
            .filter_by(user_id=user_id)
            .order_by(TransactionDB.created_at.desc())
            .first()
            if target == "last"
            else get_user_transaction(db, user_id, int(target))
        )
        if transaction is None:
            return "I couldn't find that transaction. Try 'recent transactions' to see IDs."

        value = edit.group("value").strip()
        field = edit.group("field").lower()
        try:
            if field == "amount":
                amount = Decimal(value.replace("₹", "").replace(",", "").strip())
                if amount <= 0 or amount > Decimal("9999999999.99") or amount.as_tuple().exponent < -2:
                    raise ValueError("amount must be positive with at most two decimal places")
                transaction.amount = amount
            elif field == "date":
                transaction.transaction_date = date.fromisoformat(value)
            elif field == "category":
                if len(value) > 100:
                    raise ValueError("category is too long")
                transaction.category = value.lower()
            else:
                if len(value) > 500:
                    raise ValueError("purpose is too long")
                transaction.purpose = value
        except (InvalidOperation, ValueError) as exc:
            return f"That {field} value is invalid. Use YYYY-MM-DD for dates and a positive amount."

        db.commit()
        alerts = evaluate_budget_alerts(db, user_id, transaction)
        reply = f"Updated transaction #{transaction.id}: {field} is now {value}."
        return reply + ("\n" + "\n".join(alerts) if alerts else "")

    if normalized.startswith(("edit ", "change ", "update ")):
        return (
            "Use 'edit <id> amount to 500', 'edit <id> date to 2026-10-11', "
            "or 'edit <id> category to food'. You can also use 'last' instead of an ID."
        )
    if normalized.startswith(("delete ", "remove ")):
        return "Use 'delete <id>' or 'delete last'."
    return None
