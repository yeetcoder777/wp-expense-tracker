"""CPU GLiNER2 extraction with source-span checks and deterministic normalization."""

import logging
import math
import re
from datetime import datetime, time
from decimal import Decimal
from threading import Lock

from app.config import settings
from app.schemas.transaction import Transaction
from app.services.date_service import get_today, IST

logger = logging.getLogger("uvicorn.error")
_load_lock = Lock()
_inference_lock = Lock()
_model = None
_model_key = None

CATEGORY_DESCRIPTIONS = {
    "food": "Coffee, meals, groceries, restaurants.",
    "transport": "Bus, train, taxi, Uber, fuel.",
    "shopping": "Purchases of clothes or electronics.",
    "bills": "Rent, electricity, internet, phone or subscriptions.",
    "entertainment": "Movies, games, leisure.",
    "health": "Doctors or medicines.",
    "education": "School, courses, books.",
    "salary": "Employment salary or wages received.",
    "freelance": "Consulting or freelance income.",
    "other": "Any transaction not described above.",
}


def load_local_model():
    """Load one reusable model; optional ML dependencies stay out of Groq-only startup."""
    global _model, _model_key
    key = (settings.gliner2_model_id, settings.gliner2_revision, settings.gliner2_num_threads)
    with _load_lock:
        if _model is None or _model_key != key:
            import torch
            from gliner2 import AutoExtractor
            from huggingface_hub import snapshot_download

            torch.set_num_threads(settings.gliner2_num_threads)
            directory = snapshot_download(
                repo_id=settings.gliner2_model_id,
                revision=settings.gliner2_revision,
                local_files_only=settings.gliner2_local_files_only,
                allow_patterns=["*.json", "encoder_config/*.json", "*.model", "*.safetensors"],
            )
            model = AutoExtractor.from_pretrained(directory, map_location="cpu")
            model.eval()
            _model, _model_key = model, key
            logger.info("Local extractor ready: provider=gliner2 model=%s device=cpu", settings.gliner2_model_id)
        return _model


def _schema(model):
    return (model.create_schema().entities({
        "amount": "The monetary amount spent or received, including currency if present.",
        "purpose": "What the payment was for, such as coffee, groceries, salary, rent, or bus fare.",
        "person": "The person or merchant paid or who sent money.",
        "date": "When the transaction occurred, including today, yesterday, or a calendar date.",
        "currency": "The currency code, name, or symbol.",
    }).classification("transaction_type", {
        "expense": "Money spent, paid, bought, or given to someone.",
        "income": "Money received or earned, such as salary or payment received.",
    }).classification("category", CATEGORY_DESCRIPTIONS))


def _entities(text, result, name):
    entities = result.get("entities", {})
    if not isinstance(entities, dict):
        raise ValueError("Invalid entity response")
    values = entities.get(name, [])
    if not isinstance(values, list):
        raise ValueError("Invalid entity response")
    accepted = []
    for entity in values:
        if not isinstance(entity, dict):
            raise ValueError("Invalid entity response")
        value = entity.get("text")
        confidence = float(entity.get("confidence", 0))
        if not isinstance(value, str) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("Invalid entity response")
        if confidence < settings.gliner2_entity_threshold:
            continue
        start, end = entity.get("start"), entity.get("end")
        if (type(start) is not int or type(end) is not int
                or not 0 <= start < end <= len(text) or text[start:end] != value):
            raise ValueError("Extracted text does not match its source span")
        accepted.append(entity)
    return sorted(accepted, key=lambda item: item["confidence"], reverse=True)


def _classification(result, name, choices):
    value = result.get(name, {})
    if not isinstance(value, dict):
        raise ValueError("Invalid classification response")
    label, confidence = value.get("label"), float(value.get("confidence", 0))
    if label not in choices or not math.isfinite(confidence) or not 0 <= confidence <= 1:
        raise ValueError("Invalid classification response")
    return label, confidence


def _normalize_amount(value):
    value = re.sub(r"(?i)\brs\.(?=\s|\d|$)", "", value)
    normalized = re.sub(r"(?i)\b(?:INR|USD|EUR|GBP|rupees?|dollars?|euros?|pounds?|rs\.?)\b", "", value)
    normalized = re.sub(r"[₹$€£,\s]", "", normalized)
    if not re.fullmatch(r"\+?\d+(?:\.\d{1,2})?", normalized):
        raise ValueError("Amount must be an explicit positive decimal")
    return Decimal(normalized)


def _date(value):
    import dateparser

    parsed = dateparser.parse(value, languages=["en"], settings={
        "RELATIVE_BASE": datetime.combine(get_today(), time(12), tzinfo=IST),
        "PREFER_DATES_FROM": "past", "DATE_ORDER": "DMY", "STRICT_PARSING": True,
    })
    if parsed is None:
        raise ValueError("Could not resolve transaction date")
    return parsed.date()


def normalize_local_result(text: str, result: dict) -> Transaction:
    """Do not silently guess among multiple amounts, currencies, or dates."""
    if not isinstance(result, dict):
        raise ValueError("Invalid extraction response")
    amounts = _entities(text, result, "amount")
    dates = _entities(text, result, "date")
    purpose = _entities(text, result, "purpose")
    person = _entities(text, result, "person")
    currencies = _entities(text, result, "currency")
    # Recover explicit date words even if the entity model misses their spans.
    for match in re.finditer(r"\b(?:today|yesterday|tomorrow|\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{4})\b", text, re.I):
        if not any(item["start"] <= match.start() and item["end"] >= match.end() for item in dates):
            dates.append({"text": match.group(), "start": match.start(), "end": match.end()})
    normalized_amounts = {_normalize_amount(item["text"]) for item in amounts}
    if len(normalized_amounts) != 1:
        raise ValueError("Expected one monetary amount per line")

    # Identify extra bare amounts that the model might have missed. Dates are masked.
    masked = list(text)
    for entity in dates:
        _date(entity["text"])
        masked[entity["start"]:entity["end"]] = " " * (entity["end"] - entity["start"])
    number_text = "".join(masked)
    numbers = list(re.finditer(r"(?<![\w.])\d[\d,]*(?:\.\d+)?(?![\w.])", number_text))
    if len(numbers) != 1:
        raise ValueError("Ambiguous numeric values; use one clear transaction per line")
    amount = normalized_amounts.pop()
    if _normalize_amount(numbers[0].group()) != amount:
        raise ValueError("Extracted amount does not match the message")
    if re.search(r"(?:[-−]\s*\d|\d\s*(?:k|lakh|lakhs|crore|crores|thousand|million)\b)", number_text, re.I):
        raise ValueError("Negative and abbreviated amounts need explicit positive values")

    code_map = {"₹": "INR", "$": "USD", "€": "EUR", "£": "GBP", "rs": "INR", "rupee": "INR", "rupees": "INR",
                "dollar": "USD", "dollars": "USD", "euro": "EUR", "euros": "EUR", "pound": "GBP", "pounds": "GBP"}
    currency_codes = set()
    for code in re.findall(r"\b([A-Z]{3})\s*(?=\d)|(?<=\d)\s*([A-Z]{3})\b", text):
        explicit_code = next(part for part in code if part)
        if explicit_code not in {"INR", "USD", "EUR", "GBP"}:
            raise ValueError("Unsupported explicit currency")
    for token in re.findall(r"[₹$€£]|\b(?:INR|USD|EUR|GBP|rs|rupees?|dollars?|euros?|pounds?)\b", text, re.I):
        currency_codes.add(code_map.get(token.lower(), token.upper()))
    for entity in currencies:
        token = entity["text"].strip().lower().rstrip(".")
        if token in code_map or token.upper() in {"INR", "USD", "EUR", "GBP"}:
            currency_codes.add(code_map.get(token, token.upper()))
        else:
            raise ValueError("Unsupported explicit currency")
    if len(currency_codes) > 1:
        raise ValueError("Multiple currencies in one line")
    day_values = {_date(item["text"]) for item in dates}
    if len(day_values) > 1:
        raise ValueError("Multiple dates in one transaction")
    kind, kind_confidence = _classification(result, "transaction_type", {"expense", "income"})
    if kind_confidence < settings.gliner2_classification_threshold:
        raise ValueError("Uncertain income versus expense")
    category, category_confidence = _classification(result, "category", CATEGORY_DESCRIPTIONS)
    if category_confidence < settings.gliner2_classification_threshold:
        category = "other"
    if (kind == "income" and category not in {"salary", "freelance", "other"}) or (kind == "expense" and category in {"salary", "freelance"}):
        category = "other"
    purpose_text = purpose[0]["text"].strip() if purpose else None
    if purpose_text and re.fullmatch(r"(?:spent|paid|received|earned|payment|money)", purpose_text, re.I):
        purpose_text = None
    person_text = person[0]["text"].strip() if person else None
    if person_text and person_text.lower() in {"i", "me", "my", "myself", "we", "us", "our", "you"}:
        person_text = None
    return Transaction(
        transaction_type=kind, amount=amount, currency=next(iter(currency_codes), "INR"),
        purpose=purpose_text, person=person_text,
        category=category, transaction_date=next(iter(day_values), get_today()),
    )


def extract_local_transactions(message: str) -> list[Transaction]:
    import torch

    segments = [item.strip() for item in re.split(r"[\r\n;]+", message) if item.strip()]
    if not segments or len(segments) > 20 or any(len(item) > 500 for item in segments):
        raise ValueError("Use up to 20 short transaction lines")
    model = load_local_model()
    with _inference_lock, torch.inference_mode():
        schema = _schema(model)
        transactions = []
        for text in segments:
            result = model.extract(text, schema, threshold=settings.gliner2_entity_threshold,
                                   include_confidence=True, include_spans=True)
            transactions.append(normalize_local_result(text, result))
        return transactions
