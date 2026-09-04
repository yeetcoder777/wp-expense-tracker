import json

from app.services.date_service import get_today
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
    "category": string,
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

8. Always classify the transaction into exactly ONE of these categories:

   - food
   - transport
   - shopping
   - bills
   - entertainment
   - health
   - education
   - salary
   - freelance
   - other

9. Choose the category based on the purpose and context of the transaction.

10. For expenses:
    - food: restaurants, lunch, dinner, breakfast, groceries, snacks, etc.
    - transport: Uber, Ola, taxi, bus, train, fuel, metro, etc.
    - shopping: clothes, electronics, Amazon purchases, accessories, etc.
    - bills: electricity, internet, phone bill, rent, subscriptions, etc.
    - entertainment: movies, games, concerts, events, etc.
    - health: medicines, doctors, hospitals, gym, medical expenses, etc.
    - education: books, courses, college fees, certifications, etc.
    - other: expenses that do not fit the above categories.

11. For income:
    - salary: salary, paycheck, wages, monthly salary, etc.
    - freelance: freelance work, consulting, projects, contract work, etc.
    - other: income that does not fit salary or freelance.

12. If the category cannot reasonably be determined, use "other".

13. Never use a category outside the allowed list.

14. Never infer a category from information that is not present in the
    transaction.

15. The category must always be present and must never be null.

16. If transaction_date is not specified, return null for transaction_date.
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
        transaction.transaction_date = get_today()

    return transaction

def extract_category_query(message: str) -> dict:
    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {
                "role": "system",
                "content": """
You are a query extraction system for a personal expense tracker.

Your job is to extract category and date information from a user's
natural-language expense query.

Return ONLY valid JSON.

The JSON must contain exactly these fields:

{
    "category": "food" | "transport" | "shopping" | "bills" |
                 "entertainment" | "health" | "education" | "other",
    "time_range": "all" | "today" | "yesterday" | "this_week" |
                  "this_month" | "last_month"
}

Allowed categories:

- food
- transport
- shopping
- bills
- entertainment
- health
- education
- other

Allowed time ranges:

- all
- today
- yesterday
- this_week
- this_month
- last_month

Rules:

1. Extract the category the user is asking about.

2. Only use one of the allowed categories.

3. If the user mentions something that clearly belongs to a category,
   map it to that category.

Examples:

"dinner" → food
"restaurant" → food
"Uber" → transport
"fuel" → transport
"clothes" → shopping
"electricity" → bills
"movie" → entertainment
"medicine" → health
"course" → education

4. If the category cannot be determined, use "other".

5. If the user does not specify a time range, use "all".

6. "today" → today.

7. "yesterday" → yesterday.

8. "this week" → this_week.

9. "this month" → this_month.

10. "last month" → last_month.

11. Do not infer a time range that the user did not specify.

Examples:

User: "How much did I spend on food?"
Return:
{"category": "food", "time_range": "all"}

User: "How much did I spend on food this month?"
Return:
{"category": "food", "time_range": "this_month"}

User: "How much did I spend on transport this week?"
Return:
{"category": "transport", "time_range": "this_week"}

User: "Show my shopping expenses yesterday"
Return:
{"category": "shopping", "time_range": "yesterday"}

User: "How much did I spend on electricity last month?"
Return:
{"category": "bills", "time_range": "last_month"}

Return ONLY valid JSON.
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

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"LLM returned invalid JSON: {content}"
        ) from exc

    allowed_categories = {
        "food",
        "transport",
        "shopping",
        "bills",
        "entertainment",
        "health",
        "education",
        "other",
    }

    allowed_time_ranges = {
        "all",
        "today",
        "yesterday",
        "this_week",
        "this_month",
        "last_month",
    }

    category = data.get("category")
    time_range = data.get("time_range")

    if category not in allowed_categories:
        raise ValueError(f"Invalid category returned by LLM: {category}")

    if time_range not in allowed_time_ranges:
        raise ValueError(
            f"Invalid time range returned by LLM: {time_range}"
        )

    return {
        "category": category,
        "time_range": time_range,
    }


def detect_intent(message: str) -> str:
    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {
                "role": "system",
                "content": """
You are an intent classifier for a personal expense tracker.

Classify the user's message into exactly ONE of these intents:

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
- total_income
- today_income
- week_income
- month_income
- recent_transactions
- monthly_summary
- unknown


TRANSACTION
-----------

User is recording an income or expense.

Examples:

"Paid ₹500 to Rahul"
"Received ₹50,000 salary"
"I spent ₹300 on food"
"Got ₹5000 from Amit"


TOTAL_EXPENSES
--------------

User asks how much they have spent overall.

Examples:

"How much did I spend?"
"How much have I spent so far?"
"What is my total spending?"
"How much money have I spent?"


TODAY_TOTAL
-----------

User asks for the total amount spent today.

Examples:

"How much did I spend today?"
"How much have I spent today?"
"What's my spending today?"


TODAY_TRANSACTIONS
------------------

User asks what transactions or expenses happened today.

Examples:

"What did I spend today?"
"Show today's expenses"
"What have I spent today?"


YESTERDAY_TOTAL
---------------

User asks for the total amount spent yesterday.

Examples:

"How much did I spend yesterday?"
"What was my spending yesterday?"


YESTERDAY_TRANSACTIONS
----------------------

User asks what they spent yesterday.

Examples:

"What did I spend yesterday?"
"Show yesterday's expenses"


WEEK_TOTAL
----------

User asks for the total amount spent this week.

Examples:

"How much did I spend this week?"
"What's my spending this week?"


WEEK_TRANSACTIONS
-----------------

User asks what they spent this week.

Examples:

"What did I spend this week?"
"Show this week's expenses"


MONTH_TOTAL
-----------

User asks for the total amount spent this month.

Examples:

"How much did I spend this month?"
"What's my spending this month?"


MONTH_TRANSACTIONS
------------------

User asks what they spent this month.

Examples:

"What did I spend this month?"
"Show this month's expenses"


LAST_MONTH_TOTAL
----------------

User asks for the total amount spent last month.

Examples:

"How much did I spend last month?"
"What was my spending last month?"


LAST_MONTH_TRANSACTIONS
-----------------------

User asks what they spent last month.

Examples:

"What did I spend last month?"
"Show last month's expenses"


TOTAL_INCOME
------------

User asks how much money they have earned or received overall.

Examples:

"How much have I earned?"
"How much money have I received?"
"What's my total income?"
"How much have I made so far?"
"How much did I earn overall?"


TODAY_INCOME
------------

User asks how much income they received or earned today.

Examples:

"How much did I earn today?"
"How much income did I get today?"
"How much money did I receive today?"
"What did I earn today?"


WEEK_INCOME
-----------

User asks how much income they received or earned this week.

Examples:

"How much did I earn this week?"
"How much income did I get this week?"
"What did I earn this week?"


MONTH_INCOME
------------

User asks how much income they received or earned this month.

Examples:

"How much did I earn this month?"
"How much income did I get this month?"
"What did I earn this month?"
"What's my income this month?"


RECENT_TRANSACTIONS
-------------------

User asks to see recent transactions without specifying a particular
date range.

Examples:

"Show my recent transactions"
"What did I spend recently?"
"Show my latest transactions"
"What are my recent transactions?"


MONTHLY_SUMMARY
--------------
User wants a complete financial summary for the current month.

Examples:
"Give me my monthly summary"
"Show my monthly summary"
"How did I do this month?"
"Give me a summary of this month"
"Summarize my finances this month"
"Show my income and expenses this month"
"What's my financial summary for this month?"

Return "monthly_summary" when the user wants an overall
summary containing income, expenses, balance, and spending categories.

Important:
"How much did I spend this month?"
-> month_total

"How much did I earn this month?"
-> month_income

"Give me my monthly summary"
-> monthly_summary


UNKNOWN
-------

Anything that does not match the above intents.

CATEGORY_QUERY
--------------

User asks about expenses belonging to a specific category.

Examples:

"How much did I spend on food?"
"How much did I spend on transport?"
"How much did I spend on food this month?"
"Show my shopping expenses"
"How much did I spend on electricity last month?"
"How much did I spend on movies?"

Important:

A category query asks about EXISTING transactions.

It is NOT a transaction-recording message.

Return "category_query" whenever the user asks about spending
for a particular category.

CATEGORY_LIST_QUERY
-------------------
User asks to SEE or SHOW the actual transactions belonging to a category.

Examples:
"Show my food expenses"
"Show my food expenses this month"
"List my transport expenses"
"Show my shopping transactions"
"Show my Uber expenses"
"Show my bills from last month"

Return "category_list_query" when the user wants to see the
individual transactions.

Important distinction:

"How much did I spend on food?"
-> category_query

"How much did I spend on food this month?"
-> category_query

"Show my food expenses"
-> category_list_query

"List my food expenses this month"
-> category_list_query


IMPORTANT
---------

- "How much" generally means the user wants a total.

- "What did I spend" / "Show" generally means the user wants a
  transaction list.

- "earned", "received", "income", "made" generally indicate an
  income query when the user is asking about existing records.

- "spent", "spending", "expenses", "paid" generally indicate an
  expense query.

- A message recording a new transaction must be classified as
  "transaction" even if it contains words such as "earned" or "received".

- Do not classify a transaction-recording message as an income/expense
  query just because it contains words like "earned", "received",
  "spent", or "paid".
  
- If the user mentions a specific spending category and asks about
  existing expenses, classify it as "category_query".
  
- If the user asks for the amount/total spent in a category, use "category_query".

- If the user asks to show/list/view the individual transactions in a category, use "category_list_query".

- If the user asks for an overall financial summary of the month, use "monthly_summary".

- Do not use "monthly_summary" for a question asking only for total expenses or only for total income.

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

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"LLM returned invalid JSON: {content}"
        ) from exc

    return data["intent"]
  

def extract_category_list_query(message: str) -> dict:
    prompt = """
You extract information from a user's request to LIST expense transactions.

Return ONLY valid JSON.

The JSON must contain exactly:

{
    "category": string,
    "time_range": string
}

Allowed categories:
- food
- transport
- shopping
- bills
- entertainment
- health
- education
- other

Allowed time ranges:
- all
- today
- yesterday
- this_week
- this_month
- last_month

Category mapping:
- dinner, lunch, breakfast, restaurant, groceries, snacks -> food
- Uber, Ola, taxi, bus, train, fuel, metro -> transport
- clothes, electronics, Amazon purchases, accessories -> shopping
- electricity, internet, phone bill, rent, subscriptions -> bills
- movies, games, concerts, events -> entertainment
- medicines, doctors, hospitals, gym, medical expenses -> health
- books, courses, college fees, certifications -> education

Time mapping:
- today -> today
- yesterday -> yesterday
- this week -> this_week
- this month -> this_month
- last month -> last_month
- if no time range is specified -> all

Never invent information.
Always return one allowed category and one allowed time_range.
"""

    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": message},
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

    allowed_categories = {
        "food",
        "transport",
        "shopping",
        "bills",
        "entertainment",
        "health",
        "education",
        "other",
    }

    allowed_time_ranges = {
        "all",
        "today",
        "yesterday",
        "this_week",
        "this_month",
        "last_month",
    }

    if data.get("category") not in allowed_categories:
        raise ValueError(f"Invalid category: {data.get('category')}")

    if data.get("time_range") not in allowed_time_ranges:
        raise ValueError(f"Invalid time range: {data.get('time_range')}")

    return data