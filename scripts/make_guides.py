#!/usr/bin/env python3
"""Generates the static /guides pages (plain-English help content for job seekers).

Run once from the repo root:  python3 scripts/make_guides.py
The pages are committed, so the hourly build never touches them.
"""
from __future__ import annotations

import json
import pathlib

OUT = pathlib.Path(__file__).resolve().parent.parent / "guides"
OUT.mkdir(exist_ok=True)

HEAD = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' https: data:; font-src 'self' data:; connect-src 'self' https:; form-action 'self' mailto:; base-uri 'self'; object-src 'none'">
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta name="theme-color" content="#0f2a47">
<link rel="canonical" href="https://sarmads050.github.io/rozgar/guides/{slug}.html">
<meta property="og:type" content="article">
<meta property="og:site_name" content="RozgarJobs">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="https://sarmads050.github.io/rozgar/guides/{slug}.html">
<meta property="og:image" content="https://sarmads050.github.io/rozgar/assets/img/og.png">
<link rel="icon" type="image/svg+xml" href="../assets/img/mark.svg">
<link rel="apple-touch-icon" href="../assets/img/mark.svg">
<link rel="stylesheet" href="../assets/css/style.css">
{jsonld}
</head>
<body>

<header class="site-head">
  <div class="wrap head-in">
    <a class="brand" href="../index.html">
      <img class="brand-logo" src="../assets/img/mark.svg" alt="" width="38" height="38">
      <span class="brand-text"><strong>Rozgar<span class="bj">Jobs</span></strong><small>Jobs in Pakistan</small></span>
    </a>
    <nav class="head-nav">
      <a href="../index.html">Jobs</a>
      <a href="../alerts.html">Alerts</a>
      <a href="index.html">Guides</a>
      <a href="../employers.html">Post a job</a>
    </nav>
  </div>
</header>

<main class="wrap doc">
  <nav class="crumbs"><a href="../index.html">Home</a> <span>/</span> <a href="index.html">Guides</a> <span>/</span> <span>{crumb}</span></nav>
{body}
</main>

<footer class="site-foot">
  <div class="wrap foot-grid">
    <div>
      <a class="brand small" href="../index.html"><img class="brand-logo" src="../assets/img/mark.svg" alt="" width="30" height="30"><span class="brand-text"><strong>Rozgar<span class="bj">Jobs</span></strong></span></a>
      <p class="foot-note">Jobs in Pakistan, collected from public sources with credit.</p>
    </div>
    <div>
      <h4>Site</h4>
      <a href="../index.html">Browse jobs</a>
      <a href="../locations.html">All locations</a>
      <a href="index.html">Guides</a>
      <a href="../alerts.html">Job alerts</a>
    </div>
    <div>
      <h4>Information</h4>
      <a href="../about.html">About</a>
      <a href="../contact.html">Contact</a>
      <a href="../privacy.html">Privacy</a>
      <a href="../terms.html">Terms</a>
    </div>
    <div>
      <h4>Stay safe</h4>
      <p class="foot-note">Never pay a fee for a job offer.</p>
      <a href="../contact.html">Report a listing</a>
    </div>
  </div>
  <div class="wrap foot-bottom">
    <span>&copy; <span id="yr">2026</span> RozgarJobs</span>
    <span>Updated every hour</span>
  </div>
</footer>

<nav class="bottom-nav" aria-label="Main navigation">
  <a href="../index.html"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 10.5 12 4l8 6.5V20H4z"/><path d="M9.5 20v-5.5h5V20"/></svg><span>Jobs</span></a>
  <a href="../alerts.html"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></svg><span>Alerts</span></a>
  <a href="../index.html?saved=1"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round" aria-hidden="true"><path d="M12 3.6l2.6 5.4 5.9.8-4.3 4.1 1.1 5.8L12 16.9 6.7 19.7l1.1-5.8L3.5 9.8l5.9-.8z"/></svg><span>Saved</span></a>
  <a href="../employers.html"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg><span>Post a job</span></a>
</nav>

<script>document.getElementById('yr').textContent = new Date().getFullYear();</script>
</body>
</html>
"""

STYLE = """
<style>
  .doc { padding-top: 26px; padding-bottom: 10px; max-width: 78ch; }
  .doc h1 { font-size: clamp(25px, 3.2vw, 36px); letter-spacing: -1px; margin: 8px 0 10px; line-height: 1.15; }
  .doc .lede { color: var(--muted); font-size: 16px; margin: 0 0 20px; }
  .doc h2 { font-size: 19px; letter-spacing: -.35px; margin: 28px 0 8px; }
  .doc p, .doc li { font-size: 15px; line-height: 1.68; color: var(--ink-2); }
  .doc ul, .doc ol { padding-left: 20px; }
  .doc li { margin-bottom: 7px; }
  .doc a { color: var(--brand); text-decoration: underline; }
  .doc .box { background: var(--surface); border: 1px solid var(--line); border-left: 3px solid var(--gold); border-radius: 10px; padding: 14px 16px; margin: 18px 0; }
  .doc .box p { margin: 0; }
  .doc table { width: 100%; border-collapse: collapse; font-size: 14.4px; margin: 12px 0 18px; }
  /* wide tables must scroll inside the column, never push the page sideways */
  @media (max-width: 720px) {
    .doc table { display: block; overflow-x: auto; -webkit-overflow-scrolling: touch; white-space: nowrap; }
    .doc th, .doc td { padding: 8px 10px; }
  }
  .doc th, .doc td { text-align: left; padding: 9px 12px; border-bottom: 1px solid var(--line); }
  .doc th { color: var(--muted); font-weight: 650; background: var(--surface-2); }
  .updated { font-size: 12.5px; color: var(--muted); margin-top: 26px; }
  .next { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 22px; }
  .next a { font-size: 13px; padding: 8px 14px; border-radius: 999px; border: 1px solid var(--line); background: var(--surface); color: var(--ink-2); text-decoration: none; }
  .cards { display: grid; gap: 12px; margin: 20px 0 10px; }
  .doc .gcard, .doc .gcard:hover { text-decoration: none; }
  .doc .gcard strong { text-decoration: none; }
  .doc .gcard span { text-decoration: none; }
  @media (max-width: 720px) {
    .head-nav { display: none; }
    .doc { padding-top: 18px; }
  }
  .gcard { display: block; background: var(--surface); border: 1px solid var(--line); border-radius: 13px;
    padding: 16px 18px; text-decoration: none; transition: border-color .15s, transform .15s; }
  .gcard:hover { border-color: var(--brand); transform: translateY(-1px); }
  .gcard strong { display: block; font-size: 16px; color: var(--ink); letter-spacing: -.3px; margin-bottom: 4px; }
  .gcard span { font-size: 13.6px; color: var(--muted); line-height: 1.55; }
</style>
"""


def page(slug, title, desc, crumb, body, faq=None):
    ld = ""
    if faq:
        data = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "inLanguage": "en-PK",
            "mainEntity": [
                {"@type": "Question", "name": q,
                 "acceptedAnswer": {"@type": "Answer", "text": a}}
                for q, a in faq
            ],
        }
        ld = '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False) + "</script>"
    html = HEAD.format(title=title, desc=desc, slug=slug, crumb=crumb,
                       body=STYLE + body, jsonld=ld)
    (OUT / f"{slug}.html").write_text(html, encoding="utf-8")
    return slug


GUIDES = [
    ("national-job-portal-guide", "How to apply on the National Job Portal (NJP)",
     "A step-by-step walkthrough of applying for federal government jobs on njp.gov.pk: the account, "
     "the documents, the fee and how to track your application."),
    ("bps-pay-scales", "BPS pay scales explained (BPS-01 to BPS-22)",
     "What BPS means, which scales match which posts, how pay and allowances work, and how to read the "
     "age limit and quota in a government advertisement."),
    ("documents-for-government-job", "Documents you need for a government job",
     "The full checklist: CNIC, domicile, degrees, experience letters, photographs and attestation — "
     "plus what to carry to the test."),
    ("spot-fake-job-advertisement", "How to spot a fake job advertisement",
     "Eight warning signs, the scams common in Pakistan, how to check a listing in two minutes, and what "
     "to do if you have already paid or shared documents."),
    ("government-test-interview-guide", "The written test and interview, explained",
     "What actually happens at each stage of FPSC, PPSC, NTS and departmental recruitment in Pakistan — "
     "and a two-week preparation plan that does not need a paid course."),
    ("cv-for-government-job", "How to write a CV for a government job",
     "The order, the table and the three mistakes that get an otherwise strong application rejected by a "
     "Pakistani shortlisting committee."),
]

# ── the individual pages are written below as full HTML bodies ───────────────

page(
    "national-job-portal-guide",
    "How to Apply on the National Job Portal (NJP) — Step by Step | RozgarJobs",
    "A plain-English walkthrough of applying for federal government jobs on njp.gov.pk: creating the "
    "account, uploading documents, submitting the form and tracking the status.",
    "National Job Portal",
    """
<h1>How to apply on the National Job Portal (NJP)</h1>
<p class="lede">The National Job Portal is where most federal ministries and departments now advertise
their vacancies. This is the whole process in plain English, from making the account to checking the status.</p>

<h2>What NJP is</h2>
<p>njp.gov.pk is a single website used for federal government posts. Instead of sending a separate form to
each department, you fill your details once and apply to many posts. Not every government job is there —
provincial posts, army recruitment and most teaching jobs are advertised elsewhere — but when a federal
department is hiring, NJP is usually the first place it appears.</p>

<h2>Before you start</h2>
<ul>
  <li><strong>An email address</strong> you actually open. The activation link and every later update go there.</li>
  <li><strong>Your CNIC</strong> in front of you — the number has to match your documents.</li>
  <li><strong>Scanned copies</strong> of your CNIC, domicile, degrees and experience letters, as PDF or JPG.</li>
  <li><strong>One recent photograph</strong> with a plain background.</li>
</ul>

<div class="box">
  <p><strong>File size matters.</strong> The portal refuses uploads that are too large. If a PDF will not
  upload, scan it at a lower resolution or compress it before you try again.</p>
</div>

<h2>The steps</h2>
<ol>
  <li><strong>Create the account.</strong> Open njp.gov.pk, choose sign-up, and enter your CNIC, email and
  mobile number. Confirm the activation link that arrives by email.</li>
  <li><strong>Build the profile.</strong> Fill education, experience and personal details. Everything you
  complete here is reused when you apply, so it is worth doing properly once.</li>
  <li><strong>Upload the documents.</strong> Put each certificate in the matching slot and check that the
  scan is readable — an unreadable document is a common reason for rejection.</li>
  <li><strong>Find the job.</strong> Search on the portal, or find the vacancy on
  <a href="../index.html">RozgarJobs</a> and open the original advertisement from the job page.</li>
  <li><strong>Read the advertisement first.</strong> Qualification, experience, age limit, domicile quota
  and the closing date are all in it. Applying to a post you are not eligible for wastes your time.</li>
  <li><strong>Apply and submit.</strong> Fill the form, attach what the post asks for, pay the fee if one is
  listed, and submit before the deadline — servers get slow in the last 48 hours.</li>
  <li><strong>Save the proof.</strong> Download or screenshot the submitted application. You will need the
  application number if the department calls you for a test.</li>
</ol>

<h2>After you submit</h2>
<p>Your dashboard shows the status of each application: submitted, under review, shortlisted or rejected.
Shortlisted candidates are usually contacted by email or SMS, and the test schedule is published on the
department's own website. Check both — a missed test date is rarely reopened.</p>

<h2>Common mistakes</h2>
<ul>
  <li>Applying after the closing date because the form was left for the last day.</li>
  <li>A wrong CNIC number or date of birth — it can disqualify you at verification.</li>
  <li>Uploading a degree when the post asks for a specific subject or grade.</li>
  <li>Ignoring the domicile requirement on provincial quota posts.</li>
  <li>Not keeping the application number.</li>
</ul>

<h2>Is there a fee?</h2>
<p>Some posts have an application fee and some are free. The fee, the bank and the challan number are
written inside that job's advertisement. Never pay a person who promises to "get you shortlisted".</p>

<p class="updated">Updated 24 October 2026. Portal rules can change — always follow the advertisement in front of you.</p>
<div class="next">
  <a href="bps-pay-scales.html">BPS pay scales explained &rarr;</a>
  <a href="documents-for-government-job.html">Documents checklist &rarr;</a>
  <a href="../index.html">Browse jobs &rarr;</a>
</div>
""",
    [("Do I need an account to apply on NJP?",
      "Yes. You create one account with your CNIC and email, complete the profile and upload your documents "
      "once. Every later application reuses the same profile."),
     ("Is the National Job Portal free?",
      "Creating an account and applying is free unless that specific advertisement mentions an application "
      "fee. The fee and its challan are always stated in the advertisement."),
     ("Can I apply for more than one job?",
      "Yes. One profile can be used for as many posts as you are eligible for, and each application is "
      "tracked separately on your dashboard."),
     ("What if I miss the closing date?",
      "The portal closes the application automatically. Late applications are not accepted, so apply at "
      "least two days before the deadline.")])

page(
    "bps-pay-scales",
    "BPS Pay Scales in Pakistan Explained (BPS-01 to BPS-22) | RozgarJobs",
    "What BPS means in a Pakistani government job, which scales match which posts, and how to read the "
    "pay, allowances, age limit and quota in an advertisement.",
    "BPS pay scales",
    """
<h1>BPS pay scales explained &mdash; BPS-01 to BPS-22</h1>
<p class="lede">Every government advertisement says something like “BPS-14”. That number decides your
starting pay, your promotion path and often your age limit. Here is what it actually means.</p>

<h2>What BPS stands for</h2>
<p>BPS is the <strong>Basic Pay Scale</strong>. The government puts each post on a scale from 01 to 22.
The higher the scale, the higher the basic pay and the greater the responsibility. Your salary is not one
number: it is basic pay plus allowances (house rent, medical, conveyance and others depending on the post),
and those allowances change with the annual budget.</p>

<div class="box">
  <p><strong>Important:</strong> basic pay figures change with every pay revision. Read the pay printed in
  the advertisement you are applying for.</p>
</div>

<h2>The groups in practice</h2>
<table>
  <thead><tr><th>Scale</th><th>Typical posts</th><th>Usual qualification</th></tr></thead>
  <tbody>
    <tr><td>BPS-01 to 04</td><td>Support staff: naib qasid, chowkidar, sweeper, mali</td><td>Primary or middle; sometimes none stated</td></tr>
    <tr><td>BPS-05 to 10</td><td>Clerk, driver, dispatch rider, lab attendant, junior technician</td><td>Matric or intermediate</td></tr>
    <tr><td>BPS-11 to 16</td><td>Stenographer, senior clerk, computer operator, sub-engineer, staff nurse</td><td>Intermediate to diploma or bachelor's</td></tr>
    <tr><td>BPS-17</td><td>The entry officer grade: assistant director, lecturer, section officer</td><td>Bachelor's or master's, usually through a commission test</td></tr>
    <tr><td>BPS-18 to 19</td><td>Deputy director and senior officer roles</td><td>Master's plus years of service</td></tr>
    <tr><td>BPS-20 to 22</td><td>Director general and above</td><td>Seniority and promotion; rarely open to fresh applicants</td></tr>
  </tbody>
</table>

<h2>Why BPS-17 matters</h2>
<p>BPS-17 is the line between staff and officer. Posts from BPS-17 upwards are usually filled through a
public service commission — FPSC for federal, PPSC for Punjab, SPSC for Sindh, KPPSC for Khyber
Pakhtunkhwa, BPSC for Balochistan — or through a departmental test. Expect a written test, sometimes a
screening test first, and then an interview.</p>

<h2>How to read the pay line</h2>
<ul>
  <li><strong>“BPS-14”</strong> — the post is on that scale. Pay is the scale's basic pay plus allowances.</li>
  <li><strong>“BPS-14 plus usual allowances”</strong> — allowances are added on top, as per government rules.</li>
  <li><strong>“Contract” or “consolidated”</strong> — a fixed monthly amount, not the scale, and often no pension.</li>
  <li><strong>“Daily wages”</strong> — paid per day worked, with no benefits.</li>
</ul>

<h2>Age limit, quota and experience</h2>
<p>The advertisement also states the age limit, usually with a general relaxation and separate relaxations
for certain categories and regions. Domicile quota decides how many posts are reserved for each province.
Experience normally has to come from a recognised employer and be supported by a letter — a CV claim
alone is not enough.</p>

<h2>The practical tip</h2>
<p>If two posts look identical but one is BPS-11 and the other BPS-14, the difference is pay, promotion
speed and often the required qualification. Read both advertisements fully before applying.</p>

<p class="updated">Updated 24 October 2026. Pay figures are revised by the government; confirm the current rate in the advertisement.</p>
<div class="next">
  <a href="national-job-portal-guide.html">Apply on NJP &rarr;</a>
  <a href="documents-for-government-job.html">Documents checklist &rarr;</a>
  <a href="../index.html">Browse jobs &rarr;</a>
</div>
""",
    [("What does BPS-14 mean in a job advertisement?",
      "It means the post sits on Basic Pay Scale 14. Pay is that scale's basic pay plus the allowances the "
      "department grants, and promotion follows the rules for that scale."),
     ("Which BPS is officer grade in Pakistan?",
      "BPS-17 is the entry officer grade. Posts from BPS-17 upwards are usually filled through a public "
      "service commission test or a departmental selection process."),
     ("Is a BPS post better than a contract job that pays more?",
      "Not automatically. A scale post usually brings pension, increments and promotion; a contract post can "
      "pay more per month but often has no pension and ends on its end date."),
     ("Does BPS decide the age limit?",
      "No. The age limit is set separately in each advertisement, often with relaxations for particular "
      "categories. Read that line before you apply.")])

page(
    "documents-for-government-job",
    "Documents You Need for a Government Job Application in Pakistan | RozgarJobs",
    "The full checklist for a Pakistani government job: CNIC, domicile, degrees, experience letters, "
    "photographs and attestation — plus what to carry to the test and interview.",
    "Documents checklist",
    """
<h1>Documents you need for a government job</h1>
<p class="lede">Most rejections at the verification stage are not about marks — they are about a missing
document or a name that does not match. Keep this list ready once and every later application gets easier.</p>

<h2>The core set</h2>
<ul>
  <li><strong>CNIC</strong> — front and back, scanned clearly. Your name and your father's name must match
  every certificate you submit.</li>
  <li><strong>Domicile certificate</strong> — issued by the district. Required for provincial quota posts.</li>
  <li><strong>Matric certificate</strong> and, where applicable, intermediate, bachelor's and master's
  certificates plus transcripts.</li>
  <li><strong>Experience letters</strong> from each previous employer, on letterhead, with dates and the job
  title. A CV is not a substitute.</li>
  <li><strong>Photograph</strong> — recent, plain background, in the size the advertisement asks for.</li>
  <li><strong>Character certificate</strong> — some departments ask for one from your last institution or employer.</li>
  <li><strong>Medical certificate</strong> — only where the advertisement requires it.</li>
</ul>

<h2>Attestation</h2>
<p>Many advertisements ask for attested copies rather than originals, and they name who may attest them —
usually a gazetted officer, a head of institution or a notary. Read that line before you pay anyone,
because the accepted authority differs between departments.</p>

<div class="box">
  <p><strong>Names must match.</strong> If your matric certificate spells your name differently from your
  CNIC, fix the discrepancy or attach the affidavit the advertisement allows. This one issue causes a large
  share of verification problems.</p>
</div>

<h2>For the test and interview</h2>
<ul>
  <li>Original documents plus one photocopy set.</li>
  <li>The call letter or admit card, printed.</li>
  <li>Original CNIC — you will not be allowed in without it.</li>
  <li>Two or three extra photographs, and a pen.</li>
</ul>

<h2>How to keep it organised</h2>
<ol>
  <li>Scan everything once at a readable resolution and keep the files in one folder.</li>
  <li>Name the files clearly: cnic-front.pdf, matric-certificate.pdf, experience-abc-company.pdf.</li>
  <li>Keep one set of attested photocopies in a single envelope.</li>
  <li>Note every closing date in a calendar with a reminder two days before.</li>
</ol>

<h2>Never do this</h2>
<p>Never hand original documents to anyone who is not the department itself, never pay a "processing
agent", and never let a stranger keep your CNIC copies. If a listing asks for money or originals before an
interview, <a href="../contact.html">report it to us</a>.</p>

<p class="updated">Updated 24 October 2026. Requirements differ per advertisement — treat that document as the final word.</p>
<div class="next">
  <a href="national-job-portal-guide.html">Apply on NJP &rarr;</a>
  <a href="spot-fake-job-advertisement.html">Spot a fake job ad &rarr;</a>
  <a href="../index.html">Browse jobs &rarr;</a>
</div>
""",
    [("Which documents are compulsory for a government job in Pakistan?",
      "Almost always the CNIC, domicile certificate, educational certificates and transcripts, and "
      "photographs. Experience letters and character certificates are needed when that advertisement asks "
      "for them."),
     ("Do I need attested copies?",
      "Only if the advertisement says so, and it also states who may attest them. That authority differs "
      "between departments, so read that line first."),
     ("What if my name is spelled differently on two documents?",
      "Fix it at the issuing office, or attach the affidavit the advertisement allows. Mismatched names stop "
      "a large number of candidates at verification."),
     ("Should I send original documents?",
      "No. Send copies unless the department specifically asks for originals at the interview stage, and "
      "never give originals to an agent.")])

page(
    "spot-fake-job-advertisement",
    "How to Spot a Fake Job Advertisement in Pakistan | RozgarJobs",
    "Eight warning signs of a fake job offer in Pakistan, the scams doing the rounds, how to check a "
    "listing in two minutes, and what to do if you have already paid or shared documents.",
    "Spot a fake job ad",
    """
<h1>How to spot a fake job advertisement</h1>
<p class="lede">A real employer never asks a candidate for money. That one rule filters out almost every
fake listing — but scammers keep finding new angles, so here is the fuller list.</p>

<h2>The eight warning signs</h2>
<ol>
  <li><strong>They ask for a fee.</strong> Registration, processing, interview, training, seat reservation —
  a genuine employer charges none of these. Government departments collect only the official challan printed
  in the advertisement, paid into a bank, never into someone's personal account.</li>
  <li><strong>The salary is unrealistic</strong> for the work and the experience. “Work from home, earn
  200,000 a month, no experience” is a recruitment scheme, not a job.</li>
  <li><strong>It arrives from a WhatsApp number or a personal Gmail</strong>, not from the company's domain.</li>
  <li><strong>No company details.</strong> No address, no registration number, no website — or a website
  registered last month.</li>
  <li><strong>The interview is a chat.</strong> A real hiring process has a named interviewer and a date.</li>
  <li><strong>They want CNIC copies or bank details</strong> before any interview.</li>
  <li><strong>They push you to decide today.</strong> Urgency is a pressure tactic, not a hiring practice.</li>
  <li><strong>The advertisement is someone else's photocopy</strong> with a phone number pasted over the
  original contact details.</li>
</ol>

<h2>Common scams in Pakistan</h2>
<ul>
  <li><strong>The overseas visa scam</strong> — a Gulf or Europe job that needs a visa fee paid first.</li>
  <li><strong>The “government contact”</strong> — someone with an “inside link” who will get you appointed
  for a payment. No such arrangement exists, and the money is gone.</li>
  <li><strong>The paid leads group</strong> — a WhatsApp or Facebook group charging a monthly fee for job
  leads copied from public sites.</li>
  <li><strong>The fake HR email</strong> — a lookalike domain sending an offer letter and asking for bank
  details for “salary setup”.</li>
</ul>

<h2>How to check a listing in two minutes</h2>
<ol>
  <li>Search the exact job title and employer name. A real vacancy appears in more than one place.</li>
  <li>Open the employer's own website and look for a careers page with the same vacancy.</li>
  <li>For government posts, check the department or public service commission site and the official portal.</li>
  <li>Look at the email domain: a company address is not a free mailbox.</li>
  <li>Search the phone number — numbers used in scams usually show up in complaints.</li>
</ol>

<h2>If you have already paid or shared documents</h2>
<ul>
  <li>Stop all contact and send nothing else.</li>
  <li>Report the number on the platform where the job appeared.</li>
  <li>Report it to the FIA's cybercrime wing, which takes complaints online.</li>
  <li>If you shared bank details, call your bank immediately and block the card or account.</li>
  <li>If you shared CNIC copies, watch for SIMs or accounts opened in your name.</li>
</ul>

<div class="box">
  <p><strong>RozgarJobs never charges candidates.</strong> If a listing on this site asks you for money,
  <a href="../contact.html">tell us</a> and we will remove it.</p>
</div>

<p class="updated">Updated 24 October 2026.</p>
<div class="next">
  <a href="documents-for-government-job.html">Documents checklist &rarr;</a>
  <a href="national-job-portal-guide.html">Apply on NJP &rarr;</a>
  <a href="../index.html">Browse jobs &rarr;</a>
</div>
""",
    [("Do I ever have to pay for a job in Pakistan?",
      "No. A genuine employer does not charge a candidate. Government departments may charge the official "
      "application fee printed in the advertisement, paid by bank challan — never to a person."),
     ("Someone offered me a government job for money. Is it real?",
      "No. Government appointments follow the advertised process and a merit list. Anyone selling an "
      "appointment is committing fraud."),
     ("How do I check whether a company is real?",
      "Open its website and look for an address and a careers page, search the company name with the word "
      "complaint, and check whether the email uses the company's own domain."),
     ("What should I do after paying a fake recruiter?",
      "Stop contact, report the number and the listing, file a complaint with the FIA cybercrime wing, and "
      "call your bank immediately if you shared bank details.")])

# ── guide 5: interview & test ───────────────────────────────────────────────
page(
    "government-test-interview-guide",
    "Government Test and Interview: What to Expect in Pakistan | RozgarJobs",
    "How the written test, the screening test and the interview actually work for FPSC, PPSC and "
    "departmental recruitment in Pakistan — and how to prepare in two weeks.",
    "Test & interview",
    """
<h1>The written test and interview, explained</h1>
<p class="lede">Every government advertisement ends with two words that decide the outcome: written test
and interview. Here is what actually happens at each stage, and how to prepare without buying a course.</p>

<h2>Which test will you sit</h2>
<table class="tbl">
  <tr><th>Recruiting body</th><th>Typical test</th><th>After the test</th></tr>
  <tr><td>FPSC (federal)</td><td>Objective screening test, subject-specific for technical posts</td><td>Viva before the commission</td></tr>
  <tr><td>PPSC (Punjab)</td><td>Written paper at a district centre; separate paper for lecturers</td><td>Interview at the commission</td></tr>
  <tr><td>NTS / PTS / CTS</td><td>One MCQ paper set by the testing service</td><td>Employer's own interview</td></tr>
  <tr><td>Departmental / district posts</td><td>Short written paper or a practical/typing test</td><td>Interview at the office</td></tr>
</table>

<h2>The parts that repeat every year</h2>
<p>Most screening papers share the same skeleton: English (grammar, comprehension, a short paragraph),
general knowledge and Pakistan affairs, basic mathematics, Islamiat or ethics for some posts, and
professional questions for the specific job. Preparing the first four properly covers roughly two-thirds
of the paper for almost every post.</p>

<div class="box">
  <strong>The five things candidates lose marks on</strong>
  <ul>
    <li>Filling the answer sheet incorrectly — the roll number and the bubbles are checked by machine.</li>
    <li>Guessing without a strategy; a wrong answer can carry a negative mark in some papers.</li>
    <li>Running out of time on the maths section instead of banking the easy marks first.</li>
    <li>Not reading the syllabus printed with the advertisement — it tells you the weighting.</li>
    <li>Bringing the wrong documents to the centre and being turned away at the gate.</li>
  </ul>
</div>

<h2>Two weeks of preparation that actually works</h2>
<ol>
  <li><strong>Days 1–2:</strong> read the advertisement and the syllabus line by line. Write down the exact
      subjects and their weight. Anything not in the syllabus is not your problem this month.</li>
  <li><strong>Days 3–8:</strong> one past paper under timed conditions every second day. Between papers,
      revise only the topics you got wrong — not everything.</li>
  <li><strong>Days 9–12:</strong> English and Pakistan affairs daily, 40 minutes each. These two carry the
      most marks across posts.</li>
  <li><strong>Days 13–14:</strong> two full mock papers, then stop. Sleep and logistics beat one more chapter.</li>
</ol>

<h2>The interview</h2>
<p>The viva is short — usually 10 to 20 minutes — and it is not a knowledge test. The panel is checking
whether you understand the post you applied for, whether your documents match what you claimed, and how
you behave under mild pressure. Expect three kinds of question: about your own application (why this post,
what you studied, what you have done), about the department and its work, and one situational question
about a problem you might actually face on the job.</p>
<p>Answer in complete sentences, admit what you do not know, and never argue. If a question is outside your
field, say so and offer what you do know. Panels respond better to a calm "I have not worked on that, but I
would approach it like this" than to a confident wrong answer.</p>

<h2>What to carry</h2>
<ul>
  <li>The printed roll number slip or the call letter — without it you will not be allowed in.</li>
  <li>Original CNIC, plus one photocopy.</li>
  <li>Two or three recent photographs, the same ones used on the form.</li>
  <li>Original degrees and experience letters, for verification at the interview stage.</li>
  <li>A black ballpoint, a pencil, a sharpener and a simple calculator only if the advertisement allows it.</li>
</ul>

<p class="updated">Updated 24 October 2026.</p>
<div class="next">
  <a href="documents-for-government-job.html">Documents checklist &rarr;</a>
  <a href="bps-pay-scales.html">BPS pay scales &rarr;</a>
  <a href="../sarkari-naukri.html">Government jobs &rarr;</a>
</div>
""",
    [("Is there negative marking in government tests?",
      "Some testing services apply it and some do not — it is stated on the roll number slip or the "
      "instruction page. If it is not stated, assume guesses cost nothing but still answer only where you "
      "can eliminate two options."),
     ("Can I take a calculator into the test?",
      "Only if the advertisement or the roll number slip says so. Most objective papers do not allow any "
      "electronic device, and phones are confiscated at the gate."),
     ("How long after the test is the interview?",
      "Usually four to twelve weeks. The result is published on the commission's own website with the roll "
      "numbers of shortlisted candidates, and call letters follow by post or email."),
     ("What if I fail the written test?",
      "You can apply again to the next advertisement for the same post, and there is no limit on attempts. "
      "Your previous result does not affect a new application.")])

# ── guide 6: CV for a government post ───────────────────────────────────────
page(
    "cv-for-government-job",
    "How to Write a CV for a Government Job in Pakistan | RozgarJobs",
    "The format, the order and the exact wording that government recruitment boards in Pakistan expect — "
    "plus the three mistakes that get an otherwise good application rejected.",
    "Government CV",
    """
<h1>How to write a CV for a government job</h1>
<p class="lede">A government shortlisting committee spends about 40 seconds on a CV. It is not looking for
creativity — it is checking whether you meet the advertised criteria, in the order the advertisement lists
them. This is how to make that check easy.</p>

<h2>Use the order the advertisement uses</h2>
<p>Private-sector CVs lead with a personal statement. Government CVs lead with the facts. Use this order:</p>
<ol>
  <li><strong>Name</strong> exactly as on the CNIC, then father's name, CNIC number, date of birth,
      domicile district, postal address, phone and email.</li>
  <li><strong>Post applied for</strong>, with the advertisement number and the closing date. Committees sort
      applications by post; if the post is not obvious on the first page, the file is set aside.</li>
  <li><strong>Academic record</strong> in a table: degree, institution, board or university, year, marks and
      percentage. Start from matric and go upward — the advertisement usually sets a minimum starting point.</li>
  <li><strong>Experience</strong> with dates, employer, designation and a one-line description of duties.
      Overlaps and gaps are noticed, so keep the dates exact.</li>
  <li><strong>Certificates</strong> and computer or language skills, then the document list.</li>
</ol>

<h2>The table that does the work</h2>
<p>Academic marks are the most common filter. Put them in a table so a reader can scan them in one glance:</p>
<table class="tbl">
  <tr><th>Examination</th><th>Institution / Board</th><th>Year</th><th>Marks</th><th>%</th></tr>
  <tr><td>Matric (Science)</td><td>BISE Lahore</td><td>2018</td><td>780 / 1100</td><td>70.9</td></tr>
  <tr><td>Intermediate (Pre-Engineering)</td><td>BISE Lahore</td><td>2020</td><td>760 / 1100</td><td>69.1</td></tr>
  <tr><td>BS Computer Science</td><td>University of the Punjab</td><td>2024</td><td>3.42 / 4.00 CGPA</td><td>—</td></tr>
</table>

<h2>Three mistakes that get a good application rejected</h2>
<ul>
  <li><strong>A name that does not match the CNIC.</strong> Adding "Muhammad" that is not on the card, or
      spelling a father's name differently on the CV and the form, is the single most common rejection.</li>
  <li><strong>Claiming experience you cannot prove.</strong> Every experience line needs a certificate or a
      letter that can be verified. Unverifiable experience during the interview stage removes the
      candidate from the merit list.</li>
  <li><strong>Sending the wrong number of copies.</strong> Advertisements ask for a specific number of
      copies of each document, attested in a specific way. Read that paragraph twice.</li>
</ul>

<div class="box">
  <strong>Formatting rules that matter on paper</strong>
  <ul>
    <li>Two pages maximum, single column, no photographs unless asked.</li>
    <li>Font size 11–12, black text, no colour blocks — many offices still print in black and white.</li>
    <li>Attach copies in the order the advertisement lists them, and write the post name on the envelope.</li>
    <li>Keep a photocopy of the complete application. If the original is lost in the post, the copy is your proof.</li>
  </ul>
</div>

<p class="updated">Updated 24 October 2026.</p>
<div class="next">
  <a href="documents-for-government-job.html">Documents checklist &rarr;</a>
  <a href="government-test-interview-guide.html">Test and interview &rarr;</a>
  <a href="../sarkari-naukri.html">Government jobs &rarr;</a>
</div>
""",
    [("Do government jobs accept a CV by email?",
      "Only if the advertisement says so. Most federal and provincial posts require a prescribed form, "
      "submitted online or by post — a CV alone is not an application."),
     ("Should I write a covering letter?",
      "Yes when the advertisement asks for one, and keep it to three short paragraphs: the post applied "
      "for, how you meet the criteria, and what you have attached."),
     ("Do I need to attest my documents?",
      "Usually yes — by a gazetted officer, or verified through the relevant board or university. The "
      "advertisement states the requirement; do not guess.")])

# ── guides index ────────────────────────────────────────────────────────────
cards = "".join(
    f'<a class="gcard" href="{slug}.html"><strong>{title}</strong><span>{desc}</span></a>'
    for slug, title, desc in GUIDES)

index_body = f"""
<h1>Job search guides for Pakistan</h1>
<p class="lede">Plain-English guides to the confusing parts: the National Job Portal, BPS scales, the
documents every application needs, and how to tell a real vacancy from a scam.</p>
<div class="cards">{cards}</div>

<h2>Why these pages exist</h2>
<p>Most job boards list vacancies and stop there. But a large share of applications fail for reasons that
have nothing to do with the job: a missing domicile copy, a name that does not match the CNIC, a form
submitted a day late, or a fee paid to a person who was never a recruiter. These guides fix that part.</p>

<h2>Coming next</h2>
<ul>
  <li>Provincial quota and domicile, explained</li>
  <li>How to prepare for a computer or typing test</li>
  <li>What a merit list means, and how to read it</li>
</ul>

<p class="updated">Updated 24 October 2026.</p>
<div class="next">
  <a href="../index.html">Browse jobs &rarr;</a>
  <a href="../locations.html">All locations &rarr;</a>
  <a href="../alerts.html">Job alerts &rarr;</a>
</div>
"""

(OUT / "index.html").write_text(
    HEAD.format(title="Job Search Guides for Pakistan — NJP, BPS, Documents | RozgarJobs",
                desc="Short, practical guides for job seekers in Pakistan: applying on the National Job "
                     "Portal, understanding BPS pay scales, the documents checklist and spotting fake ads.",
                slug="index", crumb="Guides", body=STYLE + index_body, jsonld=""),
    encoding="utf-8")

print("wrote", len(GUIDES) + 1, "guide pages")
