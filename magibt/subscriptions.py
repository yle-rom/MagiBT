"""Static [[subscription]] list from bills.toml (used by the web server and the CLI)."""
from decimal import ROUND_CEILING, Decimal

from magibt import config


def load():
    """[{name, amount, cycle, per_month, per_year}]; per_year is exact, per_month rounded for display."""
    subs = config.load().get("subscription", [])
    out = []
    for s in subs:
        amount = Decimal(s["amount"])
        yearly = amount * 12 if s["cycle"] == "monthly" else amount
        monthly = amount if s["cycle"] == "monthly" else (amount / 12).quantize(Decimal("0.01"))
        out.append({"name": s["name"], "amount": amount, "cycle": s["cycle"],
                    "per_month": monthly, "per_year": yearly})
    return out


def totals(subs):
    """(per month rounded UP to the cent, exact per year)."""
    year = sum((s["per_year"] for s in subs), Decimal(0))
    return (year / 12).quantize(Decimal("0.01"), rounding=ROUND_CEILING), year
