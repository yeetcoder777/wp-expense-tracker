from fastapi import APIRouter, Form, Response
from twilio.twiml.messaging_response import MessagingResponse
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.services.llm_service import extract_transaction, detect_intent
from app.services.transaction_service import (
    save_transaction,
    get_total_expenses,
    get_today_expenses,
    get_this_month_expenses,
    get_transactions,
)
from app.services.conversation_service import (
    get_missing_fields,
    save_pending,
    get_pending,
    clear_pending,
)

router = APIRouter()


@router.post("/whatsapp")
async def whatsapp_webhook(
    Body: str = Form(...),
    From: str = Form(...),
):
    db: Session = SessionLocal()

    print(f"Message from {From}: {Body}")

    response = MessagingResponse()

    try:
        pending_data = get_pending(db, From)

        # --------------------------------------------------
        # CASE 1: User is answering a previous question
        # --------------------------------------------------

        if pending_data:
            pending, pending_field = pending_data

            print("Found pending transaction:")
            print(pending.model_dump())

            print("Waiting for field:")
            print(pending_field)

            # Put the user's answer into the field
            # that the bot explicitly asked for.
            if pending_field == "person":
                pending.person = Body.strip()

            elif pending_field == "purpose":
                pending.purpose = Body.strip()

            missing = get_missing_fields(pending)

            print("Updated transaction:")
            print(pending.model_dump())

            print("Still missing:")
            print(missing)

            # Still missing something
            if missing:
                save_pending(
                    db,
                    From,
                    pending,
                    missing[0],
                )

                if missing[0] == "person":
                    response.message("Who did you pay?")

                elif missing[0] == "purpose":
                    response.message("What was the purpose?")

                return Response(
                    content=str(response),
                    media_type="application/xml",
                )

            # --------------------------------------------------
            # Transaction is now complete
            # --------------------------------------------------

            saved_transaction = save_transaction(
                db=db,
                user_id=From,
                transaction=pending,
            )

            clear_pending(db, From)

            response.message(
                f"Recorded ₹{pending.amount} "
                f"paid to {pending.person or 'unknown'} "
                f"for {pending.purpose or 'unspecified purpose'}."
            )

            print("Saved to database:")
            print(f"Transaction ID: {saved_transaction.id}")

            print("Completed transaction:")
            print(pending.model_dump())

            return Response(
                content=str(response),
                media_type="application/xml",
            )
            
        # --------------------------------------------------
        # CASE 2: Query / non-transaction message
        # --------------------------------------------------

        intent = detect_intent(Body)

        print("Detected intent:")
        print(intent)

        if intent == "total_expenses":
            total = get_total_expenses(
                db=db,
                user_id=From,
            )

            response.message(
                f"You've spent ₹{total:.2f} so far."
            )

            print("Total expenses:", total)
            print("Twilio response:")
            print(str(response))

            return Response(
                content=str(response),
                media_type="application/xml",
            )
            
        if intent == "today_expenses":
            total = get_today_expenses(
                db=db,
                user_id=From,
            )

            response.message(
                f"You've spent ₹{total:.2f} today."
            )

            print("Today's expenses:", total)
            print("Twilio response:")
            print(str(response))

            return Response(
                content=str(response),
                media_type="application/xml",
            )
            
        if intent == "this_month_expenses":
            total = get_this_month_expenses(
                db=db,
                user_id=From,
            )

            response.message(
                f"You've spent ₹{total:.2f} this month."
            )

            print("This month's expenses:", total)
            print("Twilio response:")
            print(str(response))

            return Response(
                content=str(response),
                media_type="application/xml",
            )

        if intent == "recent_transactions":

            transactions = get_transactions(
                db=db,
                user_id=From,
                limit=5,
            )

            if not transactions:
                response.message(
                    "You don't have any transactions recorded yet."
                )

                return Response(
                    content=str(response),
                    media_type="application/xml",
                )

            lines = ["Recent transactions:"]

            for transaction in transactions:
                person = transaction.person or "Unknown"
                purpose = transaction.purpose or "Unspecified"

                lines.append(
                    f"₹{transaction.amount:.2f} → "
                    f"{person} — {purpose}"
                )

            response.message("\n".join(lines))

            return Response(
                content=str(response),
                media_type="application/xml",
            )

        if intent == "unknown":

            response.message(
                "I can record expenses and show your spending. "
                "Try something like 'Paid ₹500 to Rahul' "
                "or 'How much did I spend?'"
            )

            return Response(
                content=str(response),
                media_type="application/xml",
            )

        # --------------------------------------------------
        # CASE 3: New transaction
        # --------------------------------------------------

        transaction = extract_transaction(Body)

        print("LLM transaction:")
        print(transaction.model_dump())

        missing = get_missing_fields(transaction)

        print("Missing fields:")
        print(missing)

        # --------------------------------------------------
        # Some fields are missing
        # --------------------------------------------------

        if missing:
            first_missing = missing[0]

            save_pending(
                db,
                From,
                transaction,
                first_missing,
            )

            if first_missing == "person":
                response.message("Who did you pay?")

            elif first_missing == "purpose":
                response.message("What was the purpose?")

            print("Twilio response:")
            print(str(response))

            return Response(
                content=str(response),
                media_type="application/xml",
            )

        # --------------------------------------------------
        # Complete transaction received in one message
        # --------------------------------------------------

        saved_transaction = save_transaction(
            db=db,
            user_id=From,
            transaction=transaction,
        )

        response.message(
            f"Recorded ₹{transaction.amount} "
            f"paid to {transaction.person or 'unknown'} "
            f"for {transaction.purpose or 'unspecified purpose'}."
        )

        print("Saved to database:")
        print(f"Transaction ID: {saved_transaction.id}")

        print("Completed transaction:")
        print(transaction.model_dump())

        print("Twilio response:")
        print(str(response))

        return Response(
            content=str(response),
            media_type="application/xml",
        )

    except Exception as e:
        db.rollback()

        print("ERROR:", repr(e))

        response.message(
            "Sorry, I couldn't process that transaction. "
            "Please try again."
        )

        print("Twilio error response:")
        print(str(response))

        return Response(
            content=str(response),
            media_type="application/xml",
        )

    finally:
        db.close()