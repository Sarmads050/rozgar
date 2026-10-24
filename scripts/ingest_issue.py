#!/usr/bin/env python3
"""Turn a "Post a job" GitHub issue into a row in data/manual-jobs.json.

GitHub renders an issue form as:

    ### Job title
    <blank>
    Junior Clerk
    <blank>
    ### Employer name
    ...

So parsing is a simple label → value walk. Everything is validated here rather
than in the workflow, so a bad submission produces a readable comment on the
issue instead of a red Action.
"""
import json
import os
import re
import sys
from datetime import date, datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANUAL = os.path.join(ROOT, "data", "manual-jobs.json")

REQUIRED = ("job title", "employer name", "sector", "city", "what the job involves",
            "last date to apply")

SECTOR = {"government": "government", "private": "private",
          "semi-government": "government", "ngo / ingo": "private",
          "remote / international": "private"}

CATEGORY_RULES = [
    ("Information Technology", ("software", "developer", "engineer (it)", "data", "network",
                                "devops", "programmer", "web", "cyber", "computer")),
    ("Health & Medical", ("nurse", "doctor", "medical", "lab", "pharmac", "health", "mbbs",
                          "dispenser", "paramedic", "radiolog", "dental")),
    ("Education & Teaching", ("teacher", "lecturer", "educator", "instructor", "professor",
                              "school", "college", "tutor")),
    ("Engineering", ("civil engineer", "mechanical", "electrical", "quantity", "site engineer",
                     "sub engineer", "surveyor")),
    ("Finance & Accounting", ("account", "finance", "audit", "tax", "cashier", "treasurer")),
    ("Sales", ("sales", "business development", "marketing executive", "retail")),
    ("Marketing", ("marketing", "brand", "seo", "content", "social media")),
    ("Admin & Clerical", ("clerk", "admin", "assistant", "reception", "office", "steno",
                          "typist", "record")),
    ("Customer Support", ("support", "call centre", "call center", "helpdesk", "customer service")),
    ("Forces & Security", ("police", "army", "constable", "soldier", "security guard", "ranger")),
    ("Support Staff / Class IV", ("naib qasid", "chowkidar", "sweeper", "driver", "malhi",
                                  "attendant", "bearer", "cook", "gardener")),
]


def field(body: str, label: str) -> str:
    """Value of one rendered form field."""
    pattern = re.compile(r"^###\s*" + re.escape(label) + r"\s*$\n?(.*?)(?=^###\s|\Z)",
                         re.I | re.S | re.M)
    m = pattern.search(body or "")
    if not m:
        return ""
    val = m.group(1).strip()
    if val in ("_No response_", "No response", "-", "None"):
        return ""
    return re.sub(r"\s*\n\s*", " ", val).strip()


def one_line(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0].rstrip(",;") + "…"


def slugify(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return text[:60] or "job"


def parse_date(raw: str):
    raw = (raw or "").strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y",
                "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def guess_category(title: str, desc: str) -> str:
    blob = f"{title} {desc}".lower()
    for name, keys in CATEGORY_RULES:
        if any(k in blob for k in keys):
            return name
    return "Government / Other" if "government" in blob else "Admin & Clerical"


def guess_level(title: str, exp: str) -> str:
    blob = f"{title} {exp}".lower()
    if any(k in blob for k in ("director", "manager", "head", "chief", " gm")):
        return "Senior"
    if any(k in blob for k in ("intern", "trainee", "fresh", "entry")):
        return "Entry"
    return "Mid"


def fail(msg: str) -> None:
    print(f"::error::{msg}")
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a", encoding="utf-8") as fh:
        fh.write("ok=false\n")
        fh.write("message<<" + "EOF\n" + msg + "\nEOF\n")
    sys.exit(0)


def main() -> int:
    body = os.environ.get("BODY", "")
    if not body.strip():
        fail("The issue body was empty. Use the “Post a job” form instead of a blank issue.")

    missing = [label for label in REQUIRED if not field(body, label)]
    if missing:
        fail("These required fields are empty: " + ", ".join(missing) + ".")

    title = one_line(field(body, "Job title"), 110)
    company = one_line(field(body, "Employer name"), 90)
    sector_raw = field(body, "Sector").lower()
    city = one_line(field(body, "City"), 60)
    desc = field(body, "What the job involves")
    last_raw = field(body, "Last date to apply")

    last = parse_date(last_raw)
    if not last:
        fail(f"“{last_raw}” is not a date I can read. Use the format 2026-11-15.")
    today = date.today()
    if last < today:
        fail("The closing date has already passed. Submit again with the correct date.")
    if last > today + timedelta(days=365):
        fail("A closing date more than a year away is almost always a typo. Please check it.")

    apply_url = field(body, "Apply link")
    apply_email = field(body, "Apply email")
    how = field(body, "How to apply") or "See the employer's advertisement for the application procedure."

    if not apply_url and not apply_email:
        fail("Add either an apply link (https://…) or an apply email — candidates need a way to apply.")
    if apply_url and not re.match(r"^https?://", apply_url, re.I):
        apply_url = "https://" + apply_url
    if apply_url and re.search(r"(bit\.ly|tinyurl|t\.co|linktr\.ee|forms\.gle)", apply_url, re.I):
        fail("Shortened or form-builder links hide the real employer. Use the employer's own page.")
    if apply_url and not re.match(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", apply_email or "x@y.zz", re.I):
        fail("The apply email does not look like an email address.")
    if re.search(r"(registration|processing|application)\s*fee|رسید|فیس", desc + " " + how, re.I):
        fail("This looks like it charges candidates a fee. RozgarJobs does not publish paid-application jobs.")

    vacancies = re.sub(r"[^0-9]", "", field(body, "Number of vacancies"))
    salary = one_line(field(body, "Salary or pay scale"), 70)
    bps = ""
    m = re.search(r"bps[\s-]*(\d{1,2})", f"{salary} {title} {desc}", re.I)
    if m:
        bps = f"BPS-{int(m.group(1)):02d}"

    qual = one_line(field(body, "Minimum qualification"), 80)
    exp = one_line(field(body, "Experience required"), 60)
    age = one_line(field(body, "Age limit"), 40)
    remote = bool(re.search(r"\bremote\b|work from home|wfh", city, re.I))

    row = {
        "title": title,
        "company": company,
        "employer_display": company,
        "location": "Remote" if remote else (city if "pakistan" in city.lower() else f"{city}, Pakistan"),
        "remote": remote,
        "type": "Full Time",
        "sector": SECTOR.get(sector_raw, "private"),
        "category": guess_category(title, desc),
        "level": guess_level(title, exp),
        "qualification": qual,
        "experience": exp or "Not specified",
        "age_limit": age,
        "vacancies": int(vacancies) if vacancies else None,
        "bps": bps,
        "salary": salary,
        "posted": today.isoformat(),
        "last_date": last.isoformat(),
        "how_to_apply": one_line(how, 400),
        "apply_url": apply_url,
        "contact_email": apply_email,
        "description": one_line(desc, 1200),
        "tags": [t for t in {title.split()[0], guess_category(title, desc)} if t],
        "source": "Employer submission",
        "source_url": apply_url,
        "employer_submitted": True,
        "issue_number": os.environ.get("ISSUE_NUMBER") or None,
    }
    row = {k: v for k, v in row.items() if v not in ("", None, [], 0)}

    rows = []
    if os.path.exists(MANUAL):
        with open(MANUAL, encoding="utf-8") as fh:
            rows = json.load(fh)

    key = (row["title"].lower(), row["company"].lower(), row["last_date"])
    for old in rows:
        if (old.get("title", "").lower(), old.get("company", "").lower(),
                old.get("last_date")) == key:
            fail("This exact job is already on the site — nothing to add.")

    # expired manual rows are dropped on every ingest so the file stays small
    rows = [r for r in rows if (r.get("last_date") or "9999") >= today.isoformat()]
    rows.append(row)

    with open(MANUAL, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    path = f"jobs/{slugify(title)}-{slugify(company)[:20]}.html"
    msg = (f"**{title}** at {company}\n\n"
           f"Closes {last.isoformat()} · {row['location']} · {row.get('category', '')}\n\n"
           f"Detail page: `{path}` (rebuilt in the next hourly run).")
    print(msg)
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a", encoding="utf-8") as fh:
        fh.write("ok=true\n")
        fh.write(f"title={title[:80]}\n")
        fh.write("message<<" + "EOF\n" + msg + "\nEOF\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
