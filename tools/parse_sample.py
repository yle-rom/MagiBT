"""Run a vendor parser on a saved .eml and print the fields.

Usage:
  python tools/parse_sample.py vodafone samples/vodafone.eml          # digits masked
  python tools/parse_sample.py vodafone samples/vodafone.eml --show   # real values, local only
"""
import email
import email.policy
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # so `parsers` imports when run from anywhere

import config  # noqa: E402
from parsers import get_parser  # noqa: E402


def bill_config(name):
    for bill in config.load()["bill"]:
        if bill["name"] == name:
            return bill
    sys.exit(f"no bill named {name!r} in bills.toml")


def main():
    name, path = sys.argv[1], sys.argv[2]
    show = "--show" in sys.argv
    msg = email.message_from_bytes(Path(path).read_bytes(), policy=email.policy.default)
    for key, value in get_parser(name)(msg, bill_config(name)).items():
        text = ", ".join(map(str, value)) if isinstance(value, list) else str(value)
        print(f"{key:18} {text if show else re.sub(r'[0-9]', '#', text)}")


if __name__ == "__main__":
    main()
