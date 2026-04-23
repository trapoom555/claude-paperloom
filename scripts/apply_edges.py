#!/usr/bin/env python3
"""Apply finding-linker output to the vault.

1. Write edges into each new finding's `relations.*`.
2. Mirror `contradicts` and `similar-to` back onto target findings.
3. Aggregate to paper-level relations on the new paper:
       supports    -> relations.supports
       uses        -> relations.builds-on
       extends     -> relations.extends
       contradicts -> relations.contradicts  (bidirectional on target paper too)
       similar-to  -> relations.similar-to   (bidirectional)
   Skip self-loops (when the target finding shares source-paper with the new paper).

Reads JSON payload from --input:

    {
      "vault_path":   "/abs/...",
      "new_paper":    "YYYY-MM-slug",
      "cites":        ["slug-1", ...],
      "linker_output": [
        {
          "new_finding": "finding-...",
          "edges": {
            "supports":    [{"target": "finding-...", "why": "..."}, ...],
            "contradicts": [...], "extends": [...], "uses": [...], "similar-to": [...]
          }
        }
      ]
    }

Emits a summary on stdout:
    {"edge_counts": {"supports": 3, ...}, "touched_files": N}
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
    write_frontmatter,
    unwrap_wikilink,
    wrap_wikilink,
)


EDGE_TYPES = ["supports", "contradicts", "extends", "uses", "similar-to"]
BIDIRECTIONAL = {"contradicts", "similar-to"}

# Finding-edge → paper-relation name.
FINDING_TO_PAPER_EDGE = {
    "supports":    "supports",
    "uses":        "builds-on",
    "extends":     "extends",
    "contradicts": "contradicts",
    "similar-to":  "similar-to",
}
PAPER_BIDIRECTIONAL = {"contradicts", "similar-to"}


def finding_path(vault: Path, slug: str) -> Path:
    return vault / "findings" / f"{slug}.md"


def paper_path(vault: Path, slug: str) -> Path:
    return vault / "papers" / f"{slug}.md"


def add_to_list(fm: dict[str, Any], keypath: list[str], value: str) -> bool:
    """Ensure fm[keypath...] is a list and contains value (as wikilink). Returns True if added."""
    cur: Any = fm
    for k in keypath[:-1]:
        if k not in cur or not isinstance(cur[k], dict):
            cur[k] = {}
        cur = cur[k]
    last = keypath[-1]
    lst = cur.get(last)
    if not isinstance(lst, list):
        lst = []
    wl = wrap_wikilink(value)
    if wl in lst:
        return False
    lst.append(wl)
    cur[last] = lst
    return True


def source_paper_of_finding(vault: Path, slug: str) -> str | None:
    p = finding_path(vault, slug)
    if not p.exists():
        return None
    fm, _ = read_frontmatter(p)
    return unwrap_wikilink(fm.get("source-paper") or "") or None


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--input", default="-", help="JSON payload path or '-' for stdin")
    args = ap.parse_args(argv)

    if args.input == "-":
        payload = json.load(sys.stdin)
    else:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))

    vault = require_vault(payload.get("vault_path"))
    new_paper = payload["new_paper"]
    linker = payload.get("linker_output") or []
    cites = payload.get("cites") or []

    edge_counts: dict[str, int] = {t: 0 for t in EDGE_TYPES}
    touched: set[Path] = set()

    # Accumulator for paper-level relations on the new paper.
    paper_edges: dict[str, set[str]] = {
        "cites":       set(cites),
        "builds-on":   set(),
        "supports":    set(),
        "contradicts": set(),
        "extends":     set(),
        "similar-to":  set(),
    }
    # Targets to mirror bidirectional paper edges onto.
    mirror_paper_edges: dict[str, dict[str, set[str]]] = {}  # target_paper_slug -> {edge: {new_paper}}

    for item in linker:
        nf_slug = item["new_finding"]
        nf_path = finding_path(vault, nf_slug)
        if not nf_path.exists():
            continue
        nf_fm, nf_body = read_frontmatter(nf_path)
        new_source = unwrap_wikilink(nf_fm.get("source-paper") or "") or new_paper

        for edge_type in EDGE_TYPES:
            for edge in item.get("edges", {}).get(edge_type, []) or []:
                target = edge.get("target") if isinstance(edge, dict) else edge
                if not target:
                    continue
                tgt_slug = unwrap_wikilink(target)
                if tgt_slug == nf_slug:
                    continue  # no self-loops on findings

                if add_to_list(nf_fm, ["relations", edge_type], tgt_slug):
                    edge_counts[edge_type] += 1

                # Mirror on target finding if bidirectional.
                if edge_type in BIDIRECTIONAL:
                    tp = finding_path(vault, tgt_slug)
                    if tp.exists():
                        tfm, tbody = read_frontmatter(tp)
                        if add_to_list(tfm, ["relations", edge_type], nf_slug):
                            write_frontmatter(tp, tfm, tbody)
                            touched.add(tp)

                # Paper-level aggregation.
                target_source = source_paper_of_finding(vault, tgt_slug)
                if not target_source or target_source == new_source:
                    continue
                paper_edge_name = FINDING_TO_PAPER_EDGE[edge_type]
                paper_edges[paper_edge_name].add(target_source)
                if paper_edge_name in PAPER_BIDIRECTIONAL:
                    mirror_paper_edges.setdefault(target_source, {}).setdefault(paper_edge_name, set()).add(new_source)

        write_frontmatter(nf_path, nf_fm, nf_body)
        touched.add(nf_path)

    # Write paper-level relations onto the new paper file.
    np_path = paper_path(vault, new_paper)
    if np_path.exists():
        fm, body = read_frontmatter(np_path)
        rel = fm.get("relations") or {}
        for edge_name, targets in paper_edges.items():
            existing = rel.get(edge_name) or []
            existing_set = {unwrap_wikilink(x) for x in existing if isinstance(x, str)}
            merged = sorted(existing_set | targets)
            rel[edge_name] = [wrap_wikilink(x) for x in merged]
        fm["relations"] = rel
        write_frontmatter(np_path, fm, body)
        touched.add(np_path)

    # Mirror bidirectional paper edges onto target papers.
    for target_paper, edges in mirror_paper_edges.items():
        tp_path = paper_path(vault, target_paper)
        if not tp_path.exists():
            continue
        fm, body = read_frontmatter(tp_path)
        rel = fm.get("relations") or {}
        changed = False
        for edge_name, sources in edges.items():
            existing = rel.get(edge_name) or []
            existing_set = {unwrap_wikilink(x) for x in existing if isinstance(x, str)}
            new_set = existing_set | sources
            if new_set != existing_set:
                rel[edge_name] = [wrap_wikilink(x) for x in sorted(new_set)]
                changed = True
        if changed:
            fm["relations"] = rel
            write_frontmatter(tp_path, fm, body)
            touched.add(tp_path)

    print(json.dumps({"edge_counts": edge_counts, "touched_files": len(touched)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
