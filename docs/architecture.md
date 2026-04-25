# Architecture

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

## Plugin File Structure

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
└── README.md
```

Repetitive / deterministic work lives in scripts so it's fast, cheap, and reproducible. LLMs are used only where semantic judgment is required.

## Design Principles

- **Scripts are the only writers.** Agents return JSON; Python writes the vault.
- **No per-item LLM loops.** If the pipeline ever iterates an agent over a list, it's refactored into a script.
- **The LLM never sees the whole vault.** Pre-filters and caps keep linking cost flat.
- **Deterministic where possible.** Section detection, citation matching, edge aggregation, stub creation, lint — all pure Python.
- **Obsidian-native.** Plain wikilinks + YAML frontmatter. No custom app, no lock-in. Your vault works the day the plugin stops existing.

## Out of Scope (v0.1)

- Deep / multi-agent ingest mode with figure extraction.
- Embeddings-based finding deduplication (v0.1 uses normalized-string + Levenshtein via `difflib`).
- Auto-sync on vault edits (no hooks).
- Multi-vault, Obsidian Sync, iCloud paths.
