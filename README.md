# Rozgar — Pakistan job board

A fast job board focused on **Pakistan**. Collects 1,300+ listings (government,
private and remote), refreshes every hour through GitHub Actions and hosts free on
GitHub Pages. **Every job gets its own designed poster** (1080×1350 + 1200×630) with
qualification, age limit, vacancies, last date, how-to-apply and a QR code — plus a
detail page with `JobPosting` structured data.

**This version adds:** a redesigned poster system (6 palettes, light/dark, QR),
free email + WhatsApp job alerts, a documented CSV/JSON format for local jobs with a
validating importer, and a full SEO layer (JobPosting spec, city/category landing
pages, split sitemaps, IndexNow).

```
.
├── index.html                  ← the job board
├── employers.html              ← “post a job” page for companies
├── 404.html
├── assets/css/style.css        ← light + dark theme
├── assets/js/app.js            ← search, filters, saved jobs
├── data/
│   ├── manual-jobs.json        ← 👈 your own jobs (Pakistan roles etc.)
│   ├── submissions.csv         ← optional: Google Form responses (CSV)
│   └── jobs.json               ← generated, do not edit
├── scripts/fetch_jobs.py       ← the engine
├── .github/workflows/deploy.yml← hourly refresh + auto deploy
└── SETUP_GUIDE.md              ← step-by-step Roman Urdu guide
```

## Sources

**Pakistan (scraped facts + link back):**

| Source | Content | Note |
|---|---|---|
| NJP — njp.gov.pk | federal government jobs, BPS grade, age limit, deadline | public portal, robots open |
| JobsAlert.pk | govt + private, "How to Apply", last date | WordPress REST API |
| Ilmkidunya | govt/private, city-wise, structured tables | robots open |

Punjab Job Portal (`jobs.punjab.gov.pk`) and PPSC only answer Pakistani IPs, so
GitHub's runners cannot reach them — their posts still appear through the three
sources above. Rozee / Mustakbil / Indeed expose no public API; scraping them
would breach their terms, so they are intentionally **not** included.

**International (public APIs, attribution kept):**

| Source | Terms | Indexed? |
|---|---|---|
| Arbeitnow | public API, link back | ✅ |
| Jobicy | credit + apply button must point to source | ✅ |
| Himalayas | public API, link back | ✅ |
| Remote OK | link back (follow) + name as source | ✅ |
| Remotive | link back + credit, **must not** be submitted to third parties / Google Jobs | ❌ `noindex`, no schema |
| Manual / Employer | your own listings | ✅ |

Each provider's requirement is coded in: `SCHEMA_OK` controls `noindex` and the
`JobPosting` JSON-LD, and Remotive / Remote OK links carry `rel="nofollow"` where
their terms require it.

## Posters (`scripts/poster.py`)

1080×1350 portrait + 1200×630 OG image per job, rendered with Pillow — no
templates, no external assets.

- **3 themes** — `navy` (default, navy + gold), `noir` (graphite + neon) and
  `maroon` (maroon + cream), switched with the `POSTER_THEME` env var. Each theme
  carries 6 palettes (govt / private / internship / contract / remote / alt), chosen
  deterministically from `sha1(slug)` together with a light/dark layout, so posters
  never repeat but stay stable between builds.
- **Content** — brand mark, sector badge, auto-shrunk title (≤ 3 lines), employer,
  up to 4 chips, a 2-column JOB DETAILS grid (≤ 6 facts), deadline banner with an
  “N days left” pill, HOW TO APPLY box with a 150 px QR, footer with site URL and
  source credit.
- **Scraped-text hardening** — `clean_age()` extracts a real `18–30 years` range,
  `clean_how()` throws away keyword-stuffed board paragraphs and substitutes an
  honest “apply on <source>” instruction, `short_url()` keeps long URLs inside the
  frame. The QR is only drawn when a real `http(s)` link exists.
- **Layout** — the fact grid stretches to fill the frame and the remaining slack is
  split evenly across the three tail gaps, so no poster has a hollow bottom.

## What the engine does (`scripts/fetch_jobs.py`)

1. Pulls 5 APIs (Arbeitnow 3 pages, Jobicy 3 pages, Himalayas 10 cursor pages,
   Remote OK, Remotive).
2. Cleans HTML, repairs mojibake, unescapes entities.
3. Normalises category, level, job type, region and salary into one schema.
4. Flags `pak_friendly` jobs (worldwide / Asia / UTC+4…+6).
5. De-duplicates (id + title/company key), keeps 45 days, caps at 1,600.
6. Writes `data/jobs.json` (light — no descriptions).
7. Generates `jobs/<slug>.html` for the newest 500 with schema.org `JobPosting`,
   related jobs, copy-link button, per-source `robots` rule.
8. Writes `feed.xml`, `sitemap.xml`, `robots.txt`.

Run locally:

```bash
python3 scripts/fetch_jobs.py      # ~10 s
python3 -m http.server 8000        # then open http://localhost:8000
```

## Front-end features

- Full-text search over title/company/tags/location
- Category chips with live counts, job-type / level / region filters
- 🇵🇰 “Pakistan-friendly” filter
- Saved jobs (localStorage), “NEW” badges, salary chips
- Dark mode, deep-linkable filters (`?q=react&category=Design`)
- Mobile-first layout, no frameworks, no external fonts

## Alerts (`scripts/send_alerts.py`)

Runs inside the deploy workflow right after the build. Free stack, no server:

- **Email** — Resend API (3,000/month free) or Gmail SMTP with an app password.
  Subscribers live in a Google Form → Sheet → published CSV; matching is by city,
  category, qualification and keywords.
- **WhatsApp** — a follow-only Channel linked from `alerts.html`, plus optional
  CallMeBot auto-post of each new digest.
- **Sharing** — every job page has a “WhatsApp par bhejein” button that opens a
  pre-filled message with title, closing date and the canonical link.

First run stores a baseline in `.alerts-state.json` (committed back by the bot) so
going live never blasts 1,300 emails at once.

## Local jobs

`data/manual-jobs.json` (array of objects, `data/manual-jobs.schema.json` for the
full spec) or a CSV straight from a spreadsheet:

```bash
python scripts/import_csv.py data/manual-jobs.csv --check   # validate only
python scripts/import_csv.py data/manual-jobs.csv           # merge into JSON
```

Only `title` and `company` are required. Everything else — `qualification`,
`experience`, `age_limit`, `vacancies`, `bps`, `salary`, `last_date`,
`how_to_apply`, `apply_url` — flows into the poster, the detail page, the
`JobPosting` markup and the expiry filter, exactly like a scraped job.

## SEO

| Layer | Implementation |
|---|---|
| `JobPosting` | Detail pages only, exactly one per page; description HTML ≥ 100 words, `identifier`, `validThrough`, `directApply`, `employmentType` enum, `baseSalary`, experience/education |
| Landing pages | `jobs-in/<city>.html`, `category/<cat>.html` — generated only for combos with ≥ 3 live listings |
| Sitemaps | `sitemap.xml` index → `sitemap-jobs-N.xml` (20k/file), `sitemap-pages.xml`, `sitemap-images.xml` |
| Canonicals | Absolute on every page; facet URLs (`?q=`, `?city=` …) emit `noindex,follow` |
| Expiry | Past `last_date` → page, poster and sitemap entry removed at build time |
| IndexNow | `scripts/ping_indexnow.py` pings Bing/Copilot after deploy (optional secret) |
| CI gate | `python scripts/seo_check.py` validates markup, canonicals, sitemaps |

Source terms decide markup eligibility (`SCHEMA_OK` in `fetch_jobs.py`): public APIs
that permit it, the official NJP government portal, and owner-posted jobs. Commercial
PK aggregators are listed without `JobPosting` markup and link back to the source.

## Legal notes

- Listings show **headline + short excerpt + link to the original posting**.
  Full descriptions stay on the source; we never mirror entire ads.
- **Do not copy other sites' job advertisements / banners.** That is copyright
  infringement and breaks Rozee / Indeed / LinkedIn terms. The `employers.html`
  flow lets companies submit **their own** creative instead.
- Never charge candidates. Add a report link and remove fake listings quickly.
- Honour take-down requests: remove the source line in `fetch_jobs.py`
  (or the single `manual-jobs.json` entry) and redeploy.
