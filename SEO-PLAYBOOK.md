# SEO playbook — RozgarJobs

Written for October 2026. Everything here runs from the repo; no paid tools required.

---

## 1. What the site is optimised for

| Query group | Example | Where it is targeted |
|---|---|---|
| Head terms | jobs in pakistan, government jobs in pakistan | home page (`h1`, title, schema) |
| City | jobs in karachi, jobs in lahore | `jobs-in/<city>.html` |
| Category | software development jobs, health jobs | `category/<slug>.html` |
| Long tail | last date, age limit, BPS-09, matric jobs | job pages + poster text |
| Brand | rozgarjobs | logo, OG image, schema `Organization` |

**Rule that keeps us safe:** Google's spam policies punish doorway pages and scaled
content abuse. Every generated page must carry *its own data* — real counts, real
employer names, real deadlines — and only exists when at least 5 live jobs back it.
That is why the counter on each page is computed from the same jobs the page lists.

---

## 2. What every page ships with

- one `JobPosting` per job page only (never on listings)
- `BreadcrumbList` on job and landing pages
- `FAQPage` on city and category pages, answers built from that page's numbers
- `Organization` + `WebSite` + `SearchAction` on the home page
- canonical URL, `og:image`, `twitter:card`, one `H1`
- internal links up (category, city) and across (other cities)
- filtered URLs `noindex,follow` so Google never indexes `?q=` duplicates

---

## 3. Publishing rhythm (do this every week)

| Day | Task | Time |
|---|---|---|
| Mon | Run the build; check new landing pages appeared for cities with 5+ jobs | 5 min |
| Wed | Add or refresh **one** guide page (how to apply for FPSC, how to read a BPS scale) | 30 min |
| Fri | Look at Search Console → Queries. Any query on page 2 gets its own section on an existing page | 20 min |
| Sunday | Check `scripts/seo_check.py` is still green | 2 min |

Do **not** publish 50 new pages in one day. Five to ten a week, each with real data,
is what survives an update.

---

## 4. Freshness signals

- jobs rebuilt every hour, `datePosted` and `validThrough` always current
- `sitemap-jobs-*.xml` gets a fresh `lastmod` on every build
- expired jobs are removed from the page, the sitemap and the poster folder
  (Google penalises `JobPosting` pages that stay up after the deadline)

---

## 5. Indexing

1. **Google Search Console** → URL prefix property → submit `sitemap.xml` once.
   Google re-reads the child sitemaps on its own.
2. **IndexNow** → key file `0ff29aca72ad22477ca16079c8ab229f.txt` sits at the site root;
   `scripts/ping_indexnow.py` pushes new URLs to Bing and Yandex after each build.
3. **Request indexing** manually only for the home page and the About page.

---

## 6. Content ideas that earn links (E-E-A-T)

- "How to apply on the National Job Portal, step by step"
- "BPS pay scales explained for 2026"
- "Documents you need for a government job application"
- "How to spot a fake job advertisement"
- "Test and interview pattern for FPSC / PPSC"

Each one is a normal page, written in easy English, linked from the footer and from
related job pages. They bring links; links bring authority; authority is what makes
"jobs in pakistan" reachable at all.

---

## 7. Things that hurt — never do them

- copying full advertisements or posters from other sites
- mass-generating `city × role` pages with the same paragraph
- publishing a page with 1 or 2 jobs and no unique text
- keyword stuffing the title (`jobs jobs pakistan jobs`)
- hiding text, cloaking, or buying links

---

## 8. Monthly check

```bash
python3 scripts/check_jobs.py     # local data is valid
python3 scripts/seo_check.py      # every page still has valid schema
python3 scripts/ping_indexnow.py  # push changed URLs
```

Then in Search Console: **Pages → Not indexed**. If "Crawled – currently not indexed"
grows, the page is thin — merge it or add real data. If "Discovered – not indexed"
grows, the site is too big for its authority — slow down publishing.

---

## 6. What changed in this build (October 2026 audit, all ten items)

| # | Item | Where it lives now |
|---|---|---|
| 1 | Pakistan-first content mix | Scope tabs on the home page default to **Pakistan**; German/irrelevant on-site jobs are dropped by the relevance gate before a page is created |
| 2 | More Pakistani jobs | NJP + JobsAlert.pk (WP API, 100/page) + Ilmkidunya (12 listing pages) — per-source cap raised to 320 |
| 3 | Data cleanup | `clean_employer()` + `display_title()` strip ad-speak, "PO Box" employers and keyword-stuffed titles; duplicates collapse on title+employer |
| 4 | Post a job | `.github/ISSUE_TEMPLATE/post-a-job.yml` → `ingest-issue.yml` → `scripts/ingest_issue.py` (validated, auto-published on the `approved` label) |
| 5 | Email alerts | `feed.xml` (60 newest, hourly) → point any RSS-to-email service at it; `alerts.html` posts to `email_form_url` once set |
| 6 | Analytics | `assets/js/analytics.js` — GoatCounter / Cloudflare / Plausible, off until configured in `data/site-config.json` |
| 7 | WhatsApp | `whatsapp.yml` builds a ready-to-paste post pack every 3 hours; optional CallMeBot delivery |
| 8 | Google Indexing API | `index_jobs.py` + `index-new-jobs.yml`, guarded by the `GOOGLE_INDEXING_KEY` secret |
| 9 | Search & filters | Scope tabs, closing-this-week, no-experience, qualification, BPS chips, synonym expansion ("teacher" → lecturer/educator) |
| 10 | Recovery, speed, access | Expired-job 404 with similar jobs, WebP posters (≈60% smaller) behind `<picture>`, skip link, focus rings, gold contrast fixed to 5:1, `verification.html` editorial policy |

### Pages that must exist before the next audit
- `sarkari-naukri.html` — the single biggest head term in Pakistan
- `fpsc-jobs.html`, `ppsc-jobs.html`, `nts-jobs.html`, `police-jobs.html` — commission pages with editorial body copy, rebuilt every hour with live posts merged in
- `punjab-jobs.html`, `sindh-jobs.html`, `kpk-jobs.html` (+ Balochistan once it clears 5 live jobs)

### Weekly routine (10 minutes)
1. Search Console → **Pages** → check "Discovered – currently not indexed" for new landing pages.
2. Search Console → **Performance** → note any query where a keyword page ranks 5–20; add one paragraph of genuinely new information to that page.
3. GoatCounter (once configured) → top `/search/…` terms with zero results → those are your next job sources.
4. Add **one** new guide per week from real questions people ask (the guides already use FAQPage schema).
5. Never publish more than 10 new landing pages in a week — that is the shape of a spam signal, not a growth plan.

### What still needs a human
Buy `rozgarjobs.com` and move the site there. A subfolder on `github.io` competes with a
handicap: shared host reputation, no domain age, no brand searches. The domain is the
single largest remaining ranking factor this project can control. See
`SETUP-BACKEND.md` §5 for the exact steps and the Search Console *Change of address* step.
