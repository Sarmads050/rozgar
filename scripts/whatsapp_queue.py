#!/usr/bin/env python3
"""Build the daily WhatsApp post pack.

WhatsApp has no free API for channels, so the honest automation is:

  1. This script writes data/whatsapp-queue.json — the newest jobs that have not
     been posted yet, already formatted for WhatsApp (bold title, closing date,
     qualifications, short apply link).
  2. The GitHub Action commits the queue and (optionally) pushes the first post
     to an admin number through CallMeBot, which is free and needs no business
     account: https://www.callmebot.com/blog/free-api-whatsapp-messages/
  3. The channel owner forwards the ready-made text in two taps.

The point is that nobody has to write a post by hand, and no job is ever sent
twice: posted slugs are remembered in data/whatsapp-posted.json.
"""
import json
import os
import re
import time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS = os.path.join(ROOT, "data", "jobs.json")
POSTED = os.path.join(ROOT, "data", "whatsapp-posted.json")
QUEUE = os.path.join(ROOT, "data", "whatsapp-queue.json")
CONFIG = os.path.join(ROOT, "data", "site-config.json")

MAX_POSTS = 6          # per run; a channel that spams gets muted
MAX_CHARS = 640        # WhatsApp is read on a phone lock screen


def short_url(slug, base):
    """A detail URL is long; keep it but drop the protocol for WhatsApp."""
    return f"{base}/jobs/{slug}.html".replace("https://", "").replace("http://", "")


def load(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def emoji_for(job):
    blob = f"{job.get('title','')} {job.get('category','')}".lower()
    if any(k in blob for k in ("army", "navy", "paf", "police", "ranger", "soldier")):
        return "🎖️"
    if any(k in blob for k in ("teacher", "lecturer", "professor", "education")):
        return "📚"
    if any(k in blob for k in ("nurse", "doctor", "medical", "lab", "health")):
        return "🏥"
    if any(k in blob for k in ("bank", "finance", "account")):
        return "🏦"
    if any(k in blob for k in ("software", "developer", "engineer", "data")):
        return "💻"
    if "remote" in blob or job.get("remote"):
        return "🌍"
    return "📌"


def build_post(job, base):
    lines = [f"{emoji_for(job)} *{job.get('display_title') or job['title']}*"]
    employer = job.get("company") or ""
    if employer:
        lines.append(employer)
    facts = []
    if job.get("location"):
        loc = job["location"].replace(", Pakistan", "").strip()
        facts.append("All Pakistan" if loc.lower() in ("pakistan", "") else loc)
    if job.get("qualification"):
        facts.append(job["qualification"])
    if job.get("vacancies"):
        facts.append(f"{job['vacancies']} posts")
    if facts:
        lines.append(" · ".join(facts[:3]))
    if job.get("last_date"):
        try:
            d = datetime.strptime(job["last_date"], "%Y-%m-%d").date()
            left = (d - datetime.now(timezone.utc).date()).days
            when = {"0": "today", "1": "tomorrow"}.get(str(left), f"in {left} days")
            lines.append(f"⏳ Last date: {d.strftime('%d %b %Y')} ({when})")
        except ValueError:
            lines.append(f"⏳ Last date: {job['last_date']}")
    lines.append(f"👉 {short_url(job['slug'], base)}")
    text = "\n".join(lines)
    return text[:MAX_CHARS]


def main():
    data = load(JOBS, {"jobs": []})
    jobs = data.get("jobs", [])
    cfg = load(CONFIG, {})
    base = (os.environ.get("SITE_URL") or cfg.get("site_url")
            or "https://sarmads050.github.io/rozgar").rstrip("/")

    posted = set(load(POSTED, []))
    fresh = [j for j in jobs if j.get("slug") not in posted]
    # best posts first: Pakistan, government, closing soon
    fresh.sort(key=lambda j: (
        0 if j.get("is_pk") else 1,
        0 if (j.get("sector") == "government") else 1,
        j.get("last_date") or "9999",
    ))
    fresh = fresh[:MAX_POSTS]

    queue = [{
        "slug": j["slug"],
        "text": build_post(j, base),
        "poster": j.get("poster"),
        "posted_at": None,
    } for j in fresh]

    with open(QUEUE, "w", encoding="utf-8") as fh:
        json.dump(queue, fh, indent=1, ensure_ascii=False)
        fh.write("\n")

    # Mark as posted only what actually leaves the queue, so a failed run
    # simply tries again next hour instead of losing jobs.
    posted.update(json.loads(os.environ.get("SENT_SLUGS", "[]")))
    with open(POSTED, "w", encoding="utf-8") as fh:
        json.dump(sorted(posted), fh, indent=1)
        fh.write("\n")

    print(f"WhatsApp queue: {len(queue)} posts")
    for q in queue[:3]:
        print("-" * 46)
        print(q["text"])


if __name__ == "__main__":
    main()
