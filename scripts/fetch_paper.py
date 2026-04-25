#!/usr/bin/env python3
"""Fetch a paper and cache text for downstream agents.

Classifies the input (arxiv id, DOI, URL, local PDF), downloads if remote,
writes:

    <vault>/.sources/<sha>.pdf           (or .html)
    <vault>/.sources/<sha>.txt           full plain text (for citation_match; not sent to any LLM)
    <vault>/.sources/<sha>.brief.txt     abstract + intro + conclusion (for lite-drafter)
    <vault>/.sources/<sha>.findings.txt  abstract + intro + method + results + conclusion (for finding-extractor)
    <vault>/.sources/<sha>.meta.txt      first 2 pages only (for metadata-extractor)

All three agent-facing slices are passed through compact() — numeric citations
like [1], [2,3], [4-6] are stripped (no semantic value for drafting/extraction)
and whitespace is collapsed.

If the paper is already in the vault (matched by arxiv-id, doi, or
source-url), short-circuits and emits:

    {
      "already_exists": true,
      "existing": { "slug": "...", "title": "...", ... },
      "source_type": ..., "source_url": ..., "arxiv_id": ..., "doi": ...
    }

Otherwise emits JSON on stdout:

    {
      "source_type": "arxiv" | "doi" | "pdf" | "url",
      "source_url":  "https://...",
      "arxiv_id":    "1706.03762" | null,
      "doi":         "10.xxx/..." | null,
      "sha":         "97fd27...",
      "raw_path":    "/abs/path/to/<sha>.pdf",
      "full_text_path":     ".../<sha>.txt",
      "brief_text_path":    ".../<sha>.brief.txt",
      "findings_text_path": ".../<sha>.findings.txt",
      "meta_text_path":     ".../<sha>.meta.txt",
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
from typing import Any, Optional

from _lib import require_vault, die, iter_vault_files, read_frontmatter, slug_from_path


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
    req = urllib.request.Request(url, headers={"User-Agent": "paperloom/0.1"})
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


BRIEF_CUES = re.compile(
    r"\b(conclusion|discussion|summary|takeaways?)\b",
    re.IGNORECASE,
)

FINDINGS_CUES = re.compile(
    r"\b(method|methodology|approach|"
    r"experiment|experimental|evaluation|"
    r"result|ablation|analysis|"
    r"conclusion|discussion|summary|takeaways?)\b",
    re.IGNORECASE,
)


_REF_HEADING_RE = re.compile(r"^\s*(references|bibliography)\s*$", re.IGNORECASE)


def _find_ref_cutoff(doc) -> int:
    """0-indexed page where the bibliography starts (or doc.page_count if none)."""
    ref_re = re.compile(r"^\s*(references|bibliography)\s*$", re.IGNORECASE | re.MULTILINE)
    for i in range(doc.page_count):
        if ref_re.search(doc[i].get_text("text")):
            return i
    return doc.page_count


def _toc_matches(doc, cue_re: re.Pattern, ref_cutoff: int) -> set[int]:
    """Use the PDF outline to find sections whose title matches cue_re, and
    return all pages spanning each match up to the next sibling heading.

    Returns an empty set if the PDF has no TOC or no matching entries.
    """
    toc = doc.get_toc()  # [[level, title, page_1idx], ...]
    if not toc:
        return set()

    keep: set[int] = set()
    for idx, entry in enumerate(toc):
        level, title, page = entry[0], entry[1], entry[2]
        if not cue_re.search(title):
            continue
        start = max(0, page - 1)
        # End at the next TOC entry at the same or shallower level.
        end = ref_cutoff
        for next_entry in toc[idx + 1:]:
            next_level, _, next_page = next_entry[0], next_entry[1], next_entry[2]
            if next_level <= level:
                # Include the page where the next section starts — our section
                # likely spills into the top of it.
                end = min(ref_cutoff, next_page)
                break
        keep.update(range(start, min(end, ref_cutoff)))
    return keep


def _font_matches(doc, cue_re: re.Pattern, ref_cutoff: int) -> set[int]:
    """Detect headings by font size, then keep page ranges spanned by any
    heading whose text matches cue_re.

    Body size is the most-common span size weighted by character count.
    Heading threshold is 1.1× body size.
    """
    import collections

    size_weights: collections.Counter = collections.Counter()
    for i in range(min(doc.page_count, ref_cutoff + 2)):
        try:
            blocks = doc[i].get_text("dict").get("blocks", [])
        except Exception:
            continue
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    size_weights[round(span.get("size", 0), 1)] += len(span.get("text", ""))
    if not size_weights:
        return set()
    body_size = size_weights.most_common(1)[0][0]
    threshold = body_size * 1.1

    # Collect (page_idx, y, text) for every heading-sized line on in-scope pages.
    headings: list[tuple[int, float, str]] = []
    for i in range(ref_cutoff):
        try:
            blocks = doc[i].get_text("dict").get("blocks", [])
        except Exception:
            continue
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                # A line is a heading if its *dominant* span size exceeds the threshold.
                if max(s.get("size", 0) for s in spans) < threshold:
                    continue
                text = "".join(s.get("text", "") for s in spans).strip()
                if not text or len(text) > 120:
                    continue
                bbox = line.get("bbox") or (0, 0, 0, 0)
                headings.append((i, bbox[1], text))

    if not headings:
        return set()

    headings.sort(key=lambda h: (h[0], h[1]))

    keep: set[int] = set()
    for idx, (page, _y, text) in enumerate(headings):
        if not cue_re.search(text):
            continue
        end = ref_cutoff
        if idx + 1 < len(headings):
            # Include the page where the next heading appears (spillover).
            end = min(ref_cutoff, headings[idx + 1][0] + 1)
        keep.update(range(page, end))
    return keep


def _page_header_matches(doc, cue_re: re.Pattern, ref_cutoff: int) -> set[int]:
    """Last-resort heuristic: keep any page whose first 500 chars match cue_re."""
    keep: set[int] = set()
    for i in range(ref_cutoff):
        if cue_re.search(doc[i].get_text("text")[:500]):
            keep.add(i)
    return keep


def _extract_with_cues(pdf_path: Path, cue_re: re.Pattern) -> str:
    """Abstract/intro (first 3 pages) + last 2 pre-ref pages + sections matching
    cue_re. Detection priority: PDF outline → font-size heading detection →
    page-header regex fallback. The first two are unioned; the fallback only
    fires if neither produced any matches."""
    import fitz
    doc = fitz.open(pdf_path)

    ref_cutoff = _find_ref_cutoff(doc)
    mandatory: set[int] = set(range(min(3, ref_cutoff)))
    mandatory.update(range(max(0, ref_cutoff - 2), ref_cutoff))

    matched = _toc_matches(doc, cue_re, ref_cutoff) | _font_matches(doc, cue_re, ref_cutoff)
    if not matched:
        matched = _page_header_matches(doc, cue_re, ref_cutoff)

    keep = mandatory | matched
    out: list[str] = []
    for i in sorted(keep):
        out.append(f"\n===== PAGE {i+1} =====\n" + doc[i].get_text("text"))
    return "".join(out)


def extract_brief(pdf_path: Path) -> str:
    return _extract_with_cues(pdf_path, BRIEF_CUES)


def extract_findings_slice(pdf_path: Path) -> str:
    return _extract_with_cues(pdf_path, FINDINGS_CUES)


def extract_meta_slice(pdf_path: Path) -> str:
    """First 2 pages — enough for title, authors, date, venue, and a quality
    read. Metadata-extractor uses lite-drafter's summary for `fields`, so this
    slice does not need the conclusion."""
    import fitz
    doc = fitz.open(pdf_path)
    n = min(2, doc.page_count)
    out: list[str] = []
    for i in range(n):
        out.append(f"\n===== PAGE {i+1} =====\n" + doc[i].get_text("text"))
    return "".join(out)


_CITE_RE = re.compile(r"\[\s*\d+(?:\s*[-–,]\s*\d+)*\s*\]")
_WS_RUN_RE = re.compile(r"[ \t]+")
_BLANK_RUN_RE = re.compile(r"\n{3,}")


def compact(text: str) -> str:
    """Strip numeric citations and collapse whitespace.

    Preserves page markers (`===== PAGE N =====`) and newline structure so
    downstream agents can still emit `(§3, p.5)` refs. Only low-signal noise
    is removed."""
    text = _CITE_RE.sub("", text)
    text = _WS_RUN_RE.sub(" ", text)
    text = _BLANK_RUN_RE.sub("\n\n", text)
    return text


def find_existing_paper(
    vault: Path, src_url: str, arxiv_id: Optional[str], doi: Optional[str]
) -> Optional[dict[str, Any]]:
    """Return {slug, title, source_url, arxiv_id, doi} for an existing paper that
    matches by arxiv-id, doi, or source-url. None if no match."""
    norm_arxiv = (arxiv_id or "").split("v", 1)[0].strip().lower() or None
    norm_doi = (doi or "").strip().lower() or None
    norm_url = (src_url or "").strip().lower() or None

    for path in iter_vault_files(vault, "papers"):
        fm, _ = read_frontmatter(path)
        p_arxiv = str(fm.get("arxiv-id") or "").split("v", 1)[0].strip().lower() or None
        p_doi = str(fm.get("doi") or "").strip().lower() or None
        p_url = str(fm.get("source-url") or "").strip().lower() or None

        if (norm_arxiv and p_arxiv and norm_arxiv == p_arxiv) \
                or (norm_doi and p_doi and norm_doi == p_doi) \
                or (norm_url and p_url and norm_url == p_url):
            return {
                "slug": fm.get("slug") or slug_from_path(path),
                "title": fm.get("title"),
                "source_url": fm.get("source-url"),
                "arxiv_id": fm.get("arxiv-id"),
                "doi": fm.get("doi"),
            }
    return None


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

    # Short-circuit if this paper is already in the vault (by arxiv-id, doi, or
    # source-url). Downstream agents are skipped; /ingest tells the user.
    existing = find_existing_paper(vault, src_url, arxiv_id, doi)
    if existing is not None:
        print(json.dumps({
            "already_exists": True,
            "existing": existing,
            "source_type": src_type,
            "source_url": src_url,
            "arxiv_id": arxiv_id,
            "doi": doi,
        }, indent=2))
        return 0

    # Key the cache by the canonical URL (for remote) or absolute file path (for local).
    key = src_url if src_type != "pdf" else src_url  # same — classify() already normalized
    sha = sha256_of(key)
    raw_path = sources / f"{sha}.pdf"
    txt_path = sources / f"{sha}.txt"
    brief_path = sources / f"{sha}.brief.txt"
    findings_path = sources / f"{sha}.findings.txt"
    meta_path = sources / f"{sha}.meta.txt"

    skipped_cached = False
    if (raw_path.exists() and txt_path.exists() and brief_path.exists()
            and findings_path.exists() and meta_path.exists() and not args.force):
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
            txt_path.write_text(full, encoding="utf-8")  # full text stays raw — citation_match needs it
            brief_path.write_text(compact(extract_brief(raw_path)), encoding="utf-8")
            findings_path.write_text(compact(extract_findings_slice(raw_path)), encoding="utf-8")
            meta_path.write_text(compact(extract_meta_slice(raw_path)), encoding="utf-8")
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
            compacted = compact(stripped)
            brief_path.write_text(compacted, encoding="utf-8")
            findings_path.write_text(compacted, encoding="utf-8")
            # HTML fallback has no page structure — meta slice is just the first ~6000 chars.
            meta_path.write_text(compacted[:6000], encoding="utf-8")

    out = {
        "source_type": src_type,
        "source_url": src_url,
        "arxiv_id": arxiv_id,
        "doi": doi,
        "sha": sha,
        "raw_path": str(raw_path),
        "full_text_path": str(txt_path),
        "brief_text_path": str(brief_path),
        "findings_text_path": str(findings_path),
        "meta_text_path": str(meta_path),
        "page_count": page_count,
        "skipped_cached": skipped_cached,
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
