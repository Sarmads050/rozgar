#!/usr/bin/env python3
"""
RozgarJobs — job board engine
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
import glob
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

UA = "Mozilla/5.0 (compatible; RozgarJobsJobBot/1.0; +https://github.com)"
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

# Sourced pages may still be worth indexing when they carry enough of our own
# writing: a real description (not a two-line excerpt), a closing date, a named
# employer and a place. Thin re-posts stay noindex — that is what keeps the
# site out of Google's "scaled content abuse" bucket.
THIN_EMPLOYERS = {"government of pakistan", "private sector employer", "not specified", ""}


def is_indexable(job):
    if job.get("source") in SCHEMA_OK:
        return True
    if job.get("indexable") is not None:
        return bool(job["indexable"])
    desc = (job.get("description_text") or "").strip()
    return (len(desc) >= 220
            and bool(job.get("last_date"))
            and bool(job.get("location"))
            and (job.get("company") or "").strip().lower() not in THIN_EMPLOYERS)

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



# ── language guard ─────────────────────────────────────────────────────────
# Some Pakistani boards publish the advertisement summary in Roman Urdu. The
# site is English-only, so any listing whose text is detected as Roman Urdu gets
# a plain-English description generated from its own structured facts instead.
_URDU_WORDS = ("hai", "hain", "nahi", "nahin", "aap", "karain", "karein", "karna", "karo",
               "wahan", "tafseel", "zaroori", "sakte", "sakti", "chahiye", "bhejein",
               "bhej", "darkhwast", "mukammal", "ke", "ki", "ka", "ko", "se", "mein",
               "liye", "aur", "jo", "yeh", "woh", "apni", "apne", "kya", "nahi.")


def looks_roman_urdu(text):
    """True when a block of text is mostly Roman Urdu rather than English."""
    if not text or len(text) < 40:
        return False
    words = re.findall(r"[a-zA-Z']+", text.lower())
    if len(words) < 12:
        return False
    hits = sum(1 for w in words if w in _URDU_WORDS)
    return hits / max(1, len(words)) > 0.16


def english_description(job):
    """A factual English description built from the listing's own fields."""
    parts = []
    title = job.get("title") or "This post"
    employer = job.get("company") or "the employer"
    loc = job.get("location") or "Pakistan"
    sector = (job.get("sector") or "").lower()
    kind = "government" if sector == "government" else "private-sector"

    parts.append(f"{title} is a {kind} vacancy with {employer}, based in {loc}.")
    if job.get("vacancies"):
        parts.append(f"The advertisement mentions {job['vacancies']} post(s).")
    if job.get("bps"):
        parts.append(f"The post is on {job['bps']}.")
    if job.get("qualification"):
        parts.append(f"Candidates should have {job['qualification']}.")
    if job.get("experience"):
        parts.append(f"Relevant experience required: {job['experience']}.")
    if job.get("age_limit"):
        parts.append(f"The age limit stated in the advertisement is {job['age_limit']}.")
    if job.get("salary"):
        parts.append(f"Pay and allowances: {job['salary']}.")
    if job.get("last_date"):
        parts.append(f"Applications close on {job['last_date']}.")
    parts.append(
        "The full advertisement — including the document list, the fee (if any), the test or "
        "interview schedule and the official application form — is on the employer's or "
        "publisher's own website. Open the apply link on this page to read it there before you "
        "submit anything."
    )
    parts.append(
        "RozgarJobs never asks candidates for money. If anyone demands a fee, a deposit or your bank "
        "details for this job, treat it as fraud and report the listing to us."
    )
    return " ".join(parts)


def english_apply_text(job):
    source = job.get("source") or "the original website"
    return (f"Apply on {source}: open the original advertisement, read the requirements and the "
            f"document list, then submit the application form or email before the closing date.")


def enforce_english(job):
    """Replace Roman Urdu text with English generated from the same listing."""
    desc = job.get("description_text") or ""
    if looks_roman_urdu(desc):
        job["description_text"] = english_description(job)
        job["description_translated"] = True
    how = job.get("how_to_apply") or ""
    if looks_roman_urdu(how):
        job["how_to_apply"] = english_apply_text(job)
    summ = job.get("summary") or ""
    if looks_roman_urdu(summ):
        job["summary"] = (f"{job.get('title','This post')} at {job.get('company','')} — "
                          f"{job.get('location','Pakistan')}. Full details and the apply link are on the page.")
    for key in ("title", "company"):
        pass  # titles stay as published — Google requires the original title
    return job



# ── data quality: employer names, display titles ──────────────────────────
GENERIC_EMPLOYERS = {"government company", "private company", "not specified", "company",
                     "employer", "n/a", "na", "-", "unknown", "government", "private"}

_DEPT_WORDS = ("department", "authority", "commission", "ministry", "university", "college",
               "hospital", "board", "council", "office", "directorate", "institute",
               "army", "navy", "air force", "police", "court", "bank", "psc")


# Pakistani boards sometimes put the whole advertisement in the employer field
# ("Latest Advertisement PO Box 95 GPO Rawalpindi Jobs 2026"). That is not an
# employer and it repeats the title on every card.
AD_AS_EMPLOYER = ("po box", "jobs 2026", "jobs 2025", "last date", "application form",
                  "advertisement", "apply online", "test & interview", "vacancy",
                  "www.", "click here", "read more", "government jobs in")


def clean_employer(job):
    """Replace placeholder employer names with something a reader can trust."""
    name = (job.get("company") or "").strip()
    low = name.lower().strip(" .")
    title = (job.get("title") or "")

    junk = low in GENERIC_EMPLOYERS or any(k in low for k in AD_AS_EMPLOYER)

    if junk:
        # 1. the title usually still names the real employer
        m = re.search(r"\b(?:in|at|join)\s+([A-Z][A-Za-z&.\- ]{3,40}?"
                      r"(?:Department|Authority|Commission|Ministry|University|College|"
                      r"Hospital|Board|Council|Office|Directorate|Institute|Court|Bank|"
                      r"Corporation|Company|Limited|Ltd|Force|Police|Army|Navy))", title)
        if m:
            name = re.sub(r"\s+jobs?\b.*$", "", m.group(1), flags=re.I).strip(" ,-")
            # keep the place name that follows the organisation type
            tail = title[m.end():]
            tail = re.match(r"(?:,?\s+)([A-Z][A-Za-z.\-]+(?:\s+[A-Z][A-Za-z.\-]+)?)", tail)
            if tail and tail.group(1).lower() not in ("jobs", "job"):
                name = f"{name} {tail.group(1)}".strip()
        # 2. otherwise be honest about what kind of employer it is
        elif job.get("sector") == "government" or any(w in title.lower() for w in _DEPT_WORDS):
            name = "Government of Pakistan"
        else:
            name = "Private sector employer"

    # a PO Box is a real, verifiable address — keep it when nothing else exists
    box = re.search(r"PO ?Box\s*\d+", title, re.I)
    if box and name in ("Government of Pakistan", "Private sector employer"):
        name = f"{name} ({box.group(0)})"

    return name.strip()


def display_title(job, limit=72):
    """Aggregator titles are keyword stuffed ('DSF Jobs 2026 Join Pak Army ...').
    Cards get a short, readable version. The full title stays in the data and in
    the JobPosting schema, which is what Google expects for a job page."""
    raw = re.sub(r"\s+", " ", (job.get("title") or "")).strip()
    t = raw

    # 1. cut the marketing tail
    t = re.sub(r"\s*[|–-]\s*(apply online|online apply|last date.*|apply by.*|apply now)$", "",
               t, flags=re.I).strip(" -–|,")
    t = re.sub(r"\s*[|–-]\s*(apply online|last date|apply by).*$", "", t, flags=re.I).strip(" -–|,")
    t = re.sub(r"\s+(online apply|apply online)(\s+last date)?\s*$", "", t, flags=re.I)
    t = re.sub(r"\s+last date(\s+to apply)?\s*$", "", t, flags=re.I).strip(" -–|,")

    # 2. years in the middle add nothing on a card
    t = re.sub(r"\b(19|20)\d{2}\b", "", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" -–|,")

    # 2b. Pakistani aggregator boilerplate that is not part of any job title
    BOILER = (r"application form( download| online)?|download application|"
              r"test (and|&) interview date|interview date|roll ?no slip|"
              r"advertisement|how to apply|eligibility criteria|complete details|"
              r"full details|official website|www\.[a-z0-9.\-/]+")
    t = re.sub(rf"\s*(?:[-–|,]\s*)?(?:{BOILER})\b.*$", "", t, flags=re.I).strip(" -–|,")
    t = re.sub(r"\b(download|downloa|onlin|apply onlin)$", "", t, flags=re.I).strip(" -–|,")
    t = re.sub(r"^.*?\bPO ?Box\s*\d+\s*(GPO|P\.O\.)?\s*[A-Za-z ]*?\b(?=[A-Z])", "", t).strip(" -–|,")

    # 2c. standalone filler words at either end
    for _ in range(3):
        t = re.sub(r"^(?:latest|new|apply in|apply for|apply at|jobs in|job in|"
                   r"vacancy in|vacancies in|today|join)\s+", "", t, flags=re.I)
        t = re.sub(r"\s+(?:latest|new|apply|jobs?|vacanc(?:y|ies)|today|update|"
                   r"updated|details|posts?)$", "", t, flags=re.I)
        t = re.sub(r"\s*[-–|,]\s*$", "", t).strip()

    # 3. 'Jobs' as filler ('X Jobs 2026 Join ...' → 'X Join ...')
    if len(t) > 34:
        t = re.sub(r"\bjobs?\b\s*", "", t, count=1, flags=re.I)
        t = re.sub(r"\b(vacancies|careers)\b\s*", "", t, count=1, flags=re.I)
    t = re.sub(r"\s{2,}", " ", t).strip(" -–|,")

    # 4. tidy separators left behind
    t = re.sub(r"\s*[-–|]\s*$", "", t)
    t = re.sub(r"^\s*[-–|]\s*", "", t)

    if not t or len(t) < 4 or len(t.split()) < 2:
        # Prefer whatever survives in the original title ("PO Box 95 GPO
        # Rawalpindi") over the employer label — "latest posts — government of
        # pakistan" tells a reader nothing.
        salvage = re.sub(r"(?i)^\s*(?:latest|new)\s+", "", raw)
        salvage = re.sub(r"(?i)^(?:advertisement|advert|advt)[\s.:\-]*", "", salvage)
        salvage = re.sub(r"(?i)\b(?:jobs?|vacancies?)\s*20\d{2}\b", "", salvage)
        salvage = re.sub(r"(?i)\b(?:last date|apply by|test\s*(?:&|and)\s*interview|"
                         r"application form|download)\b.*$", "", salvage)
        salvage = re.sub(r"\s{2,}", " ", salvage).strip(" -–|,")
        if len(salvage.split()) >= 2:
            t = salvage
        else:
            emp = (job.get("company") or "").strip()
            generic = ("private company", "government company", "not specified", "")
            t = f"Latest posts — {emp}" if emp.lower() not in generic else raw

    if len(t) > limit:
        cut = t[:limit].rsplit(" ", 1)[0]
        t = cut.rstrip(" ,-–|") + "…"

    # A cleaned aggregator title often reads like a notice, not a role
    # ("District and Session Court Peshawar"). Say what it is instead.
    ROLE = (r"manager|engineer|officer|clerk|teacher|nurse|driver|assistant|"
            r"technician|operator|accountant|director|superintendent|inspector|"
            r"constable|attendant|guard|developer|designer|analyst|specialist|"
            r"intern|trainee|professor|lecturer|doctor|pharmacist|lawyer|judge|"
            r"secretary|coordinator|executive|head|lead|chief|helper|sweeper|"
            r"naib|qasid|chowkidar|malhi|baildar|imam|khateeb|moazzin|store|"
            r"dispatch|receptionist|warden|supervisor|instructor|trainer|"
            r"consultant|advisor|auditor|surveyor|subedar|havildar|soldier|"
            r"staff|engineer|draftsman|photographer|security")
    if (not t.startswith("Latest posts — ")
            and not re.search(rf"\b(?:{ROLE})\b", t, re.I) and len(t.split()) >= 3):
        t = "Latest posts — " + t
    return t or raw



def enrich_description(job):
    """Pakistani job boards publish the facts, not the prose. Build a readable
    summary from those facts so the page is genuinely useful (and long enough to
    be worth indexing) instead of a two-line stub."""
    facts = []
    if job.get("qualification"):
        facts.append(f"qualification {job['qualification']}")
    if job.get("experience") and job["experience"].lower() not in ("not specified", "-"):
        facts.append(f"experience {job['experience']}")
    if job.get("age_limit"):
        facts.append(f"age limit {job['age_limit']}")
    if job.get("bps"):
        facts.append(f"pay scale {job['bps']}")
    if job.get("salary"):
        facts.append(f"salary {job['salary']}")
    if job.get("vacancies"):
        facts.append(f"{job['vacancies']} vacancies")
    if job.get("last_date"):
        facts.append(f"applications close on {job['last_date']}")

    if len(facts) < 3:
        return job  # not enough substance — the page stays noindex

    title = job.get("display_title") or job.get("title") or "This post"
    employer = job.get("company") or "the employer"
    where = job.get("location") or "Pakistan"
    lines = [f"{title} is open at {employer} in {where}."]
    lines.append("The advertisement lists " + ", ".join(facts[:-1]) +
                 (f" and {facts[-1]}." if len(facts) > 1 else "."))

    if job.get("sector") == "government":
        lines.append("This is a government post, so selection follows the department's own "
                     "procedure — a written test and interview in most cases. Government "
                     "departments check eligibility strictly on the closing date: the degree, "
                     "the experience and the age limit must match on that date, not later.")
    else:
        lines.append("The employer runs its own shortlisting, usually a test or an interview, "
                     "and contacts shortlisted candidates directly.")

    how = (job.get("how_to_apply") or "").strip()
    if how:
        lines.append("How to apply: " + one_line(how, 320))
    else:
        lines.append("Apply through the source advertisement — the apply button on this page "
                     "opens the original posting.")

    if job.get("last_date"):
        try:
            left = (datetime.strptime(job["last_date"], "%Y-%m-%d").date() - datetime.now(timezone.utc).date()).days
            if 0 <= left <= 7:
                lines.append(f"Only {left} day{'s' if left != 1 else ''} left — send the "
                             f"application before the closing date, not after.")
        except (ValueError, TypeError):
            pass

    job["description_text"] = ((job.get("description_text") or "").strip() + "\n\n" +
                               " ".join(lines)).strip()
    return job


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
    job = enrich_description(job)
    # decide indexability while the full description is still in memory
    _desc = (job.get("description_text") or "").strip()
    job["indexable"] = (job.get("source") in SCHEMA_OK or
                        (len(_desc) >= 220
                         and bool(job.get("last_date"))
                         and bool(job.get("location"))
                         and (job.get("company") or "").strip().lower() not in THIN_EMPLOYERS))
    job["summary"] = one_line(job.get("summary") or job.get("description_text", ""), SUMMARY_LIMIT)
    job["tags"] = [t for t in dict.fromkeys(job.get("tags", [])) if t][:8]
    job["pak_friendly"] = pakistan_friendly(job)
    enforce_english(job)
    job["company"] = clean_employer(job)
    job["display_title"] = display_title(job)
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
    """Employer submissions, either exported from a Google Form or filled in
    data/submissions.csv using data/jobs-template.csv. Extra poster fields are
    picked up when the column exists; missing ones are simply skipped."""
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

    skipped = 0
    for row in rows:
        title = pick(row, "job title", "title", "position")
        company = pick(row, "company", "company name", "employer")
        if not title or not company:
            skipped += 1
            continue

        desc = pick(row, "description", "job description", "details")
        location = pick(row, "location", "city") or "Pakistan"
        sector = pick(row, "sector").lower()
        if sector not in ("government", "private", "contract", "internship", "remote"):
            sector = "government" if any(w in f"{company} {title}".lower() for w in
                                         ("govt", "government", "ministry", "department",
                                          "authority", "commission", "university", "fpsc",
                                          "ppsc", "bps")) else "private"
        vacancies = pick(row, "vacancies", "posts", "no of posts")

        out.append(finish({
            "id": make_id("employer", f"{title}{company}{pick(row,'timestamp','email')}"),
            "title": title,
            "company": company,
            "employer_display": pick(row, "employer display") or company,
            "company_logo": pick(row, "logo url", "logo"),
            "url": pick(row, "apply link", "apply url", "job link", "url"),
            "source": "Employer",
            "source_url": "",
            "location": location,
            "remote": ("remote" in location.lower()) or sector == "remote",
            "type": norm_type(pick(row, "job type", "type") or "Full Time"),
            "sector": sector,
            "category": pick(row, "category"),
            # poster / detail-page facts
            "qualification": pick(row, "qualification", "education"),
            "experience": pick(row, "experience"),
            "age_limit": pick(row, "age limit", "age"),
            "vacancies": int(vacancies) if vacancies.isdigit() else vacancies,
            "bps": pick(row, "bps", "scale", "grade"),
            "how_to_apply": pick(row, "how to apply", "application instructions"),
            "last_date": pick(row, "last date", "last date to apply", "deadline", "closing date"),
            "tags": [t.strip() for t in pick(row, "skills", "tags").split(",") if t.strip()][:8],
            "description_html": "",
            "description_text": clean_text(desc, DESC_LIMIT),
            "summary": one_line(desc, SUMMARY_LIMIT),
            "published": to_ts(pick(row, "timestamp", "date", "posted")) or int(time.time()),
            "salary_text": pick(row, "salary"),
            "salary_currency": "PKR",
            "contact_email": pick(row, "email", "contact email"),
            "is_manual": True,
            "is_pk": (sector != "remote") and looks_pakistani(location),
        }))

    if skipped:
        print(f"  ! submissions.csv: {skipped} row(s) skipped (title or company missing)",
              file=sys.stderr)
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
<meta name="author" content="RozgarJobs">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="article">
<meta property="og:title" content="{title} at {company}">
<meta property="og:description" content="{meta_desc}">
<meta property="og:image" content="{og_image}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{og_image}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%230f766e'/%3E%3Cpath d='M20 17h9v13l11-13h10L37 32l14 15H40L29 34v13h-9z' fill='white'/%3E%3C/svg%3E">
<link rel="manifest" href="../manifest.webmanifest">
<link rel="stylesheet" href="../assets/css/style.css">
{jsonld}
<script src="assets/js/analytics.js" defer></script>
</head>
<body class="job-page">
<header class="site-head">
  <div class="wrap head-in">
    <a class="brand" href="../index.html">
      <img class="brand-logo" src="../assets/img/mark.svg" alt="" width="38" height="38">
      <span class="brand-text"><strong>Rozgar<span class="bj">Jobs</span></strong><small>Jobs in Pakistan</small></span>
    </a>
    <a class="head-cta" href="../index.html">← All jobs</a>
  </div>
</header>

<main class="wrap job-main">
  <nav class="crumbs"><a href="../index.html">Home</a> <span>/</span> {cat_crumb} <span>/</span> {city_crumb} <span>/</span> <span>{short_title}</span></nav>

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
          <dt>Category</dt><dd>{cat_crumb}</dd>
          <dt>Level</dt><dd>{level}</dd>
          <dt>Type</dt><dd>{type}</dd>
          <dt>Location</dt><dd>{city_crumb}</dd>
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
          Share on WhatsApp
        </a>
        <button class="share-btn" data-share>Copy link</button>
        <a class="share-btn" href="../alerts.html" style="margin-top:8px;display:block;text-align:center;text-decoration:none">
          <svg viewBox=\'0 0 24 24\' width=\'14\' height=\'14\' fill=\'none\' stroke=\'currentColor\' stroke-width=\'2\' stroke-linecap=\'round\' stroke-linejoin=\'round\' aria-hidden=\'true\' style=\'vertical-align:-2px;margin-right:4px\'><path d=\'M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9\'/><path d=\'M13.7 21a2 2 0 0 1-3.4 0\'/></svg>Get job alerts
        </a>
      </div>
    </aside>
  </div>

  {similar}

  <p class="disclaimer">
    RozgarJobs collects public job listings and links candidates to the employer or
    original job board. We never ask for money, registration fees or bank details.
    If a listing looks suspicious, report it.
  </p>
</main>

{sticky_bar}

<nav class="bottom-nav" aria-label="Main navigation">
  <a href="../index.html"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 10.5 12 4l8 6.5V20H4z"/><path d="M9.5 20v-5.5h5V20"/></svg><span>Jobs</span></a>
  <a href="../alerts.html"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></svg><span>Alerts</span></a>
  <a href="../index.html?saved=1"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round" aria-hidden="true"><path d="M12 3.6l2.6 5.4 5.9.8-4.3 4.1 1.1 5.8L12 16.9 6.7 19.7l1.1-5.8L3.5 9.8l5.9-.8z"/></svg><span>Saved</span></a>
  <a href="../employers.html"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg><span>Post a job</span></a>
</nav>

<footer class="site-foot">
  <div class="wrap">
    <p>© {year} RozgarJobs — jobs in Pakistan and remote roles, collected from public sources with credit.</p>
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
         f"{"is" if job.get("is_pk") else "is also"} listed on RozgarJobs so that candidates in Pakistan "
         f"can find it in one place. Always open the original advertisement and confirm every "
         f"detail before you apply."),
        (f"Applications are usually assessed against the qualification, experience and age "
         f"requirements listed above. Only shortlisted candidates are contacted, and incomplete "
         f"applications or those received after the closing date are normally not entertained."),
        (f"RozgarJobs never charges candidates for a listing, an application or an introduction to an "
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

    return _ld(data)


def _ld(data):
    """JSON-LD block — '</script>' ko escape karta hai taake description se breakout na ho."""
    raw = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return '<script type="application/ld+json">' + raw + "</script>"


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
    return _ld(data)


CITY_PAGES = set()      # city slugs whose landing page will exist
CAT_PAGES = set()       # category slugs whose landing page will exist


def landing_city_set(jobs):
    return {safe_slug(c) for c in LANDING_CITIES
            if sum(1 for j in jobs if (j.get("location") or "").lower().startswith(c.lower())) >= 5}


def landing_cat_set(jobs):
    return {safe_slug(c) for c in LANDING_CATS
            if sum(1 for j in jobs if (j.get("category") or "") == c) >= 5}


def build_page(job, related):
    cat_q = urllib.parse.quote(job["category"])
    city_name = (job.get("location") or "").split(",")[0].strip()
    city_slug = safe_slug(city_name) if city_name else ""
    city_href = f"../jobs-in/{city_slug}.html" if city_slug in CITY_PAGES else ""
    cat_href = f"../category/{safe_slug(job['category'])}.html" if safe_slug(job["category"]) in CAT_PAGES else ""
    city_label = city_name or "Remote"
    city_crumb = (f'<a href="{city_href}">{esc(city_label)}</a>' if city_href else esc(city_label))
    cat_crumb = (f'<a href="{cat_href}">{esc(job["category"])}</a>'
                 if cat_href else f'<a href="../index.html?category={cat_q}">{esc(job["category"])}</a>')
    sticky = (f'<div class="apply-bar"><div class="apply-bar-in">'
              f'<div class="apply-bar-txt"><strong>{esc(job["title"][:48])}</strong>'
              f'<span>{esc(city_label)} · via {esc(job["source"])}</span></div>'
              f'<a class="btn-apply" href="{esc(job.get("url") or "#")}" target="_blank" '
              f'rel="noopener noreferrer{"" if is_indexable(job) else " nofollow"}">'
              f'Apply on {esc(job["source"])} →</a></div></div>')
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
            f'<picture>'
            f'<source srcset="../posters/{esc(rel_poster.rsplit(".", 1)[0])}.webp" type="image/webp">'
            f'<img src="../posters/{esc(rel_poster)}" alt="{esc(job["title"])} — job poster" '
            f'width="1080" height="1350" loading="lazy" decoding="async">'
            f'</picture>'
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

    # ── SEO strings: "{Job Title} — {Employer} — {City} | RozgarJobs"
    city = (job.get("location") or "").split(",")[0].strip() or "Pakistan"
    seo_title = f'{job["title"]} — {job.get("company","")} — {city} | RozgarJobs'
    if len(seo_title) > 68:
        seo_title = f'{job["title"][:44]} — {city} | RozgarJobs'

    kw_parts = [job["title"], job.get("company"), city, "job", "jobs in pakistan",
                job.get("category") or "", job.get("qualification") or "",
                "government job" if job.get("sector") == "government" else "private job"]
    keywords = ", ".join(dict.fromkeys(k.strip() for k in kw_parts if k and k.strip()))[:280]

    seo_desc = (f'{job["title"]} at {job.get("company","")}, {city}. '
                + (f'Qualification: {job["qualification"]}. ' if job.get("qualification") else "")
                + (f'Age limit: {job["age_limit"]}. ' if job.get("age_limit") else "")
                + (f'Last date: {job["last_date"]}. ' if job.get("last_date") else "")
                + f'Apply on {job.get("source","RozgarJobs")}. '
                + "Full eligibility, salary and application details on RozgarJobs — updated hourly.")

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
        city_crumb=city_crumb,
        cat_crumb=cat_crumb,
        sticky_bar=sticky,
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
<meta http-equiv="Content-Security-Policy" content="default-src &#39;self&#39;; script-src &#39;self&#39; &#39;unsafe-inline&#39;; style-src &#39;self&#39; &#39;unsafe-inline&#39;; img-src &#39;self&#39; https: data:; font-src &#39;self&#39; data:; connect-src &#39;self&#39; https:; form-action &#39;self&#39; mailto:; base-uri &#39;self&#39;; object-src &#39;none&#39;">
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>{title} 2026 — {count} Open Vacancies | RozgarJobs</title>
<meta name="description" content="{desc}">
<meta name="robots" content="index,follow">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="website">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%230f2a47'/%3E%3Cpath d='M20 17h9v13l11-13h10L37 32l14 15H40L29 34v13h-9z' fill='white'/%3E%3C/svg%3E">
<link rel="stylesheet" href="../assets/css/style.css">
{json_ld}
<script src="../assets/js/analytics.js" defer></script>
</head>
<body>
<header class="site-head">
  <div class="wrap head-in">
    <a class="brand" href="../index.html">
      <img class="brand-logo" src="../assets/img/mark.svg" alt="" width="38" height="38">
      <span class="brand-text"><strong>Rozgar<span class="bj">Jobs</span></strong><small>Jobs in Pakistan</small></span>
    </a>
    <nav class="head-nav"><a href="../index.html">Jobs</a><a href="../alerts.html">Alerts</a><a href="../employers.html">Post a job</a></nav>
  </div>
</header>

<div class="topbar">
  <div class="wrap topbar-in">
    <span class="topbar-status"><i class="live-dot"></i><span>{count} live {crumb} vacancies · updated every hour</span></span>
  </div>
</div>

<section class="wrap" style="padding-top:24px">
  <nav class="crumbs"><a href="../index.html">Home</a> <span>/</span> <span>{crumb}</span></nav>
  <h1 style="font-size:clamp(25px,3.4vw,38px);letter-spacing:-1px;margin:10px 0 10px;line-height:1.15">{h1}</h1>
  <div class="landing-intro">{intro}</div>

  <div class="stat-strip" style="margin:14px 0 20px">{stat_row}</div>

  <h2 style="font-size:17px;margin:0 0 12px;letter-spacing:-.3px">Open vacancies right now</h2>
  <div class="job-list">
  {cards}
  </div>

  {more_block}

  {intro_rest}

  {employer_block}

  {faq_block}

  <div class="notice-box" style="margin-top:28px">
    <strong>About this page</strong>
    RozgarJobs collects these vacancies from official portals and public job boards. Every card links to the
    original advertisement, so you always apply on the employer's own site. We never charge candidates —
    if someone asks you for a fee, report them to us.
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
    <span>© {year} RozgarJobs</span>
    <span>Jobs in Pakistan, updated hourly</span>
  </div>
</footer>

<nav class="bottom-nav" aria-label="Main navigation">
  <a href="../index.html"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 10.5 12 4l8 6.5V20H4z"/><path d="M9.5 20v-5.5h5V20"/></svg><span>Jobs</span></a>
  <a href="../alerts.html"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></svg><span>Alerts</span></a>
  <a href="../index.html?saved=1"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round" aria-hidden="true"><path d="M12 3.6l2.6 5.4 5.9.8-4.3 4.1 1.1 5.8L12 16.9 6.7 19.7l1.1-5.8L3.5 9.8l5.9-.8z"/></svg><span>Saved</span></a>
  <a href="../employers.html"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg><span>Post a job</span></a>
</nav>

<style>
  .landing-intro p {{ font-size: 15px; line-height: 1.62; color: var(--ink-2); margin: 0 0 10px; max-width: 76ch; }}
  .landing-intro p.lead {{ font-size: 16px; color: var(--ink); }}
  .emp-list {{ display: grid; gap: 8px; }}
  .emp-row {{ display: flex; justify-content: space-between; gap: 12px; font-size: 14px;
    padding: 9px 13px; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; }}
  .emp-row b {{ font-weight: 650; }}
  .emp-row span {{ color: var(--muted); font-size: 13px; white-space: nowrap; }}
  .faq-block h2 {{ font-size: 17px; letter-spacing: -.3px; margin: 0 0 10px; }}
  .faq-block details {{ background: var(--surface); border: 1px solid var(--line); border-radius: 11px; padding: 12px 15px; margin-bottom: 8px; }}
  .faq-block summary {{ font-weight: 650; font-size: 14.5px; cursor: pointer; }}
  .faq-block p {{ color: var(--muted); font-size: 14px; margin: 8px 0 0; line-height: 1.6; }}
</style>
</body>
</html>
"""


def landing_card(j):
    return (f'<a class="job-card" href="../jobs/{esc(j["slug"])}.html" '
            f'style="grid-template-columns:64px minmax(0,1fr) auto;text-decoration:none">'
            f'<div class="logo" style="width:56px;height:56px;font-size:14px">'
            f'{esc((j["company"] or "?")[:2].upper())}</div>'
            f'<div class="job-info"><h3 class="job-title" style="margin:0 0 3px">{esc(j.get("display_title") or j["title"])}</h3>'
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


def _plural(n, word):
    return f"{n:,} {word}" if n == 1 else f"{n:,} {word}s"


def _top(counter, n):
    return [k for k, _ in counter.most_common(n) if k]


def _closes_soon(subset, days=7):
    today = datetime.now().date()
    out = []
    for j in subset:
        ld = (j.get("last_date") or "")[:10]
        try:
            d = (datetime.strptime(ld, "%Y-%m-%d").date() - today).days
        except Exception:
            continue
        if 0 <= d <= days:
            out.append((d, j))
    return sorted(out, key=lambda x: x[0])


def landing_facts(subset):
    """Real, countable facts about this page's job set — the basis of unique copy."""
    from collections import Counter
    gov = [j for j in subset if (j.get("sector") or "").lower() == "government"]
    employers = Counter((j.get("company") or "").strip() for j in subset if j.get("company"))
    quals = Counter((j.get("qualification") or "").strip() for j in subset if j.get("qualification"))
    cats = Counter((j.get("category") or "").strip() for j in subset if j.get("category"))
    cities = Counter((j.get("location") or "").split(",")[0].strip() for j in subset if j.get("location"))
    soon = _closes_soon(subset)
    no_deadline = [j for j in subset if not j.get("last_date")]
    return {
        "total": len(subset),
        "gov": len(gov),
        "priv": len(subset) - len(gov),
        "employers": employers,
        "quals": quals,
        "cats": cats,
        "cities": cities,
        "soon": soon,
        "no_deadline": len(no_deadline),
        "top_emp": _top(employers, 5),
        "top_quals": _top(quals, 3),
        "top_cats": _top(cats, 3),
        "top_cities": _top(cities, 4),
    }


def build_intro(kind, name, f):
    """Unique opening copy: every sentence comes from this page's own numbers."""
    total, gov, priv = f["total"], f["gov"], f["priv"]
    label = "jobs" if kind == "city" else "vacancies"
    p1 = f"<p class=\"lead\"><strong>{total:,} {name} {label}</strong> are open on RozgarJobs today: " \
         f"{priv:,} from private companies and {gov:,} from government departments and public bodies."
    if f["top_cats"]:
        p1 += " The largest share is in " + ", ".join(
            f"{c} ({f['cats'][c]})" for c in f["top_cats"][:2]) + "."
    p1 += "</p>"

    p2 = ""
    if f["top_emp"]:
        p2 = ("<p>The employers advertising most often are <strong>" + ", ".join(f["top_emp"][:3]) +
              "</strong>. Each card asks you to apply on that employer's own site or portal, so there is no "
              "middle step and no account to create.</p>")

    p3 = ""
    if f["soon"]:
        d0, j0 = f["soon"][0]
        when = "today" if d0 == 0 else ("tomorrow" if d0 == 1 else f"in {d0} days")
        p3 = (f"<p>{_plural(len(f['soon']), 'job')} close within a week — the soonest is "
              f"<strong>{esc(j0['title'])}</strong> at {esc(j0.get('company') or 'a public employer')}, "
              f"closing {when}. Check the last date on the card before you send an application.</p>")
    elif f["no_deadline"]:
        p3 = (f"<p>{f['no_deadline']:,} of these listings do not publish a closing date, which usually means "
              f"the employer hires until the post is filled. Apply early — those listings can disappear "
              f"without warning.</p>")

    p4 = ""
    if f["top_quals"]:
        p4 = ("<p>Most listings accept <strong>" + ", ".join(f["top_quals"][:3]) +
              "</strong>. Every card also shows the age limit and the number of vacancies when the "
              "advertisement includes them.</p>")
    return "".join(x for x in (p1, p2, p3, p4) if x)


def split_intro(html):
    """Lead paragraph stays above the list; the rest moves below it so a phone
    user sees real vacancies within one screen."""
    marker = html.find("</p>")
    if marker < 0:
        return html, ""
    return html[:marker + 4], html[marker + 4:]


def build_faqs(kind, name, f):
    """Five answered questions built from this page's data (FAQPage schema)."""
    qa = []
    qa.append((
        f"How many {name} jobs are open right now?",
        f"There are {f['total']:,} live listings: {f['priv']:,} private-sector and {f['gov']:,} government posts. "
        f"The list on this page is rebuilt every hour, so it always shows the current openings."
    ))
    if f["top_emp"]:
        qa.append((
            f"Which employers are hiring in {name}?",
            "The most active employers right now are " + ", ".join(f["top_emp"]) +
            ". New employers appear as soon as they publish a vacancy."
        ))
    if f["top_quals"]:
        qa.append((
            f"What qualifications do {name} jobs ask for?",
            "The most common requirements are " + ", ".join(f["top_quals"]) +
            ". Open a job page to see the exact qualification, experience and age limit for that post."
        ))
    qa.append((
        "Are there government jobs in this list?",
        (f"Yes — {f['gov']:,} of the {f['total']:,} listings are government posts, from BPS-01 to BPS-22. "
         "Government cards show the department, the scale and the closing date so you can check eligibility first.")
        if f["gov"] else
        "There are no government posts on this page at the moment. Government vacancies in Pakistan are "
        "published in batches, so check back — the list refreshes every hour."
    ))
    if f["soon"]:
        qa.append((
            "When is the last date to apply?",
            f"{len(f['soon'])} listings close within seven days. The earliest deadline belongs to "
            f"{f['soon'][0][1]['title']}. Deadline dates are shown on every card so you never apply late."
        ))
    else:
        qa.append((
            "How do I apply for these jobs?",
            "Open the job page and press the apply button. It takes you to the employer's own site, where you "
            "complete the application. RozgarJobs does not collect CVs and never charges a fee."
        ))
    return qa[:5]


def build_landing_pages(jobs):
    """City / category pages. Only pages with at least 5 real live jobs are built, and each
    one carries its own numbers, employers, deadline data and Q&A — no city-swapped clones."""
    os.makedirs(os.path.join(ROOT, "jobs-in"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "category"), exist_ok=True)
    made = []
    MIN_JOBS = 5

    def emit(prefix, slug, h1, title, crumb, desc, subset, related, kind, name):
        if len(subset) < MIN_JOBS:
            return
        rows = sorted(subset, key=lambda x: (x.get("last_date") or "9999"))[:40]
        canonical = f"{SITE_URL}/{prefix}/{slug}.html" if SITE_URL else f"{prefix}/{slug}.html"
        f = landing_facts(subset)

        crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList",
                  "itemListElement": [
                      {"@type": "ListItem", "position": 1, "name": "Home",
                       "item": (SITE_URL + "/") if SITE_URL else "/"},
                      {"@type": "ListItem", "position": 2, "name": crumb, "item": canonical}]}

        qa = build_faqs(kind, name, f)
        faq_ld = {"@context": "https://schema.org", "@type": "FAQPage",
                  "inLanguage": "en-PK",
                  "mainEntity": [{"@type": "Question", "name": q,
                                  "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in qa]}
        json_ld = _ld(crumbs) + "\n" + _ld(faq_ld)

        faq_block = ('<section class="faq-block" style="margin-top:26px"><h2>Questions about '
                     + esc(name) + "</h2>" +
                     "".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in qa)
                     + "</section>")

        stat_row = (
            f"<span><strong>{f['total']:,}</strong> open</span>"
            f"<span><strong>{f['gov']:,}</strong> government</span>"
            f"<span><strong>{f['priv']:,}</strong> private</span>"
            + (f"<span><strong>{len(f['soon'])}</strong> closing this week</span>" if f["soon"] else "")
        )

        emp_block = ""
        if f["employers"]:
            top = f["employers"].most_common(6)
            emp_block = ('<section style="margin-top:26px"><h2 style="font-size:17px;letter-spacing:-.3px;'
                         'margin:0 0 10px">Employers hiring in ' + esc(name) + "</h2>"
                         '<div class="emp-list">' +
                         "".join(f'<div class="emp-row"><b>{esc(k)}</b>'
                                 f'<span>{_plural(v, "open role")}</span></div>' for k, v in top) +
                         "</div></section>")

        more = ""
        if len(subset) > 40:
            more = (f'<div class="loadmore-wrap"><a class="btn-ghost" '
                    f'href="../index.html?{"city=" if prefix.startswith("jobs-in") else "category="}'
                    f'{urllib.parse.quote(name)}">See all {len(subset):,} vacancies →</a></div>')

        html_out = LANDING_PAGE.format(
            title=esc(title), desc=esc(desc), canonical=esc(canonical),
            json_ld=json_ld, crumb=esc(crumb), h1=esc(h1),
            count=f["total"],
            intro=split_intro(build_intro(kind, name, f))[0],
            intro_rest=split_intro(build_intro(kind, name, f))[1],
            stat_row=stat_row,
            cards="".join(landing_card(j) for j in rows),
            more_block=more,
            employer_block=emp_block,
            faq_block=faq_block,
            related_links="".join(
                f'<a class="chip" href="../{p}/{s}.html">{esc(n)}</a>' for p, s, n in related),
            year=datetime.now().year,
        )
        path = os.path.join(ROOT, prefix, f"{slug}.html")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html_out)
        made.append(f"{prefix}/{slug}.html")

    # ── city pages
    city_related = []
    for city in LANDING_CITIES:
        subset = [j for j in jobs if (j.get("location") or "").lower().startswith(city.lower())]
        city_related.append(("jobs-in", safe_slug(city), f"{city} jobs"))
        emit("jobs-in", safe_slug(city),
             f"Jobs in {city} — Government and Private Vacancies",
             f"Jobs in {city}",
             f"Jobs in {city}",
             f"Live government and private jobs in {city}, updated every hour. See the "
             f"qualification, age limit and closing date for each post before you apply.",
             subset, city_related, "city", city)

    # ── category pages
    cat_related = []
    for cat in LANDING_CATS:
        subset = [j for j in jobs if (j.get("category") or "") == cat]
        cat_related.append(("category", safe_slug(cat), cat))
        emit("category", safe_slug(cat),
             f"{cat} Jobs in Pakistan",
             f"{cat} Jobs in Pakistan",
             f"{cat} jobs",
             f"Open {cat.lower()} vacancies across Pakistan, including remote roles. "
             f"Each listing shows qualification, experience, age limit and the application deadline.",
             subset, cat_related, "category", cat)

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


# ══════════════════════════════════════════════════════════════════════════
#  Keyword landing pages — the phrases people actually type in Pakistan
#  ("fpsc jobs", "ppsc jobs", "sarkari naukri", "pak army jobs").
#  Same rules as city pages: 5+ real jobs, unique data, FAQPage schema.
# ══════════════════════════════════════════════════════════════════════════
PROVINCES = {
    "Punjab": ("Lahore", "Rawalpindi", "Faisalabad", "Multan", "Gujranwala", "Sialkot",
               "Bahawalpur", "Sargodha", "Sheikhupura", "Kasur", "Okara", "Sahiwal",
               "Rahim Yar Khan", "Dera Ghazi Khan", "Jhelum", "Gujrat", "Nankana Sahib",
               "Vehari", "Khanewal", "Attock", "Chakwal", "Mianwali", "Bhakkar", "Layyah"),
    "Sindh": ("Karachi", "Hyderabad", "Sukkur", "Larkana", "Nawabshah", "Mirpur Khas",
              "Jacobabad", "Shikarpur", "Khairpur", "Thatta", "Badin", "Dadu", "Ghotki"),
    "Khyber Pakhtunkhwa": ("Peshawar", "Mardan", "Abbottabad", "Swat", "Mingora", "Kohat",
                           "Bannu", "Dera Ismail Khan", "Charsadda", "Nowshera", "Swabi",
                           "Mansehra", "Haripur", "Dir", "Chitral", "Malakand"),
    "Balochistan": ("Quetta", "Gwadar", "Turbat", "Khuzdar", "Sibi", "Loralai", "Zhob",
                    "Chaman", "Dera Murad Jamali"),
    "Islamabad": ("Islamabad",),
}

KEYWORD_PAGES = [
    ("sarkari-naukri", "Sarkari Naukri — Government Jobs in Pakistan",
     "Every government job on RozgarJobs in one list: federal, provincial, teaching, health, "
     "police and defence posts, with the closing date and eligibility on each card.",
     "Sarkari naukri",
     lambda j: (j.get("sector") or "").lower() == "government"),
    ("fpsc-jobs", "FPSC Jobs 2026 — Federal Public Service Commission Vacancies",
     "Federal government posts advertised through the FPSC, collected in one place with the "
     "closing date, qualification and pay scale on every listing.",
     "FPSC jobs",
     lambda j: any(k in ((j.get("title") or "") + " " + (j.get("company") or "")).lower()
                   for k in ("fpsc", "federal public service commission"))),
    ("ppsc-jobs", "PPSC Jobs 2026 — Punjab Public Service Commission Vacancies",
     "Punjab government posts announced by the PPSC, with the last date, eligibility and "
     "application link for each one.",
     "PPSC jobs",
     lambda j: any(k in ((j.get("title") or "") + " " + (j.get("company") or "")).lower()
                   for k in ("ppsc", "punjab public service commission"))),
    ("nts-jobs", "NTS Jobs 2026 — National Testing Service Vacancies",
     "Posts advertised through the National Testing Service, collected with their closing "
     "dates and eligibility criteria.",
     "NTS jobs",
     lambda j: "nts" in ((j.get("title") or "") + " " + (j.get("company") or "")).lower().split()),
    ("pak-army-jobs", "Pak Army, PAF and Navy Jobs 2026 — Defence Jobs in Pakistan",
     "Defence vacancies open to civilians and soldiers, from soldier general duty to civilian "
     "technical posts, with eligibility and the last date.",
     "Defence jobs",
     lambda j: any(k in ((j.get("title") or "") + " " + (j.get("company") or "")).lower()
                   for k in ("pak army", "pakistan army", "army", "paf", "air force",
                             "navy", "defence", "defense", "rangers", "soldier"))),
    ("police-jobs", "Police Jobs in Pakistan 2026 — Constable, SI and FIA Posts",
     "Police and law-enforcement vacancies across Pakistan, with the physical standard, "
     "qualification and closing date wherever the advertisement gives them.",
     "Police jobs",
     lambda j: any(k in ((j.get("title") or "") + " " + (j.get("company") or "")).lower()
                   for k in ("police", "constable", "sub inspector", "fia", "rangers", "levies"))),
    ("teaching-jobs", "Teaching Jobs in Pakistan 2026 — School, College and University",
     "Teacher, lecturer and educator vacancies across Pakistan, including government school "
     "posts and private schools, with the closing date on each card.",
     "Teaching jobs",
     lambda j: any(k in ((j.get("title") or "") + " " + (j.get("category") or "")).lower()
                   for k in ("teach", "lecturer", "educator", "instructor", "professor",
                             "school", "college"))),
    ("health-jobs", "Health Jobs in Pakistan 2026 — Nurses, Doctors and Technicians",
     "Government and private hospital vacancies: staff nurse, doctor, lab technician, "
     "paramedic and allied health posts.",
     "Health jobs",
     lambda j: any(k in ((j.get("title") or "") + " " + (j.get("category") or "")).lower()
                   for k in ("nurse", "doctor", "medical", "hospital", "lab", "pharmac",
                             "paramedic", "health", "mbbs", "dispenser"))),
    ("bank-jobs", "Bank Jobs in Pakistan 2026 — NBP, Commercial and Islamic Banks",
     "Banking vacancies including government-owned banks such as NBP, with the position, "
     "qualification and closing date.",
     "Bank jobs",
     lambda j: any(k in ((j.get("title") or "") + " " + (j.get("company") or "")).lower()
                   for k in ("bank", "nbp", "hbl", "ubl", "mcb", "askari", "meezan", "banking"))),
]

PROVINCE_PAGES = [
    ("punjab-jobs", "Punjab", "Punjab Jobs 2026 — Government and Private Vacancies",
     "Jobs across Punjab: Lahore, Rawalpindi, Faisalabad, Multan, Gujranwala, Sialkot and "
     "every other district we cover."),
    ("sindh-jobs", "Sindh", "Sindh Jobs 2026 — Karachi, Hyderabad and Sukkur Vacancies",
     "Jobs across Sindh, including Karachi, Hyderabad, Sukkur, Larkana and Mirpur Khas."),
    ("kpk-jobs", "Khyber Pakhtunkhwa", "KPK Jobs 2026 — Peshawar, Mardan and Abbottabad",
     "Jobs across Khyber Pakhtunkhwa: Peshawar, Mardan, Abbottabad, Swat, Kohat and more."),
    ("balochistan-jobs", "Balochistan", "Balochistan Jobs 2026 — Quetta and Gwadar Vacancies",
     "Jobs across Balochistan, including Quetta, Gwadar, Turbat and Khuzdar."),
]

KEYWORD_PAGE = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src &#39;self&#39;; script-src &#39;self&#39; &#39;unsafe-inline&#39;; style-src &#39;self&#39; &#39;unsafe-inline&#39;; img-src &#39;self&#39; https: data:; font-src &#39;self&#39; data:; connect-src &#39;self&#39; https:; form-action &#39;self&#39; mailto:; base-uri &#39;self&#39;; object-src &#39;none&#39;">
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>{title} ({count} Open) | RozgarJobs</title>
<meta name="description" content="{desc}">
<meta name="robots" content="index,follow">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:image" content="{base}/assets/img/og.png">
<link rel="icon" type="image/svg+xml" href="assets/img/mark.svg">
<link rel="apple-touch-icon" href="assets/img/mark.svg">
<link rel="stylesheet" href="assets/css/style.css">
{json_ld}
<style>
  .landing-intro p {{ font-size:15px; line-height:1.62; color:var(--ink-2); margin:0 0 10px; max-width:76ch; }}
  .landing-intro p.lead {{ font-size:16px; color:var(--ink); }}
  .emp-list {{ display:grid; gap:8px; }}
  .emp-row {{ display:flex; justify-content:space-between; gap:12px; font-size:14px; padding:9px 13px;
    background:var(--surface); border:1px solid var(--line); border-radius:10px; }}
  .emp-row b {{ font-weight:650; }} .emp-row span {{ color:var(--muted); font-size:13px; white-space:nowrap; }}
  .faq-block h2 {{ font-size:17px; margin:0 0 10px; }}
  .faq-block details {{ background:var(--surface); border:1px solid var(--line); border-radius:11px; padding:12px 15px; margin-bottom:8px; }}
  .faq-block summary {{ font-weight:650; font-size:14.5px; cursor:pointer; }}
  .faq-block p {{ color:var(--muted); font-size:14px; margin:8px 0 0; line-height:1.6; }}
</style>
<script src="assets/js/analytics.js" defer></script>
</head>
<body>
<header class="site-head">
  <div class="wrap head-in">
    <a class="brand" href="index.html">
      <img class="brand-logo" src="assets/img/mark.svg" alt="" width="38" height="38">
      <span class="brand-text"><strong>Rozgar<span class="bj">Jobs</span></strong><small>Jobs in Pakistan</small></span>
    </a>
    <nav class="head-nav"><a href="index.html">Jobs</a><a href="alerts.html">Alerts</a>
      <a href="guides/index.html">Guides</a><a href="employers.html">Post a job</a></nav>
  </div>
</header>

<div class="topbar">
  <div class="wrap topbar-in">
    <span class="topbar-status"><i class="live-dot"></i><span>{count} live vacancies · updated every hour</span></span>
  </div>
</div>

<section class="wrap" style="padding-top:24px">
  <nav class="crumbs"><a href="index.html">Home</a> <span>/</span> <span>{crumb}</span></nav>
  <h1 style="font-size:clamp(25px,3.4vw,38px);letter-spacing:-1px;margin:10px 0 10px;line-height:1.15">{h1}</h1>
  <div class="landing-intro">{intro}</div>
  <div class="stat-strip" style="margin:14px 0 20px">{stat_row}</div>

  <h2 style="font-size:17px;margin:0 0 12px">Open vacancies right now</h2>
  <div class="job-list">
  {cards}
  </div>
  {more_block}
  {intro_rest}
  {employer_block}
  {faq_block}

  <div class="notice-box" style="margin-top:28px">
    <strong>About this page</strong>
    Every listing links to the original advertisement. RozgarJobs never charges candidates —
    if someone asks you for a fee, <a href="contact.html">report it</a>.
  </div>

  <section style="margin-top:30px">
    <h2 style="font-size:16px;margin:0 0 10px">Browse more</h2>
    <div class="tag-list" style="display:flex;flex-wrap:wrap;gap:7px">{related_links}</div>
  </section>
</section>

<footer class="site-foot" style="margin-top:40px">
  <div class="wrap foot-bottom">
    <span>© {year} RozgarJobs</span>
    <span>Jobs in Pakistan, updated hourly</span>
  </div>
</footer>
</body>
</html>
"""


def keyword_card(j):
    return (f'<a class="job-card" href="jobs/{esc(j["slug"])}.html" '
            f'style="grid-template-columns:64px minmax(0,1fr) auto;text-decoration:none">'
            f'<div class="logo" style="width:56px;height:56px;font-size:14px">'
            f'{esc((j["company"] or "?")[:2].upper())}</div>'
            f'<div class="job-info"><h3 class="job-title" style="margin:0 0 3px">'
            f'{esc(j.get("display_title") or j["title"])}</h3>'
            f'<p class="job-company" style="margin:0 0 7px"><b>{esc(j["company"])}</b>'
            f'{" · " + esc(j["location"]) if j.get("location") else ""}</p>'
            f'<div class="chips">'
            + (f'<span class="chip chip-date">Last date: {esc(human_date(to_ts(j["last_date"])))}</span>'
               if j.get("last_date") else "")
            + (f'<span class="chip">{esc(j["qualification"])}</span>' if j.get("qualification") else "")
            + f'</div></div>'
            f'<div class="job-side"><span class="time">{esc(ago_text(j.get("published")))}</span>'
            f'<span class="apply">Details →</span></div></a>')


def build_keyword_pages(jobs, made_before):
    """Root-level pages for the phrases Pakistanis search for."""
    base = SITE_URL or ""
    made = []
    SHORT = {"sarkari-naukri": "Sarkari naukri", "fpsc-jobs": "FPSC jobs",
             "ppsc-jobs": "PPSC jobs", "nts-jobs": "NTS jobs",
             "pak-army-jobs": "Army / PAF / Navy jobs", "police-jobs": "Police jobs",
             "teaching-jobs": "Teaching jobs", "health-jobs": "Health jobs",
             "bank-jobs": "Bank jobs"}
    related = [("index.html", "All jobs")] + [(f"{sl}.html", SHORT.get(sl, h.split("—")[0].strip()))
                                             for sl, h, _d, _c, _m in KEYWORD_PAGES]
    related += [(f"{s}.html", f"{p} jobs") for s, p, _t, _d in PROVINCE_PAGES]

    def emit(slug, title, desc, crumb, subset, matcher_name):
        if len(subset) < 5:
            return
        rows = sorted(subset, key=lambda x: (x.get("last_date") or "9999"))[:40]
        f = landing_facts(subset)
        qa = build_faqs("keyword", matcher_name, f)
        ld = _ld({"@context": "https://schema.org", "@type": "FAQPage", "inLanguage": "en-PK",
                  "mainEntity": [{"@type": "Question", "name": q,
                                  "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in qa]})
        faq_block = ('<section class="faq-block" style="margin-top:26px"><h2>Questions about '
                     + esc(crumb) + "</h2>" +
                     "".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in qa)
                     + "</section>")
        emp_block = ""
        if f["employers"]:
            emp_block = ('<section style="margin-top:26px"><h2 style="font-size:17px;margin:0 0 10px">'
                         'Employers hiring</h2><div class="emp-list">' +
                         "".join(f'<div class="emp-row"><b>{esc(k)}</b>'
                                 f'<span>{_plural(v, "open role")}</span></div>'
                                 for k, v in f["employers"].most_common(6)) + "</div></section>")
        stat_row = (f"<span><strong>{f['total']:,}</strong> open</span>"
                    f"<span><strong>{f['gov']:,}</strong> government</span>"
                    f"<span><strong>{f['priv']:,}</strong> private</span>"
                    + (f"<span><strong>{len(f['soon'])}</strong> closing this week</span>" if f["soon"] else ""))
        more = ""
        if len(subset) > 40:
            more = (f'<div class="loadmore-wrap"><a class="btn-ghost" href="index.html?q='
                    f'{urllib.parse.quote(crumb)}">See all {len(subset):,} vacancies →</a></div>')

        html_out = KEYWORD_PAGE.format(
            title=esc(title), desc=esc(desc), canonical=esc(f"{base}/{slug}.html"),
            base=esc(base), json_ld=ld, crumb=esc(crumb),
            h1=esc(title.split("—")[0].strip()),
            count=f["total"],
            intro=split_intro(build_intro("keyword", crumb, f))[0],
            intro_rest=split_intro(build_intro("keyword", crumb, f))[1],
            stat_row=stat_row,
            cards="".join(keyword_card(j) for j in rows),
            more_block=more, employer_block=emp_block, faq_block=faq_block,
            related_links="".join(f'<a class="chip" href="{u}">{esc(n)}</a>'
                                  for u, n in related if u != f"{slug}.html")[:6000],
            year=datetime.now().year,
        )
        with open(os.path.join(ROOT, f"{slug}.html"), "w", encoding="utf-8") as fh:
            fh.write(html_out)
        made.append(f"{slug}.html")

    for slug, title, desc, crumb, matcher in KEYWORD_PAGES:
        emit(slug, title, desc, crumb, [j for j in jobs if matcher(j)], crumb)

    for slug, prov, title, desc in PROVINCE_PAGES:
        places = {p.lower() for p in PROVINCES[prov]}
        subset = [j for j in jobs
                  if (j.get("location") or "").split(",")[0].strip().lower() in places]
        emit(slug, title, desc, f"{prov} jobs", subset, prov)

    print(f"     {'':12s} {len(made):4d} keyword pages")
    return made



# ══════════════════════════════════════════════════════════════════════════
#  Commission / recruiter pages — "fpsc jobs", "ppsc jobs", "nts jobs",
#  "police jobs". These bodies publish few vacancies at a time, so the page
#  must still be worth reading on a quiet week: how the body recruits, how the
#  written test works, what to prepare. Live vacancies are merged in when they
#  exist, never invented.
# ══════════════════════════════════════════════════════════════════════════
COMMISSION_PAGES = [
    {
        "slug": "fpsc-jobs",
        "title": "FPSC Jobs 2026 — Federal Public Service Commission Vacancies",
        "h1": "FPSC Jobs",
        "desc": "Federal Public Service Commission vacancies in Pakistan: how the FPSC recruits, "
                "which posts it advertises, how the written test and viva work, and every live "
                "federal post we track.",
        "match": ("fpsc", "federal public service commission"),
        "official": "https://www.fpsc.gov.pk",
        "official_name": "fpsc.gov.pk",
        "body": [
            ("What the FPSC does",
             "The Federal Public Service Commission is the constitutional body that hires for federal "
             "ministries and departments — BPS-16 and above in most cases. It does not run one big "
             "annual exam like the CSS; instead it advertises individual posts through consolidated "
             "advertisements published on its own website and in national newspapers, usually on a "
             "monthly cycle."),
            ("Which posts appear",
             "Recent FPSC advertisements have covered assistant directors, inspectors, "
             "superintendents, assistant private secretaries, librarians, staff nurses, assistant "
             "managers and technical posts in ministries such as Finance, Interior, Commerce, "
             "National Health Services and the Federal Board of Revenue. Posts below BPS-16 in the "
             "federal government are usually filled by the departments themselves, not the FPSC."),
            ("How the selection works",
             "Applications are submitted online through the FPSC portal, followed by a fee challan "
             "paid at a bank. Shortlisted candidates sit a written test — a screening test with "
             "objective papers relevant to the post — and those who pass go to an interview or viva "
             "before the commission. Final merit is calculated from the written test, the viva and, "
             "for some posts, experience and qualifications."),
            ("What to prepare",
             "Read the advertisement carefully for the exact syllabus: most FPSC screening tests mix "
             "English, general knowledge, Pakistan affairs, basic mathematics and professional "
             "questions for the specific post. Eligibility is checked strictly — age limit, degree "
             "and required experience must match on the closing date, not after it."),
        ],
        "faq": [
            ("How often does the FPSC advertise jobs?",
             "Consolidated advertisements usually appear every month, with individual posts added "
             "during the month. Check the official FPSC website for the current advertisement and "
             "the closing date; this page lists the federal vacancies our sources publish."),
            ("Is there an age relaxation in FPSC jobs?",
             "The advertisement states the age limit and any relaxation that applies — general age "
             "relaxation for certain categories is granted by the Establishment Division and is "
             "normally mentioned on the advert itself."),
            ("Can I apply for more than one FPSC post?",
             "Yes, but each post needs a separate application and a separate fee. Applying for one "
             "post does not cover another."),
        ],
    },
    {
        "slug": "ppsc-jobs",
        "title": "PPSC Jobs 2026 — Punjab Public Service Commission Vacancies",
        "h1": "PPSC Jobs",
        "desc": "Punjab Public Service Commission vacancies: how the PPSC recruits for Punjab "
                "departments, what the written test covers, and every live Punjab post we track.",
        "match": ("ppsc", "punjab public service commission"),
        "official": "https://ppsc.gop.pk",
        "official_name": "ppsc.gop.pk",
        "body": [
            ("What the PPSC does",
             "The Punjab Public Service Commission hires for the provincial government of Punjab — "
             "lecturers, assistant directors, tehsildars, inspectors, medical officers and other "
             "provincial posts. It publishes consolidated advertisements for the whole province, "
             "usually several times a year."),
            ("The written test",
             "Most PPSC recruitment now runs through a written examination held at centres across "
             "Punjab, followed by an interview. The written paper is subject-specific for teaching "
             "and technical posts and general for administrative posts, and the syllabus is published "
             "with the advertisement."),
            ("Applying",
             "Applications go through the PPSC online portal. Upload the required documents, pay the "
             "fee challan for your category, and keep the roll number slip — it is needed for the "
             "test centre and the interview."),
        ],
        "faq": [
            ("How many times a year does the PPSC advertise?",
             "Advertisements are published throughout the year, with larger consolidated "
             "advertisements a few times a year for lecturer and administrative posts."),
            ("What is the PPSC fee?",
             "The fee depends on the post and the candidate category and is stated on the "
             "advertisement. It is paid through a bank challan or the online payment option in the "
             "portal — never to an individual."),
        ],
    },
    {
        "slug": "nts-jobs",
        "title": "NTS Jobs 2026 — National Testing Service Vacancies and Test Dates",
        "h1": "NTS Jobs",
        "desc": "Jobs advertised through the National Testing Service in Pakistan, plus how NTS "
                "tests work, how to apply and what to carry on the test day.",
        "match": ("nts", "national testing service"),
        "official": "https://www.nts.org.pk",
        "official_name": "nts.org.pk",
        "body": [
            ("What the NTS does",
             "The National Testing Service conducts recruitment tests on behalf of employers — "
             "government departments, schools, colleges, hospitals and some private organisations. "
             "The employer advertises the post and sets the criteria; the NTS runs the test and "
             "publishes the result."),
            ("Applying through the NTS",
             "Each advertisement includes an NTS application form and a fee. Fill the form, deposit "
             "the fee in the nominated bank account, and post or submit the form before the deadline. "
             "The roll number slip is issued on the NTS website a few days before the test — print "
             "it, because you cannot sit the paper without it."),
            ("On the test day",
             "Bring the printed roll number slip, your original CNIC and the same photographs used on "
             "the form. Reach the centre early: entry closes before the paper starts."),
        ],
        "faq": [
            ("Are NTS jobs government jobs?",
             "Not always. The NTS is a testing body, not an employer — the job is with whichever "
             "department or organisation placed the advertisement. Check the employer named on the "
             "advert."),
            ("How do I find my NTS roll number slip?",
             "On the NTS website, enter your CNIC number in the roll number slip section. Slips are "
             "normally published a few days before the test date."),
        ],
    },
    {
        "slug": "police-jobs",
        "title": "Police Jobs in Pakistan 2026 — Constable, SI and FIA Vacancies",
        "h1": "Police Jobs",
        "desc": "Police and law-enforcement vacancies across Pakistan: constable, sub-inspector, "
                "FIA, Frontier Corps and traffic police posts, with eligibility and physical standards.",
        "match": ("police", "constable", "sub inspector", "fia", "rangers", "levies"),
        "official": "https://www.nip.gov.pk",
        "official_name": "National Police Portal",
        "body": [
            ("Who recruits police in Pakistan",
             "Each province runs its own police force — Punjab, Sindh, Khyber Pakhtunkhwa, "
             "Balochistan and Islamabad capital territory — and each advertises through its own "
             "board. Federal agencies such as the FIA, the Anti-Narcotics Force and the Rangers "
             "recruit separately under the Ministry of Interior."),
            ("Eligibility for a constable post",
             "Most constable advertisements ask for matric or intermediate, an age limit of roughly "
             "18 to 25 with the relaxation printed on the advert, minimum height and chest "
             "measurements, and physical tests: running, push-ups, sit-ups and a Chin-up where "
             "applied. Sub-inspector posts usually require a bachelor's degree."),
            ("The selection process",
             "Written test or MCQ screening, then physical measurement and endurance tests, then a "
             "medical examination and an interview. Candidates who clear each stage are called "
             "forward in small batches — check the force's own website for the schedule."),
        ],
        "faq": [
            ("What height is required for police constable?",
             "It differs by province and is printed on each advertisement. Typical minimums are "
             "around 5 feet 5 inches with a chest measurement specified separately. Relaxation, "
             "where it applies, is stated in the same advert."),
            ("Do women apply for police jobs in Pakistan?",
             "Yes — all provincial forces recruit women constables and officers, and advertisements "
             "reserve a quota for them. Physical standards for women are specified separately on the "
             "advert."),
        ],
    },
]


def build_commission_pages(jobs, base):
    """Editorial pages for the big recruiting bodies: unique body copy plus
    whatever live vacancies match. Built at root level so the URL is short."""
    made = []
    others = "".join(
        f'<a class="chip" href="{c["slug"]}.html">{esc(c["h1"])}</a>'
        for c in COMMISSION_PAGES)
    for c in COMMISSION_PAGES:
        keys = c["match"]
        subset = [j for j in jobs
                  if any(k in ((j.get("title") or "") + " " + (j.get("company") or "")).lower()
                         for k in keys)]
        rows = sorted(subset, key=lambda x: (x.get("last_date") or "9999"))[:40]
        f = landing_facts(subset) if subset else None

        body = "".join(f"<h2>{esc(h)}</h2><p>{esc(t)}</p>" for h, t in c["body"])
        faq = c["faq"] + ([(
            f"How many {c['h1']} vacancies are live right now?",
            f"{f['total']} right now. This page is rebuilt every hour, so the list below is current."
        )] if f else [])
        ld = _ld({"@context": "https://schema.org", "@type": "FAQPage", "inLanguage": "en-PK",
                  "mainEntity": [{"@type": "Question", "name": q,
                                  "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]})
        faq_block = ('<section class="faq-block" style="margin-top:26px"><h2>Common questions</h2>' +
                     "".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>"
                             for q, a in faq) + "</section>")

        if rows:
            jobs_block = ('<h2 style="font-size:17px;margin:0 0 12px">Live vacancies right now</h2>'
                          '<div class="job-list">' + "".join(keyword_card(j) for j in rows) + "</div>")
            intro = (f'<p class="lead"><strong>{len(subset)} live vacancies</strong> matching this '
                     f'body are on RozgarJobs right now. The guide below explains how the process '
                     f'works; the list shows what is open today.</p>')
        else:
            jobs_block = ('<div class="notice-box" style="margin:18px 0"><strong>No live vacancies '
                          'from this body right now.</strong> Advertisements appear in cycles — '
                          'the guide below stays accurate between them, and the '
                          '<a href="sarkari-naukri.html">government jobs list</a> shows every '
                          'federal and provincial post we are tracking today.</div>')
            intro = ('<p class="lead">No advertisements from this body are open at the moment. '
                     'Everything below explains how it recruits, so you know exactly what to '
                     'prepare before the next advertisement appears.</p>')

        html_out = KEYWORD_PAGE.format(
            title=esc(c["title"]), desc=esc(c["desc"]), canonical=esc(f"{base}/{c['slug']}.html"),
            base=esc(base), json_ld=ld, crumb=esc(c["h1"]), h1=esc(c["h1"]),
            count=(f["total"] if f else 0),
            intro=intro + body, intro_rest="",
            stat_row=(f"<span><strong>{f['total']}</strong> live</span>"
                      f"<span><strong>{f['gov']}</strong> government</span>" if f else
                      f'<span><strong>Official site</strong> <a href="{c["official"]}" target="_blank" '
                      f'rel="noopener nofollow">{esc(c["official_name"])}</a></span>'),
            cards="", more_block=jobs_block,
            employer_block="", faq_block=faq_block,
            related_links=others + '<a class="chip" href="index.html">All jobs</a>',
            year=datetime.now().year,
        )
        # KEYWORD_PAGE already places {more_block} after the cards, and we passed
        # the live list there — but the intro body must sit under the listings.
        html_out = html_out.replace("{intro_rest}", "")
        with open(os.path.join(ROOT, f"{c['slug']}.html"), "w", encoding="utf-8") as fh:
            fh.write(html_out)
        made.append(f"{c['slug']}.html")

    print(f"     {'':12s} {len(made):4d} commission pages")
    return made


def write_locations_page():
    """A hub that links every city and category page that actually exists.
    Google follows links, not sitemaps — this is the internal-link backbone."""
    city_rows, cat_rows = [], []
    city_dir = os.path.join(ROOT, "jobs-in")
    cat_dir = os.path.join(ROOT, "category")
    for c in LANDING_CITIES:
        fp = os.path.join(city_dir, f"{safe_slug(c)}.html")
        if os.path.exists(fp):
            city_rows.append(f'<a class="loc" href="jobs-in/{safe_slug(c)}.html">{esc(c)}'
                             f'<span>jobs in {esc(c.lower())}</span></a>')
    for c in LANDING_CATS:
        fp = os.path.join(cat_dir, f"{safe_slug(c)}.html")
        if os.path.exists(fp):
            cat_rows.append(f'<a class="loc" href="category/{safe_slug(c)}.html">{esc(c)}'
                            f'<span>{esc(c.lower())} jobs</span></a>')

    kw_rows = []
    for slug, title, _d, _c, _m in KEYWORD_PAGES:
        if os.path.exists(os.path.join(ROOT, f"{slug}.html")):
            kw_rows.append(f'<a class="loc" href="{slug}.html">{esc(title.split("—")[0].strip())}'
                           f'<span>popular search</span></a>')
    for slug, prov, _t, _d in PROVINCE_PAGES:
        if os.path.exists(os.path.join(ROOT, f"{slug}.html")):
            kw_rows.append(f'<a class="loc" href="{slug}.html">{esc(prov)}'
                           f'<span>province</span></a>')

    guides = [("national-job-portal-guide", "How to apply on NJP"),
              ("bps-pay-scales", "BPS pay scales explained"),
              ("documents-for-government-job", "Documents checklist"),
              ("spot-fake-job-advertisement", "Spot a fake job ad")]
    guide_rows = "".join(f'<a class="loc" href="guides/{g}.html">{esc(t)}<span>guide</span></a>'
                         for g, t in guides
                         if os.path.exists(os.path.join(ROOT, "guides", f"{g}.html")))

    base = SITE_URL or ""
    html = f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' https: data:; font-src 'self' data:; connect-src 'self' https:; form-action 'self' mailto:; base-uri 'self'; object-src 'none'">
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>Browse Jobs by City and Category in Pakistan | RozgarJobs</title>
<meta name="description" content="Every city and category page on RozgarJobs: Karachi, Lahore, Islamabad, Rawalpindi, Peshawar and more, plus software, health, teaching, finance and government job categories.">
<meta name="theme-color" content="#0f2a47">
<link rel="canonical" href="{base}/locations.html">
<meta property="og:type" content="website">
<meta property="og:site_name" content="RozgarJobs">
<meta property="og:title" content="Browse jobs by city and category">
<meta property="og:description" content="All city and category job pages in one place.">
<meta property="og:image" content="{base}/assets/img/og.png">
<link rel="icon" type="image/svg+xml" href="assets/img/mark.svg">
<link rel="apple-touch-icon" href="assets/img/mark.svg">
<link rel="stylesheet" href="assets/css/style.css">
<style>
  .loc-wrap {{ padding: 26px 0 20px; }}
  .loc-wrap h1 {{ font-size: clamp(25px,3.2vw,36px); letter-spacing:-1px; margin:0 0 10px; }}
  .loc-wrap .lede {{ color: var(--muted); font-size: 15.5px; max-width: 70ch; margin: 0 0 24px; }}
  .loc-wrap h2 {{ font-size: 17px; letter-spacing:-.3px; margin: 28px 0 12px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 10px; }}
  .loc {{ display: flex; flex-direction: column; gap: 2px; padding: 13px 15px; text-decoration: none;
    background: var(--surface); border: 1px solid var(--line); border-radius: 11px;
    color: var(--ink); font-weight: 650; font-size: 14.5px; }}
  .loc span {{ font-weight: 500; font-size: 12px; color: var(--muted); }}
  .loc:hover {{ border-color: var(--brand); }}
</style>
</head>
<body>
<header class="site-head">
  <div class="wrap head-in">
    <a class="brand" href="index.html">
      <img class="brand-logo" src="assets/img/mark.svg" alt="" width="38" height="38">
      <span class="brand-text"><strong>Rozgar<span class="bj">Jobs</span></strong><small>Jobs in Pakistan</small></span>
    </a>
    <nav class="head-nav"><a href="index.html">Jobs</a><a href="alerts.html">Alerts</a>
      <a href="guides/index.html">Guides</a><a href="employers.html">Post a job</a></nav>
  </div>
</header>

<main class="wrap loc-wrap">
  <h1>Browse jobs by city and category</h1>
  <p class="lede">Every place and field we cover. Each page is rebuilt every hour with the vacancies that are
  actually open, so a page disappears when it has nothing live behind it.</p>

  <h2>Cities</h2>
  <div class="grid">{''.join(city_rows) or '<p>No city pages yet.</p>'}</div>

  <h2>Popular searches</h2>
  <div class="grid">{''.join(kw_rows) or '<p>No keyword pages yet.</p>'}</div>

  <h2>Categories</h2>
  <div class="grid">{''.join(cat_rows) or '<p>No category pages yet.</p>'}</div>

  <h2>Guides</h2>
  <div class="grid">{guide_rows}</div>

  <h2>All jobs</h2>
  <p style="font-size:14.6px"><a href="index.html" style="color:var(--brand);text-decoration:underline">
    Search every live vacancy</a> — filter by city, category, sector or keyword.</p>
</main>

<footer class="site-foot">
  <div class="wrap foot-bottom">
    <span>&copy; {datetime.now().year} RozgarJobs</span>
    <span>Jobs in Pakistan, updated hourly</span>
  </div>
</footer>

<nav class="bottom-nav" aria-label="Main navigation">
  <a href="index.html"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 10.5 12 4l8 6.5V20H4z"/><path d="M9.5 20v-5.5h5V20"/></svg><span>Jobs</span></a>
  <a href="alerts.html"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></svg><span>Alerts</span></a>
  <a href="index.html?saved=1"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round" aria-hidden="true"><path d="M12 3.6l2.6 5.4 5.9.8-4.3 4.1 1.1 5.8L12 16.9 6.7 19.7l1.1-5.8L3.5 9.8l5.9-.8z"/></svg><span>Saved</span></a>
  <a href="employers.html"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg><span>Post a job</span></a>
</nav>
</body>
</html>
"""
    with open(os.path.join(ROOT, "locations.html"), "w", encoding="utf-8") as f:
        f.write(html)
    return len(city_rows) + len(cat_rows) + len(guide_rows)


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
  <title>RozgarJobs — latest jobs</title>
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
    indexable = [j for j in jobs if is_indexable(j)]

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
    for kw in glob.glob(os.path.join(ROOT, "*-jobs.html")) + glob.glob(os.path.join(ROOT, "sarkari-naukri.html")):
        name = os.path.basename(kw)
        if name == "jobs-in.html":
            continue
        pages += (f"<url><loc>{esc(base)}/{name}</loc><lastmod>{now_iso}</lastmod>"
                  f"<changefreq>daily</changefreq><priority>0.8</priority></url>")
    pages += (f"<url><loc>{esc(base)}/</loc><lastmod>{now_iso}</lastmod>"
              f"<changefreq>hourly</changefreq><priority>1.0</priority></url>"
              f"<url><loc>{esc(base)}/employers.html</loc><lastmod>{now_iso}</lastmod>"
              f"<changefreq>monthly</changefreq><priority>0.5</priority></url>")
    for extra in ("about.html", "contact.html", "alerts.html", "privacy.html", "terms.html",
                  "locations.html", "verification.html"):
        pages += (f"<url><loc>{esc(base)}/{extra}</loc><lastmod>{now_iso}</lastmod>"
                  f"<changefreq>daily</changefreq><priority>0.6</priority></url>")
    for g in sorted(glob.glob(os.path.join(ROOT, "guides", "*.html"))):
        gp = os.path.basename(g)
        pages += (f"<url><loc>{esc(base)}/guides/{gp}</loc><lastmod>{now_iso}</lastmod>"
                  f"<changefreq>monthly</changefreq><priority>0.6</priority></url>")

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

    live_count = len([j for j in jobs if j["source"] in SCHEMA_OK])
    llms = f"""# RozgarJobs
> Free job board for Pakistan. Government, private and remote vacancies, updated every hour,
> with the closing date, salary, qualification and age limit on every listing.

Site: {base}/
Language: English (en-PK)
Jobs live now: {live_count}

## Main pages
- [All jobs]({base}/): search and filter every live vacancy
- [Government jobs]({base}/): filter the Government toggle
- [Job alerts]({base}/alerts.html): email and RSS alerts
- [Post a job]({base}/employers.html): employer listings
- [All locations]({base}/locations.html): every city and category page
- [Guides]({base}/guides/index.html): NJP, BPS scales, documents, scams
- [About]({base}/about.html) · [Contact]({base}/contact.html) · [Privacy]({base}/privacy.html) · [Terms]({base}/terms.html)

## City pages
""" + "".join(f"- [{c} jobs]({base}/jobs-in/{safe_slug(c)}.html)\n" for c in LANDING_CITIES
              if os.path.exists(os.path.join(ROOT, "jobs-in", f"{safe_slug(c)}.html"))) + f"""
## Category pages
""" + "".join(f"- [{c}]({base}/category/{safe_slug(c)}.html)\n" for c in LANDING_CATS
              if os.path.exists(os.path.join(ROOT, "category", f"{safe_slug(c)}.html"))) + f"""
## Notes
- Every job page links to the original advertisement; Rozgar is an index, not the employer.
- We never charge candidates. Report a listing that asks for money.
- Machine-readable feeds: [jobs.json]({base}/data/jobs.json) · [RSS]({base}/feed.xml) · [sitemap]({base}/sitemap.xml)
"""
    with open(os.path.join(ROOT, "llms.txt"), "w", encoding="utf-8") as f:
        f.write(llms)

    with open(os.path.join(ROOT, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("User-agent: *\nAllow: /\n\n"
                "User-agent: GPTBot\nAllow: /\n\n"
                "User-agent: Google-Extended\nAllow: /\n\n"
                f"Sitemap: {base}/sitemap.xml\n"
                f"# LLM-friendly map: {base}/llms.txt\n")
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
            pk_rows = pk_sources.collect(limit_per_source=int(os.environ.get("PK_LIMIT", "320")))
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
        j["description_text"] = j.get("description_text") or j.get("description") or ""
        enforce_english(j)                      # site is English-only
        j = finish(j)                           # enrichment + indexability + slug
        j["is_pk"] = True
        j["pak_friendly"] = True
        j["region"] = "Asia"
        j["remote"] = False
        j["description"] = j["description_text"]

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

    def richness(j):
        """Prefer the copy of a duplicated job that carries the most detail."""
        score = 0
        for f in ("qualification", "age_limit", "vacancies", "bps", "last_date",
                  "description_text", "salary", "how_to_apply"):
            if j.get(f):
                score += 1
        return (score, j.get("published", 0))

    for j in sorted(collected, key=richness, reverse=True):
        if j["id"] in seen_ids:
            continue
        # normalise the key so "Jobs in Lahore" and "Jobs  Lahore" collide
        key = re.sub(r"[^a-z0-9]", "", (j["title"] + " " + j["company"]).lower())[:70]
        if key in seen_keys:
            continue
        if j.get("published") and j["published"] < cutoff:
            continue
        seen_ids.add(j["id"])
        seen_keys.add(key)
        jobs.append(j)
        if len(jobs) >= MAX_JOBS:
            break

    # ── relevance gate ───────────────────────────────────────────────────
    # A "jobs in Pakistan" site must not be 78% German on-site vacancies.
    # Only jobs a candidate in Pakistan can act on are published: local jobs
    # and remote roles open to Pakistan. Everything else is dropped before a
    # page, a poster or a sitemap entry is created.
    # Pakistani boards mix results, admit cards and date sheets into their job
    # feeds. Those are not vacancies: they have no employer, no salary and no
    # apply link, and publishing them would make the site look like a results
    # portal to both readers and Google.
    NOT_A_JOB = ("result", "admit card", "roll number slip", "date sheet",
                 "date sheet", "answer key", "past paper", "guess paper",
                 "merit list", "interview schedule", "test schedule",
                 "fee challan", "advertisement no", "announcement")
    before = len(jobs)
    jobs = [j for j in jobs
            if not any(k in (j.get("title") or "").lower() for k in NOT_A_JOB)]
    noise = before - len(jobs)
    if noise:
        print(f"     {'':12s} {noise:4d} result/notice posts skipped")

    before = len(jobs)
    jobs = [j for j in jobs if j.get("is_pk") or j.get("pak_friendly")]
    dropped = before - len(jobs)
    if dropped:
        print(f"     {'':12s} {dropped:4d} out-of-scope jobs skipped")

    now = int(time.time())
    for j in jobs:
        j["age_days"] = max(0, int((now - (j.get("published") or now)) / 86400))

    # ── write data
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "count": len(jobs),
        "companies": len({j["company"].lower() for j in jobs}),
        "out_of_scope": dropped,
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

    # which landing pages will exist (same gate as build_landing_pages)
    global CITY_PAGES, CAT_PAGES
    CITY_PAGES = landing_city_set(jobs)
    CAT_PAGES = landing_cat_set(jobs)

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
    kw_urls = build_keyword_pages(jobs, landing_urls)
    kw_urls += build_commission_pages(jobs, SITE_URL or "")
    landing_urls = landing_urls + kw_urls
    write_feed(jobs)
    n_loc = write_locations_page()
    print(f"     {'':12s} {n_loc:4d} location links")
    n_maps = write_sitemaps(jobs, landing_urls)
    print(f"     {'':12s} {len(landing_urls):4d} SEO pages, {n_maps} sitemaps")

    print(f"\nSaved {len(jobs)} jobs  •  {pages} detail pages  •  "
          f"{meta['companies']} companies  •  {meta['new_today']} new today")
    return 0 if jobs else 1


if __name__ == "__main__":
    raise SystemExit(main())
