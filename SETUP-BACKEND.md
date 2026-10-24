# Backend setup — the 5 things only you can switch on

Everything on the site already works without these. Each step below turns on one
extra capability, is free, and takes minutes. Keep this file — it is also the
checklist for the day you move to your own domain.

---

## 1. Analytics (free, 2 minutes) — see what people actually search

GoatCounter is free for a site like this and sets no cookies, so no pop-up
consent banner is needed.

1. Sign up at <https://www.goatcounter.com/signup> — pick a code, for example
   `rozgarjobs`. Your dashboard becomes `https://rozgarjobs.goatcounter.com`.
2. Open `data/site-config.json` and fill in:

   ```json
   "analytics": {
     "goatcounter": "rozgarjobs",
     "cloudflare_token": "",
     "plausible_domain": "",
     "track_search": true
   }
   ```

3. Commit. The loader (`assets/js/analytics.js`) is already on every generated
   page and starts sending only after that value exists.

**What you will see:** visits by country (watch the Pakistan share), top job
pages, referrers (Google vs WhatsApp vs direct), and every search term typed
into the search bar (`/search/<term>`). Search terms are the most valuable
signal — if people type "fpsc" and you have no FPSC jobs, that is your next
page to build.

Cloudflare Web Analytics is the alternative: Workers & Pages → Web Analytics →
add site → copy the token into `cloudflare_token`.

---

## 2. Email alerts (free, 5 minutes) — digest at 8am, automatically

The build already writes `feed.xml` — an Atom feed of the 60 newest vacancies,
rebuilt every hour. Any RSS-to-email service can turn that into a daily email
with zero code, zero server and zero cost.

**Buttondown** (simplest, free up to 100 subscribers)

1. Create an account → **Settings → RSS to email** → paste
   `https://sarmads050.github.io/rozgar/feed.xml` (later: `https://rozgarjobs.com/feed.xml`).
2. Choose "daily at 08:00 Pakistan time".
3. Copy your subscriber form endpoint into `data/site-config.json`:

   ```json
   "alerts": {
     "email_form_url": "https://buttondown.email/api/emails/embed-subscribe/rozgarjobs",
     "owner_email": "hello@rozgarjobs.com",
     "rss_feed": "feed.xml"
   }
   ```

4. Commit. `alerts.html` now posts the visitor's email straight to Buttondown,
   which sends the confirmation and then the daily digest.

**MailerLite / Brevo** work the same way: create an "RSS campaign" from
`feed.xml`, then paste their form action into `email_form_url`.

Until this is switched on, the alerts page tells visitors the truth and points
them at the feed — no fake "we will email you" promise.

---

## 3. WhatsApp channel (free, 10 minutes)

WhatsApp has no free posting API for channels, so the honest flow is:

1. Create a channel in WhatsApp → Business tools → Channels. Copy its link into
   `data/site-config.json`:

   ```json
   "whatsapp_channel_url": "https://whatsapp.com/channel/XXXXXXXX"
   ```

2. The Action `.github/workflows/whatsapp.yml` runs every 3 hours and writes
   `data/whatsapp-queue.json` — the newest 6 unposted jobs, already formatted:
   emoji, title, employer, city, last date, short link.
3. Open that file on your phone and forward the text to the channel. Two taps.

Optional: get the first post pushed to your own number automatically through
CallMeBot (<https://www.callmebot.com/blog/free-api-whatsapp-messages/>). Add
`CALLMEBOT_PHONE` and `CALLMEBOT_APIKEY` as repo secrets and set the repository
variable `CALLMEBOT_ENABLED=true`.

Posted jobs are remembered in `data/whatsapp-posted.json`, so nothing is ever
sent twice.

---

## 4. Google Indexing API (free, 5 minutes) — new jobs crawled in minutes

Google accepts `JobPosting` pages through the Indexing API (this is the one
exception Google makes for job pages). It does not improve ranking, it only gets
a new job page crawled the same day instead of whenever the next crawl happens —
which matters when a vacancy closes in 10 days.

1. <https://console.cloud.google.com> → new project → **APIs & services** →
   enable **Indexing API**.
2. **IAM → Service accounts** → create one → **Keys → Add key → JSON** →
   download.
3. Search Console → your property → **Settings → Users and permissions → Add
   user** → paste the service-account email (`...iam.gserviceaccount.com`) →
   role **Owner**.
4. GitHub repo → Settings → Secrets → new secret `GOOGLE_INDEXING_KEY` → paste
   the whole JSON file.

The workflow `.github/workflows/index-new-jobs.yml` then submits up to 180 new
job URLs every hour and remembers them in `data/indexed-slugs.json`.

Without the secret it prints a notice and exits — it never fails the build.

---

## 5. Your own domain (₹ nothing to ₹1,200/yr) — the biggest single SEO lever

Right now the site lives at `sarmads050.github.io/rozgar/`. Google treats a
subfolder on `github.io` as a low-trust host shared with thousands of unrelated
sites, and the domain has no history. `rozgarjobs.com` was unregistered when
this plan was written — buying it and moving there is worth more than any code
change on this list.

1. Buy `rozgarjobs.com` (Namecheap/Cloudflare, ~$10/yr).
2. Create `CNAME` in the repo root containing only `rozgarjobs.com`.
3. DNS at your registrar: four `A` records for the apex to
   `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`,
   and a `CNAME` for `www` → `sarmads050.github.io`.
4. GitHub → Settings → Pages → Custom domain → enter the domain → wait for the
   certificate → tick **Enforce HTTPS**.
5. Set the repository variable `SITE_URL=https://rozgarjobs.com` so canonicals,
   sitemaps, posters and the feed all switch over in the next build.
6. Search Console → add the new domain property → verify by DNS TXT record →
   **Settings → Change of address** → move from the `github.io/rozgar/` prefix
   property. This transfers the little authority the old URL has.

Search Console steps for the current `github.io` property are already done
(meta-tag verification + sitemap submitted) — do not repeat them.

---

## What runs by itself after this

| Time | What happens |
|---|---|
| Every hour at :15 UTC | Build pulls every source, drops expired and out-of-scope jobs, renders pages, posters, keyword pages, sitemaps, feed, and deploys |
| Every hour at :25 UTC | New job URLs go to the Google Indexing API (if configured) |
| Every 3 hours | WhatsApp post pack is regenerated |
| On issue labelled `approved` | Employer submission is parsed, validated, committed, rebuilt |
| Daily 08:00 PKT | Email digest goes out (once step 2 is done) |

Nothing in this file needs a server, a database or a paid plan.
