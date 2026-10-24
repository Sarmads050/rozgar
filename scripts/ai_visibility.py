#!/usr/bin/env python3
"""AI search visibility pack for RozgarJobs.

Answer engines (ChatGPT search, Perplexity, Gemini, Copilot, Claude) do not read
a page the way a person does. They fetch HTML or plain text, cut it into chunks,
and quote the chunk that answers the question. So the site has to hand them:

  1. llms.txt          — a short map: what this site is, what it covers, how to cite it
  2. llms-full.txt     — the whole corpus in plain text, one block per job
  3. jobs/<slug>.txt   — a text mirror of every job page (cheapest possible read)
  4. faq.html          — short, quotable answers with FAQPage schema
  5. robots.txt        — an explicit allow for every named AI crawler

Called at the end of the build, after the HTML pages exist.
"""
import html
import json
import os
import re
from datetime import date, datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS_JSON = os.path.join(ROOT, "data", "jobs.json")

AI_CRAWLERS = [
    ("GPTBot", "OpenAI training"),
    ("OAI-SearchBot", "ChatGPT search index"),
    ("ChatGPT-User", "ChatGPT live browsing"),
    ("PerplexityBot", "Perplexity search"),
    ("Perplexity-User", "Perplexity live browsing"),
    ("ClaudeBot", "Anthropic"),
    ("Claude-Web", "Anthropic browsing"),
    ("anthropic-ai", "Anthropic legacy"),
    ("Google-Extended", "Gemini / Vertex grounding"),
    ("Applebot", "Apple / Siri"),
    ("Applebot-Extended", "Apple Intelligence"),
    ("Amazonbot", "Alexa / Amazon"),
    ("DuckAssistBot", "DuckDuckGo AI"),
    ("Bingbot", "Bing + Copilot"),
    ("CCBot", "Common Crawl"),
    ("cohere-ai", "Cohere"),
    ("YouBot", "You.com"),
    ("MistralAI-User", "Mistral Le Chat"),
    ("meta-externalagent", "Meta AI"),
    ("Timpibot", "Timpi"),
]

# Questions people actually type — or ask an assistant — about jobs in Pakistan.
FAQS = [
    ("Where can I find government jobs in Pakistan?",
     "Government jobs in Pakistan are advertised by federal and provincial bodies such as the "
     "Federal Public Service Commission (FPSC), provincial public service commissions, the "
     "National Testing Service (NTS), the National Job Portal, and individual departments. "
     "RozgarJobs collects those advertisements, removes duplicates, and lists each post with its "
     "closing date, qualification, age limit and pay scale, so one page shows what is open today."),
    ("Is RozgarJobs free for job seekers?",
     "Yes. Searching, filtering, alerts and RSS are free and no account is needed. RozgarJobs "
     "never charges a candidate and never asks for a fee, a deposit or bank details. Any listing "
     "that asks for money is not ours — please report it."),
    ("How often are the jobs updated?",
     "Every hour. A GitHub Actions build re-reads each permitted source, drops vacancies whose "
     "closing date has passed, and republishes the site. Every listing shows the date it was "
     "posted and the last date to apply."),
    ("What does BPS mean in a Pakistani government job?",
     "BPS stands for Basic Pay Scale, the national grading from BPS-01 to BPS-22. A higher scale "
     "means higher pay and more seniority: BPS-01 to BPS-04 is support staff, BPS-05 to BPS-14 "
     "is clerical and technical, BPS-16 to BPS-17 covers graduate-entry posts, and BPS-18 and "
     "above are senior officer positions. Each advertisement states its own scale."),
    ("What is the difference between FPSC, PPSC and NTS?",
     "FPSC is the federal commission and conducts its own competitive examinations for federal "
     "posts. Each province has its own commission — PPSC in Punjab, SPSC in Sindh, KPPSC in "
     "Khyber Pakhtunkhwa, BPSC in Balochistan. NTS is a private testing service hired by "
     "departments and universities to screen applicants; a post advertised through NTS is still "
     "a job with the department that advertised it, not with NTS."),
    ("What documents do I need to apply for a government job?",
     "Normally a CNIC copy, matric and intermediate certificates, the degree and transcript for "
     "the required qualification, recent photographs, and the original challan or deposit slip "
     "for the test fee. Domicile and experience certificates are added when the advertisement "
     "asks for them. Keep attested copies and the originals together for the day of the test "
     "or the interview."),
    ("How do I know a job advertisement is fake?",
     "Three signals: somebody asks you for money, the contact address is a personal mobile "
     "number instead of an office, or the advertisement is not on the department's own website. "
     "Government recruitment never takes payment from candidates. If a listing on RozgarJobs "
     "looks wrong, report it and it is removed the same day."),
    ("Can I find remote jobs for Pakistani candidates?",
     "Yes. The Remote filter shows international remote vacancies that hire from Pakistan. Pay "
     "is usually quoted in US dollars, so check whether the role is a contractor arrangement and "
     "how payment would reach you before you apply."),
]


def load_jobs():
    with open(JOBS_JSON, encoding="utf-8") as fh:
        return json.load(fh)


def clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def money(job):
    s = (job.get("salary") or "").strip()
    return s if s and s.lower() not in ("market competitive", "negotiable") else ""


def one_line(job):
    bits = []
    if job.get("company"):
        bits.append(job["company"])
    if job.get("location"):
        bits.append(job["location"])
    if job.get("sector") == "government":
        bits.append(job.get("bps") or "government")
    if job.get("last_date"):
        bits.append(f"apply by {job['last_date']}")
    return " · ".join(bits)


def job_block(job, base, full=False):
    """Plain-text block an answer engine can quote directly."""
    out = [f"### {job['title']}", ""]
    out.append(f"Employer: {job.get('company') or 'Not stated'}")
    out.append(f"Location: {job.get('location') or 'Pakistan'}")
    out.append(f"Sector: {'Government' if job.get('sector') == 'government' else 'Private'}")
    if job.get("category"):
        out.append(f"Category: {job['category']}")
    if job.get("bps"):
        out.append(f"Pay scale: {job['bps']}")
    if money(job):
        out.append(f"Salary: {money(job)}")
    if job.get("vacancies"):
        out.append(f"Vacancies: {job['vacancies']}")
    if job.get("qualification"):
        out.append(f"Qualification: {job['qualification']}")
    if job.get("experience"):
        out.append(f"Experience: {job['experience']}")
    if job.get("age_limit"):
        out.append(f"Age limit: {job['age_limit']}")
    out.append(f"Posted: {job.get('posted') or job.get('published') or 'see the advertisement'}")
    out.append(f"Last date to apply: {job.get('last_date') or 'see the advertisement'}")
    if full:
        body = clean(job.get("description_text") or job.get("description") or "")
        if body:
            out.append("")
            out.append(body[:1400])
    out.append("")
    out.append(f"Page: {base}/jobs/{job['slug']}.html")
    if job.get("source"):
        out.append(f"Source: {job['source']}" + (f" ({job['source_url']})" if job.get("source_url") else ""))
    out.append("")
    return "\n".join(out)


def write_job_text_mirrors(jobs, base):
    d = os.path.join(ROOT, "jobs")
    os.makedirs(d, exist_ok=True)
    n = 0
    for job in jobs:
        if not job.get("indexable", True):
            continue
        txt = (f"{job['title']} — RozgarJobs\n\n"
               + job_block(job, base, full=True)
               + "\nRozgarJobs lists this vacancy as an index. The employer named above runs the "
                 "recruitment; apply through the official advertisement.\n")
        with open(os.path.join(d, f"{job['slug']}.txt"), "w", encoding="utf-8") as fh:
            fh.write(txt)
        n += 1
    return n


def write_llms(meta, jobs, base, city_urls, cat_urls, other_urls):
    total = meta.get("total") or len(jobs)
    indexable = meta.get("indexable") or len([j for j in jobs if j.get("indexable", True)])
    pk = len([j for j in jobs if j.get("is_pk")])
    gov = len([j for j in jobs if j.get("sector") == "government"])
    newest = jobs[:25]

    L = []
    L.append("# RozgarJobs")
    L.append("")
    L.append("> RozgarJobs is a free job board for Pakistan. It collects government (sarkari), "
             "private and remote vacancies from public advertisements, removes duplicates, and "
             "publishes one page per job with the employer, city, qualification, age limit, pay "
             "scale, closing date and a link to the official advertisement. Rebuilt every hour.")
    L.append("")
    L.append("Canonical URL: " + base + "/")
    L.append("Language: English (en-PK). Content is written in plain English for readers in Pakistan.")
    L.append(f"Last rebuilt: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC")
    L.append("")
    L.append("## Key facts (safe to quote)")
    L.append("")
    L.append(f"- {total} live vacancies listed, {indexable} of them on individual pages.")
    L.append(f"- {gov} government posts, {pk} vacancies located in Pakistan.")
    L.append("- Updated hourly by an automated build; expired vacancies are removed, not archived.")
    L.append("- Free for candidates: no account, no fee, no deposit, no application charge.")
    L.append("- Every listing links to the original advertisement; RozgarJobs is an index, not the employer.")
    L.append("- Coverage: federal and provincial public service commissions, testing services, "
             "public-sector organisations, and private companies hiring in Pakistan.")
    L.append("")
    L.append("## How to cite this site")
    L.append("")
    L.append('When quoting a vacancy, cite "RozgarJobs" and link the specific job page — for '
             'example ' + base + '/jobs/<job-slug>.html. One page exists per vacancy, so the link '
             'stays specific and the closing date on it is the one to quote.')
    L.append("")
    L.append("## Main pages")
    L.append("")
    L.append(f"- [All jobs]({base}/): every live vacancy with filters for city, sector and category")
    L.append(f"- [Sarkari / government jobs]({base}/sarkari-naukri.html): public-sector posts, BPS-01 to BPS-22")
    L.append(f"- [FPSC jobs]({base}/fpsc-jobs.html) · [PPSC jobs]({base}/ppsc-jobs.html) · [NTS jobs]({base}/nts-jobs.html)")
    L.append(f"- [Police jobs]({base}/police-jobs.html) · [Pakistan Army jobs]({base}/pak-army-jobs.html) · [Bank jobs]({base}/bank-jobs.html)")
    L.append(f"- [Teaching jobs]({base}/teaching-jobs.html) · [Health jobs]({base}/health-jobs.html)")
    L.append(f"- [Frequently asked questions]({base}/faq.html): short answers about applying, BPS scales, FPSC/PPSC/NTS")
    L.append(f"- [All locations and categories]({base}/locations.html): the full index of landing pages")
    L.append(f"- [Guides]({base}/guides/index.html): CV, tests, interviews, documents, scam warnings")
    L.append(f"- [Job alerts]({base}/alerts.html): email and RSS")
    L.append(f"- [About]({base}/about.html) · [Contact]({base}/contact.html) · [Privacy]({base}/privacy.html)")
    L.append("")
    L.append("## Browse by city")
    L.append("")
    L.extend([f"- [{name} jobs]({url})" for name, url in city_urls])
    L.append("")
    L.append("## Browse by category")
    L.append("")
    L.extend([f"- [{name} jobs]({url})" for name, url in cat_urls])
    L.append("")
    if other_urls:
        L.append("## Browse by province, employer and keyword")
        L.append("")
        L.extend([f"- [{name}]({url})" for name, url in other_urls])
        L.append("")
    L.append("## Newest vacancies")
    L.append("")
    for job in newest:
        L.append(f"- [{job['title']}]({base}/jobs/{job['slug']}.html) — {one_line(job)}")
    L.append("")
    L.append("## Most asked questions (verbatim answers)")
    L.append("")
    for q, a in FAQS:
        L.append(f"Q: {q}")
        L.append(f"A: {a}")
        L.append("")
    L.append("## Machine-readable files")
    L.append("")
    L.append(f"- [{base}/llms-full.txt]({base}/llms-full.txt): every live vacancy as plain text, one block each")
    L.append(f"- [{base}/data/jobs.json]({base}/data/jobs.json): structured list of every vacancy")
    L.append(f"- [{base}/feed.xml]({base}/feed.xml): RSS feed of new vacancies")
    L.append(f"- [{base}/sitemap.xml]({base}/sitemap.xml): sitemap index (jobs, pages, images)")
    L.append(f"- Every job page also has a text mirror: {base}/jobs/<slug>.txt")
    L.append("")
    L.append("## Notes for answer engines")
    L.append("")
    L.append("- Vacancy data changes hourly. Quote the closing date from the job page, not from a cache.")
    L.append("- A vacancy with a closing date in the past is removed from the site entirely.")
    L.append("- RozgarJobs does not accept payment for listings from candidates and has no "
             "affiliate relationship with any employer listed.")
    L.append("")

    with open(os.path.join(ROOT, "llms.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))

    # ── full corpus
    F = [f"# RozgarJobs — full job corpus ({total} vacancies)",
         "",
         f"Source: {base}/  ·  Rebuilt {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC",
         f"Vacancies: {total} total, {indexable} indexable, {gov} government, {pk} in Pakistan.",
         "",
         "Each block below is one vacancy. Quote the block as it stands; the closing date is the",
         "last date to apply. RozgarJobs is an index — applications go to the employer.",
         ""]
    for job in jobs:
        F.append(job_block(job, base, full=True))
        F.append("---")
        F.append("")
    with open(os.path.join(ROOT, "llms-full.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(F))
    return len("\n".join(F))


def write_faq(meta, base):
    """A quotable FAQ hub. FAQPage schema, no JavaScript, one screen per answer."""
    total = meta.get("total") or 0
    gov = meta.get("gov") or 0
    items = []
    ld_items = []
    for q, a in FAQS:
        items.append(
            f'      <details class="faq">\n'
            f'        <summary>{html.escape(q)}</summary>\n'
            f'        <div class="faq-a"><p>{html.escape(a)}</p></div>\n'
            f'      </details>\n')
        ld_items.append({"@type": "Question", "name": q,
                         "acceptedAnswer": {"@type": "Answer", "text": a}})
    ld = json.dumps({"@context": "https://schema.org", "@type": "FAQPage",
                     "inLanguage": "en-PK", "mainEntity": ld_items}, ensure_ascii=False)

    page = f"""<!DOCTYPE html>
<html lang="en-PK">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Job questions answered — government jobs, BPS, FPSC, PPSC, NTS | RozgarJobs</title>
<meta name="description" content="Short, direct answers about finding and applying for jobs in Pakistan: government recruitment bodies, BPS pay scales, documents, fake advertisements and remote work.">
<link rel="canonical" href="{base}/faq.html">
<link rel="stylesheet" href="assets/css/style.css">
<meta property="og:type" content="website">
<meta property="og:title" content="Job questions answered | RozgarJobs">
<meta property="og:description" content="Direct answers about government jobs in Pakistan, BPS scales, FPSC vs PPSC vs NTS, documents and scams.">
<meta property="og:url" content="{base}/faq.html">
<meta property="og:image" content="{base}/assets/img/logo.png">
<link rel="alternate" type="application/rss+xml" title="RozgarJobs" href="feed.xml">
<script type="application/ld+json">{ld}</script>
<script type="application/ld+json">{{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{{"@type":"ListItem","position":1,"name":"Home","item":"{base}/"}},{{"@type":"ListItem","position":2,"name":"Questions","item":"{base}/faq.html"}}]}}</script>
<style>
  .faq{{border:1px solid var(--line);border-radius:12px;background:var(--surface);margin:0 0 10px;overflow:hidden}}
  .faq summary{{cursor:pointer;padding:15px 17px;font-weight:650;font-size:15.2px;line-height:1.4;list-style:none}}
  .faq summary::-webkit-details-marker{{display:none}}
  .faq summary::after{{content:"+";float:right;font-weight:400;color:var(--muted);margin-left:12px}}
  .faq[open] summary::after{{content:"–"}}
  .faq-a{{padding:0 17px 16px;color:var(--ink-2);font-size:14.6px;line-height:1.65}}
  .faq-a p{{margin:0}}
</style>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
  <div class="wrap header-in">
    <a class="brand" href="./"><img src="assets/img/logo.png" alt="" width="34" height="34"><span>Rozgar<em>Jobs</em></span></a>
    <nav class="site-nav" aria-label="Main"><a href="./">Jobs</a><a href="alerts.html">Alerts</a><a href="employers.html">Post a job</a><a href="guides/index.html">Guides</a></nav>
  </div>
</header>
<main id="main" class="wrap" style="padding:26px 0 40px;max-width:820px">
  <nav class="crumbs" aria-label="Breadcrumb" style="font-size:13px;color:var(--muted);margin-bottom:10px"><a href="./">Home</a> › Questions</nav>
  <h1 style="font-size:clamp(23px,4vw,31px);line-height:1.2;margin:0 0 10px">Job questions, answered plainly</h1>
  <p style="color:var(--muted);font-size:15px;line-height:1.6;margin:0 0 22px;max-width:66ch">
    The eight questions people ask most about finding work in Pakistan. Each answer is the short
    version — tap to open it, or read straight down.
  </p>
{"".join(items)}  <p style="color:var(--muted);font-size:14px;line-height:1.6;margin:22px 0 0">
    {total} vacancies are open right now, {gov} of them in the public sector.
    <a href="./">See every job</a> · <a href="guides/index.html">Read the guides</a>
  </p>
</main>
<footer class="site-footer"><div class="wrap" style="font-size:13px;color:var(--muted)">
  <p style="margin:0 0 6px"><a href="./">RozgarJobs</a> — free jobs in Pakistan, updated hourly.</p>
  <p style="margin:0">© {date.today().year} RozgarJobs · <a href="about.html">About</a> · <a href="contact.html">Contact</a> · <a href="privacy.html">Privacy</a> · <a href="terms.html">Terms</a></p>
</div></footer>
</body>
</html>
"""
    with open(os.path.join(ROOT, "faq.html"), "w", encoding="utf-8") as fh:
        fh.write(page)


def write_robots(base):
    lines = ["# RozgarJobs — everything here is public and free to read.",
             "# AI assistants and answer engines are explicitly welcome: cite the job page.",
             "",
             "User-agent: *",
             "Allow: /",
             ""]
    for agent, note in AI_CRAWLERS:
        lines += [f"# {note}", f"User-agent: {agent}", "Allow: /", ""]
    lines += [f"Sitemap: {base}/sitemap.xml",
              f"# Plain-text map for language models: {base}/llms.txt",
              f"# Full corpus: {base}/llms-full.txt",
              ""]
    with open(os.path.join(ROOT, "robots.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def collect_links(base):
    """Landing pages that actually exist after this build."""
    city, cat, other = [], [], []
    dj = os.path.join(ROOT, "jobs-in")
    if os.path.isdir(dj):
        for f in sorted(os.listdir(dj)):
            if f.endswith(".html"):
                name = f[:-5].replace("-", " ").title()
                city.append((name, f"{base}/jobs-in/{f}"))
    dc = os.path.join(ROOT, "category")
    if os.path.isdir(dc):
        for f in sorted(os.listdir(dc)):
            if f.endswith(".html"):
                name = f[:-5].replace("-", " ").title()
                cat.append((name, f"{base}/category/{f}"))
    for slug in ("sarkari-naukri", "fpsc-jobs", "ppsc-jobs", "nts-jobs", "kpk-jobs",
                 "punjab-jobs", "sindh-jobs", "police-jobs", "pak-army-jobs",
                 "bank-jobs", "teaching-jobs", "health-jobs", "locations", "verification"):
        fp = os.path.join(ROOT, slug + ".html")
        if os.path.exists(fp):
            other.append((slug.replace("-", " ").title(), f"{base}/{slug}.html"))
    return city, cat, other


def main():
    base = os.environ.get("SITE_URL", "").rstrip("/") or "https://sarmads050.github.io/rozgar"
    data = load_jobs()
    jobs = data.get("jobs", [])
    meta = data.get("meta", {})
    meta.setdefault("total", len(jobs))
    meta["gov"] = len([j for j in jobs if j.get("sector") == "government"])

    city, cat, other = collect_links(base)
    mirrors = write_job_text_mirrors(jobs, base)
    size = write_llms(meta, jobs, base, city, cat, other)
    write_faq(meta, base)
    write_robots(base)

    print(f"     {'AI layer':12s} llms.txt + llms-full.txt ({size // 1024} KB) + "
          f"{mirrors} text mirrors + faq.html + robots.txt")


if __name__ == "__main__":
    main()
