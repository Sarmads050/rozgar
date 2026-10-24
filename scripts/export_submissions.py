#!/usr/bin/env python3
"""Pull approved employer submissions out of Supabase into data/manual-jobs.json.

This is the bridge between the live layer and the static site:

    employer form → Supabase (status='pending')
                  → a human approves the row
                  → THIS SCRIPT copies it into the repo
                  → the normal build turns it into a real HTML page

The order matters. Nothing is published until it has been copied into the repo,
so a spam burst or a bad row in the database can never reach Google.

Needs one secret: SUPABASE_SERVICE_KEY (service_role key).
The service key bypasses Row Level Security, which is exactly why it must live
in GitHub Secrets and never in data/site-config.json or in the browser.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "data", "site-config.json")
MANUAL = os.path.join(ROOT, "data", "manual-jobs.json")

CATEGORY_RULES = [
    ("Information Technology", ("software", "developer", "programmer", "data", "network",
                                "devops", "web", "cyber", "computer", "it ")),
    ("Health & Medical", ("nurse", "doctor", "medical", "lab", "pharmac", "health", "mbbs",
                          "dispenser", "paramedic", "radiolog", "dental")),
    ("Education & Teaching", ("teacher", "lecturer", "educator", "instructor", "professor",
                              "school", "college", "tutor")),
    ("Engineering", ("civil engineer", "mechanical", "electrical", "quantity", "site engineer",
                     "sub engineer", "surveyor", "engineer")),
    ("Finance & Accounting", ("account", "finance", "audit", "tax", "cashier", "treasurer")),
    ("Sales", ("sales", "business development", "retail")),
    ("Marketing", ("marketing", "brand", "seo", "content", "social media")),
    ("Admin & Clerical", ("clerk", "admin", "assistant", "reception", "office", "steno",
                          "typist", "record")),
    ("Customer Support", ("support", "call centre", "call center", "helpdesk", "customer service")),
    ("Forces & Security", ("police", "army", "constable", "soldier", "security guard", "ranger")),
    ("Support Staff / Class IV", ("naib qasid", "chowkidar", "sweeper", "driver", "malhi",
                                  "attendant", "bearer", "cook", "gardener")),
]


def load_config():
    try:
        with open(CONFIG, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def fetch(sql_filter):
    cfg = load_config()
    supa = cfg.get("supabase") or {}
    url = (os.environ.get("SUPABASE_URL") or supa.get("url") or "").rstrip("/")
    key = (os.environ.get("SUPABASE_SERVICE_KEY") or "").strip()

    if not url or not key:
        print("Supabase not configured (need URL + SUPABASE_SERVICE_KEY) — skipping.")
        return None

    endpoint = f"{url}/rest/v1/job_submissions?{sql_filter}"
    req = urllib.request.Request(endpoint, headers={
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        print(f"Supabase returned {e.code}: {e.read()[:200]!r}")
        return None
    except Exception as e:  # noqa: BLE001
        print(f"Supabase unreachable: {type(e).__name__}: {e}")
        return None


def guess_category(title, desc):
    blob = f"{title} {desc}".lower()
    for name, keys in CATEGORY_RULES:
        if any(k in blob for k in keys):
            return name
    return "Admin & Clerical"


def guess_level(title, exp):
    blob = f"{title} {exp or ''}".lower()
    if any(k in blob for k in ("director", "manager", "head", "chief", "gm")):
        return "Senior"
    if any(k in blob for k in ("intern", "trainee", "fresh", "entry")):
        return "Entry"
    return "Mid"


def to_row(sub):
    """Supabase row → the shape data/manual-jobs.json already understands."""
    title = (sub.get("title") or "").strip()
    company = (sub.get("company") or "").strip()
    city = (sub.get("city") or "").strip()
    desc = (sub.get("description") or "").strip()
    sector = sub.get("sector") or "private"

    remote = bool(re.search(r"\bremote\b|work from home|wfh", city, re.I))
    location = ("Remote" if remote
                else city if "pakistan" in city.lower()
                else f"{city}, Pakistan")

    salary = (sub.get("salary") or "").strip()
    bps = (sub.get("bps") or "").strip()
    if not bps:
        m = re.search(r"bps[\s-]*(\d{1,2})", f"{salary} {title} {desc}", re.I)
        if m:
            bps = f"BPS-{int(m.group(1)):02d}"

    row = {
        "title": title,
        "company": company,
        "employer_display": company,
        "location": location,
        "remote": remote,
        "type": "Full Time",
        "sector": "government" if sector in ("government", "semi-government") else "private",
        "category": guess_category(title, desc),
        "level": guess_level(title, sub.get("experience")),
        "qualification": (sub.get("qualification") or "").strip(),
        "experience": (sub.get("experience") or "Not specified").strip(),
        "age_limit": (sub.get("age_limit") or "").strip(),
        "vacancies": sub.get("vacancies"),
        "bps": bps,
        "salary": salary,
        "posted": (sub.get("created_at") or "")[:10] or date.today().isoformat(),
        "last_date": sub.get("last_date") or "",
        "how_to_apply": (sub.get("how_to_apply") or "").strip() or
                        "See the employer's advertisement for the application procedure.",
        "apply_url": (sub.get("apply_url") or "").strip(),
        "contact_email": (sub.get("apply_email") or "").strip(),
        "description": desc,
        "tags": [guess_category(title, desc)],
        "source": "Employer submission",
        "source_url": (sub.get("apply_url") or "").strip(),
        "employer_submitted": True,
        "submission_id": sub.get("id"),
    }
    return {k: v for k, v in row.items() if v not in ("", None, [], 0)}


def main():
    rows = fetch("select=*&status=eq.approved&last_date=gte." + date.today().isoformat() +
                 "&order=created_at.desc&limit=200")
    if rows is None:
        print("Nothing exported — the build keeps using the existing manual jobs.")
        return 0

    if not rows:
        print("No approved submissions waiting in Supabase.")
        return 0

    existing = []
    if os.path.exists(MANUAL):
        try:
            with open(MANUAL, encoding="utf-8") as fh:
                existing = json.load(fh)
        except ValueError:
            existing = []

    # keep hand-written rows, replace anything that came from Supabase before
    kept = [r for r in existing if not r.get("submission_id")]
    have = {(r.get("title", "").lower(), r.get("company", "").lower()) for r in kept}

    added = 0
    for sub in rows:
        row = to_row(sub)
        if not row.get("title") or not row.get("company") or not row.get("last_date"):
            continue
        key = (row["title"].lower(), row["company"].lower())
        if key in have:
            continue
        have.add(key)
        kept.append(row)
        added += 1

    today = date.today().isoformat()
    kept = [r for r in kept if (r.get("last_date") or "9999") >= today]

    with open(MANUAL, "w", encoding="utf-8") as fh:
        json.dump(kept, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print(f"Exported {added} approved submission(s); {len(kept)} rows in data/manual-jobs.json.")
    return 1 if added else 0


if __name__ == "__main__":
    sys.exit(main())
