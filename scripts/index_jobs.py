#!/usr/bin/env python3
"""Submit new job pages to the Google Indexing API.

Google's Indexing API accepts `JobPosting` pages, which is exactly what this
site publishes — so new vacancies can be crawled in minutes instead of waiting
for a weekly crawl. It is not a ranking trick; it only gets a URL *seen* sooner.

Setup (one time, ~5 minutes):
  1. Google Cloud Console → new project → enable "Indexing API".
  2. Create a service account, create a JSON key, download it.
  3. In Search Console → Settings → Users and permissions → add the service
     account email as an **Owner**.
  4. Put the JSON key in the repo secret GOOGLE_INDEXING_KEY (raw JSON).

Without that secret the script exits cleanly, so the workflow never fails.
Docs: https://developers.google.com/search/apis/indexing-api/v3/quickstart
"""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS = os.path.join(ROOT, "data", "jobs.json")
SEEN = os.path.join(ROOT, "data", "indexed-slugs.json")

API = "https://indexing.googleapis.com/v3/urlNotifications:publish"
SCOPE = "https://www.googleapis.com/auth/indexing"
DAILY_QUOTA = 180          # Google allows 200/day by default; keep a margin


def get_token(key_info):
    try:
        from google.oauth2 import service_account           # noqa: PLC0415
        from google.auth.transport.requests import Request  # noqa: PLC0415
    except ImportError:
        print("google-auth is not installed (pip install google-auth) — skipping.")
        return None
    creds = service_account.Credentials.from_service_account_info(key_info, scopes=[SCOPE])
    creds.refresh(Request())
    return creds.token


def main():
    raw = os.environ.get("GOOGLE_INDEXING_KEY", "").strip()
    if not raw:
        print("GOOGLE_INDEXING_KEY not set — nothing submitted. Add the service-account "
              "JSON as a repo secret to switch this on.")
        return 0
    try:
        key_info = json.loads(raw)
    except json.JSONDecodeError:
        print("GOOGLE_INDEXING_KEY is not valid JSON — skipping.")
        return 0

    token = get_token(key_info)
    if not token:
        return 0

    base = (os.environ.get("SITE_URL") or "https://sarmads050.github.io/rozgar").rstrip("/")
    jobs = json.load(open(JOBS, encoding="utf-8")).get("jobs", [])
    try:
        seen = set(json.load(open(SEEN, encoding="utf-8")))
    except Exception:
        seen = set()

    fresh = [j for j in jobs if j.get("slug") and j["slug"] not in seen][:DAILY_QUOTA]
    if not fresh:
        print("No new job pages since the last run.")
        return 0

    import urllib.error
    import urllib.request

    ok = 0
    for j in fresh:
        url = f"{base}/jobs/{j['slug']}.html"
        payload = json.dumps({"url": url, "type": "URL_UPDATED"}).encode()
        req = urllib.request.Request(API, data=payload, method="POST", headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                if r.status == 200:
                    ok += 1
                    seen.add(j["slug"])
        except urllib.error.HTTPError as e:
            print(f"{r.status if 'r' in dir() else e.code} {url} — {e.read()[:160]!r}")
            if e.code in (401, 403):
                print("Authorisation failed: the service account must be an Owner in "
                      "Search Console for this property.")
                break
            if e.code == 429:
                print("Daily quota reached — continuing tomorrow.")
                break
        time.sleep(0.15)

    json.dump(sorted(seen), open(SEEN, "w", encoding="utf-8"), indent=0)
    print(f"Submitted {ok} of {len(fresh)} new job URLs to the Indexing API.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
