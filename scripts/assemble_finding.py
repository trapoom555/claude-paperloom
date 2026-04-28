#!/usr/bin/env python3
"""Write finding .md files from finding-extractor output.

Reads JSON payload from --input (file or stdin):

    {
      "vault_path":   "/abs/...",
      "source_paper": "YYYY-MM-slug",
      "fields":       ["nlp", "attention-mechanism"],
      "findings": [
        {
          "statement":   "...",
          "source-ref":  "§3.2, Table 1",
          "finding-type": "empirical",
          "hedging":     "asserted",
          "quote":       "..."
        }
      ],
      "overwrite": false
    }

Writes one file per finding at <vault>/findings/finding-<kebab>.md. Emits:

    {"findings": [{"slug": "...", "path": "...", "skipped": false}, ...]}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from _lib import (
    require_vault,
    today,
    kebab,
    wrap_wikilink,
    dump_frontmatter,
)


def slug_for_finding(statement: str) -> str:
    k = kebab(statement, max_len=55)
    # Strip 'the', 'a', 'is', 'are' at start — keeps slugs punchier.
    for prefix in ("the-", "a-", "an-", "is-", "are-"):
        if k.startswith(prefix):
            k = k[len(prefix):]
    return f"finding-{k}"[:60]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--input", default="-", help="JSON payload path or '-' for stdin")
    args = ap.parse_args(argv)

    if args.input == "-":
        payload = json.load(sys.stdin)
    else:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))

    vault = require_vault(payload.get("vault_path"))
    source_paper = payload["source_paper"]
    fields = payload.get("fields") or []
    items: list[dict[str, Any]] = payload.get("findings", [])
    overwrite = bool(payload.get("overwrite", False))

    out_dir = vault / "findings"
    out_dir.mkdir(exist_ok=True)

    results: list[dict[str, Any]] = []
    seen_slugs: set[str] = set()

    for f in items:
        base_slug = slug_for_finding(f["statement"])
        slug = base_slug
        i = 2
        while slug in seen_slugs or (out_dir / f"{slug}.md").exists() and not overwrite:
            if (out_dir / f"{slug}.md").exists() and not overwrite:
                # Don't clobber an existing finding — add disambiguator.
                pass
            slug = f"{base_slug[:56]}-{i}"
            i += 1
            if i > 99:
                break
        seen_slugs.add(slug)

        fm = {
            "type": "finding",
            "statement": f["statement"],
            "slug": slug,
            "source-paper": wrap_wikilink(source_paper),
            "source-ref": f.get("source-ref", ""),
            "fields": [wrap_wikilink(fld) for fld in fields],
            "extracted-date": today(),
            "finding-type": f.get("finding-type", "empirical"),
            "hedging": f.get("hedging", "asserted"),
            "relations": {
                "supports":    [],
                "contradicts": [],
                "extends":     [],
                "uses":        [],
                "similar-to":  [],
            },
        }

        quote = f.get("quote") or f["statement"]
        source_ref = f.get("source-ref", "")

        body = f"""
# {f["statement"]}

> {quote}
— [[{source_paper}]] ({source_ref})

## Evidence

- From [[{source_paper}]] ({source_ref})

## Relations

*Edit edges in the YAML `relations` block above — these auto-render from it.*

- **Supports →** `= this.relations.supports`
- **Contradicts ⚡** `= this.relations.contradicts`
- **Extends ↗** `= this.relations.extends`
- **Uses 🔧** `= this.relations.uses`
- **Similar to ≈** `= this.relations["similar-to"]`

## Incoming edges (backlinks from other findings)

Findings that reference this one — grouped by the edge type on the *other* side.

```dataview
TABLE WITHOUT ID
  file.link AS "Finding",
  (choice(contains(relations.supports, this.file.link), "supports →", "") +
   choice(contains(relations.contradicts, this.file.link), "contradicts ⚡", "") +
   choice(contains(relations.extends, this.file.link), "extends ↗", "") +
   choice(contains(relations.uses, this.file.link), "uses 🔧", "") +
   choice(contains(relations["similar-to"], this.file.link), "similar to ≈", "")) AS "Edge type"
FROM "findings"
WHERE file.path != this.file.path AND (
  contains(relations.supports, this.file.link) OR
  contains(relations.contradicts, this.file.link) OR
  contains(relations.extends, this.file.link) OR
  contains(relations.uses, this.file.link) OR
  contains(relations["similar-to"], this.file.link)
)
```

## One-hop neighborhood (combined)

```dataview
LIST
FROM outgoing([[]]) OR [[]]
WHERE type = "finding"
```
"""

        out_path = out_dir / f"{slug}.md"
        skipped = False
        if out_path.exists() and not overwrite:
            skipped = True
        else:
            text = "---\n" + dump_frontmatter(fm) + "---\n" + body
            out_path.write_text(text, encoding="utf-8")

        results.append({"slug": slug, "path": str(out_path), "skipped": skipped})

    print(json.dumps({"findings": results}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
