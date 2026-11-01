"""Where MagiBT finds its config and data. Both can be moved with env vars (the demo does):

  MAGIBT_CONFIG  the bills.toml to read     (default: local/bills.toml)
  MAGIBT_DATA    data dir: billing.db, emails/, attachments/   (default: local/data/)

local/ holds everything personal (config, data, samples) and is gitignored;
bills.example.toml shows its layout with made-up values.
"""
import os
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # repo root
LOCAL = ROOT / "local"                          # gitignored: everything personal
BILLS_FILE = Path(os.environ.get("MAGIBT_CONFIG", LOCAL / "bills.toml")).resolve()
DATA_DIR = Path(os.environ.get("MAGIBT_DATA", LOCAL / "data")).resolve()
SAMPLES = LOCAL / "samples"


def load():
    with open(BILLS_FILE, "rb") as f:
        return tomllib.load(f)
