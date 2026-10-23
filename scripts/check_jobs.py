#!/usr/bin/env python3
"""
check_jobs.py — validate your local job files before you build.

    python3 scripts/check_jobs.py

Checks:
  • data/manual-jobs.json      (jobs you add by hand)
  • data/submissions.csv       (employer form exports, if the file exists)
  • data/jobs-template.csv     (the example sheet)

It prints one line per problem with the file and the row number, so nothing
silently disappears from the site.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

REQUIRED = ("title", "company")
VALID_SECTORS = {"government", "private", "contract", "internship", "remote"}
VALID_TYPES = {"full time", "part time", "contract", "freelance", "internship", "temporary"}
URL_RE = re.compile(r"^https?://", re.I)
MIN_DESC_WORDS = 12


def check_row(row, where, problems, seen):
    title = str(row.get("title") or "").strip()
    company = str(row.get("company") or "").strip()

    for field in REQUIRED:
        if not str(row.get(field) or "").strip():
            problems.append(f"{where}: '{field}' is empty — this job will be skipped.")

    if len(title) > 140:
        problems.append(f"{where}: title is longer than 140 characters.")
    if len(company) > 90:
        problems.append(f"{where}: company name is longer than 90 characters.")

    key = (title.lower(), company.lower(), str(row.get("location") or "").lower())
    if key in seen:
        problems.append(f"{where}: looks like a duplicate of an earlier row.")
    seen.add(key)

    sector = str(row.get("sector") or "").strip().lower()
    if sector and sector not in VALID_SECTORS:
        problems.append(f"{where}: sector '{sector}' is not one of {sorted(VALID_SECTORS)}.")

    jtype = str(row.get("type") or "").strip().lower()
    if jtype and jtype not in VALID_TYPES:
        problems.append(f"{where}: type '{jtype}' — use Full Time, Part Time, Contract, "
                        f"Freelance or Internship.")

    last = str(row.get("last_date") or "").strip()
    if last:
        try:
            if date.fromisoformat(last) < date.today():
                problems.append(f"{where}: last_date {last} has already passed — the job will be "
                                f"hidden from the site.")
        except ValueError:
            problems.append(f"{where}: last_date '{last}' must be YYYY-MM-DD.")

    url = str(row.get("apply_url") or row.get("url") or "").strip()
    if url and not URL_RE.match(url):
        problems.append(f"{where}: apply URL must start with http:// or https://")

    desc = str(row.get("description") or "").strip()
    if len(desc.split()) < MIN_DESC_WORDS:
        problems.append(f"{where}: description has {len(desc.split())} words — "
                        f"aim for {MIN_DESC_WORDS}+ so the page is not thin.")

    vacancies = row.get("vacancies")
    if vacancies not in (None, "") and not str(vacancies).isdigit():
        problems.append(f"{where}: vacancies should be a number, got '{vacancies}'.")


def check_manual(path):
    problems, seen = [], set()
    if not os.path.exists(path):
        return problems, 0
    try:
        rows = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        return [f"data/manual-jobs.json: cannot read JSON ({e})"], 0
    if not isinstance(rows, list):
        return ["data/manual-jobs.json: must be a list [ ... ] of jobs"], 0

    live = 0
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            problems.append(f"data/manual-jobs.json row {i}: not an object")
            continue
        check_row(row, f"data/manual-jobs.json row {i}", problems, seen)
        if not str(row.get("last_date") or "").strip():
            live += 1
        else:
            try:
                live += 1 if date.fromisoformat(row["last_date"]) >= date.today() else 0
            except ValueError:
                pass
    return problems, live


def check_csv(path, label):
    problems, seen, live = [], set(), 0
    if not os.path.exists(path):
        return problems, 0
    try:
        with open(path, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
    except Exception as e:
        return [f"{label}: cannot read CSV ({e})"], 0

    if rows:
        missing = [c for c in ("Job Title", "Company") if c not in rows[0]]
        if missing:
            problems.append(f"{label}: missing column(s) {missing}. "
                            f"Download the template again from data/jobs-template.csv.")

    for i, row in enumerate(rows, 2):
        norm = {
            "title": (row.get("Job Title") or "").strip(),
            "company": (row.get("Company") or "").strip(),
            "location": (row.get("Location") or "").strip(),
            "sector": (row.get("Sector") or "").strip(),
            "type": (row.get("Job Type") or "").strip(),
            "last_date": (row.get("Last Date") or "").strip(),
            "apply_url": (row.get("Apply URL") or "").strip(),
            "description": (row.get("Description") or "").strip(),
            "vacancies": (row.get("Vacancies") or "").strip(),
        }
        check_row(norm, f"{label} line {i}", problems, seen)
        live += 1
    return problems, live


def main():
    print("Checking local job files…\n")
    all_problems = []
    total_live = 0

    p, n = check_manual(os.path.join(DATA, "manual-jobs.json"))
    all_problems += p
    total_live += n
    print(f"  data/manual-jobs.json   {n:3d} usable job(s)")

    for name in ("submissions.csv", "jobs-template.csv"):
        p, n = check_csv(os.path.join(DATA, name), f"data/{name}")
        all_problems += p
        if name == "submissions.csv":
            total_live += n
            print(f"  data/submissions.csv    {n:3d} row(s)")

    print(f"\n  {total_live} job(s) will appear on the site.")

    if all_problems:
        print(f"\n{len(all_problems)} problem(s) found:\n")
        for prob in all_problems:
            print("  •", prob)
        print("\nFix these, then run: python3 scripts/fetch_jobs.py")
        return 1

    print("\n✓ Everything looks good.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
