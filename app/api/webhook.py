from fastapi import APIRouter, Form, Response
from twilio.twiml.messaging_response import MessagingResponse
from sqlalchemy.orm import Session

from datetime import date

from app.db.database import SessionLocal
from app.services.llm_service import extract_transaction, detect_intent
from app.services.transaction_service import (
    save_transaction,
    get_total_expenses,
    get_transactions,
    get_transactions_by_date,
    get_expenses_between,
)
from app.services.conversation_service import (
    get_missing_fields,
    save_pending,
    get_pending,
    clear_pending,
)
from app.services.date_service import (
    get_yesterday_range,
    get_this_week_range,
    get_this_month_range,
    get_last_month_range,
)

router = APIRouter()


def format_transactions(
    transactions,
    title: str,
) -> str:

    if not transactions:
        return f"{title}\nNo expenses found."

    lines = [title]
    total = 0

    for transaction in transactions:
        person = transaction.person or "Unknown"
        purpose = transaction.purpose or "Unspecified"

        lines.append(
            f"₹{transaction.amount:.2f} → "
            f"{person} — {purpose}"
        )

        total += transaction.amount

    lines.append("")
    lines.append(f"Total: ₹{total:.2f}")

    return "\n".join(lines)

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
        
        if intent == "today_total":
            today = date.today()

            transactions = get_transactions_by_date(
                db=db,
                user_id=From,
                transaction_date=today,
            )

            total = sum(
                transaction.amount
                for transaction in transactions
            )

            response.message(
                f"You've spent ₹{total:.2f} today."
            )

            return Response(
                content=str(response),
                media_type="application/xml",
            )
        
        if intent == "today_transactions":
            today = date.today()

            transactions = get_transactions_by_date(
                db=db,
                user_id=From,
                transaction_date=today,
            )

            if not transactions:
                response.message(
                    "You haven't recorded any expenses today."
                )

                return Response(
                    content=str(response),
                    media_type="application/xml",
                )

            lines = ["Today's expenses:"]

            total = 0

            for transaction in transactions:
                person = transaction.person or "Unknown"
                purpose = transaction.purpose or "Unspecified"

                lines.append(
                    f"₹{transaction.amount:.2f} → "
                    f"{person} — {purpose}"
                )

                total += transaction.amount

            lines.append("")
            lines.append(f"Total: ₹{total:.2f}")

            response.message("\n".join(lines))

            return Response(
                content=str(response),
                media_type="application/xml",
            )
            
        if intent == "today_expenses":
            total = get_today_expense(
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
            
        if intent == "yesterday_total":
            start_date, end_date = get_yesterday_range()

            transactions = get_expenses_between(
                db=db,
                user_id=From,
                start_date=start_date,
                end_date=end_date,
            )

            total = sum(
                transaction.amount
                for transaction in transactions
            )

            response.message(
                f"You've spent ₹{total:.2f} yesterday."
            )

            return Response(
                content=str(response),
                media_type="application/xml",
            )
            
        if intent == "yesterday_transactions":
            start_date, end_date = get_yesterday_range()

            transactions = get_expenses_between(
                db=db,
                user_id=From,
                start_date=start_date,
                end_date=end_date,
            )

            response.message(
                format_transactions(
                    transactions,
                    "Yesterday's expenses:",
                )
            )

            return Response(
                content=str(response),
                media_type="application/xml",
            )
            
        if intent == "week_total":
            start_date, end_date = get_this_week_range()

            transactions = get_expenses_between(
                db=db,
                user_id=From,
                start_date=start_date,
                end_date=end_date,
            )

            total = sum(
                transaction.amount
                for transaction in transactions
            )

            response.message(
                f"You've spent ₹{total:.2f} this week."
            )

            return Response(
                content=str(response),
                media_type="application/xml",
            )
            
        if intent == "week_transactions":
            start_date, end_date = get_this_week_range()

            transactions = get_expenses_between(
                db=db,
                user_id=From,
                start_date=start_date,
                end_date=end_date,
            )

            response.message(
                format_transactions(
                    transactions,
                    "This week's expenses:",
                )
            )

            return Response(
                content=str(response),
                media_type="application/xml",
            )
            
        if intent == "month_total":
            start_date, end_date = get_this_month_range()

            transactions = get_expenses_between(
                db=db,
                user_id=From,
                start_date=start_date,
                end_date=end_date,
            )

            total = sum(
                transaction.amount
                for transaction in transactions
            )

            response.message(
                f"You've spent ₹{total:.2f} this month."
            )

            return Response(
                content=str(response),
                media_type="application/xml",
            )
            
        if intent == "month_transactions":
            start_date, end_date = get_this_month_range()

            transactions = get_expenses_between(
                db=db,
                user_id=From,
                start_date=start_date,
                end_date=end_date,
            )

            response.message(
                format_transactions(
                    transactions,
                    "This month's expenses:",
                )
            )

            return Response(
                content=str(response),
                media_type="application/xml",
            )
            
        if intent == "last_month_total":
            start_date, end_date = get_last_month_range()

            transactions = get_expenses_between(
                db=db,
                user_id=From,
                start_date=start_date,
                end_date=end_date,
            )

            total = sum(
                transaction.amount
                for transaction in transactions
            )

            response.message(
                f"You've spent ₹{total:.2f} last month."
            )

            return Response(
                content=str(response),
                media_type="application/xml",
            )
            
        if intent == "last_month_transactions":
            start_date, end_date = get_last_month_range()

            transactions = get_expenses_between(
                db=db,
                user_id=From,
                start_date=start_date,
                end_date=end_date,
            )

            response.message(
                format_transactions(
                    transactions,
                    "Last month's expenses:",
                )
            )

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

        if transaction.transaction_type == "income":
            response.message(
                f"Recorded ₹{transaction.amount} income "
                f"from {transaction.person or 'unknown'} "
                f"for {transaction.purpose or 'unspecified purpose'}."
            )
        else:
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