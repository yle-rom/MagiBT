"""Where MagiBT finds its config and data. Both can be moved with env vars (the demo does):

  MAGIBT_CONFIG  the bills.toml to read     (default: bills.toml next to the code)
  MAGIBT_DATA    data dir: billing.db, emails/, attachments/   (default: data/)

bills.toml holds personal values (sender addresses, IBAN, amounts) and is gitignored;
bills.example.toml shows its layout with made-up values.
"""
import os
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BILLS_FILE = Path(os.environ.get("MAGIBT_CONFIG", ROOT / "bills.toml"))
DATA_DIR = Path(os.environ.get("MAGIBT_DATA", ROOT / "data"))


def load():
    with open(BILLS_FILE, "rb") as f:
        return tomllib.load(f)
