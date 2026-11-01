"""Show an email's structure and text with personal values masked.

Usage:
  python -m tools.inspect_eml local/samples/enerwave.eml [more.eml ...]

Prints the MIME tree (type, filename, size) and the text of plain/HTML
bodies and PDF attachments (via pdftotext -layout), with:
  - every digit replaced by '#'   (45,30 € -> ##,## €)
  - URLs replaced by <url>        (they often carry tokens)
  - email addresses replaced by <email>
Images (JPEG/PNG) are OCR'd with tesseract (Greek + English) and masked the same way.
Names and street names are letters, so they are NOT masked: review before sharing.
"""
import email
import email.policy
import email.header
import re
import subprocess
import sys
import tempfile
from email.message import MIMEPart
from html.parser import HTMLParser
from pathlib import Path

URL = re.compile(r"https?://\S+|www\.\S+", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
DIGIT = re.compile(r"\d")
BLANKS = re.compile(r"\n\s*\n+")


def mask(text):
    text = URL.sub("<url>", text)
    text = EMAIL.sub("<email>", text)
    return DIGIT.sub("#", text)


class TextOnly(HTMLParser):
    """HTML -> text: one line per block, script/style dropped."""
    BLOCK = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "table", "td"}

    def __init__(self):
        super().__init__()
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag in self.BLOCK:
            self.out.append("\n" if tag != "td" else " | ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_text(html):
    p = TextOnly()
    p.feed(html)
    lines = (" ".join(line.split()) for line in "".join(p.out).splitlines())
    return "\n".join(line for line in lines if line.strip(" |"))


def pdf_text(data):
    with tempfile.TemporaryDirectory() as d:
        pdf = Path(d) / "a.pdf"
        pdf.write_bytes(data)
        out = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True)
    return out.stdout if out.returncode == 0 else f"[pdftotext failed: {out.stderr.strip()}]"


IMAGE_MAGIC = (b"\xff\xd8\xff", b"\x89PNG")  # JPEG, PNG


def ocr_text(data):
    out = subprocess.run(["tesseract", "stdin", "stdout", "-l", "ell+eng"], input=data, capture_output=True)
    if out.returncode != 0:
        return f"[tesseract failed: {out.stderr.decode('utf-8', 'replace').strip()}]"
    return out.stdout.decode("utf-8", "replace")


def decode(value):
    parts = email.header.decode_header(value or "")
    return "".join(p.decode(c or "utf-8", "replace") if isinstance(p, bytes) else p for p, c in parts)


def show(part: MIMEPart, depth=0):
    pad = "  " * depth
    ctype = part.get_content_type()
    name = decode(part.get_filename()) if part.get_filename() else ""
    payload = part.get_payload(decode=True)
    size = len(payload) if isinstance(payload, bytes) else 0
    print(f"{pad}- {ctype}" + (f"  file={mask(name)}" if name else "") + (f"  {size} B" if size else ""))

    if part.is_multipart():
        for sub in part.iter_parts():
            show(sub, depth + 1)
        return
    if not isinstance(payload, bytes):
        return

    # Trust the bytes, not the label: senders mislabel attachments
    # (Enerwave sends its PDF as text/plain).
    text = None
    if payload.startswith(b"%PDF"):
        text = pdf_text(payload)
    elif payload.startswith(IMAGE_MAGIC):
        text = ocr_text(payload)
    elif name:
        return  # other attachments: listed above, never printed
    elif ctype == "text/plain":
        text = payload.decode(part.get_content_charset() or "utf-8", "replace")
    elif ctype == "text/html":
        text = html_text(payload.decode(part.get_content_charset() or "utf-8", "replace"))
    if text:
        body = BLANKS.sub("\n\n", mask(text)).strip()
        print(f"{pad}  ---- text ----")
        print("\n".join(pad + "  " + line for line in body.splitlines()))
        print(f"{pad}  ---- end ----")


def main():
    for path in sys.argv[1:]:
        msg = email.message_from_bytes(Path(path).read_bytes(), policy=email.policy.default)
        print(f"######## {path}")
        print(f"Subject: {mask(decode(msg['Subject']))}")
        show(msg)
        print()


if __name__ == "__main__":
    main()
