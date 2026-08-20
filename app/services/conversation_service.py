from app.schemas.transaction import Transaction


pending_transactions: dict[str, Transaction] = {}


def get_missing_fields(transaction: Transaction) -> list[str]:
    missing = []

    if transaction.purpose is None:
        missing.append("purpose")

    return missing


def save_pending(user_id: str, transaction: Transaction):
    pending_transactions[user_id] = transaction


def get_pending(user_id: str) -> Transaction | None:
    return pending_transactions.get(user_id)


def clear_pending(user_id: str):
    pending_transactions.pop(user_id, None)