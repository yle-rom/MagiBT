"""Koinoxrista (building fees) from the building manager.

The sheet arrives as a phone photo (JPG). OCR was tested and is not reliable
(rotated photo, grid lines over the digits, no readable labels), so the
amount is entered by hand: this parser saves the photo, returns its path,
and marks the bill for review. Emails without a photo (replies) are not bills.

Recipient name, IBAN and payment comment never change, so they come from bills.toml.
"""
from email.message import EmailMessage

from parsers.common import NotABill, ParseError, email_date, jpeg_bytes, save_attachment


def parse(msg: EmailMessage, bill: dict) -> dict:
    try:
        jpg = jpeg_bytes(msg)
    except ParseError:
        raise NotABill("no photo (a reply, not a bill)") from None
    sent = email_date(msg)
    photo = save_attachment(jpg, bill["name"], f"{sent.isoformat()}.jpg")
    return {
        "issue_date": sent,
        "total_due": None,       # entered by hand from the photo
        "needs_review": True,
        "photo_path": str(photo),
        "recipient_name": bill.get("recipient_name", ""),
        "iban": bill.get("iban", ""),
        "payment_comment": bill.get("payment_comment", ""),
    }
