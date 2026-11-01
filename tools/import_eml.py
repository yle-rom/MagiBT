"""Import a bill from a saved .eml file (e.g. one still sent to another inbox).

Usage:
  python tools/import_eml.py ydata samples/ydata.eml

Same path as ingest: the vendor's parser, then the database, deduplicated by
Message-ID, so importing the same file twice adds nothing.
"""
import email
import email.policy
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import db  # noqa: E402
import emails  # noqa: E402
import mail  # noqa: E402
from parsers import get_parser  # noqa: E402


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
