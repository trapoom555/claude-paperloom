# claude-research-librarian

A Claude Code plugin that turns a local [Obsidian](https://obsidian.md) vault into a Karpathy-style [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) for research papers.

Drop in a paper URL / arXiv ID / DOI / local PDF and the plugin:

1. Fetches and reads the paper.
2. Writes a concise 9-section summary (Background & Motivation → Related Work & Gaps → Core Idea & Contributions → Method → Experimental Setup → Results & Analysis → Discussion & Implications → Limitations & Open Questions → Key Takeaways) into the vault with section/page source references.
3. Extracts per-paper metadata: authors, publication date, research fields, venue, and a paper-quality assessment (credibility, experimental rigor, reproducibility).
4. Extracts **atomic claims** as first-class nodes and links them to existing claims with typed edges: `supports`, `contradicts`, `extends`, `uses`, `similar-to`.
5. Maintains entity pages for authors and fields, plus an append-only action log and a Dataview-powered catalog.

The knowledge graph is Obsidian-native: wikilinks + YAML frontmatter + [Dataview](https://blacksmithgu.github.io/obsidian-dataview/). Obsidian's built-in Graph View renders the whole thing for free, and filtering is Dataview queries over frontmatter.

## Install (local / development)

```bash
claude --plugin-dir /path/to/claude-research-librarian
```

On first run, Claude Code will prompt for `vault_path` (default `~/ResearchLibrarian`).

### Dependencies

Python 3 with:

- `pyyaml` — YAML frontmatter read/write (required).
- `pymupdf` — PDF text + brief extraction (required for PDF/arXiv input).

```bash
pip install pyyaml pymupdf
```

### How the plugin is structured

- `commands/*.md` — slash commands. Thin orchestrators that shell out to scripts.
- `agents/*.md` — three semantic LLM subagents (`lite-drafter`, `finding-extractor`, `metadata-extractor`, `finding-linker`). They return JSON; they never write files.
- `scripts/*.py` — deterministic work (fetch, text extraction, template assembly, edge aggregation, lint, log, citation matching). These are the only writers to the vault.
- `templates/*.md` — the actual page templates. Filled by scripts.

Repetitive/deterministic work goes in scripts so it's fast, cheap, and reproducible. LLMs are used only where semantic judgment is required.

## Setup

```
/research-librarian:init
```

Seeds the vault. Then in Obsidian:

1. Open the vault folder.
2. Settings → Community Plugins → enable → browse → install **Dataview**.
3. (Optional) install **Obsidian Git** if you want vault history.

## Commands

| Command | What it does |
|---|---|
| `/research-librarian:init [path]` | Scaffold the vault. Idempotent. |
| `/research-librarian:ingest <url\|arxiv-id\|doi\|pdf>` | **Lite ingest** — fast triage. 4-section summary (Key Takeaways, Background, Main Idea & Summary, Critique). No figures. ~30–60s. |
| `/research-librarian:ingest-full <url\|arxiv-id\|doi\|pdf>` | **Deep ingest** — full 10-section summary with embedded figures, parallel 5-agent fan-out. ~90–120s. |
| `/research-librarian:query <question>` | Search + synthesize across the vault with wikilink citations. |
| `/research-librarian:filter <k=v ...>` | Generate a Dataview filter page and print matching items. |
| `/research-librarian:lint` | Scan for orphans, schema drift, duplicate claims, asymmetric contradictions, stale wikilinks. |
| `/research-librarian:claim <slug-or-title>` | Drill into a single claim: statement, source, one-hop neighbors, backlinks. |

**When to use which ingest:** `ingest` for triaging a reading list — you want to know if a paper is worth your time. `ingest-full` for the ones you decide to study. You can always upgrade a lite paper later by running `ingest-full` on the same URL; the KG edges and claims from the first pass are preserved.

### Ingest pipelines

**Lite** (`/research-librarian:ingest`):
1. Sniff input, fetch, cache text to `<vault>/.sources/<sha>.txt`. Skip figure extraction.
2. Fan out **3 agents in parallel**: `lite-drafter` (4-section digest), `metadata-extractor` (frontmatter + quality), `claim-extractor` (claims). Main agent concurrently builds the claim-linker candidate shortlist and the missing-stub set.
3. Assemble `papers/<slug>.md` with `ingest-mode: lite` from `templates/paper-lite.md`.
4. Parallel claim file writes.
5. Second fan-out: `claim-linker` ∥ entity-stub creation.
6. Log.

**Full** (`/research-librarian:ingest-full`):
1. Sniff, fetch, cache text + **extract figures** to `<vault>/assets/<slug>/`.
2. Fan out **5 agents in parallel**: `drafter-foundations` (§2/§3/§4), `drafter-method` (§5/§6/§7), `drafter-reflection` (§8/§9/§10, on Opus), `claim-extractor` (Haiku), `metadata-extractor`. Main agent concurrently builds shortlist + missing-stub set.
3. Main synthesizes §1 Key Takeaways; assembles `papers/<slug>.md` with `ingest-mode: full` from `templates/paper.md`.
4. Parallel claim file writes.
5. Second fan-out: `claim-linker` ∥ entity-stub creation.
6. Log.

**Upgrade path**: running `ingest-full` on a paper already ingested in lite mode detects `ingest-mode: lite` in frontmatter and upgrades the body in place while preserving existing claims and KG edges.

## Filter keys

```
/research-librarian:filter field=nlp author="Vaswani, Ashish" after=2024-01-01 credibility>=4
```

Supported: `type`, `field`, `author`, `after`, `before`, `ingested-after`, `ingested-before`, `credibility>=`, `rigor>=`, `venue`, `reproducibility`, `hedging`, `claim-type`.

## Vault layout

```
<vault>/
├── CLAUDE.md          # authoritative schema — edit carefully
├── index.md           # Dataview-powered catalog
├── log.md             # append-only action log
├── papers/            # one .md per paper (9-section summary + metadata)
├── claims/            # one .md per atomic claim (the KG nodes)
├── authors/           # entity stubs with backlinks
├── fields/            # entity stubs with backlinks
├── views/             # Dataview filter pages (pre-built + /filter-generated)
├── syntheses/         # /query answers, optionally saved
└── .sources/          # cached raw PDFs / HTML, keyed by sha256
```

## Relation types

| Edge | Meaning | Symmetry |
|---|---|---|
| `supports` | Provides evidence for target | directed |
| `contradicts` | Asserts something incompatible | bidirectional |
| `extends` | Builds on target, broader/stronger form | directed |
| `uses` | Relies on target as method/tool | directed |
| `similar-to` | Independently-derived near-identical claim | bidirectional |

## Out of scope (v0.1)

- Embeddings-based claim deduplication (v0.1 uses normalized-string + Levenshtein).
- Auto-sync on vault edits (no hooks).
- Multi-vault, Obsidian Sync, iCloud paths.

## License

MIT.
