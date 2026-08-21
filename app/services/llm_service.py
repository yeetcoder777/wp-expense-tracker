import json

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

    return Transaction.model_validate(data)

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
- today_expenses
- this_month_expenses
- recent_transactions
- unknown

Rules:

- transaction: user is recording income or an expense
- total_expenses: user asks about their total spending or income across all recorded transactions
- today_expenses: user asks how much they spent today
- this_month_expenses: user asks how much they spent during the current month
- recent_transactions: user asks to see or list recent transactions
- unknown: anything else

Examples:

"Paid ₹500 to Rahul"
→ transaction

"How much did I spend?"
→ total_expenses

"How much have I spent so far?"
→ total_expenses

"How much did I spend today?"
→ today_expenses

"What did I spend today?"
→ today_expenses

"Show today's expenses"
→ today_expenses

"How much did I spend this month?"
→ this_month_expenses

"How much have I spent this month?"
→ this_month_expenses

"What did I spend this month?"
→ this_month_expenses

"How much have I spent in August?"
→ this_month_expenses

"Show my recent transactions"
→ recent_transactions

"What did I spend recently?"
→ recent_transactions

"Hello"
→ unknown

Return ONLY valid JSON:

{
    "intent": "transaction"
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