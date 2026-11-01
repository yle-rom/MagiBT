"""IMAP access through Proton Bridge, plus the bills.toml loader.

Read-only: the folder is opened read-only and every fetch uses BODY.PEEK,
so nothing is marked as read.
"""
import email
import email.header
import email.policy
import email.utils
import imaplib
import ssl
import subprocess
import time
from datetime import datetime, timezone
from email.message import EmailMessage, Message

from magibt import config

HOST, PORT = "127.0.0.1", 1143
FOLDER = '"All Mail"'
PASS_ENTRY = "billing/bridge-imap"
OLDEST = datetime.min.replace(tzinfo=timezone.utc)
LOGIN_WAIT = 30                          # seconds to wait for a just-started Bridge
NOT_READY = ("no such user", "too many login attempts")


class BridgeError(Exception):
    pass


def load_bills():
    return config.load()["bill"]


def _password():
    out = subprocess.run(["pass", "show", PASS_ENTRY], capture_output=True, text=True, check=True)
    return out.stdout.splitlines()[0]


def connect():
    """Logged-in, read-only IMAP session on All Mail. Needs Bridge running."""
    # Bridge uses a self-signed cert on loopback. Traffic never leaves the
    # machine, so skipping verification here is acceptable.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    user, password = config.load()["imap"]["user"], _password()
    deadline = time.monotonic() + LOGIN_WAIT
    while True:
        try:
            imap = imaplib.IMAP4(HOST, PORT)
        except ConnectionRefusedError:
            raise BridgeError(f"Proton Bridge is not running (nothing on {HOST}:{PORT})") from None
        imap.starttls(ssl_context=ctx)
        try:
            imap.login(user, password)
            break
        except imaplib.IMAP4.error as e:
            imap.shutdown()
            # A freshly started Bridge opens its port seconds before the account is loaded:
            # until then it answers "no such user", and rate-limits fast retries.
            if not any(s in str(e) for s in NOT_READY) or time.monotonic() > deadline:
                raise BridgeError(f"IMAP login failed: {e}") from None
            time.sleep(2)
    imap.select(FOLDER, readonly=True)
    return imap


def decode(value):
    parts = email.header.decode_header(value or "")
    return "".join(p.decode(c or "utf-8", "replace") if isinstance(p, bytes) else p for p, c in parts)


def msg_date(h: Message):
    try:
        return email.utils.parsedate_to_datetime(h["Date"])
    except (TypeError, ValueError):
        return OLDEST


def fetch_parts(imap, nums, query):
    """Fetch `query` for message numbers; return [(num, raw_bytes)]."""
    _, data = imap.fetch(b",".join(nums), query)
    out = []
    for item in data:
        if isinstance(item, tuple):  # (b'12 (BODY[...] {n}', payload); bare b')' items are separators
            out.append((item[0].split()[0], item[1]))
    return out


def matches(imap, bill):
    """Messages matching the bill's senders (and subject), newest first, as [(num, headers)]."""
    nums = set()
    for sender in bill["from"]:
        _, data = imap.search(None, "FROM", f'"{sender}"')
        if data and data[0]:
            nums.update(data[0].split())
    if not nums:
        return []
    found = []
    query = "(BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID)])"
    for num, raw in fetch_parts(imap, sorted(nums), query):
        h = email.message_from_bytes(raw)
        # Subject filter runs here, not in IMAP SEARCH: Greek text there needs CHARSET support.
        if bill.get("subject") and bill["subject"] not in decode(h["Subject"]):
            continue
        found.append((num, h))
    found.sort(key=lambda item: msg_date(item[1]), reverse=True)
    return found


def fetch_message(imap, num) -> EmailMessage:
    (_, raw), = fetch_parts(imap, [num], "(BODY.PEEK[])")
    return email.message_from_bytes(raw, policy=email.policy.default)


def find_by_message_id(imap, message_id):
    """Message number for a Message-ID, or None."""
    _, data = imap.search(None, "HEADER", "Message-ID", f'"{message_id}"')
    nums = data[0].split() if data and data[0] else []
    return nums[0] if nums else None


def fetch_raw(imap, num) -> bytes:
    (_, raw), = fetch_parts(imap, [num], "(BODY.PEEK[])")
    return raw
