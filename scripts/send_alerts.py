#!/usr/bin/env python3
"""
send_alerts.py — Rozgar job alerts (email + WhatsApp), 100% free stack.

Kaise chalta hai
----------------
1. Ye script GitHub Action se ghanta-ghanta chalti hai (deploy ke baad).
2. Pichli baar ka jobs.json (git se) aur naya jobs.json compare karti hai.
3. Sirf woh jobs uthaati hai jo naye hain (id pehle nahi tha) + jinki last date
   guzar nahi chuki.
4. Har subscriber (Google Sheet → published CSV) ke filters check karti hai:
      city / category / qualification / keywords
5. Match hui to email bhejti hai (Resend ya Gmail SMTP) aur, agar set ho,
   WhatsApp channel/group par CallMeBot se post karti hai.

Environment variables (GitHub Secrets)
--------------------------------------
  RESEND_API_KEY     — resend.com se (3,000 emails/month free)
  ALERT_FROM_EMAIL   — e.g. alerts@rozgar.pk  (Resend verified domain)
  SMTP_HOST          — Gmail ke liye smtp.gmail.com  (Resend na ho to)
  SMTP_PORT          — 587
  SMTP_USER          — aapka Gmail address
  SMTP_PASS          — Gmail App Password (16 chars)
  SUBSCRIBERS_CSV    — subscribers sheet ka published CSV URL
  WHATSAPP_APIKEY    — CallMeBot API key (optional)
  WHATSAPP_PHONE     — CallMeBot phone number (optional, intl format)
  SITE_URL           — https://rozgar.pk

Sab secrets optional hain. Kuch bhi set na ho to script chup-chaap exit ho
jaati hai aur site simply "alerts jald aa raha hai" dikhati rehti hai.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import smtplib
import ssl
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JOBS_JSON = ROOT / "data" / "jobs.json"
STATE_FILE = ROOT / ".alerts-state.json"

SITE_URL = (os.environ.get("SITE_URL") or "https://rozgar.pk").rstrip("/")
MAX_EMAILS = int(os.environ.get("MAX_EMAILS_PER_RUN", "400"))


# ────────────────────────────────────────────────────────────── helpers
def log(msg: str) -> None:
    print(msg, flush=True)


def http(url: str, *, data: bytes | None = None, headers: dict | None = None,
         timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def esc(s) -> str:
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def pretty(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        return datetime.fromisoformat(str(iso)[:10]).strftime("%d %b %Y")
    except Exception:
        return str(iso)


def load_jobs() -> list[dict]:
    with open(JOBS_JSON, encoding="utf-8") as f:
        return json.load(f)["jobs"]


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"sent_ids": []}


def is_live(j: dict) -> bool:
    ld = (j.get("last_date") or "").strip()
    if not ld:
        return True
    try:
        return date.fromisoformat(ld[:10]) >= date.today()
    except Exception:
        return True


# ─────────────────────────────────────────────────────── subscribers
def fetch_subscribers() -> list[dict]:
    """Google Form → Sheet → publish as CSV → read here."""
    url = (os.environ.get("SUBSCRIBERS_CSV") or "").strip()
    if not url:
        return []
    try:
        raw = http(url).decode("utf-8-sig", errors="replace")
    except Exception as e:  # noqa: BLE001
        log(f"  ! subscribers CSV: {type(e).__name__}: {e}")
        return []

    wanted = {
        "email": ("email", "email address", "e-mail", "your email"),
        "city": ("city", "shahar", "location"),
        "category": ("category", "job category", "field"),
        "qualification": ("qualification", "education", "degree"),
        "keywords": ("keywords", "skills", "what jobs", "search"),
        "frequency": ("frequency", "how often", "digest"),
        "confirmed": ("confirmed", "double opt in", "opt-in"),
    }
    out = []
    for row in csv.DictReader(io.StringIO(raw)):
        rec = {}
        for key, names in wanted.items():
            for col, val in row.items():
                if col and col.strip().lower() in names:
                    rec[key] = (val or "").strip()
                    break
            rec.setdefault(key, "")
        email = rec["email"].lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", email):
            continue
        # double opt-in: agar column maujood hai to "yes" hi chale
        if "confirmed" in {c.strip().lower() for c in row if c}:
            if rec["confirmed"].strip().lower() not in ("yes", "y", "true", "1", "confirmed"):
                continue
        rec["email"] = email
        out.append(rec)
    return out


def matches(job: dict, sub: dict) -> bool:
    """Subscriber ke filters — khali field ka matlab "sab kuch"."""
    city = (sub.get("city") or "").lower().strip()
    if city and city not in ("any", "all", "koi bhi", "all cities"):
        loc = (job.get("location") or "").lower()
        if city not in loc and not job.get("remote"):
            return False

    cat = (sub.get("category") or "").lower().strip()
    if cat and cat not in ("any", "all", "koi bhi"):
        hay = f'{job.get("category","")} {job.get("title","")}'.lower()
        if cat.split("&")[0].strip() not in hay:
            return False

    qual = (sub.get("qualification") or "").lower().strip()
    if qual and qual not in ("any", "all", "koi bhi"):
        hay = f'{job.get("qualification","")} {job.get("title","")}'.lower()
        key = "matric" if "matric" in qual else "inter" if "inter" in qual else \
              "bachelor" if ("bachelor" in qual or "graduat" in qual) else \
              "master" if "master" in qual else qual.split()[0]
        if key and key not in hay:
            return False

    kw = (sub.get("keywords") or "").lower().strip()
    if kw:
        hay = f'{job.get("title","")} {job.get("company","")} {job.get("tags","")} ' \
              f'{job.get("category","")}'.lower()
        if not any(w in hay for w in re.split(r"[,\s]+", kw) if len(w) > 2):
            return False
    return True


# ──────────────────────────────────────────────────────── email
SHELL = """<!DOCTYPE html>
<html><body style="margin:0;background:#f2f5f6;font-family:-apple-system,'Segoe UI',Roboto,Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f2f5f6;padding:24px 12px">
<tr><td align="center">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#fff;border-radius:14px;overflow:hidden;border:1px solid #e2e8ea">
  <tr><td style="background:#0f766e;padding:20px 24px">
    <a href="{site}" style="text-decoration:none;color:#fff;font-weight:800;font-size:19px;letter-spacing:-.4px">
      Rozgar<span style="font-weight:400;opacity:.75;font-size:13px">&nbsp; Pakistan jobs</span>
    </a>
  </td></tr>
  <tr><td style="padding:22px 24px 6px">
    <p style="margin:0 0 4px;font-size:16px;color:#0e1518;font-weight:700">{headline}</p>
    <p style="margin:0;font-size:13px;color:#65767d">{subline}</p>
  </td></tr>
  <tr><td style="padding:8px 24px 4px">{cards}</td></tr>
  <tr><td style="padding:16px 24px 24px">
    <a href="{site}" style="display:inline-block;background:#0f766e;color:#fff;text-decoration:none;
       font-weight:700;font-size:14px;padding:11px 20px;border-radius:999px">Saari jobs dekhein</a>
  </td></tr>
  <tr><td style="padding:0 24px 22px;border-top:1px solid #eef2f3">
    <p style="font-size:11.5px;color:#8b9aa1;line-height:1.6;margin:14px 0 0">
      Ye email aapne Rozgar par job alert subscribe kiya tha isliye aayi hai.
      <a href="{unsub}" style="color:#8b9aa1">Unsubscribe</a>.
      Rozgar kabhi candidate se paisa nahi maangta — koi fee maange to report karein.
    </p>
  </td></tr>
</table>
</td></tr></table></body></html>"""

CARD = """<table width="100%" cellpadding="0" cellspacing="0" style="margin:8px 0 10px;border:1px solid #e6ecee;border-radius:12px">
<tr><td style="padding:14px 16px">
  <a href="{url}" style="text-decoration:none;color:#0e1518;font-weight:700;font-size:15px;line-height:1.3;display:block">{title}</a>
  <p style="margin:5px 0 0;font-size:13px;color:#5b6c73">{company}{loc}</p>
  <p style="margin:6px 0 0;font-size:12px;color:#8b9aa1">
    {meta}{deadline}
  </p>
</td></tr></table>"""


def render_email(jobs: list[dict], sub: dict) -> tuple[str, str]:
    cards = ""
    for j in jobs[:12]:
        url = f"{SITE_URL}/jobs/{j['slug']}.html"
        meta = " · ".join(x for x in (j.get("qualification"), j.get("type")) if x)
        dl = (f' · <strong style="color:{("#b45309" if j.get("days_left") is not None and j["days_left"] <= 5 else "#5b6c73")}">'
              f"Last date {pretty(j.get('last_date'))}</strong>") if j.get("last_date") else ""
        cards += CARD.format(
            url=esc(url), title=esc(j["title"]), company=esc(j.get("company", "")),
            loc=(f' · {esc(j.get("location"))}' if j.get("location") else ""),
            meta=esc(meta), deadline=dl)

    n = len(jobs)
    subject = (f"{n} nayi job — {jobs[0]['title'][:60]}" if n == 1
               else f"{n} nayi jobs aapke liye — Rozgar")
    html = SHELL.format(
        site=SITE_URL,
        headline=("Aapke liye 1 nayi job" if n == 1 else f"Aapke liye {n} nayi jobs"),
        subline=esc(" · ".join(x for x in (sub.get("city"), sub.get("category")) if x)
                    or "Pakistan bhar se latest vacancies"),
        cards=cards,
        unsub=f"{SITE_URL}/alerts.html?unsubscribe={urllib.parse.quote(sub['email'])}",
    )
    return subject, html


def send_email(to: str, subject: str, html: str) -> bool:
    body = html.encode("utf-8")
    api = os.environ.get("RESEND_API_KEY")
    sender = os.environ.get("ALERT_FROM_EMAIL") or os.environ.get("SMTP_USER")

    if api and sender:
        payload = json.dumps({"from": formataddr(("Rozgar Jobs", sender)),
                              "to": [to], "subject": subject, "html": html}).encode()
        try:
            req = urllib.request.Request(
                "https://api.resend.com/emails", data=payload,
                headers={"Authorization": f"Bearer {api}",
                         "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return 200 <= r.status < 300
        except Exception as e:  # noqa: BLE001
            log(f"  ! resend {to}: {e}")
            return False

    host, port = os.environ.get("SMTP_HOST", "smtp.gmail.com"), int(os.environ.get("SMTP_PORT", "587"))
    user, pwd = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASS")
    if not (user and pwd):
        return False

    msg = EmailMessage()
    msg["From"] = formataddr(("Rozgar Jobs", sender or user))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="rozgar.pk")
    msg["List-Unsubscribe"] = f"<{SITE_URL}/alerts.html>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg.set_content("Ye email HTML mein hai. Apna email client update karein.")
    msg.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(host, port, timeout=25) as s:
            s.starttls(context=ssl.create_default_context())
            s.login(user, pwd)
            s.send_message(msg)
        return True
    except Exception as e:  # noqa: BLE001
        log(f"  ! smtp {to}: {type(e).__name__}: {e}")
        return False


# ─────────────────────────────────────────────────────── whatsapp
def send_whatsapp(text: str) -> bool:
    """CallMeBot — free, personal-use gateway (channel/group broadcast)."""
    key = (os.environ.get("WHATSAPP_APIKEY") or "").strip()
    phone = (os.environ.get("WHATSAPP_PHONE") or "").replace(" ", "").replace("+", "").strip()
    if not (key and phone):
        return False
    url = ("https://api.callmebot.com/whatsapp.php?"
           + urllib.parse.urlencode({"phone": phone, "text": text, "apikey": key}))
    try:
        http(url, timeout=25)
        return True
    except Exception as e:  # noqa: BLE001
        log(f"  ! whatsapp: {type(e).__name__}: {e}")
        return False


def whatsapp_digest(jobs: list[dict]) -> str:
    lines = [f"*Rozgar* — {len(jobs)} nayi job{'s' if len(jobs) > 1 else ''} 🔔", ""]
    for j in jobs[:6]:
        lines.append(f"• *{j['title']}*")
        lines.append(f"  {j.get('company','')}" + (f" — {j['location']}" if j.get("location") else ""))
        if j.get("last_date"):
            lines.append(f"  Last date: {pretty(j['last_date'])}")
    if len(jobs) > 6:
        lines.append(f"…aur {len(jobs) - 6} zyada")
    lines += ["", f"Sab dekhein: {SITE_URL}"]
    return "\n".join(lines)


# ────────────────────────────────────────────────────────── main
def main() -> int:
    if not JOBS_JSON.exists():
        log("jobs.json nahi mila"); return 1

    jobs = [j for j in load_jobs() if is_live(j)]
    state = load_state()
    seen = set(state.get("sent_ids", []))

    # Pehli baar chalne par sab kuch "naya" hota hai — isliye baseline bana ke
    # chhod dete hain, warna 1200 emails ek saath chali jayengi.
    if not seen:
        log(f"Baseline set ({len(jobs)} jobs) — is run mein koi email nahi jayegi.")
        STATE_FILE.write_text(json.dumps({"sent_ids": [j["id"] for j in jobs][:5000],
                                          "baseline": datetime.now(timezone.utc).isoformat()}),
                              encoding="utf-8")
        return 0

    fresh = [j for j in jobs if j["id"] not in seen]
    fresh.sort(key=lambda j: -(j.get("published") or 0))
    log(f"{len(fresh)} nayi jobs mili")
    if not fresh:
        return 0

    subs = fetch_subscribers()
    log(f"{len(subs)} subscribers")

    sent = failed = 0
    for sub in subs[:MAX_EMAILS]:
        mine = [j for j in fresh if matches(j, sub)]
        if not mine:
            continue
        if sub.get("frequency", "").lower().startswith(("week", "hafta")):
            continue  # weekly digest separate cron se chalta hai
        subject, html = render_email(mine, sub)
        if send_email(sub["email"], subject, html):
            sent += 1
            time.sleep(0.34)  # Resend: 2 requests/second
        else:
            failed += 1

    if os.environ.get("WHATSAPP_APIKEY"):
        if send_whatsapp(whatsapp_digest(fresh)):
            log("  ✓ WhatsApp digest bheja gaya")

    ids = list(dict.fromkeys([j["id"] for j in jobs] + state.get("sent_ids", [])))[:5000]
    STATE_FILE.write_text(json.dumps({"sent_ids": ids,
                                      "last_run": datetime.now(timezone.utc).isoformat()}),
                          encoding="utf-8")
    log(f"Emails: {sent} bheji, {failed} fail")
    return 0


if __name__ == "__main__":
    sys.exit(main())
