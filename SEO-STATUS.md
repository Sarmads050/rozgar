# SEO status — RozgarJobs

Generated 2026-10-24 by `scripts/seo_report.py`. Run it before every change so you can see whether a change made things better.

## Inventory

| | | |
|---|---|---|
| Total live jobs | 348 | |
| Pakistani jobs | 157 | |
| Government jobs | 147 | |
| Closing within 7 days | 86 | |
| Indexable job pages | 291 | |
| Keyword / commission pages | 12 | bank-jobs, fpsc-jobs, health-jobs, kpk-jobs, nts-jobs, pak-army-jobs … |
| Guides | 6 | |

## Health checks

| Check | Value | |
|---|---|---|
| Job pages Google is allowed to index | 291 of 348 (152 Pakistani) | ✅ |
| Pages in the job sitemap | 291 | ✅ |
| Landing + guide pages in the sitemap | 61 | ✅ |
| Poster images in the image sitemap | 68 | ✅ |
| Jobs visible without JavaScript | 24 cards on the home page | ✅ |
| Home page canonical + structured data | both present | ✅ |
| Invalid JSON-LD on sampled job pages | 0 of 40 | ✅ |
| Indexable pages accidentally set to noindex | 0 | ✅ |
| Email alerts switched on | no (see SETUP-BACKEND.md §2) | ⚠️ |
| Analytics collecting | no (see SETUP-BACKEND.md §1) | ⚠️ |
| WhatsApp channel linked | no (see SETUP-BACKEND.md §3) | ⚠️ |
| RSS / Atom feed | feed.xml | ✅ |
| llms.txt for AI assistants | 16,684 bytes | ✅ |
| Full plain-text corpus | 285 KB | ✅ |
| Plain-text mirror per job page | 291 files | ✅ |
| AI crawlers explicitly allowed | 8 of 8 | ✅ |
| Quotable Q&A on the home page + FAQ hub | both | ✅ |

## Do next (in order)

1. Switch on the three free services in `SETUP-BACKEND.md` — 12 minutes total, and they are the only items on this list no code can do for you.
2. Grow Pakistani listings: 157 now. Ask 2–3 Pakistani boards for API or feed access (a partnership beats scraping), and point employers at the post-a-job form.
3. 86 jobs close within 7 days — that is normal, and the build removes them automatically the day after.
4. Buy `rozgarjobs.com` when you can (see §5). A shared `github.io` subfolder is the single biggest ceiling on this site.
5. Get cited, not just indexed. Answer engines quote pages that other sites already mention: submit the site to Pakistani job aggregators, university career pages and any forum thread that asks where to find sarkari jobs. One real mention beats fifty tone-deaf directories.
6. Ask ChatGPT, Perplexity and Gemini the same question a candidate would ("government jobs in Karachi this week") once a month and note whether RozgarJobs appears. That is the only honest AI-visibility measurement — there is no console for it yet.
7. In Search Console, open **Pages** weekly and look at *Discovered – currently not indexed*. New pages that stay stuck there mean the content is too thin — add a paragraph of genuine detail, do not resubmit.

## The only numbers that really matter

1. **Clicks and impressions from Pakistan** in Search Console → Performance.
2. **Which queries you show up for on page 2** (positions 11–20). Those pages need one paragraph of real improvement, not a rewrite.
3. **Search terms people type on the site that return nothing** (GoatCounter `/search/…`). Each one is a source you are missing.

Everything else — page counts, sitemap size, schema validity — is plumbing. It has to be right, but it does not rank a site on its own.
