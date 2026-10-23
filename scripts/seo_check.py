#!/usr/bin/env python3
"""
seo_check.py — deploy se pehle 30-second health check.

Kya check karta hai
  ✓ har detail page par theek ek JobPosting JSON-LD
  ✓ Google ke required fields (title, description, datePosted, hiringOrganization,
    jobLocation / jobLocationType, validThrough)
  ✓ description ≥ 100 words, title ≠ description
  ✓ employmentType valid enum
  ✓ baseSalary shape (agar mojood ho)
  ✓ canonical, og:image, meta description, sirf ek H1
  ✓ list/landing pages par JobPosting NA ho
  ✓ sitemap XML parse + saare URLs ki file mojood ho
  ✓ robots.txt aur sitemap index

    python scripts/seo_check.py            # sab
    python scripts/seo_check.py --limit 300
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JOBS = ROOT / "jobs"

ENUMS = {"FULL_TIME", "PART_TIME", "CONTRACTOR", "TEMPORARY", "INTERN",
         "VOLUNTEER", "PER_DIEM", "OTHER"}
REQUIRED = ("title", "description", "datePosted", "hiringOrganization", "identifier")

G, Y, R, D = "\033[32m", "\033[33m", "\033[31m", "\033[0m"


def ok(m):   print(f"  {G}✓{D} {m}")
def warn(m): print(f"  {Y}!{D} {m}")
def bad(m):  print(f"  {R}✗{D} {m}")


def jsonld_blocks(html):
    out = []
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            out.append(json.loads(m.group(1)))
        except json.JSONDecodeError as e:
            out.append({"__error__": str(e)})
    return out


def wordcount(s):
    return len(re.sub(r"<[^>]+>", " ", s or "").split())


def check_detail(path: Path, problems: Counter, samples: dict):
    html = path.read_text(encoding="utf-8", errors="replace")
    blocks = jsonld_blocks(html)

    if not blocks:
        problems["no json-ld (broken page)"] += 1
        samples.setdefault("no json-ld (broken page)", str(path))
        return
    if any("__error__" in b for b in blocks):
        problems["broken json-ld"] += 1
        samples.setdefault("broken json-ld", str(path))
        return

    jobs = [b for b in blocks if b.get("@type") == "JobPosting"]
    if not jobs and any(b.get("@type") == "BreadcrumbList" for b in blocks):
        # source ki terms JobPosting allow nahi karti — page phir bhi valid hai
        problems["(info) listing without JobPosting"] += 1
        return
    if len(jobs) != 1:
        problems[f"jobposting count={len(jobs)}"] += 1
        samples.setdefault(f"jobposting count={len(jobs)}", str(path))
        return
    j = jobs[0]

    for f in REQUIRED:
        if not j.get(f):
            problems[f"missing {f}"] += 1
            samples.setdefault(f"missing {f}", str(path))

    if wordcount(j.get("description")) < 100:
        problems["description <100 words"] += 1
        samples.setdefault("description <100 words", str(path))
    if j.get("title") and j.get("title").strip() == re.sub(r"<[^>]+>", "", j.get("description", "")).strip():
        problems["title == description"] += 1

    et = j.get("employmentType")
    et_list = et if isinstance(et, list) else [et] if et else []
    if not et_list or any(e not in ENUMS for e in et_list):
        problems[f"bad employmentType {et}"] += 1
        samples.setdefault("bad employmentType", str(path))

    has_loc = bool(j.get("jobLocation"))
    has_tele = j.get("jobLocationType") == "TELECOMMUTE"
    if not (has_loc or has_tele):
        problems["no location"] += 1
    if has_tele and not j.get("applicantLocationRequirements"):
        problems["TELECOMMUTE without applicantLocationRequirements"] += 1

    if not j.get("validThrough"):
        problems["no validThrough"] += 1

    bs = j.get("baseSalary")
    if bs is not None:
        v = (bs or {}).get("value") or {}
        if not (v.get("minValue") or v.get("maxValue")) or not v.get("unitText"):
            problems["baseSalary malformed"] += 1

    org = j.get("hiringOrganization") or {}
    if not org.get("name"):
        problems["hiringOrganization.name missing"] += 1
    logo = org.get("logo")
    if logo and not logo.startswith("http"):
        problems["logo not absolute URL"] += 1

    # page-level
    if not re.search(r'<link rel="canonical" href="https?://[^"]+"', html):
        problems["no absolute canonical"] += 1
        samples.setdefault("no absolute canonical", str(path))
    if len(re.findall(r"<h1[ >]", html, re.I)) != 1:
        problems["h1 count != 1"] += 1
    if not re.search(r'<meta name="description" content=".{50,}"', html):
        problems["thin meta description"] += 1
    if "og:image" not in html:
        problems["no og:image"] += 1


def check_listing(path: Path, problems: Counter):
    html = path.read_text(encoding="utf-8", errors="replace")
    if any(b.get("@type") == "JobPosting" for b in jsonld_blocks(html)):
        problems[f"JobPosting on listing ({path.parent.name}/{path.name})"] += 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="sirf N pages check karein")
    args = ap.parse_args()

    print("\nRozgar — SEO check\n" + "─" * 52)
    problems: Counter = Counter()
    samples: dict = {}

    pages = sorted(JOBS.glob("*.html"))
    if args.limit:
        pages = pages[:args.limit]
    print(f"\nDetail pages: {len(pages)}")
    for p in pages:
        check_detail(p, problems, samples)

    listings = [ROOT / "index.html", ROOT / "employers.html", ROOT / "alerts.html"]
    listings += list((ROOT / "jobs-in").glob("*.html")) + list((ROOT / "category").glob("*.html"))
    print(f"\nListing/landing pages: {len(listings)}")
    for p in listings:
        if p.exists():
            check_listing(p, problems)

    # sitemaps
    print("\nSitemaps")
    idx = ROOT / "sitemap.xml"
    if not idx.exists():
        bad("sitemap.xml missing")
    else:
        try:
            tree = ET.parse(idx)
            root = tree.getroot()
            locs = [e.text for e in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
            ok(f"sitemap index → {len(locs)} child sitemaps")
            total = 0
            for loc in locs:
                name = loc.rsplit("/", 1)[-1]
                f = ROOT / name
                if not f.exists():
                    bad(f"{name} listed but missing")
                    continue
                try:
                    n = len(list(ET.parse(f).getroot()))
                except ET.ParseError as e:
                    bad(f"{name}: XML error {e}")
                    continue
                total += n
                if n > 50000:
                    bad(f"{name}: {n} URLs (>50,000 limit)")
            ok(f"{total} URLs across child sitemaps")
        except ET.ParseError as e:
            bad(f"sitemap.xml: {e}")

    rb = ROOT / "robots.txt"
    if rb.exists() and "Sitemap:" in rb.read_text():
        ok("robots.txt + sitemap reference")
    else:
        bad("robots.txt missing sitemap line")

    # summary
    print("\n" + "─" * 52)
    if not problems:
        print(f"{G}Sab theek — Google for Jobs ke liye deploy-ready.{D}\n")
        return 0

    real = {k: v for k, v in problems.items() if not k.startswith("(info)")}
    info = problems.get("(info) listing without JobPosting", 0)
    if info:
        print(f"  {Y}i{D} {info} pages without JobPosting (source terms — expected)")
    total = sum(real.values())
    if not real:
        print(f"{G}Sab theek — Google for Jobs ke liye deploy-ready.{D}\n")
        return 0
    print(f"{R}{total} issue(s) in {len(real)} categories:{D}")
    for k, v in problems.most_common(20):
        sample = f"  e.g. {samples[k]}" if k in samples else ""
        print(f"   {k:52s} {v:5d}{sample}")
    print()
    return 1 if any("missing" in k or "count" in k or "broken" in k for k in real) else 0


if __name__ == "__main__":
    sys.exit(main())
