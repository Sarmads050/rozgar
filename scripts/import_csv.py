#!/usr/bin/env python3
"""
import_csv.py — apni (local / employer) jobs CSV se add karein.

Kyun CSV?
---------
Google Form, Excel, ya Google Sheets ka "File → Download → CSV" — teeno se
sidha yahi format aata hai. Form se aayi submissions ko `data/submissions.csv`
ke naam se save karein, phir:

    python scripts/import_csv.py                     # submissions.csv → manual-jobs.json (add)
    python scripts/import_csv.py my-jobs.csv         # apni custom file
    python scripts/import_csv.py --replace           # poori list replace
    python scripts/import_csv.py --check             # sirf check, kuch nahi likhta

Har row ko validate karta hai aur masla ho to row number ke saath saaf error
deta hai — galat job chup-chaap skip nahi hoti.

Column names flexible hain ("Job Title", "title", "position" — sab chalta hai).
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "data" / "manual-jobs.json"

# ── column aliases ────────────────────────────────────────────────────────
ALIASES: dict[str, tuple[str, ...]] = {
    "title":          ("job title", "title", "position", "post", "designation"),
    "company":        ("company", "company name", "employer", "organization", "organisation"),
    "employer_display": ("employer display", "full employer name", "employer as shown"),
    "location":       ("location", "city", "job location", "duty station"),
    "remote":         ("remote", "work from home", "wfh", "remote?"),
    "type":           ("type", "job type", "employment type", "nature"),
    "sector":         ("sector", "government/private", "job sector"),
    "category":       ("category", "job category", "field", "department"),
    "level":          ("level", "experience level", "seniority"),
    "qualification":  ("qualification", "education", "degree", "required education"),
    "experience":     ("experience", "required experience", "min experience"),
    "age_limit":      ("age limit", "age", "maximum age"),
    "vacancies":      ("vacancies", "no of posts", "number of posts", "posts"),
    "bps":            ("bps", "grade", "pay scale", "bps/grade"),
    "salary":         ("salary", "pay", "package", "salary range"),
    "salary_min":     ("salary min", "minimum salary"),
    "salary_max":     ("salary max", "maximum salary"),
    "salary_currency": ("currency", "salary currency"),
    "salary_period":  ("salary period", "per", "salary unit"),
    "posted":         ("posted", "date posted", "posting date", "publish date"),
    "last_date":      ("last date", "last date to apply", "deadline", "closing date",
                       "apply by", "expiry"),
    "apply_url":      ("apply url", "apply link", "url", "link", "job link"),
    "how_to_apply":   ("how to apply", "apply instructions", "application process"),
    "contact_email":  ("contact email", "email", "hr email"),
    "description":    ("description", "job description", "details", "summary"),
    "tags":           ("tags", "skills", "keywords"),
    "source_url":     ("source url", "source", "original ad"),
    "employer_submitted": ("employer submitted", "submitted by employer"),
    "company_logo":   ("logo", "company logo", "logo url"),
}

REQUIRED = ("title", "company")

DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%d %b %Y",
                "%d %B %Y", "%b %d, %Y", "%Y/%m/%d")


def norm_key(k: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (k or "").lower()).strip()


def parse_date(v: str) -> str | None:
    v = (v or "").strip()
    if not v:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(v, fmt).date().isoformat()
        except ValueError:
            continue
    # Excel serial number
    if re.fullmatch(r"\d{5}", v):
        try:
            return (date(1899, 12, 30) + __import__("datetime").timedelta(days=int(v))).isoformat()
        except Exception:
            pass
    return None


def to_bool(v: str) -> bool:
    return (v or "").strip().lower() in ("1", "yes", "y", "true", "haan", "remote", "wfh")


def read_rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096); f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(f, dialect=dialect)
        rows = []
        for raw in reader:
            rec = {}
            for col, val in raw.items():
                k = norm_key(col)
                if not k:
                    continue
                for field, names in ALIASES.items():
                    if k in names and field not in rec:
                        rec[field] = (val or "").strip()
                        break
            rec["_raw_cols"] = list(raw.keys())
            rows.append(rec)
        return rows


def clean(rec: dict, n: int, errors: list[str]) -> dict | None:
    out: dict = {}
    for f in REQUIRED:
        if not rec.get(f):
            errors.append(f"row {n}: '{f}' khali hai (column '{ALIASES[f][0]}')")
            return None

    out["title"] = rec["title"]
    out["company"] = rec["company"]
    if rec.get("employer_display"):
        out["employer_display"] = rec["employer_display"]
    out["location"] = rec.get("location") or "Pakistan"
    out["remote"] = to_bool(rec.get("remote", ""))

    jtype = (rec.get("type") or "Full Time").strip().title()
    out["type"] = {"Fulltime": "Full Time", "Parttime": "Part Time"}.get(
        jtype.replace(" ", ""), jtype) if jtype not in ("Full Time", "Part Time") else jtype

    sector = (rec.get("sector") or "").strip().lower()
    out["sector"] = sector if sector in ("government", "private", "contract",
                                         "internship", "remote") else "private"

    for f in ("category", "level", "qualification", "experience", "age_limit",
              "bps", "salary", "contact_email", "how_to_apply", "source_url",
              "company_logo", "salary_currency", "salary_period"):
        if rec.get(f):
            out[f] = rec[f]

    if rec.get("vacancies"):
        v = re.sub(r"[^\d]", "", rec["vacancies"])
        out["vacancies"] = int(v) if v else rec["vacancies"]

    for f in ("salary_min", "salary_max"):
        if rec.get(f):
            try:
                out[f] = float(re.sub(r"[^\d.]", "", rec[f]))
            except ValueError:
                errors.append(f"row {n}: {f} number nahi hai ('{rec[f]}')")

    if rec.get("posted"):
        d = parse_date(rec["posted"])
        if d:
            out["posted"] = d
        else:
            errors.append(f"row {n}: posted date samajh nahi aayi ('{rec['posted']}') — YYYY-MM-DD likhein")

    if rec.get("last_date"):
        d = parse_date(rec["last_date"])
        if d:
            out["last_date"] = d
            if d < date.today().isoformat():
                errors.append(f"row {n}: last date ({d}) guzar chuki hai — job site par nahi aayegi")
        else:
            errors.append(f"row {n}: last date samajh nahi aayi ('{rec['last_date']}')")

    if rec.get("tags"):
        out["tags"] = [t.strip() for t in re.split(r"[,;|]", rec["tags"]) if t.strip()][:8]

    if rec.get("description"):
        out["description"] = rec["description"]
    elif rec.get("how_to_apply"):
        out["description"] = (f"{out['title']} at {out['company']}, {out['location']}. "
                              f"{rec['how_to_apply']}")
    else:
        errors.append(f"row {n}: description ya how_to_apply mein se ek zaroori hai")

    if rec.get("employer_submitted"):
        out["employer_submitted"] = to_bool(rec["employer_submitted"])

    if not out.get("apply_url") and not out.get("contact_email") and not out.get("how_to_apply"):
        errors.append(f"row {n}: apply ke liye kuch to ho — apply_url, contact_email ya how_to_apply")

    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?", default=str(ROOT / "data" / "submissions.csv"))
    ap.add_argument("--replace", action="store_true", help="purani list replace karein")
    ap.add_argument("--check", action="store_true", help="sirf validate, kuch na likhein")
    ap.add_argument("--out", default=str(TARGET))
    args = ap.parse_args()

    src = Path(args.csv)
    if not src.exists():
        print(f"✗ File nahi mili: {src}\n  Pehle CSV banayein — SETUP_GUIDE.md → Section 8.")
        return 1

    rows = read_rows(src)
    errors: list[str] = []
    jobs = [c for n, r in enumerate(rows, 2) if (c := clean(r, n, errors))]

    print(f"\n{src.name}: {len(rows)} rows  →  {len(jobs)} valid")
    if errors:
        print(f"\n{len(errors)} warning/masle:")
        for e in errors[:40]:
            print("  •", e)

    if args.check:
        return 0 if jobs else 1
    if not jobs:
        print("\n✗ Koi valid row nahi — file nahi likhi.")
        return 1

    out_path = Path(args.out)
    existing = []
    if out_path.exists() and not args.replace:
        try:
            existing = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:
            existing = []

    merged, seen = [], set()
    for j in jobs + existing:                      # naye pehle
        key = (j.get("title", "").lower(), j.get("company", "").lower())
        if key in seen:
            continue
        seen.add(key)
        merged.append(j)

    out_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    shown = out_path.relative_to(ROOT) if str(out_path).startswith(str(ROOT)) else out_path
    print(f"\n✓ {shown} likh diya — {len(merged)} jobs total")
    print("  Ab chalayein:  python scripts/fetch_jobs.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
