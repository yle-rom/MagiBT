"""SQLite storage for bills. Used by the web server and the CLI.

Storage rules:
  - money is TEXT ("41.22") and comes back as Decimal: SQLite has no decimal
    type and REAL would bring float rounding errors back
  - dates are ISO TEXT ("2026-10-28"), which sorts and compares correctly
  - fields every vendor shares are columns; vendor-specific ones go in `extra` (JSON)
  - "overdue" is not stored: it is unpaid + due_date in the past, computed on read
"""
import json
import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

import config

DB_PATH = config.DATA_DIR / "billing.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS bills (
    id              INTEGER PRIMARY KEY,
    vendor          TEXT NOT NULL,
    message_id      TEXT UNIQUE,              -- dedup for emailed bills; NULL for manual ones
    issue_date      TEXT,
    due_date        TEXT,
    period_start    TEXT,
    period_end      TEXT,
    total_due       TEXT,                     -- NULL until known (koinoxrista)
    status          TEXT NOT NULL DEFAULT 'unpaid'
                    CHECK (status IN ('needs_review', 'unpaid', 'paid')),
    paid_on         TEXT,
    attachment_path TEXT,
    extra           TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS bills_due ON bills (due_date);

"""

COLUMNS = ("issue_date", "due_date", "period_start", "period_end", "total_due")
FIELD_TO_COLUMN = {"photo_path": "attachment_path"}  # parser field name -> column
DROP = {"needs_review"}                              # becomes `status`, not stored in extra


def connect(path=DB_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # web server and CLI can use the file at the same time
    conn.executescript(SCHEMA)
    return conn


def _text(value):
    return None if value is None else str(value)


def add_bill(conn, vendor, message_id, fields: dict):
    """Store one parsed bill. Returns the new id, or None if message_id was already stored."""
    row = {"vendor": vendor, "message_id": message_id,
           "status": "needs_review" if fields.get("needs_review") else "unpaid"}
    extra = {}
    for key, value in fields.items():
        if key in DROP:
            continue
        if key in COLUMNS:
            row[key] = _text(value)
        elif key in FIELD_TO_COLUMN:
            row[FIELD_TO_COLUMN[key]] = _text(value)
        else:
            extra[key] = value
    row["extra"] = json.dumps(extra, default=str, ensure_ascii=False)
    cols = ", ".join(row)
    marks = ", ".join(f":{c}" for c in row)
    cur = conn.execute(f"INSERT INTO bills ({cols}) VALUES ({marks}) ON CONFLICT(message_id) DO NOTHING", row)
    conn.commit()
    return cur.lastrowid if cur.rowcount else None


def _to_dict(r: sqlite3.Row):
    bill = dict(r)
    bill["total_due"] = Decimal(bill["total_due"]) if bill["total_due"] is not None else None
    bill["extra"] = json.loads(bill["extra"])
    bill["overdue"] = (bill["status"] == "unpaid" and bill["due_date"] is not None
                       and bill["due_date"] < date.today().isoformat())
    return bill


def list_bills(conn, vendor=None, status=None):
    """Bills newest first, optionally filtered by vendor and/or status."""
    where, args = [], []
    if vendor:
        where.append("vendor = ?"); args.append(vendor)
    if status:
        where.append("status = ?"); args.append(status)
    sql = "SELECT * FROM bills" + (" WHERE " + " AND ".join(where) if where else "")
    sql += " ORDER BY COALESCE(due_date, issue_date) DESC, id DESC"
    return [_to_dict(r) for r in conn.execute(sql, args)]


def get_bill(conn, bill_id):
    r = conn.execute("SELECT * FROM bills WHERE id = ?", (bill_id,)).fetchone()
    return _to_dict(r) if r else None


def set_amount(conn, bill_id, amount: Decimal):
    """Fill in a reviewed amount (koinoxrista); moves needs_review -> unpaid."""
    conn.execute("UPDATE bills SET total_due = ?, status = CASE status WHEN 'needs_review' THEN 'unpaid' ELSE status END "
                 "WHERE id = ?", (str(amount), bill_id))
    conn.commit()


def mark_paid(conn, bill_id, paid_on: date | None = None):
    conn.execute("UPDATE bills SET status = 'paid', paid_on = ? WHERE id = ? AND status = 'unpaid'",
                 ((paid_on or date.today()).isoformat(), bill_id))
    conn.commit()


def mark_unpaid(conn, bill_id):
    """Undo mark_paid."""
    conn.execute("UPDATE bills SET status = 'unpaid', paid_on = NULL WHERE id = ? AND status = 'paid'", (bill_id,))
    conn.commit()
