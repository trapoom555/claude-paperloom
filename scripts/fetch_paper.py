#!/usr/bin/env python3
"""Fetch a paper and cache text for downstream agents.

Classifies the input (arxiv id, DOI, URL, local PDF), downloads if remote,
writes:

    <vault>/.sources/<sha>.pdf           (or .html)
    <vault>/.sources/<sha>.txt           full plain text
    <vault>/.sources/<sha>.brief.txt     ~10-25% of the paper, focused

Emits JSON on stdout:

    {
      "source_type": "arxiv" | "doi" | "pdf" | "url",
      "source_url":  "https://...",
      "arxiv_id":    "1706.03762" | null,
      "doi":         "10.xxx/..." | null,
      "sha":         "97fd27...",
      "raw_path":    "/abs/path/to/<sha>.pdf",
      "full_text_path":  ".../<sha>.txt",
      "brief_text_path": ".../<sha>.brief.txt",
      "page_count":  42,
      "skipped_cached": true|false
    }

Usage:
    python3 fetch_paper.py <vault> <input>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

from _lib import require_vault, die


ARXIV_ID_RE = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")
ARXIV_URL_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)
DOI_RE = re.compile(r"^10\.[^\s/]+/[^\s]+$")
DOI_URL_RE = re.compile(r"doi\.org/(10\.[^\s/]+/[^\s]+)", re.IGNORECASE)


def classify(arg: str) -> tuple[str, str, Optional[str], Optional[str]]:
    """Return (source_type, canonical_url_or_path, arxiv_id, doi)."""
    s = arg.strip()

    # Local file.
    p = Path(s).expanduser()
    if p.exists() and p.is_file() and p.suffix.lower() == ".pdf":
        return "pdf", str(p.resolve()), None, None

    # arXiv id.
    if ARXIV_ID_RE.match(s):
        aid = s
        return "arxiv", f"https://arxiv.org/abs/{aid}", aid, None
    m = ARXIV_URL_RE.search(s)
    if m:
        aid = m.group(1)
        return "arxiv", f"https://arxiv.org/abs/{aid}", aid, None

    # DOI.
    if DOI_RE.match(s):
        return "doi", f"https://doi.org/{s}", None, s
    m = DOI_URL_RE.search(s)
    if m:
        doi = m.group(1)
        return "doi", f"https://doi.org/{doi}", None, doi

    # URL fallback.
    if s.startswith(("http://", "https://")):
        return "url", s, None, None

    die(f"could not classify input: {arg!r}")
    return "", "", None, None  # unreachable


def sha256_of(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def arxiv_pdf_url(aid: str) -> str:
    # Strip version suffix for PDF URL; arXiv redirects to latest.
    base = aid.split("v", 1)[0] if "v" in aid else aid
    return f"https://arxiv.org/pdf/{base}.pdf"


def download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "research-librarian/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r, dest.open("wb") as f:
            shutil.copyfileobj(r, f)
    except urllib.error.URLError as e:
        die(f"download failed for {url}: {e}")


def extract_full_text(pdf_path: Path) -> tuple[str, int]:
    import fitz
    doc = fitz.open(pdf_path)
    pages: list[str] = []
    for i, page in enumerate(doc):
        pages.append(f"\n===== PAGE {i+1} =====\n" + page.get_text("text"))
    return "".join(pages), doc.page_count


def extract_brief(pdf_path: Path) -> str:
    """Reference recipe from ingest.md — first 3 pages + last 2 before refs + any
    page whose header mentions conclusion/discussion/summary/takeaways."""
    import fitz
    doc = fitz.open(pdf_path)

    ref_re = re.compile(r"^\s*(references|bibliography)\s*$", re.IGNORECASE | re.MULTILINE)
    ref_cutoff = doc.page_count
    for i in range(doc.page_count):
        if ref_re.search(doc[i].get_text("text")):
            ref_cutoff = i
            break

    keep: set[int] = set(range(min(3, ref_cutoff)))
    keep.update(range(max(0, ref_cutoff - 2), ref_cutoff))
    cue_re = re.compile(r"\b(conclusion|discussion|summary|takeaways?)\b", re.IGNORECASE)
    for i in range(ref_cutoff):
        if cue_re.search(doc[i].get_text("text")[:500]):
            keep.add(i)

    out: list[str] = []
    for i in sorted(keep):
        out.append(f"\n===== PAGE {i+1} =====\n" + doc[i].get_text("text"))
    return "".join(out)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("vault")
    ap.add_argument("input")
    ap.add_argument("--force", action="store_true", help="re-extract even if cached")
    args = ap.parse_args(argv)

    vault = require_vault(args.vault)
    sources = vault / ".sources"
    sources.mkdir(exist_ok=True)

    src_type, src_url, arxiv_id, doi = classify(args.input)

    # Key the cache by the canonical URL (for remote) or absolute file path (for local).
    key = src_url if src_type != "pdf" else src_url  # same — classify() already normalized
    sha = sha256_of(key)
    raw_path = sources / f"{sha}.pdf"
    txt_path = sources / f"{sha}.txt"
    brief_path = sources / f"{sha}.brief.txt"

    skipped_cached = False
    if raw_path.exists() and txt_path.exists() and brief_path.exists() and not args.force:
        skipped_cached = True
    else:
        if src_type == "pdf":
            shutil.copy2(Path(src_url), raw_path)
        elif src_type == "arxiv":
            download(arxiv_pdf_url(arxiv_id or ""), raw_path)
        else:
            # Generic URL / DOI — follow redirects; content may be HTML or PDF.
            download(src_url, raw_path)

    page_count = 0
    if not skipped_cached:
        # Detect PDF by magic bytes; if it's HTML (common for DOI landings),
        # fall back to writing the HTML verbatim as .txt and copying to .brief.txt.
        head = raw_path.read_bytes()[:5]
        if head.startswith(b"%PDF"):
            full, page_count = extract_full_text(raw_path)
            txt_path.write_text(full, encoding="utf-8")
            brief = extract_brief(raw_path)
            brief_path.write_text(brief, encoding="utf-8")
        else:
            # HTML / text fallback. Rename to .html for clarity.
            html_path = sources / f"{sha}.html"
            raw_path.rename(html_path)
            raw_path = html_path
            text = html_path.read_text(encoding="utf-8", errors="replace")
            # Strip tags crudely — downstream agents tolerate noise.
            stripped = re.sub(r"<script.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
            stripped = re.sub(r"<style.*?</style>", "", stripped, flags=re.DOTALL | re.IGNORECASE)
            stripped = re.sub(r"<[^>]+>", " ", stripped)
            stripped = re.sub(r"\s+", " ", stripped).strip()
            txt_path.write_text(stripped, encoding="utf-8")
            brief_path.write_text(stripped, encoding="utf-8")

    out = {
        "source_type": src_type,
        "source_url": src_url,
        "arxiv_id": arxiv_id,
        "doi": doi,
        "sha": sha,
        "raw_path": str(raw_path),
        "full_text_path": str(txt_path),
        "brief_text_path": str(brief_path),
        "page_count": page_count,
        "skipped_cached": skipped_cached,
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
