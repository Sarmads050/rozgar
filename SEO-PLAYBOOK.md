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
