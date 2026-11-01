"""Helpers shared by vendor parsers: email -> text lines, label lookup, Greek number/date formats."""
import email.utils
import re
import subprocess
from datetime import date, datetime
from decimal import Decimal
from email.message import EmailMessage
from html.parser import HTMLParser
from pathlib import Path

import config


class ParseError(Exception):
    pass


class NotABill(Exception):
    """Raised by a parser for an email from the right sender that is not a bill (e.g. a reply)."""


class _TextOnly(HTMLParser):
    """HTML -> text, one line per block element, script/style dropped."""
    BLOCK = {"p", "div", "br", "tr", "td", "li", "h1", "h2", "h3", "h4", "table"}

    def __init__(self):
        super().__init__()
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_lines(msg: EmailMessage):
    """Non-empty, whitespace-collapsed text lines of the email's HTML body."""
    part = msg.get_body(preferencelist=("html",))
    if part is None:
        raise ParseError("no HTML body")
    p = _TextOnly()
    p.feed(part.get_content())
    lines = (" ".join(line.split()) for line in "".join(p.out).splitlines())
    return [line for line in lines if line]


def find(lines, label, exact=False):
    """Index of the first line starting with `label` (or equal to it, with exact=True)."""
    for i, line in enumerate(lines):
        if line == label if exact else line.startswith(label):
            return i
    raise ParseError(f"label not found: {label!r}")


def value_after_colon(lines, label):
    """'Label: value' on one line -> 'value'."""
    return lines[find(lines, label)].split(":", 1)[1].strip()


def next_line(lines, label, exact=False):
    """Label on one line, value on the next."""
    i = find(lines, label, exact)
    if i + 1 >= len(lines):
        raise ParseError(f"no value after {label!r}")
    return lines[i + 1]


def pdf_lines(msg: EmailMessage):
    """Text lines of the first PDF attachment (pdftotext -layout), stripped, non-empty.

    Detected by the %PDF magic bytes, not the MIME type: Enerwave labels its PDF text/plain.
    """
    for part in msg.walk():
        data = part.get_payload(decode=True)
        if isinstance(data, bytes) and data.startswith(b"%PDF"):
            out = subprocess.run(["pdftotext", "-layout", "-", "-"], input=data, capture_output=True, check=True)
            lines = out.stdout.decode("utf-8", "replace").splitlines()
            return [line.strip() for line in lines if line.strip()]
    raise ParseError("no PDF attachment")


ATTACHMENTS = config.DATA_DIR / "attachments"
JPEG_MAGIC = b"\xff\xd8\xff"


def email_date(msg: EmailMessage) -> date:
    """Date the sender sent the email (Date header)."""
    return email.utils.parsedate_to_datetime(msg["Date"]).date()


def jpeg_bytes(msg: EmailMessage) -> bytes:
    """Bytes of the first JPEG attachment, found by magic bytes."""
    for part in msg.walk():
        data = part.get_payload(decode=True)
        if isinstance(data, bytes) and data.startswith(JPEG_MAGIC):
            return data
    raise ParseError("no JPEG attachment")


def save_attachment(data: bytes, bill_name: str, filename: str) -> Path:
    """Write to data/attachments/<bill>/<filename>; same name overwrites, so re-parsing is safe."""
    folder = ATTACHMENTS / bill_name
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / filename
    path.write_bytes(data)
    return path


def amount(text):
    """Money in either format -> Decimal: '1.234,56 €' or '123.45€'.

    The last '.' or ',' is the decimal separator when exactly 2 digits follow it;
    every other separator is a thousands separator.
    """
    clean = text.replace("€", "").strip()
    m = re.search(r"[.,](\d{2})$", clean)
    if m:
        whole = re.sub(r"[.,]", "", clean[: m.start()])
        return Decimal(f"{whole}.{m.group(1)}")
    return Decimal(re.sub(r"[.,]", "", clean))


def gr_date(text) -> date:
    """'28/10/2026' or '28-10-2026' -> date(2026, 10, 28)."""
    return datetime.strptime(text.strip().replace("-", "/"), "%d/%m/%Y").date()
