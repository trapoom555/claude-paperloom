#!/usr/bin/env python3
"""Read-only scans over the vault. Emits JSON for downstream scripts/agents.

Subcommands:

    papers              list existing paper frontmatter (for citation_match)
    fields              list kebab field slugs already in vault/fields/
    findings-candidates --fields f1,f2 --authors 'A;B'
                        shortlist existing findings whose fields overlap OR
                        whose source-paper's authors overlap with the given sets.
                        Cap at 50.
    authors             list existing author filenames (basenames without .md)
    findings-all        every finding's key frontmatter (used by lint)

Usage:
    python3 vault_scan.py <subcommand> <vault> [opts]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from _lib import (
    require_vault,
    read_frontmatter,
    iter_vault_files,
    slug_from_path,
    unwrap_wikilink,
)


def _unwrap_list(xs: Any) -> list[str]:
    if not isinstance(xs, list):
        return []
    return [unwrap_wikilink(x) for x in xs if isinstance(x, str)]


def cmd_papers(vault: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in iter_vault_files(vault, "papers"):
        fm, _ = read_frontmatter(path)
        out.append({
            "slug": fm.get("slug") or slug_from_path(path),
            "title": fm.get("title"),
            "authors": _unwrap_list(fm.get("authors") or []),
            "arxiv-id": fm.get("arxiv-id"),
            "doi": fm.get("doi"),
            "publication-date": fm.get("publication-date"),
        })
    return out


def cmd_fields(vault: Path) -> list[str]:
    return [slug_from_path(p) for p in iter_vault_files(vault, "fields")]


def cmd_authors(vault: Path) -> list[str]:
    return [slug_from_path(p) for p in iter_vault_files(vault, "authors")]


def cmd_findings_candidates(
    vault: Path, fields: list[str], authors: list[str], cap: int = 50,
) -> list[dict[str, Any]]:
    field_set = {f.strip() for f in fields if f.strip()}
    author_set = {a.strip() for a in authors if a.strip()}

    # Load paper authors map so we can check shared-author via source-paper.
    paper_authors: dict[str, set[str]] = {}
    for path in iter_vault_files(vault, "papers"):
        fm, _ = read_frontmatter(path)
        slug = fm.get("slug") or slug_from_path(path)
        paper_authors[slug] = set(_unwrap_list(fm.get("authors") or []))

    scored: list[tuple[int, dict[str, Any]]] = []
    for path in iter_vault_files(vault, "findings"):
        fm, _ = read_frontmatter(path)
        f_fields = set(_unwrap_list(fm.get("fields") or []))
        src = unwrap_wikilink(fm.get("source-paper") or "")
        f_authors = paper_authors.get(src, set())

        field_overlap = len(f_fields & field_set)
        author_overlap = len(f_authors & author_set)
        if field_overlap == 0 and author_overlap == 0:
            continue

        scored.append((field_overlap * 2 + author_overlap, {
            "slug": fm.get("slug") or slug_from_path(path),
            "statement": fm.get("statement"),
            "fields": [f"[[{f}]]" for f in sorted(f_fields)],
            "finding-type": fm.get("finding-type"),
            "hedging": fm.get("hedging"),
            "source-paper": f"[[{src}]]" if src else None,
        }))

    scored.sort(key=lambda t: -t[0])
    return [item for _, item in scored[:cap]]


def cmd_findings_all(vault: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in iter_vault_files(vault, "findings"):
        fm, _ = read_frontmatter(path)
        rel = fm.get("relations") or {}
        out.append({
            "slug": fm.get("slug") or slug_from_path(path),
            "statement": fm.get("statement"),
            "source-paper": unwrap_wikilink(fm.get("source-paper") or ""),
            "relations": {
                k: _unwrap_list(rel.get(k) or []) for k in
                ("supports", "contradicts", "extends", "uses", "similar-to")
            },
        })
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name in ("papers", "fields", "authors", "findings-all"):
        s = sub.add_parser(name)
        s.add_argument("vault")

    s = sub.add_parser("findings-candidates")
    s.add_argument("vault")
    s.add_argument("--fields", default="", help="comma-separated kebab field slugs")
    s.add_argument("--authors", default="", help="semicolon-separated 'Surname, Given' names")
    s.add_argument("--cap", type=int, default=50)

    args = ap.parse_args(argv)
    vault = require_vault(args.vault)

    if args.cmd == "papers":
        result = cmd_papers(vault)
    elif args.cmd == "fields":
        result = cmd_fields(vault)
    elif args.cmd == "authors":
        result = cmd_authors(vault)
    elif args.cmd == "findings-all":
        result = cmd_findings_all(vault)
    elif args.cmd == "findings-candidates":
        fields = [x for x in args.fields.split(",") if x]
        authors = [x for x in args.authors.split(";") if x]
        result = cmd_findings_candidates(vault, fields, authors, cap=args.cap)
    else:
        ap.error(f"unknown subcommand: {args.cmd}")
        return 2

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
