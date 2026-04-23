#!/usr/bin/env python3
"""Deterministic citation matcher — replaces the LLM citation-linker agent.

Given the full paper text and the list of vault papers, find which vault slugs
are cited. Match priority:

    1. arXiv id (e.g. 'arXiv:1706.03762' or 'abs/1706.03762')
    2. DOI
    3. Fuzzy title: normalized substring OR difflib ratio >= 0.85 for titles >= 20 chars
    4. First-author surname + 4-digit year within 6 chars of each other

Usage:
    python3 citation_match.py <paper_text_path> <vault_papers_json>
        vault_papers_json: path to file or '-' for stdin. Shape matches
        vault_scan.py's `papers` output.

Emits JSON on stdout:
    {"cites": ["slug-a", "slug-b"]}
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path


ARXIV_REF_RE = re.compile(
    r"(?:arxiv[:\s]+|abs/|arxiv\.org/(?:abs|pdf)/)(\d{4}\.\d{4,5})(?:v\d+)?",
    re.IGNORECASE,
)
DOI_REF_RE = re.compile(r"\b(10\.\d{4,}/[^\s,;)]+)", re.IGNORECASE)


def normalize_title(t: str | None) -> str:
    if not t:
        return ""
    s = t.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def locate_bibliography(text: str) -> str:
    """Return text from References onward, or the whole text if no header found."""
    m = re.search(r"(?:^|\n)\s*(?:\d+[\.\s]+)?(?:references|bibliography)\s*\n",
                  text, flags=re.IGNORECASE)
    if not m:
        return text
    return text[m.start():]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("paper_text_path")
    ap.add_argument("vault_papers_json", help="file path or '-' for stdin")
    ap.add_argument("--own-slug", default=None, help="skip self-reference if this slug appears")
    args = ap.parse_args(argv)

    text = Path(args.paper_text_path).read_text(encoding="utf-8", errors="replace")
    if args.vault_papers_json == "-":
        vault_papers = json.load(sys.stdin)
    else:
        vault_papers = json.loads(Path(args.vault_papers_json).read_text(encoding="utf-8"))

    if not isinstance(vault_papers, list) or not vault_papers:
        print(json.dumps({"cites": []}))
        return 0

    bib = locate_bibliography(text)

    # Build lookup tables.
    by_arxiv: dict[str, str] = {}
    by_doi: dict[str, str] = {}
    titles: list[tuple[str, str]] = []  # (normalized_title, slug)
    by_author_year: dict[tuple[str, str], str] = {}

    for p in vault_papers:
        slug = p.get("slug")
        if not slug:
            continue
        if p.get("arxiv-id"):
            by_arxiv[str(p["arxiv-id"]).lower()] = slug
        if p.get("doi"):
            by_doi[str(p["doi"]).lower()] = slug
        if p.get("title"):
            titles.append((normalize_title(p["title"]), slug))
        authors = p.get("authors") or []
        first = authors[0] if authors else ""
        surname = first.split(",", 1)[0].strip().lower() if first else ""
        pub_date = (p.get("publication-date") or "")
        year = pub_date[:4] if len(pub_date) >= 4 else ""
        if surname and year:
            by_author_year[(surname, year)] = slug

    cited: set[str] = set()

    # 1. arXiv ids
    for m in ARXIV_REF_RE.finditer(bib):
        aid = m.group(1).lower()
        if aid in by_arxiv:
            cited.add(by_arxiv[aid])

    # 2. DOIs
    for m in DOI_REF_RE.finditer(bib):
        doi = m.group(1).rstrip(".,;)").lower()
        if doi in by_doi:
            cited.add(by_doi[doi])

    # 3. Fuzzy title — only check titles >= 20 chars, substring first, then ratio.
    bib_norm = normalize_title(bib)
    for norm_t, slug in titles:
        if slug in cited or len(norm_t) < 20:
            continue
        if norm_t in bib_norm:
            cited.add(slug)
            continue
        # Scan for best window match. Use difflib on chunks.
        # This is O(|bib| * |titles|) but both are small.
        ratio = difflib.SequenceMatcher(None, norm_t, bib_norm).quick_ratio()
        if ratio >= 0.5:  # gate before the expensive ratio call
            # Find the best window of roughly the title's length.
            n = len(norm_t)
            best = 0.0
            step = max(1, n // 2)
            for i in range(0, max(1, len(bib_norm) - n + 1), step):
                window = bib_norm[i:i + n + 10]
                r = difflib.SequenceMatcher(None, norm_t, window).ratio()
                if r > best:
                    best = r
                    if best >= 0.9:
                        break
            if best >= 0.85:
                cited.add(slug)

    # 4. Author + year fallback for any remaining slug.
    # Look for 'Surname... YYYY' patterns in bib.
    for (surname, year), slug in by_author_year.items():
        if slug in cited:
            continue
        # Require the surname and the year within ~60 chars of each other.
        for m in re.finditer(re.escape(surname), bib_norm):
            start = m.start()
            window = bib_norm[start:start + 80]
            if year in window:
                cited.add(slug)
                break

    if args.own_slug and args.own_slug in cited:
        cited.discard(args.own_slug)

    print(json.dumps({"cites": sorted(cited)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
