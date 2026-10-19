"""Read-only WhatsApp reports with separate totals for each currency."""
from decimal import Decimal
from app.services.date_service import get_today, get_yesterday_range, get_this_week_range, get_this_month_range, get_last_month_range
from app.services.transaction_service import get_totals_by_currency, get_transactions, get_expenses_between, get_category_transactions, get_monthly_summary


def date_range(period):
    return {
        "today": lambda: (get_today(), get_today()), "yesterday": get_yesterday_range,
        "this_week": get_this_week_range, "this_month": get_this_month_range,
        "last_month": get_last_month_range, "all": lambda: (None, None),
    }[period]()


def format_totals(totals):
    return ", ".join(f"{currency} {amount:.2f}" for currency, amount in sorted(totals.items())) or "INR 0.00"


def format_transactions(rows, title):
    if not rows:
        return title + "\nNo transactions found."
    lines, totals = [title], {}
    for row in rows:
        day = row.transaction_date.isoformat() if row.transaction_date else "Unknown date"
        lines.append(f"#{row.id} {row.currency} {row.amount:.2f} — {row.transaction_type} — {row.purpose or 'Unspecified'} — {day}")
        totals[row.currency] = totals.get(row.currency, Decimal("0")) + row.amount
    lines.append("Total: " + format_totals(totals))
    return "\n".join(lines)


def query_reply(db, user_id, intent, category_query=None):
    if intent in {"category_query", "category_list_query"}:
        category, period = category_query["category"], category_query["time_range"]
        start, end = date_range(period)
        if intent == "category_query":
            totals = get_totals_by_currency(db, user_id, "expense", start, end, category)
            return f"You've spent {format_totals(totals)} on {category} {period.replace('_', ' ')}."
        return format_transactions(get_category_transactions(db, user_id, category, start, end), f"Your {category} expenses:")
    if intent == "monthly_summary":
        start, end = get_this_month_range()
        summary = get_monthly_summary(db, user_id, start, end)
        lines = ["Monthly Summary"]
        for currency, totals in summary["currencies"].items():
            lines.extend([
                f"{currency} income: {totals['income']:.2f}",
                f"{currency} expenses: {totals['expenses']:.2f}",
                f"{currency} net balance: {totals['balance']:.2f}",
                "Top spending categories:",
            ])
            lines.extend(f"{item['category'].capitalize()}: {currency} {item['amount']:.2f}" for item in totals["categories"][:5])
        if not summary["currencies"]:
            lines.append("No income or expenses recorded this month.")
        return "\n".join(lines)
    if intent == "recent_transactions":
        return format_transactions(get_transactions(db, user_id), "Recent transactions:")
    total_queries = {
        "total_expenses": ("expense", "all"), "total_income": ("income", "all"),
        "today_income": ("income", "today"), "week_income": ("income", "this_week"),
        "month_income": ("income", "this_month"), "today_total": ("expense", "today"),
        "yesterday_total": ("expense", "yesterday"), "week_total": ("expense", "this_week"),
        "month_total": ("expense", "this_month"), "last_month_total": ("expense", "last_month"),
    }
    if intent in total_queries:
        kind, period = total_queries[intent]
        start, end = date_range(period)
        totals = get_totals_by_currency(db, user_id, kind, start, end)
        action = "earned" if kind == "income" else "spent"
        label = "so far" if period == "all" else period.replace("_", " ")
        return f"You've {action} {format_totals(totals)} {label}."
    list_queries = {
        "today_transactions": "today", "yesterday_transactions": "yesterday",
        "week_transactions": "this_week", "month_transactions": "this_month",
        "last_month_transactions": "last_month",
    }
    if intent in list_queries:
        period = list_queries[intent]
        start, end = date_range(period)
        return format_transactions(get_expenses_between(db, user_id, start, end), f"Expenses ({period.replace('_', ' ')}):")
    return None
