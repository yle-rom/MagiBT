"""Build a demo database with made-up bills, for screenshots and the vhs tapes.

  python -m demo.seed       ->  demo/data/billing.db (recreated each run)

Run the app on it with:
  MAGIBT_CONFIG=bills.example.toml MAGIBT_DATA=demo/data tui/magibt.py

Dates are relative to today, so paid / unpaid / overdue always look current.
"""
import os
from contextlib import closing
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["MAGIBT_CONFIG"] = str(ROOT / "bills.example.toml")
os.environ["MAGIBT_DATA"] = str(ROOT / "demo" / "data")
from magibt import config, recurring  # noqa: E402  (after the env vars above)
from magibt.storage import db  # noqa: E402

# vendor, issued N days ago, days to pay, amount, paid?, extra fields
BILLS = [
    ("mobile", 92, 20, "24.90", True, {}),
    ("mobile", 61, 20, "24.90", True, {}),
    ("mobile", 31, 20, "27.40", True, {}),
    ("mobile", 1, 20, "24.90", False, {}),
    ("electricity", 85, 21, "61.37", True, {"kwh": 212}),
    ("electricity", 55, 21, "74.12", True, {"kwh": 258}),
    ("electricity", 24, 21, "58.03", False, {"kwh": 199}),     # overdue
    ("water", 47, 30, "18.60", True, {"m3": 9}),
    ("water", 6, 30, "21.15", False, {"m3": 11}),
    ("building", 58, 25, "35.00", True, {}),
    ("building", 27, 25, "35.00", True, {}),
    ("building", 0, 25, None, False, {}),                # amount still to enter
]


def main():
    db_file = config.DATA_DIR / "billing.db"
    for f in (db_file, db_file.with_name("billing.db-wal"), db_file.with_name("billing.db-shm")):
        f.unlink(missing_ok=True)
    today = date.today()
    fixed = {b["name"]: b for b in config.load()["bill"]}
    with closing(db.connect(db_file)) as conn:
        for n, (vendor, ago, days, amount, paid, extra) in enumerate(BILLS):
            issued = today - timedelta(days=ago)
            fields = {"issue_date": issued, "due_date": issued + timedelta(days=days),
                      "period_start": issued - timedelta(days=31), "period_end": issued - timedelta(days=1),
                      "payment_code": f"RF00 0000 0000 0000 {n:04d}", **extra}
            if vendor == "building":         # fixed payment details come from the config, as in the parser
                fields |= {k: fixed[vendor][k] for k in ("recipient_name", "iban", "payment_comment")}
                fields.pop("payment_code")
            if amount is None:
                fields["needs_review"] = True
            else:
                fields["total_due"] = Decimal(amount)
            bill_id = db.add_bill(conn, vendor, f"<demo-{n}@magibt.example>", fields)
            if paid:
                db.mark_paid(conn, bill_id, issued + timedelta(days=days // 2))
        recurring.ensure(conn)
        for b in db.list_bills(conn, vendor="loan"):    # older loan months already paid
            if b["extra"].get("month") != today.strftime("%Y-%m"):
                db.mark_paid(conn, b["id"], date.fromisoformat(b["due_date"]))
        print(f"demo db: {db_file.relative_to(ROOT)} ({len(db.list_bills(conn))} bills)")


if __name__ == "__main__":
    main()
