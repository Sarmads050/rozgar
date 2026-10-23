#!/usr/bin/env python3
"""
add_job.py — add one local / employer job in a few easy questions.

    python3 scripts/add_job.py

It asks the questions one by one, checks the answers, and appends the job to
data/manual-jobs.json. Press Enter to skip anything that is optional.

You can also pass everything at once (good for scripts):

    python3 scripts/add_job.py --title "Lab Technician" --company "DHQ Hospital Sukkur" \
        --location "Sukkur, Pakistan" --sector government --last-date 2026-11-15
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANUAL = os.path.join(ROOT, "data", "manual-jobs.json")

SECTORS = ("government", "private", "contract", "internship", "remote")
TYPES = ("Full Time", "Part Time", "Contract", "Freelance", "Internship")


def ask(label, default="", required=False, choices=None):
    while True:
        suffix = f" [{default}]" if default else (" *" if required else "")
        val = input(f"{label}{suffix}: ").strip() or default
        if required and not val:
            print("  This one is required. Please type something.")
            continue
        if choices and val and val.lower() not in [c.lower() for c in choices]:
            print(f"  Choose one of: {', '.join(choices)}")
            continue
        return val


def yes_no(label, default=False):
    return (ask(f"{label} (y/n)", "y" if default else "n").lower().startswith("y"))


def normalise_date(value):
    """Accept 2026-11-20, 20-11-2026, 20/11/2026 or 20 Nov 2026."""
    v = (value or "").strip()
    if not v:
        return ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        return v
    m = re.fullmatch(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", v)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    months = {m: i + 1 for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
    m = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})", v)
    if m and m.group(2)[:3].lower() in months:
        return f"{m.group(3)}-{months[m.group(2)[:3].lower()]:02d}-{int(m.group(1)):02d}"
    raise ValueError(f"'{value}' is not a date I understand. Use 2026-11-20.")


def build_job(args):
    print("\n── Add a job to Rozgar ─────────────────────────────")
    print("Type the details. Press Enter to skip an optional question.\n")

    title = args.title or ask("Job title (e.g. Stenographer BPS-14)", required=True)
    company = args.company or ask("Employer name (as candidates should see it)", required=True)
    location = args.location or ask("City and country", "Karachi, Pakistan")

    sector = (args.sector or ask(f"Sector ({'/'.join(SECTORS)})", "private")).lower()
    if sector not in SECTORS:
        sector = "private"

    jtype = args.job_type or ask(f"Job type ({'/'.join(TYPES)})", "Full Time")
    if jtype not in TYPES:
        jtype = "Full Time"

    category = args.category or ask("Category (e.g. Health & Medical, IT & Computer)", "")
    qualification = ask("Qualification needed (e.g. BSc Nursing, B.Com)", "")
    experience = ask("Experience needed (e.g. 2 years)", "")
    age_limit = ask("Age limit (e.g. 18-30 years)", "")
    vacancies = ask("How many vacancies?", "")
    bps = ask("BPS scale (government jobs only, e.g. BPS-09)", "")
    salary = ask("Salary (e.g. PKR 85,000 / month)", "")

    last_date = ""
    while True:
        raw = ask("Last date to apply (YYYY-MM-DD)", "")
        try:
            last_date = normalise_date(raw)
            break
        except ValueError as e:
            print(" ", e)

    print("\nHow should people apply? Write the real instructions.")
    how_to_apply = ask("Application steps (one line)", "")
    apply_url = ask("Application link (https://…)", "")
    contact_email = ask("Contact email (optional)", "")

    print("\nDescription — 2 to 4 sentences about the work. This goes on the job page and poster.")
    description = args.description or ask("Description", "")

    tags = [t.strip() for t in ask("Skills, separated by commas", "").split(",") if t.strip()][:8]

    job = {
        "title": title,
        "company": company,
        "location": location,
        "remote": sector == "remote",
        "type": jtype,
        "sector": sector,
        "category": category,
        "qualification": qualification,
        "experience": experience,
        "age_limit": age_limit,
        "vacancies": int(vacancies) if str(vacancies).isdigit() else (vacancies or ""),
        "bps": bps,
        "salary": salary,
        "posted": date.today().isoformat(),
        "last_date": last_date,
        "how_to_apply": how_to_apply,
        "apply_url": apply_url,
        "contact_email": contact_email,
        "description": description,
        "tags": tags,
    }
    return {k: v for k, v in job.items() if v not in ("", [], None)}


def check(job):
    problems = []
    if len(job.get("title", "")) < 3:
        problems.append("Title is too short.")
    if len(job.get("company", "")) < 2:
        problems.append("Employer name is too short.")
    if job.get("last_date"):
        try:
            d = date.fromisoformat(job["last_date"])
            if d < date.today():
                problems.append(f"Last date {d} is already in the past.")
        except ValueError:
            problems.append("Last date must look like 2026-11-20.")
    if job.get("apply_url") and not job["apply_url"].startswith(("http://", "https://")):
        problems.append("Application link must start with http:// or https://")
    if len(job.get("description", "").split()) < 12:
        problems.append("Description is very short — 12+ words keeps the page useful for Google.")
    return problems


def main():
    ap = argparse.ArgumentParser(description="Add one job to data/manual-jobs.json")
    for f in ("title", "company", "location", "sector", "category", "description"):
        ap.add_argument("--" + f, default="")
    ap.add_argument("--job-type", default="")
    ap.add_argument("--last-date", default="")
    a = ap.parse_args()

    try:
        rows = json.load(open(MANUAL, encoding="utf-8")) if os.path.exists(MANUAL) else []
    except Exception as e:
        print(f"Could not read {MANUAL}: {e}")
        return 1
    if not isinstance(rows, list):
        rows = []

    job = build_job(a)
    problems = check(job)
    if problems:
        print("\n⚠  Fix these before saving:")
        for p in problems:
            print("   -", p)
        if not yes_no("Save anyway?"):
            print("Nothing saved.")
            return 1

    print("\n── Preview ─────────────────────────────────────────")
    for k, v in job.items():
        print(f"  {k:14s} {v}")

    if not yes_no("\nSave this job?", True):
        print("Nothing saved.")
        return 0

    rows.append(job)
    with open(MANUAL, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Saved. {len(rows)} job(s) in data/manual-jobs.json")
    print("  Next: python3 scripts/fetch_jobs.py   (builds the page + poster)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
