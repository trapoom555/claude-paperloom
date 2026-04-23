#!/usr/bin/env python3
"""Create missing author/field stub pages from templates.

Reads JSON payload from --input (or stdin):

    {
      "vault_path": "/abs/...",
      "authors": ["Vaswani, Ashish", ...],   # filenames used verbatim (+ .md)
      "fields":  ["nlp", "transformer"]      # kebab slugs
    }

For each name, if <vault>/authors/<name>.md (or fields/<slug>.md) does not
exist, writes it from templates/author.md (or field.md) with the name/slug
substituted. Existing files are untouched.

Emits a summary:
    {"authors_created": [...], "authors_skipped": [...],
     "fields_created":  [...], "fields_skipped":  [...]}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _lib import require_vault


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
AUTHOR_TEMPLATE = (PLUGIN_ROOT / "templates" / "author.md").read_text(encoding="utf-8")
FIELD_TEMPLATE = (PLUGIN_ROOT / "templates" / "field.md").read_text(encoding="utf-8")


def render(template: str, mapping: dict[str, str]) -> str:
    out = template
    for k, v in mapping.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--input", default="-")
    args = ap.parse_args(argv)

    if args.input == "-":
        payload = json.load(sys.stdin)
    else:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))

    vault = require_vault(payload.get("vault_path"))
    authors = payload.get("authors") or []
    fields = payload.get("fields") or []

    authors_dir = vault / "authors"
    fields_dir = vault / "fields"
    authors_dir.mkdir(exist_ok=True)
    fields_dir.mkdir(exist_ok=True)

    a_created: list[str] = []
    a_skipped: list[str] = []
    for name in authors:
        # Filename follows "Surname, Given" convention. Sanitize path separators only.
        fname = name.replace("/", "-")
        path = authors_dir / f"{fname}.md"
        if path.exists():
            a_skipped.append(name)
            continue
        content = render(AUTHOR_TEMPLATE, {
            "NAME": name,
            "AFFILIATION": "null",
            "ORCID": "null",
        })
        path.write_text(content, encoding="utf-8")
        a_created.append(name)

    f_created: list[str] = []
    f_skipped: list[str] = []
    for slug in fields:
        path = fields_dir / f"{slug}.md"
        if path.exists():
            f_skipped.append(slug)
            continue
        content = render(FIELD_TEMPLATE, {
            "NAME": slug,
            "PARENT_FIELD": "null",
        })
        path.write_text(content, encoding="utf-8")
        f_created.append(slug)

    print(json.dumps({
        "authors_created": a_created,
        "authors_skipped": a_skipped,
        "fields_created":  f_created,
        "fields_skipped":  f_skipped,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
