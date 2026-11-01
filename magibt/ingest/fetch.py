"""Fetch bill emails over IMAP, parse them, store new ones in the database.

Usage:
  python -m magibt.ingest.fetch

Only emails whose Message-ID is not in the database yet are downloaded and
parsed, so running it again is cheap and safe. A parser failure on one
email is reported and skipped; it never stops the others. Emails a parser
flags as NotABill (e.g. replies) are counted, not reported.
"""
import importlib.util

import email
import email.policy

from magibt.ingest import mail
from magibt.parsers import get_parser
from magibt.parsers.common import NotABill, ParseError
from magibt.storage import db, emails


def has_parser(name):
    return importlib.util.find_spec(f"magibt.parsers.{name}") is not None


def known_ids(conn):
    return {r[0] for r in conn.execute("SELECT message_id FROM bills WHERE message_id IS NOT NULL")}


def backfill(conn, imap):
    """Download the source email for stored bills that have no local copy yet. Returns how many."""
    count = 0
    rows = conn.execute("SELECT id, message_id FROM bills "
                        "WHERE message_id IS NOT NULL AND message_id NOT LIKE 'recurring:%'")
    for bill_id, mid in rows.fetchall():
        if emails.has(bill_id):
            continue
        num = mail.find_by_message_id(imap, mid)
        if num:
            emails.save(bill_id, mail.fetch_raw(imap, num))
            count += 1
    return count


def run(conn):
    """Returns a summary: {"added": [(vendor, id)], "skipped": n, "ignored": n, "backfilled": n, "failed": [(vendor, subject, error)]}."""
    summary = {"added": [], "skipped": 0, "ignored": 0, "failed": []}
    seen = known_ids(conn)
    imap = mail.connect()
    try:
        for bill in mail.load_bills():
            if not bill["from"] or not has_parser(bill["name"]):
                continue
            parse = get_parser(bill["name"])
            for num, h in mail.matches(imap, bill):
                mid = h["Message-ID"]
                if mid in seen:
                    summary["skipped"] += 1
                    continue
                raw = mail.fetch_raw(imap, num)
                msg = email.message_from_bytes(raw, policy=email.policy.default)
                try:
                    fields = parse(msg, bill)
                except NotABill:
                    summary["ignored"] += 1
                    continue
                except (ParseError, ValueError, IndexError) as e:
                    summary["failed"].append((bill["name"], mail.decode(h["Subject"]), str(e)))
                    continue
                new_id = db.add_bill(conn, bill["name"], mid, fields)
                seen.add(mid)
                if new_id:
                    emails.save(new_id, raw)
                    summary["added"].append((bill["name"], new_id))
        summary["backfilled"] = backfill(conn, imap)
    finally:
        imap.logout()
    return summary


def main():
    conn = db.connect()
    s = run(conn)
    print(f"added {len(s['added'])}, already stored {s['skipped']}, not bills {s['ignored']}, email copies backfilled {s['backfilled']}, failed {len(s['failed'])}")
    for vendor, bill_id in s["added"]:
        print(f"  + {vendor} #{bill_id}")
    for vendor, subject, err in s["failed"]:
        print(f"  ! {vendor}: {subject} -> {err}")


if __name__ == "__main__":
    main()
