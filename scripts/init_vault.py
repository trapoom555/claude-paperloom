#!/usr/bin/env python3
"""Scaffold a Research Librarian vault. Idempotent.

Creates the directory tree, copies CLAUDE.md / index.md / log.md / view pages
from the plugin's templates/ dir. Appends a line to log.md.

Usage:
    python3 init_vault.py <vault_path>

Prints a report to stdout; exits non-zero if the path is unusable.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from _lib import resolve_vault, now_stamp


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = PLUGIN_ROOT / "templates"

ROOT_DIRS = ["papers", "findings", "authors", "fields", "views", ".sources"]
ROOT_FILES = ["CLAUDE.md", "index.md", "log.md"]
VIEW_FILES = [
    "recent-papers.md",
    "by-field.md",
    "by-author.md",
    "contradictions.md",
    "high-credibility.md",
]


def seed(src: Path, dst: Path) -> str:
    """Copy src → dst if dst missing. Returns 'created' | 'skipped'."""
    if dst.exists():
        return "skipped"
    if not src.exists():
        return f"missing-template({src.name})"
    shutil.copy2(src, dst)
    return "created"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("vault_path", help="Vault directory (~ and env vars expanded)")
    args = ap.parse_args(argv)

    vault = resolve_vault(args.vault_path)
    print(f"Using vault: {vault}")

    vault.mkdir(parents=True, exist_ok=True)
    for sub in ROOT_DIRS:
        (vault / sub).mkdir(exist_ok=True)

    results: list[tuple[str, str]] = []
    for name in ROOT_FILES:
        results.append((name, seed(TEMPLATES / name, vault / name)))
    for name in VIEW_FILES:
        results.append((f"views/{name}", seed(TEMPLATES / "views" / name, vault / "views" / name)))

    log_line = f"{now_stamp()} | init | {vault} | seeded"
    with (vault / "log.md").open("a", encoding="utf-8") as f:
        f.write(log_line + "\n")

    created = [n for n, s in results if s == "created"]
    skipped = [n for n, s in results if s == "skipped"]
    missing = [n for n, s in results if s.startswith("missing-template")]

    print(f"Created ({len(created)}):")
    for n in created:
        print(f"  + {n}")
    print(f"Skipped (already present) ({len(skipped)}):")
    for n in skipped:
        print(f"  = {n}")
    if missing:
        print(f"Template missing ({len(missing)}):")
        for n in missing:
            print(f"  ! {n}")

    vault_basename = vault.name
    print()
    print("Next: install the Dataview community plugin in Obsidian.")
    print(f"Open the vault: obsidian://open?vault={vault_basename}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
