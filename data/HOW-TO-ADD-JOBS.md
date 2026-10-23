# How to add your own jobs (in plain English)

Rozgar collects jobs automatically, but you can always add a job yourself —
your own listing, an employer who emailed you, or a government post you want
to make sure is included.

There are three ways. Choose one.

---

## 1. The easy way — answer a few questions

```bash
python3 scripts/add_job.py
```

It asks for the job title, the employer, the city, the salary and so on. Press
`Enter` to skip a question you do not know. Nothing is saved until you confirm,
and it saves the job to `data/manual-jobs.json` for you.

Then rebuild:

```bash
python3 scripts/fetch_jobs.py
```

---

## 2. Edit the JSON file directly

Open `data/manual-jobs.json`. It is a list; add one object per job:

```json
[
  {
    "title": "Lab Technician (BPS-09)",
    "company": "District Health Authority Sukkur",
    "location": "Sukkur, Pakistan",
    "sector": "government",
    "type": "Full Time",
    "category": "Health & Medical",
    "qualification": "F.Sc Pre-Medical or Diploma in Lab Technology",
    "experience": "1 year",
    "age_limit": "18-30 years",
    "vacancies": 4,
    "bps": "BPS-09",
    "salary": "PKR 35,000 / month",
    "posted": "2026-10-20",
    "last_date": "2026-11-15",
    "how_to_apply": "Submit the form with attested documents at the DHA office, Sukkur.",
    "apply_url": "https://example.com/apply",
    "contact_email": "hr@example.com",
    "description": "Run routine lab tests, keep the sample register and report to the medical officer.",
    "tags": ["Lab", "Health"]
  }
]
```

Every field is explained in `data/manual-jobs.schema.json`.

### The fields that matter most

| Field | Why it matters |
|---|---|
| `title` | **Required.** Use the real title, for example `Stenographer (BPS-14)`. |
| `company` | **Required.** The employer name candidates will see. |
| `location` | `Karachi, Pakistan`, or `Remote, Pakistan` for remote jobs. |
| `last_date` | `YYYY-MM-DD`. The job is hidden after this date. Leave empty if the employer did not give one. |
| `how_to_apply` | The real steps. This is printed on the poster. |
| `apply_url` | Where the candidate actually applies. |
| `description` | 12+ words. Longer text makes a better page and a better poster. |
| `salary`, `qualification`, `age_limit`, `vacancies`, `bps` | Shown on the poster and in the job details table. |

---

## 3. Import a CSV

If you have a sheet, use `data/jobs-template.csv` as the header row and save it
as `data/submissions.csv`. Then:

```bash
python3 scripts/check_jobs.py      # checks the file first
python3 scripts/fetch_jobs.py      # builds the site
```

Column names are matched loosely, so `Job Title`, `job title` and `title` all work.
If you collect employer submissions with a Google Form, export the responses as
CSV and save them as `data/submissions.csv` — the same columns apply.

---

## Always check before you build

```bash
python3 scripts/check_jobs.py
```

It reports the file, the row number and the problem — empty title, a closing date
in the past, a broken apply link, a description that is too short, or a duplicate.
A clean run prints `✓ Everything looks good.`

---

## Rules for a listing

- No job that asks a candidate for money, a fee or bank details.
- No MLM, pyramid or “investment” schemes.
- The apply link must be a real careers page, form or email address.
- If the employer sends you a banner or logo, you may use it. Do **not** copy
  another site's advertisement.
- Remove or update a listing as soon as the employer tells you it is filled.

---

## Where the job appears

After a build, each job gets:

- a card on the home page,
- its own page at `jobs/<slug>.html` with `JobPosting` structured data,
- a poster in `posters/` at 1080 × 1350 (WhatsApp and Facebook ready),
- an entry in the city and category pages when those pages exist.
