# 🔗 Rozgar ko GitHub par live karna (aur mujhe connect karna)

Aap ne Claude ke saath jo system banaya hai — **bilkul wahi** main yahan bana sakta hoon.
Farq sirf itna hai: is chat se main aapke GitHub account tak **khud** nahi pohnch sakta
jab tak aap ek access token na dein. (Is platform par GitHub app connector available nahi hai.)

Repo **tayyar hai** — 32 files, 2 commits, pehle se `main` branch par.

---

## Sab se pehle: repo banayein (1 minute)

1. <https://github.com/new>
2. **Repository name:** `rozgar`
3. **Public** ✅ (private repo par GitHub Pages free plan mein nahi chalta)
4. **README / .gitignore / license** — kuch bhi select na karein (khaali repo chahiye)
5. **Create repository**

Bas. Link copy kar lein, jaise `https://github.com/aapka-naam/rozgar`

---

## Option A — Token dein, main push kar dunga (recommended)

### Token banayein (2 minute)

1. <https://github.com/settings/tokens?type=beta> → **Generate new token**
2. **Token name:** `rozgar-push`
3. **Expiration:** 7 days (kaam ke baad khud expire ho jayega)
4. **Repository access:** `Only select repositories` → **rozgar**
5. **Permissions** (Repository permissions):

| Permission | Level | Kyun |
|---|---|---|
| **Contents** | Read and write | files push karne ke liye |
| **Workflows** | Read and write | `.github/workflows/deploy.yml` push karne ke liye — iske baghair GitHub "refusing to allow workflow" error deta hai |
| **Metadata** | Read-only | khud se aa jata hai |
| **Pages** | Read and write | *(optional)* Pages khud on karne ke liye |

6. **Generate token** → `github_pat_...` copy karein

### Phir mujhe chat mein bhejein

```
repo: https://github.com/aapka-naam/rozgar
token: github_pat_xxxxxxxx
```

Main push karta hoon, Pages on karta hoon, aur pehli build ka result bata deta hoon.

> **Security:** token sirf usi ek repo ka hai, 7 din mein khud khatam. Main ise
> repo mein commit nahi karta, na kisi file mein save karta hoon. Kaam ke baad aap
> <https://github.com/settings/tokens> se **Revoke** kar sakte hain — site chalti rehti hai.

---

## Option B — Aap khud push karein (token ki zaroorat nahi)

Main aapko `rozgar-repo.bundle` de raha hoon (poora git history, ek file mein).

```bash
git clone rozgar-repo.bundle rozgar
cd rozgar
git remote add origin https://github.com/aapka-naam/rozgar.git
git push -u origin main
```

Ya bilkul asaan tareeqa: GitHub repo page par **uploading an existing file** →
`rozgar-website.zip` extract kar ke saari files drag kar dein → **Commit changes**.

---

## Push ke baad — 2 clicks

1. Repo → **Settings** → **Pages**
2. **Build and deployment → Source = GitHub Actions**

Bas! Phir **Actions** tab mein pehli build chalti hai (~4–5 minute):
jobs scrape → 115+ posters → 1381 pages → sitemaps → deploy.

🌐 Site: `https://aapka-naam.github.io/rozgar/`

---

## Ab aage kaise kaam hoga

Aap yahan chat mein bas bolenge:

> "poster ka colour neela karo"
> "Karachi ki jobs zyada chahiye"
> "alerts page par Instagram ka button lagao"

Main change karta hoon → `git commit` → `git push` → **GitHub Action khud** sitemap,
posters aur site dobara build kar ke live kar deta hai. Aapko kuch nahi karna.

Har push ke baad main aapko bataunga:
- kaunsi files badli
- commit ka message
- Action ka status (`✓ deployed` ya error)

---

## Domain baad mein (jab website final ho)

1. Domain khareedein (Cloudflare / Namecheap ~$10/saal)
2. Repo → Settings → Pages → **Custom domain** → `rozgar.pk`
3. DNS:

| Type | Name | Value |
|---|---|---|
| A | `@` | `185.199.108.153` |
| A | `@` | `185.199.109.153` |
| A | `@` | `185.199.110.153` |
| A | `@` | `185.199.111.153` |
| CNAME | `www` | `aapka-naam.github.io` |

4. **Enforce HTTPS** ✅ — site, canonical URLs, sitemap aur JobPosting markup khud
   naye domain par shift ho jayenge (workflow URL khud detect karta hai).

---

## Kaun kya badal sakte hain — cheatsheet

| Kaam | Kaun |
|---|---|
| Poster design, colours, layout | Main (`scripts/poster.py`) |
| Naye sources add karna | Main (`scripts/pk_sources.py`) |
| Website ka text / pages | Main |
| Apni jobs add karna | Aap (`data/manual-jobs.json` ya CSV) |
| Alert form / WhatsApp link | Aap (`data/site-config.json`) |
| Secrets (Resend, IndexNow) | Aap (repo Settings → Secrets) |
| Domain, Pages settings | Aap |

---

## Agar push fail ho

| Error | Hal |
|---|---|
| `refusing to allow a Personal Access Token to create or update workflow` | Token mein **Workflows: Read and write** add karein (Option A, step 5) |
| `remote: Permission to ... denied` | Token usi repo ke liye banaya hai? Owner spelling check karein |
| `Repository not found` | Repo pehle create karein (upar step 1) |
| Pages par 404 | Settings → Pages → Source = **GitHub Actions**; phir Action dobara chalayein |
| Action fail: `qrcode` not found | Workflow khud install karta hai — dobara run karein (Actions → Re-run) |
