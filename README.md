# MagiBT

Tracks household bills locally: bill emails are read over IMAP, parsed per vendor, and stored in SQLite. Two front ends share the same data: a terminal UI (`magibt`) and a small web page.

![magibt demo](demo/magibt.gif)

*Demo data, made up: `demo/seed.py`.*

## What it does

- **Reads bill emails** through Proton Bridge (local IMAP), read-only, and parses each vendor's format: HTML bodies, PDF text, photos.
- **Tracks status**: unpaid, paid, overdue (computed from the due date, never stored), and "needs amount" for bills that arrive as a photo.
- **Monthly entries** for bills with no email (a loan), and a **subscriptions** tab with monthly/yearly totals.
- **Keeps the original email** of every bill, viewable offline in a sandboxed page.

## Architecture

```
 Proton Bridge (127.0.0.1:1143)            bills.toml
   started on demand                       (senders, subjects, fixed
          │ IMAP, read-only                 payment details, subscriptions)
          ▼                                        │
 magibt/ingest ──► magibt/parsers/<vendor>.py ◄─────┘
       │                (one file per vendor)
       ▼
 magibt/storage: SQLite (bills) + original .eml files
          ▲                       ▲
          │                       │
   web/ (server + static)   tui/ (magibt, terminal UI)
   127.0.0.1 only           f fetches, p marks paid
```

## Design notes

- **One parser per vendor** behind one interface, `parse(msg, bill) -> dict`. Shared fields are columns; vendor-specific ones go in a JSON `extra` column, so a new vendor needs no schema change.
- **Idempotent ingest**: bills are deduplicated by `Message-ID`, so fetching again never adds duplicates.
- **No orphan processes**: Bridge and the web server are children that die with their parent, even on `SIGKILL` (Linux `PR_SET_PDEATHSIG`).
- **Bridge start-up race**: Bridge opens its port seconds before it accepts logins; the client retries only on those specific errors.
- **Local-only web UI**: binds to `127.0.0.1`, accepts only JSON POSTs with a localhost `Host` header (blocks other sites and DNS rebinding). Original emails render in a sandboxed iframe with a strict CSP: no scripts, no remote images or tracking pixels.
- **No secrets in code or config**: the IMAP password is read from `pass` (GPG-encrypted); personal config is gitignored.
- **OCR tried and dropped**: building-fee sheets arrive as phone photos; Tesseract was not reliable on them, so that amount is entered by hand.

## Run the demo

Needs Python 3.11+, standard library only. The real ingest also uses `pass`, Proton Bridge and `pdftotext` (poppler).

```sh
python -m demo.seed
MAGIBT_CONFIG=bills.example.toml MAGIBT_DATA=demo/data tui/magibt.py
```

Keys: `j/k` move · `space` vendor history · `p` paid · `a` amount · `l` payment details and links · `h` back · `tab` subscriptions · `q` quit. Fetching (`f`) needs a real Proton Bridge.

## Layout

| Path | Role |
|---|---|
| `magibt/` | Core package, no UI code: `config`, `storage/` (SQLite, saved emails), `ingest/` (Bridge, IMAP, fetch), `parsers/` (one per vendor), `recurring`, `subscriptions`, `proc` (child processes) |
| `tui/` | Terminal UI, `tui/magibt.py` (executable; symlink it onto PATH) |
| `web/` | Web server and JSON API (`python -m web.server`), page in `static/` |
| `tools/` | Dev tools for writing parsers, run as `python -m tools.<name>` (digits masked by default) |
| `demo/` | Demo seed and the vhs tape for the GIF |
| `bills.example.toml` | Example config with made-up values |
| `local/` | Gitignored: real config, data, email samples, private notes |
