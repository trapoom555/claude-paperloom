#!/usr/bin/env python3
"""Vault health check — replaces the inline /lint command logic.

Runs six checks and emits a human-readable report to stdout. Non-zero exit
if any issue is found.

Checks:
    1. Frontmatter schema drift — required keys per type
    2. Orphan pages — no inbound and no outbound wikilinks
    3. Duplicate findings — NEW-vs-ALL only (not all-pairs). A pair is flagged
       only if at least one member is "new". By default --link-similar wires a
       bidirectional `similar-to` edge between each dup pair found.
    4. Asymmetric contradicts / similar-to — A links B but B doesn't link A
    5. Stale wikilinks — [[slug]] whose target file does not exist
    6. Date sanity — ISO YYYY-MM-DD; ingested-date >= publication-date

"New" is controlled by --new-slugs (explicit list) or --since (date cutoff,
defaults to today). Old-vs-old duplicates are ignored — they've either been
handled already or are intentionally kept.

Appends a line to <vault>/log.md.

Usage:
    python3 lint.py <vault>
    python3 lint.py <vault> --new-slugs finding-a,finding-b
    python3 lint.py <vault> --since 2026-04-01
    python3 lint.py <vault> --no-link-similar   # read-only mode
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path
from typing import Any

from _lib import (
    require_vault,
    read_frontmatter,
    write_frontmatter,
    iter_vault_files,
    slug_from_path,
    extract_wikilinks,
    all_wikilinks_in_file,
    unwrap_wikilink,
    wrap_wikilink,
    now_stamp,
    today,
)


# ---------------------- schema ----------------------

PAPER_REQUIRED = [
    "type", "title", "slug", "authors", "fields",
    "publication-date", "ingested-date", "source-url",
    "quality.credibility", "quality.experimental-rigor",
    "quality.reproducibility", "quality.overall", "quality.rationale",
    "findings",
    "relations.cites", "relations.builds-on", "relations.supports",
    "relations.contradicts", "relations.extends", "relations.similar-to",
]

FINDING_REQUIRED = [
    "type", "statement", "slug", "source-paper", "source-ref",
    "fields", "extracted-date", "finding-type", "hedging",
    "relations.supports", "relations.contradicts", "relations.extends",
    "relations.uses", "relations.similar-to",
]

AUTHOR_REQUIRED = ["type", "name"]
FIELD_REQUIRED = ["type", "name"]


FINDING_TYPE_ALLOWED = {"empirical", "theoretical", "definitional"}
HEDGING_ALLOWED = {"asserted", "hedged", "speculative"}
REPRODUCIBILITY_ALLOWED = {"code-released", "partial", "none"}

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def get_by_dots(d: dict[str, Any], path: str) -> tuple[bool, Any]:
    cur: Any = d
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return False, None
    return True, cur


def check_schema(vault: Path) -> list[str]:
    issues: list[str] = []

    specs = [
        ("papers",   PAPER_REQUIRED,   "paper"),
        ("findings", FINDING_REQUIRED, "finding"),
        ("authors",  AUTHOR_REQUIRED,  "author"),
        ("fields",   FIELD_REQUIRED,   "field"),
    ]

    for subdir, required, expected_type in specs:
        for path in iter_vault_files(vault, subdir):
            rel = f"{subdir}/{path.name}"
            fm, _ = read_frontmatter(path)
            if fm.get("type") != expected_type:
                issues.append(f"  - {rel}  wrong/missing type: expected '{expected_type}', got {fm.get('type')!r}")
            for key in required:
                present, val = get_by_dots(fm, key)
                if not present or val is None and key != "doi":
                    issues.append(f"  - {rel}  missing: {key}")
            # Enum checks.
            if expected_type == "finding":
                ft = fm.get("finding-type")
                if ft is not None and ft not in FINDING_TYPE_ALLOWED:
                    issues.append(f"  - {rel}  wrong value: finding-type = {ft!r} (expected {sorted(FINDING_TYPE_ALLOWED)})")
                hg = fm.get("hedging")
                if hg is not None and hg not in HEDGING_ALLOWED:
                    issues.append(f"  - {rel}  wrong value: hedging = {hg!r} (expected {sorted(HEDGING_ALLOWED)})")
            if expected_type == "paper":
                q = fm.get("quality") or {}
                repro = q.get("reproducibility")
                if repro is not None and repro not in REPRODUCIBILITY_ALLOWED:
                    issues.append(f"  - {rel}  wrong value: quality.reproducibility = {repro!r} (expected {sorted(REPRODUCIBILITY_ALLOWED)})")
    return issues


def collect_all_slugs(vault: Path) -> dict[str, Path]:
    """slug → path for every file in papers/findings/authors/fields."""
    out: dict[str, Path] = {}
    for sub in ("papers", "findings", "authors", "fields"):
        for p in iter_vault_files(vault, sub):
            out[slug_from_path(p)] = p
    return out


def check_orphans(vault: Path, all_slugs: dict[str, Path]) -> list[str]:
    # Build reverse-link index: slug -> set of files linking to it.
    incoming: dict[str, set[Path]] = {s: set() for s in all_slugs}
    outgoing: dict[Path, set[str]] = {}

    for slug, path in all_slugs.items():
        links = all_wikilinks_in_file(path)
        outgoing[path] = {unwrap_wikilink(l) for l in links}
        for l in links:
            target = unwrap_wikilink(l)
            if target in incoming:
                incoming[target].add(path)

    issues: list[str] = []
    for slug, path in all_slugs.items():
        has_in = bool(incoming.get(slug))
        has_out = any(out in all_slugs for out in outgoing.get(path, set()))
        if not has_in and not has_out:
            rel = path.relative_to(vault)
            issues.append(f"  - {rel}")
    return issues


def normalize_statement(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def check_dup_findings(
    vault: Path,
    new_slugs: set[str] | None = None,
    since_date: str | None = None,
) -> tuple[list[str], list[tuple[str, str]]]:
    """Flag near-duplicate findings — but only groups that include a NEW one.

    "New" = slug in `new_slugs` (if provided), else finding whose `extracted-date >= since_date`.
    Old-vs-old pairs are not reported — they were either already caught or intentionally kept.

    Returns (issues_text, link_pairs). `link_pairs` is a deduped list of (a, b) that
    should be wired as bidirectional `similar-to` edges. The caller decides whether to apply.
    """
    finds: list[tuple[str, str, str, bool]] = []  # (slug, normalized, source, is_new)
    for path in iter_vault_files(vault, "findings"):
        fm, _ = read_frontmatter(path)
        slug = fm.get("slug") or slug_from_path(path)
        stmt = normalize_statement(fm.get("statement") or "")
        src = unwrap_wikilink(fm.get("source-paper") or "")
        extracted = str(fm.get("extracted-date") or "")
        if new_slugs is not None:
            is_new = slug in new_slugs
        elif since_date:
            is_new = extracted >= since_date
        else:
            is_new = False
        if stmt:
            finds.append((slug, stmt, src, is_new))

    # Only compare NEW × (ALL): every pair has at least one new member.
    # Group each new finding with its near-duplicates (new or old).
    groups: list[set[int]] = []
    assigned = [-1] * len(finds)
    for i, (_, stmt_i, _, is_new_i) in enumerate(finds):
        if not is_new_i or assigned[i] >= 0:
            continue
        group = {i}
        for j, (_, stmt_j, _, _) in enumerate(finds):
            if j == i or assigned[j] >= 0:
                continue
            if difflib.SequenceMatcher(None, stmt_i, stmt_j).ratio() >= 0.92:
                group.add(j)
        if len(group) > 1:
            for k in group:
                assigned[k] = len(groups)
            groups.append(group)

    issues: list[str] = []
    link_pairs: set[tuple[str, str]] = set()
    for group in groups:
        members = [finds[k] for k in sorted(group)]
        slugs = " ⟷ ".join(f"[[{m[0]}]]" for m in members)
        sources = ", ".join(sorted({f"[[{m[2]}]]" for m in members if m[2]}))
        issues.append(f"  - {slugs}")
        if sources:
            issues.append(f"    sources: {sources}")
        member_slugs = [m[0] for m in members]
        for a in member_slugs:
            for b in member_slugs:
                if a < b:
                    link_pairs.add((a, b))

    return issues, sorted(link_pairs)


def apply_similar_links(vault: Path, pairs: list[tuple[str, str]]) -> int:
    """Create bidirectional similar-to edges between each pair. Returns edges added."""
    added = 0
    for a, b in pairs:
        for src, tgt in ((a, b), (b, a)):
            p = vault / "findings" / f"{src}.md"
            if not p.exists():
                continue
            fm, body = read_frontmatter(p)
            rel = fm.get("relations") or {}
            lst = rel.get("similar-to") or []
            existing = {unwrap_wikilink(x) for x in lst if isinstance(x, str)}
            if tgt in existing:
                continue
            lst.append(wrap_wikilink(tgt))
            rel["similar-to"] = lst
            fm["relations"] = rel
            write_frontmatter(p, fm, body)
            added += 1
    return added


def check_asymmetric(vault: Path) -> list[str]:
    # Load all findings' edges.
    edges: dict[str, dict[str, set[str]]] = {}
    for path in iter_vault_files(vault, "findings"):
        fm, _ = read_frontmatter(path)
        slug = fm.get("slug") or slug_from_path(path)
        rel = fm.get("relations") or {}
        edges[slug] = {
            k: {unwrap_wikilink(x) for x in (rel.get(k) or []) if isinstance(x, str)}
            for k in ("contradicts", "similar-to")
        }

    issues: list[str] = []
    for src, e in edges.items():
        for edge_type in ("contradicts", "similar-to"):
            for tgt in e[edge_type]:
                if tgt not in edges:
                    continue
                if src not in edges[tgt][edge_type]:
                    issues.append(f"  - [[{src}]] -> {edge_type} [[{tgt}]], but [[{tgt}]] does not list [[{src}]]")
    return issues


def check_stale(vault: Path, all_slugs: dict[str, Path]) -> list[str]:
    issues: list[str] = []
    for path in list(all_slugs.values()) + [vault / "index.md"]:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for link in extract_wikilinks(text):
            target = unwrap_wikilink(link)
            if not target:
                continue
            # Tolerate links to views/, assets/, or the file itself.
            if target.startswith(("views/", "assets/")) or target == slug_from_path(path):
                continue
            if target not in all_slugs:
                rel = path.relative_to(vault)
                issues.append(f"  - {rel}  →  [[{target}]] (target not found)")
    return issues


def check_dates(vault: Path) -> list[str]:
    issues: list[str] = []
    for path in iter_vault_files(vault, "papers"):
        fm, _ = read_frontmatter(path)
        rel = f"papers/{path.name}"
        pub = fm.get("publication-date")
        ing = fm.get("ingested-date")
        for label, val in (("publication-date", pub), ("ingested-date", ing)):
            if val is not None and not ISO_DATE_RE.match(str(val)):
                issues.append(f"  - {rel}  {label} not ISO: {val!r}")
        if pub and ing and ISO_DATE_RE.match(str(pub)) and ISO_DATE_RE.match(str(ing)):
            if str(ing) < str(pub):
                issues.append(f"  - {rel}  ingested-date ({ing}) earlier than publication-date ({pub})")
    for path in iter_vault_files(vault, "findings"):
        fm, _ = read_frontmatter(path)
        ed = fm.get("extracted-date")
        if ed is not None and not ISO_DATE_RE.match(str(ed)):
            issues.append(f"  - findings/{path.name}  extracted-date not ISO: {ed!r}")
    return issues


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("vault")
    ap.add_argument("--json", action="store_true", help="emit structured JSON instead of text report")
    ap.add_argument(
        "--new-slugs", default="",
        help="comma-separated finding slugs to treat as 'new' for dedup. "
             "Only groups that contain at least one new slug are reported/linked.",
    )
    ap.add_argument(
        "--since", default=None,
        help="ISO date (YYYY-MM-DD). Findings with extracted-date >= this are 'new' "
             "for dedup purposes. Ignored if --new-slugs is given. Defaults to today.",
    )
    ap.add_argument(
        "--link-similar", action=argparse.BooleanOptionalAction, default=True,
        help="When dup pairs are found, create bidirectional similar-to edges between them. "
             "On by default; pass --no-link-similar to keep lint read-only.",
    )
    args = ap.parse_args(argv)

    vault = require_vault(args.vault)
    all_slugs = collect_all_slugs(vault)

    new_slugs = {s.strip() for s in args.new_slugs.split(",") if s.strip()} if args.new_slugs else None
    since_date = args.since or (today() if new_slugs is None else None)

    schema_issues = check_schema(vault)
    orphan_issues = check_orphans(vault, all_slugs)
    dup_issues, dup_pairs = check_dup_findings(vault, new_slugs=new_slugs, since_date=since_date)
    asym_issues = check_asymmetric(vault)
    stale_issues = check_stale(vault, all_slugs)
    date_issues = check_dates(vault)

    edges_added = 0
    if dup_pairs and args.link_similar:
        edges_added = apply_similar_links(vault, dup_pairs)

    sections = [
        ("Schema drift",           schema_issues),
        ("Orphans",                orphan_issues),
        ("Duplicate findings",     dup_issues),
        ("Asymmetric edges",       asym_issues),
        ("Stale wikilinks",        stale_issues),
        ("Date sanity",            date_issues),
    ]

    if args.json:
        out = {name: lines for name, lines in sections}
        out["_scope"] = {
            "new_slugs": sorted(new_slugs) if new_slugs else None,
            "since_date": since_date,
        }
        out["_similar_links_added"] = edges_added
        print(json.dumps(out, indent=2))
    else:
        scope = (f"scope: {len(new_slugs)} explicit new slugs" if new_slugs
                 else f"scope: findings with extracted-date >= {since_date}" if since_date
                 else "scope: full vault")
        print(f"Lint report — {vault} — {now_stamp()}  ({scope})")
        print("─" * 60)
        for name, lines in sections:
            count = len(lines) if name != "Duplicate findings" else sum(1 for l in lines if not l.startswith("    "))
            print(f"{name} ({count}):")
            for l in lines:
                print(l)
            print()
        if edges_added:
            print(f"Auto-linked {edges_added} similar-to edge(s) between dup pairs.")
            print()

    total = sum(len(lines) for _, lines in sections)
    with (vault / "log.md").open("a", encoding="utf-8") as f:
        f.write(f"{now_stamp()} | lint | {vault} | {total} issues, {edges_added} similar-to edges added\n")

    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
