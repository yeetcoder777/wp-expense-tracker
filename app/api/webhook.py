import logging
import re
from collections.abc import Sequence

from fastapi import APIRouter, Form, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

from app.config import settings
from app.db.database import SessionLocal
from app.db.models import ProcessedWebhook, TransactionDB
from app.schemas.transaction import Transaction
from app.services.llm_service import detect_intent, extract_transactions, extract_category_query, extract_category_list_query
from app.services.transaction_service import save_transaction
from app.services.conversation_service import get_missing_fields, get_pending, save_pending, clear_pending
from app.services.transaction_command_service import handle_transaction_command
from app.services.budget_command_service import handle_budget_command
from app.services.budget_service import evaluate_budget_alerts
from app.services.whatsapp_query_service import query_reply
from app.services.transaction_extraction_service import ExtractionUnavailable

router = APIRouter()
logger = logging.getLogger("uvicorn.error")


def xml_reply(message: str) -> Response:
    response = MessagingResponse()
    response.message(message)
    return Response(content=str(response), media_type="application/xml")


def validate_twilio_request(request: Request, form_data) -> None:
    if not settings.twilio_auth_token:
        if settings.environment.lower() == "production":
            raise HTTPException(status_code=503, detail="Twilio signature validation is not configured")
        return
    validator = RequestValidator(settings.twilio_auth_token)
    callback = settings.twilio_webhook_url or str(request.url)
    if not validator.validate(callback, form_data, request.headers.get("X-Twilio-Signature", "")):
        raise HTTPException(status_code=403, detail="Invalid Twilio request signature")


def already_processed(db: Session, message_sid: str | None) -> bool:
    return bool(message_sid and db.get(ProcessedWebhook, message_sid))


def claim_processed_webhook(db: Session, user_id: str, message_sid: str | None) -> bool:
    if not message_sid:
        return True
    try:
        db.add(ProcessedWebhook(message_sid=message_sid, user_id=user_id))
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        if already_processed(db, message_sid):
            return False
        raise


def save_webhook_transactions(
    db: Session, user_id: str, transactions: Sequence[Transaction], message_sid: str | None,
) -> tuple[list[TransactionDB], bool]:
    if already_processed(db, message_sid):
        return [], True
    try:
        if message_sid:
            db.add(ProcessedWebhook(message_sid=message_sid, user_id=user_id))
        saved = [save_transaction(db, user_id, item, commit=False) for item in transactions]
        db.commit()
        for item in saved:
            db.refresh(item)
        return saved, False
    except IntegrityError:
        db.rollback()
        if already_processed(db, message_sid):
            return [], True
        raise


def record_reply(db, user_id, transactions, message_sid):
    saved, duplicate = save_webhook_transactions(db, user_id, transactions, message_sid)
    if duplicate:
        return "That transaction was already recorded."
    lines = ["Recorded transactions:"] if len(saved) > 1 else []
    for item in saved:
        action = "received" if item.transaction_type == "income" else "spent"
        detail = f" for {item.purpose}" if item.purpose else ""
        lines.append(f"Recorded {item.currency} {item.amount:.2f} {action}{detail}. #{item.id}")
    for item in saved:
        lines.extend(evaluate_budget_alerts(db, user_id, item))
    logger.info("Saved %s transaction(s) for webhook %s", len(saved), message_sid)
    return "\n".join(lines)


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    Body: str = Form(...),
    From: str = Form(...),
    MessageSid: str | None = Form(default=None),
    MediaUrl0: str | None = Form(default=None),
    MediaContentType0: str | None = Form(default=None),
):
    validate_twilio_request(request, await request.form())
    db = SessionLocal()
    try:
        if already_processed(db, MessageSid):
            return xml_reply("That message was already processed.")
        if MediaUrl0:
            return xml_reply("To review and import receipt images or bank CSV files, open the tracker dashboard and choose Imports.")

        changes_state = bool(re.match(
            r"^(?:undo(?:\s+last(?:\s+transaction)?)?|"
            r"(?:delete|remove)\s+(?:transaction\s+)?(?:#?\d+|last)|"
            r"(?:edit|change|update)\s+(?:transaction\s+)?(?:#?\d+|last)\s+"
            r"(?:amount|date|category|purpose)\b|"
            r"(?:set|create|update)\s+.+\bbudget\b)", Body.strip().lower(),
        ))
        if changes_state and not claim_processed_webhook(db, From, MessageSid):
            return xml_reply("That message was already processed.")
        for handler in (handle_transaction_command, handle_budget_command):
            reply = handler(db, From, Body)
            if reply is not None:
                return xml_reply(reply)

        pending_data = get_pending(db, From)
        if pending_data:
            pending, field = pending_data
            pending = Transaction.model_validate({**pending.model_dump(), field: Body.strip()})
            missing = get_missing_fields(pending)
            if missing:
                save_pending(db, From, pending, missing[0])
                return xml_reply("What was the purpose?")
            reply = record_reply(db, From, [pending], MessageSid)
            clear_pending(db, From)
            return xml_reply(reply)

        intent = await run_in_threadpool(detect_intent, Body)
        logger.info("Detected intent: %s", intent)
        category = None
        if intent == "category_query":
            category = extract_category_query(Body)
        elif intent == "category_list_query":
            category = extract_category_list_query(Body)
        reply = query_reply(db, From, intent, category)
        if reply is not None:
            return xml_reply(reply)
        if intent != "transaction":
            return xml_reply("I can record expenses and show your spending. Try 'Paid ₹500 for lunch', 'show my budgets', or 'undo last'.")

        transactions = await run_in_threadpool(extract_transactions, Body)
        logger.info("LLM transactions: %s", len(transactions))
        missing = [get_missing_fields(item) for item in transactions]
        if len(transactions) > 1 and any(missing):
            if not claim_processed_webhook(db, From, MessageSid):
                return xml_reply("That message was already processed.")
            return xml_reply("I found multiple transactions, but need more details for at least one. Please send each transaction in a separate message so I can ask follow-up questions.")
        if missing[0]:
            save_pending(db, From, transactions[0], missing[0][0])
            if not claim_processed_webhook(db, From, MessageSid):
                return xml_reply("That message was already processed.")
            question = "What was this income for?" if transactions[0].transaction_type == "income" else "What was the purpose?"
            return xml_reply(question)
        return xml_reply(record_reply(db, From, transactions, MessageSid))
    except ExtractionUnavailable as exc:
        db.rollback()
        return xml_reply(str(exc))
    except Exception:
        db.rollback()
        logger.exception("Could not process webhook %s", MessageSid)
        return xml_reply("Sorry, I couldn't process that transaction. Please try again.")
    finally:
        db.close()
