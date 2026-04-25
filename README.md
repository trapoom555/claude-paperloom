# claude-paperloom

<p align="center">
  <em>A self-maintaining research knowledge graph for Claude Code + Obsidian.</em>
</p>

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude_Code-plugin-8B5CF6)](https://code.claude.com/docs/en/discover-plugins)
[![Obsidian](https://img.shields.io/badge/Obsidian-native-7C3AED)](https://obsidian.md)

**Keep every paper you care about. See how they connect.** Drop in a URL, arXiv ID, DOI, or PDF — Claude files it into an Obsidian vault, extracts the atomic claims, and wires them to everything you've read before with typed edges: `supports`, `contradicts`, `extends`, `uses`, `similar-to`.

Based on [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f), tuned for research papers: arXiv / DOI / URL / PDF in, a typed finding-level knowledge graph out. **4 LLM calls per paper. Zero manual filing. Linking cost stays constant as the graph grows.**

---

## What It Does

### Ingest
You drop a URL, arXiv ID, DOI, or local PDF. Claude fetches it, picks the right pages (abstract, intro, method, results, conclusion — skipping the bibliography), writes a four-section triage summary (Key Takeaways → Background → Main Idea & Summary → Critique), and extracts metadata: authors, venue, date, research fields, and a quality assessment (credibility, experimental rigor, reproducibility).

Then it pulls out **atomic findings** as first-class graph nodes — one claim per file, each with its own frontmatter and backlinks.

### Link
Every new finding is compared against a shortlist of existing findings in your vault (pre-filtered by field + author overlap, capped at 30) and gets typed edges: `supports`, `contradicts`, `extends`, `uses`, `similar-to`. These aggregate up to paper-level relations automatically. Bibliographic citations are matched deterministically (arXiv ID → DOI → fuzzy title → first-author+year) — the LLM never sees the reference list.

### Query
Ask a question. Claude searches the vault, synthesizes an answer, and cites specific paper slugs and finding nodes via wikilinks — not training data.

### Lint
Scan for orphans, schema drift, duplicate findings, asymmetric contradictions, stale wikilinks. Near-duplicate findings auto-get bidirectional `similar-to` edges on normalized-string + Levenshtein similarity ≥ 0.92.

---

## Why claude-paperloom?

| Capability | claude-paperloom | Zotero + AI plugins | ChatGPT on PDFs |
|---|---|---|---|
| **Atomic findings as graph nodes** | Yes | No | No |
| **Typed edges** (supports / contradicts / extends / uses / similar-to) | Yes | No | No |
| **Deterministic citation matching** | arXiv + DOI + fuzzy title | Partial | No |
| **Auto-linking to existing findings** | Pre-filter + single LLM pass, ≤30 candidates | No | No |
| **Cross-paper contradiction surfacing** | Yes, bidirectional + view page | No | No |
| **Cost scales with graph size** | Constant (capped candidates) | — | Linear in context |
| **Vault is yours** | Plain Obsidian vault, wikilinks + frontmatter | Yes | No |
| **Local model support** | Ollama via `ANTHROPIC_BASE_URL` | — | No |
| **Open source** | MIT | Varies | No |

The model never sees the whole vault. A pre-filter hands it ≤30 candidate findings as `{slug, statement, fields}` triples, so **linking cost is flat — the 100th paper costs the same as the 10th.**

---

## Quick Start

### 1. Install the plugin

```bash
claude --plugin-dir /path/to/claude-paperloom
```

On first run, Claude Code prompts for `vault_path` (default `~/PaperLoom`).

### 2. Set up Python deps

All slash commands invoke Python via `${CLAUDE_PLUGIN_ROOT}/.venv/bin/python3`, so the plugin expects a venv at the plugin root.

```bash
cd /path/to/claude-paperloom
python3.11 -m venv .venv        # or any Python ≥3.9
.venv/bin/pip install pyyaml pymupdf
```

- `pyyaml` — YAML frontmatter read/write.
- `pymupdf` — PDF text extraction.

### 3. Scaffold your vault

```
/paperloom:init
```

Seeds `~/PaperLoom` with the schema, templates, five pre-built Dataview views, and the Dataview plugin itself pre-installed into `.obsidian/`. Open the folder in Obsidian and turn off Restricted Mode once to activate Dataview.

### 4. Ingest your first paper

```
/paperloom:ingest https://arxiv.org/abs/1706.03762
```

---

## Commands

| You run | Claude does |
|---|---|
| `/paperloom:init [path]` | Scaffold the vault. Idempotent. Seeds Dataview. |
| `/paperloom:ingest <url\|arxiv-id\|doi\|pdf>` | Fetch, summarize, extract findings, link. Skips the paper if arXiv ID / DOI / source URL already in vault. |
| `/paperloom:query <question>` | Search + synthesize across the vault with wikilink citations. |
| `/paperloom:lint` | Health check. Auto-wires near-duplicate findings with bidirectional `similar-to` unless `--no-link-similar`. |

---

## The Ingest Pipeline

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

---

## How Linking Works

Five layers, four deterministic. The LLM only sees ≤30 candidate findings — never the whole vault.

| Layer | Mechanism | LLM? |
|---|---|---|
| **Entity stubs** | `create_stubs.py` materializes missing `authors/*.md` / `fields/*.md` as Obsidian wikilinks | no |
| **Citations** (paper → paper) | `citation_match.py` matches references by arXiv ID → DOI → fuzzy title (ratio ≥ 0.85) → first-author+year | no |
| **Candidate pre-filter** | `vault_scan.py findings-candidates` scores every vault finding by `field_overlap × 2 + author_overlap`; keeps top 30 | no |
| **Finding edges** (typed) | `finding-linker` ranks within the 30 and assigns one of `supports` / `contradicts` / `extends` / `uses` / `similar-to` (≤5 per new finding) | **yes (the only linking LLM call)** |
| **Paper edges** (aggregated) | `apply_edges.py` rolls finding edges up: `uses` → `builds-on`; others keep their name; self-loops skipped; `contradicts` + `similar-to` mirrored | no |
| **Near-dup similar-to** | `lint.py` normalizes statements, wires bidirectional `similar-to` on `difflib` ratio ≥ 0.92 | no |

---

## Section Detection

How `fetch_paper.py` picks which pages to feed downstream agents — three strategies, cascaded:

1. **PDF outline (TOC)** — `doc.get_toc()` gives `[level, title, page]`. Sections whose title matches the cue regex are kept through the next sibling heading. Usable on most arXiv / journal papers.
2. **Font-size heading detection** — body size is the character-count-weighted mode of all spans; headings are lines whose largest span exceeds 1.1× body size and are ≤120 chars. A matching heading's page range extends to the next heading.
3. **Page-header regex** — fallback only; a page is kept if its first 500 chars contain a cue word.

Strategies 1 and 2 are unioned; the regex fallback fires only if neither matched. First 3 pages and last 2 pre-bibliography pages are always included.

---

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

---

## Vault Layout

```
<vault>/
├── CLAUDE.md          # authoritative schema — edit carefully
├── index.md           # Dataview-powered catalog
├── log.md             # append-only action log
├── papers/            # one .md per paper (4-section summary + metadata)
├── findings/          # one .md per atomic finding — the KG nodes
├── authors/           # entity stubs with backlinks
├── fields/            # entity stubs with backlinks
├── views/             # pre-built Dataview views
│   ├── by-author.md
│   ├── by-field.md
│   ├── contradictions.md
│   ├── high-credibility.md
│   └── recent-papers.md
└── .sources/          # cached raw PDFs / HTML + text slices, keyed by sha256
```

Obsidian's Graph View renders the whole thing for free. Filtering is Dataview queries over frontmatter.

---

## Models

Configured per plugin via `.claude-plugin/plugin.json`:

| Key | Default | Used by |
|---|---|---|
| `model_normal` | `claude-haiku-4-5` | `finding-extractor`, `finding-linker`, `metadata-extractor` |
| `model_reasoning` | `claude-sonnet-4-6` | `lite-drafter` (critique / critical thinking) |

Point either at an Ollama model name and set `ANTHROPIC_BASE_URL=http://localhost:11434/v1` to run locally.

---

## Token Cost Per Ingest

| Stage | Input | Model | Notes |
|---|---|---|---|
| `finding-extractor` | findings slice (~40–60% of paper) | Haiku | heaviest in tokens |
| `lite-drafter` | brief (~10–25%) | Sonnet | pricier per token |
| `metadata-extractor` | first 2 pages (~5%) | Haiku | tight |
| `finding-linker` | ≤30 × `{slug, statement, fields}` | Haiku | tiny, **graph-size-independent** |

Scripts, lint, vault scan, citation match, stub creation, edge aggregation: **0 tokens**.

---

## File Structure

```
claude-paperloom/
├── .claude-plugin/
│   └── plugin.json              # manifest + userConfig
├── commands/                    # thin slash-command orchestrators
│   ├── init.md
│   ├── ingest.md
│   ├── query.md
│   └── lint.md
├── agents/                      # four semantic LLM subagents
│   ├── lite-drafter.md          # 4-section triage summary
│   ├── finding-extractor.md     # atomic findings
│   ├── metadata-extractor.md    # title/authors/date/venue/fields/quality
│   └── finding-linker.md        # typed edges (the only linking LLM call)
├── scripts/                     # the only writers to the vault
│   ├── fetch_paper.py           # sniff + download + extract 4 text slices
│   ├── vault_scan.py            # read-only scans (fields, papers, authors, candidates)
│   ├── assemble_paper.py        # template fill + quality.overall + slug
│   ├── assemble_finding.py      # write findings/*.md
│   ├── citation_match.py        # deterministic bibliographic matching
│   ├── apply_edges.py           # write edges, mirror, aggregate to paper-level
│   ├── create_stubs.py          # missing author/field stubs
│   ├── init_vault.py            # scaffold vault + seed .obsidian/
│   ├── lint.py                  # orphans, dupes, schema drift, stale links
│   └── log.py                   # append-only action log
├── templates/                   # page templates filled by scripts
│   ├── paper-lite.md
│   ├── finding.md
│   ├── author.md
│   ├── field.md
│   ├── index.md
│   ├── CLAUDE.md                # seeded schema inside the vault
│   ├── views/                   # five pre-built Dataview views
│   └── dot-obsidian/            # bundled .obsidian/ (Dataview pre-installed)
└── README.md                    # this file
```

Repetitive / deterministic work lives in scripts so it's fast, cheap, and reproducible. LLMs are used only where semantic judgment is required.

---

## Design Principles

- **Scripts are the only writers.** Agents return JSON; Python writes the vault.
- **No per-item LLM loops.** If the pipeline ever iterates an agent over a list, it's refactored into a script.
- **The LLM never sees the whole vault.** Pre-filters and caps keep linking cost flat.
- **Deterministic where possible.** Section detection, citation matching, edge aggregation, stub creation, lint — all pure Python.
- **Obsidian-native.** Plain wikilinks + YAML frontmatter. No custom app, no lock-in. Your vault works the day the plugin stops existing.

---

## Out of Scope (v0.1)

- Deep / multi-agent ingest mode with figure extraction.
- Embeddings-based finding deduplication (v0.1 uses normalized-string + Levenshtein via `difflib`).
- Auto-sync on vault edits (no hooks).
- Multi-vault, Obsidian Sync, iCloud paths.

---

## License

MIT.
