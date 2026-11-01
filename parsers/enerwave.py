"""Enerwave e-bill (noreply@ebill-enerwave.gr).

Bill fields come from the HTML body (Greek half; an English copy follows it).
Each label is on its own line, the value on the next:
  Συνολικό ποσό πληρωμής:      ###.##€
  Ημ. λήξης Λογαριασμού:       ##-##-####
  Κωδικός Πληρωμής:            RF#######################
  Ποσό τρέχοντος Λογαριασμού:  ###.##€
  Ημ. Έκδοσης Λογαριασμού:     ##-##-####
  Προηγούμενο Ανεξόφλητο
  (κατά την ημ. έκδοσης):      ###.##€

Meter readings come from the PDF (sent as text/plain). The table labels
(Τελευταία / Προηγούμενη / Διαφορά / Κατανάλωση / Αρ. Μετρητή) are not in
pdftotext's output, only the numbers, as five lines holding one integer each:
  ####  last
  ####  previous
  ###   difference
  ###   consumption (kWh)
  ######## meter number
They are found by shape and confirmed by arithmetic: last - previous == difference.
The difference is only used for that check; it is not returned.
"""
import re
from email.message import EmailMessage

from parsers.common import ParseError, amount, gr_date, html_lines, next_line, pdf_lines

NUMBER_ONLY = re.compile(r"^\d+$")


def meter_readings(lines):
    for i in range(len(lines) - 4):
        block = lines[i : i + 5]
        if not all(NUMBER_ONLY.match(line) for line in block):
            continue
        last, previous, diff, consumption = (int(n) for n in block[:4])
        if last - previous == diff:
            return {
                "meter_last": last,
                "meter_previous": previous,
                "consumption_kwh": consumption,
                "meter_number": block[4],
            }
    raise ParseError("meter readings block not found in PDF")


def parse(msg: EmailMessage, bill: dict) -> dict:
    lines = html_lines(msg)
    return {
        "total_due": amount(next_line(lines, "Συνολικό ποσό πληρωμής")),
        "due_date": gr_date(next_line(lines, "Ημ. λήξης Λογαριασμού")),
        "payment_code": next_line(lines, "Κωδικός Πληρωμής"),
        "current_charges": amount(next_line(lines, "Ποσό τρέχοντος Λογαριασμού")),
        "issue_date": gr_date(next_line(lines, "Ημ. Έκδοσης Λογαριασμού")),
        "previous_balance": amount(next_line(lines, "(κατά την ημ. έκδοσης)")),
        **meter_readings(pdf_lines(msg)),
    }
