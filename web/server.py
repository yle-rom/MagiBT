"""Local web UI: python -m web.server [--db PATH] [--port N] [--no-bridge]  ->  http://127.0.0.1:8421

Starts Proton Bridge with the server and stops it on exit (unless one is already running).

Stdlib only. Binds to 127.0.0.1, so nothing else on the network can reach it.

API:
  GET  /api/bills                     all bills (JSON)
  POST /api/fetch                     run ingest (needs Proton Bridge running)
  POST /api/bills/<id>/paid           {"paid": true|false}
  POST /api/bills/<id>/amount         {"amount": "41,22"}  (needs_review -> unpaid)
  GET  /api/bills/<id>/attachment     the saved photo (koinoxrista)
  GET  /api/subscriptions             static subscription list from bills.toml
  GET  /bills/<id>/email              viewer for the bill's original email
  GET  /api/bills/<id>/email/body     the email's own HTML, under a strict CSP
  GET  /api/bills/<id>/email/part/<n> attachment n (PDF, photo)
  GET  /api/bills/<id>/email.eml      raw source download

Protection against other websites in your browser calling this API:
  - POSTs must be Content-Type: application/json. A foreign page can only send
    that after a CORS preflight, which this server never approves.
  - The Host header must be 127.0.0.1/localhost (blocks DNS rebinding).
"""
import argparse
import signal
from contextlib import closing
from html import escape
import json
import mimetypes
import re
from urllib.parse import quote
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from magibt import recurring, subscriptions
from magibt.ingest import bridge, mail
from magibt.ingest import fetch as ingest
from magibt.parsers.common import ATTACHMENTS, amount as parse_amount
from magibt.storage import db, emails

STATIC = Path(__file__).resolve().parent / "static"
INDEX = STATIC / "index.html"
FAVICON = STATIC / "favicon.svg"
ALLOWED_HOSTS = {"127.0.0.1", "localhost"}
DB_FILE = db.DB_PATH  # replaced by --db
BRIDGE = None        # Bridge child process, if this server started one


def to_json(obj):
    return json.dumps(obj, default=str, ensure_ascii=False).encode()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # quieter: method + path only
        print(f"{self.command} {self.path}")

    # ---- helpers
    def send(self, status, body=b"", ctype="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def error(self, status, message):
        self.send(status, to_json({"error": message}))

    def host_ok(self):
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        return host in ALLOWED_HOSTS

    def json_body(self):
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            raise ValueError("Content-Type must be application/json")
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}")

    # ---- routes
    def do_GET(self):
        if not self.host_ok():
            return self.error(403, "bad host")
        if self.path == "/":
            return self.send(200, INDEX.read_bytes(), "text/html; charset=utf-8")
        if self.path in ("/favicon.svg", "/favicon.ico"):
            return self.send(200, FAVICON.read_bytes(), "image/svg+xml")
        if self.path == "/api/bills":
            with closing(db.connect(DB_FILE)) as conn:
                recurring.ensure(conn)  # adds this month's loan entry when the month changes
                bills = db.list_bills(conn)
            for b in bills:
                b["has_email"] = emails.has(b["id"])
            return self.send(200, to_json(bills))
        if self.path == "/api/subscriptions":
            return self.send(200, to_json(subscriptions.load()))
        m = re.fullmatch(r"/api/bills/(\d+)/attachment", self.path)
        if m:
            return self.attachment(int(m.group(1)))
        m = re.fullmatch(r"/bills/(\d+)/email|/api/bills/(\d+)/email/body|/api/bills/(\d+)/email/part/(\d+)"
                         r"|/api/bills/(\d+)/email\.eml", self.path)
        if m:
            return self.email_route(m)
        self.error(404, "not found")

    # ---- original email
    # The sender's HTML may hold scripts and tracking pixels. It is served on its
    # own URL with a CSP that forbids scripts and every remote load, and shown in a
    # sandboxed iframe (no scripts, unique origin), so it can neither run code on
    # this localhost app nor tell the sender it was opened.
    BODY_CSP = "default-src 'none'; img-src data:; style-src 'unsafe-inline'; font-src data:"

    def email_route(self, m):
        bill_id = int(next(g for g in m.groups() if g is not None))
        if not emails.has(bill_id):
            return self.error(404, "no stored email for this bill (run Fetch to backfill)")
        msg = emails.load(bill_id)
        if m.group(1):
            return self.send(200, self.viewer_page(bill_id, msg).encode(), "text/html; charset=utf-8")
        if m.group(2):
            self.send_response(200)
            body = emails.html_body(msg).encode()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Security-Policy", self.BODY_CSP)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return self.wfile.write(body)
        if m.group(3):
            wanted = int(m.group(4))
            for i, name, ctype, data in emails.attachments(msg):
                if i == wanted:
                    self.send_response(200)
                    self.send_header("Content-Type", ctype)
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header("Content-Disposition", f"inline; filename*=UTF-8''{quote(name)}")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    return self.wfile.write(data)
            return self.error(404, "no such attachment")
        raw = emails.path_for(bill_id).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "message/rfc822")
        self.send_header("Content-Disposition", f'attachment; filename="bill-{bill_id}.eml"')
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def viewer_page(self, bill_id, msg):
        links = "".join(
            f'<li><a href="/api/bills/{bill_id}/email/part/{i}" target="_blank">{escape(name)}</a> '
            f'<span>{escape(ctype)}, {len(data) // 1024} KB</span></li>'
            for i, name, ctype, data in emails.attachments(msg))
        rows = "".join(f"<tr><th>{k}</th><td>{escape(str(msg[k] or ''))}</td></tr>" for k in ("From", "To", "Date", "Subject"))
        return f'''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Bill #{bill_id} email</title>
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<style>
  :root {{ --bg:#fafafa; --fg:#1d1d1f; --muted:#6e6e73; --line:#e3e3e6; --accent:#2f6fed; }}
  @media (prefers-color-scheme: dark) {{ :root {{ --bg:#141416; --fg:#ececf0; --muted:#9a9aa2; --line:#2c2c31; --accent:#6b9bff; }} }}
  body {{ margin:0; padding:16px; background:var(--bg); color:var(--fg); font:14px/1.45 system-ui, sans-serif; }}
  main {{ max-width:1000px; margin:0 auto; }}
  a {{ color:var(--accent); }}
  table {{ border-collapse:collapse; margin:8px 0; }}
  th {{ text-align:left; color:var(--muted); font-weight:500; padding:2px 12px 2px 0; vertical-align:top; }}
  ul {{ padding-left:18px; }} li span {{ color:var(--muted); font-size:12px; }}
  iframe {{ width:100%; height:75vh; border:1px solid var(--line); border-radius:8px; background:#fff; }}
</style></head><body><main>
<p><a href="/">← Back</a> · <a href="/api/bills/{bill_id}/email.eml">Download .eml</a></p>
<table>{rows}</table>
{"<h3>Attachments</h3><ul>" + links + "</ul>" if links else ""}
<iframe sandbox src="/api/bills/{bill_id}/email/body" title="Original email"></iframe>
<p style="color:var(--muted);font-size:12px">Remote images and scripts in the email are blocked.</p>
</main></body></html>'''

    def do_POST(self):
        if not self.host_ok():
            return self.error(403, "bad host")
        try:
            body = self.json_body()
        except ValueError as e:
            return self.error(415, str(e))
        if self.path == "/api/fetch":
            return self.fetch()
        m = re.fullmatch(r"/api/bills/(\d+)/(paid|amount)", self.path)
        if not m:
            return self.error(404, "not found")
        bill_id, action = int(m.group(1)), m.group(2)
        with closing(db.connect(DB_FILE)) as conn:
            if not db.get_bill(conn, bill_id):
                return self.error(404, "no such bill")
            if action == "paid":
                (db.mark_paid if body.get("paid") else db.mark_unpaid)(conn, bill_id)
            else:
                try:
                    value = parse_amount(str(body.get("amount", "")))
                except InvalidOperation:
                    return self.error(400, "amount must look like 41,22")
                if value <= Decimal(0):
                    return self.error(400, "amount must be positive")
                db.set_amount(conn, bill_id, value)
            return self.send(200, to_json(db.get_bill(conn, bill_id)))

    def fetch(self):
        if BRIDGE is not None and not bridge.wait_ready(BRIDGE):
            return self.error(503, "Proton Bridge did not start (check the GPG passphrase prompt)")
        try:
            with closing(db.connect(DB_FILE)) as conn:
                summary = ingest.run(conn)
        except mail.BridgeError as e:
            return self.error(503, str(e))
        self.send(200, to_json(summary))

    def attachment(self, bill_id):
        with closing(db.connect(DB_FILE)) as conn:
            bill = db.get_bill(conn, bill_id)
        if not bill or not bill["attachment_path"]:
            return self.error(404, "no attachment")
        path = Path(bill["attachment_path"]).resolve()
        if not path.is_relative_to(ATTACHMENTS.resolve()) or not path.is_file():
            return self.error(404, "no attachment")
        self.send(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or "application/octet-stream")


def main():
    global DB_FILE, BRIDGE
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=db.DB_PATH)
    ap.add_argument("--port", type=int, default=8421)
    ap.add_argument("--no-bridge", action="store_true", help="don't start Proton Bridge")
    args = ap.parse_args()
    DB_FILE = args.db
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)

    if not args.no_bridge:
        BRIDGE = bridge.start()
        print("Proton Bridge: " + ("started (stops with the server)" if BRIDGE else "already running, leaving it alone"))
    # Closing the terminal sends SIGHUP and `kill` sends SIGTERM: treat both like Ctrl+C
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt))

    print(f"billing tracker on http://127.0.0.1:{args.port}  (db: {DB_FILE})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if BRIDGE:
            print("stopping Proton Bridge...")
            bridge.stop(BRIDGE)


if __name__ == "__main__":
    main()
