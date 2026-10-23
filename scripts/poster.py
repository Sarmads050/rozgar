#!/usr/bin/env python3
"""
Rozgar — job poster generator (v2)
==================================
Every listing gets its own designed poster, generated from the structured facts
we extracted. We never copy another site's ad creative.

What's new in v2
----------------
• 6 colour palettes (auto-picked from the job, so the feed looks varied)
• 2 layouts — "light" (paper style) and "bold" (dark card style)
• Real brand mark drawn on the canvas (no external logo file needed)
• Clearer hierarchy: badge → title → employer → fact grid → deadline → apply
• Long text is measured and shrunk instead of overflowing
• Posters never render text under the QR code

Output
------
posters/<slug>.jpg     1080 × 1350  (WhatsApp / Instagram portrait)
posters/<slug>-og.jpg  1200 ×  630  (social / Open Graph preview)
"""

import hashlib
import os
import re
from datetime import date, datetime

import qrcode
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(os.path.dirname(HERE), "assets", "fonts")

# ── palettes ────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════
#  THEMES — har theme mein 6 palettes + dark backgrounds
#
#  POSTER_THEME env var se switch karein:  navy (default) | noir | maroon
#  Sector → palette mapping neeche SECTOR_PALETTE mein hai.
# ══════════════════════════════════════════════════════════════════════════
_THEMES = {
    # ── A: deep navy + gold — official, premium, newspaper-clean
    "navy": {
        "palettes": {
            "emerald": dict(accent="#12305A", accent2="#3C7DD9", soft="#EEF3FA", ink="#0A1B33", badge="#0C2140"),
            "royal":   dict(accent="#1F2E8A", accent2="#5B7CFA", soft="#EEF1FD", ink="#0B1433", badge="#16226B"),
            "crimson": dict(accent="#9A1B3D", accent2="#E2557C", soft="#FDF1F4", ink="#3A0716", badge="#77122C"),
            "amber":   dict(accent="#8A6512", accent2="#D9A928", soft="#FCF7E7", ink="#2E2204", badge="#6A4C0B"),
            "violet":  dict(accent="#43267F", accent2="#8C6BE8", soft="#F4F1FD", ink="#180D35", badge="#331E63"),
            "teal":    dict(accent="#0A5C6B", accent2="#2AB5C8", soft="#EAF8FA", ink="#03303A", badge="#074954"),
        },
        "dark": {"emerald": "#071A33", "royal": "#060F2B", "crimson": "#2A0712",
                 "amber": "#211705", "violet": "#120A28", "teal": "#032A32"},
    },
    # ── B: graphite + neon — modern tech, strong contrast
    "noir": {
        "palettes": {
            "emerald": dict(accent="#1F2937", accent2="#60A5FA", soft="#F3F4F6", ink="#0B1220", badge="#111827"),
            "royal":   dict(accent="#0F172A", accent2="#38BDF8", soft="#F1F5F9", ink="#080E1C", badge="#0B1220"),
            "crimson": dict(accent="#7F1D1D", accent2="#F87171", soft="#FEF2F2", ink="#2A0808", badge="#5C1414"),
            "amber":   dict(accent="#78350F", accent2="#FBBF24", soft="#FFFBEB", ink="#2C1A05", badge="#5A270B"),
            "violet":  dict(accent="#312E81", accent2="#A78BFA", soft="#F5F3FF", ink="#15133F", badge="#252262"),
            "teal":    dict(accent="#134E4A", accent2="#2DD4BF", soft="#F0FDFA", ink="#042F2C", badge="#0D3B38"),
        },
        "dark": {"emerald": "#0B1220", "royal": "#060B18", "crimson": "#240606",
                 "amber": "#1F1404", "violet": "#110F33", "teal": "#04211F"},
    },
    # ── C: maroon + cream — warm, traditional, "newspaper of jobs"
    "maroon": {
        "palettes": {
            "emerald": dict(accent="#6B1220", accent2="#C99A2E", soft="#FAF3EC", ink="#320812", badge="#520E19"),
            "royal":   dict(accent="#1F3B57", accent2="#4C86B8", soft="#EFF4F8", ink="#0B1A28", badge="#172D43"),
            "crimson": dict(accent="#8E1F4B", accent2="#D9558A", soft="#FCF1F5", ink="#360818", badge="#6D1739"),
            "amber":   dict(accent="#8A5A12", accent2="#D9A33A", soft="#FBF5E8", ink="#2E1D04", badge="#6A440D"),
            "violet":  dict(accent="#4A2A6B", accent2="#9B72CF", soft="#F6F2FB", ink="#1C0F2B", badge="#38214F"),
            "teal":    dict(accent="#14524B", accent2="#38A79A", soft="#EDF8F6", ink="#04302B", badge="#0E3D38"),
        },
        "dark": {"emerald": "#2A0710", "royal": "#08192B", "crimson": "#260613",
                 "amber": "#221703", "violet": "#160B26", "teal": "#052621"},
    },
}

THEME = (os.environ.get("POSTER_THEME") or "navy").strip().lower()
_ACTIVE = _THEMES.get(THEME, _THEMES["navy"])
PALETTES = _ACTIVE["palettes"]
DARK_BG = _ACTIVE["dark"]

SECTOR_PALETTE = {
    "government": "emerald",     # theme ka main colour
    "private": "royal",
    "remote": "violet",
    "internship": "crimson",
    "contract": "amber",
}

THEME_NAMES = {"navy": "Navy + Gold", "noir": "Graphite + Neon", "maroon": "Maroon + Cream"}


# ── tiny helpers ────────────────────────────────────────────────────────────
def _font_file(weight):
    for name in (f"Inter-{weight}.ttf", "Inter-700.ttf", "Inter-400.ttf"):
        p = os.path.join(FONT_DIR, name)
        if os.path.exists(p):
            return p
    return None


def F(size, weight="700"):
    p = _font_file(weight)
    if p:
        return ImageFont.truetype(p, size)
    for name in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default(size)


def hexc(c):
    if isinstance(c, (tuple, list)):
        return tuple(int(v) for v in c[:3])
    c = str(c).lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def mix(c1, c2, k):
    a, b = hexc(c1), hexc(c2)
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


def gradient(w, h, top, bottom):
    col = Image.new("RGB", (1, h))
    for y in range(h):
        col.putpixel((0, y), mix(top, bottom, y / max(1, h - 1)))
    return col.resize((w, h))


def wrap(d, text, font, max_w, max_lines=3, ellipsis=True):
    words = str(text or "").split()
    if not words:
        return []
    lines, cur = [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if d.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if ellipsis and len(" ".join(lines)) < len(" ".join(words)):
        last = lines[-1]
        while last and d.textlength(last + "…", font=font) > max_w:
            last = last[:-1]
        lines[-1] = last.rstrip(" ,.;:-") + "…"
    return lines


def fit(d, text, size, weight, max_w, min_size=14):
    while size > min_size:
        f = F(size, weight)
        if d.textlength(text, font=f) <= max_w:
            return f
        size -= 2
    return F(min_size, weight)


AGE_RE = re.compile(r"(\d{1,2})\s*(?:-|–|—|to|se)\s*(\d{1,2})")


def clean_age(v):
    """Scraped age text often is garbage — sirf asli range rakhein."""
    t = str(v or "").strip()
    if not t:
        return ""
    m = AGE_RE.search(t)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        if 10 <= lo < hi <= 70:
            return f"{lo}–{hi} years"
    m = re.search(r"(?:max(?:imum)?|upto|up to)\D{0,12}(\d{1,2})", t, re.I)
    if m and 10 <= int(m.group(1)) <= 70:
        return f"Up to {int(m.group(1))} years"
    return "" if re.search(r"applicant|looking|candidate|apply|click", t, re.I) else t[:22]


INSTRUCTION_WORDS = ("apply", "send", "submit", "visit", "email", "e-mail", "form",
                     "deposit", "dispatch", "post ", "courier", "online", "upload",
                     "registration", "register", "contact", "walk-in", "whatsapp")


def clean_how(v, source="", limit=230):
    """HOW TO APPLY — scraped body text ko instruction mein badlein."""
    t = re.sub(r"\s+", " ", str(v or "")).strip()
    t = re.sub(r"\s*(tap this page|click here|read more|open the link)\b.*$", "", t,
               flags=re.I).strip(" .")
    low = t.lower()
    instructional = any(k in low for k in INSTRUCTION_WORDS)

    # job board ka generic paragraph — asli instruction nahi hota
    if not t or not instructional or len(t) < 40 or t.endswith(("then", "and", "or", "to", "for")):
        src = (source or "the original ad").replace(".pk", ".pk")
        return (f"Apply online on {src} — QR scan karein ya job page kholein. "
                f"Poora advertisement, documents ki list aur fee ki tafseel wahan hai.")

    if len(t) > limit:
        cut = t[:limit].rsplit(" ", 1)[0].rstrip(" ,.;")
        t = cut + "…"
    return t


def short_url(u, limit=44):
    t = re.sub(r"^https?://(www\.)?", "", str(u or "").strip())
    t = t.split("?")[0].rstrip("/")
    if len(t) > limit:
        head = t.split("/")[0]
        tail = t.split("/")[-1][:max(6, limit - len(head) - 4)]
        t = f"{head}/…/{tail}"
    return t


def days_left(job):
    ld = job.get("last_date")
    if not ld:
        return None
    for fmt in ("%Y-%m-%d", "%d %b %Y", "%d-%m-%Y", "%d %B %Y"):
        try:
            return (datetime.strptime(ld, fmt).date() - date.today()).days
        except Exception:
            continue
    return None


def pretty_date(ld):
    if not ld:
        return "Open till filled"
    for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(ld, fmt).strftime("%d %b %Y")
        except Exception:
            pass
    return str(ld)


def pick_style(job):
    """Palette + layout are stable per job, but varied across jobs."""
    sector = (job.get("sector") or "").lower()
    jtype = (job.get("type") or "").lower()
    if "intern" in jtype:
        base = "crimson"
    elif sector in SECTOR_PALETTE:
        base = SECTOR_PALETTE[sector]
    elif job.get("remote"):
        base = "violet"
    elif jtype.startswith("contract"):
        base = "amber"
    else:
        base = "royal"

    key = (job.get("slug") or job.get("title") or "x").encode()
    h = int(hashlib.sha1(key).hexdigest()[:8], 16)
    # 60% keep the sector colour, 40% rotate to a neighbour for variety
    order = list(PALETTES)
    if h % 10 < 4:
        base = order[(order.index(base) + 1 + (h % 3)) % len(order)]
    layout = "dark" if h % 2 else "light"
    return PALETTES[base], layout, base


def qr_img(data, px):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=1)
    qr.add_data(data)
    qr.make(fit=True)
    im = qr.make_image(fill_color="#0b1114", back_color="white").convert("RGB")
    return im.resize((px, px), Image.LANCZOS)


def brand_mark(img, d, x, y, size, fg, bg):
    """Small rounded-square 'R' mark — drawn, not loaded from a file."""
    d.rounded_rectangle([x, y, x + size, y + size], radius=int(size * 0.28), fill=bg)
    f = F(int(size * 0.58), "900")
    tw = d.textlength("R", font=f)
    d.text((x + (size - tw) / 2, y + size * 0.17), "R", font=f, fill=fg)


def fact_grid(d, img, x, y, w, rows, fg, label, line, row_h=92):
    """2-column fact grid with hairlines. Returns the new y."""
    col_w = (w - 36) // 2
    for i, (k, v) in enumerate(rows):
        col, row = i % 2, i // 2
        cx = x + col * (col_w + 36)
        cy = y + row * row_h
        d.text((cx, cy), k.upper(), font=F(16, "800"), fill=label)
        val = str(v)
        vf = fit(d, val, 29, "700", col_w)
        d.text((cx, cy + 26), val[:52], font=vf, fill=fg)
        d.line([cx, cy + row_h - 18, cx + col_w, cy + row_h - 18], fill=line, width=2)
    return y + ((len(rows) + 1) // 2) * row_h


# ══════════════════════════════════════════════════════════════════════════
#  PORTRAIT POSTER — 1080 × 1350
# ══════════════════════════════════════════════════════════════════════════
def render_poster(job, out_path, site_url="", source_line=""):
    W, H = 1080, 1350
    M = 64
    pal, layout, pname = pick_style(job)
    accent, accent2, soft, ink, badge = (pal["accent"], pal["accent2"], pal["soft"],
                                         pal["ink"], pal["badge"])

    if layout == "light":
        bg_top, bg_bottom = "#ffffff", soft
    else:
        bg_top, bg_bottom = DARK_BG[pname], mix(accent, "#000000", 0.55)

    img = gradient(W, H, bg_top, bg_bottom).convert("RGB")

    # accent block on the right edge (a modern "spine")
    spine = Image.new("RGB", (W, H), bg_top)
    sd = ImageDraw.Draw(spine)
    sd.rectangle([W - 26, 0, W, H], fill=accent)
    sd.ellipse([W - 520, -300, W + 120, 300], fill=accent2)
    spine = spine.filter(ImageFilter.GaussianBlur(120))
    img = Image.blend(img, spine, 0.16 if layout == "light" else 0.34)

    d = ImageDraw.Draw(img)
    on_dark = layout == "dark"
    text_main = "#ffffff" if on_dark else ink
    text_mut = "#c8d6d2" if on_dark else "#5c6b70"
    line_col = mix(accent, "#ffffff" if on_dark else accent, 0.7) if on_dark else "#e3e8e6"

    # ── header
    brand_mark(img, d, M, 52, 56, fg="#ffffff", bg=accent)
    d.text((M + 72, 54), "ROZGAR", font=F(32, "900"), fill=text_main)
    d.text((M + 72, 92), "Pakistan Jobs Portal", font=F(18, "600"), fill=text_mut)

    label = {"government": "GOVERNMENT JOB", "private": "PRIVATE SECTOR",
             "remote": "REMOTE JOB", "internship": "INTERNSHIP",
             "contract": "CONTRACT"}.get((job.get("sector") or "").lower(),
                                         "JOB OPPORTUNITY")
    bf = F(18, "900")
    bw = d.textlength(label, font=bf)
    d.rounded_rectangle([W - M - bw - 44, 56, W - M, 104], radius=24, fill=accent)
    d.text((W - M - bw - 22, 69), label, font=bf, fill="#ffffff")

    # ── title
    y = 176
    title = (job.get("title") or "Job Opportunity").strip()
    size = 64
    tf = F(size, "800")
    lines = wrap(d, title, tf, W - M * 2 - 30, max_lines=3)
    while len(lines) == 3 and size > 42 and len(" ".join(lines).split()) < len(title.split()):
        size -= 6
        tf = F(size, "800")
        lines = wrap(d, title, tf, W - M * 2 - 30, max_lines=3)
    for ln in lines:
        d.text((M, y), ln, font=tf, fill=text_main)
        y += int(size * 1.14)

    # ── employer
    employer = (job.get("employer_display") or job.get("company") or "").strip()
    if employer:
        ef = fit(d, employer, 29, "600", W - M * 2 - 30)
        for ln in wrap(d, employer, ef, W - M * 2 - 30, max_lines=2):
            d.text((M, y + 8), ln, font=ef, fill=accent if not on_dark else accent2)
            y += 36
    y += 20

    # ── chips
    chips = [job.get("location"), (f"{job['vacancies']} post" + ("s" if str(job.get('vacancies')) != "1" else ""))
             if job.get("vacancies") else "", job.get("bps"), job.get("type")]
    chips = [c for c in chips if c][:4]
    cf = F(20, "700")
    cx = M
    for c in chips:
        w = d.textlength(str(c), font=cf)
        hh = 44
        d.rounded_rectangle([cx, y, cx + w + 54, y + hh], radius=hh // 2,
                            fill=mix(accent, "#ffffff", 0.86) if not on_dark else mix(accent, "#ffffff", 0.16))
        d.ellipse([cx + 18, y + hh / 2 - 4, cx + 26, y + hh / 2 + 4], fill=accent)
        d.text((cx + 38, y + 11), str(c), font=cf,
               fill=ink if not on_dark else "#eaf5f2")
        cx += w + 54 + 10
        if cx > W - M - 40:
            break
    y += 70

    # ── fact grid
    rows = [(k, v) for k, v in [
        ("Qualification", job.get("qualification")),
        ("Experience", job.get("experience") or "Not specified"),
        ("Age limit", clean_age(job.get("age_limit"))),
        ("Vacancies", job.get("vacancies")),
        ("Salary", job.get("salary_text") or job.get("salary")),
        ("Location", job.get("location")),
        ("Job type", job.get("type")),
    ] if v][:6]

    # ── work out the tail block heights first, then stretch the grid to fill
    how = clean_how(job.get("how_to_apply") or "", job.get("source") or "")
    link = (job.get("apply_url") or job.get("url") or "").strip()
    if not link.startswith(("http://", "https://")):
        link = ""                      # QR sirf tab jab asli link ho
    QR = 150 if link else 0
    TEXT_W = W - M * 2 - QR - (90 if link else 56)
    how_lines = wrap(d, how, F(21, "500"), TEXT_W, max_lines=5) if how else []
    apply_h = max(196, 96 + max(1, len(how_lines)) * 32 + (34 if link else 0))

    BOTTOM = H - 118                      # last pixel the content may use
    nrow = max(1, (len(rows) + 1) // 2)
    bh, G = 112, 24                       # deadline banner height, base gap
    nblocks = 3 if rows else 2

    # 1) grid rows stretch first (dead space ko content mein le jate hain)
    row_h = 92
    if rows:
        room = BOTTOM - y - (84 + G) - bh - G - apply_h - G
        row_h = max(88, min(122, room / nrow))
    box_h = 84 + nrow * row_h if rows else 0

    # 2) jo bacha ho woh teen gaps mein barabar baant dein
    free = BOTTOM - y - box_h - bh - apply_h - G * nblocks
    gap = G + max(0, min(44, free / nblocks))

    if rows:
        d.rounded_rectangle([M, y, W - M, y + box_h], radius=26,
                            fill=mix(accent, "#ffffff", 0.94) if not on_dark else mix(accent, "#000000", 0.62),
                            outline=line_col, width=2)
        d.text((M + 30, y + 24), "JOB DETAILS", font=F(17, "900"),
               fill=accent if not on_dark else accent2)
        fact_grid(d, img, M + 30, y + 62, W - M * 2 - 60, rows,
                  text_main if on_dark else ink,
                  accent if not on_dark else accent2,
                  line_col, row_h=row_h)
        y += box_h + gap

    # ── deadline banner
    dl = days_left(job)
    d.rounded_rectangle([M, y, W - M, y + bh], radius=24, fill=accent)
    d.text((M + 30, y + 20), "LAST DATE TO APPLY", font=F(17, "900"),
           fill=mix(accent, "#ffffff", 0.72))
    d.text((M + 30, y + 46), pretty_date(job.get("last_date")), font=F(42, "900"), fill="#ffffff")
    if dl is not None:
        msg = f"{dl} days left" if dl > 1 else ("Last day!" if dl >= 0 else "Expired")
        f2 = F(24, "900")
        w2 = d.textlength(msg, font=f2)
        d.rounded_rectangle([W - M - w2 - 56, y + 34, W - M - 26, y + 34 + 46],
                            radius=23, fill=mix(accent, "#000000", 0.34))
        d.text((W - M - w2 - 41, y + 44), msg, font=f2, fill="#ffffff")
    y += bh + gap

    # ── how to apply + QR
    d.rounded_rectangle([M, y, W - M, y + apply_h], radius=24,
                        fill=mix(accent, "#ffffff", 0.945) if not on_dark else mix(accent, "#000000", 0.55),
                        outline=line_col, width=2)
    d.text((M + 28, y + 22), "HOW TO APPLY", font=F(17, "900"),
           fill=accent if not on_dark else accent2)
    ty = y + 56
    if how_lines:
        for ln in how_lines:
            d.text((M + 28, ty), ln, font=F(21, "500"),
                   fill="#26312f" if not on_dark else "#dbeae6")
            ty += 32
    else:
        d.text((M + 28, ty), "Open the job page for the full application",
               font=F(21, "500"), fill="#26312f" if not on_dark else "#dbeae6")
        d.text((M + 28, ty + 32), "procedure and required documents.",
               font=F(21, "500"), fill="#26312f" if not on_dark else "#dbeae6")

    if link:
        lf = F(17, "600")
        d.text((M + 28, y + apply_h - 42), short_url(link, 58), font=lf,
               fill=accent if not on_dark else accent2)
        qx, qy = int(W - M - QR - 26), int(y + (apply_h - QR) // 2)
        d.rounded_rectangle([qx - 8, qy - 8, qx + QR + 8, qy + QR + 8], radius=16, fill="#ffffff")
        try:
            img.paste(qr_img(link, QR), (qx, qy))
        except Exception as e:  # noqa: BLE001
            print(f"  ! qr: {type(e).__name__}: {e}")
            d.rounded_rectangle([qx - 8, qy - 8, qx + QR + 8, qy + QR + 8], radius=16,
                                fill=mix(accent, "#ffffff", 0.9))
    y += apply_h + 22

    # ── footer
    d.line([M, H - 92, W - M - 40, H - 92], fill=line_col, width=2)
    d.text((M, H - 74), "Full details, documents & apply link:", font=F(18, "600"), fill=text_mut)
    d.text((M, H - 46), (site_url or "rozgar.pk"), font=F(23, "900"), fill=text_main)
    if source_line:
        sf = fit(d, source_line, 16, "600", 360)
        sw = d.textlength(source_line, font=sf)
        d.text((W - M - 40 - sw, H - 42), source_line, font=sf, fill=text_mut)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, "JPEG", quality=88, optimize=True, progressive=True)
    return out_path


# ══════════════════════════════════════════════════════════════════════════
#  OG IMAGE — 1200 × 630
# ══════════════════════════════════════════════════════════════════════════
def render_og(job, out_path, site_url=""):
    W, H = 1200, 630
    M = 60
    pal, layout, pname = pick_style(job)
    accent, accent2, ink = pal["accent"], pal["accent2"], pal["ink"]
    on_dark = layout == "dark"

    img = gradient(W, H, "#ffffff" if not on_dark else DARK_BG[pname], pal["soft"]).convert("RGB")
    glow = Image.new("RGB", (W, H), accent)
    gd = ImageDraw.Draw(glow)
    gd.ellipse([W - 460, -260, W + 140, 340], fill=accent2)
    glow = glow.filter(ImageFilter.GaussianBlur(160))
    img = Image.blend(img, glow, 0.18 if not on_dark else 0.34)
    d = ImageDraw.Draw(img)

    text_main = "#ffffff" if on_dark else ink
    text_mut = "#c8d6d2" if on_dark else "#5c6b70"

    brand_mark(img, d, M, 44, 44, fg="#ffffff", bg=accent)
    d.text((M + 58, 46), "ROZGAR", font=F(26, "900"), fill=text_main)
    d.text((M + 58, 76), "Pakistan Jobs Portal", font=F(15, "600"), fill=text_mut)

    label = {"government": "GOVERNMENT JOB", "private": "PRIVATE SECTOR",
             "remote": "REMOTE JOB", "internship": "INTERNSHIP",
             "contract": "CONTRACT"}.get((job.get("sector") or "").lower(), "JOB")
    bf = F(15, "900")
    bw = d.textlength(label, font=bf)
    d.rounded_rectangle([W - M - bw - 36, 46, W - M, 88], radius=21, fill=accent)
    d.text((W - M - bw - 18, 58), label, font=bf, fill="#ffffff")

    tf = F(48, "800")
    lines = wrap(d, job.get("title", ""), tf, W - M * 2 - 200, max_lines=3)
    y = 152
    for ln in lines:
        d.text((M, y), ln, font=tf, fill=text_main)
        y += 56

    emp = (job.get("employer_display") or job.get("company") or "")[:70]
    if emp:
        d.text((M, y + 6), emp, font=fit(d, emp, 25, "600", W - M * 2 - 200),
               fill=accent if not on_dark else accent2)
    y += 56

    cf = F(18, "700")
    cx = M
    for c in [job.get("location"), job.get("type"), job.get("qualification")]:
        if not c:
            continue
        w = d.textlength(c, font=cf)
        hh = 40
        d.rounded_rectangle([cx, y, cx + w + 46, y + hh], radius=hh // 2,
                            fill=mix(accent, "#ffffff", 0.86) if not on_dark else mix(accent, "#ffffff", 0.18))
        d.text((cx + 18, y + 10), c, font=cf, fill=ink if not on_dark else "#eaf5f2")
        cx += w + 46 + 10

    dl = days_left(job)
    d.rounded_rectangle([M, H - 130, M + 460, H - 50], radius=18, fill=accent)
    d.text((M + 22, H - 118), "LAST DATE", font=F(14, "900"), fill=mix(accent, "#ffffff", 0.72))
    d.text((M + 22, H - 98), pretty_date(job.get("last_date")), font=F(30, "900"), fill="#ffffff")
    if dl is not None:
        d.text((M + 300, H - 92), f"{dl}d left" if dl >= 0 else "expired",
               font=F(19, "900"), fill="#ffffff")

    link = job.get("apply_url") or site_url
    if link:
        qs = 120
        d.rounded_rectangle([W - M - qs - 10, H - qs - 58, W - M + 6, H - 38], radius=14, fill="#ffffff")
        try:
            img.paste(qr_img(link, qs), (W - M - qs, H - qs - 48))
        except Exception:
            pass
    d.text((M + 486, H - 96), (site_url or "")[:58], font=F(17, "700"), fill=text_mut)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, "JPEG", quality=86, optimize=True, progressive=True)
    return out_path
