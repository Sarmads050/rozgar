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
