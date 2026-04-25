# How Linking Works

Five layers, four deterministic. The LLM only sees ≤30 candidate findings — never the whole vault.

| Layer | Mechanism | LLM? |
|---|---|---|
| **Entity stubs** | `create_stubs.py` materializes missing `authors/*.md` / `fields/*.md` as Obsidian wikilinks | no |
| **Citations** (paper → paper) | `citation_match.py` matches references by arXiv ID → DOI → fuzzy title (ratio ≥ 0.85) → first-author+year | no |
| **Candidate pre-filter** | `vault_scan.py findings-candidates` scores every vault finding by `field_overlap × 2 + author_overlap`; keeps top 30 | no |
| **Finding edges** (typed) | `finding-linker` ranks within the 30 and assigns one of `supports` / `contradicts` / `extends` / `uses` / `similar-to` (≤5 per new finding) | **yes (the only linking LLM call)** |
| **Paper edges** (aggregated) | `apply_edges.py` rolls finding edges up: `uses` → `builds-on`; others keep their name; self-loops skipped; `contradicts` + `similar-to` mirrored | no |
| **Near-dup similar-to** | `lint.py` normalizes statements, wires bidirectional `similar-to` on `difflib` ratio ≥ 0.92 | no |

## Relation Types

### Finding-level

| Edge | Meaning | Symmetry |
|---|---|---|
| `supports` | Provides evidence for target | directed |
| `contradicts` | Asserts something incompatible | bidirectional |
| `extends` | Builds on target, broader/stronger form | directed |
| `uses` | Relies on target as method/tool | directed |
| `similar-to` | Independently-derived near-identical claim | bidirectional |

### Paper-level (aggregated automatically)

| Edge | Source |
|---|---|
| `cites` | `citation_match.py` |
| `builds-on` | aggregated from finding-level `uses` |
| `supports` / `extends` / `contradicts` / `similar-to` | aggregated from finding-level edges of the same name |
