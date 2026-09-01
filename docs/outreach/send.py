#!/usr/bin/env python3
"""Send the outreach drafts that have a verified address, from michael@crowelogic.com.

Reads recipients.csv (n,name,channel,to_name,to_email,status,sent_on). A row is sent only when
to_email is non-empty and status is not 'sent'. Each send attaches the investor report PDF,
records the SMTP result in sent-log.csv, and marks the row sent. --dry prints and sends nothing.
"""
import csv, glob, os, smtplib, ssl, sys, time
from email.message import EmailMessage

HERE = os.path.dirname(os.path.abspath(__file__))
DRY = "--dry" in sys.argv
ONLY = [a for a in sys.argv[1:] if a.isdigit()]
PDF = os.path.join(HERE, "crowe-sense-investor-report.pdf")

def draft_for(n):
    f = glob.glob(os.path.join(HERE, f"{int(n):02d}-*.md"))[0]
    text = open(f).read()
    body = text.split("\n---\n", 1)[1].lstrip("\n")
    lines = body.split("\n")
    subject = next(l for l in lines if l.startswith("Subject:")).split(":", 1)[1].strip()
    start = lines.index(next(l for l in lines if l.startswith("Subject:"))) + 1
    return subject, "\n".join(lines[start:]).strip() + "\n", os.path.basename(f)

rows = list(csv.DictReader(open(os.path.join(HERE, "recipients.csv"))))
todo = [r for r in rows if r["to_email"].strip() and r["status"] != "sent" and (not ONLY or r["n"] in ONLY)]
print(f"{len(todo)} to send, {sum(1 for r in rows if r['status']=='sent')} already sent, {len(rows)-len(todo)-sum(1 for r in rows if r['status']=='sent')} without an address")
if not todo: sys.exit(0)

frm = os.environ["ZOHO_MICHAEL_EMAIL"]; pw = os.environ.get("ZOHO_SMTP_PASS") or os.environ["ZOHO_MICHAEL_APP_PASSWORD"]
host = os.environ.get("ZOHO_SMTP_HOST", "smtp.zoho.com")
log = open(os.path.join(HERE, "sent-log.csv"), "a")
srv = None
if not DRY:
    srv = smtplib.SMTP(host, 587, timeout=30); srv.ehlo(); srv.starttls(context=ssl.create_default_context()); srv.ehlo(); srv.login(frm, pw)
for r in todo:
    subject, body, fname = draft_for(r["n"])
    to = r["to_email"].strip()
    msg = EmailMessage()
    msg["From"] = f"Michael Crowe <{frm}>"; msg["To"] = to; msg["Subject"] = subject
    msg["Reply-To"] = frm
    msg.set_content(body)
    msg.add_attachment(open(PDF, "rb").read(), maintype="application", subtype="pdf", filename="crowe-sense-investor-report.pdf")
    if DRY:
        print(f"[dry] {r['n']:>2} {r['name']} -> {to} | {subject} | {fname} | {len(body)} chars"); continue
    try:
        refused = srv.send_message(msg)
        result = "accepted" if not refused else f"refused:{refused}"
    except Exception as e:
        result = f"error:{type(e).__name__}:{str(e)[:120]}"
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    log.write(f"{r['n']},{r['name']!r},{to},{stamp},{result}\n"); log.flush()
    print(f"{r['n']:>2} {r['name']} -> {to}: {result}")
    if result == "accepted":
        r["status"] = "sent"; r["sent_on"] = stamp
    time.sleep(2)
if srv: srv.quit()
if not DRY:
    with open(os.path.join(HERE, "recipients.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
