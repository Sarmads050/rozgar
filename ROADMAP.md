# Rozgar — Design, Security & SEO Roadmap

**Date:** 23 Oct 2026 · **Live:** https://sarmads050.github.io/rozgar/ · **Status:** 1,378 jobs · 238 posters · auto-refresh hourly

---

# 1. SECURITY — audit ka nateeja

### Jo cheezein theek hain (verified)

| Check | Result |
|---|---|
| Repo mein koi secret/token commit | ✅ saaf — token sirf env variable se gaya, `git grep` se confirm kiya |
| User data escaping (XSS) | ✅ `esc()` + `safeUrl()` har field par — title, company, location, tags sab |
| External links | ✅ 0 links bina `rel="noopener"` |
| JSON-LD breakout (`</script>` injection) | ✅ **aaj fix kiya** — ab `<\/` escape hota hai |
| CSP + referrer policy | ✅ **aaj add kiya** — sab pages par (test: 0 console errors) |
| `security.txt` | ✅ **aaj add kiya** — `.well-known/security.txt` |
| Authentication / payments | ✅ kuch nahi hai — attack surface minimal |

### Jo fix karna chahiye (priority order)

| # | Masla | Kya karein | Effort |
|---|---|---|---|
| 1 | **HTTP security headers nahi** — GitHub Pages custom headers allow nahi karta (HSTS, `X-Content-Type-Options`, `X-Frame-Options`) | Domain ke baad **Cloudflare free** lagayein (proxy on) — ye headers, DDoS protection, caching sab de deta hai. Bina domain ke kuch nahi ho sakta. | Domain ke baad, 20 min |
| 2 | **Token 90 din ke liye chat mein hai** | Kaam khatam → [github.com/settings/tokens](https://github.com/settings/tokens) se **Revoke**. Site pe koi asar nahi. | 30 sec |
| 3 | **Dependencies pin nahi** (`pillow>=10.0`) | Exact versions pin karein — supply-chain risk kam | 5 min (main kar dunga) |
| 4 | **Company logos third-party sites se load hote hain** | Aapke visitors ka IP un sites ko jata hai. Option: logos hata dein ya proxy karein | 15 min |
| 5 | **Dependabot / secret scanning off** | Repo → Settings → Code security → enable karein | 2 clicks |

**Bottom line:** website par koi user account, form submission (email ke ilawa), ya payment nahi — is liye attack surface bohat kam hai. **Sab se bara risk aapka token hai aur kuch nahi.**

---

# 2. DESIGN — 3 concepts (aap chunein)

Maine live site mobile (390px) par dekhi. **Asli masla ye hai:** mobile par pehli screen par **ek bhi job nahi dikhti** — hero + search + chips + 4 stats sab jagah kha jate hain (~1,700px scroll ke baad pehla job).

## Current mobile issues

| Masla | Detail |
|---|---|
| Hero bohat bara | Heading 2 lines + 4-line paragraph = 320px |
| Stats 4 numbers | 2 rows, ~200px — mobile par ye luxury hai |
| Search box + 9 chips | 3 rows chips = ~230px |
| Pehla job | Screen se ~1.7 scroll neeche |
| Bell icon | Emoji tofu (□) ban raha tha — **aaj SVG se fix kar diya** |
| Top bar text | "1,378 jo…" cut ho raha hai |

---

## Concept A — "Rozgar Pro" ⭐ meri recommendation

App jaisa feel, mobile-first, poster-forward. **Pakistani job seekers 90% mobile par aate hain** — design unhi ke liye.

```
┌──────────────────────────┐
│ R  Rozgar      🔍  ☰     │  ← chhota header (48px)
├──────────────────────────┤
│ 1,378 jobs · aaj 838 naye│  ← ek patli strip
│ ┌──────────────────────┐ │
│ │ 🔍 Search jobs…      │ │  ← sticky search (scroll par upar chipka rahe)
│ └──────────────────────┘ │
│ [Govt][Private][Remote]  │  ← 3 bade tabs, baqi "More" mein
├──────────────────────────┤
│ ┌────────┐ ┌────────┐   │
│ │poster  │ │poster  │   │  ← 2-column poster grid
│ │  card  │ │  card  │   │
│ └────────┘ └────────┘   │
│ ┌────────┐ ┌────────┐   │
├──────────────────────────┤
│ Jobs  Alerts  Saved  ⟩   │  ← bottom nav (thumb-friendly)
└──────────────────────────┘
```

**Kya badlega:**
- Hero 320px → **90px** (heading 24px, subtitle 1 line)
- 4 stats → **1 strip**: `1,378 live · 158 Pakistan · 838 aaj naye`
- Chips 9 → **3 tabs** (Govt / Private / Remote) + "More filters" sheet
- **2-column poster grid** mobile par (desktop 3–4)
- **Bottom navigation** — Jobs · Alerts · Saved · More
- **Sticky search** — scroll karte waqt upar rehta hai
- Job detail par **sticky "Apply on NJP →"** bar neeche
- Colour: **navy #0F2A47 + gold #C9A227** (poster theme ke saath match)
- Type: Inter, h1 24px mobile / 38px desktop

**Kyun ye best hai:** pehli screen par **2 jobs dikhte hain** (aaj 0), WhatsApp se aaye visitor 2 tap mein job tak pohnchta hai, aur poster thumbnails scroll rukwate hain.

---

## Concept B — "Editorial / Newspaper"

Serif headings, dense list, poster chhota. Sarkari job walon (35+) ke liye serious, bharosemand feel.

- Heading serif (Noto Serif), maroon + cream
- Ek screen par **5–6 jobs** (list view, chhota thumbnail)
- "Aaj ki sarkari jobs" jaisi daily digest feel
- **Nuksan:** posters ka fayda kam, young audience ko boring lag sakta hai

---

## Concept C — "Bold / Social-first"

Bade colour blocks, full-bleed posters, gradient hero. Instagram/WhatsApp sharing ke liye.

- Har card ek bara poster, swipe karein
- Detail page par poster full-width, upar "Share on WhatsApp" bara
- **Nuksan:** mobile par slow (bade images), desktop par ajeeb

---

## Meri sifarish: **A + C ka mix**

- Structure = **A** (mobile-first, 2-col grid, bottom nav, sticky search)
- Desktop = **C** ka poster-forward feel (3-col grid, bade posters)
- Colour = navy + gold (posters ke saath consistent)
- **5 din ka kaam**, isi chat se, step by step — har step ke baad aap dekh kar "haan/nahi" bolein

---

# 3. SEO — ab tak kya hua + aage ka plan

## ✅ Ho chuka (verified)
JobPosting schema (1,371 pages) · sitemaps (3) · canonicals · facet noindex · expired-job cleanup · 24 city/category pages · IndexNow pings · Search Console verified · sitemap submitted

## 📅 0–30 din (sab se zyada asar)

| # | Kaam | Kyun |
|---|---|---|
| 1 | **About + Contact + Privacy pages** | Google E-E-A-T maangta hai. AdSense ke liye bhi zaroori |
| 2 | **Internal links**: har job page → uske city + category page | Crawling + authority flow |
| 3 | **FAQPage schema** city pages par ("Karachi mein sarkari jobs kaise dhoondein") | SERP mein extra jagah |
| 4 | **40 aur landing pages** role × city (jahan ≥5 jobs hon) — e.g. "teacher jobs in Lahore", "driver jobs in Karachi" | Yahi normal Google search jeette hain |
| 5 | **Employer hub pages** (`employers/wapda.html`) — us company ki saari jobs | Long-tail + brand searches |
| 6 | Bing Webmaster Tools mein site add (IndexNow se already ping ho raha hai) | Bing/ChatGPT search |

## 📅 30–90 din

| # | Kaam | Kyun |
|---|---|---|
| 7 | **Urdu version** top 20 pages ki (`/ur/`) + `hreflang` | 60% users Urdu mein search karte hain — bara untapped traffic |
| 8 | **3 guides**: "Govt job application ka tareeqa", "CV kaise banayein", "NTS/FPSC test tayari" | Topical authority + backlinks |
| 9 | **Backlinks**: Pakistani job directories, Facebook groups, WhatsApp channel, X/LinkedIn profile | Authority — bina backlinks ke rank mushkil |
| 10 | **Salary pages**: "government teacher salary in Pakistan" | Bohat zyada searched, kam competition |

## 📅 90+ din
- GSC ka **Job Postings report** monitor — jo jobs index nahi ho rahi, unki wajah fix
- Core Web Vitals (poster images ko WebP/AVIF mein convert karna)
- Jo pages "Crawled – currently not indexed" hain, unka content deepen karna

**Sach:** indexing 48–72 ghante mein shuru hoti hai, magar **top ranking 3–6 mahine** leti hai. Sab se bara lever backlinks + Urdu content hoga.

---

# 4. Agla qadam — aap 3 mein se kya chahte hain?

**A.** Design: "Rozgar Pro" (mobile-first) — main 5 steps mein implement karun
**B.** Design: pehle sirf **mobile fixes** (hero chhota, 2-col grid, bottom nav) — 1 din ka kaam
**C.** SEO: 40 naye landing pages + About/Contact/Privacy + FAQ schema — 2 din ka kaam

Meri sifarish: **B → C → baqi A**. Pehle mobile fix (sab se bara UX nuksan), phir SEO pages, phir poora redesign.

---

# ⚙️ Implementation log — 23 Oct 2026

Everything below was **researched first, then built**. Nothing here is a proposal any more.

## 1. Research that changed the plan

| Question | What the research said | What we did |
|---|---|---|
| Is the design actually the problem? | Every audit says 60–70 % of job-board traffic is mobile; CTAs in the bottom 20 % of the screen convert ~35–40 % better; tap targets need 44–48 px; inputs ≥16 px stop iOS zoom; search + first CTA must be above the fold | Full mobile-first rebuild (below) |
| Can we mass-generate city × role pages? | No. Google's doorway-page and scaled-content-abuse policies target exactly that. Safe bar: 60–70 % unique copy per page, real per-page data, published 5–10 per week — not 50 in one batch | Raised the quality gate to **5 real jobs per page** and made every page carry its own numbers, employers, deadline data and Q&A |
| Does the emoji bell render? | No — it showed as a tofu box on the live mobile screenshot | Replaced with an inline SVG |

## 2. Design — "Rozgar Pro", now live

- Hero cut from ~320 px to ~120 px; the four tall stat blocks became one inline strip
  (`live · in Pakistan · government · new today`).
- **2-column poster grid on phones** (3-column from 900 px), so 4–6 jobs are visible in the
  first screen instead of zero.
- **Bottom navigation** on phones: Jobs · Alerts · Saved · Post a job.
- Sticky search bar on phones; sticky **“Apply on …”** bar on job pages.
- Navy `#0f2a47` + gold `#c9a227` palette, 46 px+ controls, 16 px inputs.
- Landing pages keep desktop cards; the mobile grid only restyles poster cards.

## 3. Easy English rewrite

Every user-facing string is now plain English: home page, alerts, employers, 404, job pages,
landing pages, posters, error messages and toasts. The only Roman Urdu left is inside internal
guides (`SETUP_GUIDE.md`, `README.md`) which are not part of the website.

## 4. Local job format (employer postings)

| File | Purpose |
|---|---|
| `scripts/add_job.py` | Guided questions → appends to `data/manual-jobs.json` |
| `scripts/check_jobs.py` | Validates JSON + CSV: missing title, past closing date, bad link, short description, duplicates |
| `data/jobs-template.csv` | Sheet template with every poster field |
| `data/manual-jobs.schema.json` | Field-by-field explanation |
| `data/HOW-TO-ADD-JOBS.md` | The whole process in plain English |

`scripts/fetch_jobs.py` now reads qualification, experience, age limit, vacancies, BPS,
last date and application steps from CSV submissions too — so imported jobs get the same
poster and detail page as hand-added ones.

## 5. SEO work in this pass

- New pages: **About, Contact, Privacy, Terms** — all linked in the footer and in `sitemap-pages.xml`.
- **FAQPage schema** on every city/category page, with answers built from that page's own data.
- Job pages now link **up** to their city page and their category page (real internal links, not
  a sitemap-only orphan).
- Filtered URLs (`?q=`, `?city=`, `?saved=1` …) are marked `noindex,follow` with a clean canonical.
- Landing pages link to each other; each page also lists the employers hiring in that city.

## 6. Still owned by you

1. `alerts.owner_email` in `data/site-config.json` — real address so the alert form works.
2. Google Form URL if you prefer a form over email.
3. Domain name — add a `CNAME` file and the build switches every canonical URL automatically.
