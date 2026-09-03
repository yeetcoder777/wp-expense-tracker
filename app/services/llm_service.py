import json
from datetime import date

from groq import Groq

from app.config import settings
from app.schemas.transaction import Transaction


client = Groq(api_key=settings.groq_api_key)


SYSTEM_PROMPT = """
You are a transaction extraction system for a personal expense tracker.

Your job is to extract financial transaction information from natural-language
messages.

Return ONLY valid JSON.

The JSON must contain exactly these fields:

{
    "transaction_type": "expense" or "income",
    "amount": number,
    "currency": string,
    "person": string or null,
    "purpose": string or null,
    "category": string or null,
    "transaction_date": "YYYY-MM-DD" or null
}

Rules:

1. "expense" means money was spent or paid.
2. "income" means money was received or earned.
3. If the currency is not specified, use "INR".
4. If a field cannot be determined, use null.
5. Never invent information.
6. Extract the amount exactly as stated.
7. Do not include explanations or markdown.
"""


def extract_transaction(message: str) -> Transaction:
    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": message,
            },
        ],
        temperature=0,
	response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content

    if not content:
        raise ValueError("LLM returned an empty response")

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"LLM returned invalid JSON: {content}"
        ) from exc

    transaction = Transaction.model_validate(data)

    if transaction.transaction_date is None:
        transaction.transaction_date = date.today()

    return transaction

def detect_intent(message: str) -> str:
    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {
    "role": "system",
    "content": """
You are an intent classifier for a personal expense tracker.

Classify the user's message into exactly one of these intents:

- transaction
- total_expenses
- today_total
- today_transactions
- yesterday_total
- yesterday_transactions
- week_total
- week_transactions
- month_total
- month_transactions
- last_month_total
- last_month_transactions
- recent_transactions
- unknown

Rules:

- transaction:
  User is recording an income or expense.
  Examples:
  "Paid ₹500 to Rahul"
  "Received ₹50,000 salary"

- total_expenses:
  User asks how much they have spent overall.
  Examples:
  "How much did I spend?"
  "How much have I spent so far?"

- today_total:
  User asks for the total amount spent today.
  Examples:
  "How much did I spend today?"
  "How much have I spent today?"

- today_transactions:
  User asks what transactions/expenses happened today.
  Examples:
  "What did I spend today?"
  "Show today's expenses"

- yesterday_total:
  User asks for the total amount spent yesterday.

- yesterday_transactions:
  User asks what they spent yesterday.

- week_total:
  User asks for the total amount spent this week.

- week_transactions:
  User asks what they spent this week.

- month_total:
  User asks for the total amount spent this month.

- month_transactions:
  User asks what they spent this month.

- last_month_total:
  User asks for the total amount spent last month.

- last_month_transactions:
  User asks what they spent last month.

- recent_transactions:
  User asks to see recent transactions without specifying a particular date range.
  Examples:
  "Show my recent transactions"
  "What did I spend recently?"

- unknown:
  Anything that does not match the above intents.

Important:
"How much" means the user wants a total.
"What did I spend" / "Show" means the user wants a transaction list.

Return ONLY valid JSON:

{
    "intent": "one_of_the_intents_above"
}
""",
            },
            {
                "role": "user",
                "content": message,
            },
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content

    if not content:
        raise ValueError("LLM returned an empty response")

    data = json.loads(content)

    return data["intent"]