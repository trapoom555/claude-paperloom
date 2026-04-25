#!/usr/bin/env python3
"""Append a line to <vault>/log.md.

Usage:
    python3 log.py <vault> <action> <target> <note...>

Example:
    python3 log.py ~/PaperLoom ingest-lite 2017-06-attention-is-all-you-need \
        "8 findings, 5 edges"
"""

from __future__ import annotations

import argparse
import sys

from _lib import require_vault, now_stamp


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("vault")
    ap.add_argument("action")
    ap.add_argument("target")
    ap.add_argument("note", nargs="*")
    args = ap.parse_args(argv)

    vault = require_vault(args.vault)
    note = " ".join(args.note)
    line = f"{now_stamp()} | {args.action} | {args.target} | {note}"
    with (vault / "log.md").open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
