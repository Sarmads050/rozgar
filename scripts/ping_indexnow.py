#!/usr/bin/env python3
"""
ping_indexnow.py — naye job pages Bing/Yandex (aur ChatGPT search) ko turant batayein.

Google IndexNow support nahi karta (uske liye Search Console / Indexing API hai),
lekin Bing par naye pages ghanton ke bajaye minute mein index ho jate hain — aur
Bing ka index hi ChatGPT search aur Copilot use karte hain.

Setup (ek dafa, 2 minute)
-------------------------
1. Ek random key banayein, jaise:  python3 -c "import secrets;print(secrets.token_hex(16))"
2. Us key ke naam se site root par ek file rakhein jismein sirf wohi key likhi ho:
      abc123def456.txt   →   abc123def456
3. GitHub → Settings → Secrets → Actions → naya secret: INDEXNOW_KEY = abc123def456

Agar key set na ho to script chup-chaap skip ho jaati hai.
"""
from __future__ import annotations

import json
import pathlib
import re
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE_URL = (os.environ.get("SITE_URL") or "https://rozgar.pk").rstrip("/")
def _key_from_repo():
    """The key file lives in the repo root (it has to be public anyway), so the
    secret is optional — the filename IS the key."""
    root = pathlib.Path(__file__).resolve().parent.parent
    for f in root.glob("*.txt"):
        stem = f.stem
        if re.fullmatch(r"[a-f0-9]{16,64}", stem):
            return stem
    return ""


KEY = (os.environ.get("INDEXNOW_KEY") or _key_from_repo()).strip()
MAX_URLS = 10000


def sitemap_urls() -> list[str]:
    import xml.etree.ElementTree as ET
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    out: list[str] = []
    idx = ROOT / "sitemap.xml"
    if not idx.exists():
        return out
    for loc in ET.parse(idx).getroot().iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
        name = (loc.text or "").rsplit("/", 1)[-1]
        f = ROOT / name
        if not f.exists():
            continue
        try:
            for u in ET.parse(f).getroot().iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
                if u.text:
                    out.append(u.text)
        except ET.ParseError:
            continue
    return out[:MAX_URLS]


def main() -> int:
    if not KEY:
        print("INDEXNOW_KEY set nahi — skip (SETUP_GUIDE.md → Section 10).")
        return 0

    # key file root mein honi chahiye
    (ROOT / f"{KEY}.txt").write_text(KEY, encoding="utf-8")

    urls = sitemap_urls()
    if not urls:
        print("Koi URL nahi mila — pehle site build karein.")
        return 1

    payload = json.dumps({
        "host": SITE_URL.split("://", 1)[-1].split("/")[0],
        "key": KEY,
        "keyLocation": f"{SITE_URL}/{KEY}.txt",
        "urlList": urls,
    }).encode()

    req = urllib.request.Request(
        "https://api.indexnow.org/indexnow", data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"IndexNow: {len(urls)} URLs submitted → HTTP {r.status}")
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"IndexNow fail: {type(e).__name__}: {e}")
        return 0          # deploy kabhi na roke


if __name__ == "__main__":
    sys.exit(main())
