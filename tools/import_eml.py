"""Import a bill from a saved .eml file (e.g. one still sent to another inbox).

Usage:
  python -m tools.import_eml ydata local/samples/ydata.eml

Same path as ingest: the vendor's parser, then the database, deduplicated by
Message-ID, so importing the same file twice adds nothing.
"""
import email
import email.policy
import sys
from contextlib import closing
from pathlib import Path

from magibt.ingest import mail
from magibt.parsers import get_parser
from magibt.storage import db, emails


def main():
    vendor, path = sys.argv[1], Path(sys.argv[2])
    bill = next((b for b in mail.load_bills() if b["name"] == vendor), None)
    if bill is None:
        sys.exit(f"no bill named {vendor!r} in bills.toml")
    msg = email.message_from_bytes(path.read_bytes(), policy=email.policy.default)
    fields = get_parser(vendor)(msg, bill)
    with closing(db.connect()) as conn:
        new_id = db.add_bill(conn, vendor, msg["Message-ID"], fields)
        if not new_id:  # already stored: still make sure the copy exists
            row = conn.execute("SELECT id FROM bills WHERE message_id = ?", (msg["Message-ID"],)).fetchone()
            bill_id = row[0]
        else:
            bill_id = new_id
    if not emails.has(bill_id):
        emails.save(bill_id, path.read_bytes())
    print(f"added {vendor} #{new_id}" if new_id else f"already stored ({path.name})")


if __name__ == "__main__":
    main()
