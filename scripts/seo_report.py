#!/usr/bin/env python3
"""Make a one-page SEO health report: what Google can see, and what to fix next.

Run it any time:

    python3 scripts/seo_report.py

It writes SEO-STATUS.md — a short dashboard you can read in a minute before
touching anything. No API keys needed: everything is computed from the files
this repo already builds.
"""
import glob
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "SEO-STATUS.md")


def load_jobs():
    path = os.path.join(ROOT, "data", "jobs.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return json.load(fh).get("jobs", [])


def read(path):
    p = os.path.join(ROOT, path)
    if not os.path.exists(p):
        return ""
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def count_urls(sitemap):
    return sitemap.count("<loc>")


def jsonld_ok(html):
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    for b in blocks:
        try:
            json.loads(b)
        except json.JSONDecodeError:
            return False
    return bool(blocks)


def main():
    jobs = load_jobs()
    today = datetime.now(timezone.utc).date().isoformat()
    pk = [j for j in jobs if j.get("is_pk")]
    gov = [j for j in jobs if (j.get("sector") or "") == "government"]
    indexable = [j for j in jobs if j.get("indexable")]
    expiring = [j for j in jobs
                if j.get("last_date") and 0 <= (datetime.fromisoformat(j["last_date"]).date()
                                                - datetime.now(timezone.utc).date()).days <= 7]

    pages_sitemap = read("sitemap-pages.xml")
    job_maps = sum(count_urls(read(os.path.basename(f)))
                   for f in sorted(glob.glob(os.path.join(ROOT, "sitemap-jobs-*.xml"))))
    image_map = count_urls(read("sitemap-images.xml"))

    # ── sample checks on real pages
    sample = sorted(glob.glob(os.path.join(ROOT, "jobs", "*.html")))[:40]
    bad_schema = [os.path.basename(p) for p in sample if not jsonld_ok(read(
        os.path.relpath(p, ROOT)))]
    noindex_in_sitemap = 0
    for j in indexable[:60]:
        html = read(os.path.join("jobs", f"{j['slug']}.html"))
        if 'content="noindex' in html:
            noindex_in_sitemap += 1

    home = read("index.html")
    home_static_cards = home.count('<article class="job-card"')
    has_canonical = 'rel="canonical"' in home
    has_schema = jsonld_ok(home)
    guides = sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "guides", "*.html")))
    keyword_pages = sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "*-jobs.html"))
                           + [os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "sarkari-naukri.html"))])

    feed = os.path.exists(os.path.join(ROOT, "feed.xml"))
    config = json.loads(read("data/site-config.json") or "{}")
    analytics_on = bool((config.get("analytics") or {}).get("goatcounter")
                        or (config.get("analytics") or {}).get("cloudflare_token"))
    alerts_on = bool((config.get("alerts") or {}).get("email_form_url"))
    wa_on = bool((config.get("alerts") or {}).get("whatsapp_channel_url"))

    def tick(ok):
        return "✅" if ok else "⚠️"

    rows = []
    rows.append(("Job pages Google is allowed to index",
                 f"{len(indexable):,} of {len(jobs):,} "
                 f"({len([j for j in indexable if j.get('is_pk')]):,} Pakistani)",
                 tick(len(indexable) > 100)))
    rows.append(("Pages in the job sitemap", f"{job_maps:,}", tick(job_maps > 50)))
    rows.append(("Landing + guide pages in the sitemap", f"{count_urls(pages_sitemap):,}",
                 tick(count_urls(pages_sitemap) > 30)))
    rows.append(("Poster images in the image sitemap", f"{image_map:,}", tick(image_map > 20)))
    rows.append(("Jobs visible without JavaScript", f"{home_static_cards} cards on the home page",
                 tick(home_static_cards >= 12)))
    rows.append(("Home page canonical + structured data",
                 "both present" if has_canonical and has_schema else "missing",
                 tick(has_canonical and has_schema)))
    rows.append(("Invalid JSON-LD on sampled job pages", f"{len(bad_schema)} of {len(sample)}",
                 tick(not bad_schema)))
    rows.append(("Indexable pages accidentally set to noindex", str(noindex_in_sitemap),
                 tick(noindex_in_sitemap == 0)))
    rows.append(("Email alerts switched on", "yes" if alerts_on else "no (see SETUP-BACKEND.md §2)",
                 tick(alerts_on)))
    rows.append(("Analytics collecting", "yes" if analytics_on else "no (see SETUP-BACKEND.md §1)",
                 tick(analytics_on)))
    rows.append(("WhatsApp channel linked", "yes" if wa_on else "no (see SETUP-BACKEND.md §3)",
                 tick(wa_on)))
    rows.append(("RSS / Atom feed", "feed.xml" if feed else "missing", tick(feed)))

    # ── what to do next, in priority order
    todo = []
    if not (analytics_on and alerts_on and wa_on):
        todo.append("Switch on the three free services in `SETUP-BACKEND.md` — 12 minutes total, "
                    "and they are the only items on this list no code can do for you.")
    if len(pk) < 400:
        todo.append(f"Grow Pakistani listings: {len(pk)} now. Ask 2–3 Pakistani boards for API or "
                    "feed access (a partnership beats scraping), and point employers at the "
                    "post-a-job form.")
    if expiring:
        todo.append(f"{len(expiring)} jobs close within 7 days — that is normal, and the build "
                    "removes them automatically the day after.")
    todo.append("Buy `rozgarjobs.com` when you can (see §5). A shared `github.io` subfolder is the "
                "single biggest ceiling on this site.")
    todo.append("In Search Console, open **Pages** weekly and look at *Discovered – currently not "
                "indexed*. New pages that stay stuck there mean the content is too thin — add a "
                "paragraph of genuine detail, do not resubmit.")

    lines = [
        "# SEO status — RozgarJobs",
        "",
        f"Generated {today} by `scripts/seo_report.py`. Run it before every change so you can see "
        "whether a change made things better.",
        "",
        "## Inventory",
        "",
        "| | | |",
        "|---|---|---|",
        f"| Total live jobs | {len(jobs):,} | |",
        f"| Pakistani jobs | {len(pk):,} | |",
        f"| Government jobs | {len(gov):,} | |",
        f"| Closing within 7 days | {len(expiring):,} | |",
        f"| Indexable job pages | {len(indexable):,} | |",
        f"| Keyword / commission pages | {len(keyword_pages)} | {', '.join(p.replace('.html','') for p in keyword_pages[:6])} … |",
        f"| Guides | {len(guides) - 1} | |",
        "",
        "## Health checks",
        "",
        "| Check | Value | |",
        "|---|---|---|",
    ]
    for name, value, mark in rows:
        lines.append(f"| {name} | {value} | {mark} |")

    lines += ["", "## Do next (in order)", ""]
    lines += [f"{i}. {t}" for i, t in enumerate(todo, 1)]

    lines += [
        "",
        "## The only numbers that really matter",
        "",
        "1. **Clicks and impressions from Pakistan** in Search Console → Performance.",
        "2. **Which queries you show up for on page 2** (positions 11–20). Those pages need one "
        "paragraph of real improvement, not a rewrite.",
        "3. **Search terms people type on the site that return nothing** (GoatCounter `/search/…`). "
        "Each one is a source you are missing.",
        "",
        "Everything else — page counts, sitemap size, schema validity — is plumbing. It has to be "
        "right, but it does not rank a site on its own.",
    ]

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"wrote {os.path.relpath(OUT, ROOT)} — {len(jobs)} jobs, {len(indexable)} indexable, "
          f"{len(pk)} Pakistani")


if __name__ == "__main__":
    main()
