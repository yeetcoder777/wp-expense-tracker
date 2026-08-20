from fastapi import APIRouter, Form, Response
from twilio.twiml.messaging_response import MessagingResponse

from app.services.llm_service import extract_transaction
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
    print(f"Message from {From}: {Body}")

    response = MessagingResponse()

    try:
        pending = get_pending(From)

        # --------------------------------------------------
        # CASE 1: User is answering a previous question
        # --------------------------------------------------
        if pending:
            print("Found pending transaction:")
            print(pending.model_dump())

            if pending.purpose is None:
                pending.purpose = Body.strip()

            missing = get_missing_fields(pending)

            print("Updated transaction:")
            print(pending.model_dump())

            print("Still missing:")
            print(missing)

            if missing:
                save_pending(From, pending)

                if "purpose" in missing:
                    response.message("What was the purpose?")

                elif "person" in missing:
                    response.message("Who was this transaction with?")

                print("Twilio response:")
                print(str(response))

                return Response(
                content=str(response),
                media_type="application/xml",
            )

            # Transaction is complete
            clear_pending(From)

            response.message(
                f"Recorded ₹{pending.amount} "
                f"paid to {pending.person or 'unknown'} "
                f"for {pending.purpose or 'unspecified purpose'}."
            )

            print("Completed transaction:")
            print(pending.model_dump())

            print("Twilio response:")
            print(str(response))

            return Response(
                content=str(response),
                media_type="application/xml",
            )

        # --------------------------------------------------
        # CASE 2: New transaction
        # --------------------------------------------------

        transaction = extract_transaction(Body)

        print("LLM transaction:")
        print(transaction.model_dump())

        missing = get_missing_fields(transaction)

        print("Missing fields:")
        print(missing)

        if missing:
            save_pending(From, transaction)

            if "purpose" in missing:
                response.message("What was the purpose?")

            elif "person" in missing:
                response.message("Who was this transaction with?")

            print("Twilio response:")
            print(str(response))

            return Response(
                content=str(response),
                media_type="application/xml",
            )

        # Complete transaction received in one message
        response.message(
            f"Recorded ₹{transaction.amount} "
            f"paid to {transaction.person or 'unknown'} "
            f"for {transaction.purpose or 'unspecified purpose'}."
        )

        print("Completed transaction:")
        print(transaction.model_dump())

        print("Twilio response:")
        print(str(response))

        return Response(
                content=str(response),
                media_type="application/xml",
            )

    except Exception as e:
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
