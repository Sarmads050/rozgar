# 🚀 Rozgar — Pakistan Job Website (Complete Setup Guide)

Ye guide aap ki **job website** 10–15 minute mein live kar dega.
Har job ka **apna designed poster** khud ban jata hai — koi ad copy karne ki zaroorat nahi.

**Is version mein naya kya hai:**

| # | Feature | Kahan |
|---|---|---|
| 1 | Naya poster design — 6 palettes, dark/light, QR, deadline pill | § Poster |
| 2 | Email + WhatsApp job alerts (100% free) | STEP 8 |
| 3 | Apni local jobs ka set format — CSV/JSON importer, live validation | STEP 6 |
| 4 | Deep SEO — JobPosting spec, city/category pages, sitemaps, IndexNow | STEP 9 |

---

## 60-second quick start

```bash
python scripts/fetch_jobs.py      # jobs + posters + pages banao
python scripts/seo_check.py       # deploy se pehle check
python -m http.server 8000        # local preview
```

---

## Pehle ye samajh lein (important)

Aap chahte thay ke "job advertisements download kar ke laga doon". Wo **legally
possible nahi** — kisi doosri site/company ka ad ya banner copy karna copyright
aur unki terms ki violation hai (domain ban ho sakta hai).

**Jo system main ne banaya hai wo behtar hai:**

| Aap ki demand | Jo implement hua |
|---|---|
| Choti se bari har job | NJP (govt), JobsAlert.pk, Ilmkidunya + 5 international APIs = **1,300+ jobs** |
| Automatic aayen | GitHub Action **har ghante** chal kar sab kuch khud update karta hai |
| Ad ki jagah poster | Har job ka **apna 1080×1350 poster** generate hota hai — branded design |
| Poster mein poori detail | Qualification, experience, **age limit**, vacancies, BPS grade, **last date**, **how to apply**, QR code |
| Koi job miss na ho | Pakistan jobs (govt/private) + remote + international, sab ek jagah |

> Poster **hum khud design karte hain** us job ki asli information se — kisi ki
> creative copy nahi hoti. Ye legal hai aur professional bhi lagta hai.

---

## STEP 1 — Repository

1. [github.com/new](https://github.com/new)
2. Naam: `rozgar`, visibility **Public** ✅
3. README add **na** karein → **Create repository**

## STEP 2 — Files upload

1. `rozgar-website.zip` extract karein
2. Repo page → **“uploading an existing file”**
3. Andar ki **saari files** drag karein → **Commit changes**

> ⚠️ `index.html` repo ki **root** mein hona chahiye.
> ℹ️ `.github` aur `.gitignore` hidden hote hain — Windows: `View → Show → Hidden items`.
> Agar browser upload na kare to GitHub Desktop use karein.

## STEP 3 — Pages on karein

Repo → **Settings → Pages → Source: GitHub Actions**

## STEP 4 — Pehli build chalayein

1. Repo → **Actions** tab
2. **“Refresh jobs & deploy site”** → **Run workflow**
3. 3–5 minute (poster rendering thoda waqt leta hai)
4. Live: `https://<username>.github.io/rozgar/`

Har ghante khud refresh hota rahega.

---

## STEP 5 — Pakistan ki jobs kahan se aa rahi hain?

| Source | Kya milta hai | Kitni |
|---|---|---|
| **NJP** (njp.gov.pk) | Federal govt jobs, BPS grade, age limit, deadline | ~30 live |
| **JobsAlert.pk** | Govt + private, "How to Apply" + last date | 100+ |
| **Ilmkidunya** | Punjab/Sindh/KP govt + private, city-wise | 100+ |
| Arbeitnow / Himalayas / Remote OK / Jobicy / Remotive | Remote & international (Pakistanis apply kar sakte hain) | 1,200+ |

**Rozee, Mustakbil, Indeed ki public API nahi hai** aur unhe scrape karna unki
terms ke khilaf hai — is liye wo legally shamil nahi kiye. Baqi apni **local jobs**
aap khud add kar sakte hain (neeche STEP 6).

Har source ka control `scripts/pk_sources.py` me hai:

```python
SOURCES_ENABLED = {"njp": True, "jobsalert": True, "ilmkidunya": True}
```

Kisi source par aitraaz ho to `False` kar dein — bas.

---

## STEP 6 — Apni (local) jobs add karna

Do tareeqe hain — **CSV** (asaan, Google Form / Excel se) ya **JSON** (developer-friendly).
Dono ka nateeja bilkul same hai: job site par waise hi dikhegi jaise scraped jobs,
apne **unique poster**, detail page aur apply block ke saath.

### 6a. CSV se (recommended)

1. `data/jobs-template.csv` kholein (Excel ya Google Sheets mein) — column names
   already set hain, sirf rows bharein.
2. File ko `data/manual-jobs.csv` ke naam se save karein.
3. Terminal / GitHub Actions mein:

```bash
python scripts/import_csv.py data/manual-jobs.csv        # naye jobs add
python scripts/import_csv.py data/manual-jobs.csv --check  # sirf check
python scripts/import_csv.py --replace                   # poori list replace
```

Importer har row check karta hai aur row number ke saath saaf error deta hai —
"last date samajh nahi aayi", "apply ka koi tareeqa nahi diya", waghera.
Date `2026-11-20`, `20-11-2026`, `20 Nov 2026` — teeno chaltein hain.

### 6b. JSON se

`data/manual-jobs.json` mein array of objects. **Sirf `title` aur `company` lazmi hain.**

| Field | Kya likhein | Poster par |
|---|---|---|
| `title` | Asli job title, e.g. `Assistant Manager Finance` | Bara heading |
| `company` | Chhota naam | Employer line |
| `employer_display` | Poora official naam | Employer line |
| `location` | `Lahore, Pakistan` / `Remote — Pakistan` | Chip + grid |
| `sector` | `government` · `private` · `contract` · `internship` · `remote` | **Poore poster ka colour** |
| `qualification` | `MBA Finance / M.Com` | JOB DETAILS |
| `experience` | `3 years` | JOB DETAILS |
| `age_limit` | `18–30 years` | JOB DETAILS |
| `vacancies` | `2` | Chip + grid |
| `bps` | `BPS-17` (govt) | Chip |
| `salary` | `PKR 120,000 – 150,000 / month` | JOB DETAILS |
| `salary_min` / `salary_max` | sirf number (`120000`) | Google for Jobs |
| `last_date` | `2026-11-20` | Deadline banner + "N days left" |
| `how_to_apply` | 2–4 lines ka tareeqa | HOW TO APPLY box |
| `apply_url` | Online apply ka link | **QR code** |
| `description` | 100+ words | Detail page (Google) |
| `tags` | `["Finance", "Tax"]` | Chips |

Poori list: `data/manual-jobs.schema.json`.
Example: `data/manual-jobs.json` (teen sample jobs — apni jobs se replace karein).

> **Zaroori:** `last_date` guzarne ke baad job build se khud nikal jati hai —
> page, poster aur sitemap entry sab saaf ho jate hain.

### 6c. Employer khud bheje (Google Form)

STEP 7 dekhein — form ki CSV ko `data/submissions.csv` ke naam se rakhein,
aur `python scripts/import_csv.py data/submissions.csv` chala dein.

---

## STEP 7 — Employers khud job bhejein (optional, powerful)

1. [forms.google.com](https://forms.google.com) → blank form
2. Fields (naam bilkul yahi rakhein — importer inhein pehchanta hai):
   `Job Title` · `Company` · `Location` · `Job Type` · `Sector` · `Category` ·
   `Qualification` · `Experience` · `Age Limit` · `Vacancies` · `BPS` · `Salary` ·
   `Last Date` · `How to Apply` · `Apply URL` · `Email` · `Description`
3. Responses → **Link to Sheets** → `File → Share → Publish to web` → **CSV**
4. Us CSV ka link `data/submissions.csv` ke roop mein download karein, ya
   `scripts/import_csv.py` mein seedha URL de dein.

Har ghante bot us file ko parh kar job + poster publish kar dega.

---

## STEP 8 — Job alerts (email + WhatsApp)

**Sab kuch free hai.** Alerts page pehle se bana hua hai: `alerts.html`.

### 8a. Email alerts — Google Form + Resend (free 3,000/month)

1. **Form banayein** ([forms.google.com](https://forms.google.com)) — fields:
   `Email` · `City` · `Category` · `Qualification` · `Keywords` · `Frequency`
   (`Daily` / `Instant` / `Weekly`) · `Confirmed` (dropdown `Yes` / `No`).
   *Tip:* settings mein "Collect email addresses" on karein — double opt-in mil jata hai.
2. **Sheet publish karein:** Responses → Sheets → `File → Share → Publish to web` → CSV.
   Woh link copy karein.
3. **Resend:** [resend.com](https://resend.com) par free account → API key banayein
   (3,000 emails/month, 100/day). Domain verify karein, warna `onboarding@resend.dev` use karein.
4. **GitHub Secrets** (Settings → Secrets and variables → Actions):

| Secret | Value |
|---|---|
| `RESEND_API_KEY` | `re_...` |
| `ALERT_FROM_EMAIL` | `alerts@aapka-domain.com` |
| `SUBSCRIBERS_CSV` | Google Sheet ka published CSV link |

5. **Form ka link site par lagayein:** `data/site-config.json` →

```json
"alerts": { "email_form_url": "https://forms.gle/xxxxxxx" }
```

Alerts page khud hi button live kar dega.

> Gmail se bhejna hai? `SMTP_USER`, `SMTP_PASS` (Gmail **App Password**) set karein
> — Resend ki zaroorat nahi. Lekin Gmail ki limit ~500/day hai.

### 8b. WhatsApp alerts — Channel (free)

1. WhatsApp → **Updates** → **Channels** → **+** → naya channel banayein
   (naam: `Rozgar Jobs`).
2. Channel khol kar **Invite link** copy karein (`https://whatsapp.com/channel/...`).
3. `data/site-config.json` mein daal dein:

```json
"alerts": { "whatsapp_channel_url": "https://whatsapp.com/channel/xxxxx" }
```

Aap channel par har nayi job ka poster + link post karein — subscribers ko
notification chala jayega. Unka number aapko nazar nahi aata.

### 8c. WhatsApp auto-post (optional, CallMeBot)

Har build ke baad nayi jobs khud channel/group par chali jayein:

1. Apne number se <https://www.callmebot.com/blog/whatsapp/> par "Get API key" — free.
2. Secrets: `WHATSAPP_PHONE` (923xxxxxxxxx) aur `WHATSAPP_APIKEY`.
3. Agli build se digest khud chala jayega.

### 8d. Share button

Har job page par **WhatsApp par bhejein** button hai — title, last date aur link
tayyar message mein chala jata hai. Poster download karke bhi bhej sakte hain.

---

## STEP 9 — SEO (Google for Jobs + normal search)

Ye sab already build mein hai — aapko sirf 3 kaam karne hain.

### 9a. Search Console (zaroori)

1. [search.google.com/search-console](https://search.google.com/search-console) → **Add property**
2. `https://aapka-site` daalein → verify (HTML tag ya file — GitHub Pages par file asaan hai)
3. **Sitemaps** → `sitemap.xml` submit karein (index hai, baqi khud utha lega)
4. **Job postings** report dekhein — yahan dikhega kaunsi jobs Google Jobs mein hain

### 9b. IndexNow (Bing + ChatGPT search, 2 minute)

1. Key banayein: `python3 -c "import secrets;print(secrets.token_hex(16))"`
2. Secret `INDEXNOW_KEY` set karein — bot khud `<key>.txt` file bana kar ping kar dega.

### 9c. Kya-kya ban raha hai (build ke andar)

| Cheez | Detail |
|---|---|
| `JobPosting` JSON-LD | Sirf detail page par, exactly ek — Google ki poori spec (description 100+ words, `validThrough`, `employmentType`, `identifier`, `directApply`, salary, experience/education) |
| City pages | `jobs-in/karachi.html` waghera — 3+ live jobs ho tabhi banti hain |
| Category pages | `category/finance-accounting.html` waghera |
| Sitemaps | `sitemap.xml` index → `sitemap-jobs-N.xml` (20k URLs/file), `sitemap-pages.xml`, `sitemap-images.xml` (posters) |
| Canonical | Har page par absolute |
| Facets | `?q=` `?city=` waghera par `noindex,follow` — duplicate content se bachao |
| Expired jobs | Page, poster, sitemap — sab se hat jati hain |
| `robots.txt` | Allow-all + sitemap line |
| Check | `python scripts/seo_check.py` — deploy se pehle 30 second |

---

## STEP 10 — Domain

1. Domain khareedein — Cloudflare / Namecheap (~$10–11/saal `.com`)
2. Settings → Pages → **Custom domain**
3. DNS:

| Type | Name | Value |
|---|---|---|
| A | `@` | `185.199.108.153` |
| A | `@` | `185.199.109.153` |
| A | `@` | `185.199.110.153` |
| A | `@` | `185.199.111.153` |
| CNAME | `www` | `<username>.github.io` |

4. **Enforce HTTPS** ✅

---

## Poster — naya design (v2)

Har job ka **apna** poster banta hai — 1080 × 1350 (Instagram/WhatsApp portrait),
plus ek 1200 × 630 OG image jo link share karne par dikhti hai.

**3 themes** (env var `POSTER_THEME` se switch):

| Theme | Look | Kab use karein |
|---|---|---|
| `navy` *(default)* | Deep navy + gold — official, premium | sarkari jobs ke liye sab se bharosemand |
| `noir` | Graphite + neon — modern tech | private/IT focus ho to |
| `maroon` | Maroon + cream — warm, traditional | "newspaper" feel chahiye to |

Theme badalne ke liye bas ek line:

```bash
POSTER_THEME=maroon python scripts/fetch_jobs.py
```

GitHub Actions mein permanently badalna ho to `.github/workflows/deploy.yml` ke
`Fetch jobs…` step mein add karein: `POSTER_THEME: "maroon"`.

Har theme ke andar **6 palettes** sector ke hisaab se chunti hain:

| Sector | Palette |
|---|---|
| Government | theme ka main colour (navy / graphite / maroon) |
| Private | indigo / sapphire |
| Internship | crimson |
| Contract | gold / amber |
| Remote | violet / teal |

Palette aur light/dark layout job ke slug se deterministically chunte hain — yani
ek job ka poster hamesha same dikhta hai, lekin 1000 jobs ke 1000 different posters
lagte hain (kabhi repeat nahi).

**Poster par kya hota hai:** brand mark · sector badge · title (auto-shrink, 3 lines
tak) · employer · chips (city, posts, BPS, type) · JOB DETAILS grid (qualification,
experience, age limit, vacancies, salary, location) · deadline banner with
**"N days left"** pill · HOW TO APPLY box + **QR code** · footer with site URL + source credit.

Poster kabhi delete/overwrite nahi hota bina build ke — har build par dobara render
hota hai, is liye last date ke din khud update hote hain.

```bash
python scripts/fetch_jobs.py        # sab posters dobara bante hain
```

Sirf ek job ka poster test karna ho:

```bash
python - <<'EOF'
import sys, json; sys.path.insert(0, "scripts")
from poster import render_poster
job = json.load(open("data/jobs.json"))["jobs"][0]
render_poster(job, "/tmp/test.jpg", site_url="https://rozgar.pk", source_line="Source: " + job["source"])
EOF
```

---

## Rozana ka 5-minute routine

| Kaam | File |
|---|---|
| Nayi local job add | `data/manual-jobs.json` |
| Employer submissions | `data/submissions.csv` |
| Source on/off | `scripts/pk_sources.py` → `SOURCES_ENABLED` |
| Design/colors | `scripts/poster.py` → `THEMES` |
| Kitni PK jobs | workflow → `PK_LIMIT` (default 90) |
| Refresh ka waqt | `.github/workflows/deploy.yml` → `cron` |

---

## Troubleshooting

| Masla | Hal |
|---|---|
| Build fail on `pip install` | Workflow mein "Install poster dependencies" step check karein |
| Posters nahi ban rahe | Actions log mein `! poster ...` dekhein — font missing ho to `assets/fonts/` upload hui? |
| Punjab/PPSC jobs nahi aa rahin | Un ki site **sirf Pakistani IP** se khulti hai — GitHub servers block karte hain. NJP/JobsAlert/Ilmkidunya se wo cover ho jati hain |
| Koi job purani lag rahi | `KEEP_DAYS = 45` — us se purani hat jati hain |
| Poster par text kata hua | Title bohat lamba — script khud shrink karta hai, phir bhi ajeeb lage to `poster.py` mein font size adjust karein |

---

## File map

```
job-site/
├── index.html               # home + filters + Pakistan band
├── alerts.html              # email / WhatsApp alerts page
├── employers.html           # "post a job" page
├── jobs/                    # 1 page per job (auto)
├── jobs-in/                 # city landing pages (auto, 3+ jobs only)
├── category/                # category landing pages (auto)
├── posters/                 # poster + og image per job (auto)
├── data/
│   ├── jobs.json            # poori live list (front-end isi se chalta hai)
│   ├── manual-jobs.json     # aapki apni jobs
│   ├── manual-jobs.schema.json
│   ├── jobs-template.csv    # CSV template
│   ├── site-config.json     # alert links, contact email
│   └── submissions.csv      # Google Form se (optional)
├── assets/css/style.css
├── assets/js/app.js
├── assets/fonts/            # Inter (poster)
├── scripts/
│   ├── fetch_jobs.py        # main engine
│   ├── pk_sources.py        # NJP / JobsAlert / Ilmkidunya
│   ├── poster.py            # poster + OG renderer
│   ├── import_csv.py        # CSV → manual-jobs.json
│   ├── send_alerts.py       # email + WhatsApp alerts
│   ├── ping_indexnow.py     # Bing / ChatGPT search ping
│   └── seo_check.py         # deploy se pehle health check
├── sitemap.xml              # index → sitemap-jobs-N / pages / images
├── feed.xml, robots.txt
└── .github/workflows/deploy.yml   # hourly: fetch → posters → pages → alerts → deploy
```

---

## Kya cheez kahan badalni hai

| Badalna hai | File |
|---|---|
| Brand colour, fonts, layout | `assets/css/style.css` |
| Poster ka design/palette | `scripts/poster.py` |
| Kitni PK jobs scrape hon | workflow mein `PK_LIMIT` (default 90) |
| Kitne posters banein | `POSTER_LIMIT` (default 400) |
| Alert form / WhatsApp channel link | `data/site-config.json` |
| Apni jobs | `data/manual-jobs.json` ya CSV |
| Site ka domain | `SITE_URL` (workflow khud set karta hai) |
