from fastapi import APIRouter, Form, Response
from twilio.twiml.messaging_response import MessagingResponse
from sqlalchemy.orm import Session

from app.db.database import SessionLocal

from app.services.llm_service import (
    extract_transaction,
    detect_intent,
    extract_category_query,
)
from app.services.transaction_service import (
    save_transaction,
    get_total_expenses,
    get_transactions,
    get_transactions_by_date,
    get_expenses_between,
    get_total_income,
    get_today_income,
    get_income_between,
    get_category_expenses,
    get_category_expenses_between,
)
from app.services.conversation_service import (
    get_missing_fields,
    save_pending,
    get_pending,
    clear_pending,
)
from app.services.date_service import (
    get_today,
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

def get_category_date_range(time_range):
    today = get_today()

    if time_range == "all":
        return None, None

    if time_range == "today":
        return today, today

    if time_range == "yesterday":
        start, end = get_yesterday_range()
        return start, end

    if time_range == "this_week":
        start, end = get_this_week_range()
        return start, end

    if time_range == "this_month":
        start, end = get_this_month_range()
        return start, end

    if time_range == "last_month":
        start, end = get_last_month_range()
        return start, end

    raise ValueError(f"Unsupported category time range: {time_range}")


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

            # --------------------------------------------------
            # Still missing something
            # --------------------------------------------------

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
                    if pending.transaction_type == "income":
                        response.message("What was this income for?")
                    else:
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

            # --------------------------------------------------
            # Confirmation message
            # --------------------------------------------------

            if pending.transaction_type == "income":

                if pending.person:
                    message = (
                        f"Recorded ₹{pending.amount} "
                        f"received from {pending.person}"
                    )
                else:
                    message = (
                        f"Recorded ₹{pending.amount} received"
                    )

            else:

                if pending.person:
                    message = (
                        f"Recorded ₹{pending.amount} "
                        f"paid to {pending.person}"
                    )
                else:
                    message = (
                        f"Recorded ₹{pending.amount}"
                    )

            if pending.purpose:
                message += f" for {pending.purpose}"

            message += "."

            response.message(message)

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
        
        # --------------------------------------------------
        # CATEGORY QUERY
        # --------------------------------------------------

        if intent == "category_query":

            query = extract_category_query(Body)

            category = query["category"]
            time_range = query["time_range"]

            print("Category query:")
            print(query)

            start_date, end_date = get_category_date_range(time_range)

            if time_range == "all":

                total = get_category_expenses(
                    db=db,
                    user_id=From,
                    category=category,
                )

                period_text = "overall"

            else:

                total = get_category_expenses_between(
                    db=db,
                    user_id=From,
                    category=category,
                    start_date=start_date,
                    end_date=end_date,
                )

                period_names = {
                    "today": "today",
                    "yesterday": "yesterday",
                    "this_week": "this week",
                    "this_month": "this month",
                    "last_month": "last month",
                }

                period_text = period_names[time_range]

            response.message(
                f"You've spent ₹{total:.2f} on {category} {period_text}."
            )

            print("Category:", category)
            print("Time range:", time_range)
            print("Total:", total)

            return Response(
                content=str(response),
                media_type="application/xml",
            )

        # --------------------------------------------------
        # TOTAL EXPENSES
        # --------------------------------------------------

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
            
        # --------------------------------------------------
        # TOTAL INCOME
        # --------------------------------------------------

        if intent == "total_income":

            total = get_total_income(
                db=db,
                user_id=From,
            )

            response.message(
                f"You've earned ₹{total:.2f} so far."
            )

            return Response(
                content=str(response),
                media_type="application/xml",
            )

        # --------------------------------------------------
        # TODAY INCOME
        # --------------------------------------------------

        if intent == "today_income":

            total = get_today_income(
                db=db,
                user_id=From,
            )

            response.message(
                f"You've earned ₹{total:.2f} today."
            )

            return Response(
                content=str(response),
                media_type="application/xml",
            )

        # --------------------------------------------------
        # WEEKLY INCOME
        # --------------------------------------------------

        if intent == "week_income":

            start_date, end_date = get_this_week_range()

            transactions = get_income_between(
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
                f"You've earned ₹{total:.2f} this week."
            )

            return Response(
                content=str(response),
                media_type="application/xml",
            )

        # --------------------------------------------------
        # MONTHLY INCOME
        # --------------------------------------------------

        if intent == "month_income":

            start_date, end_date = get_this_month_range()

            transactions = get_income_between(
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
                f"You've earned ₹{total:.2f} this month."
            )

            return Response(
                content=str(response),
                media_type="application/xml",
            )

        # --------------------------------------------------
        # TODAY TOTAL
        # --------------------------------------------------

        if intent == "today_total":

            today = get_today()

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

        # --------------------------------------------------
        # TODAY TRANSACTIONS
        # --------------------------------------------------

        if intent == "today_transactions":

            today = get_today()

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

        # --------------------------------------------------
        # YESTERDAY TOTAL
        # --------------------------------------------------

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

        # --------------------------------------------------
        # YESTERDAY TRANSACTIONS
        # --------------------------------------------------

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

        # --------------------------------------------------
        # THIS WEEK TOTAL
        # --------------------------------------------------

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

        # --------------------------------------------------
        # THIS WEEK TRANSACTIONS
        # --------------------------------------------------

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

        # --------------------------------------------------
        # THIS MONTH TOTAL
        # --------------------------------------------------

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

        # --------------------------------------------------
        # THIS MONTH TRANSACTIONS
        # --------------------------------------------------

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

        # --------------------------------------------------
        # LAST MONTH TOTAL
        # --------------------------------------------------

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

        # --------------------------------------------------
        # LAST MONTH TRANSACTIONS
        # --------------------------------------------------

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

        # --------------------------------------------------
        # RECENT TRANSACTIONS
        # --------------------------------------------------

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

                if transaction.transaction_type == "income":

                    if person:
                        lines.append(
                            f"₹{transaction.amount:.2f} "
                            f"received from {person}"
                            f" — {purpose}"
                        )
                    else:
                        lines.append(
                            f"₹{transaction.amount:.2f} "
                            f"received — {purpose}"
                        )

                else:

                    if person:
                        lines.append(
                            f"₹{transaction.amount:.2f} "
                            f"paid to {person}"
                            f" — {purpose}"
                        )
                    else:
                        lines.append(
                            f"₹{transaction.amount:.2f} "
                            f"— {purpose}"
                        )

            response.message("\n".join(lines))

            return Response(
                content=str(response),
                media_type="application/xml",
            )

        # --------------------------------------------------
        # UNKNOWN INTENT
        # --------------------------------------------------

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

                if transaction.transaction_type == "income":
                    response.message("Who did you receive this from?")
                else:
                    response.message("Who did you pay?")

            elif first_missing == "purpose":

                if transaction.transaction_type == "income":
                    response.message("What was this income for?")
                else:
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

        # --------------------------------------------------
        # Confirmation message
        # --------------------------------------------------

        if transaction.transaction_type == "income":

            if transaction.person:
                message = (
                    f"Recorded ₹{transaction.amount} "
                    f"received from {transaction.person}"
                )
            else:
                message = (
                    f"Recorded ₹{transaction.amount} received"
                )

        else:

            if transaction.person:
                message = (
                    f"Recorded ₹{transaction.amount} "
                    f"paid to {transaction.person}"
                )
            else:
                message = (
                    f"Recorded ₹{transaction.amount}"
                )

        if transaction.purpose:
            message += f" for {transaction.purpose}"

        message += "."

        response.message(message)

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