"""The intent labels understood by the WhatsApp query and transaction handlers."""

INTENT_CRITERIA: dict[str, str] = {
    "transaction": "Record new spending or income, including several entries. Example: spent 250 on coffee. Not a question about existing records.",
    "total_expenses": "Ask for total spending across all recorded time, with no specific period or category.",
    "today_total": "Ask for the total amount spent today, not a list of entries.",
    "today_transactions": "Show individual expenses recorded for today.",
    "yesterday_total": "Ask for the total amount spent yesterday.",
    "yesterday_transactions": "Show individual expenses for yesterday.",
    "week_total": "Ask for the total amount spent this week.",
    "week_transactions": "Show individual expenses for this week.",
    "month_total": "Ask for total spending this month, without requesting income or a full financial summary.",
    "month_transactions": "Show individual expenses for this month.",
    "last_month_total": "Ask for total spending last calendar month.",
    "last_month_transactions": "Show individual expenses for last calendar month.",
    "total_income": "Ask for total income across all recorded time.",
    "today_income": "Ask how much income was received today.",
    "week_income": "Ask how much income was received this week.",
    "month_income": "Ask how much income was received this month.",
    "recent_transactions": "Show recent transaction entries without specifying a period or spending category.",
    "category_query": "Ask for total spending in a specific category, optionally with a period. Example: how much on food this month? Prefer this over an overall period total when a category is named.",
    "category_list_query": "Show individual expenses in a specific category, optionally with a period. Example: list my food expenses this week.",
    "monthly_summary": "Request an overall monthly financial summary of income, expenses, and balance, rather than only one total.",
    "unknown": "Greetings, unrelated messages, unsupported tasks, or requests that fit none of the supported intents. Do not force an unsupported request into another label.",
}


def validate_intent(label: str) -> str:
    if label not in INTENT_CRITERIA:
        raise ValueError("Classifier returned an unsupported intent")
    return label
