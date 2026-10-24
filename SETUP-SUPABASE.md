# Supabase setup — 15 minutes, once

The site is designed to work with Supabase **off**. Nothing breaks while it is off; the employer
form quietly falls back to the GitHub issue form and the alerts page offers the RSS feed. Switching
it on adds four things that need a database:

| Feature | What it does |
|---|---|
| **Post a job** | Employer fills a real form → row lands in `job_submissions` as `pending` |
| **Job alerts** | Email + city + keyword stored in `alert_subscribers`, double opt-in |
| **View counts** | `record_view()` increments one row per job per day |
| **Saved jobs** | A visitor's shortlist follows them across pages, keyed by a random device id |

---

## 1. Create the project

1. Go to <https://supabase.com/dashboard> — you said the account already exists (GitHub login).
2. **New project** → name `rozgar`, region **Southeast Asia (Singapore)** *(closest to Pakistan;
   Mumbai is also fine and sometimes faster for PK users)*, strong database password — save it in
   your password manager, you rarely need it again.
3. Wait ~2 minutes for provisioning.

## 2. Run the schema

1. Left sidebar → **SQL Editor** → **New query**.
2. Paste the entire contents of [`supabase/schema.sql`](supabase/schema.sql) → **Run**.
3. Expected result: `Success. No rows returned`. The script is idempotent — you can run it again
   after any change without dropping data.

What it creates:

- `job_submissions` — employer listings, `status` in `pending / approved / rejected / published`
- `alert_subscribers` — emails with `confirm_token` and `unsub_token` (double opt-in)
- `job_views` — one row per `(job_slug, day)`, written only through the `record_view()` function
- `saved_jobs` — a browser device id and a job slug, nothing personal
- **Row Level Security on all four tables.** Anonymous visitors may only:
  insert a submission with `status='pending'`, insert an unconfirmed subscriber, and call
  `record_view()`. They cannot read submissions, cannot read other people's emails,
  and cannot call `approve_submission()`.

## 3. Copy two values

Dashboard → **Project Settings** → **API**:

| Value | Where it goes | Safe to publish? |
|---|---|---|
| **Project URL** (`https://xxxx.supabase.co`) | `data/site-config.json` → `supabase.url` | ✅ yes |
| **anon / public** key | `data/site-config.json` → `supabase.anon_key` | ✅ yes — it is designed for browsers, RLS does the protecting |
| **service_role** key | GitHub → Settings → Secrets → `SUPABASE_SERVICE_KEY` | ❌ **never** in the repo, never in the browser |

```json
"supabase": {
  "url": "https://abcdefghijklm.supabase.co",
  "anon_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9....",
  "enabled": true
}
```

Also add the site as a **variable** (Settings → Variables → Actions → New variable):
`SUPABASE_URL` = the same project URL. The workflow uses it to pull approved rows.

> If the anon key ever leaks it is not a disaster — that is what RLS is for. If the
> **service_role** key leaks, rotate it immediately in Project Settings → API → *Reset*.

## 4. Tell Supabase which site may write

Dashboard → **Authentication** → **URL Configuration** (only needed once you add email
confirmation links in step 6). Add:

- Site URL: `https://sarmads050.github.io/rozgar/`
- Redirect URLs: `https://sarmads050.github.io/rozgar/*`

## 5. How a listing goes live

```
employer submits the form
        │
        ▼
job_submissions  (status = pending)          ← spam protection: the form has a honeypot,
        │                                       the row is invisible to the public
        ▼
you open Table Editor → look at the row → set status = approved
        │
        ▼
next hourly build runs scripts/export_submissions.py
        │  (service_role key, GitHub Secret)
        ▼
data/manual-jobs.json  →  committed by the bot
        │
        ▼
normal build writes jobs/<slug>.html with JobPosting schema
        │
        ▼
Google and the AI assistants see a real static page
```

Nothing reaches the public site until a human sets `status = approved`. That is deliberate: one
bad row in the database cannot put spam on the site or in Google's index.

Reviewing is two clicks: **Table Editor → job_submissions → filter `status = pending` → approve or
reject**. To do it in SQL instead:

```sql
-- see what is waiting
select id, created_at, title, company, city, last_date, contact_email
from job_submissions where status = 'pending' order by created_at;

-- approve
select approve_submission('<id>');

-- reject, with a reason kept for the record
select reject_submission('<id>', 'closing date already passed');
```

## 6. Email alerts (optional, next step)

`alert_subscribers` stores the list with double opt-in tokens. To actually send mail you need a
sender — Brevo (300/day free) or Resend (3,000/month free) both work. The digest job then:

1. selects subscribers where `confirmed = true`
2. matches `city` / `keyword` against jobs published in the last 24 h
3. sends one email, with the `unsub_token` link in the footer

That script is the next thing to write once the first real subscriber exists. Until then the alerts
page tells visitors honestly that email delivery is not switched on and offers the feed.

## 7. Security checklist before you call it done

- [ ] `select tablename, rowsecurity from pg_tables where schemaname='public';` → every row `true`
- [ ] Open the site in a private window, DevTools → Console → `RozgarDB.isConfigured()` → `true`
- [ ] In the same console: `fetch(cfg.url+'/rest/v1/job_submissions?select=*')` returns `[]`, not rows
- [ ] `service_role` key appears **nowhere** in the repo: `git grep -i "service_role"`
- [ ] Anonymous insert with `status='approved'` is rejected by RLS (the `with check` clause)
- [ ] The public view `job_submissions_public` exposes approved, unexpired listings only

## 8. What still needs a human

These cannot be done from code — they are account actions:

1. Create the project and paste the three values above.
2. Approve listings (two clicks, any time).
3. Set `SUPABASE_SERVICE_KEY` and `SUPABASE_URL` in GitHub.
4. Choose an email sender if you want real digests.
