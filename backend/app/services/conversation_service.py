import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models import ConversationState
from app.schemas.transaction import Transaction


def get_missing_fields(transaction: Transaction) -> list[str]:
    missing = []

    if transaction.purpose is None:
        missing.append("purpose")

    return missing


def save_pending(
    db: Session,
    user_id: str,
    transaction: Transaction,
    pending_field: str,
):
    existing = (
        db.query(ConversationState)
        .filter(ConversationState.user_id == user_id)
        .first()
    )

    transaction_data = json.dumps(
        transaction.model_dump(mode="json")
    )

    if existing:
        existing.transaction_data = transaction_data
        existing.pending_field = pending_field
    else:
        state = ConversationState(
            user_id=user_id,
            transaction_data=transaction_data,
            pending_field=pending_field,
        )

        db.add(state)

    db.commit()


def get_pending(
    db: Session,
    user_id: str,
) -> tuple[Transaction, str] | None:

    state = (
        db.query(ConversationState)
        .filter(ConversationState.user_id == user_id)
        .first()
    )

    if not state:
        return None

    updated_at = state.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - updated_at > timedelta(hours=24):
        db.delete(state)
        db.commit()
        return None

    transaction = Transaction.model_validate(
        json.loads(state.transaction_data)
    )

    return transaction, state.pending_field


def clear_pending(
    db: Session,
    user_id: str,
):
    state = (
        db.query(ConversationState)
        .filter(ConversationState.user_id == user_id)
        .first()
    )

    if state:
        db.delete(state)
        db.commit()
