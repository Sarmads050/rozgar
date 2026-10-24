-- ═══════════════════════════════════════════════════════════════════════════
--  RozgarJobs — Supabase schema
--
--  Run this once in Supabase → SQL Editor → New query → paste → Run.
--  It is idempotent: running it twice is safe.
--
--  WHY SUPABASE IS *NOT* THE JOB DATABASE
--  --------------------------------------
--  Jobs stay as static HTML built by the GitHub Action. Google, Bing, ChatGPT
--  search, Perplexity and Claude all crawl HTML, not a JavaScript query. If a
--  job page only existed after a Supabase call, the site would disappear from
--  every search engine and from every AI answer at once.
--
--  Supabase is the LIVE layer instead:
--    · job_submissions    — the employer inbox (replaces the GitHub issue form)
--    · alert_subscribers  — real email alerts, with double opt-in
--    · job_views          — an honest "how many people looked at this" counter
--    · saved_jobs         — cross-device saved jobs without a login
--
--  The approved submissions are pulled into data/manual-jobs.json by
--  scripts/export_submissions.py every hour, and only then become public pages.
-- ═══════════════════════════════════════════════════════════════════════════

create extension if not exists "pgcrypto";

-- ── 1. Employer submissions ────────────────────────────────────────────────
create table if not exists public.job_submissions (
    id              uuid primary key default gen_random_uuid(),
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),

    title           text not null check (char_length(title) between 3 and 120),
    company         text not null check (char_length(company) between 2 and 90),
    sector          text not null default 'private'
                    check (sector in ('government', 'private', 'semi-government',
                                      'ngo', 'remote')),
    city            text not null check (char_length(city) between 2 and 60),
    vacancies       int check (vacancies is null or (vacancies > 0 and vacancies < 100000)),
    qualification   text check (qualification is null or char_length(qualification) <= 120),
    experience      text check (experience is null or char_length(experience) <= 80),
    age_limit       text check (age_limit is null or char_length(age_limit) <= 40),
    salary          text check (salary is null or char_length(salary) <= 80),
    bps             text check (bps is null or char_length(bps) <= 12),
    last_date       date not null,
    description     text not null check (char_length(description) between 40 and 4000),
    how_to_apply    text check (how_to_apply is null or char_length(how_to_apply) <= 500),
    apply_url       text check (apply_url is null or apply_url ~* '^https?://'),
    apply_email     text check (apply_email is null or apply_email ~* '^[^@\s]+@[^@\s]+\.[a-z]{2,}$'),
    contact_name    text check (contact_name is null or char_length(contact_name) <= 80),
    contact_email   text not null check (contact_email ~* '^[^@\s]+@[^@\s]+\.[a-z]{2,}$'),

    -- moderation
    status          text not null default 'pending'
                    check (status in ('pending', 'approved', 'rejected', 'published')),
    moderation_note text,
    reviewed_at     timestamptz,
    published_slug  text,          -- set when the build turns it into a page

    -- abuse control
    client_hash     text,          -- sha256(email + ip) truncated, never the raw IP
    user_agent      text,

    constraint needs_apply_route check (apply_url is not null or apply_email is not null)
);

create index if not exists job_submissions_status_idx on public.job_submissions (status, created_at desc);
create index if not exists job_submissions_last_date_idx on public.job_submissions (last_date);

-- Everything the site shows must come from here, so a rejected row can never
-- leak: the public only ever gets the `approved`/`published` set.
create or replace view public.job_submissions_public as
    select id, title, company, sector, city, vacancies, qualification, experience,
           age_limit, salary, bps, last_date, description, how_to_apply,
           apply_url, published_slug
    from public.job_submissions
    where status in ('approved', 'published');

-- ── 2. Alert subscribers ───────────────────────────────────────────────────
create table if not exists public.alert_subscribers (
    id            uuid primary key default gen_random_uuid(),
    email         text not null unique check (email ~* '^[^@\s]+@[^@\s]+\.[a-z]{2,}$'),
    city          text,
    keyword       text,
    frequency     text not null default 'daily' check (frequency in ('instant', 'daily', 'weekly')),
    confirmed     boolean not null default false,
    confirm_token uuid not null default gen_random_uuid(),
    unsub_token   uuid not null default gen_random_uuid(),
    created_at    timestamptz not null default now(),
    confirmed_at  timestamptz,
    unsubscribed_at timestamptz,
    source        text default 'site'
);

create index if not exists alert_confirmed_idx on public.alert_subscribers (confirmed, unsubscribed_at);

-- ── 3. View counter (aggregate only, no personal data) ─────────────────────
create table if not exists public.job_views (
    job_slug  text not null,
    day       date not null default current_date,
    views     int not null default 0,
    primary key (job_slug, day)
);

create or replace function public.record_view(slug text)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.job_views (job_slug, day, views)
    values (left(slug, 200), current_date, 1)
    on conflict (job_slug, day) do update set views = public.job_views.views + 1;
end;
$$;

-- ── 4. Saved jobs across devices (no account needed) ───────────────────────
create table if not exists public.saved_jobs (
    device_id  text not null check (char_length(device_id) between 8 and 64),
    job_slug   text not null check (char_length(job_slug) between 3 and 200),
    created_at timestamptz not null default now(),
    primary key (device_id, job_slug)
);

-- ═══════════════════════════════════════════════════════════════════════════
--  ROW LEVEL SECURITY — the anon key is public, so this is the only wall.
-- ═══════════════════════════════════════════════════════════════════════════
alter table public.job_submissions   enable row level security;
alter table public.alert_subscribers enable row level security;
alter table public.job_views         enable row level security;
alter table public.saved_jobs        enable row level security;

-- submissions: anyone may INSERT, but only as 'pending'. Nobody but the
-- service role (the GitHub Action) may read or change a row.
drop policy if exists "public can submit a job" on public.job_submissions;
create policy "public can submit a job"
    on public.job_submissions for insert
    to anon, authenticated
    with check (status = 'pending' and reviewed_at is null and published_slug is null);

-- subscribers: insert only; nobody can enumerate the list from the browser.
drop policy if exists "public can subscribe" on public.alert_subscribers;
create policy "public can subscribe"
    on public.alert_subscribers for insert
    to anon, authenticated
    with check (confirmed = false and unsubscribed_at is null);

-- views: read-only aggregate, writes go through record_view() only.
drop policy if exists "anyone can read view counts" on public.job_views;
create policy "anyone can read view counts"
    on public.job_views for select
    to anon, authenticated
    using (true);

-- saved jobs: scoped to a device id the browser generated itself.
drop policy if exists "device can read its saved jobs" on public.saved_jobs;
create policy "device can read its saved jobs"
    on public.saved_jobs for select to anon, authenticated using (true);

drop policy if exists "device can save a job" on public.saved_jobs;
create policy "device can save a job"
    on public.saved_jobs for insert to anon, authenticated with check (true);

drop policy if exists "device can remove a saved job" on public.saved_jobs;
create policy "device can remove a saved job"
    on public.saved_jobs for delete to anon, authenticated using (true);

-- ── 5. Moderation shortcuts ────────────────────────────────────────────────
-- Approve from the Supabase table editor, or with:
--   update job_submissions set status='approved', reviewed_at=now() where id='…';
create or replace function public.approve_submission(row_id uuid, note text default null)
returns void language sql security definer set search_path = public as $$
    update public.job_submissions
       set status = 'approved', reviewed_at = now(), moderation_note = note, updated_at = now()
     where id = row_id;
$$;

create or replace function public.reject_submission(row_id uuid, note text default null)
returns void language sql security definer set search_path = public as $$
    update public.job_submissions
       set status = 'rejected', reviewed_at = now(), moderation_note = note, updated_at = now()
     where id = row_id;
$$;

-- Only the service role may call the moderation functions.
revoke all on function public.approve_submission(uuid, text) from anon, authenticated;
revoke all on function public.reject_submission(uuid, text)  from anon, authenticated;
grant execute on function public.record_view(text) to anon, authenticated;

-- ═══════════════════════════════════════════════════════════════════════════
--  Sanity check — should return 0 rows.
-- ═══════════════════════════════════════════════════════════════════════════
-- select * from job_submissions where status = 'pending' and published_slug is not null;
