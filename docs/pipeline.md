# The Ingest Pipeline

Four LLM calls per paper. Everything else is deterministic Python.

```
┌ 1. fetch_paper.py     sniff → download → extract 4 text slices
│     .txt            full plain text (citation_match only, never sent to an LLM)
│     .brief.txt      abstract + intro + conclusion            (~10–25% of paper)
│     .findings.txt   abstract + intro + method + results + conclusion  (~40–60%)
│     .meta.txt       first 2 pages only
│     (agent-facing slices are compact()-ed: numeric citations
│      like [1], [2,3], [4-6] stripped, whitespace collapsed)
│     → early exit if arXiv-id / DOI / URL already in vault
│
├ 2. vault_scan.py     parallel reads: fields, papers, authors (0 tokens)
│
├ 3. PARALLEL FAN-OUT  (2 LLM calls)
│     lite-drafter          ← .brief.txt       → 4-section JSON
│     finding-extractor     ← .findings.txt    → atomic findings JSON
│
├ 4. metadata-extractor (1 LLM call)
│     ← .meta.txt + drafter summary
│     → title / authors / date / venue / fields / quality
│
├ 5. assemble_paper.py   fill templates/paper-lite.md, compute slug,
│                        compute quality.overall, write papers/<slug>.md
│
├ 6. PARALLEL (all scripts, 0 tokens)
│     assemble_finding.py    write findings/*.md
│     citation_match.py      bibliographic matching → cites edges
│     vault_scan.py          candidate shortlist (≤30, trimmed payload)
│     create_stubs.py        missing author/field stubs
│
├ 7. finding-linker (1 LLM call)
│     ← new findings + ≤30 candidates
│     → typed-edge proposals (JSON)
│   apply_edges.py       write edges, mirror bidirectional,
│                        aggregate to paper-level, merge with cites
│
└ 8. log.py   →   9. lint.py --new-slugs ...
```

## Section Detection

How `fetch_paper.py` picks which pages to feed downstream agents — three strategies, cascaded:

1. **PDF outline (TOC)** — `doc.get_toc()` gives `[level, title, page]`. Sections whose title matches the cue regex are kept through the next sibling heading. Usable on most arXiv / journal papers.
2. **Font-size heading detection** — body size is the character-count-weighted mode of all spans; headings are lines whose largest span exceeds 1.1× body size and are ≤120 chars. A matching heading's page range extends to the next heading.
3. **Page-header regex** — fallback only; a page is kept if its first 500 chars contain a cue word.

Strategies 1 and 2 are unioned; the regex fallback fires only if neither matched. First 3 pages and last 2 pre-bibliography pages are always included.

## Models

Hardcoded in each agent's frontmatter:

| Agent | Model |
|---|---|
| `finding-extractor`, `finding-linker`, `metadata-extractor` | `haiku` |
| `lite-drafter` (critique / critical thinking) | `sonnet` |

## Token Cost Per Ingest

| Stage | Input | Model | Notes |
|---|---|---|---|
| `finding-extractor` | findings slice (~40–60% of paper) | Haiku | heaviest in tokens |
| `lite-drafter` | brief (~10–25%) | Sonnet | pricier per token |
| `metadata-extractor` | first 2 pages (~5%) | Haiku | tight |
| `finding-linker` | ≤30 × `{slug, statement, fields}` | Haiku | tiny, **graph-size-independent** |

Scripts, lint, vault scan, citation match, stub creation, edge aggregation: **0 tokens**.
