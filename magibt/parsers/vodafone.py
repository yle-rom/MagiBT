"""Vodafone My eBill (noreply_ebill@vodafone.com): all fields are in the HTML body.

Layout (digits masked):
  Λογαριασμός Vodafone Οκτωβρίου ####
  Ημερομηνία έκδοσης: ##/##/####
  Μητρώο συνδρομητή: ##########
  Αριθμός/οί τηλεφώνου: ##########
  Περίοδος λογαριασμού: ##/##/####-##/##/####
  Κωδικός πληρωμής: RF#######################
  Τρέχουσες οφειλές         <- amount on the next line
  Πληρωμή έως: ##/##/####
  Προηγούμενο υπόλοιπο      <- amount on the next line
  Συνολικό οφειλόμενο ποσό  <- amount on the next line
"""
from email.message import EmailMessage

from magibt.parsers.common import amount, find, gr_date, html_lines, next_line, value_after_colon


def parse(msg: EmailMessage, bill: dict) -> dict:
    lines = html_lines(msg)
    start, end = value_after_colon(lines, "Περίοδος λογαριασμού").split("-")
    return {
        "title": lines[find(lines, "Λογαριασμός Vodafone")],
        "issue_date": gr_date(value_after_colon(lines, "Ημερομηνία έκδοσης")),
        "subscriber_id": value_after_colon(lines, "Μητρώο συνδρομητή"),
        "phone_numbers": [n.strip() for n in value_after_colon(lines, "Αριθμός/οί τηλεφώνου").split(",")],
        "payment_code": value_after_colon(lines, "Κωδικός πληρωμής"),
        "current_charges": amount(next_line(lines, "Τρέχουσες οφειλές")),
        "due_date": gr_date(value_after_colon(lines, "Πληρωμή έως")),
        "previous_balance": amount(next_line(lines, "Προηγούμενο υπόλοιπο")),
        "total_due": amount(next_line(lines, "Συνολικό οφειλόμενο ποσό")),
        "period_start": gr_date(start),
        "period_end": gr_date(end),
    }
