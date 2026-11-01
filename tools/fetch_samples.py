"""Find bill emails over IMAP and save samples as .eml for parser design.

Bills and their sender rules live in bills.toml (project root).

Usage:
  python tools/fetch_samples.py list
  python tools/fetch_samples.py save

list: print every match per bill, newest first (headers only).
save: write the newest match per bill to samples/<name>.eml.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import mail  # noqa: E402

SAMPLES = ROOT / "samples"


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "list"
    imap = mail.connect()
    try:
        for bill in mail.load_bills():
            if not bill["from"]:
                print(f"== {bill['name']}: skipped (no sender in bills.toml)")
                continue
            found = mail.matches(imap, bill)
            print(f"== {bill['name']}: {len(found)} emails")
            if mode == "list":
                for _, h in found:
                    print(f"   {mail.msg_date(h):%Y-%m-%d} | {mail.decode(h['From'])} | to {mail.decode(h['To'])} | {mail.decode(h['Subject'])}")
            elif mode == "save" and found:
                SAMPLES.mkdir(exist_ok=True)
                path = SAMPLES / f"{bill['name']}.eml"
                path.write_bytes(mail.fetch_raw(imap, found[0][0]))
                print(f"   saved {path}")
    finally:
        imap.logout()


if __name__ == "__main__":
    main()
