from datetime import date, timedelta
import calendar


def get_today_range() -> tuple[date, date]:
    today = date.today()
    return today, today


def get_yesterday_range() -> tuple[date, date]:
    yesterday = date.today() - timedelta(days=1)
    return yesterday, yesterday


def get_this_week_range() -> tuple[date, date]:
    today = date.today()

    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)

    return start, end


def get_this_month_range() -> tuple[date, date]:
    today = date.today()

    start = today.replace(day=1)

    last_day = calendar.monthrange(
        today.year,
        today.month,
    )[1]

    end = today.replace(day=last_day)

    return start, end


def get_last_month_range() -> tuple[date, date]:
    today = date.today()

    first_this_month = today.replace(day=1)

    last_day_previous_month = first_this_month - timedelta(days=1)

    start = last_day_previous_month.replace(day=1)
    end = last_day_previous_month

    return start, end