"""Local copies of the original bill emails: <data dir>/emails/<bill id>.eml (default local/data).

Kept so every bill can be checked against its source, offline, even if the
email is later deleted from the mailbox.
"""
import email
import email.policy
from email.message import EmailMessage
from pathlib import Path

from magibt import config

EMAILS = config.DATA_DIR / "emails"


def path_for(bill_id: int) -> Path:
    return EMAILS / f"{bill_id}.eml"


def has(bill_id: int) -> bool:
    return path_for(bill_id).is_file()


def save(bill_id: int, raw: bytes):
    EMAILS.mkdir(parents=True, exist_ok=True)
    path_for(bill_id).write_bytes(raw)


def load(bill_id: int) -> EmailMessage:
    return email.message_from_bytes(path_for(bill_id).read_bytes(), policy=email.policy.default)


def sniff_type(data: bytes, declared: str) -> str:
    """Real type from magic bytes; senders mislabel (Enerwave's PDF is 'text/plain')."""
    if data.startswith(b"%PDF"):
        return "application/pdf"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG"):
        return "image/png"
    return declared


def attachments(msg: EmailMessage):
    """[(index, filename, content_type, bytes)] for every attachment, in order."""
    out = []
    for i, part in enumerate(msg.iter_attachments()):
        data = part.get_payload(decode=True)
        if isinstance(data, bytes):
            out.append((i, part.get_filename() or f"attachment-{i}", sniff_type(data, part.get_content_type()), data))
    return out


def html_body(msg: EmailMessage) -> str:
    part = msg.get_body(preferencelist=("html", "plain"))
    if part is None:
        return "<p>(no body)</p>"
    text = part.get_content()
    if part.get_content_type() == "text/plain":
        from html import escape
        return f"<pre style='white-space:pre-wrap'>{escape(text)}</pre>"
    return text
