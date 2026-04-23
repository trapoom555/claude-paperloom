---
description: Lite ingest — fetch a paper and write a short 4-section triage summary (Key Takeaways, Background, Main Idea & Summary, Critique). No figures, fast.
argument-hint: "<url | arxiv-id | doi | pdf-path>"
---

# /research-librarian:ingest

Fast, triage-grade ingest. `$ARGUMENTS` is the paper reference.

**Division of labor**: the deterministic steps (fetch, parse, template fill, edge aggregation, logging, stub creation, citation matching) are done by Python scripts in `${CLAUDE_PLUGIN_ROOT}/scripts/`. The LLM is used only for the three remaining semantic subagents: `lite-drafter`, `finding-extractor`, `metadata-extractor`. Per-item LLM loops are forbidden — if you find yourself running an agent N times for N items, stop and shell out to a script.

## Step 0 — greet the user

Print exactly:
> 📖 Ingesting your paper — this will take a moment. Sit back, get cozy, and maybe grab a coffee ☕️

## Step 1 — fetch + extract

Shell out. The script validates the vault, classifies the input, caches the raw file, and produces full + brief text:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fetch_paper.py" "<vault-path>" "$ARGUMENTS"
```

Parse the JSON result. Keep `full_text_path`, `brief_text_path`, `source_url`, `arxiv_id`, `doi` for later steps.

## Step 2 — scan vault for context

Run these in parallel (they're independent reads):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vault_scan.py" fields  "<vault-path>"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vault_scan.py" papers  "<vault-path>"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vault_scan.py" authors "<vault-path>"
```

Hold the outputs: `existing_fields`, `vault_papers`, `existing_authors`.

## Step 3 — fan-out: 2 LLM subagents (semantic-only)

Launch in **one parallel message**:

| Agent | Model | Input | Purpose |
|---|---|---|---|
| `lite-drafter` | `model_reasoning` | `brief_text_path` | returns the 4 sections JSON |
| `finding-extractor` | `model_normal` | `full_text_path` | returns atomic findings JSON |

**Do not spawn a citation-linker agent** — bibliographic matching is deterministic and runs in step 6 via `citation_match.py`.

## Step 4 — metadata (after lite-drafter)

Once `lite-drafter` returns, spawn `metadata-extractor` (`model_normal`) with:
- `paper_text_path` = `brief_text_path` (title/authors/date/venue/quality)
- `summary_text` = the concatenated markdown returned by `lite-drafter` (for `fields`)
- `existing_fields` = list from step 2
- `source_url`, `arxiv_id`, `doi` = from step 1

The agent returns metadata JSON. It does NOT compute `quality.overall` or the slug — the assembly script does both.

## Step 5 — assemble the paper page

Build the payload (metadata + sections + source_url + empty findings/relations) and pipe to:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/assemble_paper.py" --input /tmp/paper_payload.json
```

The script computes `quality.overall`, generates `slug` if absent, fills `templates/paper-lite.md`, and writes `<vault>/papers/<slug>.md`. It refuses to overwrite unless `overwrite: true` is set in the payload — ask the user first.

Capture the returned `slug`.

## Step 6 — in parallel: findings, citations, candidates, stubs

Launch all four at once — they're independent:

```bash
# 6a. Write finding files in one script call.
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/assemble_finding.py" --input /tmp/findings_payload.json

# 6b. Deterministic citation matching. Feed vault_papers from step 2.
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/citation_match.py" \
    "<full_text_path>" <(echo "$VAULT_PAPERS_JSON") \
    --own-slug "<slug>"

# 6c. Candidate finding shortlist for finding-linker.
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vault_scan.py" findings-candidates "<vault-path>" \
    --fields <metadata.fields joined by ,> \
    --authors "<metadata.authors joined by ;>" \
    --cap 50

# 6d. Missing author/field stubs.
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/create_stubs.py" --input /tmp/stubs_payload.json
```

Now update the paper page's `findings:` frontmatter with the new slugs:

```bash
# Re-run assemble_paper.py with overwrite:true and findings: [...] populated.
```

(Or, equivalently, edit just the frontmatter via a targeted Edit on `<vault>/papers/<slug>.md`.)

## Step 7 — finding-linker (the last LLM step)

Spawn **`finding-linker`** (`model_normal`) **once**, with:
- `new_findings` = the slugs + statements + fields written in 6a
- `candidate_existing_findings` = output of 6c

It returns typed-edge proposals. Pipe them to:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/apply_edges.py" --input /tmp/edges_payload.json
```

The script:
- writes edges into each new finding's `relations.*`,
- mirrors `contradicts` / `similar-to` onto target findings,
- aggregates finding edges to paper-level relations (`uses→builds-on`, `supports`, `extends`, `contradicts`, `similar-to`),
- mirrors bidirectional paper edges onto target papers,
- merges with `cites` from 6b into the new paper's `relations.cites`.

Pass `cites` from 6b inside the same payload.

## Step 8 — log

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/log.py" "<vault-path>" ingest-lite "<slug>" \
    "<n> findings, <e> edges"
```

## Step 9 — lint

Invoke lint scoped to the findings just written, so the dedup check only considers the new set against the existing vault (not all-pairs):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lint.py" "<vault-path>" \
    --new-slugs "<finding-slug-1>,<finding-slug-2>,..."
```

`--link-similar` is on by default — any near-duplicate pairs found get bidirectional `similar-to` edges automatically. Display the report inline.

## Step 10 — open (optional)

If `${CLAUDE_PLUGIN_CONFIG:open_in_obsidian}` is truthy, print (don't auto-run):

```
open "obsidian://open?vault=<vault-basename>&file=papers/<slug>"
```

## Report back

End-of-run summary:
- paper slug + `quality.overall`
- finding count
- new vs existing field/author stubs (from 6d output)
- edge counts by type (from apply_edges)

## Guardrails

- **Scripts do the writing.** The LLM only produces JSON payloads for the scripts to consume.
- **No per-item LLM loops.** If you catch yourself iterating an agent over a list, stop and script it.
- **Do not embed figures.** Lite mode is text-only.
- **Do not overwrite** an existing `papers/<slug>.md` without asking.
- If `finding-extractor` returns zero findings, warn the user — the paper may have been abstract-only.
