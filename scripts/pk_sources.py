#!/usr/bin/env python3
"""
Rozgar — Pakistan job sources
=============================
Extracts *facts* from public Pakistani job pages (title, employer, city,
vacancies, BPS/grade, qualification, experience, age limit, last date,
how to apply). Each listing keeps a link to the original page.

Sources
-------
• NJP — National Jobs Portal (njp.gov.pk)      government, structured pages
• JobsAlert.pk                                  WordPress REST API (full text)
• Ilmkidunya                                    government/private, structured tables

All three allow crawling (robots.txt open). We store only short factual
excerpts + a link and we always credit the source. Removal is a one-line
change in SOURCES_ENABLED.
"""

import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")
TIMEOUT = 30
MAX_PER_SOURCE = 90

SOURCES_ENABLED = {"njp": True, "jobsalert": True, "ilmkidunya": True}

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


# ── http ────────────────────────────────────────────────────────────────────
def _get(url, accept="text/html", retries=2):
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": accept,
                "Accept-Language": "en-US,en;q=0.9",
            })
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.2 * (attempt + 1))
    raise last


def _json(url):
    return json.loads(_get(url, accept="application/json"))


# ── text helpers ────────────────────────────────────────────────────────────
def txt(raw):
    if not raw:
        return ""
    s = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    s = html.unescape(s)
    s = re.sub(r"<(br|/p|/div|/li|/tr|/h[1-6])[^>]*>", "\n", s, flags=re.I)
    s = TAG_RE.sub(" ", s)
    s = html.unescape(s)
    s = s.replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


def one_line(s):
    return WS_RE.sub(" ", (s or "")).strip()


def clip(s, n):
    s = one_line(s)
    if len(s) <= n:
        return s
    cut = s[:n]
    return (cut.rsplit(" ", 1)[0] if " " in cut else cut).rstrip(" ,.;:-") + "…"


DATE_RE = re.compile(
    r"(\d{1,2}\s*(?:st|nd|rd|th)?\s*[-/., ]?\s*"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*[-/., ]?\s*\d{2,4}"
    r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}\s*,?\s*\d{2,4}"
    r"|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})", re.I)

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def parse_date_any(s):
    """Return YYYY-MM-DD from every date shape used on Pakistani job sites."""
    if not s:
        return ""
    s = one_line(str(s))
    m = DATE_RE.search(s)
    if not m:
        return ""
    raw = m.group(1)
    raw = re.sub(r"(\d)(st|nd|rd|th)", r"\1", raw, flags=re.I)
    raw = raw.replace(".", " ").replace(",", " ").replace("/", "-").replace("–", "-")

    # find the year first (last 4-digit or 2-digit group), then day + month name
    year = None
    ym = re.search(r"\b(20\d{2}|19\d{2})\b", raw)
    if ym:
        year = int(ym.group(1))
    day = None
    dm = re.search(r"\b(\d{1,2})\b", raw)
    if dm:
        day = int(dm.group(1))
    mon = None
    for token in re.findall(r"[A-Za-z]{3,}", raw):
        if token[:3].lower() in MONTHS:
            mon = MONTHS[token[:3].lower()]
            break

    if mon is None:
        # numeric form 23-10-2026 (d-m-y) or 10-23-2026 (m-d-y)
        nums = [int(n) for n in re.findall(r"\b\d{1,2}\b", raw)][:2]
        nums = [n for n in nums if n != day or True]
        if len(nums) >= 2:
            a, b = nums[0], nums[1]
            if year is None:
                return ""
            if a > 12:
                day, mon = a, b
            elif b > 12:
                day, mon = b, a
            else:
                day, mon = a, b
        else:
            return ""
    if year is None:
        # 2-digit year such as 09-Nov-26 -> assume 20xx
        ym2 = re.search(r"\b(\d{2})\b(?!.*\b\d{2}\b)", raw)
        if ym2:
            y = int(ym2.group(1))
            year = 2000 + y if y < 80 else 1900 + y
    if not (year and mon and day):
        return ""
    # sanity: the deadline of a live job is never far in the past
    today = date.today()
    try:
        d = date(year, mon, day)
    except ValueError:
        return ""
    if year < today.year - 1 or year > today.year + 3:
        return ""
    return d.strftime("%Y-%m-%d")


def field_next(lines, *labels, span=3):
    """Label on one line, value a couple of lines below (JobsAlert style)."""
    for lab in labels:
        for i, ln in enumerate(lines):
            if ln.strip().rstrip(":").lower() == lab.lower():
                for j in range(i + 1, min(i + 1 + span, len(lines))):
                    v = lines[j].strip()
                    if v and not v.endswith(":"):
                        return v
            if ln.strip().lower().startswith(lab.lower() + ":"):
                vals = ln.split(":", 1)[1].strip()
                if vals:
                    return vals
    return ""


def field(text, *labels):
    """Pull 'Label: value' style facts out of a block of text."""
    for lab in labels:
        # value runs to the end of the line (labels on Pakistani sites are
        # separated by newlines once the HTML is flattened)
        pat = re.compile(rf"(?:^|\n)\s*{re.escape(lab)}\s*[:\-–]\s*(.{{2,160}})", re.I)
        m = pat.search(text)
        if m:
            v = one_line(m.group(1)).strip(" .;:-")
            if v and len(v) > 1 and not v.lower().startswith(("and ", "or ")):
                return v
        # same line fallback: "Age Limit: 18-30 Years"
        pat2 = re.compile(rf"{re.escape(lab)}\s*[:\-–]\s*(.{{2,80}}?)(?:\.|$)", re.I)
        m = pat2.search(text)
        if m:
            v = one_line(m.group(1)).strip(" .;:-")
            if v and len(v) > 1:
                return v
    return ""


def classify_pk(title, body=""):
    t = f"{title} {body[:400]}".lower()
    if any(k in t for k in ["army", "navy", "air force", "paf ", "pak navy", "soldier",
                            "fia ", "police", "rangers", "fc ", "army"]):
        return "Forces & Security"
    if any(k in t for k in ["lecturer", "teacher", "professor", "education", "school",
                            "college", "university", "educator"]):
        return "Education & Teaching"
    if any(k in t for k in ["doctor", "nurse", "medical", "health", "hospital",
                            "pharmacist", "technician", "mbbs", "paramedic"]):
        return "Health & Medical"
    if any(k in t for k in ["engineer", "civil", "electrical", "mechanical", "wAPDA",
                            "construction", "sub-engineer"]):
        return "Engineering"
    if any(k in t for k in ["accountant", "accounts", "finance", "audit", "bank",
                            "cashier", "treasurer"]):
        return "Finance & Accounting"
    if any(k in t for k in ["driver", "chowkidar", "sweeper", "helper", "cook",
                            "messenger", "naib qasid", "attendant", "guard", "malhi",
                            "dispatch", "labour", "labor"]):
        return "Support Staff (Class IV)"
    if any(k in t for k in ["clerk", "assistant", "stenographer", "typist", "junior",
                            "superintendent", "officer", "director", "manager"]):
        return "Admin & Clerical"
    if any(k in t for k in ["software", "developer", "programmer", "it ", "computer",
                            "network", "data", "web"]):
        return "IT & Computer"
    return "Government / Other"


def norm_qual(text):
    t = (text or "").lower()
    for key, label in [
        ("phd", "PhD"), ("m.phil", "M.Phil"), ("master", "Master's"), ("mba", "MBA"),
        ("bachelor", "Bachelor's"), ("graduation", "Graduate"), ("graduate", "Graduate"),
        ("intermediate", "Intermediate (FA/FSc)"), ("f.sc", "Intermediate (FA/FSc)"),
        ("fsc", "Intermediate (FA/FSc)"), ("matric", "Matric"),
        ("middle", "Middle"), ("primary", "Primary"),
    ]:
        if key in t:
            return label
    return clip(text, 46) if text else ""


# ═══════════════════════════════════════════════════════════════════════════
#  1. National Jobs Portal (njp.gov.pk) — government, structured pages
# ═══════════════════════════════════════════════════════════════════════════
def fetch_njp(limit=MAX_PER_SOURCE):
    out, seen = [], set()
    for page in range(1, 8):
        if len(out) >= limit:
            break
        try:
            html_src = _get(f"https://njp.gov.pk/jobs/live?page={page}").decode("utf-8", "ignore")
        except Exception as e:  # noqa: BLE001
            print(f"    njp list p{page}: {type(e).__name__}", flush=True)
            break
        ids = re.findall(r"njp\.gov\.pk/jobs/(\d+)", html_src)
        ids = list(dict.fromkeys(ids))
        if not ids:
            break
        for jid in ids:
            if jid in seen or len(out) >= limit:
                continue
            seen.add(jid)
            try:
                detail = _get(f"https://njp.gov.pk/jobs/{jid}").decode("utf-8", "ignore")
            except Exception:
                continue
            job = _parse_njp(jid, detail)
            if job:
                out.append(job)
            time.sleep(0.35)
    return out


def _parse_njp(jid, src):
    body = txt(src)
    lines = [ln.strip() for ln in body.split("\n") if ln.strip()]

    # The page starts: Contract / <title> / <employer> / Government of Pakistan / Grade / ...
    title = ""
    for pat in (r'<h1[^>]*>(.*?)</h1>', r'<h2[^>]*>(.*?)</h2>',
                r'<meta property="og:title" content="([^"]+)"'):
        m = re.search(pat, src, re.S | re.I)
        if m:
            title = one_line(txt(m.group(1)))
            if title:
                break

    employer = field(body, "About Employer") or ""
    if not employer:
        # first "Government of Pakistan"-preceding lines hold the department
        for i, ln in enumerate(lines[:14]):
            if ln.lower().startswith("government of pakistan") and i:
                employer = lines[i - 1]
                break

    grade = field(body, "Grade")
    job_type = field(body, "Job Type") or "Full Time"
    vacancies = field(body, "Vacancies")
    vac_num = re.search(r"(\d+)", vacancies or "")
    experience = field(body, "Experience")
    age = field(body, "Age Limit")
    deadline = parse_date_any(field(body, "Deadline") or field(body, "Application Deadline"))
    posted = parse_date_any(field(body, "Posted"))
    email = field(body, "Email")
    landline = field(body, "Landline") or field(body, "Phone")

    desc_start = body.find("Job Description")
    desc = body[desc_start + len("Job Description"):] if desc_start >= 0 else ""
    desc = desc.split("Eligibility Criteria")[0]
    desc = clip(desc, 700)

    elig_start = body.find("Eligibility Criteria")
    elig = body[elig_start:elig_start + 260] if elig_start >= 0 else ""

    if not title or not employer:
        return None

    loc = ""
    for kw in ["Islamabad", "Karachi", "Lahore", "Rawalpindi", "Peshawar", "Quetta",
               "Multan", "Faisalabad", "Hyderabad", "Sukkur", "Gilgit", "Muzaffarabad"]:
        if kw.lower() in body.lower():
            loc = kw
            break

    return {
        "source": "NJP",
        "source_url": "https://njp.gov.pk",
        "source_id": f"njp-{jid}",
        "url": f"https://njp.gov.pk/jobs/{jid}",
        "apply_url": f"https://njp.gov.pk/jobs/{jid}",
        "title": title,
        "company": employer,
        "employer_display": employer,
        "location": loc or "Pakistan",
        "type": job_type,
        "sector": "government",
        "category": classify_pk(title, body),
        "bps": grade,
        "vacancies": int(vac_num.group(1)) if vac_num else None,
        "experience": clip(experience, 40),
        "age_limit": clip(age, 40),
        "qualification": norm_qual(desc),
        "last_date": deadline,
        "posted": posted,
        "description": desc,
        "how_to_apply": "Apply online through the National Jobs Portal (njp.gov.pk). Create an account, complete your profile and submit the application before the deadline."
                        + (f" Contact: {email}" if email else ""),
        "contact": email or landline,
        "is_pk": True,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  2. JobsAlert.pk — WordPress REST API
# ═══════════════════════════════════════════════════════════════════════════
def fetch_jobsalert(limit=MAX_PER_SOURCE, pages=5):
    out = []
    per = 20
    for page in range(1, pages + 1):
        if len(out) >= limit:
            break
        url = (f"https://jobsalert.pk/wp-json/wp/v2/posts?per_page={per}&page={page}"
               f"&_fields=id,date,link,title,content,excerpt")
        try:
            posts = _json(url)
        except Exception as e:  # noqa: BLE001
            print(f"    jobsalert p{page}: {type(e).__name__}", flush=True)
            break
        if not isinstance(posts, list) or not posts:
            break
        for p in posts:
            job = _parse_jobsalert(p)
            if job:
                out.append(job)
            if len(out) >= limit:
                break
        time.sleep(0.4)
    return out


def _parse_jobsalert(post):
    raw_html = post.get("content", {}).get("rendered", "")
    body = txt(raw_html)
    title = one_line(txt(post.get("title", {}).get("rendered", "")))
    if not title or len(body) < 200:
        return None

    low = body.lower()
    employer = ""
    m = re.search(r"(?:for|at|in)\s+([A-Z][A-Za-z&.\- ]{4,60}(?:Department|Ministry|University|College|Board|Authority|Commission|Force|Army|Navy|Bank|Company|Corporation|Institute|Office|Hospital|School|Police|Limited|Ltd|Pakistan))", body)
    if m:
        employer = one_line(m.group(1))
    if not employer or len(employer) > 70:
        head = re.sub(r"\b(jobs?|2026|2025|online apply|apply online|last date)\b.*$", "",
                      title, flags=re.I).strip(" -–|,")
        employer = one_line(head)[:60] or one_line(title)[:60]

    blines = [ln.strip() for ln in body.split("\n") if ln.strip()]

    quals = re.findall(r"(?:^|\n)\s*(?:Overall Qualification|Qualification|Education|Educational Qualification)\s*[:\-–]\s*(.{2,220})", body, re.I)
    if not quals:
        quals = re.findall(r"[^.]{0,60}(?:Matric|Intermediate|Bachelor|Master|Graduation|BPS)[^.]{0,90}", body, re.I)[:2]
    joined = " / ".join(q.strip() for q in quals[:4] if q.strip())
    qualification = norm_qual(joined) if joined else ""
    bad = ("levels", "al &", "experience", "domicile", "court", "department")
    if qualification and (len(qualification) < 4 or any(b in qualification.lower() for b in bad)):
        qualification = ""
    experience = (field(body, "Experience")
                  or field_next(blines, "Experience"))
    age = ""
    m = re.search(r"age\s*(?:limit|of the candidate|should be)?[^.\n]{0,40}?(\d{2}\s*(?:to|-|–)\s*\d{2}\s*years)", body, re.I)
    if not m:
        m = re.search(r"(\d{2}\s*(?:to|-|–)\s*\d{2})\s*(?:years)?[^.\n]{0,20}age", body, re.I)
    if not m:
        m = re.search(r"age\s*limit\s*(?:is|:)?\s*([^.\n]{2,40})", body, re.I)
    age = one_line(m.group(1)) if m else (field(body, "Age Limit", "Age") or "")
    am = re.search(r"(\d{2})\s*(?:to|-|–)\s*(\d{2})", age or "")
    if am:
        age = f"{am.group(1)}–{am.group(2)} years"
    elif age:
        age = clip(age, 26)
    vacancies = (field(body, "Vacancies", "No. of Posts", "Total Vacancies", "Posts")
                 or field_next(blines, "Vacancies", "No. of Posts", "Total Vacancies", "Posts"))
    vac_num = re.search(r"(\d+)", vacancies or "")

    deadline = ""
    # 1) "Last Date to Apply: November 06, 2026"  /  "Last Date For Application: ..."
    for pat in (r"last\s*date[^.\n:]{0,40}[:\s]\s*(" + DATE_RE.pattern + r")",
                r"(?:last\s*date|deadline|closing date)[^.\n]{0,60}?(?:is|:)\s*(" + DATE_RE.pattern + r")",
                r"(" + DATE_RE.pattern + r")[^.\n]{0,30}(?:is the\s*last date|last date)"):
        m = re.search(pat, body, re.I)
        if m:
            deadline = parse_date_any(m.group(1))
            if deadline:
                break
    if not deadline:
        for lab in ("Last Date to Apply", "Last Date For Application", "Last Date",
                    "Application Deadline", "Closing Date", "Registration Date", "Last date"):
            v = field(body, lab) or field_next(blines, lab)
            if v:
                deadline = parse_date_any(v)
                if deadline:
                    break
    if not deadline:
        # "Registration will be held from 01st November 2026 to 07th January 2027"
        m = re.search(r"from\s+(" + DATE_RE.pattern + r")\s*(?:to|till|-)\s*(" + DATE_RE.pattern + r")", body, re.I)
        if m:
            deadline = parse_date_any(m.group(2))

    apply_block = ""
    m = re.search(r"How\s*to\s*Apply(?:\s*for[^:\n]{0,60})?\s*:?\s*(.{20,600}?)(?:\n\s*(?:Last|Address|Click|Vacant|Apply Now|Note|Important)\b|$)",
                  body, re.I | re.S)
    if m:
        apply_block = clip(m.group(1), 320)

    loc = ""
    for kw in ["Karachi", "Lahore", "Islamabad", "Rawalpindi", "Peshawar", "Quetta",
               "Multan", "Faisalabad", "Hyderabad", "Sukkur", "Gujranwala", "Sialkot",
               "Bahawalpur", "Gilgit", "Muzaffarabad", "Pakistan"]:
        if kw.lower() in low:
            loc = kw
            break

    govt = any(k in low for k in ["government", "govt", "ministry", "department", "bps",
                                  "pak army", "navy", "air force", "fpsc", "ppsc", "nts",
                                  "public service commission"])
    return {
        "source": "JobsAlert.pk",
        "source_url": "https://jobsalert.pk",
        "source_id": f"ja-{post.get('id')}",
        "url": post.get("link", ""),
        "apply_url": post.get("link", ""),
        "title": clip(title, 120),
        "company": clip(employer, 70),
        "employer_display": clip(employer, 70),
        "location": loc or "Pakistan",
        "type": "Full Time",
        "sector": "government" if govt else "private",
        "category": classify_pk(title, body),
        "bps": (field(body, "BPS", "Grade") or ""),
        "vacancies": int(vac_num.group(1)) if vac_num else None,
        "experience": clip(experience, 40),
        "age_limit": clip(age, 40),
        "qualification": qualification,
        "last_date": deadline,
        "posted": (post.get("date") or "")[:10],
        "description": clip(body, 700),
        "how_to_apply": apply_block or clip(body, 320),
        "is_pk": True,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  3. Ilmkidunya — structured job tables
# ═══════════════════════════════════════════════════════════════════════════
def fetch_ilmkidunya(limit=MAX_PER_SOURCE):
    out, seen = [], set()
    listing_urls = [
        "https://www.ilmkidunya.com/jobs",
        "https://www.ilmkidunya.com/jobs/industry/govt-service",
        "https://www.ilmkidunya.com/jobs/city-wise/jobs-in-karachi",
        "https://www.ilmkidunya.com/jobs/city-wise/jobs-in-lahore",
        "https://www.ilmkidunya.com/jobs/city-wise/jobs-in-islamabad",
        "https://www.ilmkidunya.com/jobs/city-wise/jobs-in-rawalpindi",
        "https://www.ilmkidunya.com/jobs/city-wise/jobs-in-faisalabad",
        "https://www.ilmkidunya.com/jobs/city-wise/jobs-in-peshawar",
    ]
    for url in listing_urls:
        if len(out) >= limit:
            break
        try:
            src = _get(url).decode("utf-8", "ignore")
        except Exception as e:  # noqa: BLE001
            print(f"    ilmkidunya {url.rsplit('/', 1)[-1]}: {type(e).__name__}", flush=True)
            continue
        slugs = re.findall(r'href="(/jobs/[a-z0-9][a-z0-9-]*-\d{5,7})"', src)
        slugs = list(dict.fromkeys(slugs))[:22]
        for slug in slugs:
            if slug in seen or len(out) >= limit:
                continue
            seen.add(slug)
            try:
                detail = _get("https://www.ilmkidunya.com" + slug).decode("utf-8", "ignore")
            except Exception:
                continue
            job = _parse_ilmkidunya(slug, detail)
            if job:
                out.append(job)
            time.sleep(0.3)
    return out


def _parse_ilmkidunya(slug, src):
    body = txt(src)
    lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
    if not lines:
        return None

    m = re.search(r"<title>(.*?)</title>", src, re.S | re.I)
    title = one_line(txt(m.group(1))) if m else ""
    title = re.sub(r"\s*[-|]\s*(Jobs|Ilmkidunya).*$", "", title, flags=re.I)

    total = field(body, "Total Vacancies")
    deadline = parse_date_any(field(body, "Last Date to Apply") or field(body, "Last Date"))
    posted = parse_date_any(field(body, "Job Ad Date"))
    jtype = field(body, "Job Type") or "Full Time"

    # Location: read it from the little label/value table on the page
    loc = ""
    m = re.search(r"<th[^>]*>\s*Location\s*</th>\s*<td[^>]*>(.*?)</td>", src, re.S | re.I)
    if not m:
        m = re.search(r"Location\s*:?\s*</[a-z]+>\s*<[a-z]+[^>]*>(.*?)</", src, re.S | re.I)
    if m:
        loc = one_line(txt(m.group(1)))
    if not loc or len(loc) > 42:
        loc = field(body, "Location")
    if not loc or len(loc) > 42 or "{" in loc:
        for kw in ["Karachi", "Lahore", "Islamabad", "Rawalpindi", "Faisalabad", "Peshawar",
                   "Quetta", "Multan", "Hyderabad", "Sukkur", "Gujranwala", "Sialkot",
                   "Bahawalpur", "Nankana", "Gilgit", "Muzaffarabad"]:
            if kw.lower() in body.lower():
                loc = kw
                break
    loc = re.sub(r"[^A-Za-z ,.-]", "", loc or "").strip() or "Pakistan"

    # employer usually appears right after the details block
    employer = ""
    m = re.search(r"Details of Job Advertisement by (.+?)\s+\d", body)
    if m:
        employer = one_line(m.group(1))
    if not employer:
        for ln in lines[:12]:
            if any(w in ln for w in ["University", "Department", "Ministry", "Board",
                                     "Authority", "Company", "College", "Institute",
                                     "Corporation", "Office", "Hospital", "Bank", "Force"]):
                employer = ln
                break
    if not employer:
        employer = title

    EDU_WORDS = ("matric", "middle", "primary", "intermediate", "f.sc", "fsc", "fa/",
                 "bachelor", "master", "graduation", "graduate", "b.sc", "bsc", "m.sc",
                 "msc", "mba", "b.a", "m.a", "bcs", "bs ", "ms ", "phd", "m.phil",
                 "mbbs", "b.ed", "m.ed", "llb", "diploma", "dae", "certificate",
                 "literate", "read and write", "middle pass", "middle standard")
    qual = ""
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", src, re.S | re.I)
    quals = []
    for row in rows:
        cells = [one_line(txt(c)) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)]
        for c in cells:
            low = c.lower()
            if c and 3 < len(c) < 80 and any(w in low for w in EDU_WORDS) and "table-of-content" not in low:
                quals.append(c)
    if quals:
        qual = norm_qual(" / ".join(list(dict.fromkeys(quals))[:3]))
    if not qual:
        m = re.search(r"(Matric(?:ulation)?\s*/\s*(?:Middle|Intermediate)[^.\n]{0,80}|"
                      r"Matric\s*(?:pass|or above)[^.\n]{0,60}|"
                      r"Intermediate\s*/\s*Matric[^.\n]{0,60})", body, re.I)
        if m:
            qual = norm_qual(m.group(1))
    if qual and ("{" in qual or "table-of-content" in qual or "/ male" in qual.lower()):
        qual = ""
    age = field(body, "Age Limit", "Age")
    experience = field(body, "Experience")

    # "How to apply" style paragraph
    how = ""
    for pat in (r"(Applicants? (?:are|should|must|need|can)[^.]{20,320}\.)",
                r"(Applications? (?:along with|must|should)[^.]{20,320}\.)",
                r"(Interested candidates[^.]{20,320}\.)",
                r"(Candidates (?:are|should|must)[^.]{20,320}\.)"):
        m = re.search(pat, body, re.I)
        if m:
            how = one_line(m.group(1))
            break
    if not how:
        m = re.search(r"Interviews? will be held[^.]{10,200}\.", body, re.I)
        if m:
            how = one_line(m.group(0))
    vac = re.search(r"(\d+)", total or "")

    return {
        "source": "Ilmkidunya",
        "source_url": "https://www.ilmkidunya.com",
        "source_id": "ilm-" + slug.rsplit("-", 1)[-1],
        "url": "https://www.ilmkidunya.com" + slug,
        "apply_url": "https://www.ilmkidunya.com" + slug,
        "title": clip(title, 120),
        "company": clip(employer, 70),
        "employer_display": clip(employer, 70),
        "location": clip(loc, 40) or "Pakistan",
        "type": jtype if "full" in jtype.lower() or "part" in jtype.lower() else "Full Time",
        "sector": "government" if "government" in jtype.lower() or "govt" in (jtype + body[:600]).lower() else "private",
        "category": classify_pk(title, body),
        "bps": field(body, "BPS", "Grade"),
        "vacancies": int(vac.group(1)) if vac else None,
        "experience": clip(experience, 40),
        "age_limit": clip(age, 40),
        "qualification": qual,
        "last_date": deadline,
        "posted": posted,
        "description": clip(body[body.find("Details of Job"):] if "Details of Job" in body else body, 700),
        "how_to_apply": how or "See the original advertisement for the application procedure.",
        "is_pk": True,
    }


# ═══════════════════════════════════════════════════════════════════════════
def collect(limit_per_source=MAX_PER_SOURCE, verbose=True):
    jobs = []
    if SOURCES_ENABLED.get("njp"):
        t = time.time()
        rows = fetch_njp(limit_per_source)
        jobs += rows
        if verbose:
            print(f"  NJP            {len(rows):3d} jobs  ({time.time()-t:.1f}s)", flush=True)
    if SOURCES_ENABLED.get("jobsalert"):
        t = time.time()
        rows = fetch_jobsalert(limit_per_source)
        jobs += rows
        if verbose:
            print(f"  JobsAlert.pk   {len(rows):3d} jobs  ({time.time()-t:.1f}s)", flush=True)
    if SOURCES_ENABLED.get("ilmkidunya"):
        t = time.time()
        rows = fetch_ilmkidunya(limit_per_source)
        jobs += rows
        if verbose:
            print(f"  Ilmkidunya     {len(rows):3d} jobs  ({time.time()-t:.1f}s)", flush=True)
    return jobs


if __name__ == "__main__":
    rows = collect(12)
    for j in rows[:6]:
        print(json.dumps({k: j[k] for k in ("source", "title", "company", "location",
                                            "qualification", "last_date", "vacancies")},
                         ensure_ascii=False, indent=1))
    print("total:", len(rows))
