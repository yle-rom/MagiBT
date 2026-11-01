"""Ydata / ΔΕΥΑ Ιωαννίνων water bill (sent to Gmail for now; same format assumed on subs@).

All fields come from the HTML body: a table where each cell becomes its own
line, so every label is followed by its value (digits masked):
  ΣΥΝΟΛΟ ΤΡΕΧΟΝΤΟΣ ΛΟΓ/ΣΜΟΥ      ##,##
  ΠΡΟΗΓΟΥΜΕΝΗ ΟΦΕΙΛΗ             ##,##
  ΣΥΝΟΛΟ ΟΦΕΙΛΩΝ                 ##,##
  ΛΗΞΗ ΠΡΟΣΘΕΣΜΙΑΣ ΠΛΗΡΩΜΗΣ      ##/##/####
  ΑΡ. ΥΔΡΟΜΕΤΡΟΥ                 ##-####
  ΕΚΔΟΣΗ ΛΟΓ/ΣΜΟΥ                ##/##/####
  ΠΕΡΙΟΔΟΣ ΚΑΤΑΝΑΛΩΣΗΣ           ΑΠΟ: ##/##/####   ΕΩΣ:   ##/##/####
  Πρ. Μέτρηση / Νέα Μέτρηση / Κατανάλωση   ####  ####  ##
  Κωδικός πληρωμής μέσω ΔΙΑΣ     RF#######################

The two PDFs (bill copy, myDATA notice) are not needed.
"""
from email.message import EmailMessage

from magibt.parsers.common import amount, find, gr_date, html_lines, next_line


def parse(msg: EmailMessage, bill: dict) -> dict:
    lines = html_lines(msg)
    i = find(lines, "ΠΕΡΙΟΔΟΣ ΚΑΤΑΝΑΛΩΣΗΣ")  # next lines: 'ΑΠΟ: <date>', 'ΕΩΣ:', '<date>'
    return {
        "total_due": amount(next_line(lines, "ΣΥΝΟΛΟ ΟΦΕΙΛΩΝ", exact=True)),
        "due_date": gr_date(next_line(lines, "ΛΗΞΗ ΠΡΟΣΘΕΣΜΙΑΣ ΠΛΗΡΩΜΗΣ", exact=True)),
        "payment_code": next_line(lines, "Κωδικός πληρωμής μέσω ΔΙΑΣ", exact=True),
        "current_charges": amount(next_line(lines, "ΣΥΝΟΛΟ ΤΡΕΧΟΝΤΟΣ ΛΟΓ/ΣΜΟΥ", exact=True)),
        "issue_date": gr_date(next_line(lines, "ΕΚΔΟΣΗ ΛΟΓ/ΣΜΟΥ", exact=True)),
        "previous_balance": amount(next_line(lines, "ΠΡΟΗΓΟΥΜΕΝΗ ΟΦΕΙΛΗ", exact=True)),
        "period_start": gr_date(lines[i + 1].removeprefix("ΑΠΟ:")),
        "period_end": gr_date(lines[i + 3]),
        "meter_previous": int(next_line(lines, "Πρ. Μέτρηση", exact=True)),
        "meter_last": int(next_line(lines, "Νέα Μέτρηση", exact=True)),
        "consumption_m3": int(next_line(lines, "Κατανάλωση", exact=True)),
        "meter_number": next_line(lines, "ΑΡ. ΥΔΡΟΜΕΤΡΟΥ", exact=True),
    }
