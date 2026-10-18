import csv
import hashlib
import io
import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from app.db.models import ImportedTransaction, TransactionDB
from app.schemas.transaction import Transaction

_DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%d %b %Y", "%d-%b-%Y")
_ALIASES = {
    "date": ("date", "transaction date", "posted date", "trans date"),
    "description": ("description", "details", "narration", "merchant", "payee", "name"),
    "amount": ("amount", "transaction amount", "value"),
    "debit": ("debit", "debit amount", "withdrawal", "money out"),
    "credit": ("credit", "credit amount", "deposit", "money in"),
    "type": ("type", "transaction type", "dr/cr", "debit/credit"),
    "currency": ("currency", "ccy"),
    "category": ("category", "expense category"),
    "person": ("person", "counterparty", "merchant"),
}


def transaction_fingerprint(transaction: Transaction) -> str:
    canonical = {
        "type": transaction.transaction_type,
        "amount": str(transaction.amount.quantize(Decimal("0.01"))),
        "currency": transaction.currency.upper(),
        "date": transaction.transaction_date.isoformat() if transaction.transaction_date else "",
        "category": (transaction.category or "").strip().lower(),
        "purpose": (transaction.purpose or "").strip().lower(),
        "person": (transaction.person or "").strip().lower(),
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode("utf-8")).hexdigest()


def _normalize_header(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower().replace("_", " "))


def _column(headers: list[str], key: str) -> str | None:
    aliases = set(_ALIASES[key])
    return next((header for header in headers if _normalize_header(header) in aliases), None)


def _parse_date(value: str) -> date:
    value = value.strip()
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError("date must use YYYY-MM-DD or a common day/month/year format")


def _parse_amount(value: str) -> Decimal:
    cleaned = value.strip().replace(",", "")
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = re.sub(r"[^0-9.\-]", "", cleaned.strip("()"))
    try:
        result = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError("amount is not a valid number") from exc
    return -result if negative else result


def parse_bank_csv(content: bytes) -> tuple[list[Transaction], list[dict]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8 encoded") from exc
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV has no header row")

    headers = reader.fieldnames
    date_column = _column(headers, "date")
    description_column = _column(headers, "description")
    amount_column = _column(headers, "amount")
    debit_column = _column(headers, "debit")
    credit_column = _column(headers, "credit")
    if not date_column or not description_column or not (amount_column or debit_column or credit_column):
        raise ValueError("CSV needs date, description, and amount (or debit/credit) columns")

    type_column = _column(headers, "type")
    currency_column = _column(headers, "currency")
    category_column = _column(headers, "category")
    person_column = _column(headers, "person")
    transactions: list[Transaction] = []
    errors: list[dict] = []

    for row_number, row in enumerate(reader, start=2):
        if row_number > 2001:
            errors.append({"row": row_number, "error": "Import is limited to 2,000 rows per file"})
            break
        try:
            if debit_column and credit_column and (row.get(debit_column) or row.get(credit_column)):
                debit_value = (row.get(debit_column) or "").strip()
                credit_value = (row.get(credit_column) or "").strip()
                transaction_type = "expense" if debit_value else "income"
                raw_amount = debit_value or credit_value
                amount = abs(_parse_amount(raw_amount))
            else:
                raw_amount = (row.get(amount_column) or "").strip() if amount_column else ""
                signed_amount = _parse_amount(raw_amount)
                type_value = (row.get(type_column) or "").strip().lower() if type_column else ""
                if type_value in {"credit", "cr", "income", "deposit"}:
                    transaction_type = "income"
                elif type_value in {"debit", "dr", "expense", "withdrawal"}:
                    transaction_type = "expense"
                elif type_value:
                    raise ValueError("type must be debit/expense or credit/income")
                else:
                    transaction_type = "expense"
                amount = abs(signed_amount)

            if amount <= 0:
                raise ValueError("amount must be greater than zero")
            description = (row.get(description_column) or "").strip()
            if not description:
                raise ValueError("description is empty")
            currency = ((row.get(currency_column) or "").strip().upper() or "INR") if currency_column else "INR"
            category = ((row.get(category_column) or "").strip().lower() or "other") if category_column else "other"
            person = (row.get(person_column) or "").strip() or None if person_column else None
            transactions.append(Transaction(
                transaction_type=transaction_type,
                amount=amount,
                currency=currency,
                person=person,
                purpose=description,
                category=category,
                transaction_date=_parse_date(row.get(date_column) or ""),
            ))
        except (ValueError, InvalidOperation) as exc:
            errors.append({"row": row_number, "error": str(exc)})
    return transactions, errors


def is_possible_duplicate(
    db: Session,
    user_id: str,
    transaction: Transaction,
) -> bool:
    fingerprint = transaction_fingerprint(transaction)
    imported = db.query(ImportedTransaction.id).filter(
        ImportedTransaction.user_id == user_id,
        ImportedTransaction.fingerprint == fingerprint,
    ).first()
    if imported:
        return True

    query = db.query(TransactionDB.id).filter(
        TransactionDB.user_id == user_id,
        TransactionDB.transaction_type == transaction.transaction_type,
        TransactionDB.amount == transaction.amount,
        TransactionDB.currency == transaction.currency.upper(),
        TransactionDB.transaction_date == transaction.transaction_date,
    )
    if transaction.category:
        query = query.filter(TransactionDB.category == transaction.category)
    if transaction.purpose:
        query = query.filter(TransactionDB.purpose == transaction.purpose)
    if transaction.person:
        query = query.filter(TransactionDB.person == transaction.person)
    return query.first() is not None


def find_duplicate_rows(
    db: Session,
    user_id: str,
    transactions: list[Transaction],
) -> list[bool]:
    seen: set[str] = set()
    duplicate_flags: list[bool] = []
    for transaction in transactions:
        fingerprint = transaction_fingerprint(transaction)
        duplicate_flags.append(
            fingerprint in seen or is_possible_duplicate(db, user_id, transaction)
        )
        seen.add(fingerprint)
    return duplicate_flags


def commit_import(
    db: Session,
    user_id: str,
    transactions: list[Transaction],
    source_name: str,
    skip_possible_duplicates: bool = True,
) -> dict:
    from app.services.budget_service import evaluate_budget_alerts
    from app.services.transaction_service import save_transaction

    imported_count = 0
    duplicate_count = 0
    alerts: list[str] = []
    for transaction in transactions:
        fingerprint = transaction_fingerprint(transaction)
        already_imported = db.query(ImportedTransaction.id).filter(
            ImportedTransaction.user_id == user_id,
            ImportedTransaction.fingerprint == fingerprint,
        ).first()
        possible_duplicate = is_possible_duplicate(db, user_id, transaction)
        if skip_possible_duplicates and (already_imported or possible_duplicate):
            duplicate_count += 1
            continue

        occurrence = db.query(func.max(ImportedTransaction.occurrence)).filter(
            ImportedTransaction.user_id == user_id,
            ImportedTransaction.fingerprint == fingerprint,
        ).scalar() or 0

        try:
            with db.begin_nested():
                saved = save_transaction(db, user_id, transaction, commit=False)
                db.add(ImportedTransaction(
                    user_id=user_id,
                    fingerprint=fingerprint,
                    occurrence=occurrence + 1,
                    transaction_id=saved.id,
                    source_name=source_name[:255],
                ))
                db.flush()
            db.commit()
        except IntegrityError:
            duplicate_count += 1
            continue
        db.refresh(saved)
        imported_count += 1
        alerts.extend(evaluate_budget_alerts(db, user_id, saved))

    return {
        "imported": imported_count,
        "skipped_duplicates": duplicate_count,
        "budget_alerts": alerts,
    }
