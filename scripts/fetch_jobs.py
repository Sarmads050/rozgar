#!/usr/bin/env python3
"""
Rozgar — job board engine
=========================
Collects jobs from public, attribution-based job APIs, normalises them into
one schema, writes data/jobs.json, generates a detail page per job
(jobs/<slug>.html) with schema.org JobPosting markup, plus feed.xml and
sitemap.xml.

Sources & their terms
---------------------
• Arbeitnow      — public job-board API, link back
• Jobicy         — public API, credit + apply button must point to source
• Himalayas      — public API, link back
• Remote OK      — public API, link back (follow) + name as source
• Remotive       — public API, link back + credit. Their terms explicitly ask
                   NOT to submit their jobs to third parties / Google Jobs, so
                   those pages are generated with noindex + no JobPosting schema.
• manual         — jobs the site owner adds in data/manual-jobs.json
                   (used for Pakistan-based roles and direct employer posts)

Nothing here copies full descriptions: pages show a truncated excerpt and a
prominent "Apply on <source>" link.
"""

import csv
import hashlib
import html
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import pk_sources
    import poster as posterlib
    POSTERS = True
except Exception as _e:  # pragma: no cover
    print(f"! poster/pk_sources unavailable: {_e}", file=sys.stderr)
    POSTERS = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
JOBS_JSON = os.path.join(DATA, "jobs.json")
MANUAL_JSON = os.path.join(DATA, "manual-jobs.json")
SUBMISSIONS_CSV = os.path.join(DATA, "submissions.csv")
JOB_DIR = os.path.join(ROOT, "jobs")
POSTER_DIR = os.path.join(ROOT, "posters")
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")   # e.g. https://user.github.io/rozgar

UA = "Mozilla/5.0 (compatible; RozgarJobBot/1.0; +https://github.com)"
TIMEOUT = 40
MAX_JOBS = 1600          # kept in data/jobs.json
MAX_PAGES = 2500        # a page for every listed job (no dead links)
SUMMARY_LIMIT = 240
DESC_LIMIT = 1400
KEEP_DAYS = 45

# Providers whose licence allows JobPosting structured data / indexing.
# Remotive explicitly asks not to be submitted to third parties / Google Jobs.
# Jin sources ke liye JobPosting markup likhte hain.
#  • APIs jinki terms structured data allow karti hain (credit + link back)
#  • NJP — Government of Pakistan ka official portal, public advertisements
#  • Manual/Employer — job apni site par post hui hai
# Commercial PK aggregators (Ilmkidunya, JobsAlert) ko bahar rakha hai: unka
# content republish karke schema dena unki terms ke khilaf ho sakta hai.
SCHEMA_OK = {"Arbeitnow", "Jobicy", "Himalayas", "Remotive", "Manual", "Employer", "NJP"}

CATEGORIES = [
    "Software Development", "Data & Analytics", "Design", "Product",
    "Marketing", "Sales", "Customer Support", "Finance & Accounting",
    "HR & Recruiting", "Writing & Content", "Operations", "Engineering",
    "Other",
]

CATEGORY_KEYWORDS = {
    "Software Development": ["developer", "engineer", "programmer", "frontend", "backend",
        "full stack", "fullstack", "devops", "sre", "mobile", "ios", "android", "python",
        "javascript", "react", "node", "php", "java", "golang", "rust", "qa", "tester",
        "software", "architect", "cloud", "security engineer", "blockchain"],
    "Data & Analytics": ["data scientist", "data analyst", "data engineer", "analytics",
        "machine learning", "ml engineer", "ai engineer", "bi ", "business intelligence",
        "database", "statistician"],
    "Design": ["designer", "ux", "ui ", "graphic", "product design", "illustrator",
        "motion", "brand design", "figma"],
    "Product": ["product manager", "product owner", "product lead", "scrum", "project manager",
        "program manager"],
    "Marketing": ["marketing", "seo", "growth", "social media", "content marketing",
        "ppc", "performance marketing", "brand manager", "digital marketing", "email marketing"],
    "Sales": ["sales", "business development", "account executive", "bdr", "sdr",
        "account manager", "partnerships"],
    "Customer Support": ["customer support", "customer success", "support agent",
        "help desk", "technical support", "call center", "customer service"],
    "Finance & Accounting": ["accountant", "accounting", "finance", "financial", "payroll",
        "bookkeeper", "audit", "tax", "controller", "cfo"],
    "HR & Recruiting": ["recruiter", "talent", "hr ", "human resources", "people ops",
        "people partner", "hiring"],
    "Writing & Content": ["writer", "copywriter", "editor", "content writer", "translator",
        "technical writer", "producer", "video editor"],
    "Operations": ["operations", "ops ", "logistics", "supply chain", "admin", "virtual assistant",
        "executive assistant", "coordinator"],
    "Engineering": ["mechanical engineer", "electrical engineer", "civil engineer",
        "civil engineering", "manufacturing", "hardware", "circuit", "chemical engineer"],
}

TYPE_MAP = {
    "full_time": "Full Time", "full-time": "Full Time", "fulltime": "Full Time",
    "full time": "Full Time", "permanent": "Full Time", "contract": "Contract",
    "contractor": "Contract", "part_time": "Part Time", "part-time": "Part Time",
    "part time": "Part Time", "internship": "Internship", "intern": "Internship",
    "temporary": "Contract", "freelance": "Freelance", "volunteer": "Volunteer",
}

LEVEL_KEYWORDS = {
    "Internship": ["intern", "internship", "trainee", "graduate"],
    "Junior": ["junior", "jr.", "entry level", "entry-level", "associate"],
    "Lead": ["lead", "principal", "head of", "director", "vp ", "chief"],
    "Senior": ["senior", "sr.", "sr ", "manager"],
}

REGION_MAP = [
    ("Worldwide", ["worldwide", "anywhere", "global", "all countries", "no restriction"]),
    ("Asia", ["asia", "pakistan", "india", "bangladesh", "uae", "dubai", "saudi", "qatar",
              "singapore", "indonesia", "malaysia", "philippines", "vietnam", "turkey",
              "middle east", "south asia"]),
    ("Europe", ["europe", "emea", "eu ", "european union", "germany", "uk", "united kingdom",
                "france", "spain", "netherlands", "poland", "portugal", "italy", "sweden",
                "ireland", "switzerland", "austria", "denmark", "norway", "finland"]),
    ("Americas", ["usa", "united states", "america", "canada", "latam", "latin america",
                  "brazil", "mexico", "argentina", "chile", "colombia"]),
    ("Africa", ["africa", "nigeria", "kenya", "egypt", "south africa", "morocco", "ghana"]),
    ("Oceania", ["australia", "new zealand", "oceania"]),
]

PAKISTAN_FRIENDLY = ["worldwide", "anywhere", "global", "asia", "pakistan", "south asia",
                     "india", "emea", "middle east", "utc+5", "utc+4", "utc+6", "no restriction"]

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


# ───────────────────────────────────────────────────────────── helpers
def fetch(url, headers=None):
    h = {"User-Agent": UA, "Accept": "application/json, text/csv, */*"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def fetch_json(url):
    return json.loads(fetch(url))


def fix_mojibake(text):
    """Repair double-encoded UTF-8 (Remote OK sometimes ships 'ÙØ³Ù' style text)."""
    if not text:
        return text
    try:
        repaired = text.encode("latin-1", "strict").decode("utf-8", "strict")
        # only accept the repair if it clearly reduced mojibake markers
        if repaired.count("Ã") + repaired.count("Ù") < text.count("Ã") + text.count("Ù"):
            return repaired
    except Exception:
        pass
    return text


def clean_text(raw, limit=None):
    if not raw:
        return ""
    # unescape first: many feeds ship &lt;h3&gt; instead of <h3>
    txt = html.unescape(raw)
    txt = re.sub(r"<(br|/p|/div|/li|tr|/tr|/h[1-6])[^>]*>", "\n", txt, flags=re.I)
    txt = TAG_RE.sub(" ", txt)
    txt = html.unescape(txt)          # a second pass for double-escaped feeds
    txt = TAG_RE.sub(" ", txt)
    txt = fix_mojibake(txt)
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n\s*\n+", "\n", txt).strip()
    if limit and len(txt) > limit:
        cut = txt[:limit]
        cut = cut.rsplit(" ", 1)[0] if " " in cut else cut
        txt = cut.rstrip(" ,;:-") + "…"
    return txt


def one_line(text, limit):
    return WS_RE.sub(" ", fix_mojibake(text or "")).strip()[:limit].strip()


def safe_slug(text):
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return re.sub(r"-{2,}", "-", t)[:80] or "job"


def make_id(source, key):
    return hashlib.sha1(f"{source}:{key}".encode("utf-8", "ignore")).hexdigest()[:14]


def to_ts(value):
    if value in (None, "", 0):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip()
    if s.isdigit():
        return int(s)
    s = s.replace("Z", "+00:00")
    for parse in (
        lambda v: datetime.fromisoformat(v),
        lambda v: datetime.strptime(v, "%Y-%m-%d %H:%M:%S"),
        lambda v: datetime.strptime(v, "%Y-%m-%d"),
        lambda v: datetime.strptime(v, "%a, %d %b %Y %H:%M:%S %z"),
    ):
        try:
            dt = parse(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except Exception:
            continue
    return 0


def norm_type(values):
    if isinstance(values, str):
        values = [values]
    out = []
    for v in values or []:
        key = str(v).strip().lower().replace("_", " ").replace("-", " ")
        out.append(TYPE_MAP.get(key, TYPE_MAP.get(key.replace(" ", "_"), "")))
    out = [t for t in out if t]
    return out[0] if out else "Full Time"


def norm_category(text, fallback="Other"):
    low = " " + (text or "").lower() + " "
    best, best_hits = fallback, 0
    for cat, words in CATEGORY_KEYWORDS.items():
        hits = sum(1 for w in words if w in low)
        if hits > best_hits:
            best, best_hits = cat, hits
    return best


def norm_level(title, explicit=""):
    low = (title or "").lower()
    if explicit:
        e = explicit.lower()
        if "intern" in e:
            return "Internship"
        if "entry" in e or "junior" in e:
            return "Junior"
        if "senior" in e:
            return "Senior"
        if "lead" in e or "principal" in e or "director" in e or "executive" in e:
            return "Lead"
        if "mid" in e:
            return "Mid"
    for level in ("Internship", "Junior", "Lead", "Senior"):
        if any(k in low for k in LEVEL_KEYWORDS[level]):
            return level
    return "Mid"


def norm_region(location, extra=""):
    low = f"{location or ''} {extra or ''}".lower()
    if not low.strip():
        return "Worldwide"
    for region, words in REGION_MAP:
        if any(w in low for w in words):
            return region
    return "Other"


def pakistan_friendly(job):
    if job.get("region") in ("Worldwide", "Asia"):
        return True
    blob = f"{job.get('location','')} {job.get('region','')}".lower()
    return any(w in blob for w in PAKISTAN_FRIENDLY)


PK_CITY_WORDS = (
    "karachi", "lahore", "islamabad", "rawalpindi", "faisalabad", "peshawar", "multan",
    "quetta", "hyderabad", "gujranwala", "sialkot", "bahawalpur", "sukkur", "larkana",
    "nawabshah", "abbottabad", "mardan", "murree", "nankana", "jhang", "sargodha",
    "sheikhupura", "kasur", "okara", "sahiwal", "rahimyarkhan", "dera ghazi khan",
    "mirpur", "gilgit", "skardu", "muzaffarabad", "turbat", "gwadar", "chitral",
    "pakistan", "punjab", "sindh", "balochistan", "khyber", "kpk", "gb", "ajk",
)


def looks_pakistani(location):
    low = (location or "").lower()
    return any(w in low for w in PK_CITY_WORDS)


def salary_string(job):
    lo, hi, cur = job.get("salary_min"), job.get("salary_max"), job.get("salary_currency") or ""
    period = job.get("salary_period") or ""
    def fmt(n):
        try:
            n = float(n)
        except Exception:
            return ""
        if n <= 0:
            return ""
        return f"{int(n):,}"
    if lo and hi:
        s = f"{cur} {fmt(lo)} – {fmt(hi)}".strip()
    elif lo:
        s = f"{cur} {fmt(lo)}+".strip()
    elif hi:
        s = f"Up to {cur} {fmt(hi)}".strip()
    else:
        return job.get("salary_text", "") or ""
    return f"{s} {period}".strip()


def finish(job):
    """Shared post-processing."""
    for key in ("title", "company", "location"):
        if isinstance(job.get(key), str):
            job[key] = fix_mojibake(job[key])
    job["category"] = job.get("category") or norm_category(
        f"{job.get('title','')} {' '.join(job.get('tags', []))}")
    job["level"] = job.get("level") or norm_level(job.get("title", ""))
    loc_low = (job.get("location") or "").strip().lower()
    generic_loc = loc_low in ("", "remote", "anywhere", "worldwide", "remote job", "remote - anywhere")
    job["region"] = job.get("region") or ("Worldwide" if (generic_loc and job.get("remote"))
                                          else norm_region(job.get("location", "")))
    job["salary"] = job.get("salary") or salary_string(job)
    job["summary"] = one_line(job.get("summary") or job.get("description_text", ""), SUMMARY_LIMIT)
    job["tags"] = [t for t in dict.fromkeys(job.get("tags", [])) if t][:8]
    job["pak_friendly"] = pakistan_friendly(job)
    job["slug"] = f"{safe_slug(job['title'])}-{safe_slug(job['company'])[:24]}-{job['id'][:6]}"
    return job


# ───────────────────────────────────────────────────────────── providers
def load_arbeitnow():
    out = []
    for page in (1, 2, 3):
        try:
            d = fetch_json(f"https://www.arbeitnow.com/api/job-board-api?page={page}")
        except Exception as e:
            print(f"  ! Arbeitnow page {page}: {e}", file=sys.stderr)
            break
        rows = d.get("data") or []
        if not rows:
            break
        for r in rows:
            desc = clean_text(r.get("description"), DESC_LIMIT)
            out.append(finish({
                "id": make_id("arbeitnow", r.get("slug") or r.get("url")),
                "title": html.unescape(r.get("title", "")).strip(),
                "company": html.unescape(r.get("company_name", "")).strip(),
                "company_logo": "",
                "url": r.get("url", ""),
                "source": "Arbeitnow",
                "source_url": "https://www.arbeitnow.com",
                "location": (r.get("location") or "").strip() or ("Remote" if r.get("remote") else ""),
                "remote": bool(r.get("remote")),
                "type": norm_type(r.get("job_types")),
                "tags": [html.unescape(t) for t in (r.get("tags") or [])][:8],
                "description_html": r.get("description", "")[:6000],
                "description_text": desc,
                "published": to_ts(r.get("created_at")),
                "level": "",
                "category": "",
            }))
    return out


def load_jobicy(pages=3):
    out, cursor = [], ""
    for _ in range(pages):
        url = "https://jobicy.com/api/v2/remote-jobs?count=50"
        if cursor:
            url += "&cursor=" + urllib.parse.quote(cursor)
        try:
            d = fetch_json(url)
        except Exception as e:
            print(f"  ! Jobicy: {e}", file=sys.stderr)
            break
        rows = d.get("jobs") or []
        if not rows:
            break
        out.extend([_jobicy_row(r) for r in rows])
        cursor = d.get("nextCursor") or ""
        if not cursor or not d.get("hasMore"):
            break
        time.sleep(0.3)
    return out


def _jobicy_row(r):
    return finish({
        "id": make_id("jobicy", r.get("id") or r.get("url")),
        "title": html.unescape(r.get("jobTitle", "")).strip(),
        "company": html.unescape(r.get("companyName", "")).strip(),
        "company_logo": r.get("companyLogo") or "",
        "url": r.get("url", ""),
        "source": "Jobicy",
        "source_url": "https://jobicy.com",
        "location": (r.get("jobGeo") or "").strip() or "Remote",
        "remote": True,
        "type": norm_type(r.get("jobType")),
        "tags": [t for t in (r.get("jobIndustry") or [])][:6],
        "level": norm_level(r.get("jobTitle", ""), r.get("jobLevel") or ""),
        "description_html": (r.get("jobDescription") or "")[:6000],
        "description_text": clean_text(r.get("jobDescription") or r.get("jobExcerpt"), DESC_LIMIT),
        "summary": clean_text(r.get("jobExcerpt"), SUMMARY_LIMIT),
        "published": to_ts(r.get("pubDate")),
        "salary_min": r.get("annualSalaryMin"),
        "salary_max": r.get("annualSalaryMax"),
        "salary_currency": r.get("salaryCurrency") or "",
        "salary_period": "per year" if r.get("annualSalaryMin") else "",
        "category": norm_category(" ".join((r.get("jobIndustry") or []) + [r.get("jobTitle", "")])),
    })


def load_himalayas(pages=10):
    out, cursor = [], ""
    for _ in range(pages):
        url = "https://himalayas.app/jobs/api?limit=20"
        if cursor:
            url += "&cursor=" + urllib.parse.quote(cursor)
        try:
            d = fetch_json(url)
        except Exception as e:
            print(f"  ! Himalayas: {e}", file=sys.stderr)
            break
        rows = d.get("jobs") or []
        if not rows:
            break
        cursor = d.get("nextCursor") or ""
        out.extend([_himalayas_row(r) for r in rows])
        if not cursor:
            break
        time.sleep(0.3)
    return out


def _himalayas_row(r):
    locs = r.get("locationRestrictions") or []
    loc = ", ".join(locs[:3]) if locs else "Worldwide"
    desc = clean_text(r.get("description"), DESC_LIMIT)
    return finish({
        "id": make_id("himalayas", r.get("guid") or r.get("title", "") + r.get("companyName", "")),
        "title": html.unescape(r.get("title", "")).strip(),
        "company": html.unescape(r.get("companyName", "")).strip(),
        "company_logo": r.get("companyLogo") or "",
        "url": r.get("guid") or r.get("applicationLink") or "",
        "source": "Himalayas",
        "source_url": "https://himalayas.app",
        "location": loc,
        "remote": True,
        "type": norm_type(r.get("employmentType")),
        "tags": (r.get("parentCategories") or [])[:6],
        "level": norm_level(r.get("title", ""), ", ".join(r.get("seniority") or [])),
        "description_html": (r.get("description") or "")[:6000],
        "description_text": desc,
        "summary": clean_text(r.get("excerpt"), SUMMARY_LIMIT) or desc[:SUMMARY_LIMIT],
        "published": to_ts(r.get("pubDate")),
        "salary_min": r.get("minSalary"),
        "salary_max": r.get("maxSalary"),
        "salary_currency": r.get("currency") or "",
        "salary_period": r.get("salaryPeriod") or "",
        "category": norm_category(" ".join((r.get("parentCategories") or []) + [r.get("title", "")])),
    })


def load_remoteok():
    out = []
    try:
        d = fetch_json("https://remoteok.com/api")
    except Exception as e:
        print(f"  ! RemoteOK: {e}", file=sys.stderr)
        return out
    for r in d:
        if not isinstance(r, dict) or "position" not in r:
            continue  # first element is the legal notice
        desc = clean_text(r.get("description"), DESC_LIMIT)
        out.append(finish({
            "id": make_id("remoteok", r.get("id") or r.get("slug")),
            "title": html.unescape(r.get("position", "")).strip(),
            "company": html.unescape(r.get("company", "")).strip(),
            "company_logo": r.get("company_logo") or r.get("logo") or "",
            "url": r.get("apply_url") or r.get("url") or "",
            "source": "Remote OK",
            "source_url": "https://remoteok.com",
            "location": (r.get("location") or "").strip() or "Remote",
            "remote": True,
            "type": "Full Time",
            "tags": [t for t in (r.get("tags") or [])][:8],
            "description_html": (r.get("description") or "")[:6000],
            "description_text": desc,
            "summary": desc[:SUMMARY_LIMIT],
            "published": to_ts(r.get("epoch") or r.get("date")),
            "salary_min": r.get("salary_min"),
            "salary_max": r.get("salary_max"),
            "salary_currency": "USD",
            "salary_period": "per year",
        }))
    return out


def load_remotive():
    out = []
    try:
        d = fetch_json("https://remotive.com/api/remote-jobs?limit=100")
    except Exception as e:
        print(f"  ! Remotive: {e}", file=sys.stderr)
        return out
    for r in d.get("jobs", []):
        desc = clean_text(r.get("description"), DESC_LIMIT)
        out.append(finish({
            "id": make_id("remotive", r.get("id") or r.get("url")),
            "title": html.unescape(r.get("title", "")).strip(),
            "company": html.unescape(r.get("company_name", "")).strip(),
            "company_logo": r.get("company_logo") or "",
            "url": r.get("url", ""),
            "source": "Remotive",
            "source_url": "https://remotive.com",
            "location": (r.get("candidate_required_location") or "").strip() or "Remote",
            "remote": True,
            "type": norm_type(r.get("job_type")),
            "tags": [t.strip() for t in (r.get("tags") or [])][:8],
            "description_html": (r.get("description") or "")[:6000],
            "description_text": desc,
            "summary": desc[:SUMMARY_LIMIT],
            "published": to_ts(r.get("publication_date")),
            "salary_text": (r.get("salary") or "").strip(),
            "category": norm_category(f"{r.get('category','')} {r.get('title','')}"),
        }))
    return out


# ───────────────────────────────────────────────────────────── manual jobs
def load_manual():
    """Jobs the owner adds by hand (Pakistan-based roles, direct employer posts)."""
    out = []
    if not os.path.exists(MANUAL_JSON):
        return out
    try:
        with open(MANUAL_JSON, encoding="utf-8") as f:
            rows = json.load(f)
    except Exception as e:
        print(f"  ! manual-jobs.json: {e}", file=sys.stderr)
        return out

    for n, r in enumerate(rows, 1):
        title = (r.get("title") or "").strip()
        company = (r.get("company") or "").strip()
        if not title or not company:
            print(f"  ! manual-jobs.json entry #{n}: title aur company zaroori hain — skip",
                  file=sys.stderr)
            continue
        url = (r.get("apply_url") or r.get("url") or "").strip()
        desc = (r.get("description") or "").strip()
        location = (r.get("location") or "Pakistan").strip()
        sector = (r.get("sector") or "").strip().lower()
        if sector not in ("government", "private", "contract", "internship", "remote"):
            sector = "government" if any(w in f"{company} {title}".lower() for w in
                                         ("govt", "government", "ministry", "department",
                                          "authority", "commission", "university", "fpsc",
                                          "ppsc", "bps")) else "private"

        out.append(finish({
            "id": make_id("manual", url or f"{title}{company}{r.get('posted','')}"),
            "title": title,
            "company": company,
            "employer_display": (r.get("employer_display") or company).strip(),
            "company_logo": r.get("company_logo") or "",
            "url": url,
            "source": "Employer" if r.get("employer_submitted") else "Manual",
            "source_url": (r.get("source_url") or "").strip(),
            "location": location,
            "remote": bool(r.get("remote")),
            "type": norm_type(r.get("type") or "Full Time"),
            "sector": sector,
            # poster/detail-page facts
            "qualification": (r.get("qualification") or "").strip(),
            "experience": (r.get("experience") or "").strip(),
            "age_limit": str(r.get("age_limit") or "").strip(),
            "vacancies": r.get("vacancies") or "",
            "bps": str(r.get("bps") or "").strip(),
            "how_to_apply": (r.get("how_to_apply") or "").strip(),
            "last_date": (r.get("last_date") or "").strip(),
            "tags": (r.get("tags") or [])[:8],
            "description_html": "",
            "description_text": clean_text(desc, DESC_LIMIT),
            "summary": one_line(desc, SUMMARY_LIMIT),
            "published": to_ts(r.get("posted")) or int(time.time()),
            "salary_text": (r.get("salary") or "").strip(),
            "salary_min": r.get("salary_min"),
            "salary_max": r.get("salary_max"),
            "salary_currency": (r.get("salary_currency") or "PKR").strip(),
            "salary_period": (r.get("salary_period") or "month").strip(),
            "category": norm_category(f"{r.get('category','')} {title}"),
            "level": norm_level(title, r.get("level") or ""),
            "region": norm_region(r.get("location", ""), "pakistan" if not r.get("remote") else ""),
            "contact_email": (r.get("contact_email") or "").strip(),
            "is_manual": True,
            "is_pk": (not r.get("remote")) and looks_pakistani(location),
        }))
    if out:
        print(f"     {'manual':12s} {len(out):4d} jobs from data/manual-jobs.json")
    return out


def load_submissions_csv():
    """Optional: employer submissions collected via a Google Form (published CSV)."""
    out = []
    if not os.path.exists(SUBMISSIONS_CSV):
        return out
    try:
        with open(SUBMISSIONS_CSV, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
    except Exception as e:
        print(f"  ! submissions.csv: {e}", file=sys.stderr)
        return out

    def pick(row, *names):
        for n in names:
            for k, v in row.items():
                if k and k.strip().lower() == n:
                    return (v or "").strip()
        return ""

    for row in rows:
        title = pick(row, "job title", "title", "position")
        company = pick(row, "company", "company name", "employer")
        if not title or not company:
            continue
        desc = pick(row, "description", "job description", "details")
        out.append(finish({
            "id": make_id("employer", f"{title}{company}{pick(row,'timestamp','email')}"),
            "title": title,
            "company": company,
            "company_logo": pick(row, "logo url", "logo"),
            "url": pick(row, "apply link", "apply url", "job link", "url"),
            "source": "Employer",
            "source_url": "",
            "location": pick(row, "location", "city") or "Pakistan",
            "remote": "remote" in pick(row, "location", "work type").lower(),
            "type": norm_type(pick(row, "job type", "type") or "Full Time"),
            "tags": [t.strip() for t in pick(row, "skills", "tags").split(",") if t.strip()][:8],
            "description_html": "",
            "description_text": clean_text(desc, DESC_LIMIT),
            "summary": one_line(desc, SUMMARY_LIMIT),
            "published": to_ts(pick(row, "timestamp", "date")) or int(time.time()),
            "salary_text": pick(row, "salary"),
            "category": norm_category(pick(row, "category") + " " + title),
            "level": norm_level(title, pick(row, "level", "experience")),
            "contact_email": pick(row, "email", "contact email"),
            "is_manual": True,
        }))
    return out


# ───────────────────────────────────────────────────────────── page renderer
PAGE = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{page_title}</title>
<meta name="description" content="{meta_desc}">
<meta name="keywords" content="{keywords}">
<meta name="author" content="Rozgar">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="article">
<meta property="og:title" content="{title} at {company}">
<meta property="og:description" content="{meta_desc}">
<meta property="og:image" content="{og_image}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{og_image}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%230f766e'/%3E%3Cpath d='M20 17h9v13l11-13h10L37 32l14 15H40L29 34v13h-9z' fill='white'/%3E%3C/svg%3E">
<link rel="stylesheet" href="../assets/css/style.css">
{jsonld}
</head>
<body class="job-page">
<header class="site-head">
  <div class="wrap head-in">
    <a class="brand" href="../index.html">
      <span class="brand-mark">R</span>
      <span class="brand-text"><strong>Rozgar</strong><small>Remote &amp; Pakistan jobs</small></span>
    </a>
    <a class="head-cta" href="../index.html">← All jobs</a>
  </div>
</header>

<main class="wrap job-main">
  <nav class="crumbs"><a href="../index.html">Home</a> <span>/</span> <a href="../index.html?category={cat_q}">{category}</a> <span>/</span> <span>{short_title}</span></nav>

  <article class="job-hero">
    <div class="job-hero-top">
      <div class="job-logo">{logo}</div>
      <div class="job-hero-info">
        <h1>{title}</h1>
        <p class="job-company">{company_site}</p>
        <div class="chips">
          <span class="chip"><svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><path d="M12 21s6.5-5.4 6.5-10.5a6.5 6.5 0 1 0-13 0C5.5 15.6 12 21 12 21z" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="12" cy="10.4" r="2.4" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>{location}</span>
          <span class="chip"><svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><circle cx="12" cy="12" r="8.5" fill="none" stroke="currentColor" stroke-width="1.9"/><path d="M12 7.5V12l3 1.8" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/></svg>{type}</span>
          {salary_chip}
          <span class="chip"><svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><path d="M4 18V13M10 18V9M16 18V6M22 18v-3" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>{level}</span>
          <span class="chip chip-source">via {source}</span>
        </div>
      </div>
    </div>
    <div class="job-hero-actions">
      <a class="btn-apply" href="{url}" target="_blank" rel="noopener noreferrer{rel_extra}">Apply on {source} →</a>
      <span class="posted">Posted {posted_human}</span>
    </div>
  </article>

  <div class="job-detail-grid">
    <div class="job-desc">
      {poster_block}
      <h2>Role overview</h2>
      <p>{description}</p>
      {truncated_note}
      <div class="job-cta-box">
        <div>
          <strong>Ready to apply?</strong>
          <span>You will finish the application on {source}’s website.</span>
        </div>
        <a class="btn-apply" href="{url}" target="_blank" rel="noopener noreferrer{rel_extra}">Apply now →</a>
      </div>
    </div>

    <aside class="job-side">
      <div class="side-card">
        <h3>Job details</h3>
        <dl>
          <dt>Category</dt><dd><a href="../index.html?category={cat_q}">{category}</a></dd>
          <dt>Level</dt><dd>{level}</dd>
          <dt>Type</dt><dd>{type}</dd>
          <dt>Location</dt><dd>{location}</dd>
          <dt>Region</dt><dd>{region}</dd>
          <dt>Source</dt><dd>{source_link}</dd>
        </dl>
      </div>
      {tags_card}
      <div class="side-card side-share">
        <h3>Share this job</h3>
        <a class="share-btn share-wa" data-wa target="_blank" rel="noopener"
           style="display:flex;align-items:center;justify-content:center;gap:8px;background:#25d366;color:#06301c;border-color:#25d366;font-weight:700">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M17.5 14.4c-.3-.2-1.7-.9-2-1-.3-.1-.5-.1-.7.2s-.7 1-.9 1.2c-.2.2-.3.2-.6.1-1.7-.9-2.9-1.6-4-3.6-.3-.5.3-.5.8-1.5.1-.2 0-.4 0-.5s-.7-1.6-.9-2.2c-.2-.6-.5-.5-.7-.5h-.6c-.2 0-.5.1-.8.4-.3.3-1 1-1 2.5s1.1 2.9 1.2 3.1c.1.2 2.1 3.2 5.1 4.5 1.9.8 2.6.9 3.5.7.6-.1 1.7-.7 1.9-1.4.2-.7.2-1.2.2-1.4-.1-.1-.3-.2-.5-.3z"/><path d="M12 2a10 10 0 0 0-8.5 15.3L2 22l4.8-1.4A10 10 0 1 0 12 2zm0 18.2c-1.6 0-3.1-.4-4.4-1.2l-.3-.2-2.9.8.8-2.8-.2-.3A8.2 8.2 0 1 1 12 20.2z"/></svg>
          WhatsApp par bhejein
        </a>
        <button class="share-btn" data-share>Copy link</button>
        <a class="share-btn" href="../alerts.html" style="margin-top:8px;display:block;text-align:center;text-decoration:none">
          🔔 Aise jobs ki alert lein
        </a>
      </div>
    </aside>
  </div>

  {similar}

  <p class="disclaimer">
    Rozgar collects public job listings and links candidates to the employer or
    original job board. We never ask for money, registration fees or bank details.
    If a listing looks suspicious, report it.
  </p>
</main>

<footer class="site-foot">
  <div class="wrap">
    <p>© {year} Rozgar — remote &amp; Pakistan jobs, collected from public APIs with attribution.</p>
  </div>
</footer>
<script>
  var waBtn = document.querySelector('[data-wa]');
  if (waBtn) {{
    var msg = {wa_msg};
    waBtn.href = 'https://wa.me/?text=' + encodeURIComponent(msg);
  }}
  document.querySelectorAll('[data-share]').forEach(function (b) {{
    b.addEventListener('click', function () {{
      navigator.clipboard.writeText(location.href).then(function () {{
        b.textContent = 'Link copied ✓';
        setTimeout(function () {{ b.textContent = 'Copy link'; }}, 1800);
      }});
    }});
  }});
  try {{
    var t = localStorage.getItem('rozgar-theme');
    if (t) document.documentElement.dataset.theme = t;
  }} catch (e) {{}}
</script>
</body>
</html>
"""


def esc(s):
    return html.escape(str(s or ""), quote=True)


def human_date(ts):
    if not ts:
        return "recently"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%d %b %Y")


EMPLOYMENT_ENUM = {
    "Full Time": "FULL_TIME", "Part Time": "PART_TIME", "Contract": "CONTRACTOR",
    "Temporary": "TEMPORARY", "Internship": "INTERN", "Freelance": "CONTRACTOR",
    "Volunteer": "VOLUNTEER", "Per Diem": "PER_DIEM",
}

# Google: "Use the real employer, not a vague label" — these are aggregator
# labels, so we fall back to the employer name where possible.
VAGUE_COMPANIES = {"national jobs portal", "government company", "private company",
                   "defence force", "n/a", "unknown", "-"}


def _clean_company(job):
    name = (job.get("employer_display") or job.get("company") or "").strip()
    if not name or name.lower() in VAGUE_COMPANIES:
        title = job.get("title") or ""
        # "DSF Jobs 2026 Join Pak Army ..." → "Pak Army"
        for kw in ("Pak Army", "Pakistan Navy", "Pakistan Air Force", "WAPDA",
                   "Punjab", "Sindh", "Khyber", "Balochistan", "Karachi", "Lahore"):
            if kw.lower() in title.lower():
                return kw
        return "Government of Pakistan"
    return name


def _desc_html(job):
    """Full description in HTML — Google wants substantial, matching content."""
    parts = []
    desc = (job.get("description") or job.get("description_text") or "").strip()
    if desc:
        parts.append("".join(f"<p>{esc(p)}</p>" for p in desc.split("\n") if p.strip())[:6000])

    rows = [(k, v) for k, v in (
        ("Employer", job.get("employer_display") or job.get("company")),
        ("Location", job.get("location")),
        ("Vacancies", job.get("vacancies")),
        ("Grade / BPS", job.get("bps")),
        ("Qualification", job.get("qualification")),
        ("Experience", job.get("experience")),
        ("Age limit", job.get("age_limit")),
        ("Job type", job.get("type")),
        ("Last date to apply", job.get("last_date")),
    ) if v]
    if rows:
        parts.append("<h3>Job details</h3><ul>" +
                     "".join(f"<li><strong>{esc(k)}:</strong> {esc(str(v))}</li>" for k, v in rows) +
                     "</ul>")

    how = (job.get("how_to_apply") or "").strip()
    if how:
        parts.append("<h3>How to apply</h3>" +
                     "".join(f"<p>{esc(p)}</p>" for p in how.split("\n") if p.strip()))

    body = "".join(parts)

    # Google treats <100 words as thin — pad with honest, page-matching context
    pad = [
        (f"This vacancy was published by {esc(job.get('source', 'a public job source'))} and "
         f"{"is" if job.get("is_pk") else "is also"} listed on Rozgar so that candidates in Pakistan "
         f"can find it in one place. Always open the original advertisement and confirm every "
         f"detail before you apply."),
        (f"Applications are usually assessed against the qualification, experience and age "
         f"requirements listed above. Only shortlisted candidates are contacted, and incomplete "
         f"applications or those received after the closing date are normally not entertained."),
        (f"Rozgar never charges candidates for a listing, an application or an introduction to an "
         f"employer. If anyone asks you for a fee, a registration charge or your bank details in "
         f"connection with this job, treat it as fraud and report it."),
        (f"Keep a copy of your submitted application, note the last date in your calendar, and "
         f"check the employer's own notice for any addendum, test schedule or interview call "
         f"letter before travelling."),
    ]
    for extra in pad:
        if len(re.sub(r"<[^>]+>", " ", body).split()) >= 100:
            break
        body += f"<p>{extra}</p>"
    return body


def job_jsonld(job, canonical, page_url=""):
    if job["source"] not in SCHEMA_OK:
        return ""
    url = job.get("apply_url") or job.get("url") or canonical

    data = {
        "@context": "https://schema.org/",
        "@type": "JobPosting",
        "title": job["title"],
        "description": _desc_html(job),
        "identifier": {
            "@type": "PropertyValue",
            "name": esc(_clean_company(job)),
            "value": job.get("id") or job["slug"],
        },
        "datePosted": datetime.fromtimestamp(
            job.get("published") or time.time(), tz=timezone.utc).strftime("%Y-%m-%d"),
        "hiringOrganization": {
            "@type": "Organization",
            "name": esc(_clean_company(job)),
            **({"sameAs": esc(job["source_url"])} if job.get("source_url") else {}),
            **({"logo": esc(job["company_logo"])} if job.get("company_logo") else {}),
        },
        "directApply": False,
        "url": canonical,
    }

    # employmentType (case-sensitive enum, may be an array)
    et = EMPLOYMENT_ENUM.get(job.get("type") or "", "FULL_TIME")
    data["employmentType"] = et

    # ── location: physical address, or TELECOMMUTE for fully-remote roles
    if job.get("remote"):
        data["jobLocationType"] = "TELECOMMUTE"
        region = (job.get("region") or "").strip()
        country = "Pakistan" if job.get("is_pk") else (
            "Worldwide" if region in ("Worldwide", "") else region)
        data["applicantLocationRequirements"] = {
            "@type": "Country",
            "name": "Pakistan" if job.get("is_pk") else (
                region if region and region != "Other" else "United States"),
        }
        if job.get("is_pk"):
            data["jobLocation"] = {"@type": "Place", "address": {
                "@type": "PostalAddress",
                "addressLocality": job.get("location") or "Pakistan",
                "addressCountry": "PK",
            }}
    else:
        data["jobLocation"] = {"@type": "Place", "address": {
            "@type": "PostalAddress",
            "addressLocality": job.get("location") or "Pakistan",
            "addressCountry": "PK" if job.get("is_pk") else "US",
        }}

    # ── validThrough — required when the job has a closing date
    if job.get("last_date"):
        data["validThrough"] = str(job["last_date"]) + "T23:59:59+05:00"
    else:
        # aggregator listings: keep 45 days so Google never sees stale jobs
        exp = (job.get("published") or time.time()) + 45 * 86400
        data["validThrough"] = datetime.fromtimestamp(exp, tz=timezone.utc).strftime("%Y-%m-%dT23:59:59Z")

    # ── salary (only when the employer/source published it)
    if job.get("salary_min") or job.get("salary_max"):
        try:
            lo = float(job["salary_min"] or job["salary_max"])
            hi = float(job["salary_max"] or job["salary_min"])
            period = (job.get("salary_period") or "").lower()
            unit = ("HOUR" if "hour" in period else "MONTH" if "month" in period
                    else "WEEK" if "week" in period else "YEAR")
            data["baseSalary"] = {
                "@type": "MonetaryAmount",
                "currency": job.get("salary_currency") or "PKR",
                "value": {"@type": "QuantitativeValue", "minValue": lo, "maxValue": hi,
                          "unitText": unit},
            }
        except Exception:
            pass

    # ── experience & education (both help matching)
    exp_req = (job.get("experience") or "").strip()
    if exp_req:
        m = re.search(r"(\d+)", exp_req)
        if m:
            data["experienceRequirements"] = {
                "@type": "OccupationalExperienceRequirements",
                "monthsOfExperience": int(m.group(1)) * 12,
            }
        else:
            data["experienceRequirements"] = {"@type": "OccupationalExperienceRequirements",
                                              "monthsOfExperience": 0}

    qual = (job.get("qualification") or "").lower()
    edu_map = [("phd", "doctoral"), ("m.phil", "postgraduate"), ("master", "postgraduate"),
               ("mba", "postgraduate"), ("bachelor", "bachelor"), ("graduat", "bachelor"),
               ("intermediate", "high school"), ("f.sc", "high school"), ("matric", "high school"),
               ("middle", "middle school"), ("primary", "primary school")]
    for key, val in edu_map:
        if key in qual:
            data["educationRequirements"] = {
                "@type": "EducationalOccupationalCredential", "credentialCategory": val}
            break

    data["industry"] = "Government" if job.get("sector") == "government" else "Private sector"
    if job.get("category"):
        data["occupationalCategory"] = job["category"]

    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False) + "</script>"


def breadcrumb_jsonld(job, canonical):
    items = [
        ("Home", (SITE_URL + "/") if SITE_URL else "/"),
        (job.get("category") or "Jobs", (SITE_URL + "/?category=" + urllib.parse.quote(job.get("category") or "")) if SITE_URL else "/"),
        (job["title"], canonical),
    ]
    data = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": url}
            for i, (name, url) in enumerate(items)
        ],
    }
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False) + "</script>"


def build_page(job, related):
    cat_q = urllib.parse.quote(job["category"])
    canonical = f"{SITE_URL}/jobs/{job['slug']}.html" if SITE_URL else f"jobs/{job['slug']}.html"
    logo_url = job.get("company_logo") or ""
    logo = (f'<img src="{esc(logo_url)}" alt="{esc(job["company"])} logo" loading="lazy" '
            f'referrerpolicy="no-referrer" onerror="this.replaceWith(document.createTextNode(\'{esc(job["company"][:2].upper())}\'))">'
            if logo_url else esc(job["company"][:2].upper()))

    desc = job.get("description_text") or job.get("summary") or "No description was provided by the source. Open the original listing for full details."
    desc_html = "".join(f"<p>{esc(p)}</p>" for p in desc.split("\n") if p.strip())

    similar = ""
    if related:
        cards = "".join(
            f'<a class="mini-card" href="{esc(r["slug"])}.html">'
            f'<strong>{esc(r["title"])}</strong>'
            f'<span>{esc(r["company"])} · {esc(r["location"])}</span></a>'
            for r in related
        )
        similar = f'<section class="similar"><h2>Similar jobs</h2><div class="mini-grid">{cards}</div></section>'

    tags_card = ""
    if job.get("tags"):
        tags = "".join(f'<span class="tag">{esc(t)}</span>' for t in job["tags"])
        tags_card = f'<div class="side-card"><h3>Skills &amp; tags</h3><div class="tag-list">{tags}</div></div>'

    poster_block = ""
    if job.get("poster"):
        rel_poster = job["poster"].split("/")[-1]
        poster_block = (
            '<section class="poster-box">'
            '<div class="poster-box-head">'
            '<h2>Job poster</h2>'
            f'<a class="dl-btn" href="../posters/{esc(rel_poster)}" download>Download poster</a>'
            '</div>'
            f'<img src="../posters/{esc(rel_poster)}" alt="{esc(job["title"])} — job poster" loading="lazy">'
            '<p class="poster-note">Share this poster on WhatsApp, Facebook or print it — '
            'it carries the full eligibility and the apply link.</p>'
            '</section>'
        )

    facts = []
    for label, value in (
        ("Employer", job.get("employer_display") or job.get("company")),
        ("Location", job.get("location")),
        ("Vacancies", job.get("vacancies")),
        ("Grade / BPS", job.get("bps")),
        ("Qualification", job.get("qualification")),
        ("Experience", job.get("experience")),
        ("Age limit", job.get("age_limit")),
        ("Last date", human_date(to_ts(job.get("last_date"))) if job.get("last_date") else ""),
        ("Job type", job.get("type")),
        ("Sector", "Government" if job.get("sector") == "government" else ("Private" if job.get("sector") else "")),
    ):
        if value:
            facts.append(f"<tr><th>{esc(label)}</th><td>{esc(human_date(to_ts(value)) if label == 'Last date' else value)}</td></tr>")
    facts_block = ('<section class="facts-box"><h2>Eligibility &amp; details</h2>'
                   f'<table class="facts-table">{"".join(facts)}</table></section>') if facts else ""

    salary_chip = ('<span class="chip chip-salary"><svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true">'
               '<rect x="2.5" y="6.5" width="19" height="11" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/>'
               '<circle cx="12" cy="12" r="2.6" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>'
               + esc(job["salary"]) + "</span>") if job.get("salary") else ""
    src_url = job.get("source_url") or job.get("url") or ""
    source_link = (f'<a href="{esc(src_url)}" target="_blank" rel="noopener noreferrer">{esc(job["source"])}</a>'
                   if src_url else esc(job["source"]))
    rel_extra = ' nofollow' if job["source"] not in SCHEMA_OK else ""

    # ── SEO strings: "{Job Title} — {Employer} — {City} | Rozgar"
    city = (job.get("location") or "").split(",")[0].strip() or "Pakistan"
    seo_title = f'{job["title"]} — {job.get("company","")} — {city} | Rozgar'
    if len(seo_title) > 68:
        seo_title = f'{job["title"][:44]} — {city} | Rozgar'

    kw_parts = [job["title"], job.get("company"), city, "job", "jobs in pakistan",
                job.get("category") or "", job.get("qualification") or "",
                "government job" if job.get("sector") == "government" else "private job"]
    keywords = ", ".join(dict.fromkeys(k.strip() for k in kw_parts if k and k.strip()))[:280]

    seo_desc = (f'{job["title"]} at {job.get("company","")}, {city}. '
                + (f'Qualification: {job["qualification"]}. ' if job.get("qualification") else "")
                + (f'Age limit: {job["age_limit"]}. ' if job.get("age_limit") else "")
                + (f'Last date: {job["last_date"]}. ' if job.get("last_date") else "")
                + f'Apply on {job.get("source","Rozgar")}. '
                + "Full eligibility, salary and application details on Rozgar — updated hourly.")

    return PAGE.format(
        page_title=esc(seo_title),
        keywords=esc(keywords),
        title=esc(job["title"]),
        company=esc(job["company"]),
        short_title=esc(job["title"][:46] + ("…" if len(job["title"]) > 46 else "")),
        meta_desc=esc(seo_desc[:300]),
        robots="index,follow" if job["source"] in SCHEMA_OK else "noindex,follow",
        canonical=esc(canonical),
        og_image=esc((SITE_URL + "/posters/" + job["slug"] + "-og.jpg") if job.get("og") and SITE_URL
                     else (logo_url or "")),
        wa_msg=json.dumps(
            f"{job['title']} — {job.get('company','')}\n"
            + (f"Location: {job['location']}\n" if job.get("location") else "")
            + (f"Last date: {job['last_date']}\n" if job.get("last_date") else "")
            + f"Details & apply: {canonical}").replace("<", "\\u003c"),
        jsonld=job_jsonld(job, canonical) + breadcrumb_jsonld(job, canonical),
        cat_q=cat_q,
        category=esc(job["category"]),
        logo=logo,
        company_site=esc(job["company"]),
        location=esc(job.get("location") or "Remote"),
        type=esc(job["type"]),
        level=esc(job["level"]),
        region=esc(job.get("region") or "—"),
        salary_chip=salary_chip,
        source=esc(job["source"]),
        source_link=source_link,
        url=esc(job.get("url") or "#"),
        rel_extra=rel_extra,
        posted_human=esc(human_date(job.get("published"))),
        description=desc_html,
        poster_block=poster_block + facts_block,
        truncated_note=('<p class="note">This is a short excerpt. The full description and '
                        f'the application form are on {esc(job["source"])}.</p>') if job.get("description_text") else "",
        tags_card=tags_card,
        similar=similar,
        year=datetime.now().year,
    )


# ══════════════════════════════════════════════════════════════════════════
#  SEO landing pages (city / category / province) — these target the long-tail
#  queries people actually type, e.g. "jobs in karachi", "government jobs".
#  Google wants NO JobPosting markup here — only on detail pages.
# ══════════════════════════════════════════════════════════════════════════
LANDING_CITIES = ["Karachi", "Lahore", "Islamabad", "Rawalpindi", "Faisalabad",
                  "Peshawar", "Multan", "Quetta", "Hyderabad", "Gujranwala",
                  "Sialkot", "Bahawalpur", "Sukkur", "Nankana Sahib"]

LANDING_CATS = ["Admin & Clerical", "Education & Teaching", "Health & Medical",
                "Engineering", "Finance & Accounting", "IT & Computer",
                "Forces & Security", "Support Staff (Class IV)", "Government / Other",
                "Software Development", "Marketing", "Sales", "Customer Support",
                "Design", "Data & Analytics", "Product", "Operations",
                "Human Resources", "HR & Recruiting", "Writing & Content"]

LANDING_PAGE = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} ({count} Vacancies) | Rozgar</title>
<meta name="description" content="{desc}">
<meta name="robots" content="index,follow">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="website">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%230f766e'/%3E%3Cpath d='M20 17h9v13l11-13h10L37 32l14 15H40L29 34v13h-9z' fill='white'/%3E%3C/svg%3E">
<link rel="stylesheet" href="../assets/css/style.css">
{breadcrumb}
</head>
<body>
<header class="site-head">
  <div class="wrap head-in">
    <a class="brand" href="../index.html">
      <span class="brand-mark">R</span>
      <span class="brand-text"><strong>Rozgar</strong><small>Remote &amp; Pakistan jobs</small></span>
    </a>
    <nav class="head-nav"><a href="../index.html">Jobs</a><a href="../alerts.html">Alerts</a><a href="../employers.html">Post a job</a></nav>
  </div>
</header>

<section class="wrap" style="padding-top:26px">
  <nav class="crumbs"><a href="../index.html">Home</a> <span>/</span> <span>{crumb}</span></nav>
  <h1 style="font-size:clamp(24px,3.2vw,36px);letter-spacing:-.8px;margin:8px 0 6px">{h1}</h1>
  <p style="color:var(--muted);max-width:70ch;margin:0 0 6px">{desc}</p>
  <p style="color:var(--muted);font-size:13px;margin:0 0 22px">
    <strong style="color:var(--ink)">{count}</strong> live vacancies · updated every hour ·
    latest one posted {freshness}
  </p>

  <div class="job-list">
  {cards}
  </div>

  {more_block}

  <div class="notice-box" style="margin-top:28px">
    <strong>About this page</strong>
    Rozgar collects these vacancies from official portals and public job boards, and every
    card links to the original advertisement. We never charge candidates — if someone asks
    you for a fee, report it.
  </div>

  <section style="margin-top:30px">
    <h2 style="font-size:16px;margin:0 0 10px">Browse more</h2>
    <div class="tag-list" style="display:flex;flex-wrap:wrap;gap:7px">
      {related_links}
    </div>
  </section>
</section>

<footer class="site-foot" style="margin-top:40px">
  <div class="wrap foot-bottom">
    <span>© {year} Rozgar</span>
    <span>Pakistan jobs, updated hourly</span>
  </div>
</footer>
</body>
</html>
"""


def landing_card(j):
    return (f'<a class="job-card" href="../jobs/{esc(j["slug"])}.html" '
            f'style="grid-template-columns:64px minmax(0,1fr) auto;text-decoration:none">'
            f'<div class="logo" style="width:56px;height:56px;font-size:14px">'
            f'{esc((j["company"] or "?")[:2].upper())}</div>'
            f'<div class="job-info"><h3 class="job-title" style="margin:0 0 3px">{esc(j["title"])}</h3>'
            f'<p class="job-company" style="margin:0 0 7px"><b>{esc(j["company"])}</b>'
            f'{" · " + esc(j["location"]) if j.get("location") else ""}</p>'
            f'<div class="chips">'
            + (f'<span class="chip chip-date">Last date: {esc(human_date(to_ts(j["last_date"])))}</span>' if j.get("last_date") else "")
            + (f'<span class="chip">{esc(j["qualification"])}</span>' if j.get("qualification") else "")
            + (f'<span class="chip">{esc(j["type"])}</span>' if j.get("type") else "")
            + f'</div></div>'
            f'<div class="job-side"><span class="time">{esc(ago_text(j.get("published")))}</span>'
            f'<span class="apply">Details →</span></div></a>')


def ago_text(ts):
    if not ts:
        return "recently"
    d = max(0, int(time.time()) - int(ts))
    if d < 3600:
        return f"{max(1, d // 60)} min ago"
    if d < 86400:
        return f"{d // 3600}h ago"
    return f"{d // 86400}d ago"


def build_landing_pages(jobs):
    """city + category pages with at least 3 live listings (quality gate)."""
    os.makedirs(os.path.join(ROOT, "jobs-in"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "category"), exist_ok=True)
    made = []

    def emit(prefix, slug, h1, title, crumb, desc, subset, related):
        if len(subset) < 3:
            return
        rows = sorted(subset, key=lambda x: (x.get("last_date") or "9999"))[:40]
        canonical = f"{SITE_URL}/{prefix}/{slug}.html" if SITE_URL else f"{prefix}/{slug}.html"
        crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList",
                  "itemListElement": [
                      {"@type": "ListItem", "position": 1, "name": "Home",
                       "item": (SITE_URL + "/") if SITE_URL else "/"},
                      {"@type": "ListItem", "position": 2, "name": crumb, "item": canonical}]}
        more = ""
        if len(subset) > 40:
            more = (f'<div class="loadmore-wrap"><a class="btn-ghost" '
                    f'href="../index.html?{"city=" if prefix.startswith("jobs-in") else "category="}'
                    f'{urllib.parse.quote(h1)}">See all {len(subset)} vacancies →</a></div>')
        html_out = LANDING_PAGE.format(
            title=esc(title), desc=esc(desc), canonical=esc(canonical),
            breadcrumb='<script type="application/ld+json">' + json.dumps(crumbs) + "</script>",
            crumb=esc(crumb), h1=esc(h1),
            count=len(subset),
            freshness=ago_text(max((j.get("published") or 0) for j in subset)),
            cards="".join(landing_card(j) for j in rows),
            more_block=more,
            related_links="".join(
                f'<a class="chip" href="../{p}/{s}.html">{esc(n)}</a>' for p, s, n in related),
            year=datetime.now().year,
        )
        path = os.path.join(ROOT, prefix, f"{slug}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html_out)
        made.append(f"{prefix}/{slug}.html")

    # ── city pages
    city_related = []
    for city in LANDING_CITIES:
        subset = [j for j in jobs if (j.get("location") or "").lower().startswith(city.lower())]
        city_related.append(("jobs-in", safe_slug(city), f"{city} jobs"))
        emit("jobs-in", safe_slug(city),
             f"Jobs in {city}",
             f"Jobs in {city}",
             f"Jobs in {city}",
             f"Latest government and private jobs in {city}. Filter by qualification, "
             f"check the last date and apply directly — every listing shows the full "
             f"eligibility criteria.",
             subset, city_related)

    # ── category pages
    cat_related = []
    for cat in LANDING_CATS:
        subset = [j for j in jobs if (j.get("category") or "") == cat]
        cat_related.append(("category", safe_slug(cat), cat))
        emit("category", safe_slug(cat),
             f"{cat} Jobs in Pakistan",
             f"{cat} Jobs in Pakistan",
             f"{cat} jobs",
             f"Find {cat.lower()} vacancies across Pakistan and remote roles. "
             f"Each listing includes qualification, experience, age limit and the "
             f"application deadline.",
             subset, cat_related)

    # ── rewrite related links now that every slug exists
    for prefix, slug_list in (("jobs-in", city_related), ("category", cat_related)):
        for _, slug, _n in slug_list:
            fp = os.path.join(ROOT, prefix, f"{slug}.html")
            if not os.path.exists(fp):
                continue
            html_src = open(fp, encoding="utf-8").read()
            links = "".join(f'<a class="chip" href="../{p}/{s}.html">{esc(nm)}</a>'
                            for p, s, nm in slug_list
                            if os.path.exists(os.path.join(ROOT, p, f"{s}.html")))
            html_src = re.sub(r'(<div class="tag-list"[^>]*>).*?(</div>)',
                              r"\1" + links + r"\2", html_src, flags=re.S)
            open(fp, "w", encoding="utf-8").write(html_src)

    print(f"     {'':12s} {len(made):4d} landing pages")
    return made


def write_feed(jobs):
    latest = jobs[:50]
    items = "".join(f"""
    <item>
      <title>{esc(j['title'])} — {esc(j['company'])}</title>
      <link>{esc((SITE_URL + '/jobs/' + j['slug'] + '.html') if SITE_URL else j.get('url', ''))}</link>
      <guid isPermaLink="false">{esc(j['id'])}</guid>
      <pubDate>{datetime.fromtimestamp(j['published'] or time.time(), tz=timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>
      <category>{esc(j['category'])}</category>
      <description>{esc(j.get('summary') or j['title'])}</description>
    </item>""" for j in latest)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Rozgar — latest jobs</title>
  <link>{esc(SITE_URL or '/')}</link>
  <description>Remote and Pakistan jobs, updated hourly.</description>
  <language>en</language>
  <lastBuildDate>{datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')}</lastBuildDate>
  {items}
</channel></rss>"""
    with open(os.path.join(ROOT, "feed.xml"), "w", encoding="utf-8") as f:
        f.write(xml)


def write_sitemaps(jobs, landing_urls):
    """sitemap.xml (index) → sitemap-jobs-*.xml + sitemap-pages.xml + sitemap-images.xml"""
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    base = SITE_URL or ""
    chunks, per_file = [], 20000
    indexable = [j for j in jobs if j["source"] in SCHEMA_OK]

    for i in range(0, len(indexable), per_file):
        part = indexable[i:i + per_file]
        body = "".join(
            f"<url><loc>{esc(base)}/jobs/{esc(j['slug'])}.html</loc>"
            f"<lastmod>{now_iso}</lastmod><changefreq>daily</changefreq><priority>0.8</priority></url>"
            for j in part)
        name = f"sitemap-jobs-{i // per_file + 1}.xml"
        with open(os.path.join(ROOT, name), "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + body + "</urlset>")
        chunks.append((name, None))

    # landing pages
    pages = "".join(
        f"<url><loc>{esc(base)}/{esc(u)}</loc><lastmod>{now_iso}</lastmod>"
        f"<changefreq>hourly</changefreq><priority>0.7</priority></url>" for u in landing_urls)
    pages += (f"<url><loc>{esc(base)}/</loc><lastmod>{now_iso}</lastmod>"
              f"<changefreq>hourly</changefreq><priority>1.0</priority></url>"
              f"<url><loc>{esc(base)}/employers.html</loc><lastmod>{now_iso}</lastmod>"
              f"<changefreq>monthly</changefreq><priority>0.5</priority></url>")
    with open(os.path.join(ROOT, "sitemap-pages.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + pages + "</urlset>")
    chunks.append(("sitemap-pages.xml", now_iso))

    # image sitemap (posters) — helps Google Images pick up the posters
    posters = [j for j in jobs if j.get("poster")][:1500]
    if posters:
        imgs = "".join(
            f"<url><loc>{esc(base)}/jobs/{esc(j['slug'])}.html</loc>"
            f"<image:image><image:loc>{esc(base)}/{esc(j['poster'])}</image:loc>"
            f"<image:title>{esc(j['title'])}</image:title></image:image></url>"
            for j in posters)
        with open(os.path.join(ROOT, "sitemap-images.xml"), "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
                    'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">'
                    + imgs + "</urlset>")
        chunks.append(("sitemap-images.xml", now_iso))

    # index
    idx = "".join(
        f"<sitemap><loc>{esc(base)}/{name}</loc>"
        + (f"<lastmod>{lm}</lastmod>" if lm else "") + "</sitemap>"
        for name, lm in chunks)
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                + idx + "</sitemapindex>")

    with open(os.path.join(ROOT, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("User-agent: *\nAllow: /\n\n"
                "User-agent: GPTBot\nAllow: /\n\n"
                "User-agent: Google-Extended\nAllow: /\n\n"
                f"Sitemap: {base}/sitemap.xml\n")
    return len(chunks)


# ───────────────────────────────────────────────────────────── main
def reset_output_dirs():
    """Purani build ke pages/posters hata dein — warna dead job pages index reh jate hain."""
    import shutil
    removed = 0
    for d in (JOB_DIR, POSTER_DIR, os.path.join(ROOT, "jobs-in"), os.path.join(ROOT, "category")):
        if os.path.isdir(d):
            removed += len(os.listdir(d))
            shutil.rmtree(d)
        os.makedirs(d, exist_ok=True)
    for f in ("sitemap.xml", "sitemap-pages.xml", "sitemap-images.xml"):
        fp = os.path.join(ROOT, f)
        if os.path.exists(fp):
            os.remove(fp)
    for f in os.listdir(ROOT):
        if re.match(r"sitemap-jobs-\d+\.xml$", f):
            os.remove(os.path.join(ROOT, f))
    if removed:
        print(f"     {'clean':12s} {removed:4d} stale files removed")


def main():
    os.makedirs(DATA, exist_ok=True)
    os.makedirs(JOB_DIR, exist_ok=True)

    reset_output_dirs()
    print("Fetching jobs…")
    collected = []
    for name, fn in [("Arbeitnow", load_arbeitnow), ("Jobicy", load_jobicy),
                     ("Himalayas", load_himalayas), ("Remote OK", load_remoteok),
                     ("Remotive", load_remotive)]:
        started = time.time()
        try:
            rows = fn()
        except Exception as e:
            print(f"FAIL {name:12s} {type(e).__name__}: {e}")
            continue
        rows = [r for r in rows if r.get("title") and r.get("company") and r.get("url")]
        collected += rows
        print(f"OK   {name:12s} {len(rows):4d} jobs  ({time.time()-started:.1f}s)")
        time.sleep(0.7)

    # ── Pakistan-specific sources (NJP, JobsAlert.pk, Ilmkidunya)
    pk_rows = []
    if POSTERS:
        try:
            pk_rows = pk_sources.collect(limit_per_source=int(os.environ.get("PK_LIMIT", "90")))
            pk_rows = [j for j in pk_rows if j.get("title") and j.get("company") and j.get("url")]
            print(f"OK   {'Pakistan':12s} {len(pk_rows):4d} jobs")
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {'Pakistan':12s} {type(e).__name__}: {e}")

    manual = load_manual() + load_submissions_csv()
    print(f"OK   {'Manual':12s} {len(manual):4d} jobs")
    collected += manual

    # ── Pakistan rows: normalise into the common schema
    for j in pk_rows:
        j["source"] = j.get("source") or "Pakistan"
        j["type"] = j.get("type") or "Full Time"
        j["sector"] = j.get("sector") or "government"
        j["region"] = "Asia"
        j["remote"] = False
        j["pak_friendly"] = True
        j["is_pk"] = True
        j["salary"] = j.get("salary") or ""
        j["slug"] = f"{safe_slug(j['title'])}-{safe_slug(j.get('company', ''))[:24]}-{j.get('source_id','pk')[-6:]}"
        j["id"] = make_id(j.get("source", "pk"), j.get("source_id") or j.get("url"))
        j["published"] = to_ts(j.get("posted")) or int(time.time())
        # keep PK jobs searchable through the normal category filter
        j["category"] = j.get("category") or norm_category(j["title"])
        j["level"] = norm_level(j["title"])
        j["summary"] = one_line(j.get("description") or j.get("how_to_apply") or j["title"], SUMMARY_LIMIT)

    expired_pk = 0
    live = []
    today_iso = datetime.now(timezone.utc).date().isoformat()
    for j in pk_rows:
        ld = (j.get("last_date") or "").strip()
        if ld and ld < today_iso:
            expired_pk += 1
            continue
        live.append(j)
    if expired_pk:
        print(f"     {'':12s} {expired_pk:4d} expired posts skipped")
    pk_rows = live
    collected += pk_rows

    # ── de-duplicate + sort
    cutoff = int(time.time()) - KEEP_DAYS * 86400
    seen_ids, seen_keys, jobs = set(), set(), []
    for j in sorted(collected, key=lambda x: x.get("published", 0), reverse=True):
        if j["id"] in seen_ids:
            continue
        key = re.sub(r"[^a-z0-9]", "", (j["title"] + j["company"]).lower())[:60]
        if key in seen_keys:
            continue
        if j.get("published") and j["published"] < cutoff:
            continue
        seen_ids.add(j["id"])
        seen_keys.add(key)
        jobs.append(j)
        if len(jobs) >= MAX_JOBS:
            break

    now = int(time.time())
    for j in jobs:
        j["age_days"] = max(0, int((now - (j.get("published") or now)) / 86400))

    # ── write data
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "count": len(jobs),
        "companies": len({j["company"].lower() for j in jobs}),
        "pak_friendly": sum(1 for j in jobs if j.get("pak_friendly")),
        "new_today": sum(1 for j in jobs if j.get("age_days", 9) == 0),
        "categories": {c: sum(1 for j in jobs if j["category"] == c) for c in CATEGORIES},
        "sources": sorted({j["source"] for j in jobs}),
    }
    # (jobs.json is written after posters, so poster paths land in the payload)
    page_descriptions = {j["id"]: {k: j.get(k, "") for k in ("description_text", "description_html")}
                         for j in jobs}

    # ── posters: one designed image per job (Pakistan jobs first)
    poster_count = 0
    if POSTERS:
        os.makedirs(POSTER_DIR, exist_ok=True)
        poster_jobs = [j for j in jobs if j.get("is_pk")][:int(os.environ.get("POSTER_LIMIT", "400"))]
        # also give a poster to the newest non-PK jobs so cards look consistent
        poster_jobs += [j for j in jobs if not j.get("is_pk") and j.get("company_logo")][:int(os.environ.get("POSTER_LIMIT_EXTRA", "80"))]
        for j in poster_jobs:
            full = dict(j)
            # posters need the long description, which the light JSON drops
            full["description"] = (page_descriptions.get(j["id"]) or {}).get("description_text", "")
            try:
                posterlib.render_poster(
                    full,
                    os.path.join(POSTER_DIR, f"{j['slug']}.jpg"),
                    site_url=SITE_URL or "",
                    source_line=f"Source: {j['source']}",
                )
                posterlib.render_og(full, os.path.join(POSTER_DIR, f"{j['slug']}-og.jpg"), site_url=SITE_URL or "")
                poster_count += 1
            except Exception as e:  # noqa: BLE001
                print(f"  ! poster {j['slug'][:40]}: {type(e).__name__}: {e}", file=sys.stderr)
            j["poster"] = f"posters/{j['slug']}.jpg"
            j["og"] = f"posters/{j['slug']}-og.jpg"
    print(f"     {'':12s} {poster_count:4d} posters rendered")

    # ── detail pages (newest first, capped)
    by_cat = {}
    for j in jobs:
        by_cat.setdefault(j["category"], []).append(j)
    pages = 0
    for j in jobs[:MAX_PAGES]:
        related = [r for r in by_cat.get(j["category"], []) if r["slug"] != j["slug"]][:3]
        with open(os.path.join(JOB_DIR, f"{j['slug']}.html"), "w", encoding="utf-8") as f:
            f.write(build_page(j, related))
        pages += 1

    # keep descriptions in memory (posters use them) but out of the JSON payload
    HEAVY = ("description_html", "description_text")
    light_jobs = [{k: v for k, v in j.items() if k not in HEAVY} for j in jobs]
    meta["posters"] = poster_count
    with open(JOBS_JSON, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "jobs": light_jobs}, f, ensure_ascii=False, separators=(",", ":"))

    landing_urls = build_landing_pages(jobs)
    write_feed(jobs)
    n_maps = write_sitemaps(jobs, landing_urls)
    print(f"     {'':12s} {len(landing_urls):4d} SEO pages, {n_maps} sitemaps")

    print(f"\nSaved {len(jobs)} jobs  •  {pages} detail pages  •  "
          f"{meta['companies']} companies  •  {meta['new_today']} new today")
    return 0 if jobs else 1


if __name__ == "__main__":
    raise SystemExit(main())
