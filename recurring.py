"""Monthly bills with no email (the house loan): one fixed-amount entry per month.

Configured under [[recurring]] in bills.toml. ensure() creates any missing
months from `start` up to the current month; it is idempotent because each
entry's message_id is "recurring:<name>:<YYYY-MM>", which the database keeps unique.

An entry covers the whole month: period 1st -> last day, due on the last day
(the debit date moves around weekends, so only the month matters). The page
shows it as "OCT/2026" via extra.month.
"""
import calendar
from datetime import date
from decimal import Decimal

import config
import db


def load():
    return config.load().get("recurring", [])


def month_bounds(year, month):
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def months(start: str, today: date):
    y, m = map(int, start.split("-"))
    while (y, m) <= (today.year, today.month):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def ensure(conn, today: date | None = None):
    """Create missing monthly entries (and keep existing ones' month fields current). Returns new ids."""
    today = today or date.today()
    added = []
    for item in load():
        for y, m in months(item["start"], today):
            first, last = month_bounds(y, m)
            mid, month = f"recurring:{item['name']}:{y:04d}-{m:02d}", f"{y:04d}-{m:02d}"
            new_id = db.add_bill(conn, item["name"], mid, {
                "period_start": first, "period_end": last, "due_date": last,
                "total_due": Decimal(item["amount"]), "month": month,
            })
            if new_id:
                added.append(new_id)
            else:  # rows created before this layout: bring them in line (amount and status untouched)
                conn.execute("UPDATE bills SET period_start = ?, period_end = ?, due_date = ?, "
                             "extra = json_set(extra, '$.month', ?) WHERE message_id = ?",
                             (first.isoformat(), last.isoformat(), last.isoformat(), month, mid))
        conn.commit()
    return added
